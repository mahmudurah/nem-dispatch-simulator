"""
Step-by-Step Real Market Study for NSW (2025 & 2026)
===================================================
Fetches real AEMO market data using `nemosis`, formats the time series,
runs the HiGHS LP Economic Dispatch simulator, and compares simulated
merit order prices directly with actual AEMO wholesale clearing prices (RRP).
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Tuple
from nemosis import dynamic_data_compiler

# Add repo root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nem_simulator.generator import Generator, StorageAsset, Interconnector
from nem_simulator.scenarios import load_nsw_scenario, get_nsw_interconnectors, load_trace_data
from nem_simulator.model import NEMDispatchEngine, DispatchResult

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
CACHE_DIR = os.path.join(DATA_DIR, 'nemosis_cache')

def fetch_real_aemo_day(date_str: str) -> pd.DataFrame:
    """
    Step 1: Download real 5-minute AEMO dispatch data for NSW1 from NEMWEB.
    """
    start_time = f"{date_str} 00:00:00"
    end_time   = f"{date_str} 23:55:00"
    os.makedirs(CACHE_DIR, exist_ok=True)

    print(f"\n[Step 1] Downloading real AEMO dispatch data for NSW1 on {date_str}...")
    
    # Regional Demand & Intermittent (Renewable) generation
    df_region = dynamic_data_compiler(
        start_time=start_time,
        end_time=end_time,
        table_name="DISPATCHREGIONSUM",
        raw_data_location=CACHE_DIR,
        select_columns=["SETTLEMENTDATE", "REGIONID", "TOTALDEMAND", "NETINTERCHANGE", "SEMISCHEDULE_CLEAREDMW"],
        filter_cols=["REGIONID"],
        filter_values=(["NSW1"],),
        fformat="csv",
        keep_csv=False
    )

    # Regional Reference Price (RRP in $/MWh)
    df_price = dynamic_data_compiler(
        start_time=start_time,
        end_time=end_time,
        table_name="DISPATCHPRICE",
        raw_data_location=CACHE_DIR,
        select_columns=["SETTLEMENTDATE", "REGIONID", "RRP"],
        filter_cols=["REGIONID"],
        filter_values=(["NSW1"],),
        fformat="csv",
        keep_csv=False
    )

    df_region['SETTLEMENTDATE'] = pd.to_datetime(df_region['SETTLEMENTDATE'])
    df_price['SETTLEMENTDATE'] = pd.to_datetime(df_price['SETTLEMENTDATE'])

    merged = pd.merge(df_region, df_price[['SETTLEMENTDATE', 'RRP']], on='SETTLEMENTDATE', how='inner')
    merged = merged.sort_values('SETTLEMENTDATE').set_index('SETTLEMENTDATE')

    # Convert numeric fields
    merged['TOTALDEMAND'] = pd.to_numeric(merged['TOTALDEMAND'], errors='coerce')
    merged['NETINTERCHANGE'] = pd.to_numeric(merged['NETINTERCHANGE'], errors='coerce')
    merged['SEMISCHEDULE_CLEAREDMW'] = pd.to_numeric(merged['SEMISCHEDULE_CLEAREDMW'], errors='coerce').fillna(0.0)
    merged['RRP'] = pd.to_numeric(merged['RRP'], errors='coerce')

    print(f" -> Successfully retrieved {len(merged)} 5-minute AEMO intervals.")
    return merged

def process_to_30min_intervals(df_5min: pd.DataFrame) -> pd.DataFrame:
    """
    Step 2: Resample 5-minute data to 48 standard half-hour trading intervals.
    """
    print("[Step 2] Resampling 5-minute data to 30-minute trading intervals...")
    df_30min = df_5min[['TOTALDEMAND', 'NETINTERCHANGE', 'SEMISCHEDULE_CLEAREDMW', 'RRP']].resample('30min').mean().dropna()

    # Calculate intermittent renewable capacity factor based on NSW installed capacity (~4,100 MW existing)
    installed_renewable_capacity = 4100.0
    df_30min['renewable_cf'] = np.clip(df_30min['SEMISCHEDULE_CLEAREDMW'] / installed_renewable_capacity, 0.05, 1.0)

    print(f" -> Prepared {len(df_30min)} trading intervals for simulation.")
    return df_30min

def simulate_real_day(df_30min: pd.DataFrame, scenario_name: str = "Baseline_2024") -> Tuple[DispatchResult, pd.DataFrame]:
    """
    Step 3 & 4: Configure the physical grid and solve the LP economic dispatch.
    """
    print(f"[Step 3] Initializing generator fleet under '{scenario_name}' scenario...")
    gens, stor = load_nsw_scenario(scenario_name)
    interconnectors = get_nsw_interconnectors()

    demand_list = df_30min['TOTALDEMAND'].tolist()
    renewable_cf_list = df_30min['renewable_cf'].tolist()

    engine = NEMDispatchEngine(
        generators=gens,
        storage_assets=stor,
        interconnectors=interconnectors,
        interval_minutes=30
    )

    print(f"[Step 4] Solving multi-interval LP with HiGHS optimizer...")
    # Use real renewable capacity factor for solar and wind
    result = engine.solve(
        demand_trace_mw=demand_list,
        solar_capacity_factor=renewable_cf_list,
        wind_capacity_factor=renewable_cf_list,
        enforce_ramp_rates=True
    )

    if not result.success:
        raise RuntimeError(f"Solver failed: {result.status_message}")

    sim_prices = result.prices_df['clearing_price_per_mwh'].tolist()

    # Build comparison dataframe
    df_comp = pd.DataFrame({
        'Trading_Interval': [t.strftime('%H:%M') for t in df_30min.index],
        'Actual_NSW_Demand_MW': np.round(demand_list, 1),
        'Actual_Renewables_MW': np.round(df_30min['SEMISCHEDULE_CLEAREDMW'].values, 1),
        'Actual_AEMO_Price_AUD': np.round(df_30min['RRP'].values, 2),
        'Simulated_Model_Price_AUD': np.round(sim_prices, 2)
    })

    return result, df_comp

def run_study():
    dates = [
        ("2025/01/15", "Baseline_2024", "Summer 2025 Peak"),
        ("2026/01/15", "Baseline_2024", "Summer 2026 Peak")
    ]

    for date_str, sc_name, label in dates:
        print("\n" + "=" * 70)
        print(f" RUNNING REAL MARKET STUDY: {label} ({date_str})")
        print("=" * 70)

        # 1. Download
        df_5min = fetch_real_aemo_day(date_str)

        # 2. Resample
        df_30min = process_to_30min_intervals(df_5min)

        # 3 & 4. Simulate
        res, df_comp = simulate_real_day(df_30min, sc_name)

        # 5. Display comparison
        print("\n[Step 5] Sample Comparison Results (Morning & Midday Hours):")
        print(df_comp.iloc[14:26].to_string(index=False))

        avg_actual_price = df_comp['Actual_AEMO_Price_AUD'].mean()
        avg_sim_price = df_comp['Simulated_Model_Price_AUD'].mean()
        max_demand = df_comp['Actual_NSW_Demand_MW'].max()

        print("\n--- Key Performance Metrics ---")
        print(f" Peak NSW Demand:             {max_demand:,.1f} MW")
        print(f" Actual AEMO Average Price:   ${avg_actual_price:.2f} / MWh")
        print(f" Simulated Model Avg Price:   ${avg_sim_price:.2f} / MWh")
        print(f" Total Energy Generated:      {res.total_generation_mwh:,.1f} MWh")
        print(f" Carbon Emissions:            {res.total_emissions_tco2:,.1f} tCO2-e")
        print(f" Carbon Intensity:            {res.total_emissions_tco2 / res.total_generation_mwh:.3f} tCO2-e / MWh")

        # Save output
        out_name = f"real_vs_simulated_{date_str.replace('/', '')}.csv"
        out_file = os.path.join(DATA_DIR, out_name)
        df_comp.to_csv(out_file, index=False)
        print(f" Saved validation file to: {out_file}")

if __name__ == "__main__":
    from typing import Tuple
    run_study()
