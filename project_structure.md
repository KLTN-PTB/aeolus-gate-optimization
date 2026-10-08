# Project Structure — Aeolus V4 Full System

**Current Protocol**: `AEOLUS_V4_PHASE14_FINAL_CERTIFICATION` (Phase P14 Certified)  
**Lifecycle Status**: `CERTIFIED_WITH_LIMITATIONS` (Phase P14 Final Certification, REBUILD_REQUIRED = NO)  
**Host Environment**: Python 3.11.15 (Windows 10 AMD64)  
**Active Test Harness**: 1,216 active tests (100% PASS across full suite), including 75 narrow certification tests & 21 P11-R downstream parity tests (4 legacy guard tests safely quarantined)  

---

## 1. Top-Level Repository Layout

```text
Aeolus/
├── configs/                         # YAML configuration specs and parameter registries
│   ├── base.yaml                    # Dual prediction task contracts (Core vs Auxiliary)
│   ├── current_state.yaml           # Machine-readable current system state (v2.0, frozen)
│   ├── model_catalog_v2.yaml        # Authoritative catalog of all point & probabilistic models
│   ├── model_selection_protocol_v2.yaml # Pre-registered selection criteria & indifference band
│   ├── monte_carlo_protocol_v2.yaml # Downstream Monte Carlo simulation parameters
│   ├── probabilistic_metric_capabilities_v2.yaml # Contract flags for probabilistic scoring
│   ├── reconstructed_chain_feature_policy.yaml # Fail-closed chain policy
│   ├── retired_guard_scope_manifest.json # Quarantined historical freeze-guard manifest
│   └── seed_registry.yaml           # Deployment seeds [202601, 202602, 202603]
│
├── data/                            # Local/untracked data boundary (IMMUTABLE / GIT-IGNORED)
│   ├── raw/                         # Raw BTS flight CSVs (2016–2024, 54.6M rows)
│   │   ├── tabular/<2016-2024>/     # Canonical raw BTS On-Time Performance tables
│   │   └── chain/<2016-2024>/       # Original Aeolus .pt files (FINAL_NO_GO, immutable)
│   ├── processed/                   # Versioned derived partitions
│   │   ├── tabular_by_year/         # Parquet partitions by year (2016–2024)
│   │   ├── inbound_atl/             # Core Arrival population (DEST=ATL)
│   │   ├── outbound_atl/            # Auxiliary Departure population (ORIGIN=ATL)
│   │   └── flight_chain_reconstructed_v1/ # Reconstructed schedule chain (2016–2023)
│   └── simulation/                  # Synthetic operational benchmark scenarios
│
├── src/                             # Core Python source packages
│   ├── audit/                       # Verification, provenance, and protocol guard engines
│   │   ├── artifact_freshness.py    # Manifest freshness auditor
│   │   ├── claim_auditor.py         # Claim boundary verification
│   │   ├── protocol_guards.py       # Strict temporal & parameter guards
│   │   └── provenance.py            # Lineage tracking utilities
│   ├── contracts/                   # Mathematical distribution interfaces & contracts
│   │   └── distribution.py          # PredictiveDistribution, NGBoostStudentTDistribution,
│   │                                # QuantilePredictiveDistribution, EmpiricalDistribution
│   ├── data/                        # Ingestion, canonicalization, and preprocessing
│   │   ├── access_guard.py          # Temporal partition enforcement
│   │   ├── canonicalize.py          # Schema projection and validation
│   │   ├── leakage_rules.py         # Task-aware fail-closed leakage firewall
│   │   ├── preprocessing.py         # Tabular preprocessing pipelines
│   │   └── stratified_loader.py     # Stratified sample loader for evaluation
│   ├── dependence/                  # Multivariate uncertainty & copula modeling
│   │   ├── base.py                  # Base dependence interfaces
│   │   ├── d0_independent.py        # Independent marginals
│   │   ├── d1_scenario.py           # Scenario-based coupling
│   │   ├── d2_gaussian_copula.py    # Gaussian copula dependence
│   │   ├── pit.py                   # Probability Integral Transform utilities
│   │   └── psd.py                   # Positive semi-definite projection
│   ├── evaluation/                  # Scoring metrics, guards, and statistical testing
│   │   ├── algorithmic_stability.py # Cross-fold seed & parameter stability
│   │   ├── calibration.py           # Interval coverage & calibration assessment
│   │   ├── downstream_comparison.py # Operational gate schedule cost scoring
│   │   ├── final_evaluation_guard_v2.py # Pre-evaluation cryptographic freeze verifier
│   │   ├── forecast_metrics.py      # CRPS, pinball, NLL, MAE, RMSE metrics
│   │   ├── mc_convergence.py        # Monte Carlo sample size convergence
│   │   ├── model_selection.py       # Ranking-free multi-attribute selection
│   │   ├── native_downstream_p4.py  # P4 native student-t Monte Carlo downstream engine
│   │   ├── paired_comparison.py     # Paired statistical significance (Wilcoxon/t-test)
│   │   └── week10_robustness_recourse.py # Robustness, recourse, sensitivity engine
│   ├── features/                    # Feature engineering & transformation
│   │   ├── refactored_features.py   # Refactored robust 10-feature arrival set
│   │   └── tabular_features.py      # Base schedule/calendar/carrier/route features
│   ├── models/                      # Point & probabilistic model implementations
│   │   ├── baselines.py             # Ridge, Logistic, Random Forest, HistGB baselines
│   │   ├── interfaces.py            # Base model wrapper interfaces
│   │   ├── registry.py              # Central model factory & capability lookup
│   │   └── probabilistic/           # Probabilistic forecasting candidates
│   │       ├── candidate_interfaces.py # P1-P5 candidate implementations
│   │       ├── metrics.py           # Scoring formulas & PRE_REGISTERED_QUANTILES
│   │       ├── student_t_correctness.py # Analytical Student-T CRPS (Jordan et al.)
│   │       └── unified_evaluation.py # Unified evaluation engine (CRPS, NLL, PIT)
│   ├── optimization/                # Flight-to-gate assignment optimization solvers
│   │   ├── config.py                # Solver budget configs & time limit ceilings
│   │   ├── domain.py                # Flight, Gate, Schedule, and Conflict data classes
│   │   ├── evaluation.py            # Objective cost function & hard constraint validator
│   │   ├── sa/                      # Simulated Annealing engine
│   │   │   ├── annealer.py          # Cooling schedule & Markov chain loop
│   │   │   ├── neighborhood.py      # Move operators (reassign, swap)
│   │   │   ├── objective.py         # Incremental cost evaluator
│   │   │   └── state.py             # Solution representation & incumbent tracker
│   │   └── solvers/                 # Multi-paradigm solver implementations
│   │       ├── cp_sat_solver.py     # Google OR-Tools CP-SAT exact formulation
│   │       └── greedy_solver.py     # Deterministic O(N log M) heuristic baseline
│   ├── pipeline/                    # End-to-end benchmark pipelines
│   │   ├── academic_point_benchmark.py # Point model rolling benchmark
│   │   └── probabilistic_benchmark_runner.py # Probabilistic candidate evaluation
│   └── simulation/                  # Airport operational turn & gate simulation
│       ├── aircraft_turn.py         # Aircraft turnaround buffer synthesis
│       ├── conflict_detector.py     # Gate overlap & minimum separation checking
│       ├── downstream_metrics.py    # Operational schedule impact metrics
│       ├── gate_simulator.py        # Discrete event gate dispatcher
│       ├── scenario_runner.py       # Multi-scenario operational batch runner
│       └── turn_synthesis.py        # Inbound-outbound aircraft pairing
│
├── tests/                           # Complete 1,216 active-test verification & regression harness
│   ├── audit/                       # Provenance & freeze audit tests
│   ├── benchmark/                   # Point & probabilistic benchmark integrity tests
│   ├── contracts/                   # Distribution contract & numerical safety tests
│   ├── downstream/                  # Gate solver semantics & budget tests
│   ├── evaluation/                  # Metric formula & guard verification tests
│   ├── probabilistic/               # P1-P5 correctness, CDF, and sampling tests
│   ├── selection/                   # Model selection & tie-breaking tests
│   ├── downstream/test_p11r_post_holdout.py # Phase P11-R post-holdout regression tests (7 passed)
│   ├── downstream/test_week10_robustness_freeze.py # Phase P10-B freeze & recourse tests (7 passed)
│   ├── downstream/test_native_p4_downstream.py # Phase P10-A P4 native downstream tests (7 passed)
│   ├── test_phase10_system_freeze.py        # Phase P10 cryptographic freeze audit (4 passed)
│   ├── test_r24_final_certification.py      # Final certification baseline tests (12 passed)
│   ├── test_r25_point_selection_consistency.py # Phase R25 gate tests (16 passed)
│   ├── test_r26_solver_equal_compute.py        # Phase R26 solver parity tests (9 passed)
│   ├── test_r27_certification_hardening.py    # Phase R27 hardening tests (12 passed)
│   ├── test_r28_probabilistic_audit.py        # Phase R28 probabilistic tests (14 passed)
│   ├── test_r29_execution_provenance.py       # Phase R29 provenance tests (16 passed)
│   ├── test_r30_final_reconciliation.py       # Phase R30 reconciliation tests (20 passed)
│   ├── test_r31_final_certification.py        # Phase R31 certification tests (15 passed)
│   ├── test_r33_p4_metric_lineage.py          # Phase R33 P4 lineage tests (8 passed)
│   ├── test_r34_p5_mathematical_audit.py      # Phase R34 P5 math audit tests (10 passed)
│   ├── test_r35_solver_repro.py               # Phase R35 solver repro tests (11 passed)
│   ├── test_r36_final_reconciliation.py       # Phase R36 reconciliation V2 tests (20 passed)
│   └── test_r37_final_certification.py        # Phase R37 final gate tests (19 passed)
│   # Note: 4 legacy freeze-guard tests safely quarantined via pytest.ini (retired_guard_scope_manifest.json)
│
├── scripts/                         # Operational execution & forensic verification scripts
│   ├── run_academic_point_benchmark_v2.py    # Point benchmark runner
│   ├── run_downstream_model_comparison.py    # Downstream gate simulation runner
│   ├── run_final_reproducibility_p13.py      # Phase P13 reproducibility verifier
│   ├── run_final_scientific_certification_p14.py # Phase P14 certification packager
│   ├── run_monte_carlo_comparison.py         # Monte Carlo uncertainty propagation
│   ├── run_native_p4_downstream.py           # Phase P10-A native P4 simulation runner
│   ├── run_p11r_post_holdout_reevaluation.py # Phase P11-R post-holdout re-evaluation runner
│   ├── run_post_holdout_evaluation_v2.py     # Historical 2024 post-holdout evaluation engine
│   ├── run_r26_solver_equal_compute.py       # 112-run solver benchmark runner
│   ├── run_r30_final_evidence_reconciliation.py # R30 reconciliation generator
│   ├── run_r31_final_certification.py        # R31 certification packager
│   └── run_week10_completion_and_freeze.py   # Phase P10-B freeze & recourse runner
│
├── docs/                            # Comprehensive documentation library
│   ├── README.md                    # Master documentation index & navigation hub
│   ├── CURRENT_STATE.md             # Authoritative system state & model registry (v4.0.0)
│   ├── audit/                       # Formal forensic audit & certification reports
│   │   ├── FINAL_EVIDENCE_CERTIFICATION_V5.md # Supreme authoritative certification (R37)
│   │   ├── FINAL_EVIDENCE_RECONCILIATION_V2.md # 13 Claims & Domains reconciliation (R36)
│   │   ├── R35_SOLVER_REPRODUCIBILITY_AUDIT.md # Solver compute semantics & env (R35)
│   │   ├── R34_P5_MATHEMATICAL_AUDIT.md       # P5 9-quantiles & approx CRPS (R34)
│   │   ├── R33_P4_METRIC_LINEAGE.md          # P4 Student-T authoritative lineage (R33)
│   │   └── R32_INDEPENDENT_FORENSIC_VERIFICATION.md # Independent verification (R32)
│   ├── dataset_audit/               # Historical schema, data dictionary, leakage audits
│   ├── decisions/                   # Architectural Decision Records (ADRs)
│   ├── experiments/                 # Historical experiment logs (Weeks 4-5)
│   ├── roadmap/                     # 12-week roadmap specifications (V3/V4)
│   └── thesis_notes/                # Academic research notes, assumptions, limitations
│
├── artifacts/                       # Cryptographic evidence & frozen manifests
│   ├── audit/                       # Verification manifests & SHA-256 sidecars (R13-P15)
│   │   ├── final_scientific_certification_p14.json (.sha256)
│   │   ├── p13_scoped_reproducibility.json (.sha256)
│   │   ├── final_evidence_certification_v5.json (.sha256)
│   │   ├── final_freeze_manifest_v5.json (.sha256)
│   │   ├── system_freeze_manifest.json (.sha256)
│   │   └── r36_final_evidence_reconciliation_v2.json (.sha256)
│   ├── manifests/                   # System freeze, model selection, protocol manifests
│   │   ├── academic_model_selection_v3.json (.sha256)
│   │   └── system_freeze_manifest_v3.json (.sha256)
│   ├── post_holdout_re_evaluation_v1/ # P11-R Repaired 2024 Post-Holdout Re-Evaluation artifacts
│   │   ├── p11r_marginal_forecast_metrics_2024.json (.sha256)
│   │   └── p11r_post_holdout_manifest.json (.sha256)
│   └── post_holdout_v3/             # Historical 2024 post-holdout evaluation artifacts
│       ├── marginal_forecast_metrics_2024_v3.json
│       └── post_holdout_evaluation_manifest_v3.json (.sha256)
│
├── FINAL_SCIENTIFIC_CERTIFICATION_REPORT.md # Authoritative Phase P14 final certification report
├── SCOPED_REPRODUCIBILITY_AUDIT.md          # Authoritative Phase P13 reproducibility report
├── FINAL_TEST_SCOPE_RECONCILIATION.md       # Authoritative Phase P12-R1 test reconciliation
├── P11R_FINAL_REPORT.md                     # Authoritative Phase P11-R post-holdout report
├── THESIS_EVIDENCE_NORMALIZATION_REPORT.md  # Authoritative Phase P15 thesis normalization report
├── PROJECT_SUMMARY.md               # Vietnamese executive summary of the entire project
├── project_structure.md             # This document (Repository tree & module guide)
└── README.md                        # Primary GitHub repository landing page
```

---

## 2. Key Architectural Invariants & Data Flow

### A. Dual Prediction Architecture (Firewall Boundary)
- **Core Arrival (`DEST = 'ATL'`)**: The only pipeline feeding gate simulation and optimization. Strictly conditioned on features available at $t_{\text{cutoff}} = \text{CRS\_DEP\_TIME} - 2\text{ hours}$. Weather and flight chain features are excluded to prevent point-in-time leakage.
- **Auxiliary Departure (`ORIGIN = 'ATL'`)**: A quarantined exploratory research benchmark for departure delay classification. Strictly barred from feeding the gate optimizer.

### B. Downstream Optimization Flow
1. **Forecast Input**: Arrival delay predictions pass into turn synthesis based on decoupled mathematical roles:
   - **Role B (`P5_quantile_regression`)**: Marginal Quantile Forecast Champion (9 pre-registered quantiles, forecast-only, no continuous density, no Monte Carlo draws).
   - **Role C (`P4_ngboost_student_t`)**: Continuous Downstream Simulation Champion (3-parameter Student-T parametric distribution, native continuous Monte Carlo sampling).
2. **Turn Synthesis**: Aircraft turns are constructed at ATL with scheduled turnaround buffers.
3. **Solver Allocation**:
   - `DeterministicGreedy`: $O(N \log M)$ heuristic initialization ($1.1$ ms).
   - `CPSat`: Exact branch-and-bound integer constraint solver ($0.44$ s mean runtime, proven global optimum on 28/28 audited instances).
   - `SimulatedAnnealing`: Stochastic local search ($2.0$ s ceiling, $2351$ moves).
   - `HybridCPSatSA`: 1.0s CP-SAT warm-start followed by 1.0s SA refinement ($\Delta = 0.0$ on audited cases).
4. **Equal Wall-Clock Budget & Hard Constraints**: All solvers operate under a strictly enforced equal wall-clock budget ceiling ($T = 2.0$ seconds). 100% hard constraint feasibility (zero gate conflicts, zero aircraft overlap, buffer satisfaction) across all evaluated instances. P4 native draws achieve 100% feasibility under 500 shocks in Summer peak compared to 27.6% for schedule-only and 2.4% for Ridge baseline. Evaluated on synthetic research instances; zero real-world ATL operations claimed.

---

## 3. Cryptographic Verification & Reproducibility
- All critical lineage artifacts across historical and post-repair generations are hashed and verifiable via `.sha256` sidecars.
- The narrow forensic certification suite (75 tests) executes in ~1.5 seconds:
  ```powershell
  python -m pytest tests/test_r24_final_certification.py tests/test_r27_certification_hardening.py tests/test_r31_final_certification.py tests/test_r37_final_certification.py tests/test_phase10_system_freeze.py -q
  ```
- The P11-R downstream regression suite (21 tests) executes in ~6.7 seconds:
  ```powershell
  python -m pytest tests/downstream/test_p11r_post_holdout.py tests/downstream/test_week10_robustness_freeze.py tests/downstream/test_native_p4_downstream.py -q
  ```
- The full active test harness (1,216 tests) executes in ~82 seconds under Python 3.11.15 Windows AMD64 (4 legacy freeze-guard tests safely quarantined via `pytest.ini`):
  ```powershell
  python -m pytest -q
  ```
