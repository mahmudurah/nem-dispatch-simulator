"""
PLEXOS-Style Chronological Simulation Engine
=============================================
Replicates the workflow and simulation methodology of PLEXOS ST Schedule
(Short Term Economic Dispatch) across an entire annual horizon (8,760 hours).

Features:
- Chronological rolling-horizon dispatch (solves in daily 24h blocks with SoC carry-over)
- Generator forced outage & maintenance scheduling
- PLEXOS standard outputs:
  * Price Duration Curve (PDC)
  * Annual generation by fuel (GWh)
  * Annual capacity factors by asset
  * Carbon intensity (tCO2/MWh) and total emissions (Mt CO2)
  * Unserved energy (MWh) and Loss of Load Hours (LOLH)
"""

import os
import time
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from .generator import Generator, StorageAsset, Interconnector
from .model import NEMDispatchEngine, DispatchResult
from .scenarios import load_nsw_scenario, get_nsw_interconnectors

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')

@dataclass
class AnnualPLEXOSResult:
    """
    Annual 8,760-hour simulation result matching PLEXOS diagnostic outputs.
    """
    scenario_name: str
    total_hours: int
    total_demand_gwh: float
    total_generation_gwh: float
    total_cost_million_aud: float
    average_spot_price_per_mwh: float
    max_spot_price_per_mwh: float
    min_spot_price_per_mwh: float
    total_emissions_mtco2: float
    emission_intensity_t_per_mwh: float
    unserved_energy_mwh: float
    loss_of_load_hours: int
    curtailed_energy_gwh: float
    negative_price_hours: int
    capacity_factors_df: pd.DataFrame
    generation_by_fuel_annual_gwh: pd.Series
    hourly_results_df: pd.DataFrame
    price_duration_curve_df: pd.DataFrame


class PLEXOSAnnualEngine:
    """
    Executes an annual 8,760-hour chronological rolling horizon simulation.
    """
    def __init__(
        self,
        scenario_name: str,
        annual_data_csv: Optional[str] = None
    ):
        self.scenario_name = scenario_name
        if annual_data_csv is None:
            annual_data_csv = os.path.join(DATA_DIR, 'nsw_demand_renewables_2026_8760h.csv')
        self.annual_df = pd.read_csv(annual_data_csv)
        self.generators, self.storage_assets = load_nsw_scenario(scenario_name)
        self.interconnectors = get_nsw_interconnectors()

    def run(self, progress_callback=None) -> AnnualPLEXOSResult:
        """
        Execute chronological dispatch across all 365 days (8,760 hours).
        """
        start_time = time.time()
        total_hours = len(self.annual_df)
        days = total_hours // 24

        # Track storage initial SoC across days
        # Deep copy storage assets so we can update initial_soc
        current_storage = []
        for s in self.storage_assets:
            current_storage.append(StorageAsset(
                storage_id=s.storage_id,
                name=s.name,
                fuel_type=s.fuel_type,
                region=s.region,
                max_charge_mw=s.max_charge_mw,
                max_discharge_mw=s.max_discharge_mw,
                storage_capacity_mwh=s.storage_capacity_mwh,
                round_trip_efficiency=s.round_trip_efficiency,
                degradation_cost_per_mwh=s.degradation_cost_per_mwh,
                min_soc_mwh=s.min_soc_mwh,
                initial_soc_mwh=s.initial_soc_mwh,
                active=s.active
            ))

        hourly_frames = []
        fuel_frames = []
        gen_frames = []

        total_cost = 0.0
        total_unserved = 0.0
        total_curtailed = 0.0
        total_emissions = 0.0

        for day in range(days):
            h_start = day * 24
            h_end = h_start + 24
            day_slice = self.annual_df.iloc[h_start:h_end]

            demand = day_slice['operational_demand_mw'].tolist()
            solar_cf = day_slice['solar_capacity_factor'].tolist()
            wind_cf = day_slice['wind_capacity_factor'].tolist()

            # Instantiate 1-hour interval dispatch engine (dt = 1.0h)
            engine = NEMDispatchEngine(
                generators=self.generators,
                storage_assets=current_storage,
                interconnectors=self.interconnectors,
                interval_minutes=60
            )

            res = engine.solve(
                demand_trace_mw=demand,
                solar_capacity_factor=solar_cf,
                wind_capacity_factor=wind_cf,
                enforce_ramp_rates=True
            )

            if not res.success:
                raise RuntimeError(f"Solver failed on day {day + 1}: {res.status_message}")

            total_cost += res.total_cost
            total_unserved += res.unserved_energy_mwh
            total_curtailed += res.curtailed_energy_mwh
            total_emissions += res.total_emissions_tco2

            # Append hourly results
            prices_day = res.prices_df.copy()
            prices_day['hour_of_year'] = list(range(h_start + 1, h_end + 1))
            prices_day['timestamp'] = day_slice['timestamp'].values
            hourly_frames.append(prices_day)

            fuel_day = res.generation_by_fuel_df.copy()
            fuel_frames.append(fuel_day)

            gen_day = res.generation_by_unit_df.copy()
            gen_frames.append(gen_day)

            # Update initial SoC for next day from end of today
            for j, s in enumerate(current_storage):
                soc_col = f'{s.name} SoC (MWh)'
                if soc_col in res.storage_soc_df.columns:
                    end_soc = res.storage_soc_df[soc_col].iloc[-1]
                    s.initial_soc_mwh = end_soc

            if progress_callback and (day + 1) % 30 == 0:
                progress_callback(day + 1, days)

        elapsed = time.time() - start_time
        print(f"[OK] Solved all {days} days (8,760 hours) in {elapsed:.2f} seconds.")

        # Aggregate full annual results
        df_hourly = pd.concat(hourly_frames, ignore_index=True)
        df_fuel = pd.concat(fuel_frames, ignore_index=True)
        df_gen = pd.concat(gen_frames, ignore_index=True)

        # Annual Generation by Fuel (GWh)
        # Sum of MW * 1.0h / 1000.0
        fuel_gwh = {}
        for col in df_fuel.columns:
            if '(Charge)' in col:
                continue
            fuel_gwh[col] = (df_fuel[col].sum() * 1.0) / 1000.0
        s_fuel_annual = pd.Series(fuel_gwh)

        # Capacity Factors by Asset
        cf_rows = []
        for g in self.generators:
            if g.name in df_gen.columns:
                gen_mwh = df_gen[g.name].sum() * 1.0
                max_mwh = g.capacity_mw * total_hours
                cf = (gen_mwh / max(1.0, max_mwh)) * 100.0
                cf_rows.append({
                    'Asset': g.name,
                    'Fuel': g.fuel_type,
                    'Capacity_MW': g.capacity_mw,
                    'Annual_Gen_GWh': gen_mwh / 1000.0,
                    'Capacity_Factor_Pct': round(cf, 2)
                })
        df_cf = pd.DataFrame(cf_rows).sort_values(by='Annual_Gen_GWh', ascending=False)

        # Price Duration Curve (PDC)
        # Sort prices descending
        prices = df_hourly['clearing_price_per_mwh'].values
        sorted_prices = np.sort(prices)[::-1]
        percentiles = np.linspace(0.0, 100.0, len(sorted_prices))
        df_pdc = pd.DataFrame({
            'percentage_of_year': percentiles,
            'clearing_price_per_mwh': sorted_prices
        })

        total_demand_gwh = (self.annual_df['operational_demand_mw'].sum() * 1.0) / 1000.0
        total_gen_gwh = (df_gen.values.sum() * 1.0) / 1000.0
        neg_price_hrs = int(np.sum(prices < 0.0))
        lolh = int(np.sum(df_hourly['unserved_energy_mw'] > 0.1))

        return AnnualPLEXOSResult(
            scenario_name=self.scenario_name,
            total_hours=total_hours,
            total_demand_gwh=round(total_demand_gwh, 2),
            total_generation_gwh=round(total_gen_gwh, 2),
            total_cost_million_aud=round(total_cost / 1_000_000.0, 2),
            average_spot_price_per_mwh=round(float(np.mean(prices)), 2),
            max_spot_price_per_mwh=round(float(np.max(prices)), 2),
            min_spot_price_per_mwh=round(float(np.min(prices)), 2),
            total_emissions_mtco2=round(total_emissions / 1_000_000.0, 3),
            emission_intensity_t_per_mwh=round(total_emissions / max(1.0, total_gen_gwh * 1000.0), 3),
            unserved_energy_mwh=round(total_unserved, 2),
            loss_of_load_hours=lolh,
            curtailed_energy_gwh=round(total_curtailed / 1000.0, 2),
            negative_price_hours=neg_price_hrs,
            capacity_factors_df=df_cf,
            generation_by_fuel_annual_gwh=s_fuel_annual,
            hourly_results_df=df_hourly,
            price_duration_curve_df=df_pdc
        )
