# 06_TEST_RESULTS.md

## AEOLUS-G12B Comprehensive Verification & Test Results Report

**Author:** Release Test Lead, Scientific Software Verification Engineer  
**Date:** October 12, 2026  
**Repository:** `aeolus-gate-optimization`

---

### 1. Test Execution Summary

| Test Suite File | Domain / Focus | Tests Run | Passed | Failed | Execution Time |
|---|---|---|---|---|---|
| `tests/test_g12b_contract_closure.py` | Contract Closure (A1-A4) | 10 | 10 | 0 | 1.17 s |
| `tests/test_g12b_hybrid_incumbent.py` | Hybrid Incumbent & Deadlines | 16 | 16 | 0 | 2.58 s |
| `tests/test_g12a_causal_online_recourse.py` | Causal Recourse Mode B2 | 15 | 15 | 0 | 1.25 s |
| `tests/test_g2_monte_carlo_causality.py` | Monte Carlo Causality & CRN | 12 | 12 | 0 | 0.95 s |
| `tests/test_sa_hybrid_correctness_p03.py` | SA & Hybrid Protocol P03 | 27 | 27 | 0 | 8.84 s |
| `tests/test_g5_solver_correctness.py` | OR Formulation & Parity | 25 | 25 | 0 | 12.15 s |
| `tests/test_simulated_annealing.py` | SA Heuristic Neighborhood | 25 | 25 | 0 | 5.32 s |
| **TOTAL** | **Full G12B Verification** | **130** | **130** | **0** | **32.26 s** |

**Overall Pass Rate: 100.0% (130 / 130 tests passing, 0 failures, 0 regressions)**

---

### 2. Detailed Breakdown: `test_g12b_contract_closure.py`

| Test Function | Verification Target | Status |
|---|---|---|
| `test_gate_01_incompatible_carrier_on_initial_gate_triggers_recourse` | Prohibited carrier on initial gate triggers online recourse | **PASSED** |
| `test_gate_02_incompatible_carrier_on_candidate_gate_rejected` | Prohibited carrier on candidate gate rejected | **PASSED** |
| `test_gate_03_gate_closed_during_occupancy_window_rejected` | Maintenance closure on gate during flight window rejected | **PASSED** |
| `test_gate_04_gate_only_partially_open_rejected` | Gate closing before buffer ends rejected | **PASSED** |
| `test_gate_05_compatible_available_gate_accepted` | Compatible and open gate accepted without reassignment | **PASSED** |
| `test_gate_06_no_valid_contact_gate_falls_back_to_remote` | Incompatible contact gates fall back to remote stand | **PASSED** |
| `test_gate_07_no_contact_and_no_remote_returns_unassigned` | Incompatible contact and full remote stand returns unassigned | **PASSED** |
| `test_gate_08_end_to_end_mode_b2_carrier_and_availability` | Full Mode B2 schedule simulation with carrier restrictions | **PASSED** |
| `test_stat_01_accounting_decomposes_evaluations_and_failures` | Statistical summary accounting decomposes failure modes | **PASSED** |
| `test_stat_03_solver_status_classification` | Explicit distinction between `ONLINE_FEASIBLE` and `ONLINE_INFEASIBLE_NO_CAPACITY` | **PASSED** |

---

### 3. Detailed Breakdown: `test_g12b_hybrid_incumbent.py`

| Test Function | Verification Target | Status |
|---|---|---|
| `test_hyb_01_sa_worse_objective_rejected_incumbent_preserved` | Outer incumbent guard rejects SA solution with degraded objective | **PASSED** |
| `test_hyb_02_sa_infeasible_proposal_rejected_incumbent_preserved` | Outer incumbent guard rejects SA candidate violating hard constraints | **PASSED** |
| `test_hyb_03_sa_exception_caught_incumbent_preserved` | Solver catches SA runtime exceptions and retains certified incumbent | **PASSED** |
| `test_hyb_04_sa_improved_feasible_objective_accepted` | Feasible, improved SA solution accepted by solver | **PASSED** |
| `test_hyb_05_strict_invariant_final_obj_le_incumbent_obj` | Strict invariant $J_{\text{final}} \le J_{\text{inc}} + 10^{-6}$ verified on real runs | **PASSED** |
| `test_hyb_06_cpsat_timeout_with_incumbent_passes_incumbent` | CP-SAT timeout with feasible incumbent passed to Stage 2 | **PASSED** |
| `test_hyb_07_sa_wallclock_deadline_terminates_early` | Tight deadline forces early SA break with `TIME_LIMIT` | **PASSED** |
| `test_hyb_08_zero_remaining_budget_skips_sa` | Stage 1 consuming budget causes SA skip without failure | **PASSED** |
| `test_hyb_09_total_wallclock_bounded_by_budget` | Total wall-clock time bounded by `total_wall_clock_budget_seconds` | **PASSED** |
| `test_hyb_10_deterministic_reproducibility_with_seed` | Identical seeds yield bit-for-bit identical assignments and costs | **PASSED** |
| `test_hyb_11_empty_flights_handled_gracefully` | Edge case: 0 flights returns valid empty assignment | **PASSED** |
| `test_hyb_12_single_flight_handled_gracefully` | Edge case: 1 flight returns optimal zero-cost assignment | **PASSED** |
| `test_hyb_13_all_remote_fallback_preserved` | Remote stand fallback honored under gate congestion | **PASSED** |
| `test_hyb_14_tight_buffer_feasibility_preserved` | Temporal buffer violations strictly prevented | **PASSED** |
| `test_hyb_15_carrier_incompatibility_preserved` | Allowed carriers constraint strictly enforced across both stages | **PASSED** |
| `test_hyb_16_hybrid_provenance_trace_completeness` | All required provenance and guard fields present in solver configuration | **PASSED** |
