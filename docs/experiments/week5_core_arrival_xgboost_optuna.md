# Week 5 Core Arrival: XGBoost and Fixed-Budget Optuna Closeout

## Purpose

This report closes Week 5 after validating the four Core Arrival base methods, six fixed-budget HPO studies, and tuned rolling development OOF evidence. No Week-6 activity is performed here.

## Frozen protocol

- Version: `week5_hpo_protocol_v1_1`
- Hash: `b987c0489c5d18b02500f34c786c01359f45e50b2b32bdea3de4332a161556e5`
- Four equal-weight temporal folds spanning validation years 2019-2022.
- Classification maximizes macro mean PR-AUC from probabilities; regression minimizes macro mean MAE on signed ARR_DELAY.
- Ten COMPLETE trials per study, TPESampler seed 202601, NopPruner, single-study parallelism, and 14,400 seconds per study.

## Methods

1. Logistic / Ridge - preserved Week-4 evidence.
2. Random Forest - tuned Week-5 evidence.
3. HistGradientBoosting - tuned Week-5 evidence.
4. XGBoost - baseline plus tuned Week-5 evidence.
5. Weighted Ensemble - not started; belongs to Week 6.

## Production HPO studies

| Study | Direction | COMPLETE | Best trial | Best objective | Cleanup provenance |
|---|---:|---:|---:|---:|---|
| `random_forest_classification` | MAXIMIZE | 10 | 9 | 0.188565116115 | ACCEPTED_VIA_NON_STATISTICAL_AMENDMENT |
| `random_forest_regression` | MINIMIZE | 10 | 3 | 19.2597111193 | ACCEPTED_VIA_NON_STATISTICAL_AMENDMENT |
| `hist_gradient_boosting_classification` | MAXIMIZE | 10 | 7 | 0.192060588817 | GUARD_CLEANUP_SUCCESS |
| `hist_gradient_boosting_regression` | MINIMIZE | 10 | 3 | 19.2581900138 | GUARD_CLEANUP_SUCCESS |
| `xgboost_classification` | MAXIMIZE | 10 | 1 | 0.195615749776 | GUARD_CLEANUP_SUCCESS |
| `xgboost_regression` | MINIMIZE | 10 | 6 | 19.1901123652 | GUARD_CLEANUP_SUCCESS |

## RF environmental incident and amendments

The original RF protocol-v1 Classification attempt remains `BLOCKED_INCOMPLETE` with three COMPLETE trials after an environmental wall-clock interruption. It was not resumed or counted as a completed production study. Fresh RF v1.1 Classification and Regression studies each reached 10 COMPLETE trials. The execution amendment and non-statistical cleanup-provenance amendment remain part of the authoritative history; historical Prompt 04F/04G failures are not rewritten.

## Tuned development OOF

All four methods use the same four validation folds and exact 1,254,518-row `flight_key`, `y_arr_cls`, and signed `y_arr_reg` universe.

| Method | Rows | Pooled development OOF metrics |
|---|---:|---|
| linear_ridge | 1,254,518 | PR-AUC 0.1868351234; ROC-AUC 0.6133788377; Brier 0.2370814659; MAE 20.1336296835; RMSE 44.7960827824; R2 -0.0023045259 |
| random_forest | 1,254,518 | PR-AUC 0.1877330070; ROC-AUC 0.6100267180; Brier 0.2169006846; MAE 19.4625054289; RMSE 44.6936771886; R2 0.0022728506 |
| hist_gradient_boosting | 1,254,518 | PR-AUC 0.2022412961; ROC-AUC 0.6158501622; Brier 0.2063848254; MAE 19.4863533863; RMSE 44.7360667804; R2 0.0003793701 |
| xgboost | 1,254,518 | PR-AUC 0.2020756400; ROC-AUC 0.6176766805; Brier 0.2084977211; MAE 19.4080017676; RMSE 44.6565480251; R2 0.0039298808 |

These are 2016-2022 development OOF diagnostics, not final test results. No champion was selected from them.

## Information and temporal boundaries

- Population is inbound `DEST=ATL`; prediction cutoff is `CRS_DEP_TIME - 2 hours`.
- HPO and OOF use 2016-2022 only. No row-level 2023 HPO access, 2023 selection, ensemble fitting, or row-level 2024 access occurred.
- Arrival inputs exclude Weather, predicted Departure, DEP_DELAY, realized operations, and Chain predictors.
- ARR-B remains disabled and Chain ML remains blocked pending new point-in-time evidence (`KEEP_SAFE=[]`).
- External point-in-time Weather remains `AUDIT_REQUIRED`; no DEP-A/DEP-B Weather experiment ran in Week 5.

## Limitations

- All reported model metrics are 2016-2022 development OOF diagnostics, not final test results.
- Weighted Ensemble, 2023 selection, SHAP, ARR ablation, and conditional DEP Weather ablation remain Week-6 work.
- ARR-B remains disabled because E006 has KEEP_SAFE=[].
- DEP-A/DEP-B remains blocked until point-in-time Weather provenance passes audit.

## Week-6 readiness

Week 5 is complete and the evidence is ready for the controlled Week-6 stage. Weighted Ensemble, 2023 comparison/selection, SHAP, ARR ablation, and conditional DEP Weather ablation remain not started. This report does not start Week 6 or open 2023/2024 row-level data.
