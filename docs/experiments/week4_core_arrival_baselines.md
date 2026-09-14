# Week 4 — Core Arrival rolling baseline evidence

This is descriptive consolidation of three completed locked baseline runs. It reads only production manifests and OOF artifacts; it does not retrain, tune, calibrate, select a champion, or access row-level 2023/2024 data.

- Target: `y_arr_cls = 1[ARR_DELAY >= 15]`; signed `ARR_DELAY` regression.
- Population/cutoff: inbound `DEST=ATL`; `CRS_DEP_TIME - 2h`.
- Excluded: Weather, departure target/prediction, actual operations, Chain, and identifiers as predictors.
- Threshold: fixed `0.5`; calibration is ten fixed-width bins with no post-hoc calibrator.

## Common folds and row parity

| Method | Fold | Validation year | Train rows | Validation rows | Positive prevalence | Missing target drops | Trace parity |
| --- | --- | --- | --- | --- | --- | --- | --- |
| linear | fold_1 | 2019 | 1,126,009 | 391,075 | 0.1418 | 0 | PASS |
| linear | fold_2 | 2020 | 1,517,084 | 242,121 | 0.0810 | 0 | PASS |
| linear | fold_3 | 2021 | 1,759,205 | 309,621 | 0.1130 | 0 | PASS |
| linear | fold_4 | 2022 | 2,068,826 | 311,701 | 0.1613 | 0 | PASS |
| random_forest | fold_1 | 2019 | 1,126,009 | 391,075 | 0.1418 | 0 | PASS |
| random_forest | fold_2 | 2020 | 1,517,084 | 242,121 | 0.0810 | 0 | PASS |
| random_forest | fold_3 | 2021 | 1,759,205 | 309,621 | 0.1130 | 0 | PASS |
| random_forest | fold_4 | 2022 | 2,068,826 | 311,701 | 0.1613 | 0 | PASS |
| hist_gradient_boosting | fold_1 | 2019 | 1,126,009 | 391,075 | 0.1418 | 0 | PASS |
| hist_gradient_boosting | fold_2 | 2020 | 1,517,084 | 242,121 | 0.0810 | 0 | PASS |
| hist_gradient_boosting | fold_3 | 2021 | 1,759,205 | 309,621 | 0.1130 | 0 | PASS |
| hist_gradient_boosting | fold_4 | 2022 | 2,068,826 | 311,701 | 0.1613 | 0 | PASS |

Exact `flight_key`, classification-label, and signed-regression-label parity passed within every fold. The full ten-bin diagnostics are in the machine-readable summary manifest.

## Classification metrics by fold

| Method | Year | ROC-AUC | PR-AUC | Recall@0.5 | F1@0.5 | Brier | ECE (10 bins) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| linear | 2019 | 0.6369 | 0.2171 | 0.7464 | 0.2909 | 0.2756 | 0.3911 |
| linear | 2020 | 0.5623 | 0.1020 | 0.5779 | 0.1626 | 0.2614 | 0.4205 |
| linear | 2021 | 0.6274 | 0.1795 | 0.4233 | 0.2522 | 0.2018 | 0.3152 |
| linear | 2022 | 0.6395 | 0.2583 | 0.4455 | 0.3277 | 0.2049 | 0.2681 |
| random_forest | 2019 | 0.6366 | 0.2267 | 0.5446 | 0.2970 | 0.2314 | 0.3296 |
| random_forest | 2020 | 0.5797 | 0.1029 | 0.4002 | 0.1653 | 0.2227 | 0.3747 |
| random_forest | 2021 | 0.5927 | 0.1461 | 0.0564 | 0.0849 | 0.1408 | 0.1939 |
| random_forest | 2022 | 0.6473 | 0.2720 | 0.3789 | 0.3205 | 0.1928 | 0.2458 |
| hist_gradient_boosting | 2019 | 0.6367 | 0.2332 | 0.5833 | 0.2970 | 0.2399 | 0.3395 |
| hist_gradient_boosting | 2020 | 0.5693 | 0.1016 | 0.4317 | 0.1636 | 0.2295 | 0.3794 |
| hist_gradient_boosting | 2021 | 0.6015 | 0.1510 | 0.0911 | 0.1212 | 0.1474 | 0.2100 |
| hist_gradient_boosting | 2022 | 0.6520 | 0.2747 | 0.4421 | 0.3358 | 0.2010 | 0.2609 |

## Regression metrics by fold

| Method | Year | MAE | RMSE | R² |
| --- | --- | --- | --- | --- |
| linear | 2019 | 22.2920 | 45.3233 | 0.0035 |
| linear | 2020 | 19.0305 | 37.4825 | -0.0552 |
| linear | 2021 | 17.9303 | 42.0232 | 0.0031 |
| linear | 2022 | 20.4711 | 51.5135 | -0.0044 |
| random_forest | 2019 | 21.6539 | 45.3398 | 0.0028 |
| random_forest | 2020 | 18.2189 | 37.3445 | -0.0475 |
| random_forest | 2021 | 17.1192 | 42.3299 | -0.0115 |
| random_forest | 2022 | 20.5394 | 51.4035 | -0.0001 |
| hist_gradient_boosting | 2019 | 21.8268 | 45.7012 | -0.0132 |
| hist_gradient_boosting | 2020 | 18.2110 | 37.6008 | -0.0619 |
| hist_gradient_boosting | 2021 | 17.1253 | 42.3218 | -0.0111 |
| hist_gradient_boosting | 2022 | 20.3842 | 51.3308 | 0.0027 |

## Aggregate pooled OOF diagnostics (2019–2022)

| Method | OOF rows | ROC-AUC | PR-AUC | Recall@0.5 | F1@0.5 | Brier | ECE (10 bins) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| linear | 1254518 | 0.6134 | 0.1868 | 0.5609 | 0.2653 | 0.2371 | 0.3475 |
| random_forest | 1254518 | 0.6087 | 0.1967 | 0.3685 | 0.2548 | 0.1978 | 0.2840 |
| hist_gradient_boosting | 1254518 | 0.6152 | 0.1998 | 0.4131 | 0.2616 | 0.2054 | 0.2957 |

| Method | MAE | RMSE | R² |
| --- | --- | --- | --- |
| linear | 20.1336 | 44.7961 | -0.0023 |
| random_forest | 19.5949 | 44.8189 | -0.0033 |
| hist_gradient_boosting | 19.6102 | 44.9519 | -0.0093 |

Values vary by year and method. This report intentionally makes no final model-selection or champion claim; accuracy is not a primary metric.

## Resource record

| Method | Fit seconds | Predict seconds | Total seconds | Max traced Python MiB | Max post-fold RSS MiB | OOF size MiB |
| --- | --- | --- | --- | --- | --- | --- |
| linear | 489.06 | 3.36 | 566.61 | 844.8 | 1778.8 | 62.9 |
| random_forest | 1219.69 | 18.34 | 1311.01 | 712.4 | 1810.0 | 62.9 |
| hist_gradient_boosting | 104.67 | 9.67 | 184.83 | 712.4 | 1833.1 | 62.7 |

`tracemalloc` records Python-allocation peaks, not portable exact RSS peaks. Post-fold RSS was separately observed using `psutil` and is not estimator-only peak memory.

## Source evidence

- `artifacts/manifests/arrival_linear_rolling_run_v1.json`
- `artifacts/manifests/arrival_random_forest_rolling_run_v1.json`
- `artifacts/manifests/arrival_hist_gradient_boosting_rolling_run_v1.json`
- Per-fold OOF Parquet paths in `artifacts/manifests/week4_core_arrival_baselines_summary_v1.json`.
