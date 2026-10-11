# AEOLUS DASHBOARD — UI-R07 TEST CATALOG & VERIFICATION RESULTS
**Test Module**: `tests/dashboard/test_ui_r07_robustness_monte_carlo.py`  
**Total Tests**: 35 automated tests (`R07-T01` to `R07-T35`)  
**Pass Rate**: 100% (35 / 35 passing in 1.34s)  

---

## 1. Test Matrix

| ID | Test Function | Target Task | Invariant / Validation Verified |
| :---: | :--- | :---: | :--- |
| `R07-T01` | `test_r07_t01_artifact_schema_validated` | R07-A | Required columns present across fixed, recourse, and oracle CSVs. |
| `R07-T02` | `test_r07_t02_missing_mc_artifact_unavailable` | R07-A | Missing artifacts raise `ArtifactNotFoundError` gracefully. |
| `R07-T03` | `test_r07_t03_no_fake_numerical_fallback` | R07-A | Empty summary returns `{}` without fabricated fallback numbers. |
| `R07-T04` | `test_r07_t04_500_scenarios_x_3_solvers_distinct` | R07-A | 1,500 rows = 500 distinct scenarios × 3 solvers (`CPSat`, `Greedy`, `Hybrid`). |
| `R07-T05` | `test_r07_t05_1500_evaluations_not_labeled_1500_independent_scenarios` | R07-A | Separates 500 stochastic scenarios from 1,500 total evaluations. |
| `R07-T06` | `test_r07_t06_solver_filter_applied_to_histogram` | R07-B | Multi-solver DataFrame filtered to single solver for histogram. |
| `R07-T07` | `test_r07_t07_solver_filter_applied_to_ecdf` | R07-B | Single-solver isolation verified for ECDF. |
| `R07-T08` | `test_r07_t08_solver_filter_applied_to_boxplot` | R07-B | Single-solver isolation verified for boxplot. |
| `R07-T09` | `test_r07_t09_solver_filter_applied_to_convergence` | R07-B | Running mean convergence trace receives homogeneous 500 rows. |
| `R07-T10` | `test_r07_t10_mixed_solver_population_rejected_when_not_allowed` | R07-B | Raises `IncompatibleComparisonError` when `allow_filter=False`. |
| `R07-T11` | `test_r07_t11_duplicate_scenario_ids_detected` | R07-A | `validate_mc_dataframe` detects duplicate scenario identifiers. |
| `R07-T12` | `test_r07_t12_failed_observations_counted` | R07-F | `failures.json` confirms exactly 0 failed evaluations in P09. |
| `R07-T13` | `test_r07_t13_requested_vs_evaluated_counts_correct` | R07-F | Manifest (500) and summary (500) counts match. |
| `R07-T14` | `test_r07_t14_mean_correct` | R07-F | `calculate_mc_stats` calculates exact arithmetic sample mean. |
| `R07-T15` | `test_r07_t15_median_correct` | R07-F | `calculate_mc_stats` calculates exact sample median. |
| `R07-T16` | `test_r07_t16_std_mcse_correct` | R07-F | Sample std uses $ddof=1$ and $\text{MCSE} = s / \sqrt{n}$. |
| `R07-T17` | `test_r07_t17_ci_from_fixture_correct` | R07-F | 95% Confidence Interval follows $[\mu \pm 1.96 \cdot \text{MCSE}]$. |
| `R07-T18` | `test_r07_t18_p90_p95_correct` | R07-F | Quantiles p90 and p95 match numpy empirical percentiles. |
| `R07-T19` | `test_r07_t19_cvar95_correct` | R07-F | $\text{CVaR}_{95}$ is upper tail mean and strictly $\ge P_{95}$. |
| `R07-T20` | `test_r07_t20_mode_a_feasibility_and_conflict_distinct` | R07-C | Physical conflict rate (74.8%) and static feasibility (0.0%) distinct. |
| `R07-T21` | `test_r07_t21_mode_b_c_effective_solver_audited` | R07-D | Both Mode B and Mode C run `DeterministicGreedyGateSolver`. |
| `R07-T22` | `test_r07_t22_greedy_mode_c_not_globally_optimal` | R07-D | Heuristic Mode C cannot claim global optimality. |
| `R07-T23` | `test_r07_t23_oracle_parity_claim_blocked_if_unsupported` | R07-D | Mode C deployability claim raises `IncompatibleComparisonError`. |
| `R07-T24` | `test_r07_t24_mode_c_clearly_non_deployable` | R07-D | `views["mode_c"].is_deployable == False`. |
| `R07-T25` | `test_r07_t25_paired_join_uses_matching_scenario_ids` | R07-G | Inner join matches strictly on `realization_id` key. |
| `R07-T26` | `test_r07_t26_unmatched_paired_data_rejected` | R07-G | Unmatched scenario IDs raise `ValueError`. |
| `R07-T27` | `test_r07_t27_paired_difference_sign_correct` | R07-G | Mode A vs B paired difference has positive mean delta (+1338 pts). |
| `R07-T28` | `test_r07_t28_different_cost_semantics_handled` | R07-E | Mode A (penalty) vs Mode B (decision cost) semantics distinguished. |
| `R07-T29` | `test_r07_t29_scenario_dropdown_derives_from_records` | R07-I | Scenario options derive dynamically from 500 real records. |
| `R07-T30` | `test_r07_t30_missing_scenario_not_default_success` | R07-I | Missing scenario returns None, never defaulting `feasible=True`. |
| `R07-T31` | `test_r07_t31_no_fabricated_flight_level_gantt` | R07-I | Drill-down declares `flight_level_assignments_available = False`. |
| `R07-T32` | `test_r07_t32_research_inspector_defaults_not_checked`| R07-J | Inspector defaults to `NOT_CHECKED` without false verification. |
| `R07-T33` | `test_r07_t33_chart_selection_does_not_rerun_mc` | R07-B | In-memory filtering executes zero simulations. |
| `R07-T34` | `test_r07_t34_export_preserves_experiment_metadata` | R07-J | Export CSV preserves experiment identifier. |
| `R07-T35` | `test_r07_t35_no_scientific_warning_accidentally_hidden` | R07-H | All 4 scientific warnings (D1, D2, Oracle, 2024) documented in page. |

---

## 2. Regression Results

- `pytest tests/dashboard/test_ui_r07_robustness_monte_carlo.py`: **35 passed in 1.34s**.
- `pytest tests/dashboard/`: **319 passed in 7.13s**.
- Backend OR / ML Regression Tests: **65 passed in 7.70s**.
