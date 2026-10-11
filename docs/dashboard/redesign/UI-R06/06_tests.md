# AEOLUS DASHBOARD — UI-R06 VERIFICATION TEST CATALOG
**Test Module**: `tests/dashboard/test_ui_r06_optimization_benchmarking.py`  
**Total Tests**: 28 automated tests (`R06-T01` to `R06-T28`)  
**Pass Rate**: 100% (28 / 28 passing)  

---

## 1. Test Matrix

| ID | Test Function | Target Task | Description & Scientific Invariant Verified |
| :---: | :--- | :---: | :--- |
| `R06-T01` | `test_r06_t01_artifact_record_count_correct` | R06-A | Exactly 95 benchmark records exist in `solver_runs.csv`. |
| `R06-T02` | `test_r06_t02_schema_validation_required_columns` | R06-A | Mandatory columns (`run_id`, `scenario_id`, `objective_value`, etc.) present. |
| `R06-T03` | `test_r06_t03_same_workload_comparison_valid` | R06-B | Records with identical scenario and feasible status pass compatibility check. |
| `R06-T04` | `test_r06_t04_different_scenario_ranking_blocked` | R06-B | Comparing different scenario IDs raises `IncompatibleComparisonError`. |
| `R06-T05` | `test_r06_t05_different_gate_inventory_blocked` | R06-B | Comparing different gate counts raises `IncompatibleComparisonError`. |
| `R06-T06` | `test_r06_t06_different_capacity_blocked` | R06-B | Comparing different capacity policies raises `IncompatibleComparisonError`. |
| `R06-T07` | `test_r06_t07_different_objective_blocked` | R06-B | Comparing different objective definitions raises `IncompatibleComparisonError`. |
| `R06-T08` | `test_r06_t08_different_prediction_source_blocked`| R06-B | Comparing different prediction sources raises `IncompatibleComparisonError`. |
| `R06-T09` | `test_r06_t09_unknown_without_incumbent_no_cost` | R06-D | UNKNOWN runs without incumbent have cost `None` (never 0.0 or fabricated). |
| `R06-T10` | `test_r06_t10_infeasible_excluded_from_ranking` | R06-D | INFEASIBLE runs are rejected from comparative ranking. |
| `R06-T11` | `test_r06_t11_invalid_result_excluded_from_ranking` | R06-D | `is_status_feasible_for_ranking` returns False for UNKNOWN and INFEASIBLE. |
| `R06-T12` | `test_r06_t12_feasible_not_labeled_as_optimal` | R06-D | `FEASIBLE` status badge does not claim optimal (`is_optimal = False`). |
| `R06-T13` | `test_r06_t13_greedy_not_globally_optimal_by_default` | R06-D | Deterministic Greedy has `optimality_proven == False` across all runs. |
| `R06-T14` | `test_r06_t14_sa_not_globally_optimal_by_default` | R06-D | Standalone SA has `optimality_proven == False` across all runs. |
| `R06-T15` | `test_r06_t15_cost_from_real_artifact_no_fallback` | R06-E | Costs originate from real CSV records; hardcoded 130.00 pts eliminated. |
| `R06-T16` | `test_r06_t16_runtime_units_correct_positive_numbers` | R06-E | All wall-clock runtimes are finite positive numbers in milliseconds. |
| `R06-T17` | `test_r06_t17_total_vs_search_time_distinguished` | R06-G | Invariant: Total wall-clock time $\ge$ search time across all 95 runs. |
| `R06-T18` | `test_r06_t18_hybrid_stages_represented_correctly` | R06-G | Hybrid solver records build, search, and validation times. |
| `R06-T19` | `test_r06_t19_pareto_nondominance_correct` | R06-F | `ScientificValidator.compute_pareto_frontier` calculates exact non-dominated points. |
| `R06-T20` | `test_r06_t20_scatter_correctly_labeled_and_scaled`| R06-F | Pareto scatter chart has clean title and log-scale X-axis without raw IDs. |
| `R06-T21` | `test_r06_t21_missing_scalability_artifact_empty_state` | R06-H | Empty scalability DataFrame renders empty-state without fake lines. |
| `R06-T22` | `test_r06_t22_historical_1500_unknown_if_artifact_used`| R06-H | N=1500 case in scalability results is strictly UNKNOWN with feasible=False. |
| `R06-T23` | `test_r06_t23_repeated_runs_grouped_by_scenario_and_variant` | R06-C | Repeated runs (replications) group under the same scenario & variant. |
| `R06-T24` | `test_r06_t24_zero_baseline_improvement_na` | R06-I | Relative improvement returns `None` (N/A) when baseline cost is 0.0. |
| `R06-T25` | `test_r06_t25_switching_experiment_updates_workload_records` | R06-C | Switching workloads returns disjoint scenario records. |
| `R06-T26` | `test_r06_t26_filter_does_not_launch_solver` | R06-C | Filtering benchmark records is purely passive and executes zero solvers. |
| `R06-T27` | `test_r06_t27_benchmark_provenance_metadata_complete` | R06-A | Provenance metadata contains valid SHA-256 hash and row counts. |
| `R06-T28` | `test_r06_t28_no_modification_of_research_artifacts` | R06-I | SHA-256 hashes of all 3 research artifacts remain byte-for-byte identical. |

---

## 2. Regression Test Summary

- `pytest tests/dashboard/test_ui_r06_optimization_benchmarking.py`: **28 passed in 0.29s**.
- `pytest tests/dashboard/`: **284 passed in 6.85s**.
- Backend OR / ML regression tests: **65 passed in 9.08s**.
