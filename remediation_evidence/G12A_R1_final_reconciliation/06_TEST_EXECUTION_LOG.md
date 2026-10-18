# AEOLUS-G12A-R1: TEST EXECUTION LOG & VERIFICATION MATRIX

**Date:** 2026-10-12  
**Auditor:** Senior Scientific Software Verification Engineer, Release Test Lead  
**Test Environment:** Python 3.11.15 win32, pytest 9.1.1, pluggy 1.6.0  
**Test Suites Executed:**
1. `tests/test_g12a_causal_online_recourse.py` (13 tests)
2. `tests/test_g2_monte_carlo_causality.py` (14 tests)
3. `tests/test_finite_remote_capacity_p02.py` (25 tests)

---

## 1. Executive Summary

- **Total Test Items Collected:** 52
- **Passed:** 52
- **Failed:** 0
- **Skipped:** 0
- **Execution Time:** 1.55s
- **Pass Rate:** **100.0%**

---

## 2. Itemized Verification Matrix

### 2.1 G12A Targeted Causal Tests (`tests/test_g12a_causal_online_recourse.py`)
| Test ID | Function Name | Invariant Checked | Status |
| :--- | :--- | :--- | :---: |
| **CAUSAL-01..03** | `test_causal_01_02_03_identical_history_different_future_gate_out` | Identical past history $\mathcal{I}_t$ produces bitwise identical gate assignment regardless of future departure delays. | **PASS** |
| **CAUSAL-04** | `test_causal_04_own_future_gate_out_mutation_invariance` | Mutating flight's own departure delay in future does not alter decision at arrival. | **PASS** |
| **CAUSAL-05** | `test_causal_05_observed_departure_alters_decision` | Observed departures $\le t$ genuinely alter gate availability. | **PASS** |
| **CAUSAL-06** | `test_causal_06_missing_forecast_deterministic_fallback` | Missing ML forecast handled via deterministic monotonic scheduled-time fallback. | **PASS** |
| **CAUSAL-07** | `test_causal_07_future_data_access_across_boundary_rejected` | Accessing `precomputed_gate_out_min` across snapshot boundary raises `AttributeError`. | **PASS** |
| **CAUSAL-08** | `test_causal_08_lock_horizon_demonstrable_impact` | Modifying $H_{\text{lock}}$ from 45 to 15 demonstrably alters recourse decisions. | **PASS** |
| **CAUSAL-09** | `test_causal_09_docked_aircraft_immutability` | Aircraft docked at gate cannot be retroactively moved. | **PASS** |
| **CAUSAL-10** | `test_causal_10_finite_remote_stand_capacity` | Finite remote stand capacity respected under single overflow. | **PASS** |
| **CAUSAL-11** | `test_causal_11_gate_compatibility_and_buffer` | Aircraft type compatibility and 15-min buffers strictly enforced. | **PASS** |
| **CAUSAL-12** | `test_causal_12_midnight_boundary_crossover` | Cross-midnight flight intervals handled monotonically without modulo rollover errors. | **PASS** |
| **CAUSAL-13** | `test_causal_13_deterministic_replay` | Bitwise identical execution results across 5 repeated simulation runs. | **PASS** |
| **CAUSAL-14** | `test_causal_14_ex_post_evaluation_independence` | Decision policy terminates before independent ex-post audit. | **PASS** |
| **CAUSAL-15** | `test_causal_15_finite_capacity_exhaustion_unassigned` | Complete capacity exhaustion produces `UNASSIGNED` with reason `NO_CAPACITY_EXHAUSTED` and `composite_feasible=False`. | **PASS** |

### 2.2 G2 Regression Causal Tests (`tests/test_g2_monte_carlo_causality.py`)
All 14 historical causality tests passed without regression:
- `test_mc_causal_01` through `test_mc_causal_09`: **ALL PASSED**.
- `test_feas_01` (Decomposition separates physical conflict from static consistency): **PASSED**.
- `test_feas_02` (Physical conflict causes composite infeasible): **PASSED**.
- `test_mode_01`, `test_mode_02`, `test_mode_03`: **ALL PASSED**.
- `test_stat_01` (CRN paired comparison metrics): **PASSED**.

### 2.3 P02 Finite Remote Capacity Contract Tests (`tests/test_finite_remote_capacity_p02.py`)
All 25 contract tests covering discrete and pooled finite remote stand constraints passed 100% green.

---

## 3. Raw Pytest Execution Trace

```text
============================= test session starts =============================
platform win32 -- Python 3.11.15, pytest-9.1.1, pluggy-1.6.0 -- D:\Study\Code\Python\Aelous\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: D:\Study\Code\Python\Aelous
configfile: pytest.ini
plugins: anyio-4.15.1
collecting ... collected 52 items

tests/test_g12a_causal_online_recourse.py::test_causal_01_02_03_identical_history_different_future_gate_out PASSED [  1%]
tests/test_g12a_causal_online_recourse.py::test_causal_04_own_future_gate_out_mutation_invariance PASSED [  3%]
tests/test_g12a_causal_online_recourse.py::test_causal_05_observed_departure_alters_decision PASSED [  5%]
tests/test_g12a_causal_online_recourse.py::test_causal_06_missing_forecast_deterministic_fallback PASSED [  7%]
tests/test_g12a_causal_online_recourse.py::test_causal_07_future_data_access_across_boundary_rejected PASSED [  9%]
tests/test_g12a_causal_online_recourse.py::test_causal_08_lock_horizon_demonstrable_impact PASSED [ 11%]
tests/test_g12a_causal_online_recourse.py::test_causal_09_docked_aircraft_immutability PASSED [ 13%]
tests/test_g12a_causal_online_recourse.py::test_causal_10_finite_remote_stand_capacity PASSED [ 15%]
tests/test_g12a_causal_online_recourse.py::test_causal_11_gate_compatibility_and_buffer PASSED [ 17%]
tests/test_g12a_causal_online_recourse.py::test_causal_12_midnight_boundary_crossover PASSED [ 19%]
tests/test_g12a_causal_online_recourse.py::test_causal_13_deterministic_replay PASSED [ 21%]
tests/test_g12a_causal_online_recourse.py::test_causal_14_ex_post_evaluation_independence PASSED [ 23%]
tests/test_g12a_causal_online_recourse.py::test_causal_15_finite_capacity_exhaustion_unassigned PASSED [ 25%]
tests/test_g2_monte_carlo_causality.py::test_mc_causal_01_same_history_different_future_same_current_action PASSED [ 26%]
tests/test_g2_monte_carlo_causality.py::test_mc_causal_02_future_delay_mutation_does_not_alter_past_decisions PASSED [ 28%]
tests/test_g2_monte_carlo_causality.py::test_mc_causal_03_observed_past_event_changes_future_action PASSED [ 30%]
tests/test_g2_monte_carlo_causality.py::test_mc_causal_04_and_05_cannot_move_already_docked_flight PASSED [ 32%]
tests/test_g2_monte_carlo_causality.py::test_mc_causal_06_midnight_crossover_handled_monotonically PASSED [ 34%]
tests/test_g2_monte_carlo_causality.py::test_mc_causal_07_missing_decision_timestamp_handled_fail_closed PASSED [ 36%]
tests/test_g2_monte_carlo_causality.py::test_mc_causal_08_decision_trace_contains_epoch_and_reason PASSED [ 38%]
tests/test_g2_monte_carlo_causality.py::test_mc_causal_09_deterministic_replay PASSED [ 40%]
tests/test_g2_monte_carlo_causality.py::test_feas_01_decomposition_separates_physical_conflict_from_static_consistency PASSED [ 42%]
tests/test_g2_monte_carlo_causality.py::test_feas_02_physical_conflict_causes_composite_infeasible PASSED [ 44%]
tests/test_g2_monte_carlo_causality.py::test_mode_01_mode_b1_retrospective_regime PASSED [ 46%]
tests/test_g2_monte_carlo_causality.py::test_mode_02_mode_b2_online_regime PASSED [ 48%]
tests/test_g2_monte_carlo_causality.py::test_mode_03_mode_c1_vs_c2_optimality_flag PASSED [ 50%]
tests/test_g2_monte_carlo_causality.py::test_stat_01_crn_paired_comparison_metrics PASSED [ 51%]
tests/test_finite_remote_capacity_p02.py::test_r01_verifier_detects_overlap_on_finite_remote_stand PASSED [ 53%]
tests/test_finite_remote_capacity_p02.py::test_r02_verifier_detects_exceeding_k_on_pooled_remote PASSED [ 55%]
tests/test_finite_remote_capacity_p02.py::test_r03_unbounded_apron_allows_concurrency PASSED [ 57%]
tests/test_finite_remote_capacity_p02.py::test_r04_greedy_does_not_place_overlapping_flights_on_same_finite_stand PASSED [ 59%]
tests/test_finite_remote_capacity_p02.py::test_r05_greedy_respects_capacity_k_of_pooled_remote PASSED [ 61%]
tests/test_finite_remote_capacity_p02.py::test_r06_cpsat_enforces_no_overlap_on_finite_remote_stand PASSED [ 63%]
tests/test_finite_remote_capacity_p02.py::test_r07_cpsat_enforces_capacity_k_pooled_remote PASSED [ 65%]
tests/test_finite_remote_capacity_p02.py::test_r08_sa_treats_remote_stand_overlap_as_infeasible PASSED [ 67%]
tests/test_finite_remote_capacity_p02.py::test_r09_sa_neighborhood_rejects_remote_stand_overlap PASSED [ 69%]
tests/test_finite_remote_capacity_p02.py::test_r10_hybrid_solver_preserves_capacity_semantics PASSED [ 71%]
tests/test_finite_remote_capacity_p02.py::test_r11_hybrid_incumbent_reverified_before_transfer PASSED [ 73%]
tests/test_finite_remote_capacity_p02.py::test_r12_generator_max_overflow_zero_creates_no_overflow PASSED [ 75%]
tests/test_finite_remote_capacity_p02.py::test_r13_generator_max_overflow_k_discrete_and_pooled PASSED [ 76%]
tests/test_finite_remote_capacity_p02.py::test_r14_no_silent_unbounded_fallback_when_forbidden PASSED [ 78%]
tests/test_finite_remote_capacity_p02.py::test_r15_diagnostic_separates_contact_and_remote_violations PASSED [ 80%]
tests/test_finite_remote_capacity_p02.py::test_r16_diagnostic_contains_max_concurrent_remote_usage PASSED [ 82%]
tests/test_finite_remote_capacity_p02.py::test_r17_reassignment_cost_calculated_correctly_for_remote_stand PASSED [ 84%]
tests/test_finite_remote_capacity_p02.py::test_r18_overflow_cost_separation PASSED [ 86%]
tests/test_finite_remote_capacity_p02.py::test_r19_time_window_with_buffer_min_applied_uniformly PASSED [ 88%]
tests/test_finite_remote_capacity_p02.py::test_r20_zero_capacity_gate_rejected PASSED [ 90%]
tests/test_finite_remote_capacity_p02.py::test_r21_duplicate_gate_id_rejected PASSED [ 92%]
tests/test_finite_remote_capacity_p02.py::test_r22_negative_capacity_gate_rejected PASSED [ 94%]
tests/test_finite_remote_capacity_p02.py::test_r23_unknown_resource_type_rejected PASSED [ 96%]
tests/test_finite_remote_capacity_p02.py::test_r24_backward_compatibility_unbounded_apron PASSED [ 98%]
tests/test_finite_remote_capacity_p02.py::test_differential_oracle_solvers_agree_on_finite_remote_feasibility PASSED [100%]

============================= 52 passed in 1.55s ==============================
```
