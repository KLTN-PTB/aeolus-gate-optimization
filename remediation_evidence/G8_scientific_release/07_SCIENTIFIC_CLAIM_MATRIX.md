# AEOLUS-G8 — Comprehensive Scientific Claim Reconciliation Matrix

## 1. Domain-by-Domain Scientific Claims Audit

This matrix reconciles every core scientific claim advanced in the Aeolus Gate Optimization project against source code implementations, test evidence, raw inputs, experimental artifacts, statistical validity, reproducibility, and documented limitations.

---

### 1.1 Data & Feature Engineering Domain

| Field | Claim 1.1: T-2h Temporal Cutoff Information Barrier | Claim 1.2: Real Data Provenance & Anti-Rebranding Guard | Claim 1.3: Flight Chain & Weather Decoupling |
|:---|:---|:---|:---|
| **Claim** | Operational features are strictly frozen at scheduled arrival minus 2 hours ($T-2\text{h}$) to eliminate future data leakage. | Datasets are tagged into explicit origins (`REAL_AEOLUS`, `SYNTHETIC_CANONICAL`); synthetic scenarios cannot claim real provenance. | Flight Chain and METAR weather features are excluded from certified production pipeline to prevent lookahead leakage. |
| **Source Implementation** | `src/contracts/temporal.py`, `validate_feature_temporal_availability()` | `src/contracts/provenance.py`, `dashboard/adapters/export_adapter.py` | `src/data/leakage_rules.py`, `src/features/` |
| **Test Evidence** | `tests/test_g1_provenance_and_temporal_contracts.py::test_time02` | `tests/test_g1_...::test_prov02`, `test_prov05`, `tests/test_g7_...::test_inv07` | `tests/test_leakage_audit.py`, `tests/test_g3_ml_validation.py` |
| **Experiment Artifact** | `artifacts/remediation/ml_validation/leakage_audit.json` | `remediation_evidence/G1_data_contracts/04_EVIDENCE_MANIFEST.json` | `artifacts/remediation/ml_validation/feature_ablation.csv` |
| **Raw Input Evidence** | BTS TranStats 2016–2023 flight schedules with local timestamps. | Parquet files in `data/processed/` and scenario configs in `configs/`. | BTS raw flight records and METAR weather logs. |
| **Statistical Validity** | Prevents feature lookahead bias; causal timestamps strictly enforced. | Cryptographic verification of scenario manifests. | Empirically verified: omitting chain features removes unverified upstream assumptions. |
| **Reproducibility** | Deterministic cutoff assertion across all flight rows. | Bitwise validation on CSV/JSON export serialization. | Fully reproducible via frozen ablation metrics. |
| **Limitation** | Real flight turn information earlier than $T-2\text{h}$ is unavailable if gate delays occur upstream. | Raw BTS data omits `TAIL_NUM` column; real-only mode yields unlinked turn jobs. | Flight Chain comparison requires formal thesis advisor written deviation approval. |
| **Verdict** | **`CERTIFIED_PASS`** | **`CERTIFIED_PASS`** | **`ACCEPTED_WITH_LIMITATION`** |

---

### 1.2 Machine Learning & Uncertainty Domain

| Field | Claim 2.1: Inbound Continuous Student-t Simulation Core | Claim 2.2: Outbound Calibrated Probability Classification | Claim 2.3: Median Baseline vs ML Regressor Duality |
|:---|:---|:---|:---|
| **Claim** | Model P4 (NGBoost Student-t) generates continuous heavy-tailed arrival delay distributions with native checkpoint inference. | Outbound delays $\ge 15$ min are predicted by calibrated Logistic Regression and XGBoost classifiers, eliminating heuristic sigmoid risk scores. | Median regressor achieves lower MAE due to L1 median optimality on zero-skew bulk, but ML wins on RMSE and extreme tail error ($\ge 15, \ge 60$m). |
| **Source Implementation** | `artifacts/probabilistic/ngboost_student_t/`, `src/models/probabilistic/` | `scripts/train_outbound_classifiers_g3.py`, `src/data/departure_preprocessing.py` | `src/models/`, `artifacts/dual_core/models/departure_xgboost_baseline_v1.joblib` |
| **Test Evidence** | `tests/test_ml_research_validation_p08.py`, `tests/test_g4_native_e2e.py` | `tests/test_g3_ml_validation.py` (14 tests) | `tests/test_ml_research_validation_p08.py`, `tests/test_g3_ml_validation.py` |
| **Experiment Artifact** | `model_weights_frozen_v1.joblib` (SHA: `e7e7462f...`) | `artifacts/remediation/outbound_classification/calibrated_metrics.json` | `artifacts/remediation/ml_validation/regression_metrics.csv` |
| **Raw Input Evidence** | Year 2023 Selection split ($N = 332,734$ flights). | Year 2023 Selection split ($N = 332,734$, prevalence = $20.63\%$). | Year 2023 Selection split ($N = 332,734$). |
| **Statistical Validity** | Degrees of freedom $\nu = 4.5$ captures heavy-tail apron delay spikes. | Brier Score = $0.156$ (vs $0.168$ baseline); $\text{ECE} \approx 0.011 \le 0.05$ (Platt/Isotonic). | Mathematical proof: L1 median theorem explains MAE; L2 gradient boosting minimizes variance & tails. |
| **Reproducibility** | Bitwise model weight verification; exact quantile replication. | Deterministic probability calibration on 2022 dev split. | Recomputed and verified across full selection split. |
| **Limitation** | Model P5 (Quantile Regressor) is predictions-only (no serialized binary). | Outbound Random Forest classifier was not serialized; calibrated LR and XGBoost are certified. | Students must explain the L1 vs L2 duality during defense. |
| **Verdict** | **`CERTIFIED_PASS`** | **`CERTIFIED_PASS`** | **`CERTIFIED_PASS`** |

---

### 1.3 Operations Research & Optimization Domain

| Field | Claim 3.1: Hard Constraint Independent Verification | Claim 3.2: Combinatorial Oracle Parity | Claim 3.3: Hybrid Solver Monotonicity & 0% Gain Theorem |
|:---|:---|:---|:---|
| **Claim** | All solver solutions are verified by an independent checker outside the solver for 100% feasibility (no overlaps, buffer, remote capacity). | On small instances, CP-SAT proven optimum matches brute-force exhaustive combinatorial oracle to within $< 10^{-4}$ tolerance. | Simulated Annealing improves Greedy solutions (+14.2 points); on CP-SAT optimal solutions, Hybrid reports honest $0.0\%$ improvement. |
| **Source Implementation** | `src/optimization/domain.py`, `verify_hard_constraints_independently()` | `src/optimization/solvers/exhaustive_oracle.py`, `CPSatGateSolver` | `src/optimization/solvers/hybrid_solver.py`, `src/optimization/sa/` |
| **Test Evidence** | `tests/test_g5_solver_correctness.py::test_or01..06`, `test_g7_...::test_inv03` | `tests/test_g5_...::test_or09`, `tests/test_g7_...::test_inv04` | `tests/test_g5_...::test_hyb01..03`, `tests/test_sa_benchmark.py` |
| **Experiment Artifact** | `artifacts/remediation/benchmarks/g5_fair_benchmark/fair_benchmark_results.json`| `artifacts/remediation/cp_sat/parity_results.json` | `artifacts/development_end_to_end/aggregate_metrics.json` |
| **Raw Input Evidence** | 5 multi-scale scenarios ($N=10$ to $300$ flights, $M=4$ to $51$ gates). | Small benchmark instances ($N=3, M=2$). | Fair benchmark instances and scalability scenarios. |
| **Statistical Validity** | Independent audit decoupling verifier from solver internal state. | Exact mathematical global minimum enumeration. | Mathematical theorem: Global optimum cannot be improved by metaheuristics. |
| **Reproducibility** | Deterministic verifier execution with zero tolerance on conflicts. | Deterministic permutation invariance ($< 10^{-4}$ diff). | 100% reproducible across all seeds and scenarios. |
| **Limitation** | Scalability on $N > 300$ flights encounters CP-SAT time horizon (30s). | Oracle is computationally restricted to $N \le 5$ due to exponential complexity. | Defends $0\%$ hybrid gain as mathematical proof rather than defect. |
| **Verdict** | **`CERTIFIED_PASS`** | **`CERTIFIED_PASS`** | **`CERTIFIED_PASS`** |

---

### 1.4 Simulation & Causality Domain

| Field | Claim 4.1: Non-Anticipative Online Recourse (Mode B2) | Claim 4.2: Optimal Foresight Oracle (Mode C-Oracle) | Claim 4.3: Physical Conflict vs Static Feasibility |
|:---|:---|:---|:---|
| **Claim** | Mode B2 enforces strict event-driven online causality; distant future delays cannot alter past or current gate decisions. | Mode C-Oracle uses CP-SAT to establish a mathematically proven offline lower bound, separated from the Greedy baseline (Mode C1). | Separates operational physical gate conflicts from static slot consistency, resolving the misleading "0% feasibility" artifact. |
| **Source Implementation** | `src/simulation/monte_carlo_engine_v2.py`, `evaluate_mode_b2...` | `src/simulation/monte_carlo_engine_v2.py`, `evaluate_mode_c_optimal...` | `src/simulation/monte_carlo_engine_v2.py`, `decompose_feasibility()` |
| **Test Evidence** | `tests/test_g2_monte_carlo_causality.py::test_mc_causal_01..09`, `test_g7_...::test_inv02`| `tests/test_g2_...::test_mc_oracle_01..04` | `tests/test_g2_...::test_mc_feasibility_01..03` |
| **Experiment Artifact** | `artifacts/remediation/monte_carlo_remediated/remediated_simulation_manifest.json`| `artifacts/remediation/monte_carlo_remediated/remediated_statistical_summary.json`| `artifacts/remediation/monte_carlo_remediated/remediated_paired_comparison.csv` |
| **Raw Input Evidence** | 100 correlated realization scenarios via Gaussian Copula ($\rho = 0.45$). | 100 correlated realization scenarios. | 100 correlated realization scenarios. |
| **Statistical Validity** | Causal event sweep verified: future mutation invariant holds 100%. | CP-SAT optimality proven boolean verified on 100% of oracle runs. | Disaggregated accounting reveals 76.0% physical contact conflicts in Mode A. |
| **Reproducibility** | CRN scenario-by-scenario paired delta replication. | Verified deterministic lower bound across all seeds. | Exact replication of disaggregated conflict counters. |
| **Limitation** | Validated on $N=100$ pilot realizations; full $N=500$ batch takes ~2h. | Offline foresight is non-deployable in real-world operations. | Static schedule plans naturally degrade under stochastic apron delays. |
| **Verdict** | **`CERTIFIED_PASS`** | **`CERTIFIED_PASS`** | **`CERTIFIED_PASS`** |

---

### 1.5 Presentation & Dashboard Domain

| Field | Claim 5.1: Scientific Truth-in-Labeling UI | Claim 5.2: Canonical Path Security Containment | Claim 5.3: Offline & Demo Readiness |
|:---|:---|:---|:---|
| **Claim** | UI strictly displays `OPTIMAL (PROVEN)` only on proven optima, tags heuristic benchmarks, and displays `N/A` on missing CDFs. | File path validators enforce canonical path containment, preventing directory traversal and prefix spoofing attacks. | Dashboard runs offline without external cloud dependencies; state isolation prevents cross-scenario leakage. |
| **Source Implementation** | `dashboard/core/status_mapping.py`, `dashboard/core/contracts.py` | `dashboard/core/config.py`, `is_path_allowlisted()`, `is_model_dir_...` | `dashboard/app.py`, `dashboard/services/scenario_service.py` |
| **Test Evidence** | `tests/test_g6_dashboard_integrity.py::test_ui_solver_03`, `test_ui_data_04` | `tests/test_g6_...::test_ui_sec_01..02` | `tests/dashboard/` (359 tests passed) |
| **Experiment Artifact** | `docs/dashboard/redesign/UI-R08/` documentation package. | Audit test logs in `remediation_evidence/G6_dashboard/`. | Export manifests in `audit_exports/`. |
| **Raw Input Evidence** | Streamlit AppTest framework inspecting DOM elements headlessly. | Canonical Path resolution via `pathlib.Path.resolve()`. | 5 interactive Streamlit pages. |
| **Statistical Validity** | 100% view model parity against backend domain structures. | Rigorous containment: `resolved == base or base in resolved.parents`. | 359 tests pass with zero assertion failures in 8.91s. |
| **Reproducibility** | Deterministic UI rendering without background execution on filter change. | 100% reproducible path security verification. | 100% reproducible headless test suite. |
| **Limitation** | Live browser visual inspection remains `VISUAL_QA_PENDING`. | Only allowlisted directories (`artifacts/`, `configs/`) are accessible. | Requires Streamlit local server launch during thesis defense. |
| **Verdict** | **`CERTIFIED_PASS`** | **`CERTIFIED_PASS`** | **`ACCEPTED_WITH_LIMITATION`** |
