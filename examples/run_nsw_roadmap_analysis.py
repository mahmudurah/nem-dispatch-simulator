"""
NSW Electricity Infrastructure Roadmap — Scenario Analysis Example
===================================================================
Executes a comparative simulation of the NSW Generation Fleet:
1. Baseline (2024 operating coal, gas, renewables, Waratah BESS)
2. Eraring Retirement Unfirmed (Simulating 2,880 MW thermal exit without replacement)
3. NSW Roadmap 2030 (3 GW Central-West Orana REZ + Long-Duration Storage + Batteries)

Author: Dr. Md Mahmudur Rahman (PhD)
"""

import os
import sys
import pandas as pd

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nem_simulator.scenarios import run_scenario_comparison
from nem_simulator.visualization import generate_interactive_dashboard

def main():
    print("=" * 75)
    print("   NSW ELECTRICITY INFRASTRUCTURE ROADMAP — DISPATCH SIMULATION")
    print("=" * 75)

    # 1. Run all scenarios
    results = run_scenario_comparison()

    # 2. Compile comparative metrics
    rows = []
    for name, res in results.items():
        row = {
            'Scenario': name,
            'Total Generation (GWh)': res.total_generation_mwh / 1000.0,
            'Total Daily Cost ($M AUD)': res.total_cost / 1_000_000.0,
            'Average Spot Price ($/MWh)': res.average_price_per_mwh,
            'Carbon Emissions (kt CO2-e)': res.total_emissions_tco2 / 1000.0,
            'Emission Intensity (t/MWh)': res.total_emissions_tco2 / max(1.0, res.total_generation_mwh),
            'Unserved Energy (MWh)': res.unserved_energy_mwh
        }
        rows.append(row)

    df_summary = pd.DataFrame(rows)
    print("\n--- POLICY SCENARIO SUMMARY MATRIX ---")
    print(df_summary.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))

    # 3. Output files
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output')
    os.makedirs(output_dir, exist_ok=True)

    summary_csv = os.path.join(output_dir, 'nsw_roadmap_policy_matrix.csv')
    df_summary.to_csv(summary_csv, index=False)
    print(f"\n[OK] Summary matrix saved to: {summary_csv}")

    dash_file = os.path.join(output_dir, 'nem_dispatch_dashboard.html')
    generate_interactive_dashboard(results, dash_file)
    print(f"[OK] Interactive Plotly dashboard generated at: {dash_file}")
    print(f"     Open locally: file://{os.path.abspath(dash_file)}")

    # 4. Key Takeaways
    base = df_summary.loc[df_summary['Scenario'] == 'Baseline_2024'].iloc[0]
    exit_sc = df_summary.loc[df_summary['Scenario'] == 'Eraring_Retirement_Unfirmed'].iloc[0]
    roadmap = df_summary.loc[df_summary['Scenario'] == 'NSW_Roadmap_2030'].iloc[0]

    price_spike_pct = ((exit_sc['Average Spot Price ($/MWh)'] - base['Average Spot Price ($/MWh)']) / base['Average Spot Price ($/MWh)']) * 100.0
    emissions_cut_pct = ((base['Carbon Emissions (kt CO2-e)'] - roadmap['Carbon Emissions (kt CO2-e)']) / base['Carbon Emissions (kt CO2-e)']) * 100.0
    cost_saving_pct = ((base['Total Daily Cost ($M AUD)'] - roadmap['Total Daily Cost ($M AUD)']) / base['Total Daily Cost ($M AUD)']) * 100.0

    print("\n--- STRATEGIC POLICY TAKEAWAYS FOR DCCEEW ---")
    print(f"1. Unfirmed Coal Exit Risk: If Eraring retires without firming, average spot price surges by +{price_spike_pct:.1f}%.")
    print(f"2. Roadmap Decarbonisation: Deploying CWO REZ and Long-Duration Storage cuts daily emissions by {emissions_cut_pct:.1f}%.")
    print(f"3. Economic Efficiency: The completed 2030 Roadmap lowers total daily wholesale cost by {cost_saving_pct:.1f}% vs Baseline.")
    print("=" * 75)

if __name__ == '__main__':
    main()
