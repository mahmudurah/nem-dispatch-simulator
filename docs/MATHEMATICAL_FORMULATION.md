# Mathematical Formulation: NEM Economic Dispatch & Storage Co-Optimization

This document provides the rigorous mathematical formulation of the **NEM Dispatch Simulator**, which mirrors the core economic dispatch and unit commitment algorithms implemented in commercial energy modeling platforms such as **PLEXOS (ST Schedule)** and **AEMO's NEMDE**.

---

## 1. Sets and Indices

* $t \in \mathcal{T} = \{1, 2, \dots, T\}$: Trading intervals across the simulation horizon (e.g., $T=48$ half-hour intervals or $T=288$ five-minute intervals).
* $i \in \mathcal{G}$: Set of scheduled and semi-scheduled generation assets (Coal, Gas CCGT, Gas OCGT, Solar, Wind).
* $j \in \mathcal{S}$: Set of energy storage systems (Battery Energy Storage Systems - BESS, and Pumped Hydro Energy Storage - PHES).
* $l \in \mathcal{L}$: Set of high-voltage transmission interconnectors (e.g., VNI, QNI).
* $\Delta t$: Interval duration in hours ($\Delta t = 0.5$ for 30-minute intervals, $\Delta t = \frac{1}{12}$ for 5-minute intervals).

---

## 2. Decision Variables

For each time interval $t \in \mathcal{T}$:

* $p_{i,t} \ge 0$: Active power output of generator $i$ in interval $t$ [MW].
* $c_{j,t} \ge 0$: Charging power of storage asset $j$ in interval $t$ [MW].
* $d_{j,t} \ge 0$: Discharging power of storage asset $j$ in interval $t$ [MW].
* $soc_{j,t} \ge 0$: Stored energy state of charge of storage asset $j$ at the end of interval $t$ [MWh].
* $imp_{l,t} \ge 0$: Power imported across interconnector $l$ into the regional node [MW].
* $s^{\text{def}}_t \ge 0$: Unserved energy (slack deficit) in interval $t$ [MW].
* $s^{\text{curt}}_t \ge 0$: Curtailed renewable generation (slack excess) in interval $t$ [MW].

---

## 3. Objective Function

The objective is to minimize total system short-run marginal cost across the entire simulation horizon:

$$\min_{\mathbf{p}, \mathbf{c}, \mathbf{d}, \mathbf{soc}, \mathbf{imp}, \mathbf{s}} \sum_{t=1}^{T} \left[ \sum_{i \in \mathcal{G}} C_i \cdot p_{i,t} \cdot \Delta t + \sum_{j \in \mathcal{S}} C^{\text{deg}}_j \cdot d_{j,t} \cdot \Delta t + \sum_{l \in \mathcal{L}} C^{\text{wheel}}_l \cdot imp_{l,t} \cdot \Delta t + \text{MPC} \cdot s^{\text{def}}_t \cdot \Delta t + \epsilon \cdot s^{\text{curt}}_t \cdot \Delta t \right]$$

Where:
* $C_i$: Short-Run Marginal Cost (SRMC) of generator $i$ [$\$/\text{MWh}$], comprising fuel costs, carbon permits, and variable operating and maintenance (VOM) expenses.
* $C^{\text{deg}}_j$: Cycle degradation cost of storage asset $j$ [$\$/\text{MWh}$] (reflecting cell wear or pumping maintenance).
* $C^{\text{wheel}}_l$: Interconnector wheeling tariff / transmission loss charge [$\$/\text{MWh}$].
* $\text{MPC}$: NEM Market Price Cap ($17,500/\text{MWh}$ in the 2024–2026 regulatory framework), ensuring that unserved energy is only incurred as a last resort.
* $\epsilon$: Small positive penalty ($\$0.01/\text{MWh}$) to prevent arbitrary curtailment when generation is costless.

---

## 4. Operational Constraints

### 4.1. Regional Supply-Demand Balance (Nodal Equilibrium)
At each time interval $t \in \mathcal{T}$, total generated power, net storage discharge, and interconnector imports must exactly satisfy operational demand:

$$\sum_{i \in \mathcal{G}} p_{i,t} + \sum_{j \in \mathcal{S}} \left( d_{j,t} - c_{j,t} \right) + \sum_{l \in \mathcal{L}} imp_{l,t} + s^{\text{def}}_t - s^{\text{curt}}_t = D_t \quad \forall t \in \mathcal{T} \quad (\lambda_t)$$

#### The Shadow Price (Dual Variable $\lambda_t$)
The dual variable (Lagrange multiplier) associated with this equality constraint is $\lambda_t$. 
Mathematically, $\lambda_t$ represents the change in the optimal objective value per unit increase in regional demand $D_t$:

$$\lambda_t = \frac{\partial \text{Cost}^*}{\partial D_t}$$

In the National Electricity Market (NEM), $\lambda_t$ is defined as the **Regional Reference Price (Spot Clearing Price)** in $\$ / \text{MWh}$. It is bounded within the regulatory band:
$$\text{Market Floor Price } (-\$1,000/\text{MWh}) \le \lambda_t \le \text{Market Price Cap } (\$17,500/\text{MWh})$$

---

### 4.2. Generator Capacity & Variable Renewable Availability
Generators are constrained by their technical minimum and maximum capacities, adjusted for interval-specific renewable resource availability:

$$P_{i,\min} \le p_{i,t} \le P_{i,\max} \cdot \alpha_{i,t} \quad \forall i \in \mathcal{G}, \forall t \in \mathcal{T}$$

Where $\alpha_{i,t} \in [0, 1]$ is the renewable capacity factor trace:
* For thermal units (Coal, Gas CCGT, Gas OCGT): $\alpha_{i,t} = 1.0$.
* For utility solar: $\alpha_{i,t} = \text{SolarAvailability}_t$.
* For wind farms: $\alpha_{i,t} = \text{WindAvailability}_t$.

---

### 4.3. Storage Dynamics & State-of-Charge (SoC) Transitions
Energy storage systems are governed by mass-energy conservation across time intervals:

#### Charge & Discharge Power Limits:
$$0 \le c_{j,t} \le P^{\text{ch}}_{j,\max} \quad \forall j \in \mathcal{S}, \forall t \in \mathcal{T}$$
$$0 \le d_{j,t} \le P^{\text{dis}}_{j,\max} \quad \forall j \in \mathcal{S}, \forall t \in \mathcal{T}$$

#### State of Charge Evolution:
$$soc_{j,t} = soc_{j,t-1} + \left( \eta^{\text{ch}}_j \cdot c_{j,t} - \frac{1}{\eta^{\text{dis}}_j} \cdot d_{j,t} \right) \Delta t \quad \forall j \in \mathcal{S}, \forall t \ge 2$$

For the initial interval $t=1$:
$$soc_{j,1} = SoC^{\text{init}}_j + \left( \eta^{\text{ch}}_j \cdot c_{j,1} - \frac{1}{\eta^{\text{dis}}_j} \cdot d_{j,1} \right) \Delta t$$

#### Storage Capacity Bounds:
$$SoC_{j,\min} \le soc_{j,t} \le SoC_{j,\max} \quad \forall j \in \mathcal{S}, \forall t \in \mathcal{T}$$

Where $\eta^{\text{ch}}_j \cdot \eta^{\text{dis}}_j = \eta^{\text{round-trip}}_j$ (e.g., $0.88$ for lithium-ion BESS, $0.76$ for pumped hydro).

---

### 4.4. Thermal Ramp Rate Constraints
Baseload thermal units (e.g. Bayswater, Mt Piper) have mechanical stress constraints limiting how rapidly power output can change between adjacent intervals:

$$p_{i,t} - p_{i,t-1} \le R^{\text{up}}_i \cdot \Delta t_{\text{min}} \quad \forall i \in \mathcal{G}_{\text{thermal}}, \forall t \ge 2$$
$$p_{i,t-1} - p_{i,t} \le R^{\text{down}}_i \cdot \Delta t_{\text{min}} \quad \forall i \in \mathcal{G}_{\text{thermal}}, \forall t \ge 2$$

Where $R^{\text{up}}_i$ and $R^{\text{down}}_i$ are specified in $\text{MW/min}$.

---

### 4.5. Transmission Interconnector Flow Limits
Power transferred between regional nodes (e.g. Victoria to NSW via VNI, Queensland to NSW via QNI) must obey thermal transfer limits:

$$0 \le imp_{l,t} \le F^{\max}_{l,t} \quad \forall l \in \mathcal{L}, \forall t \in \mathcal{T}$$

---

## 5. Carbon Emissions Accounting

Total carbon emissions $E_{\text{total}}$ in tonnes of $\text{CO}_2\text{-e}$ are calculated directly from generator activity:

$$E_{\text{total}} = \sum_{t=1}^{T} \sum_{i \in \mathcal{G}} \left( p_{i,t} \cdot \Delta t \cdot \mu_i \right)$$

Where $\mu_i$ is the emissions intensity factor for unit $i$ in $\text{tCO}_2\text{-e}/\text{MWh}$:
* Black Coal: $\sim 0.89 - 0.94\text{ tCO}_2\text{-e}/\text{MWh}$
* Gas CCGT: $\sim 0.42\text{ tCO}_2\text{-e}/\text{MWh}$
* Gas OCGT / Peaker: $\sim 0.52 - 0.64\text{ tCO}_2\text{-e}/\text{MWh}$
* Solar / Wind / Hydro / BESS: $0.00\text{ tCO}_2\text{-e}/\text{MWh}$

The average grid emission intensity is:
$$\bar{\mu} = \frac{E_{\text{total}}}{\sum_{t=1}^{T} \sum_{i \in \mathcal{G}} p_{i,t} \cdot \Delta t} \quad [\text{tCO}_2\text{-e}/\text{MWh}]$$

---

## 6. Computational Solution Technique

The system is compiled into standard Linear Programming matrix form:

$$\begin{aligned}
\min_{\mathbf{x}} \quad & \mathbf{c}^T \mathbf{x} \\
\text{subject to} \quad & \mathbf{A}_{\text{eq}} \mathbf{x} = \mathbf{b}_{\text{eq}} \\
& \mathbf{A}_{\text{ub}} \mathbf{x} \le \mathbf{b}_{\text{ub}} \\
& \mathbf{l} \le \mathbf{x} \le \mathbf{u}
\end{aligned}$$

The problem is solved using the **HiGHS (High Performance Dual Revised Simplex / Interior Point) solver** via `scipy.optimize.linprog`. HiGHS guarantees global optimality in polynomial time, returns verified dual variables for pricing, and scales effortlessly to thousands of time intervals.
