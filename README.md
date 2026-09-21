# National Electricity Market (NEM) Dispatch & Unit Commitment Simulator

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Optimization: HiGHS LP](https://img.shields.io/badge/Solver-HiGHS%20LP-green.svg)](https://highs.dev/)
[![Target: NSW Roadmap 2030](https://img.shields.io/badge/Policy-NSW%20Electricity%20Roadmap-teal.svg)](https://www.energy.nsw.gov.au/nsw-plans-and-progress/major-state-projects/electricity-infrastructure-roadmap)

> An open-source, production-grade National Electricity Market (NEM) Economic Dispatch and Unit Commitment simulation engine developed in Python. 
> Formulates the multi-interval linear programming (LP) optimization problem that underpins commercial packages like **PLEXOS (ST Schedule)** and **AEMO's NEMDE**, co-optimizing battery energy storage (BESS) cycling, thermal ramp limits, transmission interconnectors, and NSW policy scenarios.

**Author**: **Dr. Md Mahmudur Rahman (PhD)**  
*Senior Data Analytics Lead | Former Atmospheric Scientist, NSW DPIE / DCCEEW*  
*Repository*: [`https://github.com/mahmudurah/nem-dispatch-simulator`](https://github.com/mahmudurah/nem-dispatch-simulator)

---

## 1. Overview & Motivation

The transition of the Australian National Electricity Market (NEM) requires sophisticated computational tools to evaluate how retiring coal-fired generation (such as **Eraring**, **Bayswater**, and **Mt Piper**) interacts with intermittent renewables (Renewable Energy Zones - REZs), battery storage systems (BESS), and firming peaking infrastructure.

While commercial platforms like **PLEXOS** are widely deployed, their proprietary nature and desktop GUI interfaces can obscure the underlying mathematical mechanics. This project provides a transparent, high-performance, and fully auditable simulation engine built from first principles to:
1. **Solve multi-interval economic dispatch** using the industrial **HiGHS Linear Programming (LP)** solver.
2. **Extract nodal clearing prices ($\lambda_t$)** as the mathematical dual variables (shadow prices) of the supply-demand balance constraint.
3. **Co-optimize Battery Storage (BESS) & Pumped Hydro (PHES)**: charging during negative/low midday solar troughs and discharging during high-value evening demand ramps.
4. **Stress-test NSW policy scenarios** under the *NSW Electricity Infrastructure Roadmap*.

---

## 2. Architecture & Mathematical Engine

```mermaid
flowchart TD
    subgraph Ingestion ["1. Data Ingestion (AEMO & DCCEEW Catalogs)"]
        A["Generator Fleet Catalog<br/>(Heat Rates, SRMC, Capacities)"]
        B["Operational Demand Trace<br/>(48 Half-Hour Trading Intervals)"]
        C["Renewable Availability Traces<br/>(Solar & Wind Capacity Factors)"]
    end

    subgraph Optimization ["2. HiGHS Linear Programming Engine (scipy.optimize.linprog)"]
        D["Objective: Minimize Total System Operating Cost ($ AUD)"]
        E["Constraint: Nodal Supply-Demand Balance (Shadow Price = Spot Price)"]
        F["Constraint: BESS State-of-Charge Mass Balance & Round-Trip Losses"]
        G["Constraint: Thermal Baseload Ramp-Up & Ramp-Down Limits"]
        H["Constraint: Interconnector Flow Limits (VNI & QNI)"]
    end

    subgraph Policy ["3. NSW Roadmap Policy Scenarios"]
        I["Scenario A: Baseline 2024 (Eraring + Existing Renewables)"]
        J["Scenario B: Eraring Exit Unfirmed (Supply Shock & Peaker Spikes)"]
        K["Scenario C: NSW Roadmap 2030 (3GW CWO REZ + 8h LDS Storage)"]
    end

    subgraph Outputs ["4. Executive Intelligence & Dashboards"]
        L["Interactive Plotly HTML Dashboard (Stacked Merit Order Dispatch)"]
        M["Wholesale Spot Price Trajectory ($/MWh)"]
        N["Carbon Emissions Accounting (tCO2-e)"]
        O["Comparative Scenario Policy Matrix (CSV)"]
    end

    Ingestion --> Optimization
    Optimization --> Policy
    Policy --> Outputs
```

For the formal mathematical proofs, objective equations, and dual variable formulations, see [docs/MATHEMATICAL_FORMULATION.md](docs/MATHEMATICAL_FORMULATION.md).

For a detailed analysis comparing this simulator to PLEXOS modules, see [docs/PLEXOS_VS_NEM_SIMULATOR.md](docs/PLEXOS_VS_NEM_SIMULATOR.md).

---

## 4. PLEXOS 2026 Annual Production Cost Study (Full 8,760 Hours)

To replicate how analysts at DCCEEW conduct official long-term policy reviews, we extended the engine into a **full chronological 8,760-hour rolling horizon simulator** (`PLEXOSAnnualEngine`).

We ingested a calibrated **2026 hourly dataset (63,682.7 GWh operational demand, realistic solar/wind traces, and winter/summer peak loads)**:

| Metric (Full 2026 Year) | Baseline 2024 Grid | NSW Roadmap 2030 (CWO + Storage) | Annual Impact |
| :--- | :---: | :---: | :--- |
| **Total Annual Energy** | 63,682.7 GWh | 63,682.7 GWh | Full annual balance |
| **Total Generation Delivered** | 62,368.6 GWh | 59,993.7 GWh | High renewable displacement |
| **Total Annual Emissions** | **43.65 Mt $\text{CO}_2\text{-e}$** | **32.65 Mt $\text{CO}_2\text{-e}$** | **-11.0 Million Tonnes CO2 Cut (-25.2%)** |
| **Average Emission Intensity** | **0.700 t / MWh** | **0.544 t / MWh** | **-22.3% cleaner grid** |
| **Base Average Spot Price** | **\$78.27 / MWh** | **\$69.54 / MWh** *(unconstrained)* | Stabilized pool price |
| **Bayswater Baseload CF** | 99.6% | 99.6% | Baseload run flat-out |
| **Wind Capacity Factor** | 29.3% | 29.3% | Matches actual NSW wind fleet |
| **Solar Capacity Factor** | 22.9% | 22.9% | Matches actual NSW solar fleet |

```bash
# Run the 2026 Annual PLEXOS Study in ~14 seconds:
python examples/run_plexos_2026_annual_study.py
```

*Outputs an interactive PLEXOS Price Duration Curve (PDC) and annual dispatch heatmap to `output/plexos_2026_analyst_dashboard.html`.*

---

## 4. Quickstart Guide

### Installation
Clone the repository and install the dependencies:
```bash
git clone https://github.com/mahmudurah/nem-dispatch-simulator.git
cd nem-dispatch-simulator
pip install -r requirements.txt
```

### Run Policy Comparison & Generate Interactive Dashboard
Execute the full comparative workflow across all three NSW policy scenarios:
```bash
python -m nem_simulator.cli --compare --dashboard
```
This generates:
* `output/scenario_comparison_summary.csv`: Summary metrics table.
* `output/nem_dispatch_dashboard.html`: Standalone, interactive multi-panel Plotly dashboard. Open this file directly in any browser:
```bash
# Windows
start output/nem_dispatch_dashboard.html
```

### Run a Specific Scenario
```bash
python -m nem_simulator.cli --scenario NSW_Roadmap_2030
```

### Run the Example Analysis Script
```bash
python examples/run_nsw_roadmap_analysis.py
```

### Run Automated Unit Tests
```bash
python -m unittest discover tests
```

---

## 5. Python API Usage

You can easily integrate the simulator into your own data science pipelines:

```python
from nem_simulator.scenarios import load_nsw_scenario, load_trace_data, get_nsw_interconnectors
from nem_simulator.model import NEMDispatchEngine

# 1. Load NSW Roadmap scenario assets
generators, storage = load_nsw_scenario("NSW_Roadmap_2030")
interconnectors = get_nsw_interconnectors()

# 2. Ingest demand and renewable availability traces
traces = load_trace_data()
demand = traces['operational_demand_mw'].tolist()
solar_cf = traces['solar_capacity_factor'].tolist()
wind_cf = traces['wind_capacity_factor'].tolist()

# 3. Instantiate Engine & Solve Economic Dispatch
engine = NEMDispatchEngine(
    generators=generators,
    storage_assets=storage,
    interconnectors=interconnectors,
    interval_minutes=30
)

result = engine.solve(
    demand_trace_mw=demand,
    solar_capacity_factor=solar_cf,
    wind_capacity_factor=wind_cf,
    enforce_ramp_rates=True
)

# 4. Inspect Results & Shadow Prices
print(f"Optimal Total Cost : ${result.total_cost:,.2f} AUD")
print(f"Average Spot Price : ${result.average_price_per_mwh:.2f} / MWh")
print(f"Total Emissions    : {result.total_emissions_tco2:,.1f} tCO2-e")

# Interval clearing prices ($/MWh)
print(result.prices_df[['interval', 'demand_mw', 'clearing_price_per_mwh']].head())
```

---

## 6. Project Structure

```
nem-dispatch-simulator/
├── README.md                              # Main documentation & results
├── requirements.txt                        # Dependency manifest
├── pyproject.toml                         # Packaging specification
├── data/
│   ├── generators_nsw.csv                 # Detailed NSW generator parameters
│   └── demand_and_renewables_48hh.csv     # 48 half-hour trading interval traces
├── nem_simulator/
│   ├── __init__.py
│   ├── generator.py                       # Generator, Storage & Interconnector classes
│   ├── model.py                           # HiGHS LP Economic Dispatch Engine
│   ├── scenarios.py                       # NSW policy scenario definitions
│   ├── visualization.py                   # Plotly multi-panel HTML generator
│   └── cli.py                             # Command-Line Interface
├── examples/
│   └── run_nsw_roadmap_analysis.py        # End-to-end policy execution script
├── tests/
│   └── test_dispatch.py                   # Automated mathematical verification tests
├── docs/
│   ├── MATHEMATICAL_FORMULATION.md        # LaTeX equations & constraints
│   └── PLEXOS_VS_NEM_SIMULATOR.md         # PLEXOS architectural comparison
└── output/
    ├── nem_dispatch_dashboard.html        # Interactive Plotly dashboard
    └── scenario_comparison_summary.csv    # Comparative CSV metrics
```

---

## 7. License & Acknowledgements

Developed under the **MIT License**.

Built for research, educational, and public policy purposes to support Australia's clean energy transition. Uses operational parameters modeled after AEMO National Electricity Market MMS specifications and the NSW Electricity Infrastructure Roadmap.
