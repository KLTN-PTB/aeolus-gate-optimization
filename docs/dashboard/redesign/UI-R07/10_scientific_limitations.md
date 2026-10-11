# AEOLUS DASHBOARD — ROBUSTNESS LAB SCIENTIFIC LIMITATIONS
**Phase**: UI-R07 v2.0  
**Authors**: Principal Monte Carlo Simulation Scientist & Operations Research Auditor  

---

## 1. Register of Known Scientific Limitations

### Limitation 1: Finding D1 — Mode A Static Feasibility vs Physical Conflict
- **Empirical Reality**: Under Mode A, 74.8% of scenarios experience direct overlapping occupancy on physical contact gates. In the remaining 25.2% of scenarios, late flight turnarounds erode the 15-minute separation buffer or shift the flight outside its planned slot window.
- **Limitation**: Mode A evaluates a completely frozen schedule with zero recourse adjustments. In actual airport gate control, operations controllers never allow overlapping aircraft to park at the same gate; Mode A therefore measures the **unmitigated disruption risk**, not an operational gate schedule.

### Limitation 2: Finding D2 — Mode B vs Mode C Parity Under Greedy Solver
- **Empirical Reality**: Both Mode B (Reactive Recourse) and Mode C (Oracle Reference) yielded identical mean costs of 130.7302 pts and identical gate assignments across all 500 scenarios.
- **Root Cause**: The P09 Monte Carlo engine invoked `DeterministicGreedyGateSolver` for both Mode B and Mode C on the realized sequence of flights.
- **Scientific Limitation**:
  - Parity between Mode B and Mode C does **not** prove that reactive recourse achieves the global mathematical lower bound.
  - Mode C is a heuristic benchmark (Greedy with future knowledge), **not an exact global optimum** (which would require CP-SAT or MILP solved offline).
  - Claims of "optimality proven" or "oracle lower bound certification" are scientifically false and strictly prohibited.

### Limitation 3: Non-Deployability of Mode C
- **Operational Reality**: Mode C presumes perfect, clairvoyant advance knowledge of all flight delays throughout the operational day before flight arrival.
- **Scientific Limitation**: This information set is non-causal. Mode C serves exclusively as an idealized theoretical reference and must never be evaluated for real-world deployment.

### Limitation 4: Temporal Scope & 2024 Holdout Quarantine
- **Empirical Scope**: All Monte Carlo distributions were fitted and simulated using historical flight operations from calendar year 2023 at Atlanta Hartsfield-Jackson International Airport (ATL).
- **Quarantine**: Calendar year 2024 operations data remain strictly sealed in an independent holdout quarantine under Protocol V4 to prevent data leakage during model tuning.
