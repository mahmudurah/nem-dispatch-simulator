"""
Comprehensive Real NSW Market Data Extraction & Analytics
==========================================================
Extracts official AEMO dispatch data for NSW1 across 2024, 2025, and 2026,
and executes deep statistical and market analytics:
1. Wholesale Price Distribution & Extreme Volatility Analysis
2. Negative Price Frequency & The Midday Solar Duck Curve
3. The 5-9 PM Evening Peak Ramp & The Battery Arbitrage Spread
4. Renewable Penetration & Interconnector Dependence
"""

import os
import sys
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Tuple
import nemosis

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
CACHE_DIR = os.path.join(DATA_DIR, 'nemosis_cache')
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'output')

def extract_nsw_multiyear_dataset(
    years = ['2024', '2025', '2026'],
    month_day_range = ("01/01 00:00:00", "01/25 23:55:00")
) -> pd.DataFrame:
    """
    Extract and harmonize AEMO dispatch records for NSW1 across multiple years.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    frames = []

    print("\n" + "=" * 70)
    print(" 1. EXTRACTING REAL AEMO DISPATCH DATA FOR NSW1 (2024, 2025, 2026)")
    print("=" * 70)

    for yr in years:
        start_time = f"{yr}/{month_day_range[0]}"
        end_time   = f"{yr}/{month_day_range[1]}"
        print(f" -> Fetching NSW1 data for {yr} ({start_time} to {end_time})...")

        # 1. Prices (DISPATCHPRICE)
        df_price = nemosis.dynamic_data_compiler(
            start_time=start_time,
            end_time=end_time,
            table_name="DISPATCHPRICE",
            raw_data_location=CACHE_DIR,
            select_columns=["SETTLEMENTDATE", "REGIONID", "RRP"],
            filter_cols=["REGIONID"],
            filter_values=(["NSW1"],),
            keep_csv=False
        )

        # 2. Regional Demand & Renewables & Interconnectors (DISPATCHREGIONSUM)
        df_region = nemosis.dynamic_data_compiler(
            start_time=start_time,
            end_time=end_time,
            table_name="DISPATCHREGIONSUM",
            raw_data_location=CACHE_DIR,
            select_columns=["SETTLEMENTDATE", "REGIONID", "TOTALDEMAND", "NETINTERCHANGE", "SEMISCHEDULE_CLEAREDMW"],
            filter_cols=["REGIONID"],
            filter_values=(["NSW1"],),
            keep_csv=False
        )

        df_price['SETTLEMENTDATE'] = pd.to_datetime(df_price['SETTLEMENTDATE'])
        df_region['SETTLEMENTDATE'] = pd.to_datetime(df_region['SETTLEMENTDATE'])

        merged = pd.merge(df_price, df_region[['SETTLEMENTDATE', 'TOTALDEMAND', 'NETINTERCHANGE', 'SEMISCHEDULE_CLEAREDMW']], on='SETTLEMENTDATE')
        merged['Year'] = yr
        merged['RRP'] = pd.to_numeric(merged['RRP'], errors='coerce')
        merged['TOTALDEMAND'] = pd.to_numeric(merged['TOTALDEMAND'], errors='coerce')
        merged['NETINTERCHANGE'] = pd.to_numeric(merged['NETINTERCHANGE'], errors='coerce')
        merged['SEMISCHEDULE_CLEAREDMW'] = pd.to_numeric(merged['SEMISCHEDULE_CLEAREDMW'], errors='coerce').fillna(0.0)
        
        frames.append(merged)
        print(f"    [OK] Loaded {len(merged):,} intervals for {yr}.")

    df_full = pd.concat(frames, ignore_index=True)
    df_full['Hour'] = df_full['SETTLEMENTDATE'].dt.hour
    df_full['Date'] = df_full['SETTLEMENTDATE'].dt.date
    return df_full

def perform_market_analytics(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Perform quantitative analytics on the extracted multi-year dataset.
    """
    print("\n" + "=" * 70)
    print(" 2. EXECUTING QUANTITATIVE ENERGY MARKET ANALYTICS")
    print("=" * 70)

    # ---------------------------------------------------------
    # A. Annual Summary Statistics
    # ---------------------------------------------------------
    stats_list = []
    for yr, group in df.groupby('Year'):
        prices = group['RRP']
        demand = group['TOTALDEMAND']
        renewables = group['SEMISCHEDULE_CLEAREDMW']

        # Midday (10:00 - 14:00) vs Evening Peak (17:00 - 21:00)
        midday = group[(group['Hour'] >= 10) & (group['Hour'] <= 14)]
        evening = group[(group['Hour'] >= 17) & (group['Hour'] <= 21)]

        midday_avg_price = midday['RRP'].mean()
        evening_avg_price = evening['RRP'].mean()
        spread = evening_avg_price - midday_avg_price

        stats_list.append({
            'Year': yr,
            'Avg_Spot_Price_AUD': np.round(prices.mean(), 2),
            'Median_Spot_Price_AUD': np.round(prices.median(), 2),
            'Std_Dev_Spot_Price': np.round(prices.std(), 2),
            'Max_Spot_Price_AUD': np.round(prices.max(), 2),
            'Min_Spot_Price_AUD': np.round(prices.min(), 2),
            'Negative_Price_Intervals_Pct': np.round((prices < 0).mean() * 100, 2),
            'Extreme_Spikes_Gt_300_Pct': np.round((prices > 300).mean() * 100, 2),
            'Avg_Operational_Demand_MW': np.round(demand.mean(), 1),
            'Peak_Demand_MW': np.round(demand.max(), 1),
            'Avg_Renewables_MW': np.round(renewables.mean(), 1),
            'Max_Renewables_MW': np.round(renewables.max(), 1),
            'Midday_Avg_Price_10_14': np.round(midday_avg_price, 2),
            'Evening_Peak_Avg_Price_17_21': np.round(evening_avg_price, 2),
            'Battery_Arbitrage_Spread_AUD': np.round(spread, 2)
        })

    df_summary = pd.DataFrame(stats_list)

    # ---------------------------------------------------------
    # B. Diurnal 24-Hour Profile by Year
    # ---------------------------------------------------------
    diurnal_price = df.groupby(['Hour', 'Year'])['RRP'].mean().unstack().round(2)
    diurnal_demand = df.groupby(['Hour', 'Year'])['TOTALDEMAND'].mean().unstack().round(1)
    diurnal_renewables = df.groupby(['Hour', 'Year'])['SEMISCHEDULE_CLEAREDMW'].mean().unstack().round(1)

    diurnal_df = pd.DataFrame({
        'Hour': list(range(24)),
        'Price_2024': diurnal_price['2024'].values,
        'Price_2025': diurnal_price['2025'].values,
        'Price_2026': diurnal_price['2026'].values,
        'Demand_2024': diurnal_demand['2024'].values,
        'Demand_2025': diurnal_demand['2025'].values,
        'Demand_2026': diurnal_demand['2026'].values,
        'Renewables_2024': diurnal_renewables['2024'].values,
        'Renewables_2025': diurnal_renewables['2025'].values,
        'Renewables_2026': diurnal_renewables['2026'].values,
    })

    return df_summary, diurnal_df, df

def export_and_print_insights(df_summary: pd.DataFrame, diurnal_df: pd.DataFrame):
    """
    Print formatted tables and export to disk.
    """
    print("\n--- Key Market Metrics by Year (NSW1 Summer Analysis) ---")
    cols_to_show = ['Year', 'Avg_Spot_Price_AUD', 'Median_Spot_Price_AUD', 'Max_Spot_Price_AUD', 'Negative_Price_Intervals_Pct', 'Evening_Peak_Avg_Price_17_21', 'Battery_Arbitrage_Spread_AUD', 'Peak_Demand_MW']
    print(df_summary[cols_to_show].to_string(index=False))

    print("\n--- 24-Hour Diurnal Price Curve ($/MWh) Across Years ---")
    print(diurnal_df[['Hour', 'Price_2024', 'Price_2025', 'Price_2026']].to_string(index=False))

    # Save exports
    summary_path = os.path.join(OUTPUT_DIR, 'nsw_real_market_multiyear_analysis.csv')
    diurnal_path = os.path.join(OUTPUT_DIR, 'nsw_real_market_diurnal_profiles.csv')

    df_summary.to_csv(summary_path, index=False)
    diurnal_df.to_csv(diurnal_path, index=False)
    print(f"\n[OK] Saved summary analytics to: {summary_path}")
    print(f"[OK] Saved 24-hour diurnal profiles to: {diurnal_path}")

if __name__ == "__main__":
    from typing import Tuple
    df_raw = extract_nsw_multiyear_dataset()
    df_summary, diurnal_df, df_full = perform_market_analytics(df_raw)
    export_and_print_insights(df_summary, diurnal_df)
