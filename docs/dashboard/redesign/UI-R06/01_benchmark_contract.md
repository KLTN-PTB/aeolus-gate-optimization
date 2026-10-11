# AEOLUS DASHBOARD — UI-R06 BENCHMARK CONTRACT
**Artifact Path**: `artifacts/remediation/benchmarks/solver_runs.csv`  
**Phase**: UI-R06 v2.0  
**Author**: Principal Operations Research Scientist & Scientific Software QA Lead  

---

## 1. Executive Summary & Provenance

The Aeolus Optimization Lab evaluates four optimization solver families across five standardized benchmark workloads:
- **Solvers**: Deterministic Greedy (`GREEDY_STANDALONE`), Constraint Programming (`CP_SAT_STANDALONE`), Simulated Annealing (`SA_STANDALONE`, `SA_FROM_PRECOMPUTED_INCUMBENT`), and Hybrid Decomposition (`HYBRID_STANDALONE`).
- **Workloads**: 5 distinct operational scenarios spanning 10 flights to 300 flights.
- **Dataset Size**: Exactly 95 benchmark execution runs recorded in `artifacts/remediation/benchmarks/solver_runs.csv`.
- **SHA-256 Hash**: `8f75063f6fa37f7a1f59990e666a4bc20d6f461e7fc3049b8a3e7a0e36ec2658` (strictly frozen, unmutated).

---

## 2. Workload Breakdown (95 Total Records)

The 95 runs represent rigorous repetitions across the workload tiers:

| Workload ID | Flight Count ($N$) | Gate Count ($M$) | Recorded Solvers & Repetitions | Total Runs |
| :--- | :---: | :---: | :--- | :---: |
| `SCEN_TIER_A_10F_3G` | 10 | 3 | Greedy (5 reps), CP-SAT (5 reps), SA Standalone (5 reps), SA Incumbent (5 reps), Hybrid (5 reps) | 25 |
| `SCEN_TIER_A_20F_6G` | 20 | 6 | Greedy (5 reps), CP-SAT (5 reps), SA Standalone (5 reps), SA Incumbent (5 reps), Hybrid (5 reps) | 25 |
| `SCEN_TIER_B_100F_20G` | 100 | 20 | Greedy (3 reps), CP-SAT (3 reps), SA Standalone (3 reps), SA Incumbent (3 reps), Hybrid (3 reps) | 15 |
| `SCEN_TIER_B_200F_30G` | 200 | 30 | Greedy (3 reps), CP-SAT (3 reps), SA Standalone (3 reps), SA Incumbent (3 reps), Hybrid (3 reps) | 15 |
| `SCEN_TIER_B_300F_50G` | 300 | 50 | Greedy (3 reps), CP-SAT (3 reps), SA Standalone (3 reps), SA Incumbent (3 reps), Hybrid (3 reps) | 15 |
| **Total** | — | — | — | **95** |

---

## 3. Schema Specification & Invariants

Each record in `solver_runs.csv` adheres to the following strict schema:

| Column Name | Type | Description | Scientific Invariant |
| :--- | :---: | :--- | :--- |
| `run_id` | `str` | Repetition identifier (`rep_1`, `rep_2`, ...) | Repetitions are grouped per `(scenario_id, solver_variant)`. |
| `scenario_id` | `str` | Target scenario identifier | Must match active workload. |
| `solver_variant` | `str` | Solver implementation variant | Must belong to recognized solver family. |
| `status` | `str` | Internal mathematical status | `OPTIMAL`, `FEASIBLE`, `UNKNOWN`, `INFEASIBLE`. |
| `feasible` | `bool` | Independent hard-constraint verification | Must be `True` for inclusion in ranking / Pareto curves. |
| `optimality_proven` | `bool` | Proven mathematical global optimality | **True only** for CP-SAT with gap=0.0%. Never `True` for standalone heuristics. |
| `objective_value` | `float` \| `None` | Decision-dependent objective cost | `None` for UNKNOWN/INFEASIBLE without incumbent. Never 0.0 or fabricated. |
| `optimality_gap` | `float` \| `None` | Relative gap $(UB - LB)/UB$ | Defined only when lower bound $LB$ exists. |
| `total_wall_clock_ms`| `float` | End-to-end execution wall time in ms | Finite positive number. |
| `build_time_ms` | `float` | Model formulation & variable creation time | $0 \le \text{build} \le \text{total}$. |
| `search_time_ms` | `float` | Solver search / optimization time | $0 \le \text{search} \le \text{total}$. |
| `validation_time_ms`| `float` | Post-solve constraint audit time | $0 \le \text{validation} \le \text{total}$. |
| `n_flights` | `int` | Turn population size | Matches workload tier metadata. |
| `n_gates` | `int` | Resource inventory count | Matches workload tier metadata. |

---

## 4. Integrity Safeguards

1. **Zero Fake Data**: Fallback mechanisms that insert synthetic baseline numbers (e.g. hardcoded `130.00 pts` or mock CP-SAT records) are eliminated.
2. **Deterministic Immutability**: All benchmark figures are rendered directly from disk artifacts. No live solver processes are executed when loading, filtering, or viewing the Optimization Lab.
