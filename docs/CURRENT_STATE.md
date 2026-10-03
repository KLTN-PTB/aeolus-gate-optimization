# Aeolus Gate Optimization — Current Architecture & State Registry

**Document Version**: 2.0.0  
**Generated At**: 2026-10-02T01:30:00+07:00  
**Architecture Protocol**: `AEOLUS_V4_SYNCHRONIZED_PROTOCOL`  
**System Lifecycle State**: `POST_HOLDOUT_STABILIZED` & `FAIL_CLOSED_CERTIFIED`  
**Machine-Readable Companion**: [`configs/current_state.yaml`](file:///D:/Study/Code/Python/Aelous/configs/current_state.yaml)  
**Authoritative Model Catalog**: [`configs/model_catalog_v2.yaml`](file:///D:/Study/Code/Python/Aelous/configs/model_catalog_v2.yaml)  
**Authoritative Model Registry Code**: [`src/models/registry.py`](file:///D:/Study/Code/Python/Aelous/src/models/registry.py)  
**Model Registry Manifest**: [`artifacts/manifests/model_registry_manifest_v2.json`](file:///D:/Study/Code/Python/Aelous/artifacts/manifests/model_registry_manifest_v2.json)  

---

## 1. Executive Summary & Core Invariants

1. **Two Separate Operational Tasks**:
   - **Core Arrival** (`DEST=ATL`): Inbound flight delay prediction at cutoff `CRS_DEP_TIME - 2h`. Feeds the downstream gate optimization pipeline. Strictly **NO Weather** features and **NO Flight Chain** features.
   - **Auxiliary Departure** (`ORIGIN=ATL`): Secondary research task for departure delay classification `1[DEP_DELAY >= 15]`. Strictly **forbidden from feeding the downstream gate optimizer**.
2. **Target Semantics**:
   - Classification: `y_arr_cls = 1[ARR_DELAY >= 15]`.
   - Regression: `y_arr_reg = ARR_DELAY` in signed minutes (no absolute value, no clipping, no target imputation).
3. **Core Method Cap = 5**:
   - The authoritative V4 Core Point methodology is capped at exactly 5 canonical method families:
     1. `arrival_linear_baseline_v1` (Linear / Ridge regression, Logistic classification)
     2. `arrival_random_forest_baseline_v1` (Random Forest default baseline)
     3. `arrival_hist_gradient_boosting_baseline_v1` (HistGradientBoosting default baseline)
     4. `arrival_xgboost_baseline_v1` (XGBoost default baseline)
     5. `arrival_weighted_ensemble_v1` (Inverse-MAE / inverse-variance weighted ensemble)
   - Week 5 Optuna HPO models (`*_tuned_v1_1`) are **tuned parameterization variants** of their respective base families, not distinct core method families.
4. **Temporal Discipline & 2024 Post-Holdout Integrity**:
   - 2016–2022: Expanding-window rolling folds (Folds 1–4) for development and HPO.
   - 2023: Controlled development dataset reserved for model selection and benchmark comparison; blocked from HPO.
   - 2024: Historically evaluated in Stage 11 post-freeze. The repository is in `POST_HOLDOUT_STABILIZED` state. 2024 is **not an untouched holdout**; refitting, re-tuning, or re-selecting models using 2024 is strictly prohibited.
5. **Downstream Gate Optimization Admissibility**:
   - Only certified Core Arrival models with `downstream_eligible = True` can supply delay forecasts to gate solvers. Auxiliary Departure models are rejected fail-closed.

---

## 2. Model Catalog & Registry Architecture

Models in the repository are strictly classified into clear architectural categories to eliminate ambiguity between active production models, research candidates, and historical legacy comparators:

### 2.1. Core Point Models (5 Canonical Families — Cap = 5)

| Model ID | Family | Task | Category | Status | Downstream Eligible | Rationale & Evidence |
|---|---|---|---|---|:---:|---|
| `arrival_linear_baseline_v1` | `linear` | Core Arrival | `CORE_POINT` | `current_core` | **Yes** | Week 4 linear reference baseline (Ridge / Logistic). |
| `arrival_random_forest_baseline_v1` | `random_forest` | Core Arrival | `CORE_POINT` | `current_core` | **Yes** | Week 4 default Random Forest baseline. |
| `arrival_hist_gradient_boosting_baseline_v1` | `hist_gradient_boosting` | Core Arrival | `CORE_POINT` | `current_core` | **Yes** | Week 4 HistGradientBoosting baseline. |
| `arrival_xgboost_baseline_v1` | `xgboost` | Core Arrival | `CORE_POINT` | `current_core` | **Yes** | Week 5 XGBoost baseline. |
| `arrival_weighted_ensemble_v1` | `weighted_ensemble` | Core Arrival | `CORE_POINT` | `current_core` | **Yes** | Core Method #5; inverse-MAE weighted ensemble across base methods. |

### 2.2. Tuned Variants (Under Base Core Families)

| Model ID | Family | Variant Of | Category | Status | Downstream Eligible | Rationale & Evidence |
|---|---|---|---|---|:---:|---|
| `arrival_random_forest_tuned_v1_1` | `random_forest` | `arrival_random_forest_baseline_v1` | `TUNED_VARIANT` | `current_core` | **Yes** | Week 5 Optuna HPO tuned across 4 rolling folds (10 trials). |
| `arrival_hist_gradient_boosting_tuned_v1_1` | `hist_gradient_boosting` | `arrival_hist_gradient_boosting_baseline_v1` | `TUNED_VARIANT` | `current_core` | **Yes** | Week 5 Optuna HPO tuned across 4 rolling folds (10 trials). |
| `arrival_xgboost_tuned_v1_1` | `xgboost` | `arrival_xgboost_baseline_v1` | `TUNED_VARIANT` | `current_core` | **Yes** | Week 5 Optuna HPO tuned across 4 rolling folds (Top mean PR-AUC = 0.1956). |

### 2.3. Probabilistic Research Candidates (Academic Benchmark Pool)

| Model ID | Family | Task | Category | Status | Downstream Eligible | Rationale & Evidence |
|---|---|---|---|---|:---:|---|
| `P1_empirical` | `empirical_carrier_hour` | Core Arrival | `PROBABILISTIC_CANDIDATE` | `research_candidate` | **No** | Empirical carrier x scheduled-hour baseline with hierarchical backoff. |
| `P2_xgb_gaussian_oof` | `xgb_gaussian_oof` | Core Arrival | `PROBABILISTIC_CANDIDATE` | `research_candidate` | **No** | XGBoost mean + OOF residual uncertainty (Fixed-sigma Gaussian). |
| `P3_ngboost_normal` | `ngboost_normal` | Core Arrival | `PROBABILISTIC_CANDIDATE` | `research_candidate` | **No** | NGBoost Normal with heteroscedastic location and scale. |
| `P4_ngboost_student_t` | `ngboost_student_t` | Core Arrival | `PROBABILISTIC_CANDIDATE` | `research_candidate` | **No** | NGBoost Student-T heteroscedastic heavy-tail research candidate. |
| `P5_quantile_regression` | `quantile_regression` | Core Arrival | `PROBABILISTIC_CANDIDATE` | `research_candidate` | **No** | Quantile regression comparator via multi-pinball loss LightGBM. |

### 2.4. Legacy Frozen Comparator

| Model ID | Family | System Identity | Category | Status | Downstream Eligible | Rationale & Evidence |
|---|---|---|---|---|:---:|---|
| `b5_ngboost_student_t` | `ngboost` | `SYS_B5_ngboost_student_t__DEP_D2_gaussian_copula` | `LEGACY_FROZEN` | `legacy_frozen` | **Yes** | Historical frozen Stage 10 checkpoint evaluated on 2024; historical comparator. |

### 2.5. Auxiliary Departure Task & Research Ablation

| Model ID | Family | Task | Category | Status | Downstream Eligible | Rationale & Evidence |
|---|---|---|---|---|:---:|---|
| `departure_auxiliary_baseline_v1` | `linear` | Auxiliary Departure | `AUXILIARY_DEPARTURE` | `research_candidate` | **No** | Outbound ORIGIN=ATL departure classification; strictly isolated from gate optimization. |
| `arrival_hurdle_predictor_two_stage` | `two_stage_hurdle` | Core Arrival | `RESEARCH_CANDIDATE` | `research_candidate` | **No** | Experimental two-stage classifier + conditional regressor ablation. |

---

## 3. System Identities & Manifest Boundaries

To eliminate identity conflation across parallel tracks, systems have mutually exclusive identities:

1. **`AEOLUS_V4_CORE_ARRIVAL`**:
   - Scope: V4 Authoritative Core Arrival ML pipeline (5 Core Point methods + Week 5 Tuned variants).
   - Manifest: [`artifacts/manifests/model_registry_manifest_v2.json`](file:///D:/Study/Code/Python/Aelous/artifacts/manifests/model_registry_manifest_v2.json)
2. **`AEOLUS_LEGACY_PROBABILISTIC_B5`**:
   - Scope: Historical frozen probabilistic system `SYS_B5_ngboost_student_t__DEP_D2_gaussian_copula` from Stage 10.
   - Manifest: [`artifacts/manifests/system_freeze_manifest.json`](file:///D:/Study/Code/Python/Aelous/artifacts/manifests/system_freeze_manifest.json)
3. **`AEOLUS_PROBABILISTIC_RESEARCH`**:
   - Scope: Academic marginal probabilistic candidate pool (P1–P5).
   - Manifest: [`artifacts/manifests/academic_model_selection_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/manifests/academic_model_selection_v1.json)
4. **`AEOLUS_DOWNSTREAM_OPTIMIZATION`**:
   - Scope: Downstream gate assignment engine (Greedy, CP-SAT, Simulated Annealing).
   - Admissibility: Only Core Arrival models passing `is_downstream_eligible(model_id)`.

---

## 4. Query Rules & Fail-Closed Protocols

- **No Filename Heuristics**: Scripts must query [`get_model_spec(model_id)`](file:///D:/Study/Code/Python/Aelous/src/models/registry.py) rather than inferring status from file paths or names.
- **Fail-Closed Downstream Guard**: `is_downstream_eligible(model_id)` returns `False` for unknown models, auxiliary departure models, and unpromoted research candidates.
- **Scientific Validation Disclaimer**: Presence in the catalog reflects engineering provenance and architectural registration; it does not constitute an unreserved claim that all research candidates are scientifically optimal.
