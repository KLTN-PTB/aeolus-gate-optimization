# Day 3 — LightGBM native categorical result

Ngày thực hiện: 2026-09-21  
Artifact chính: `artifacts/manifests/phase_a_benchmark_lightgbm_v1_1_per_fold.json`  
Artifact Fold 4: `artifacts/manifests/phase_a_benchmark_lightgbm_v1_1_fold4.json`

## Protocol

- Feature set: V1.1, manifest hash được ghi trong artifact.
- Model: LightGBM `LGBMRegressor`, native categorical.
- Objective: `regression_l1`; metric: `mae`.
- Native categorical: `OP_CARRIER`, `ORIGIN`, `OP_CARRIER_FL_NUM`.
- Params: `num_leaves=31`, `learning_rate=0.05`, `n_estimators=500`, `min_data_in_leaf=20`, `n_jobs=1`, không HPO.
- Seeds: `[42, 43, 44, 45, 46]`.
- Sampling: 25K train mỗi năm, 25K validation; rolling folds 2019–2022.
- Không dùng actual operation, weather, chain, DEST; row-level 2023/2024 flags đều false.

## Comparison to XGBoost B2

| Fold / year | B2 skill | LightGBM skill | Delta LGBM − B2 | B2 MAE | LGBM MAE |
|---|---:|---:|---:|---:|---:|
| Fold 1 / 2019 | +0.4740% | −0.3169% | −0.7909pp | 18.1019 | 18.2455 |
| Fold 2 / 2020 | +1.2444% | −1.3040% | −2.5484pp | 13.4858 | 13.8338 |
| Fold 3 / 2021 | +0.1698% | −0.9959% | −1.1658pp | 15.8161 | 16.0008 |
| Fold 4 / 2022 | −0.2519% | −0.8292% | −0.5773pp | 19.8864 | 20.0005 |
| Macro 4-fold | +0.4091% | −0.8615% | −1.2706pp | — | — |

LightGBM không thắng B2 ở Fold 4 hoặc macro. Severe MAE Fold 4 là `162.9570`, shrinkage `−0.0611`; gần như cùng tail profile với B2 (`163.0096`, `−0.0614`). Vì vậy chênh lệch chủ yếu nằm ở mean point regression, không phải một tail outlier mới.

Trend 2021→2022 của LightGBM tăng từ `−0.9959%` lên `−0.8292%` (+0.1667pp), tốt hơn trend B2 nhưng vẫn dưới baseline ở cả hai năm. Đây là cải thiện temporal slope, không phải generalization pass.

## Gate 3.3

**FAIL — XGBoost B2 vẫn là reference.** LightGBM default native categorical không phải model class thắng cuộc theo Fold 4 hoặc macro. Không chạy LightGBM+V1.2 theo điều kiện “chỉ chạy thêm nếu V1.1 tích cực”; không cập nhật Decision Registry từ kết quả này.

Khuyến nghị: nếu tiếp tục Day 4, ưu tiên focused HPO trên XGBoost B2 hoặc interval/quantile work. LightGBM chỉ nên quay lại như candidate HPO có regularization/leaf-size tuning, không dùng default result này làm model chính.

