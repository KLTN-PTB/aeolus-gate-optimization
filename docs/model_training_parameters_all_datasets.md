# Aeolus - Model Training Parameters Across All Recorded Datasets

> Generated: `2026-09-17T12:24:49.094862+00:00`
>
> This file is a parameter/provenance inventory. It does not retrain models, alter parameters, or perform model selection.

## 1. Scope and interpretation

The inventory covers every recorded Arrival Core model run: Week-4 Linear/Ridge, Random Forest, HistGradientBoosting, the Prompt-03 XGBoost baseline, Week-5 Optuna HPO trials and best configurations, and Week-5 tuned OOF refits. Auxiliary Departure/Weather models, Weighted Ensemble, SHAP, 2023 selection, and ARR/DEP ablations were not trained in the recorded scope.

## 2. Dataset and common information contract

- Dataset manifest: `artifacts/manifests/processed_data_manifest_v1.json` (SHA-256: `8e0856fea4697c8e42e79d31beb0eac85207ae5ca6c404806f38d06f852d2933`)
- Feature manifest: `artifacts/manifests/feature_manifest_arrival_v1.json` (SHA-256: `cb352a56d194e9f39ee9477fdbc5da7929ba03b5ba089100cbd88b01dec09e85`)
- Temporal fold manifest: `artifacts/manifests/temporal_folds_manifest.json` (SHA-256: `8c5bfbd400e0f0c8591ff0bdcf37759e7e4eaead00697f5e5d92c2a9fcea0f31`)
- Arrival population: inbound flights with `DEST=ATL`.
- Prediction cutoff: `CRS_DEP_TIME - 2 hours`.
- Classification target: `y_arr_cls = 1[ARR_DELAY >= 15]`.
- Regression target: signed `ARR_DELAY` minutes (`y_arr_reg`).
- Approved feature families: Schedule, Calendar, Carrier, Route.
- Final approved predictor columns (11): `CRS_ELAPSED_TIME`, `calendar_year`, `calendar_month`, `calendar_day_of_month`, `calendar_day_of_week`, `is_weekend`, `scheduled_departure_hour`, `scheduled_departure_minute`, `OP_CARRIER`, `ORIGIN`, `OP_CARRIER_FL_NUM`.
- Preprocessing fit boundary: each fold's training rows only.
- Excluded predictors: Weather, DEP_DELAY, predicted Departure, actual operational outcomes, Chain, identifiers as predictors.

### Dataset partitions and roles

| Year | Role | Source rows | Inbound ATL rows | Outbound ATL rows |
|---:|---|---:|---:|---:|
| 2016 | DEVELOPMENT | 5,537,987 | 381,166 | 381,303 |
| 2017 | DEVELOPMENT | 5,575,872 | 358,263 | 358,537 |
| 2018 | DEVELOPMENT | 6,986,842 | 386,580 | 386,460 |
| 2019 | DEVELOPMENT | 7,161,827 | 391,075 | 391,053 |
| 2020 | DEVELOPMENT | 4,312,091 | 242,121 | 242,207 |
| 2021 | DEVELOPMENT | 5,755,666 | 309,621 | 309,488 |
| 2022 | DEVELOPMENT | 6,413,416 | 311,701 | 311,746 |
| 2023 | DEVELOPMENT | 6,645,461 | 332,741 | 332,734 |
| 2024 | FINAL_HOLDOUT | 6,284,841 | 309,165 | 309,142 |

### Locked folds

| Fold | Training years | Validation year |
|---|---|---:|
| fold_1 | 2016, 2017, 2018 | 2019 |
| fold_2 | 2016, 2017, 2018, 2019 | 2020 |
| fold_3 | 2016, 2017, 2018, 2019, 2020 | 2021 |
| fold_4 | 2016, 2017, 2018, 2019, 2020, 2021 | 2022 |

## 3. Model inventory

| Model/run | Dataset scope | Classifier | Regressor | Status |
|---|---|---|---|---|
| Linear / Ridge Week 4 | Arrival Core, rolling OOF 2016-2022 | LogisticRegression | Ridge | PASS / preserved |
| Random Forest Week 4 baseline | Arrival Core, rolling OOF 2016-2022 | RandomForestClassifier | RandomForestRegressor | PASS / preserved |
| HistGradientBoosting Week 4 baseline | Arrival Core, rolling OOF 2016-2022 | HistGradientBoostingClassifier | HistGradientBoostingRegressor | PASS / preserved |
| XGBoost Prompt-03 baseline | Arrival Core, rolling OOF 2016-2022 | XGBClassifier | XGBRegressor | PASS / preserved |
| Random Forest Week 5 tuned | Arrival Core, four locked folds | RandomForestClassifier | RandomForestRegressor | PASS |
| HistGradientBoosting Week 5 tuned | Arrival Core, four locked folds | HistGradientBoostingClassifier | HistGradientBoostingRegressor | PASS |
| XGBoost Week 5 tuned | Arrival Core, four locked folds | XGBClassifier | XGBRegressor | PASS |

## 4. Week-4 baseline configurations

The following blocks are complete YAML configurations, including estimator, regularization, sampling, resource, threshold, and HPO-policy fields.

### Linear / Ridge (Week 4)

Source: `configs/week4_linear_baseline.yaml` (SHA-256: `d61657d2155e832f5806738eb1ac6da6f6ab906d0ef63b45ba8fe01c81b8faf1`)

```yaml
baseline_version: arrival_linear_baseline_v1
experiment_contract_version: arrival_week4_experiment_v1
task: arrival_core
method_id: linear
feature_manifest_version: feature_manifest_arrival_v1
preprocessing_version: arrival_preprocessing_v1
classification:
  estimator: LogisticRegression
  solver: saga
  C: 1.0
  max_iter: 300
  tol: 0.001
  fit_intercept: true
  class_weight_policy: balanced_from_training_fold_only
  random_state_source: configs/base.yaml:reproducibility.project_seed
regression:
  estimator: Ridge
  alpha: 1.0
  solver: lsqr
  tol: 0.001
  fit_intercept: true
threshold_policy:
  fixed_probability_threshold: 0.5
  validation_optimization_allowed: false
hpo:
  allowed: false
  rationale: Conservative fixed regularization baseline; C, alpha, and threshold are
    locked before production validation.
```

### Random Forest (Week 4)

Source: `configs/week4_random_forest_baseline.yaml` (SHA-256: `54b83e533666ff0111f1acffddb806e4f884b670029d1bfe59494fca6731c64c`)

```yaml
baseline_version: arrival_random_forest_baseline_v1
experiment_contract_version: arrival_week4_experiment_v1
task: arrival_core
method_id: random_forest
feature_manifest_version: feature_manifest_arrival_v1
preprocessing_version: arrival_preprocessing_v1
classification:
  estimator: RandomForestClassifier
  n_estimators: 96
  criterion: gini
  max_depth: 14
  min_samples_split: 40
  min_samples_leaf: 20
  max_features: sqrt
  bootstrap: true
  max_samples: null
  n_jobs: 1
  class_weight_policy: balanced_from_training_fold_only
  random_state_source: configs/base.yaml:reproducibility.project_seed
regression:
  estimator: RandomForestRegressor
  n_estimators: 96
  criterion: squared_error
  max_depth: 14
  min_samples_split: 40
  min_samples_leaf: 20
  max_features: sqrt
  bootstrap: true
  max_samples: null
  n_jobs: 1
  random_state_source: configs/base.yaml:reproducibility.project_seed
resource_policy:
  target_memory_gib: 16
  execution_parallelism: 1
  production_training_rows: full_eligible_fold_rows
  production_sampling_allowed: false
  max_samples_policy: null_means_full_bootstrap_draw_size
  rationale: 'Fixed capacity-bound baseline: shallow-enough trees, minimum leaf support,
    feature subsampling, and single-process execution cap concurrent forest memory.
    No parameter was selected from validation metrics.

    '
threshold_policy:
  fixed_probability_threshold: 0.5
  validation_optimization_allowed: false
hpo:
  allowed: false
  rationale: Fixed deterministic Week-4 baseline; RF tuning is out of scope for this
    prompt.
```

### HistGradientBoosting (Week 4)

Source: `configs/week4_hist_gradient_boosting_baseline.yaml` (SHA-256: `b63b77ddbff4c3be722bff245ec8fd0095b55e20351eb91ba385fb40e08ff258`)

```yaml
baseline_version: arrival_hist_gradient_boosting_baseline_v1
experiment_contract_version: arrival_week4_experiment_v1
task: arrival_core
method_id: hist_gradient_boosting
feature_manifest_version: feature_manifest_arrival_v1
preprocessing_version: arrival_preprocessing_v1
classification:
  estimator: HistGradientBoostingClassifier
  loss: log_loss
  learning_rate: 0.05
  max_iter: 200
  max_leaf_nodes: 31
  max_depth: 8
  min_samples_leaf: 50
  l2_regularization: 1.0
  max_features: 1.0
  max_bins: 255
  categorical_features: null
  early_stopping: false
  warm_start: false
  class_weight_policy: balanced_from_training_fold_only
  random_state_source: configs/base.yaml:reproducibility.project_seed
regression:
  estimator: HistGradientBoostingRegressor
  loss: squared_error
  learning_rate: 0.05
  max_iter: 200
  max_leaf_nodes: 31
  max_depth: 8
  min_samples_leaf: 50
  l2_regularization: 1.0
  max_features: 1.0
  max_bins: 255
  categorical_features: null
  early_stopping: false
  warm_start: false
  random_state_source: configs/base.yaml:reproducibility.project_seed
resource_policy:
  target_memory_gib: 16
  production_training_rows: full_eligible_fold_rows
  production_sampling_allowed: false
  early_stopping_policy: disabled_no_internal_validation_split
  rationale: 'Fixed capacity-bound baseline: capped boosting iterations, bounded tree
    complexity and leaf support, plus no internal validation split. No parameter was
    selected from production validation metrics.

    '
threshold_policy:
  fixed_probability_threshold: 0.5
  validation_optimization_allowed: false
hpo:
  allowed: false
  rationale: Fixed deterministic Week-4 baseline; HGB tuning is out of scope for this
    prompt.
```

### XGBoost baseline (Prompt 03)

Source: `configs/week5_xgboost_baseline.yaml` (SHA-256: `cf27f717c80f9041d9176e62f3cbbbee650545f95a260060fe0bab5c9d525d2f`)

```yaml
baseline_version: arrival_xgboost_baseline_v1
experiment_contract_version: arrival_week5_xgboost_experiment_v1
task: arrival_core
method_id: xgboost
feature_manifest_version: feature_manifest_arrival_v1
preprocessing_version: arrival_preprocessing_v1
classification:
  estimator: XGBClassifier
  objective: binary:logistic
  eval_metric: logloss
  n_estimators: 128
  learning_rate: 0.05
  max_depth: 6
  min_child_weight: 20.0
  subsample: 0.8
  colsample_bytree: 0.8
  reg_alpha: 0.0
  reg_lambda: 2.0
  tree_method: hist
  device: cpu
  max_bin: 256
  n_jobs: 1
  early_stopping: false
  random_state_source: configs/base.yaml:reproducibility.project_seed
  class_imbalance_policy: scale_pos_weight_from_training_fold_only
regression:
  estimator: XGBRegressor
  objective: reg:squarederror
  eval_metric: rmse
  n_estimators: 128
  learning_rate: 0.05
  max_depth: 6
  min_child_weight: 20.0
  subsample: 0.8
  colsample_bytree: 0.8
  reg_alpha: 0.0
  reg_lambda: 2.0
  tree_method: hist
  device: cpu
  max_bin: 256
  n_jobs: 1
  early_stopping: false
  random_state_source: configs/base.yaml:reproducibility.project_seed
resource_policy:
  target_memory_gib: 16
  execution_parallelism: 1
  production_training_rows: full_eligible_fold_rows
  production_sampling_allowed: false
  gpu_allowed: false
  early_stopping_policy: disabled_no_locked_validation_control
  rationale: 'Fixed CPU-safe baseline pre-registered before production validation
    metrics: histogram trees, bounded depth and estimators, conservative row/column
    sampling, regularization, single-process execution, and no validation-driven early
    stopping.'
threshold_policy:
  fixed_probability_threshold: 0.5
  validation_optimization_allowed: false
hpo:
  allowed: false
```

## 5. Week-4 baseline results

| Method | Model version | Rows | Pooled development diagnostics | Manifest |
|---|---|---:|---|---|
| linear | `arrival_linear_baseline_v1` | 1,254,518 | PR-AUC=0.1868351234216295; ROC-AUC=0.6133788376784445; Brier=0.23708146593989085; MAE=20.133629683479462; RMSE=44.79608278241707; R²=-0.0023045259247718164 | `artifacts/manifests/arrival_linear_rolling_run_v1.json` (SHA-256: `f974b6c63296f5cae2f688f70c344956d305ffc176484b6d08955f450103f866`) |
| random_forest | `arrival_random_forest_baseline_v1` | 1,254,518 | PR-AUC=0.19668651186545036; ROC-AUC=0.6087353377382; Brier=0.1977771002137716; MAE=19.59485270630749; RMSE=44.818925498261855; R²=-0.0033269901015251513 | `artifacts/manifests/arrival_random_forest_rolling_run_v1.json` (SHA-256: `953b5592b9f1ba4597127aeff989861050685a383dadddd322d9a50e04b89cca`) |
| hist_gradient_boosting | `arrival_hist_gradient_boosting_baseline_v1` | 1,254,518 | PR-AUC=0.19978273430293686; ROC-AUC=0.615176937043345; Brier=0.20539317809263535; MAE=19.61018246391032; RMSE=44.9519254014552; R²=-0.00929055954611191 | `artifacts/manifests/arrival_hist_gradient_boosting_rolling_run_v1.json` (SHA-256: `186d0db8cbbff4f074ff6e77fe6503e009de3a7ac237f79fe817145e06ad46b7`) |
| xgboost | `arrival_xgboost_baseline_v1` | 1,254,518 | PR-AUC=0.2035070987466659; ROC-AUC=0.6185847659353222; Brier=0.20586648231834576; MAE=19.48164858977673; RMSE=44.741530113986144; R²=0.00013520047122683732 | `artifacts/manifests/arrival_xgboost_rolling_run_v1.json` (SHA-256: `07fb2fee458492f2fa30fcbe521a3a40c08a385c28fe7324bb29603ed561fe05`) |

## 6. Week-5 frozen HPO settings

Protocol: `week5_hpo_protocol_v1_1`; hash: `b987c0489c5d18b02500f34c786c01359f45e50b2b32bdea3de4332a161556e5`.

- Trials per study: 10 COMPLETE.
- Sampler: TPESampler, seed 202601.
- Pruner: NopPruner.
- Optuna parallelism: 1; timeout: 14,400 seconds per study.
- Classification objective: maximize equal-fold macro mean PR-AUC using `predict_proba`.
- Regression objective: minimize equal-fold macro mean MAE on signed `ARR_DELAY`.
- Reporting threshold: 0.5; threshold tuning disabled.

Protocol source: `artifacts/manifests/week5_hpo_protocol_v1_1.json` (SHA-256: `b7eed99fd42f5e6c907cb9fc57e0c48c8e53f1806134f91741a7042cd1e740a6`)

### Search spaces, fixed parameters, and selected parameters

#### `random_forest_classification`

- Study name: `week5_hpo_protocol_v1_1__random_forest_classification`
- Direction/objective: `MAXIMIZE` / `mean_pr_auc_across_locked_folds`
- Best trial: `9`; best objective: `0.18856511611502808`
- Result manifest: `artifacts/manifests/week5_hpo_protocol_v1_1__random_forest_classification_result_v1.json` (SHA-256: `2eb072c1aa6691d30c3576b138230a226942f972738f0e05c21d1252ed4589a1`)
- SQLite storage: `artifacts/optuna_studies/week5_hpo_protocol_v1_1__random_forest_classification.sqlite3`; SHA-256: `32dfdfe6fda85b1fc966ad6f8f4b7de02d793b5afc1f152e2a6c706acbb7c3d6`

Frozen search space:
```json
{
  "n_estimators": {
    "type": "int",
    "low": 64,
    "high": 192,
    "step": 32
  },
  "max_depth": {
    "type": "int",
    "low": 6,
    "high": 18,
    "step": 4
  },
  "min_samples_split": {
    "type": "int",
    "low": 20,
    "high": 80,
    "step": 20
  },
  "min_samples_leaf": {
    "type": "int",
    "low": 10,
    "high": 40,
    "step": 10
  },
  "max_features": {
    "type": "categorical",
    "choices": [
      "sqrt",
      "log2",
      0.75
    ]
  },
  "max_samples": {
    "type": "categorical",
    "choices": [
      0.6,
      0.8,
      1.0
    ]
  }
}
```

Frozen fixed parameters:
```json
{
  "n_jobs": 1,
  "bootstrap": true,
  "class_weight_policy": "balanced_from_training_fold_only",
  "random_state": 202601
}
```

Selected best parameters:
```json
{
  "max_depth": 6,
  "max_features": "log2",
  "max_samples": 0.6,
  "min_samples_leaf": 40,
  "min_samples_split": 20,
  "n_estimators": 160
}
```

#### `random_forest_regression`

- Study name: `week5_hpo_protocol_v1_1__random_forest_regression`
- Direction/objective: `MINIMIZE` / `mean_mae_across_locked_folds`
- Best trial: `3`; best objective: `19.25971111931776`
- Result manifest: `artifacts/manifests/week5_hpo_protocol_v1_1__random_forest_regression_result_v1.json` (SHA-256: `2192444e3495a6080752619001b88bd733e7c42b109ff5924f06418f18cce85d`)
- SQLite storage: `artifacts/optuna_studies/week5_hpo_protocol_v1_1__random_forest_regression.sqlite3`; SHA-256: `e775984504831acaf050f7c4fdf1f3126882617ce52ead1f14d7416aa06082e7`

Frozen search space:
```json
{
  "n_estimators": {
    "type": "int",
    "low": 64,
    "high": 192,
    "step": 32
  },
  "max_depth": {
    "type": "int",
    "low": 6,
    "high": 18,
    "step": 4
  },
  "min_samples_split": {
    "type": "int",
    "low": 20,
    "high": 80,
    "step": 20
  },
  "min_samples_leaf": {
    "type": "int",
    "low": 10,
    "high": 40,
    "step": 10
  },
  "max_features": {
    "type": "categorical",
    "choices": [
      "sqrt",
      "log2",
      0.75
    ]
  },
  "max_samples": {
    "type": "categorical",
    "choices": [
      0.6,
      0.8,
      1.0
    ]
  }
}
```

Frozen fixed parameters:
```json
{
  "n_jobs": 1,
  "bootstrap": true,
  "random_state": 202601
}
```

Selected best parameters:
```json
{
  "max_depth": 10,
  "max_features": "sqrt",
  "max_samples": 0.6,
  "min_samples_leaf": 30,
  "min_samples_split": 20,
  "n_estimators": 192
}
```

#### `hist_gradient_boosting_classification`

- Study name: `week5_hpo_protocol_v1_1__hist_gradient_boosting_classification`
- Direction/objective: `MAXIMIZE` / `mean_pr_auc_across_locked_folds`
- Best trial: `7`; best objective: `0.19206058881695232`
- Result manifest: `artifacts/manifests/week5_hpo_protocol_v1_1__hist_gradient_boosting_classification_result_v1.json` (SHA-256: `aa1c91aa7adec6875300642d07796e9c1e40ccafc083c0a029c318057cc89951`)
- SQLite storage: `artifacts\optuna_studies\week5_hpo_protocol_v1_1__hist_gradient_boosting_classification.sqlite3`; SHA-256: `663f6c81d55ed53b46900c67ebd8fec066d3789612deecb61fc1cd3f2cce12f4`

Frozen search space:
```json
{
  "learning_rate": {
    "type": "float",
    "low": 0.03,
    "high": 0.15,
    "log": true
  },
  "max_iter": {
    "type": "int",
    "low": 100,
    "high": 300,
    "step": 50
  },
  "max_leaf_nodes": {
    "type": "int",
    "low": 15,
    "high": 63,
    "step": 8
  },
  "max_depth": {
    "type": "int",
    "low": 4,
    "high": 12,
    "step": 2
  },
  "min_samples_leaf": {
    "type": "int",
    "low": 20,
    "high": 100,
    "step": 20
  },
  "l2_regularization": {
    "type": "float",
    "low": 0.0,
    "high": 5.0,
    "step": 0.5
  },
  "max_features": {
    "type": "float",
    "low": 0.5,
    "high": 1.0,
    "step": 0.1
  }
}
```

Frozen fixed parameters:
```json
{
  "early_stopping": false,
  "class_weight_policy": "balanced_from_training_fold_only",
  "random_state": 202601
}
```

Selected best parameters:
```json
{
  "l2_regularization": 1.0,
  "learning_rate": 0.05589991383688294,
  "max_depth": 6,
  "max_features": 0.6,
  "max_iter": 150,
  "max_leaf_nodes": 39,
  "min_samples_leaf": 20
}
```

#### `hist_gradient_boosting_regression`

- Study name: `week5_hpo_protocol_v1_1__hist_gradient_boosting_regression`
- Direction/objective: `MINIMIZE` / `mean_mae_across_locked_folds`
- Best trial: `3`; best objective: `19.25819001384582`
- Result manifest: `artifacts/manifests/week5_hpo_protocol_v1_1__hist_gradient_boosting_regression_result_v1.json` (SHA-256: `358b6ccb42d8e15214a3fd0bf669420575d3885b630020c4d9ead7ca63a4206e`)
- SQLite storage: `artifacts\optuna_studies\week5_hpo_protocol_v1_1__hist_gradient_boosting_regression.sqlite3`; SHA-256: `46990b0361d12a98ff4cafc73329ea6e70ad994d5e8eb3c6e3cd49680391d1b5`

Frozen search space:
```json
{
  "learning_rate": {
    "type": "float",
    "low": 0.03,
    "high": 0.15,
    "log": true
  },
  "max_iter": {
    "type": "int",
    "low": 100,
    "high": 300,
    "step": 50
  },
  "max_leaf_nodes": {
    "type": "int",
    "low": 15,
    "high": 63,
    "step": 8
  },
  "max_depth": {
    "type": "int",
    "low": 4,
    "high": 12,
    "step": 2
  },
  "min_samples_leaf": {
    "type": "int",
    "low": 20,
    "high": 100,
    "step": 20
  },
  "l2_regularization": {
    "type": "float",
    "low": 0.0,
    "high": 5.0,
    "step": 0.5
  },
  "max_features": {
    "type": "float",
    "low": 0.5,
    "high": 1.0,
    "step": 0.1
  }
}
```

Frozen fixed parameters:
```json
{
  "early_stopping": false,
  "random_state": 202601
}
```

Selected best parameters:
```json
{
  "l2_regularization": 4.0,
  "learning_rate": 0.07954536476970449,
  "max_depth": 4,
  "max_features": 0.6,
  "max_iter": 250,
  "max_leaf_nodes": 55,
  "min_samples_leaf": 60
}
```

#### `xgboost_classification`

- Study name: `week5_hpo_protocol_v1_1__xgboost_classification`
- Direction/objective: `MAXIMIZE` / `mean_pr_auc_across_locked_folds`
- Best trial: `1`; best objective: `0.19561574977614776`
- Result manifest: `artifacts/manifests/week5_hpo_protocol_v1_1__xgboost_classification_result_v1.json` (SHA-256: `1da21cff50447c741efdc4de644dc1bce88f203af11b00895cebeeb64a621680`)
- SQLite storage: `artifacts\optuna_studies\week5_hpo_protocol_v1_1__xgboost_classification.sqlite3`; SHA-256: `dc86f2b3f039831f7807c04865951f7467a75b06954fc8f2e98490a1dd44fc52`

Frozen search space:
```json
{
  "n_estimators": {
    "type": "int",
    "low": 100,
    "high": 400,
    "step": 50
  },
  "learning_rate": {
    "type": "float",
    "low": 0.03,
    "high": 0.2,
    "log": true
  },
  "max_depth": {
    "type": "int",
    "low": 3,
    "high": 8,
    "step": 1
  },
  "min_child_weight": {
    "type": "float",
    "low": 1.0,
    "high": 12.0,
    "step": 1.0
  },
  "subsample": {
    "type": "float",
    "low": 0.6,
    "high": 1.0,
    "step": 0.1
  },
  "colsample_bytree": {
    "type": "float",
    "low": 0.6,
    "high": 1.0,
    "step": 0.1
  },
  "reg_alpha": {
    "type": "float",
    "low": 0.0,
    "high": 5.0,
    "step": 0.5
  },
  "reg_lambda": {
    "type": "float",
    "low": 0.1,
    "high": 10.0,
    "log": true
  }
}
```

Frozen fixed parameters:
```json
{
  "tree_method": "hist",
  "device": "cpu",
  "max_bin": 256,
  "n_jobs": 1,
  "objective": "binary:logistic",
  "eval_metric": "logloss",
  "class_weight_policy": "balanced_from_training_fold_only",
  "random_state": 202601
}
```

Selected best parameters:
```json
{
  "colsample_bytree": 0.6,
  "learning_rate": 0.03230824360421075,
  "max_depth": 6,
  "min_child_weight": 7.0,
  "n_estimators": 150,
  "reg_alpha": 4.5,
  "reg_lambda": 0.30338019740385763,
  "subsample": 0.9
}
```

#### `xgboost_regression`

- Study name: `week5_hpo_protocol_v1_1__xgboost_regression`
- Direction/objective: `MINIMIZE` / `mean_mae_across_locked_folds`
- Best trial: `6`; best objective: `19.19011236521375`
- Result manifest: `artifacts/manifests/week5_hpo_protocol_v1_1__xgboost_regression_result_v1.json` (SHA-256: `eb82039e078ff99e7b4bce9960bf6365377f99723b8ab10204bb0a6760faf20e`)
- SQLite storage: `artifacts\optuna_studies\week5_hpo_protocol_v1_1__xgboost_regression.sqlite3`; SHA-256: `a90d8c5b4cd0fadce2e4dde3c316f7973b463a3f9b060fd74c735ce6456186f4`

Frozen search space:
```json
{
  "n_estimators": {
    "type": "int",
    "low": 100,
    "high": 400,
    "step": 50
  },
  "learning_rate": {
    "type": "float",
    "low": 0.03,
    "high": 0.2,
    "log": true
  },
  "max_depth": {
    "type": "int",
    "low": 3,
    "high": 8,
    "step": 1
  },
  "min_child_weight": {
    "type": "float",
    "low": 1.0,
    "high": 12.0,
    "step": 1.0
  },
  "subsample": {
    "type": "float",
    "low": 0.6,
    "high": 1.0,
    "step": 0.1
  },
  "colsample_bytree": {
    "type": "float",
    "low": 0.6,
    "high": 1.0,
    "step": 0.1
  },
  "reg_alpha": {
    "type": "float",
    "low": 0.0,
    "high": 5.0,
    "step": 0.5
  },
  "reg_lambda": {
    "type": "float",
    "low": 0.1,
    "high": 10.0,
    "log": true
  }
}
```

Frozen fixed parameters:
```json
{
  "tree_method": "hist",
  "device": "cpu",
  "max_bin": 256,
  "n_jobs": 1,
  "objective": "reg:squarederror",
  "eval_metric": "mae",
  "random_state": 202601
}
```

Selected best parameters:
```json
{
  "colsample_bytree": 0.6,
  "learning_rate": 0.062477640978226154,
  "max_depth": 4,
  "min_child_weight": 6.0,
  "n_estimators": 200,
  "reg_alpha": 1.0,
  "reg_lambda": 0.39186667315961216,
  "subsample": 0.7
}
```

### Every recorded HPO trial configuration

The tables below are read-only projections of the six authoritative Optuna SQLite studies. They include every recorded trial state, objective value, parameter set, and timestamps.

#### `random_forest_classification`

| Trial | State | Objective | Parameters | Start (UTC) | Complete (UTC) |
|---:|---|---:|---|---|---|
| 0 | COMPLETE | 0.18825535558784806 | `{"max_depth": 10, "max_features": "log2", "max_samples": 0.6, "min_samples_leaf": 30, "min_samples_split": 20, "n_estimators": 160}` | 2026-09-17T01:26:36.355489 | 2026-09-17T01:37:41.590110 |
| 1 | COMPLETE | 0.18727719152921063 | `{"max_depth": 14, "max_features": "sqrt", "max_samples": 0.6, "min_samples_leaf": 10, "min_samples_split": 60, "n_estimators": 128}` | 2026-09-17T01:37:41.605747 | 2026-09-17T01:47:44.384191 |
| 2 | COMPLETE | 0.1768219018535495 | `{"max_depth": 14, "max_features": 0.75, "max_samples": 0.8, "min_samples_leaf": 30, "min_samples_split": 80, "n_estimators": 160}` | 2026-09-17T01:47:44.399826 | 2026-09-17T02:14:14.975037 |
| 3 | COMPLETE | 0.1884546355927051 | `{"max_depth": 10, "max_features": "sqrt", "max_samples": 0.6, "min_samples_leaf": 30, "min_samples_split": 20, "n_estimators": 192}` | 2026-09-17T02:14:14.975037 | 2026-09-17T02:27:07.652095 |
| 4 | COMPLETE | 0.17553388795546954 | `{"max_depth": 18, "max_features": 0.75, "max_samples": 0.6, "min_samples_leaf": 20, "min_samples_split": 80, "n_estimators": 64}` | 2026-09-17T02:27:07.652095 | 2026-09-17T02:37:19.027577 |
| 5 | COMPLETE | 0.18168103391202062 | `{"max_depth": 10, "max_features": 0.75, "max_samples": 0.8, "min_samples_leaf": 10, "min_samples_split": 40, "n_estimators": 96}` | 2026-09-17T02:37:19.043179 | 2026-09-17T02:51:04.089874 |
| 6 | COMPLETE | 0.18587102057131774 | `{"max_depth": 18, "max_features": "sqrt", "max_samples": 1.0, "min_samples_leaf": 40, "min_samples_split": 60, "n_estimators": 96}` | 2026-09-17T02:51:04.105500 | 2026-09-17T03:02:02.527643 |
| 7 | COMPLETE | 0.18855215727435443 | `{"max_depth": 10, "max_features": "sqrt", "max_samples": 0.8, "min_samples_leaf": 10, "min_samples_split": 80, "n_estimators": 192}` | 2026-09-17T03:02:02.527643 | 2026-09-17T03:17:11.167835 |
| 8 | COMPLETE | 0.1747402011838529 | `{"max_depth": 18, "max_features": 0.75, "max_samples": 0.8, "min_samples_leaf": 20, "min_samples_split": 60, "n_estimators": 160}` | 2026-09-17T03:17:11.183449 | 2026-09-17T03:45:51.574838 |
| 9 | COMPLETE | 0.18856511611502808 | `{"max_depth": 6, "max_features": "log2", "max_samples": 0.6, "min_samples_leaf": 40, "min_samples_split": 20, "n_estimators": 160}` | 2026-09-17T03:45:51.590483 | 2026-09-17T03:55:08.683620 |

#### `random_forest_regression`

| Trial | State | Objective | Parameters | Start (UTC) | Complete (UTC) |
|---:|---|---:|---|---|---|
| 0 | COMPLETE | 19.261325671039074 | `{"max_depth": 10, "max_features": "log2", "max_samples": 0.6, "min_samples_leaf": 30, "min_samples_split": 20, "n_estimators": 160}` | 2026-09-17T03:55:08.918984 | 2026-09-17T04:03:28.183597 |
| 1 | COMPLETE | 19.40813132668006 | `{"max_depth": 14, "max_features": "sqrt", "max_samples": 0.6, "min_samples_leaf": 10, "min_samples_split": 60, "n_estimators": 128}` | 2026-09-17T04:03:28.199221 | 2026-09-17T04:11:43.290158 |
| 2 | COMPLETE | 19.80178531241035 | `{"max_depth": 14, "max_features": 0.75, "max_samples": 0.8, "min_samples_leaf": 30, "min_samples_split": 80, "n_estimators": 160}` | 2026-09-17T04:11:43.290158 | 2026-09-17T04:37:19.698966 |
| 3 | COMPLETE | 19.25971111931776 | `{"max_depth": 10, "max_features": "sqrt", "max_samples": 0.6, "min_samples_leaf": 30, "min_samples_split": 20, "n_estimators": 192}` | 2026-09-17T04:37:19.714591 | 2026-09-17T04:47:04.237741 |
| 4 | COMPLETE | 20.021505339479877 | `{"max_depth": 18, "max_features": 0.75, "max_samples": 0.6, "min_samples_leaf": 20, "min_samples_split": 80, "n_estimators": 64}` | 2026-09-17T04:47:04.253366 | 2026-09-17T04:57:16.336386 |
| 5 | COMPLETE | 19.506943862885237 | `{"max_depth": 10, "max_features": 0.75, "max_samples": 0.8, "min_samples_leaf": 10, "min_samples_split": 40, "n_estimators": 96}` | 2026-09-17T04:57:16.336386 | 2026-09-17T05:10:12.903015 |
| 6 | COMPLETE | 19.41832789936559 | `{"max_depth": 18, "max_features": "sqrt", "max_samples": 1.0, "min_samples_leaf": 40, "min_samples_split": 60, "n_estimators": 96}` | 2026-09-17T05:10:12.903015 | 2026-09-17T05:19:32.527840 |
| 7 | COMPLETE | 19.286134603799788 | `{"max_depth": 10, "max_features": "sqrt", "max_samples": 0.8, "min_samples_leaf": 10, "min_samples_split": 80, "n_estimators": 192}` | 2026-09-17T05:19:32.527840 | 2026-09-17T05:31:03.168369 |
| 8 | COMPLETE | 20.08471100174822 | `{"max_depth": 18, "max_features": 0.75, "max_samples": 0.8, "min_samples_leaf": 20, "min_samples_split": 60, "n_estimators": 160}` | 2026-09-17T05:31:03.186181 | 2026-09-17T06:00:06.496475 |
| 9 | COMPLETE | 19.296169154156157 | `{"max_depth": 6, "max_features": "log2", "max_samples": 0.6, "min_samples_leaf": 40, "min_samples_split": 20, "n_estimators": 160}` | 2026-09-17T06:00:06.512101 | 2026-09-17T06:06:20.763057 |

#### `hist_gradient_boosting_classification`

| Trial | State | Objective | Parameters | Start (UTC) | Complete (UTC) |
|---:|---|---:|---|---|---|
| 0 | COMPLETE | 0.1894102577161897 | `{"l2_regularization": 5.0, "learning_rate": 0.08879694703955916, "max_depth": 10, "max_features": 0.9, "max_iter": 150, "max_leaf_nodes": 23, "min_samples_leaf": 40}` | 2026-09-17T15:51:28.577240 | 2026-09-17T15:53:10.523181 |
| 1 | COMPLETE | 0.1910637062686652 | `{"l2_regularization": 3.5, "learning_rate": 0.08920317147402633, "max_depth": 8, "max_features": 0.5, "max_iter": 100, "max_leaf_nodes": 15, "min_samples_leaf": 60}` | 2026-09-17T15:53:10.541283 | 2026-09-17T15:54:36.509276 |
| 2 | COMPLETE | 0.18607690191020995 | `{"l2_regularization": 0.0, "learning_rate": 0.1223038214133949, "max_depth": 8, "max_features": 0.8, "max_iter": 150, "max_leaf_nodes": 55, "min_samples_leaf": 40}` | 2026-09-17T15:54:36.515882 | 2026-09-17T15:56:15.142664 |
| 3 | COMPLETE | 0.19108294764137235 | `{"l2_regularization": 4.0, "learning_rate": 0.07954536476970449, "max_depth": 4, "max_features": 0.6, "max_iter": 250, "max_leaf_nodes": 55, "min_samples_leaf": 60}` | 2026-09-17T15:56:15.162563 | 2026-09-17T15:58:15.735952 |
| 4 | COMPLETE | 0.18961442073639978 | `{"l2_regularization": 3.5, "learning_rate": 0.09380355954530502, "max_depth": 8, "max_features": 0.8, "max_iter": 100, "max_leaf_nodes": 63, "min_samples_leaf": 40}` | 2026-09-17T15:58:15.756773 | 2026-09-17T15:59:56.020028 |
| 5 | COMPLETE | 0.18895814819940462 | `{"l2_regularization": 1.0, "learning_rate": 0.0619422979517792, "max_depth": 10, "max_features": 1.0, "max_iter": 100, "max_leaf_nodes": 63, "min_samples_leaf": 60}` | 2026-09-17T15:59:56.032462 | 2026-09-17T16:01:36.760116 |
| 6 | COMPLETE | 0.18717150659978588 | `{"l2_regularization": 5.0, "learning_rate": 0.13565254232591137, "max_depth": 8, "max_features": 0.7, "max_iter": 200, "max_leaf_nodes": 23, "min_samples_leaf": 80}` | 2026-09-17T16:01:36.778234 | 2026-09-17T16:03:28.230172 |
| 7 | COMPLETE | 0.19206058881695232 | `{"l2_regularization": 1.0, "learning_rate": 0.05589991383688294, "max_depth": 6, "max_features": 0.6, "max_iter": 150, "max_leaf_nodes": 39, "min_samples_leaf": 20}` | 2026-09-17T16:03:28.248895 | 2026-09-17T16:05:17.211345 |
| 8 | COMPLETE | 0.19127577495321274 | `{"l2_regularization": 4.0, "learning_rate": 0.05794522865933138, "max_depth": 6, "max_features": 0.8, "max_iter": 200, "max_leaf_nodes": 47, "min_samples_leaf": 40}` | 2026-09-17T16:05:17.230327 | 2026-09-17T16:07:13.383796 |
| 9 | COMPLETE | 0.18788462569642556 | `{"l2_regularization": 0.0, "learning_rate": 0.13790680431816987, "max_depth": 6, "max_features": 0.8, "max_iter": 200, "max_leaf_nodes": 39, "min_samples_leaf": 40}` | 2026-09-17T16:07:13.399664 | 2026-09-17T16:09:05.057487 |

#### `hist_gradient_boosting_regression`

| Trial | State | Objective | Parameters | Start (UTC) | Complete (UTC) |
|---:|---|---:|---|---|---|
| 0 | COMPLETE | 19.469960840396638 | `{"l2_regularization": 5.0, "learning_rate": 0.08879694703955916, "max_depth": 10, "max_features": 0.9, "max_iter": 150, "max_leaf_nodes": 23, "min_samples_leaf": 40}` | 2026-09-17T16:30:28.596583 | 2026-09-17T16:32:02.472968 |
| 1 | COMPLETE | 19.264931074104325 | `{"l2_regularization": 3.5, "learning_rate": 0.08920317147402633, "max_depth": 8, "max_features": 0.5, "max_iter": 100, "max_leaf_nodes": 15, "min_samples_leaf": 60}` | 2026-09-17T16:32:02.494163 | 2026-09-17T16:33:26.991711 |
| 2 | COMPLETE | 19.674962392612613 | `{"l2_regularization": 0.0, "learning_rate": 0.1223038214133949, "max_depth": 8, "max_features": 0.8, "max_iter": 150, "max_leaf_nodes": 55, "min_samples_leaf": 40}` | 2026-09-17T16:33:27.009517 | 2026-09-17T16:35:00.335760 |
| 3 | COMPLETE | 19.25819001384582 | `{"l2_regularization": 4.0, "learning_rate": 0.07954536476970449, "max_depth": 4, "max_features": 0.6, "max_iter": 250, "max_leaf_nodes": 55, "min_samples_leaf": 60}` | 2026-09-17T16:35:00.351430 | 2026-09-17T16:36:41.852183 |
| 4 | COMPLETE | 19.47640761680078 | `{"l2_regularization": 3.5, "learning_rate": 0.09380355954530502, "max_depth": 8, "max_features": 0.8, "max_iter": 100, "max_leaf_nodes": 63, "min_samples_leaf": 40}` | 2026-09-17T16:36:41.869600 | 2026-09-17T16:38:11.174250 |
| 5 | COMPLETE | 19.514679734949123 | `{"l2_regularization": 1.0, "learning_rate": 0.0619422979517792, "max_depth": 10, "max_features": 1.0, "max_iter": 100, "max_leaf_nodes": 63, "min_samples_leaf": 60}` | 2026-09-17T16:38:11.190786 | 2026-09-17T16:39:39.498358 |
| 6 | COMPLETE | 19.556263045559277 | `{"l2_regularization": 5.0, "learning_rate": 0.13565254232591137, "max_depth": 8, "max_features": 0.7, "max_iter": 200, "max_leaf_nodes": 23, "min_samples_leaf": 80}` | 2026-09-17T16:39:39.514809 | 2026-09-17T16:41:15.267467 |
| 7 | COMPLETE | 19.28829348263966 | `{"l2_regularization": 1.0, "learning_rate": 0.05589991383688294, "max_depth": 6, "max_features": 0.6, "max_iter": 150, "max_leaf_nodes": 39, "min_samples_leaf": 20}` | 2026-09-17T16:41:15.286490 | 2026-09-17T16:42:50.185308 |
| 8 | COMPLETE | 19.35983983236376 | `{"l2_regularization": 4.0, "learning_rate": 0.05794522865933138, "max_depth": 6, "max_features": 0.8, "max_iter": 200, "max_leaf_nodes": 47, "min_samples_leaf": 40}` | 2026-09-17T16:42:50.200454 | 2026-09-17T16:44:33.763521 |
| 9 | COMPLETE | 19.690301422496933 | `{"l2_regularization": 0.0, "learning_rate": 0.13790680431816987, "max_depth": 6, "max_features": 0.8, "max_iter": 200, "max_leaf_nodes": 39, "min_samples_leaf": 40}` | 2026-09-17T16:44:33.779879 | 2026-09-17T16:46:12.732859 |

#### `xgboost_classification`

| Trial | State | Objective | Parameters | Start (UTC) | Complete (UTC) |
|---:|---|---:|---|---|---|
| 0 | COMPLETE | 0.19118988001166942 | `{"colsample_bytree": 1.0, "learning_rate": 0.05196496696782546, "max_depth": 4, "min_child_weight": 8.0, "n_estimators": 300, "reg_alpha": 4.0, "reg_lambda": 2.2602747344150025, "subsample": 0.7}` | 2026-09-17T16:59:55.649199 | 2026-09-17T17:03:33.415961 |
| 1 | COMPLETE | 0.19561574977614776 | `{"colsample_bytree": 0.6, "learning_rate": 0.03230824360421075, "max_depth": 6, "min_child_weight": 7.0, "n_estimators": 150, "reg_alpha": 4.5, "reg_lambda": 0.30338019740385763, "subsample": 0.9}` | 2026-09-17T17:03:33.431588 | 2026-09-17T17:06:06.695062 |
| 2 | COMPLETE | 0.19029356163830696 | `{"colsample_bytree": 0.9, "learning_rate": 0.08111430103513835, "max_depth": 5, "min_child_weight": 1.0, "n_estimators": 350, "reg_alpha": 4.0, "reg_lambda": 2.87665996438603, "subsample": 0.9}` | 2026-09-17T17:06:06.705477 | 2026-09-17T17:10:01.775852 |
| 3 | COMPLETE | 0.1928262690245677 | `{"colsample_bytree": 0.6, "learning_rate": 0.06911469740344414, "max_depth": 7, "min_child_weight": 3.0, "n_estimators": 150, "reg_alpha": 5.0, "reg_lambda": 0.6401119830882372, "subsample": 0.9}` | 2026-09-17T17:10:01.791487 | 2026-09-17T17:12:46.885028 |
| 4 | COMPLETE | 0.18837563782226774 | `{"colsample_bytree": 1.0, "learning_rate": 0.11591740176014889, "max_depth": 6, "min_child_weight": 6.0, "n_estimators": 150, "reg_alpha": 3.0, "reg_lambda": 1.335592482585551, "subsample": 0.6}` | 2026-09-17T17:12:46.902456 | 2026-09-17T17:15:34.201695 |
| 5 | COMPLETE | 0.18117002253515438 | `{"colsample_bytree": 0.8, "learning_rate": 0.19677403361718057, "max_depth": 8, "min_child_weight": 6.0, "n_estimators": 150, "reg_alpha": 3.5, "reg_lambda": 6.7643233695301985, "subsample": 0.7}` | 2026-09-17T17:15:34.217809 | 2026-09-17T17:18:31.193202 |
| 6 | COMPLETE | 0.1942860475411889 | `{"colsample_bytree": 0.6, "learning_rate": 0.062477640978226154, "max_depth": 4, "min_child_weight": 6.0, "n_estimators": 200, "reg_alpha": 1.0, "reg_lambda": 0.39186667315961216, "subsample": 0.7}` | 2026-09-17T17:18:31.213711 | 2026-09-17T17:21:28.901506 |
| 7 | COMPLETE | 0.1905315324668529 | `{"colsample_bytree": 0.9, "learning_rate": 0.08932164892342243, "max_depth": 6, "min_child_weight": 3.0, "n_estimators": 200, "reg_alpha": 3.0, "reg_lambda": 7.862210909636297, "subsample": 0.7}` | 2026-09-17T17:21:28.917299 | 2026-09-17T17:24:46.331788 |
| 8 | COMPLETE | 0.19169497223935872 | `{"colsample_bytree": 0.9, "learning_rate": 0.0731471096973765, "max_depth": 5, "min_child_weight": 4.0, "n_estimators": 250, "reg_alpha": 5.0, "reg_lambda": 0.34775771466012717, "subsample": 0.6}` | 2026-09-17T17:24:46.348788 | 2026-09-17T17:28:23.574171 |
| 9 | COMPLETE | 0.19058846432192708 | `{"colsample_bytree": 0.8, "learning_rate": 0.036032997957054065, "max_depth": 7, "min_child_weight": 4.0, "n_estimators": 400, "reg_alpha": 3.0, "reg_lambda": 0.995692193967802, "subsample": 0.9}` | 2026-09-17T17:28:23.591236 | 2026-09-17T17:33:41.417715 |

#### `xgboost_regression`

| Trial | State | Objective | Parameters | Start (UTC) | Complete (UTC) |
|---:|---|---:|---|---|---|
| 0 | COMPLETE | 19.26632106042119 | `{"colsample_bytree": 1.0, "learning_rate": 0.05196496696782546, "max_depth": 4, "min_child_weight": 8.0, "n_estimators": 300, "reg_alpha": 4.0, "reg_lambda": 2.2602747344150025, "subsample": 0.7}` | 2026-09-17T17:33:41.769415 | 2026-09-17T17:37:17.712253 |
| 1 | COMPLETE | 19.224675450364394 | `{"colsample_bytree": 0.6, "learning_rate": 0.03230824360421075, "max_depth": 6, "min_child_weight": 7.0, "n_estimators": 150, "reg_alpha": 4.5, "reg_lambda": 0.30338019740385763, "subsample": 0.9}` | 2026-09-17T17:37:17.733292 | 2026-09-17T17:39:55.808034 |
| 2 | COMPLETE | 19.502323082629225 | `{"colsample_bytree": 0.9, "learning_rate": 0.08111430103513835, "max_depth": 5, "min_child_weight": 1.0, "n_estimators": 350, "reg_alpha": 4.0, "reg_lambda": 2.87665996438603, "subsample": 0.9}` | 2026-09-17T17:39:55.826092 | 2026-09-17T17:43:53.673931 |
| 3 | COMPLETE | 19.45739911646075 | `{"colsample_bytree": 0.6, "learning_rate": 0.06911469740344414, "max_depth": 7, "min_child_weight": 3.0, "n_estimators": 150, "reg_alpha": 5.0, "reg_lambda": 0.6401119830882372, "subsample": 0.9}` | 2026-09-17T17:43:53.688973 | 2026-09-17T17:46:37.280290 |
| 4 | COMPLETE | 19.68066177341461 | `{"colsample_bytree": 1.0, "learning_rate": 0.11591740176014889, "max_depth": 6, "min_child_weight": 6.0, "n_estimators": 150, "reg_alpha": 3.0, "reg_lambda": 1.335592482585551, "subsample": 0.6}` | 2026-09-17T17:46:37.295910 | 2026-09-17T17:49:08.399407 |
| 5 | COMPLETE | 20.398840156934067 | `{"colsample_bytree": 0.8, "learning_rate": 0.19677403361718057, "max_depth": 8, "min_child_weight": 6.0, "n_estimators": 150, "reg_alpha": 3.5, "reg_lambda": 6.7643233695301985, "subsample": 0.7}` | 2026-09-17T17:49:08.424175 | 2026-09-17T17:51:45.614478 |
| 6 | COMPLETE | 19.19011236521375 | `{"colsample_bytree": 0.6, "learning_rate": 0.062477640978226154, "max_depth": 4, "min_child_weight": 6.0, "n_estimators": 200, "reg_alpha": 1.0, "reg_lambda": 0.39186667315961216, "subsample": 0.7}` | 2026-09-17T17:51:45.616912 | 2026-09-17T17:54:24.588126 |
| 7 | COMPLETE | 19.544710627457896 | `{"colsample_bytree": 0.9, "learning_rate": 0.08932164892342243, "max_depth": 6, "min_child_weight": 3.0, "n_estimators": 200, "reg_alpha": 3.0, "reg_lambda": 7.862210909636297, "subsample": 0.7}` | 2026-09-17T17:54:24.603784 | 2026-09-17T17:57:15.281812 |
| 8 | COMPLETE | 19.4024564926602 | `{"colsample_bytree": 0.9, "learning_rate": 0.0731471096973765, "max_depth": 5, "min_child_weight": 4.0, "n_estimators": 250, "reg_alpha": 5.0, "reg_lambda": 0.34775771466012717, "subsample": 0.6}` | 2026-09-17T17:57:15.288290 | 2026-09-17T18:00:24.381110 |
| 9 | COMPLETE | 19.594641924301712 | `{"colsample_bytree": 0.8, "learning_rate": 0.036032997957054065, "max_depth": 7, "min_child_weight": 4.0, "n_estimators": 400, "reg_alpha": 3.0, "reg_lambda": 0.995692193967802, "subsample": 0.9}` | 2026-09-17T18:00:24.385280 | 2026-09-17T18:05:01.304684 |

## 7. Tuned Week-5 OOF refit configurations

These are deterministic refits from the frozen best parameters above; no additional tuning was performed.

### Random Forest tuned

- Run version: `arrival_random_forest_tuned_rolling_run_v1_1`
- Method: `random_forest`; seed: `202601`
- Feature manifest: `feature_manifest_arrival_v1`
- Preprocessing: `arrival_preprocessing_v1`
- OOF schema: `arrival_oof_prediction_v1`
- Rows: `1,254,518`
- HPO linkage: `{'classification_result': 'artifacts\\manifests\\week5_hpo_protocol_v1_1__random_forest_classification_result_v1.json', 'classification_result_sha256': '2eb072c1aa6691d30c3576b138230a226942f972738f0e05c21d1252ed4589a1', 'regression_result': 'artifacts\\manifests\\week5_hpo_protocol_v1_1__random_forest_regression_result_v1.json', 'regression_result_sha256': '2192444e3495a6080752619001b88bd733e7c42b109ff5924f06418f18cce85d', 'summary': 'artifacts\\manifests\\week5_random_forest_hpo_v1_1_summary_v4.json', 'summary_sha256': '54247aa8111dd7a73c8b636eb299da84ad442f818b3f447ecc5019c4efba77b0'}`

Frozen parameters:
```json
{
  "classification": {
    "max_depth": 6,
    "max_features": "log2",
    "max_samples": 0.6,
    "min_samples_leaf": 40,
    "min_samples_split": 20,
    "n_estimators": 160
  },
  "regression": {
    "max_depth": 10,
    "max_features": "sqrt",
    "max_samples": 0.6,
    "min_samples_leaf": 30,
    "min_samples_split": 20,
    "n_estimators": 192
  }
}
```

Pooled development diagnostics: PR-AUC=0.18773300702911916; ROC-AUC=0.6100267179930955; Brier=0.21690068463033743; MAE=19.46250542890854; RMSE=44.69367718856669; R²=0.0022728505995704973

| Fold | Train years | Validation year | Rows | OOF artifact |
|---|---|---:|---:|---|
| fold_1 | 2016, 2017, 2018 | 2019 | 391,075 | `artifacts\predictions\arrival_random_forest_tuned_rolling_run_v1_1_fold_1.parquet` |
| fold_2 | 2016, 2017, 2018, 2019 | 2020 | 242,121 | `artifacts\predictions\arrival_random_forest_tuned_rolling_run_v1_1_fold_2.parquet` |
| fold_3 | 2016, 2017, 2018, 2019, 2020 | 2021 | 309,621 | `artifacts\predictions\arrival_random_forest_tuned_rolling_run_v1_1_fold_3.parquet` |
| fold_4 | 2016, 2017, 2018, 2019, 2020, 2021 | 2022 | 311,701 | `artifacts\predictions\arrival_random_forest_tuned_rolling_run_v1_1_fold_4.parquet` |

Final manifest: `artifacts/manifests/arrival_random_forest_tuned_rolling_run_v1_1.json` (SHA-256: `f827e4c6f9748107b4aa5dfc6099220f890f8e82c547865d61ce4901db95f592`)

### HistGradientBoosting tuned

- Run version: `arrival_hist_gradient_boosting_tuned_rolling_run_v1_1`
- Method: `hist_gradient_boosting`; seed: `202601`
- Feature manifest: `feature_manifest_arrival_v1`
- Preprocessing: `arrival_preprocessing_v1`
- OOF schema: `arrival_oof_prediction_v1`
- Rows: `1,254,518`
- HPO linkage: `{'classification_result': 'artifacts\\manifests\\week5_hpo_protocol_v1_1__hist_gradient_boosting_classification_result_v1.json', 'classification_result_sha256': 'aa1c91aa7adec6875300642d07796e9c1e40ccafc083c0a029c318057cc89951', 'regression_result': 'artifacts\\manifests\\week5_hpo_protocol_v1_1__hist_gradient_boosting_regression_result_v1.json', 'regression_result_sha256': '358b6ccb42d8e15214a3fd0bf669420575d3885b630020c4d9ead7ca63a4206e', 'summary': 'artifacts\\manifests\\week5_hist_gradient_boosting_hpo_v1_1_summary_v1.json', 'summary_sha256': 'ba5d7c74e5a2ad1cb88f082c73021644cc737617ae9b275c443d5e4a66f272df'}`

Frozen parameters:
```json
{
  "classification": {
    "l2_regularization": 1.0,
    "learning_rate": 0.05589991383688294,
    "max_depth": 6,
    "max_features": 0.6,
    "max_iter": 150,
    "max_leaf_nodes": 39,
    "min_samples_leaf": 20
  },
  "regression": {
    "l2_regularization": 4.0,
    "learning_rate": 0.07954536476970449,
    "max_depth": 4,
    "max_features": 0.6,
    "max_iter": 250,
    "max_leaf_nodes": 55,
    "min_samples_leaf": 60
  }
}
```

Pooled development diagnostics: PR-AUC=0.20224129614544412; ROC-AUC=0.6158501622159459; Brier=0.20638482540291617; MAE=19.48635338625982; RMSE=44.7360667804361; R²=0.0003793700995550209

| Fold | Train years | Validation year | Rows | OOF artifact |
|---|---|---:|---:|---|
| fold_1 | 2016, 2017, 2018 | 2019 | 391,075 | `artifacts\predictions\arrival_hist_gradient_boosting_tuned_rolling_run_v1_1_fold_1.parquet` |
| fold_2 | 2016, 2017, 2018, 2019 | 2020 | 242,121 | `artifacts\predictions\arrival_hist_gradient_boosting_tuned_rolling_run_v1_1_fold_2.parquet` |
| fold_3 | 2016, 2017, 2018, 2019, 2020 | 2021 | 309,621 | `artifacts\predictions\arrival_hist_gradient_boosting_tuned_rolling_run_v1_1_fold_3.parquet` |
| fold_4 | 2016, 2017, 2018, 2019, 2020, 2021 | 2022 | 311,701 | `artifacts\predictions\arrival_hist_gradient_boosting_tuned_rolling_run_v1_1_fold_4.parquet` |

Final manifest: `artifacts/manifests/arrival_hist_gradient_boosting_tuned_rolling_run_v1_1.json` (SHA-256: `ca6695a3e85e95bdb521877685718e4775c5c1f3bbeb4f1490d46715a7c0a011`)

### XGBoost tuned

- Run version: `arrival_xgboost_tuned_rolling_run_v1_1`
- Method: `xgboost`; seed: `202601`
- Feature manifest: `feature_manifest_arrival_v1`
- Preprocessing: `arrival_preprocessing_v1`
- OOF schema: `arrival_oof_prediction_v1`
- Rows: `1,254,518`
- HPO linkage: `{'classification_result': 'artifacts\\manifests\\week5_hpo_protocol_v1_1__xgboost_classification_result_v1.json', 'classification_result_sha256': '1da21cff50447c741efdc4de644dc1bce88f203af11b00895cebeeb64a621680', 'regression_result': 'artifacts\\manifests\\week5_hpo_protocol_v1_1__xgboost_regression_result_v1.json', 'regression_result_sha256': 'eb82039e078ff99e7b4bce9960bf6365377f99723b8ab10204bb0a6760faf20e', 'summary': 'artifacts\\manifests\\week5_xgboost_hpo_v1_1_summary_v1.json', 'summary_sha256': 'cc9dfc6fe8218565533473c68098b4682749e11f4fb8d906e15f44776cefc4e8'}`

Frozen parameters:
```json
{
  "classification": {
    "colsample_bytree": 0.6,
    "learning_rate": 0.03230824360421075,
    "max_depth": 6,
    "min_child_weight": 7.0,
    "n_estimators": 150,
    "reg_alpha": 4.5,
    "reg_lambda": 0.30338019740385763,
    "subsample": 0.9
  },
  "regression": {
    "colsample_bytree": 0.6,
    "learning_rate": 0.062477640978226154,
    "max_depth": 4,
    "min_child_weight": 6.0,
    "n_estimators": 200,
    "reg_alpha": 1.0,
    "reg_lambda": 0.39186667315961216,
    "subsample": 0.7
  }
}
```

Pooled development diagnostics: PR-AUC=0.20207564001837933; ROC-AUC=0.6176766804615507; Brier=0.20849772114256346; MAE=19.408001767596527; RMSE=44.65654802510613; R²=0.003929880824889764

| Fold | Train years | Validation year | Rows | OOF artifact |
|---|---|---:|---:|---|
| fold_1 | 2016, 2017, 2018 | 2019 | 391,075 | `artifacts\predictions\arrival_xgboost_tuned_rolling_run_v1_1_fold_1.parquet` |
| fold_2 | 2016, 2017, 2018, 2019 | 2020 | 242,121 | `artifacts\predictions\arrival_xgboost_tuned_rolling_run_v1_1_fold_2.parquet` |
| fold_3 | 2016, 2017, 2018, 2019, 2020 | 2021 | 309,621 | `artifacts\predictions\arrival_xgboost_tuned_rolling_run_v1_1_fold_3.parquet` |
| fold_4 | 2016, 2017, 2018, 2019, 2020, 2021 | 2022 | 311,701 | `artifacts\predictions\arrival_xgboost_tuned_rolling_run_v1_1_fold_4.parquet` |

Final manifest: `artifacts/manifests/arrival_xgboost_tuned_rolling_run_v1_1.json` (SHA-256: `8d4bc4e075dfde0bdc53efdbee14896b8ac066f3d22275eac8dcd49564930143`)

## 8. Week-5 final status and boundaries

Authoritative closeout: `artifacts/manifests/week5_core_arrival_xgboost_optuna_summary_v1.json` (SHA-256: `2d20f61cb7fde764fe11711febcdc60a15f373f6684d5fdbdad1043844ed826e`)
- Protocol: `week5_hpo_protocol_v1_1` / `b987c0489c5d18b02500f34c786c01359f45e50b2b32bdea3de4332a161556e5`.
- Status: `PASS`; Week 5 completed: `True`.
- OOF parity: `PASS` row parity, `PASS` target parity; 1,254,518 common rows.
- No 2023 HPO or model selection; no row-level 2024 access.
- Weather, predicted Departure, DEP_DELAY, actual operational outcomes, and Chain predictors were not used.
- ARR-B disabled; auxiliary Weather not run because point-in-time provenance remains AUDIT_REQUIRED.
- Weighted Ensemble, SHAP, 2023 selection, and controlled ablations remain Week-6 work and were not started.

## 9. Important interpretation

The listed metrics are development OOF diagnostics for 2016-2022. They are not final 2024 holdout results and are not a model-champion decision. The original interrupted RF protocol-v1 attempt remains historical evidence and is not counted as an additional completed production study.
