# AEOLUS-G7 — Test Results and Execution Breakdown

## 1. Executive Summary Table

| Test Suite / Scope | Collected | Executed | Passed | Failed | Skipped | Pass Rate | Runtime |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Remediation Suite (G1–G7)** | 127 | 127 | 127 | 0 | 0 | **100.0%** | 24.16s |
| **Scientific Invariants (INV & FLOW)** | 15 | 15 | 15 | 0 | 0 | **100.0%** | 1.30s |
| **Dashboard Acceptance Suite** | 359 | 359 | 359 | 0 | 0 | **100.0%** | 8.91s |
| **Research Protocols (P07–P09)** | 89 | 89 | 89 | 0 | 0 | **100.0%** | 6.21s |
| **Full Repository Test Suite** | 2,117 | 2,117 | 2,113 | 4 | 0 | **99.81%** | 148.81s |
| **Reproducibility Workloads** | 6 | 6 | 6 | 0 | 0 | **100.0%** | 2.15s |

---

## 2. Remediation Test Suite Breakdown by Gate

| Gate | Test File | Test Items | Status | Key Coverage Area |
|:---|:---|:---:|:---:|:---|
| **G1** | `tests/test_g1_provenance_and_temporal_contracts.py` | 22 | **PASS** | T-2h barrier, provenance tagging, data lineage contracts |
| **G2** | `tests/test_g2_monte_carlo_causality.py` | 24 | **PASS** | Non-anticipative Mode B2, Mode C-Oracle bounds, Copula positive definiteness |
| **G3** | `tests/test_g3_ml_validation.py` | 14 | **PASS** | Outbound classifier calibration, Brier score, ROC-AUC, thresholding |
| **G4** | `tests/test_g4_native_e2e.py` | 19 | **PASS** | Verified aircraft turn pairing, tail-number linkage, native pipeline |
| **G5** | `tests/test_g5_solver_correctness.py` | 21 | **PASS** | CP-SAT optimality, Greedy determinism, SA validation, fair benchmark |
| **G6** | `tests/test_g6_dashboard_integrity.py` | 12 | **PASS** | Research vs Presentation modes, SHAP display, export adapters |
| **G7** | `tests/test_g7_scientific_invariants.py` | 15 | **PASS** | INV-01..10 metamorphic properties and FLOW-A..E end-to-end flows |
| **Total** | **7 Files** | **127** | **PASS** | **100.0% Remediation Verification** |

---

## 3. Detailed Results for Invariant & Metamorphic Suite (`tests/test_g7_scientific_invariants.py`)

| ID | Test Name | Invariant Description | Status | Execution Time |
|:---|:---|:---|:---:|:---:|
| `INV-01` | `test_inv01_row_permutation_invariance_verified_pairing` | Permuting input legs produces identical verified turn pairs | **PASS** | 0.08s |
| `INV-02` | `test_inv02_future_only_mutation_invariance_online_recourse` | Mutating distant future delays does not alter past/current decisions in Mode B2 | **PASS** | 0.09s |
| `INV-03` | `test_inv03_solver_feasible_output_zero_hard_violations` | Any feasible solver output satisfies 100% hard constraints | **PASS** | 0.12s |
| `INV-04` | `test_inv04_oracle_cpsat_exact_agreement_on_small_instance` | Exhaustive combinatorial oracle and CP-SAT proven optimum agree to < 1e-4 | **PASS** | 0.09s |
| `INV-05` | `test_inv05_deterministic_reproducibility_same_seed_config` | Solvers with same scenario, config, seed produce bitwise identical assignments | **PASS** | 0.08s |
| `INV-06` | `test_inv06_paired_comparison_alignment_permutation_invariance` | Paired differences preserve mean and variance under row permutation | **PASS** | 0.08s |
| `INV-07` | `test_inv07_adapter_rejects_synthetic_to_real_rebranding` | Export adapter rejects synthetic scenario claiming REAL_AEOLUS origin | **PASS** | 0.08s |
| `INV-08` | `test_inv08_missing_checkpoint_fails_closed_in_strict_real` | Missing model checkpoint in strict mode fails closed without dummy fallback | **PASS** | 0.07s |
| `INV-09` | `test_inv09_metrics_invariance_under_flight_ordering` | Objective evaluation function yields identical value under reordered flight sequence | **PASS** | 0.08s |
| `INV-10` | `test_inv10_unknown_solver_status_never_becomes_optimal` | Status mapping never maps UNKNOWN or TIME_LIMIT without proof to OPTIMAL | **PASS** | 0.08s |
| `FLOW-A` | `test_flow_a_real_data_ml_turn_cpsat_pipeline` | Real Data -> ML Predictions -> Verified Aircraft Turn -> CP-SAT Optimization | **PASS** | 0.10s |
| `FLOW-B` | `test_flow_b_synthetic_scenario_solver_independent_evaluator` | Synthetic Scenario -> Multi-Solver -> Independent Verifier Parity | **PASS** | 0.09s |
| `FLOW-C` | `test_flow_c_monte_carlo_paired_metrics_dashboard` | Monte Carlo Simulation -> Paired Comparison -> Dashboard Metrics View Model | **PASS** | 0.08s |
| `FLOW-D` | `test_flow_d_ml_evidence_metrics_reports` | ML Predictive Metrics Lineage -> Loss Breakdown -> Calibration Invariants | **PASS** | 0.08s |
| `FLOW-E` | `test_flow_e_dashboard_scenario_optimization_artifact_export` | Dashboard Scenario View -> Solver Execution -> Verified JSON & CSV Export | **PASS** | 0.08s |

---

## 4. Full Suite Non-Passing Items Breakdown

The 4 legacy test failures documented in Section 3 of `02_IMPLEMENTATION_REPORT.md` are:
1. `tests/benchmark/test_model_registry.py::test_registry_integration_retrieval` (Dual-Core expansion introduces `CORE_DEPARTURE`).
2. `tests/test_r22_system_freeze_v3.py::test_guard_v3_verifies_all_frozen_files` (Intermediate Sep 2026 hash snapshot).
3. `tests/test_r22_system_freeze_v3.py::test_guard_v3_authorizes_clean_post_holdout_access` (Intermediate Sep 2026 hash snapshot).
4. `tests/test_r27_certification_hardening.py::test_r22_freeze_manifest_integrity` (Intermediate Sep 2026 hash snapshot).

All other 2,113 tests in the repository pass cleanly with zero errors.
