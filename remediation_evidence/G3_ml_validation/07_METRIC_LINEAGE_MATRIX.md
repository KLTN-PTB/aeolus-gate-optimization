# AEOLUS-G3 — DELIVERABLE 07: METRIC LINEAGE MATRIX

## 1. Authoritative Lineage Classification Taxonomy

Each reported metric across Phase P08 and Gate G3 is classified under one of four rigorous scientific statuses:
- **`RECOMPUTED_VERIFIED`:** Metric has been independently recomputed row-by-row from existing prediction-level parquets and validated within mathematical rounding tolerance ($< 10^{-4}$).
- **`HISTORICAL_REPORTED`:** Metric originates from an earlier documented training run whose raw prediction-level parquets are archived separately or whose aggregate summary manifest exists, but was hardcoded in intermediate validation scripts.
- **`HEURISTIC_DERIVED`:** Metric was computed using an ad-hoc heuristic transformation (e.g. sigmoid transformation on regression continuous predictions) rather than an actual trained probabilistic model.
- **`NOT_REPRODUCIBLE`:** Metric lacks raw data, prediction parquets, configuration manifests, or mathematical formulas.

---

## 2. Complete Metric Lineage Matrix

### 2.1 Arrival Classification Metrics

| Model ID | Task / Target | Split | N Rows | $y_{true}$ Source | Prediction Source | Metric Formula | Generation Script | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `arrival_linear_baseline_v1` | P(ARR_DELAY $\ge$ 15) | OOF 4-Fold Macro | 16,000 | `oof/arrival_linear_...parquet` | `pred_cls_prob` | ROC-AUC, PR-AUC, Brier | `scripts/generate_p08_validation_artifacts.py` | **`RECOMPUTED_VERIFIED`** |
| `arrival_random_forest_baseline_v1` | P(ARR_DELAY $\ge$ 15) | OOF 4-Fold Macro | 16,000 | `oof/arrival_random_forest_...parquet` | `pred_cls_prob` | ROC-AUC, PR-AUC, Brier | `scripts/generate_p08_validation_artifacts.py` | **`RECOMPUTED_VERIFIED`** |
| `arrival_hist_gradient_boosting_baseline_v1` | P(ARR_DELAY $\ge$ 15) | OOF 4-Fold Macro | 16,000 | `oof/arrival_hist_...parquet` | `pred_cls_prob` | ROC-AUC, PR-AUC, Brier | `scripts/generate_p08_validation_artifacts.py` | **`RECOMPUTED_VERIFIED`** |
| `arrival_xgboost_baseline_v1` | P(ARR_DELAY $\ge$ 15) | OOF 4-Fold Macro | 16,000 | `oof/arrival_xgboost_...parquet` | `pred_cls_prob` | ROC-AUC, PR-AUC, Brier | `scripts/generate_p08_validation_artifacts.py` | **`RECOMPUTED_VERIFIED`** |
| `arrival_weighted_ensemble_v1` | P(ARR_DELAY $\ge$ 15) | OOF 4-Fold Macro | 16,000 | `oof/arrival_weighted_...parquet` | `pred_cls_prob` | ROC-AUC, PR-AUC, Brier | `scripts/generate_p08_validation_artifacts.py` | **`RECOMPUTED_VERIFIED`** |
| `arrival_xgboost_tuned_v1_1` | P(ARR_DELAY $\ge$ 15) | OOF 4-Fold Macro | 16,000 | `artifacts/predictions/arrival_xgboost_tuned...` | Hardcoded in P08 script | ROC-AUC, PR-AUC, Brier | `scripts/generate_p08_validation_artifacts.py` | **`HISTORICAL_REPORTED`** |

### 2.2 Arrival Regression Metrics

| Model ID | Task / Target | Split | N Rows | $y_{true}$ Source | Prediction Source | Metric Formula | Generation Script | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `baseline_zero` | ARR_DELAY (min) | OOF 4-Fold Macro | 16,000 | `oof/*.parquet` | Constant $0.0$ | MAE, RMSE, Tail MAE | `scripts/generate_p08_validation_artifacts.py` | **`RECOMPUTED_VERIFIED`** |
| `baseline_median` | ARR_DELAY (min) | OOF 4-Fold Macro | 16,000 | `oof/*.parquet` | Constant median ($-8.0$) | MAE, RMSE, Tail MAE | `scripts/generate_p08_validation_artifacts.py` | **`RECOMPUTED_VERIFIED`** |
| `arrival_linear_baseline_v1` | ARR_DELAY (min) | OOF 4-Fold Macro | 16,000 | `oof/*.parquet` | `pred_reg` | MAE, RMSE, Tail MAE | `scripts/generate_p08_validation_artifacts.py` | **`RECOMPUTED_VERIFIED`** |
| `arrival_random_forest_baseline_v1` | ARR_DELAY (min) | OOF 4-Fold Macro | 16,000 | `oof/*.parquet` | `pred_reg` | MAE, RMSE, Tail MAE | `scripts/generate_p08_validation_artifacts.py` | **`RECOMPUTED_VERIFIED`** |
| `arrival_hist_gradient_boosting_baseline_v1` | ARR_DELAY (min) | OOF 4-Fold Macro | 16,000 | `oof/*.parquet` | `pred_reg` | MAE, RMSE, Tail MAE | `scripts/generate_p08_validation_artifacts.py` | **`RECOMPUTED_VERIFIED`** |
| `arrival_xgboost_baseline_v1` | ARR_DELAY (min) | OOF 4-Fold Macro | 16,000 | `oof/*.parquet` | `pred_reg` | MAE, RMSE, Tail MAE | `scripts/generate_p08_validation_artifacts.py` | **`RECOMPUTED_VERIFIED`** |
| `arrival_weighted_ensemble_v1` | ARR_DELAY (min) | OOF 4-Fold Macro | 16,000 | `oof/*.parquet` | `pred_reg` | MAE, RMSE, Tail MAE | `scripts/generate_p08_validation_artifacts.py` | **`RECOMPUTED_VERIFIED`** |

### 2.3 Departure Classification & Outbound Probability Metrics

| Model ID | Task / Target | Split | N Rows | $y_{true}$ Source | Prediction Source | Metric Formula | Generation Script | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `departure_ridge_heuristic_p08` | P(DEP_DELAY $\ge$ 15) | Selection 2023 | 332,734 | `departure_point_selection_2023_v1.parquet` | $\text{sigmoid}((\text{pred}-15)/10)$ | ROC-AUC, PR-AUC, Brier | `scripts/generate_p08_validation_artifacts.py` | **`HEURISTIC_DERIVED`** |
| `departure_xgboost_heuristic_p08`| P(DEP_DELAY $\ge$ 15) | Selection 2023 | 332,734 | `departure_point_selection_2023_v1.parquet` | $\text{sigmoid}((\text{pred}-15)/10)$ | ROC-AUC, PR-AUC, Brier | `scripts/generate_p08_validation_artifacts.py` | **`HEURISTIC_DERIVED`** |
| `constant_prevalence_baseline` | P(DEP_DELAY $\ge$ 15) | Selection 2023 | 332,734 | `outbound_classification_selection_2023.parquet`| Constant prevalence ($0.1426$) | Brier, ECE, LogLoss | `scripts/train_outbound_classifiers_g3.py` | **`RECOMPUTED_VERIFIED`** |
| `outbound_logistic_calibrated_v1`| P(DEP_DELAY $\ge$ 15) | Selection 2023 | 332,734 | `outbound_classification_selection_2023.parquet`| Isotonic calibrated LR | ROC, PR-AUC, Brier, ECE | `scripts/train_outbound_classifiers_g3.py` | **`RECOMPUTED_VERIFIED`** |
| `outbound_xgboost_calibrated_v1` | P(DEP_DELAY $\ge$ 15) | Selection 2023 | 332,734 | `outbound_classification_selection_2023.parquet`| Platt calibrated XGB | ROC, PR-AUC, Brier, ECE | `scripts/train_outbound_classifiers_g3.py` | **`RECOMPUTED_VERIFIED`** |

### 2.4 Departure Regression Metrics

| Model ID | Task / Target | Split | N Rows | $y_{true}$ Source | Prediction Source | Metric Formula | Generation Script | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `baseline_zero` | DEP_DELAY (min) | Selection 2023 | 332,734 | `departure_point_selection_2023_v1.parquet` | Constant $0.0$ | MAE, RMSE, Tail MAE | `scripts/generate_p08_validation_artifacts.py` | **`RECOMPUTED_VERIFIED`** |
| `baseline_median` | DEP_DELAY (min) | Selection 2023 | 332,734 | `departure_point_selection_2023_v1.parquet` | Constant median ($-1.0$) | MAE, RMSE, Tail MAE | `scripts/generate_p08_validation_artifacts.py` | **`RECOMPUTED_VERIFIED`** |
| `departure_ridge_baseline_v1` | DEP_DELAY (min) | Selection 2023 | 332,734 | `departure_point_selection_2023_v1.parquet` | `pred_ridge` | MAE, RMSE, Tail MAE | `scripts/generate_p08_validation_artifacts.py` | **`RECOMPUTED_VERIFIED`** |
| `departure_xgboost_baseline_v1`| DEP_DELAY (min) | Selection 2023 | 332,734 | `departure_point_selection_2023_v1.parquet` | `pred_xgboost` | MAE, RMSE, Tail MAE | `scripts/generate_p08_validation_artifacts.py` | **`RECOMPUTED_VERIFIED`** |

### 2.5 Probabilistic Modeling Metrics (P1–P5)

| Candidate ID | Task / Target | Split | N Rows | Raw Data Parquet | Native Checkpoint | Metric Formula | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `P1_empirical` | Arrival Distribution | 4-Fold Macro | 20,000 | `artifacts/probabilistic/empirical/` | NO | CRPS, Cov-80, Cov-90 | **`HISTORICAL_REPORTED`** |
| `P2_xgb_gaussian_oof` | Gaussian Residual | 4-Fold Macro | 20,000 | `artifacts/probabilistic/xgb_gaussian/` | NO | CRPS, Cov-80, Cov-90 | **`RECOMPUTED_VERIFIED`** |
| `P3_ngboost_normal` | Normal NGBoost | 4-Fold Macro | 20,000 | `artifacts/probabilistic/ngboost/` | NO | CRPS, Cov-80, Cov-90 | **`RECOMPUTED_VERIFIED`** |
| `P4_ngboost_student_t` | Student-t NGBoost | 4-Fold Macro | 20,000 | `artifacts/probabilistic/ngboost_student_t/`| **YES** (`model_weights_frozen_v1.joblib`)| CRPS, Cov-80, Cov-90 | **`RECOMPUTED_VERIFIED`** |
| `P5_quantile_regression`| LightGBM Quantiles | 4-Fold Macro | 20,000 | `artifacts/probabilistic/lightgbm_quantile/`| NO (Predictions only) | CRPS, Cov-80, Cov-90 | **`RECOMPUTED_VERIFIED`** |

### 2.6 Feature Ablation & SHAP

| Artifact / ID | Scope / Description | Source Parquet | Checkpoint Source | Status |
| :--- | :--- | :--- | :--- | :--- |
| `A_tabular_only` | Schedule + Calendar + Route (10 feats) | `data/processed/outbound_atl/` | `departure_xgboost_baseline_v1.joblib` | **`VALID_CAUSAL_ABLATION`** |
| `B_tabular_plus_chain` | Tabular + Reconstructed Flight Chain | Hardcoded in P08 script | None | **`HISTORICAL_EXPLORATORY_ABLATION`** |
| `C_tabular_plus_chain_plus_weather` | Tabular + Chain + METAR Weather | Hardcoded in P08 script | None | **`HISTORICAL_EXPLORATORY_ABLATION`** |
| `SHAP Global Importance` | TreeSHAP on 1,000 Outbound ATL sample | `data/processed/tabular_by_year/year=2023/`| `departure_xgboost_baseline_v1.joblib` | **`RECOMPUTED_VERIFIED`** |
