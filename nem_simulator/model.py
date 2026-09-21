"""
Mathematical Optimization Dispatch Engine
==========================================
Formulates and solves the multi-interval Unit Commitment & Economic Dispatch (ED)
problem for the National Electricity Market (NEM) using Linear Programming (LP).

Solves the core optimization problem that commercial packages like PLEXOS solve:
Minimizes total system short-run marginal cost subject to physical constraints,
extracting the dual variables (shadow prices) as NEM Regional Reference Prices ($/MWh).
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional
from scipy.optimize import linprog
from dataclasses import dataclass, field

from .generator import Generator, StorageAsset, Interconnector

@dataclass
class DispatchResult:
    """
    Simulation result containing interval-by-interval dispatch, prices, and metrics.
    """
    success: bool
    status_message: str
    intervals: int
    interval_hours: float
    total_cost: float
    total_generation_mwh: float
    total_emissions_tco2: float
    average_price_per_mwh: float
    unserved_energy_mwh: float
    curtailed_energy_mwh: float
    summary_df: pd.DataFrame
    generation_by_unit_df: pd.DataFrame
    generation_by_fuel_df: pd.DataFrame
    storage_soc_df: pd.DataFrame
    prices_df: pd.DataFrame


class NEMDispatchEngine:
    """
    Multi-Interval NEM Economic Dispatch & Storage Co-Optimization Engine.
    """
    def __init__(
        self,
        generators: List[Generator],
        storage_assets: Optional[List[StorageAsset]] = None,
        interconnectors: Optional[List[Interconnector]] = None,
        market_price_cap: float = 17500.0,       # NEM Market Price Cap ($17,500/MWh)
        market_floor_price: float = -1000.0,     # NEM Market Floor Price (-$1,000/MWh)
        interval_minutes: int = 30               # 30-minute trading intervals (or 5-min)
    ):
        self.generators = [g for g in generators if g.active]
        self.storage_assets = [s for s in (storage_assets or []) if s.active]
        self.interconnectors = interconnectors or []
        self.market_price_cap = market_price_cap
        self.market_floor_price = market_floor_price
        self.interval_minutes = interval_minutes
        self.dt = interval_minutes / 60.0        # Interval duration in hours (e.g. 0.5h)

    def solve(
        self,
        demand_trace_mw: List[float],
        solar_capacity_factor: Optional[List[float]] = None,
        wind_capacity_factor: Optional[List[float]] = None,
        enforce_ramp_rates: bool = True
    ) -> DispatchResult:
        """
        Formulate and solve the Linear Programming multi-interval economic dispatch.
        """
        T = len(demand_trace_mw)
        N_g = len(self.generators)
        N_s = len(self.storage_assets)
        N_l = len(self.interconnectors)

        if solar_capacity_factor is None:
            solar_capacity_factor = [1.0] * T
        if wind_capacity_factor is None:
            wind_capacity_factor = [1.0] * T

        # Variable index offsets:
        # 1. Generation: p[i, t] -> N_g * T variables
        # 2. Storage Charge: c[j, t] -> N_s * T variables
        # 3. Storage Discharge: d[j, t] -> N_s * T variables
        # 4. Storage State-of-Charge: soc[j, t] -> N_s * T variables
        # 5. Interconnector Import: imp[l, t] -> N_l * T variables
        # 6. Unserved Energy / Deficit: def[t] -> T variables
        # 7. Curtailed Energy / Spill: curt[t] -> T variables

        idx_gen = 0
        idx_ch = idx_gen + N_g * T
        idx_dis = idx_ch + N_s * T
        idx_soc = idx_dis + N_s * T
        idx_imp = idx_soc + N_s * T
        idx_def = idx_imp + N_l * T
        idx_curt = idx_def + T
        total_vars = idx_curt + T

        def var_gen(i, t): return idx_gen + i * T + t
        def var_ch(j, t):  return idx_ch + j * T + t
        def var_dis(j, t): return idx_dis + j * T + t
        def var_soc(j, t): return idx_soc + j * T + t
        def var_imp(l, t): return idx_imp + l * T + t
        def var_def(t):    return idx_def + t
        def var_curt(t):   return idx_curt + t

        # -------------------------------------------------------------
        # 1. Objective Function (Minimize System Cost)
        # -------------------------------------------------------------
        c_obj = np.zeros(total_vars)

        for i, gen in enumerate(self.generators):
            for t in range(T):
                # Cost = SRMC * Output * dt
                c_obj[var_gen(i, t)] = gen.srmc_per_mwh * self.dt

        for j, stor in enumerate(self.storage_assets):
            for t in range(T):
                # Storage discharge degradation cost
                c_obj[var_dis(j, t)] = stor.degradation_cost_per_mwh * self.dt
                # Small negative penalty on charging to prefer charging when prices are low
                c_obj[var_ch(j, t)] = 0.001 * self.dt

        for l, ic in enumerate(self.interconnectors):
            for t in range(T):
                c_obj[var_imp(l, t)] = ic.marginal_cost_per_mwh * self.dt

        for t in range(T):
            # Heavy penalty on unserved energy (Market Price Cap = $17,500/MWh)
            c_obj[var_def(t)] = self.market_price_cap * self.dt
            # Small penalty on spill/curtailment to avoid artificial non-zero slack
            c_obj[var_curt(t)] = 0.01 * self.dt

        # -------------------------------------------------------------
        # 2. Variable Bounds (Lower and Upper Limits)
        # -------------------------------------------------------------
        bounds = [(0.0, None)] * total_vars

        for i, gen in enumerate(self.generators):
            for t in range(T):
                # Calculate available capacity based on fuel type
                cf = 1.0
                if gen.fuel_type.lower() == 'solar':
                    cf = solar_capacity_factor[t]
                elif gen.fuel_type.lower() == 'wind':
                    cf = wind_capacity_factor[t]
                
                avail = gen.available_capacity(cf)
                bounds[var_gen(i, t)] = (0.0, avail)

        for j, stor in enumerate(self.storage_assets):
            for t in range(T):
                bounds[var_ch(j, t)] = (0.0, stor.max_charge_mw)
                bounds[var_dis(j, t)] = (0.0, stor.max_discharge_mw)
                bounds[var_soc(j, t)] = (stor.min_soc_mwh, stor.storage_capacity_mwh)

        for l, ic in enumerate(self.interconnectors):
            for t in range(T):
                bounds[var_imp(l, t)] = (0.0, ic.reverse_limit_mw)

        for t in range(T):
            bounds[var_def(t)] = (0.0, None)
            bounds[var_curt(t)] = (0.0, None)

        # -------------------------------------------------------------
        # 3. Equality Constraints: Supply-Demand Balance & SoC Dynamics
        # -------------------------------------------------------------
        eq_rows = []
        b_eq = []

        # (a) Supply-Demand Balance for each interval t:
        # sum(gen) + sum(dis - ch) + sum(imp) + def - curt = Demand_t
        for t in range(T):
            row = np.zeros(total_vars)
            for i in range(N_g):
                row[var_gen(i, t)] = 1.0
            for j in range(N_s):
                row[var_dis(j, t)] = 1.0
                row[var_ch(j, t)] = -1.0
            for l in range(N_l):
                row[var_imp(l, t)] = 1.0
            row[var_def(t)] = 1.0
            row[var_curt(t)] = -1.0

            eq_rows.append(row)
            b_eq.append(demand_trace_mw[t])

        # (b) Storage State-of-Charge Dynamics:
        # soc[j, t] = soc[j, t-1] + eta_ch * ch[j, t] * dt - (1/eta_dis) * dis[j, t] * dt
        for j, stor in enumerate(self.storage_assets):
            # One-way efficiency: sqrt(round_trip)
            eta = np.sqrt(stor.round_trip_efficiency)
            eta_ch = eta
            inv_eta_dis = 1.0 / eta

            for t in range(T):
                row = np.zeros(total_vars)
                row[var_soc(j, t)] = 1.0
                row[var_ch(j, t)] = -eta_ch * self.dt
                row[var_dis(j, t)] = inv_eta_dis * self.dt

                if t == 0:
                    b_eq.append(stor.initial_soc_mwh)
                else:
                    row[var_soc(j, t - 1)] = -1.0
                    b_eq.append(0.0)

                eq_rows.append(row)

        A_eq = np.array(eq_rows) if eq_rows else None
        b_eq = np.array(b_eq) if b_eq else None

        # -------------------------------------------------------------
        # 4. Inequality Constraints: Thermal Ramp Rates
        # -------------------------------------------------------------
        ub_rows = []
        b_ub = []

        if enforce_ramp_rates:
            for i, gen in enumerate(self.generators):
                # Apply ramp limits to thermal baseload
                if gen.fuel_type in ['Black Coal', 'Gas CCGT']:
                    max_ramp_mw_per_interval = gen.ramp_rate_mw_per_min * self.interval_minutes
                    for t in range(1, T):
                        # Ramp Up: p[i, t] - p[i, t-1] <= max_ramp
                        row_up = np.zeros(total_vars)
                        row_up[var_gen(i, t)] = 1.0
                        row_up[var_gen(i, t - 1)] = -1.0
                        ub_rows.append(row_up)
                        b_ub.append(max_ramp_mw_per_interval)

                        # Ramp Down: p[i, t-1] - p[i, t] <= max_ramp
                        row_down = np.zeros(total_vars)
                        row_down[var_gen(i, t - 1)] = 1.0
                        row_down[var_gen(i, t)] = -1.0
                        ub_rows.append(row_down)
                        b_ub.append(max_ramp_mw_per_interval)

        A_ub = np.array(ub_rows) if ub_rows else None
        b_ub = np.array(b_ub) if b_ub else None

        # -------------------------------------------------------------
        # 5. Solve via HiGHS Solver
        # -------------------------------------------------------------
        res = linprog(
            c=c_obj,
            A_ub=A_ub,
            b_ub=b_ub,
            A_eq=A_eq,
            b_eq=b_eq,
            bounds=bounds,
            method='highs'
        )

        if not res.success:
            return DispatchResult(
                success=False,
                status_message=res.message,
                intervals=T,
                interval_hours=self.dt,
                total_cost=0.0,
                total_generation_mwh=0.0,
                total_emissions_tco2=0.0,
                average_price_per_mwh=0.0,
                unserved_energy_mwh=0.0,
                curtailed_energy_mwh=0.0,
                summary_df=pd.DataFrame(),
                generation_by_unit_df=pd.DataFrame(),
                generation_by_fuel_df=pd.DataFrame(),
                storage_soc_df=pd.DataFrame(),
                prices_df=pd.DataFrame()
            )

        # -------------------------------------------------------------
        # 6. Extract Results & Shadow Prices
        # -------------------------------------------------------------
        x_opt = res.x

        # Extract Dual Variables (Shadow Prices of Supply-Demand Balance)
        # In HiGHS, marginal of equality constraint represents change in cost per unit change in RHS
        # Price ($/MWh) = marginal / dt
        eq_marginals = res.eqlin.marginals if hasattr(res, 'eqlin') and res.eqlin is not None else None
        
        clearing_prices = []
        for t in range(T):
            if eq_marginals is not None and len(eq_marginals) > t:
                # Absolute value of marginal scaled by interval dt gives marginal price in $/MWh
                raw_price = abs(eq_marginals[t]) / self.dt
                # Bound within NEM price cap and floor
                price = max(self.market_floor_price, min(self.market_price_cap, raw_price))
            else:
                price = 0.0
            clearing_prices.append(price)

        # Build Unit Dispatch Matrix
        gen_matrix = np.zeros((T, N_g))
        for i in range(N_g):
            for t in range(T):
                gen_matrix[t, i] = x_opt[var_gen(i, t)]

        gen_cols = [g.name for g in self.generators]
        df_gen = pd.DataFrame(gen_matrix, columns=gen_cols)

        # Group by Fuel Type
        fuel_dict = {}
        for i, g in enumerate(self.generators):
            ft = g.fuel_type
            if ft not in fuel_dict:
                fuel_dict[ft] = np.zeros(T)
            fuel_dict[ft] += gen_matrix[:, i]

        df_fuel = pd.DataFrame(fuel_dict)

        # Storage Charge & Discharge & SoC
        storage_soc_dict = {}
        if N_s > 0:
            for j, s in enumerate(self.storage_assets):
                ch_vals = [x_opt[var_ch(j, t)] for t in range(T)]
                dis_vals = [x_opt[var_dis(j, t)] for t in range(T)]
                soc_vals = [x_opt[var_soc(j, t)] for t in range(T)]

                df_fuel[f'{s.name} (Discharge)'] = dis_vals
                df_fuel[f'{s.name} (Charge)'] = [-c for c in ch_vals]
                storage_soc_dict[f'{s.name} SoC (MWh)'] = soc_vals
                storage_soc_dict[f'{s.name} SoC (%)'] = [
                    (soc / s.storage_capacity_mwh) * 100.0 for soc in soc_vals
                ]

        # Interconnector Imports
        if N_l > 0:
            for l, ic in enumerate(self.interconnectors):
                imp_vals = [x_opt[var_imp(l, t)] for t in range(T)]
                df_fuel[ic.name] = imp_vals

        df_soc = pd.DataFrame(storage_soc_dict)

        # Unserved & Curtailed Energy
        unserved_mw = np.array([x_opt[var_def(t)] for t in range(T)])
        curtailed_mw = np.array([x_opt[var_curt(t)] for t in range(T)])

        # Emissions Calculation (tCO2-e)
        emissions_per_interval = np.zeros(T)
        for i, g in enumerate(self.generators):
            emissions_per_interval += gen_matrix[:, i] * g.emission_factor * self.dt

        total_emissions = float(np.sum(emissions_per_interval))
        total_gen_mwh = float(np.sum(gen_matrix) * self.dt)
        total_unserved_mwh = float(np.sum(unserved_mw) * self.dt)
        total_curtailed_mwh = float(np.sum(curtailed_mw) * self.dt)

        df_prices = pd.DataFrame({
            'interval': list(range(1, T + 1)),
            'demand_mw': demand_trace_mw,
            'clearing_price_per_mwh': clearing_prices,
            'emissions_tco2': emissions_per_interval,
            'unserved_energy_mw': unserved_mw,
            'curtailed_energy_mw': curtailed_mw
        })

        summary_df = pd.DataFrame([{
            'total_intervals': T,
            'total_demand_mwh': float(np.sum(demand_trace_mw) * self.dt),
            'total_generation_mwh': total_gen_mwh,
            'total_cost_aud': float(res.fun),
            'total_emissions_tco2': total_emissions,
            'avg_emission_intensity_t_per_mwh': total_emissions / max(1.0, total_gen_mwh),
            'average_spot_price_aud_per_mwh': float(np.mean(clearing_prices)),
            'max_spot_price_aud_per_mwh': float(np.max(clearing_prices)),
            'min_spot_price_aud_per_mwh': float(np.min(clearing_prices)),
            'unserved_energy_mwh': total_unserved_mwh,
            'curtailed_energy_mwh': total_curtailed_mwh
        }])

        return DispatchResult(
            success=True,
            status_message="Optimal dispatch solved successfully via HiGHS LP solver.",
            intervals=T,
            interval_hours=self.dt,
            total_cost=float(res.fun),
            total_generation_mwh=total_gen_mwh,
            total_emissions_tco2=total_emissions,
            average_price_per_mwh=float(np.mean(clearing_prices)),
            unserved_energy_mwh=total_unserved_mwh,
            curtailed_energy_mwh=total_curtailed_mwh,
            summary_df=summary_df,
            generation_by_unit_df=df_gen,
            generation_by_fuel_df=df_fuel,
            storage_soc_df=df_soc,
            prices_df=df_prices
        )
