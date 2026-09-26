# CP-SAT Gate Assignment Optimization Design

**Date:** 2026-09-20  
**Status:** APPROVED  
**Scope:** CP-SAT Gate Assignment Optimization, Simulated Annealing, Airport Simulation, Monte Carlo Evaluation, and Strategy Comparison.

## 1. Purpose and Decision Boundaries

This spec details the technical design for the airport gate optimization system (Weeks 7–10 of the V4 roadmap).
The system follows the pipeline:
`Predict (Core Arrival) -> Simulate (Airport Topology) -> Optimize (CP-SAT -> CP-SAT+SA) -> Evaluate (Monte Carlo)`.

### Key Rules and Safety Invariants:
1. **Model Inputs Only**: Optimizer input must ONLY be model predictions (`p_delay` classification probability and `delay_est_min` regression estimate). Raw ground truth labels (`ARR_DELAY`, `DEP_DELAY`) MUST NOT be passed into the optimizer during optimization.
2. **Synthetic Airport Data**: Aeolus dataset lacks airport gate assignment and physical aircraft identity. The airport topology, gate capacity, and aircraft types are synthetically simulated.
3. **Holdout Preservation**: `assert_data_access_allowed` guards 2024 Final Holdout. Simulation and Monte Carlo runs must use synthetic sampling or development partitions (2016–2023).

## 2. Architecture & Solvers

### 2.1 Airport Simulation (`src/simulation/simulate_airport.py`)
- Generates synthetic `Gate` objects (`G01`, `G02`, ...) with contact/remote status, widebody compatibility, and time availability windows.
- Maps flights to synthetic `aircraft_type` values (`A319`, `A320`, `A321`, `B737`, `B738`, `B739`, `WIDEBODY`).

### 2.2 CP-SAT Model (`src/optimization/cp_sat_solver.py`)
- Uses Google OR-Tools `CpModel`.
- Decision variables: $x_{f, g} \in \{0, 1\}$ (flight $f$ assigned to gate $g$).
- Optional interval variables: `NewOptionalIntervalVar(start_i, duration_i, end_i, x_{f, g}, ...)`.
- Constraints:
  - Aircraft type compatibility: $x_{f, g} = 0$ if $f.\text{aircraft\_type} \notin g.\text{compatible\_types}$.
  - Availability window: $start_i \ge g.\text{available\_from\_min}$ and $end_i \le g.\text{available\_to\_min}$.
  - Gate single assignment: $\sum_{g} x_{f, g} = 1, \forall f$.
  - No overlap per gate: `AddNoOverlap(intervals_by_gate[g])`.
  - Flight turn pairing: Flight pairs in the same `chain_group_id` reuse gate timelines appropriately.
- Objective: Minimize gate reassignment penalty $y_f = (1 - x_{f, \text{current\_gate}})$.

### 2.3 Simulated Annealing (`src/optimization/simulated_annealing.py`)
- Refines CP-SAT solution considering soft penalties:
  - $W_1$: Reassignment penalty
  - $W_2$: Expected delay risk cost ($p_{delay} \times delay_{est}$)
  - $W_3$: Gate load balance variance
  - $W_4$: Remote stand usage penalty
- Neighborhood search: Reassign a single flight to a random compatible gate while preserving strict feasibility via `is_feasible()`.

### 2.4 Greedy Baseline (`src/optimization/greedy_baseline.py`)
- Sorts flights by scheduled time and assigns the first available free gate in sequence.

### 2.5 Monte Carlo Simulation (`src/simulation/monte_carlo.py`)
- Evaluates fixed gate assignments across $N$ synthetic delay realization scenarios.
- Counts realized gate occupancy overlaps (`_count_conflicts`).

### 2.6 Strategy Comparison (`src/evaluation/compare_gate_strategies.py`)
- Compares Greedy vs CP-SAT vs CP-SAT+SA across soft cost, gate conflicts, remote usage, and solve runtime.
