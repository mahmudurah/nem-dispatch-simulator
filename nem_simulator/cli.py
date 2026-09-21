"""
Command-Line Interface for NEM Dispatch Simulator
==================================================
Usage:
    python -m nem_simulator.cli --compare --dashboard
    python -m nem_simulator.cli --scenario NSW_Roadmap_2030
"""

import os
import sys
import argparse
import pandas as pd

from .scenarios import run_scenario_comparison, load_nsw_scenario, load_trace_data, get_nsw_interconnectors
from .model import NEMDispatchEngine
from .visualization import generate_interactive_dashboard

def main():
    parser = argparse.ArgumentParser(
        description="NEM Dispatch Simulator — Unit Commitment & Economic Dispatch (HiGHS LP)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m nem_simulator.cli --compare --dashboard
  python -m nem_simulator.cli --scenario Baseline_2024
  python -m nem_simulator.cli --scenario NSW_Roadmap_2030 --output-dir results/
        """
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Run comparative analysis across Baseline, Eraring Exit, and NSW Roadmap 2030"
    )
    parser.add_argument(
        "--scenario",
        type=str,
        default="NSW_Roadmap_2030",
        help="Run a single scenario: Baseline_2024, Eraring_Retirement_Unfirmed, or NSW_Roadmap_2030"
    )
    parser.add_argument(
        "--dashboard",
        action="store_true",
        help="Generate interactive multi-panel Plotly HTML dashboard"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output",
        help="Directory to save output CSV summaries and HTML dashboards (default: output/)"
    )

    args = parser.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    print("=" * 75)
    print("      NEM Unit Commitment & Economic Dispatch Simulator")
    print("      Author: Dr. Md Mahmudur Rahman (PhD) | Engine: HiGHS LP")
    print("=" * 75)

    if args.compare or args.dashboard:
        print("\n[INFO] Running comparative policy scenarios across the NSW Grid...\n")
        results = run_scenario_comparison()

        summary_rows = []
        for name, res in results.items():
            print(f"--- Scenario: {name} ---")
            print(f"  Solver Status   : {res.status_message}")
            print(f"  Total Cost      : ${res.total_cost:,.2f} AUD")
            print(f"  Avg Spot Price  : ${res.average_price_per_mwh:.2f} / MWh")
            print(f"  Total Emissions : {res.total_emissions_tco2:,.1f} tCO2-e")
            print(f"  Unserved Energy : {res.unserved_energy_mwh:,.1f} MWh")
            print(f"  Curtailed Solar : {res.curtailed_energy_mwh:,.1f} MWh\n")

            row = res.summary_df.iloc[0].to_dict()
            row['scenario'] = name
            summary_rows.append(row)

        # Save comparative summary CSV
        df_comp = pd.DataFrame(summary_rows)
        comp_csv = os.path.join(args.output_dir, "scenario_comparison_summary.csv")
        df_comp.to_csv(comp_csv, index=False)
        print(f"[OK] Saved comparative metrics to: {comp_csv}")

        # Generate Dashboard if requested
        if args.dashboard:
            dash_path = os.path.join(args.output_dir, "nem_dispatch_dashboard.html")
            generate_interactive_dashboard(results, dash_path)
            print(f"[OK] Generated Interactive HTML Dashboard: {dash_path}")
            print(f"     Open in browser: file://{os.path.abspath(dash_path)}")

    else:
        print(f"\n[INFO] Executing single scenario: {args.scenario}...\n")
        traces = load_trace_data()
        demand = traces['operational_demand_mw'].tolist()
        solar_cf = traces['solar_capacity_factor'].tolist()
        wind_cf = traces['wind_capacity_factor'].tolist()
        interconnectors = get_nsw_interconnectors()

        gens, stor = load_nsw_scenario(args.scenario)
        engine = NEMDispatchEngine(
            generators=gens,
            storage_assets=stor,
            interconnectors=interconnectors,
            interval_minutes=30
        )
        res = engine.solve(
            demand_trace_mw=demand,
            solar_capacity_factor=solar_cf,
            wind_capacity_factor=wind_cf,
            enforce_ramp_rates=True
        )

        print(f"Solver Status   : {res.status_message}")
        print(f"Total Cost      : ${res.total_cost:,.2f} AUD")
        print(f"Avg Spot Price  : ${res.average_price_per_mwh:.2f} / MWh")
        print(f"Total Emissions : {res.total_emissions_tco2:,.1f} tCO2-e")
        print(f"Unserved Energy : {res.unserved_energy_mwh:,.1f} MWh")

        out_csv = os.path.join(args.output_dir, f"{args.scenario}_dispatch_summary.csv")
        res.prices_df.to_csv(out_csv, index=False)
        print(f"[OK] Detailed interval dispatch saved to: {out_csv}")

    print("\n[COMPLETE] Simulation workflow finished successfully.")

if __name__ == "__main__":
    main()
