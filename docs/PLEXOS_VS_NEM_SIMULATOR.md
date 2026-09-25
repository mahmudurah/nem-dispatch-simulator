# PLEXOS Under the Hood: A Structural Comparison with NEM Dispatch Simulator

> **Note**: This is an open-source educational and research learning project designed for researchers, analysts, and students who want to understand, simulate, and demystify the mathematical mechanics of the Australian National Electricity Market (NEM) and commercial tools like PLEXOS from first principles.

---

## 1. What is PLEXOS Actually?

PLEXOS (by Energy Exemplar) is the dominant commercial simulation software used across the Australian National Electricity Market (AEMO, state energy departments, transmission network service providers, and gentailers).

At its core, **PLEXOS is not a physical black-box machine; it is a relational database and Graphical User Interface (GUI) wrapped around industrial mathematical optimization solvers** (such as CPLEX, Gurobi, or Xpress).

PLEXOS organizes power system simulation into four hierarchical timeframes:

```mermaid
flowchart TD
    A["1. Long Term (LT Plan)<br/>Capacity Expansion (10-30 Years)<br/><i>Decides what power plants & batteries to build</i>"] --> B["2. Project Assessment of System Adequacy (PASA)<br/>Maintenance & Outage Scheduling (1-5 Years)<br/><i>Schedules generator overhauls & calculates reserve margins</i>"]
    B --> C["3. Medium Term (MT Schedule)<br/>Hydro & Storage Boundary Conditions (1 Year)<br/><i>Calculates water value curves & seasonal storage targets</i>"]
    C --> D["4. Short Term (ST Schedule)<br/>Unit Commitment & Economic Dispatch (Daily / 5-Minute)<br/><i>Calculates 5-minute dispatch & nodal clearing prices</i>"]
```

| PLEXOS Module | Horizon | Mathematical Formulation | What It Solves |
| :--- | :--- | :--- | :--- |
| **LT Plan** (Long Term) | 10–30 Years | Mixed-Integer Linear Programming (MILP) / LP | Optimal generation build, storage expansion, and transmission lines under policy mandates (e.g. Net Zero targets). |
| **PASA** | 1–5 Years | Heuristic / Integer Programming | Scheduled generator maintenance windows, Loss of Load Probability (LOLP), Expected Unserved Energy (EUE). |
| **MT Schedule** | 1 Year | Stochastic Dynamic Programming / LP | Seasonal hydro storage management, water opportunity values, and multi-month gas contract caps. |
| **ST Schedule** | Days / Weeks | MILP / LP (Interval Dispatch) | **5-minute economic dispatch, unit commitment, BESS cycling, transmission constraints, and spot prices.** |

---

## 2. How the NEM Dispatch Simulator Maps to PLEXOS ST Schedule

The **NEM Dispatch Simulator** directly reproduces the mathematical engine of the **PLEXOS ST Schedule (Short Term Economic Dispatch)**:

| Modeling Feature | PLEXOS Implementation | NEM Dispatch Simulator Implementation |
| :--- | :--- | :--- |
| **Objective Function** | Minimizes total generation costs, start-up costs, unserved energy penalties, and wheeling charges. | Formulates linear objective minimizing $\sum C_i \cdot p_i + C_{\text{deg}} \cdot d + \text{MPC} \cdot s_{\text{def}}$. |
| **Solver Engine** | Solves via external commercial engines (CPLEX / Gurobi / Xpress). | Solves via **HiGHS (Dual Revised Simplex / Interior Point)** via `scipy.optimize.linprog`. |
| **Dispatch Resolution** | 5-minute dispatch intervals or 30-minute trading intervals. | Configurable $\Delta t$ (30-minute, 5-minute, or 60-minute intervals). |
| **Storage Modeling** | Models state of charge, round-trip efficiency, charge/discharge power, and head loss. | Mass-energy conservation constraint with round-trip efficiency $\eta$ and cycle degradation penalty. |
| **Price Formation** | Dual variable (Lagrangian shadow price) of the regional energy balance constraint. | Dual variable ($\lambda_t$) extracted directly from HiGHS equality constraints (`res.eqlin.marginals`). |
| **Transmission** | Linear DC power flow with flow limits and marginal loss factors (MLFs). | Interconnector import limits and marginal wheeling tariffs. |
| **Emissions** | Calculates total emissions via fuel heat rates and emissions intensity factors. | Direct interval-by-interval emissions calculation based on generator fuel factors. |

---

## 3. Key Market Modeling Concepts & Terminology

Understanding these core power system economics concepts is essential when analyzing electricity markets:

### 1. "Marginal Clearing Price" vs "Bid Stacks"
* **Concept**: In the NEM, generators submit bids across 10 price bands (-\$1,000 to +\$17,500/MWh). In economic dispatch models like PLEXOS, generators are dispatched in **merit order** based on their Short-Run Marginal Cost (SRMC). 
* **Mechanic**: The wholesale clearing spot price is the shadow price (dual variable) of the supply-demand balance constraint, set by the marginal dispatched generator.

### 2. "Heat Rates" and "SRMC"
* **Concept**: Thermal efficiency of coal and gas plants is measured in Heat Rate ($\text{GJ/MWh}$). Multiplying fuel cost ($\$/\text{GJ}$) by heat rate and adding Variable O&M gives the Short-Run Marginal Cost (SRMC).
* **Mechanic**: Calibrating generator heat rates and fuel price assumptions to AEMO GenCost and IASR projections ensures model validity.

### 3. "Dunkelflaute" (Dark Doldrums)
* **Concept**: Extended periods of low wind and overcast skies across southeast Australia.
* **Mechanic**: While short-duration BESS flattens the daily duck curve, multi-day dunkelflaute events require Long-Duration Storage (LDS) or gas peaker firming to maintain reliability.

### 4. "Dual Variables / Shadow Prices"
* **Concept**: The mathematical derivative of total system cost with respect to a constraint limit.
* **Mechanic**: Spot prices are extracted as the dual variable ($\lambda_t$) of the nodal energy balance equation, exactly as PLEXOS and NEMDE do.

---

## 4. Why Demystifying PLEXOS from First Principles Matters

While commercial simulation suites are widely deployed across government and industry, their proprietary nature and desktop graphical interfaces can obscure the underlying mathematical mechanics.

By rebuilding the dispatch engine from first principles in pure Python:
1. **Full Algorithmic Transparency**: The optimization matrices, constraint bounds, and dual variables are completely open, auditable, and mathematically visible.
2. **Accessible Education**: Students, energy researchers, and data scientists can experiment with unit commitment, storage cycling, and transmission limits without requiring expensive proprietary licenses.
3. **Reproducibility**: The engine integrates directly with standard Python scientific packages (`numpy`, `pandas`, `scipy`, `plotly`), allowing researchers to verify market theories with empirical data.
