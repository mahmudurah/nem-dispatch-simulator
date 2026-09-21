"""
PLEXOS 2026 Annual Production Cost Study — NSW Electricity Grid
================================================================
Replicates an institutional 8,760-hour PLEXOS simulation run across all 365 days of 2026.
Produces:
1. PLEXOS Price Duration Curve (PDC)
2. Annual Generation Mix & Asset Capacity Factors
3. Reliability & Emissions Impact Matrix
4. Interactive PLEXOS Analyst Terminal Dashboard (HTML)

Author: Dr. Md Mahmudur Rahman (PhD)
"""

import os
import sys
import pandas as pd

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nem_simulator.plexos_engine import PLEXOSAnnualEngine
from nem_simulator.plexos_analyst_dashboard import generate_plexos_analyst_dashboard

def main():
    print("=" * 80)
    print("      PLEXOS 2026 ANNUAL PRODUCTION COST SIMULATION — NSW GRID (8,760h)")
    print("      Engine: Chronological Rolling Horizon (HiGHS LP) | Author: Dr. Md Mahmudur Rahman")
    print("=" * 80)

    # 1. Run NSW Roadmap 2030
    print("\n[STEP 1/2] Simulating 8,760 hours for Scenario: NSW_Roadmap_2030...")
    engine_roadmap = PLEXOSAnnualEngine("NSW_Roadmap_2030")
    res_roadmap = engine_roadmap.run(progress_callback=lambda d, total: print(f"  Day {d:03d}/{total} solved..."))

    # 2. Run Baseline 2024
    print("\n[STEP 2/2] Simulating 8,760 hours for Scenario: Baseline_2024...")
    engine_baseline = PLEXOSAnnualEngine("Baseline_2024")
    res_baseline = engine_baseline.run(progress_callback=lambda d, total: print(f"  Day {d:03d}/{total} solved..."))

    # 3. Print Executive Summary Comparison Table
    print("\n" + "=" * 80)
    print("            ANNUAL PLEXOS SIMULATION COMPARISON — 2026 FULL YEAR")
    print("=" * 80)

    metrics = [
        ("Total Annual Demand", f"{res_baseline.total_demand_gwh:,.1f} GWh", f"{res_roadmap.total_demand_gwh:,.1f} GWh"),
        ("Total Generation Delivered", f"{res_baseline.total_generation_gwh:,.1f} GWh", f"{res_roadmap.total_generation_gwh:,.1f} GWh"),
        ("Total Annual Wholesale Cost", f"${res_baseline.total_cost_million_aud:,.1f}M AUD", f"${res_roadmap.total_cost_million_aud:,.1f}M AUD"),
        ("Average Annual Spot Price", f"${res_baseline.average_spot_price_per_mwh:.2f} / MWh", f"${res_roadmap.average_spot_price_per_mwh:.2f} / MWh"),
        ("Total Carbon Emissions", f"{res_baseline.total_emissions_mtco2:.2f} Mt CO2-e", f"{res_roadmap.total_emissions_mtco2:.2f} Mt CO2-e"),
        ("Average Emissions Intensity", f"{res_baseline.emission_intensity_t_per_mwh:.3f} t/MWh", f"{res_roadmap.emission_intensity_t_per_mwh:.3f} t/MWh"),
        ("Unserved Energy (EUE)", f"{res_baseline.unserved_energy_mwh:,.1f} MWh", f"{res_roadmap.unserved_energy_mwh:,.1f} MWh"),
        ("Loss of Load Hours (LOLH)", f"{res_baseline.loss_of_load_hours} hours", f"{res_roadmap.loss_of_load_hours} hours"),
        ("Negative Spot Price Hours", f"{res_baseline.negative_price_hours} hours", f"{res_roadmap.negative_price_hours} hours"),
    ]

    df_comp = pd.DataFrame(metrics, columns=["Metric", "Baseline 2024", "NSW Roadmap 2030"])
    print(df_comp.to_string(index=False))

    # 4. Save Outputs
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output')
    os.makedirs(output_dir, exist_ok=True)

    csv_path = os.path.join(output_dir, 'plexos_2026_annual_comparison.csv')
    df_comp.to_csv(csv_path, index=False)
    print(f"\n[OK] Saved Annual PLEXOS Comparison Matrix to: {csv_path}")

    # Generate Analyst Dashboard for Roadmap
    html_path = os.path.join(output_dir, 'plexos_2026_analyst_dashboard.html')
    generate_plexos_analyst_dashboard(res_roadmap, html_path)
    print(f"[OK] Generated Interactive PLEXOS Analyst Dashboard at: {html_path}")
    print(f"     Open locally in browser: file://{os.path.abspath(html_path)}")

    # Capacity Factors CSV
    cf_path = os.path.join(output_dir, 'plexos_2026_asset_capacity_factors.csv')
    res_roadmap.capacity_factors_df.to_csv(cf_path, index=False)
    print(f"[OK] Saved Asset Capacity Factors to: {cf_path}")

    print("\n" + "=" * 80)
    print("   [SUCCESS] Full 2026 PLEXOS production cost simulation completed.")
    print("=" * 80)

if __name__ == '__main__':
    main()
