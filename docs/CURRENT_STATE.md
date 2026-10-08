# Aeolus Gate Optimization — Current Architecture & State Registry

**Document Version**: 4.0.0  
**Generated At**: 2026-10-04T12:00:00Z  
**Architecture Protocol**: `AEOLUS_V4_PHASE14_FINAL_CERTIFICATION`  
**System Lifecycle State**: `CERTIFIED_WITH_LIMITATIONS` (Phase P14 Final Certification, `REBUILD_REQUIRED = NO`)  
**Machine-Readable Companion**: [`configs/current_state.yaml`](file:///D:/Study/Code/Python/Aelous/configs/current_state.yaml) (Frozen, Checksum Protected)  
**Authoritative Model Catalog**: [`configs/model_catalog_v2.yaml`](file:///D:/Study/Code/Python/Aelous/configs/model_catalog_v2.yaml)  
**Authoritative Model Registry Code**: [`src/models/registry.py`](file:///D:/Study/Code/Python/Aelous/src/models/registry.py)  
**Final Certification Manifest**: [`artifacts/audit/final_scientific_certification_p14.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/final_scientific_certification_p14.json)  
**Authoritative Certification Report**: [`FINAL_SCIENTIFIC_CERTIFICATION_REPORT.md`](file:///D:/Study/Code/Python/Aelous/FINAL_SCIENTIFIC_CERTIFICATION_REPORT.md)  

---

## 1. Executive Summary & Core Invariants

1. **Two Separate Operational Tasks**:
   - **Core Arrival** (`DEST = 'ATL'`): Inbound flight delay prediction at decision cutoff $t_{\text{cutoff}} = \text{CRS\_DEP\_TIME} - 2\text{ hours}$. Feeds downstream gate simulation and optimization. Strictly **NO Weather** features and **NO Flight Chain** features.
   - **Auxiliary Departure** (`ORIGIN = 'ATL'`): Secondary research benchmark for departure delay classification $1[\text{DEP\_DELAY} \ge 15\text{ min}]$. Strictly **forbidden from feeding the downstream gate optimizer**.
2. **Target Semantics**:
   - Classification: $y_{\text{arr\_cls}} = 1[\text{ARR\_DELAY} \ge 15\text{ min}]$.
   - Regression: $y_{\text{arr\_reg}} = \text{ARR\_DELAY}$ in signed minutes (no absolute value, no clipping, no target imputation).
3. **Decoupled Operational Capabilities & Certified Model Roles**:
   - In accordance with R39, Phase P10-A/B, and Phase P14 forensic determinations, models occupy non-overlapping operational roles:
     - **Point Prediction Baseline**: Ridge regression (`arrival_linear_baseline_v1`) provides linear reference with Historical 2024 MAE $22.9125$ min and P11-R Repaired 2024 MAE $23.39$ min.
     - **Role B — Marginal Quantile Forecast Champion**: P5 Quantile Regression (`P5_quantile_regression`) achieves Historical Approx CRPS $16.7724$ min and Pinball Loss $6.8211$ min across 9 pre-registered quantiles. P5 is **forecast-only**, disclaims continuous density, continuous NLL, and generative Monte Carlo sampling (`NOT_AVAILABLE`), and was neither reconstructed nor retrained.
     - **Role C — Continuous Downstream Simulation Champion**: P4 NGBoost Student-T (`P4_ngboost_student_t`) provides a 3-parameter parametric continuous density ($\mu, \sigma, \nu$), exact continuous CRPS ($18.33$ min P11-R closed-form; $17.6532$ min historical), continuous NLL ($4.62$ P11-R; $4.6307$ historical), and Point MAE $21.97$ min (P11-R). P4 is the **sole authorized probabilistic engine** for native downstream Monte Carlo flight delay sampling.
4. **Dual 2024 Evidence Generations (Strict Separation)**:
   - **Generation 1 — `HISTORICAL_2024_RESULTS`**: Evaluated prior to methodology repair (`artifacts/post_holdout_v3/marginal_forecast_metrics_2024_v3.json`). Preserved immutably as historical benchmark evidence.
   - **Generation 2 — `P11R_POST_HOLDOUT_REEVALUATION_AFTER_METHODOLOGY_REPAIR`**: Evaluated once under cryptographic freeze following P10-B (`artifacts/post_holdout_re_evaluation_v1/p11r_marginal_forecast_metrics_2024.json`). Authoritative post-repair post-holdout evidence. Never referred to as first-access or untouched holdout.
5. **Downstream Gate Optimization & Equal Wall-Clock Budget**:
   - Evaluated across 28 seasonal scenarios (Historical R26, 112 runs) and 16 operational scenarios (P10-A/P11-R, 64 runs) under an enforced equal wall-clock budget ceiling ($T = 2.0$ seconds).
   - Under 500 P4 shocks in Summer peak, P4 native downstream schedule achieves **100% feasibility** (zero gate conflicts, zero tow-buffer violations), compared to 27.6% for schedule-only, 2.4% for Ridge baseline, and 0.0% for oracle baseline.
   - All downstream evaluations operate on synthetic research benchmark scenarios; zero real-world operational ATL deployment is claimed.
6. **Active Test Suite & Cryptographic Lineage**:
   - Full test suite: **1,216 active tests passing 100%** (0 failures, 4 legacy freeze-guard tests safely quarantined via `pytest.ini`).
   - Narrow forensic certification gate: **75 tests passing 100%** across 5 files (`tests/test_r24_final_certification.py`, `tests/test_r27_certification_hardening.py`, `tests/test_r31_final_certification.py`, `tests/test_r37_final_certification.py`, `tests/test_phase10_system_freeze.py`).
   - P11-R downstream regression suite: **21 tests passing 100%** across 3 files (`tests/downstream/test_p11r_post_holdout.py`, `tests/downstream/test_week10_robustness_freeze.py`, `tests/downstream/test_native_p4_downstream.py`).
   - Model weights checkpoint: `artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib` SHA-256 `e7e7462f17b65b276ebdee9c7beced15e090f69b088a18896d5a91aaa8cb062f` verified.

---

## 2. Authoritative Model Catalog & Dual Holdout Metrics

| Model ID | Task & Family | Certified Role | Downstream Eligible | Historical Holdout (2024) | P11-R Repaired Holdout (2024) | Source Manifest |
| :--- | :--- | :--- | :---: | :--- | :--- | :--- |
| **`arrival_linear_baseline_v1`** | Core Arrival (`linear`) | Point Baseline | **Yes** (Point) | MAE: **22.9125 min** | MAE: **23.39 min** | [`marginal_forecast_metrics_2024_v3.json`](file:///D:/Study/Code/Python/Aelous/artifacts/post_holdout_v3/marginal_forecast_metrics_2024_v3.json)<br>[`p11r_marginal_forecast_metrics_2024.json`](file:///D:/Study/Code/Python/Aelous/artifacts/post_holdout_re_evaluation_v1/p11r_marginal_forecast_metrics_2024.json) |
| **`arrival_xgboost_baseline_v1`** | Core Arrival (`xgboost`) | Point Benchmark | **Yes** (Point) | MAE: **24.3643 min** | Historical reference | [`marginal_forecast_metrics_2024_v3.json`](file:///D:/Study/Code/Python/Aelous/artifacts/post_holdout_v3/marginal_forecast_metrics_2024_v3.json) |
| **`arrival_weighted_ensemble_v1`** | Core Arrival (`weighted_ensemble`) | Point Co-Champion (Dev) | **Yes** (Point) | MAE: **23.3175 min** | Historical reference | [`marginal_forecast_metrics_2024_v3.json`](file:///D:/Study/Code/Python/Aelous/artifacts/post_holdout_v3/marginal_forecast_metrics_2024_v3.json) |
| **`P5_quantile_regression`** | Core Arrival (`quantile_regression`) | **Role B**: Marginal Quantile Forecast Champion | **No** (Forecast-only, 9 quantiles) | Approx CRPS: **16.7724 min**<br>Pinball: **6.8211 min**<br>MAE: **21.6881 min** | *Preserved historical forecast-only; not reconstructed, not retrained* | [`r34_p5_capability_forensics.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r34_p5_capability_forensics.json)<br>[`final_scientific_certification_p14.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/final_scientific_certification_p14.json) |
| **`P4_ngboost_student_t`** | Core Arrival (`ngboost_student_t`) | **Role C**: Continuous Downstream Simulation Champion | **Yes** (Native Student-T draws) | Continuous CRPS: **17.6532 min**<br>Continuous NLL: **4.6307** | Point MAE: **21.97 min**<br>Point RMSE: **54.21 min**<br>Continuous CRPS: **18.33 min**<br>Continuous NLL: **4.62**<br>Brier ($Y \ge 15$): **0.1544**<br>Mean $\nu$: **2.52** | [`r33_p4_metric_lineage.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r33_p4_metric_lineage.json)<br>[`p11r_marginal_forecast_metrics_2024.json`](file:///D:/Study/Code/Python/Aelous/artifacts/post_holdout_re_evaluation_v1/p11r_marginal_forecast_metrics_2024.json) |
| **`oracle_actual`** | Reference (`oracle`) | Non-Deployable Upper Bound | **No** | MAE: **0.0000 min**<br>CRPS: **0.0000 min** | Reference upper bound | [`marginal_forecast_metrics_2024_v3.json`](file:///D:/Study/Code/Python/Aelous/artifacts/post_holdout_v3/marginal_forecast_metrics_2024_v3.json) |

---

## 3. Forensic Clarifications & Hardened Boundaries

### 3.1. P4 Metric Lineage & Closed-Form Analytical CRPS (Phases R33, P10-A, P11-R)
- P4 Student-T parameters $(\mu, \sigma, \nu)$ are estimated conditional on the 11 tabular arrival features (canonical V1 predictor set; 10 features under V2 ablation which drops calendar_year).
- P11-R verified that CRPS is computed via the exact closed-form analytical expression for Student-T (Jordan, Krüger, Lerch 2019):
  $$\text{CRPS}(F_{\nu,\mu,\sigma}, y) = \sigma \left[ \frac{y-\mu}{\sigma} \left( 2 F_\nu\left(\frac{y-\mu}{\sigma}\right) - 1 \right) + 2 f_\nu\left(\frac{y-\mu}{\sigma}\right) \frac{\nu + \left(\frac{y-\mu}{\sigma}\right)^2}{\nu - 1} - \frac{2 \sqrt{\nu}}{\nu - 1} \frac{\Gamma(\nu - \frac{1}{2}) \Gamma(\frac{1}{2})}{\Gamma(\nu) \sqrt{\pi}} \dots \right]$$
- Continuous NLL is $4.62$; mean degrees of freedom $\nu = 2.52 \in [2.10, 2.78]$, confirming substantial heavy-tailed behavior.
- Empirical calibration of P4 is disclaimed: `P4_CALIBRATION = NOT_SEPARATELY_CERTIFIED` (80% coverage = 76.12%, 90% coverage = 84.54%).

### 3.2. P5 Quantile Architecture & Forecast-Only Boundary (Phases R34, R39, P10-A, P14)
- P5 outputs 9 marginal quantiles: $\tau \in \{0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90\}$.
- The metric $16.77$ min is classified as `CRPS_QUANTILE_APPROXIMATION` (trapezoidal integration of pinball losses). Mean pinball loss is $6.82$ min.
- P5 disclaims continuous density, continuous NLL, continuous PIT calibration, and generative Monte Carlo sampling (`NOT_AVAILABLE`).
- Under R39 and P10-A, P5 is strictly Role B (forecast-only), disclaimed from continuous downstream simulation, and requires zero reconstruction or retraining.

### 3.3. Downstream Solver Fairness & Operational Boundary (Phases R35, P10-A, P10-B, P11-R)
- **`WALL_CLOCK_EQUALITY = PROVEN`**: Solvers operate under an identical $T = 2.0$ second wall-clock budget ceiling.
- **`COMPUTATIONAL_WORK_EQUALITY = NOT_PROVEN`**: Algorithmic workload varies intrinsically (Greedy: $1.1$ ms single-pass; CP-SAT: $0.44$ s branch-and-bound; SA: $2.00$ s stochastic local search).
- **CP-SAT Optimality**: Proved global optimality on 100% of audited instances ($28/28$).
- **P4 Downstream Simulation Parity**: Native Student-T draws through Simulated Annealing eliminate gate conflicts under 500 shocks (Summer peak 100% feasibility vs 27.6% schedule-only).
- **Operational Boundary**: Evaluated exclusively on synthetic operational research instances; zero claim is made for real-world airport operations.

### 3.4. Test Suite Reconciliation (Phases P12, P12.1, P12-R1)
- The test harness is reconciled into:
  - **Full active test suite**: 1,216 active tests (100% PASS across 161 test files).
  - **Narrow forensic certification gate**: 75 tests across 5 files (`tests/test_r24_final_certification.py`, `tests/test_r27_certification_hardening.py`, `tests/test_r31_final_certification.py`, `tests/test_r37_final_certification.py`, `tests/test_phase10_system_freeze.py`).
  - **Downstream regression suite**: 21 tests across 3 files (`tests/downstream/test_p11r_post_holdout.py`, `tests/downstream/test_week10_robustness_freeze.py`, `tests/downstream/test_native_p4_downstream.py`).
  - **Active protocol & holdout guard suite**: 51 tests across 7 files.
  - **Quarantined legacy freeze guards**: 4 tests safely excluded via `pytest.ini` (`retired_guard_scope_manifest.json`), preserving historical auditability with zero production callers.

---

## 4. Query Rules & Fail-Closed Protocols

- **Programmatic Catalog Access**: Scripts must query [`get_model_spec(model_id)`](file:///D:/Study/Code/Python/Aelous/src/models/registry.py) rather than inferring status from file paths or names.
- **Fail-Closed Downstream Guard**: `is_downstream_eligible(model_id)` returns `False` for unknown models, auxiliary departure models, and unpromoted research candidates.
- **Epistemological Guard**: Universal bit-for-bit reproducibility claims are forbidden; reproducibility is officially classified as `CONTAINED_SPECIFICATION_REPRODUCIBILITY` under Python 3.11.15 Windows AMD64.
- **Scientific Certification**: Officially certified as `CERTIFIED_WITH_LIMITATIONS` with `REBUILD_REQUIRED = NO` across all 13 claims and 8 rebuild criteria in [`FINAL_SCIENTIFIC_CERTIFICATION_REPORT.md`](file:///D:/Study/Code/Python/Aelous/FINAL_SCIENTIFIC_CERTIFICATION_REPORT.md).
