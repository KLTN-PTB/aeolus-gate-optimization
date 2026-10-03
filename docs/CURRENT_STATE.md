# Aeolus Gate Optimization — Current Architecture & State Registry

**Document Version**: 3.0.0  
**Generated At**: 2026-10-03T10:15:00Z  
**Architecture Protocol**: `AEOLUS_V4_SYNCHRONIZED_PROTOCOL`  
**System Lifecycle State**: `FINAL_FORENSICALLY_CERTIFIED_WITH_LIMITATIONS` (Phase R37 V5)  
**Machine-Readable Companion**: [`configs/current_state.yaml`](file:///D:/Study/Code/Python/Aelous/configs/current_state.yaml)  
**Authoritative Model Catalog**: [`configs/model_catalog_v2.yaml`](file:///D:/Study/Code/Python/Aelous/configs/model_catalog_v2.yaml)  
**Authoritative Model Registry Code**: [`src/models/registry.py`](file:///D:/Study/Code/Python/Aelous/src/models/registry.py)  
**Final Certification Manifest**: [`artifacts/audit/final_evidence_certification_v5.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/final_evidence_certification_v5.json)  

---

## 1. Executive Summary & Core Invariants

1. **Two Separate Operational Tasks**:
   - **Core Arrival** (`DEST = 'ATL'`): Inbound flight delay prediction at decision cutoff $t_{\text{cutoff}} = \text{CRS\_DEP\_TIME} - 2\text{ hours}$. Feeds the downstream gate simulation and optimization pipeline. Strictly **NO Weather** features and **NO Flight Chain** features.
   - **Auxiliary Departure** (`ORIGIN = 'ATL'`): Secondary research benchmark for departure delay classification $1[\text{DEP\_DELAY} \ge 15\text{ min}]$. Strictly **forbidden from feeding the downstream gate optimizer**.
2. **Target Semantics**:
   - Classification: $y_{\text{arr\_cls}} = 1[\text{ARR\_DELAY} \ge 15\text{ min}]$.
   - Regression: $y_{\text{arr\_reg}} = \text{ARR\_DELAY}$ in signed minutes (no absolute value, no clipping, no target imputation).
3. **Decoupled Operational Capabilities (No Single Champion)**:
   - In accordance with Phase R36 and R37 findings, models are selected for decoupled operational roles based on distinct mathematical capabilities:
     - **Point Prediction Co-Champions (Dev 2023)**: Ridge regression (`arrival_linear_baseline_v1`) and 50/50 Weighted Ensemble (`arrival_weighted_ensemble_v1`) tie within the $0.10$ min indifference band ($|\Delta| = 0.00045$ min). On 2024 holdout, Ridge achieved MAE $22.9125$ min vs. Ensemble $23.3175$ min ($|\Delta| = 0.405$ min, not tied).
     - **Probabilistic Forecasting Champion**: P5 Quantile Regression (`P5_quantile_regression`) achieves champion CRPS quantile approximation ($16.85$ min dev, $16.77$ min holdout) and pinball loss ($6.88$ min dev, $6.82$ min holdout) across 9 pre-registered quantiles.
     - **Continuous Downstream Simulation Champion**: P4 NGBoost Student-T (`P4_ngboost_student_t`) provides a 3-parameter parametric continuous density, exact continuous CRPS ($17.6532$ min holdout), and exact continuous NLL ($4.6307$), uniquely enabling continuous Monte Carlo flight delay sampling.
4. **Temporal Discipline & Evaluated 2024 Post-Holdout**:
   - 2016–2022: Expanding-window rolling folds (Folds 1–4) for development and HPO.
   - 2023: Controlled development dataset reserved for model selection and benchmark comparison; blocked from HPO.
   - 2024: Formally evaluated post-freeze in Phase R23 and re-audited in Phases R28, R31, R33, R36, and R37. The repository is in `FINAL_FORENSICALLY_CERTIFIED_WITH_LIMITATIONS` state. Retraining or tuning using 2024 is strictly prohibited.
5. **Downstream Gate Optimization Admissibility**:
   - Only certified Core Arrival models with `downstream_eligible = True` can supply delay forecasts to gate solvers. Auxiliary Departure models are rejected fail-closed.

---

## 2. Authoritative Model Catalog & Certified Roles

| Model ID | Family | Task | Category | Certified Role | Downstream Eligible | Authoritative Holdout Metric (2024) | Source Manifest |
| :--- | :--- | :--- | :--- | :--- | :---: | :--- | :--- |
| **`arrival_linear_baseline_v1`** | `linear` | Core Arrival | `CORE_POINT` | Point Reference / Co-Champion | **Yes** | MAE: **22.9125 min** | [`marginal_forecast_metrics_2024_v3.json`](file:///D:/Study/Code/Python/Aelous/artifacts/post_holdout_v3/marginal_forecast_metrics_2024_v3.json) |
| **`arrival_xgboost_baseline_v1`** | `xgboost` | Core Arrival | `CORE_POINT` | Point Benchmark | **Yes** | MAE: **24.3643 min** | [`marginal_forecast_metrics_2024_v3.json`](file:///D:/Study/Code/Python/Aelous/artifacts/post_holdout_v3/marginal_forecast_metrics_2024_v3.json) |
| **`arrival_weighted_ensemble_v1`** | `weighted_ensemble` | Core Arrival | `CORE_POINT` | Point Co-Champion (Dev) | **Yes** | MAE: **23.3175 min** | [`marginal_forecast_metrics_2024_v3.json`](file:///D:/Study/Code/Python/Aelous/artifacts/post_holdout_v3/marginal_forecast_metrics_2024_v3.json) |
| **`P5_quantile_regression`** | `quantile_regression` | Core Arrival | `PROBABILISTIC_CANDIDATE` | Probabilistic Quantile Champion | **No** (Scalar median only) | Approx CRPS: **16.7724 min** \| Pinball: **6.8211 min** | [`r34_p5_capability_forensics.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r34_p5_capability_forensics.json) |
| **`P4_ngboost_student_t`** | `ngboost_student_t` | Core Arrival | `PROBABILISTIC_CANDIDATE` | Continuous Simulation Champion | **Yes** (Generative draws) | Exact CRPS: **17.6532 min** \| NLL: **4.6307** | [`r33_p4_metric_lineage.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r33_p4_metric_lineage.json) |
| **`oracle_actual`** | `oracle` | Reference | `THEORETICAL_BOUND` | Non-Deployable Upper Bound | **No** | MAE: **0.0000 min** \| CRPS: **0.0000 min** | [`marginal_forecast_metrics_2024_v3.json`](file:///D:/Study/Code/Python/Aelous/artifacts/post_holdout_v3/marginal_forecast_metrics_2024_v3.json) |

---

## 3. Forensic Clarifications & Hardened Boundaries

### 3.1. P4 Metric Lineage (Resolved in Phase R33)
- The authoritative holdout metrics for P4 on 2024 data are **$\text{CRPS} = 17.6532$ min** and **$\text{NLL} = 4.6307$** (backed by raw physical artifact `marginal_forecast_metrics_2024_v3.json`).
- The narrative reporting figures $17.15$ / $4.032$ appearing in R32 text were forensically proven to be an isolated typographical transcription defect and are deleted from all active manifests.
- Empirical calibration of P4 is disclaimed: `P4_CALIBRATION = NOT_SEPARATELY_CERTIFIED`.

### 3.2. P5 Quantile Architecture & Metric Taxonomy (Resolved in Phase R34)
- P5 is strictly a **9-quantile estimator**:
  $$\alpha \in \{0.025, 0.050, 0.100, 0.250, 0.500, 0.750, 0.900, 0.950, 0.975\}$$
- The metric $16.85$ min (dev) / $16.77$ min (holdout) is mathematically classified as **`CRPS_QUANTILE_APPROXIMATION`** (evaluated via trapezoidal integration of pinball losses across the 9 quantiles).
- Mean pinball loss is a distinct metric of magnitude **$6.88$ min** (dev) / **$6.82$ min** (holdout). Conflating the two is prohibited.
- P5 disclaims continuous density, continuous NLL, continuous PIT calibration, and generative Monte Carlo sampling (`NOT_AVAILABLE`).

### 3.3. Downstream Solver Fairness Semantics (Resolved in Phase R35)
- **`WALL_CLOCK_EQUALITY = PROVEN`**: All 4 solvers operate under a uniform configured ceiling of $T_{\text{total}} = 2.0$ seconds.
- **`COMPUTATIONAL_WORK_EQUALITY = NOT_PROVEN`**: Algorithms execute fundamentally different workloads (Greedy: $1.1$ ms single-pass; CP-SAT: $0.44$ s branch-and-bound; SA: $2.00$ s stochastic local search).
- **CP-SAT Optimality**: Proved global optimality on 100% of audited instances ($28/28$), explaining why warm-starting SA yields zero marginal gain ($\Delta_i = 0.0000$).
- **Benchmark Scope Separation**: R26 evaluates 28 instances ($112$ runs) on 2024 seasonal post-holdout scenarios; R21 evaluated 28 instances ($84$ runs) on 2023 development scenarios. They are separate benchmarks.

---

## 4. Query Rules & Fail-Closed Protocols

- **Programmatic Catalog Access**: Scripts must query [`get_model_spec(model_id)`](file:///D:/Study/Code/Python/Aelous/src/models/registry.py) rather than inferring status from file paths or names.
- **Fail-Closed Downstream Guard**: `is_downstream_eligible(model_id)` returns `False` for unknown models, auxiliary departure models, and unpromoted research candidates.
- **Epistemological Guard**: Universal bit-for-bit reproducibility claims are forbidden; reproducibility is officially classified as `CONTAINED_SPECIFICATION_REPRODUCIBILITY` under Python 3.11.15 Windows AMD64.
