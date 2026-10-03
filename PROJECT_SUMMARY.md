# Aeolus Gate Optimization — Tóm tắt toàn bộ dự án

> Cập nhật theo trạng thái artifact trong repository đến ngày 2026-09-20. Đây là bản tổng hợp hiện trạng, dữ liệu, pipeline, mô hình và kết quả tốt nhất đang có; không phải kết quả đánh giá holdout cuối cùng trên 2024.

## 1. Kết luận nhanh

- Dự án đang theo kiến trúc **Predict → Simulate → Optimize → Evaluate**, với ATL là hub thí nghiệm.
- Nhánh chính đã hoàn tất đến **Week 5 / Core Arrival ML**. Week 4 baseline, Week 5 HPO và tuned OOF đều có artifact hợp lệ.
- Bài toán lõi là dự đoán **Arrival Delay cho chuyến inbound `DEST=ATL`** tại thời điểm `CRS_DEP_TIME - 2 giờ`:
  - Classification: `y_arr_cls = 1[ARR_DELAY >= 15]`.
  - Regression: `y_arr_reg = ARR_DELAY` có dấu, tính theo phút; không lấy trị tuyệt đối, không clip và không impute target.
- Tập đặc trưng Core Arrival hiện hành là **Schedule + Calendar + Carrier + Route**, không dùng Weather, Departure delay, actual-operation fields, identifiers hoặc Chain features chưa được chứng minh point-in-time safe.
- **Week 5 HPO đã PASS**: 6 study độc lập (RF/HGB/XGBoost × classification/regression), mỗi study 10 trial, không dùng row-level 2023/2024.
- Kết quả tốt nhất theo tiêu chí HPO trên 4 rolling folds:
  - Classification: **XGBoost, mean PR-AUC = 0.1956**.
  - Regression: **XGBoost, mean MAE = 19.190 phút**.
- Kết quả OOF phát triển 2016–2022 sau tuned params cho thấy XGBoost có regression MAE **19.408 phút**, nhưng `R² = 0.0039`; classification PR-AUC pooled là **0.2021**.
- Fold 4 refactor năm 2022 cho thấy HGB có overall MAE thấp nhất trong leaderboard hiện tại (**20.37 phút**), nhưng tất cả point regressors đều cảnh báo **prediction collapse ở delay nặng**. Đây chưa phải mô hình đủ an toàn để khẳng định dự đoán tốt tail.
- Holdout 2024 vẫn **sealed**; chưa có đánh giá cuối cùng được phép dùng để retune/chọn model.

## 2. Kiến trúc và các quyết định khóa

### Hai task

| Task | Population | Target | Weather | Vai trò |
|---|---|---|---|---|
| Core Arrival | inbound `DEST=ATL` | classification + signed regression của `ARR_DELAY` | Không được dùng | Nhánh duy nhất được feed vào simulation/optimization |
| Auxiliary Departure | outbound `ORIGIN=ATL` | classification `y_dep_cls = 1[DEP_DELAY >= 15]` | Chỉ có thể dùng external point-in-time Weather sau audit | Nghiên cứu phụ, không feed optimizer |

### Temporal protocol

| Fold | Train | Validation |
|---|---|---|
| fold 1 | 2016–2018 | 2019 |
| fold 2 | 2016–2019 | 2020 |
| fold 3 | 2016–2020 | 2021 |
| fold 4 | 2016–2021 | 2022 |

2016–2022 là rolling development; 2023 dùng cho model-selection/controlled development theo protocol; 2024 là final end-to-end holdout sau khi freeze toàn hệ thống. Random split bị cấm. Preprocessor và mọi thống kê fit chỉ trên train side của từng fold.

### Flight Chain và Weather

- Raw Flight Chain `.pt`: `FINAL_NO_GO`, read-only, không được dùng cho core/ablation.
- Reconstructed `schedule_chain_v1`: `FULL_DATA_PASS` / `GO_FOR_ABLATION`, chỉ là schedule/service-number context, không phải physical aircraft identity và bị disable mặc định.
- Audit E006 không tìm thấy schedule publication/version/snapshot evidence tại T-2h: `KEEP_SAFE = []`; 7 feature `REVIEW_REQUIRED`, 11 feature `BLOCKED_UNTIL_PROVEN`, 4 field chỉ được làm identifier. Chain ML branch: `BLOCKED_PENDING_NEW_EVIDENCE`.
- Sáu raw Weather field của Aeolus (`O_TEMP`, `O_PRCP`, `O_WSPD`, `D_TEMP`, `D_PRCP`, `D_WSPD`) giữ nguyên trong storage nhưng bị `DROP_FROM_PREDICTORS` vì không chứng minh được availability/issue/publication time.
- External Weather chưa có provider, chưa download/join/train; contract W1–W15 mới là template và đang `AUDIT_REQUIRED`, `enabled=false`.

## 3. Dataset từ raw đến preprocessed

### 3.1. Raw Tabular

Nguồn chính là 9 CSV `data/raw/tabular/<year>/flight_with_weather_<year>.csv`, năm 2016–2024. Raw được coi là immutable; không rewrite, rename, move, normalize hoặc ghi output ngược vào `data/raw`.

| Năm | Số dòng | Kích thước CSV | Tỷ lệ `ARR_DELAY >= 15` |
|---:|---:|---:|---:|
| 2016 | 5,537,987 | 1.54 GB | 17.41% |
| 2017 | 5,575,872 | 1.55 GB | 18.45% |
| 2018 | 6,986,842 | 1.94 GB | 19.09% |
| 2019 | 7,161,827 | 1.99 GB | 19.11% |
| 2020 | 4,312,091 | 1.20 GB | 9.73% |
| 2021 | 5,755,666 | 1.60 GB | 17.08% |
| 2022 | 6,413,416 | 1.78 GB | 20.99% |
| 2023 | 6,645,461 | 1.85 GB | 20.54% |
| 2024 | 6,284,841 | 1.75 GB | 20.81% |
| **Tổng** | **54,674,003** | **15.20 GB** | — |

Schema audit cho thấy cả 9 năm đều có 34 canonical fields, `ARR_DELAY` không thiếu, không có duplicate row theo audit streaming, và min/max date đúng theo năm. Weather có một lượng nhỏ missing value; missingness không biến Weather thành predictor hợp lệ.

Các nhóm field chính:

- Schedule: `FL_DATE`, `OP_CARRIER`, `OP_CARRIER_FL_NUM`, `ORIGIN`, `DEST`, `CRS_DEP_TIME`, `CRS_ARR_TIME`, `CRS_ELAPSED_TIME`.
- Actual/outcome: `DEP_TIME`, `DEP_DELAY`, `WHEELS_OFF`, `WHEELS_ON`, `TAXI_IN`, `TAXI_OUT`, `ARR_TIME`, `ARR_DELAY`, `ACTUAL_ELAPSED_TIME`, `AIR_TIME`.
- Calendar: `MONTH`, `DAY_OF_MONTH`, `DAY_OF_WEEK`.
- Airport/index/coordinate: `ORIGIN_INDEX`, `DEST_INDEX`, `O_LATITUDE`, `O_LONGITUDE`, `D_LATITUDE`, `D_LONGITUDE`.
- Raw Aeolus Weather: 6 field `O_*`/`D_*` nói trên.
- `FLIGHTS` vẫn chưa có semantics/availability evidence đủ để đưa vào `X`.

### 3.2. Canonical và processed Tabular

Pipeline materialization được mô tả trong `artifacts/manifests/processed_data_manifest_v1.json`:

1. Đọc CSV theo năm bằng batch/column projection.
2. Giữ `source_year`, `source_row_number` và tạo `flight_key_v1` cho traceability; các field actual/target bị loại khỏi cấu phần key.
3. Ghi partition Parquet ra `data/processed/tabular_by_year/year=<YYYY>/` với cùng số dòng như raw.
4. Tạo hai flow theo ATL:
   - `data/processed/inbound_atl/year=<YYYY>/`: Core Arrival, lọc `DEST=ATL`.
   - `data/processed/outbound_atl/year=<YYYY>/`: Auxiliary Departure/simulation, lọc `ORIGIN=ATL`.

| Năm | Vai trò | Tabular | Inbound ATL | Outbound ATL |
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
| **Tổng** | — | **54,674,003** | **3,022,433** | **3,022,670** |

`data/processed.rar` cũng hiện diện như archive lớn, nhưng các partition Parquet và manifest là nguồn tham chiếu logic của pipeline; không có một file monolithic bắt buộc.

### 3.3. Core Arrival feature preprocessing

Manifest V1 (`feature_manifest_arrival_v1.json`) định nghĩa 11 predictor cuối:

```text
CRS_ELAPSED_TIME
calendar_year
calendar_month
calendar_day_of_month
calendar_day_of_week
is_weekend
scheduled_departure_hour
scheduled_departure_minute
OP_CARRIER
ORIGIN
OP_CARRIER_FL_NUM
```

`FL_DATE` và `CRS_DEP_TIME` là source-only inputs để derive calendar/departure-clock/cutoff; chúng không đi vào `X` dưới dạng raw. `DEST` và các ATL constants bị drop; `CRS_ARR_TIME` không được dùng để suy ra overnight/duration vì canonical audit chưa chứng minh rollover semantics. `ORIGIN_INDEX`, coordinates và `FLIGHTS` bị giữ ở trạng thái review/blocked.

Preprocessor theo family:

- Linear: median imputer + missing indicators + `StandardScaler`; categorical one-hot `handle_unknown=ignore`; flight number dùng training-fold frequency map.
- Tree/boosting: median imputer + missing indicators, không scaling; categorical `OrdinalEncoder(unknown=-1)`; flight number frequency map, unknown fallback 0.
- Tất cả fit riêng trên train rows của fold; không target encoding.

Nhánh refactor V2 (`feature_manifest_arrival_v2.json`, code `src/features/refactored_features.py`) loại `calendar_year` vì PSI được báo cáo là 8.75 và còn 10 feature chu kỳ/schedule. Code có thể nhận một `chain_map` để thêm trạng thái `has_prior_flight`/missing-indicator, nhưng E006 không phê duyệt feature Chain nào nên đây không phải feature set production-safe hiện tại. File manifest V2 hiện có ký tự `\n` literal sau JSON nên `ConvertFrom-Json` không parse được; cần sửa artifact trước khi dùng làm manifest máy đọc.

### 3.4. Raw Flight Chain và reconstructed processed Chain

- Raw: 27 `.pt` (3 file/năm × 2016–2024), tổng khoảng 13.75 GB. Tên `train/val/test` chỉ là nhãn filename của source, không thay thế temporal split của thesis.
- Reconstructed: `data/processed/flight_chain_reconstructed_v1/`, gồm `chain_groups`, `chain_members`, `inbound_target_map`, partition 2016–2023.
- Reconstruction dùng group `(source_year, FL_DATE, OP_CARRIER, OP_CARRIER_FL_NUM)`, order theo `CRS_DEP_TIME` với tie-breaker `ORIGIN`, `DEST`, `flight_key`.
- Manifest production: 48,389,162/48,389,162 rows mapped, coverage 100%, 38,004,376 chains, 2,713,268 inbound ATL targets, output khoảng 4.06 GB. Có 19,264 chains dài hơn context metadata 6; membership đầy đủ vẫn được giữ.
- Không có reconstructed partition năm 2024 và không mở raw `.pt` khi chạy reconstruction. Artifact này chỉ sẵn sàng cho ablation sau khi feature-level availability được chứng minh lại.

## 4. Mô hình và kết quả hiện tại

### 4.1. Week 4 baseline — pooled OOF 2016–2022

Các phương pháp baseline dùng cùng folds, cùng row/target parity và cùng feature manifest V1. Classification dùng probability metrics; regression giữ signed `ARR_DELAY`.

| Model | ROC-AUC | PR-AUC | Brier | Recall@0.5 | F1@0.5 | Reg MAE (min) | RMSE | R² |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Linear/Ridge | 0.6134 | 0.1868 | 0.2371 | 0.5609 | 0.2653 | 20.1336 | 44.7961 | -0.0023 |
| Random Forest | 0.6087 | 0.1967 | 0.1978 | 0.3685 | 0.2548 | 19.5949 | 44.8189 | -0.0033 |
| HistGradientBoosting | 0.6152 | 0.1998 | 0.2054 | 0.4131 | 0.2616 | 19.6102 | 44.9519 | -0.0093 |
| XGBoost | **0.6186** | **0.2035** | 0.2059 | 0.4252 | **0.2660** | **19.4816** | **44.7415** | **0.0001** |

Đây là development OOF, không phải final holdout. XGBoost baseline là lựa chọn tốt nhất trong bộ baseline theo nhiều metric pooled nhưng signal hồi quy rất yếu.

### 4.2. Week 5 HPO — 6 fixed-budget studies

Protocol `week5_hpo_protocol_v1_1`: 10 trial/study, TPE sampler, seed 202601, `n_jobs=1`, no early stopping, objective classification là mean PR-AUC macro trên 4 folds và regression là mean MAE macro trên 4 folds. 2023/2024, Weather, Departure prediction và Chain đều bị guard chặn.

| Method | Classification best mean PR-AUC | Best classification params tóm tắt | Regression best mean MAE (min) | Best regression params tóm tắt |
|---|---:|---|---:|---|
| Random Forest | 0.188565 | 160 trees, depth 6, `log2`, `max_samples=0.6`, leaf 40, split 20 | 19.259711 | 192 trees, depth 10, `sqrt`, `max_samples=0.6`, leaf 30, split 20 |
| HistGradientBoosting | 0.192061 | 150 iter, depth 6, leaf nodes 39, lr 0.0559, `max_features=0.6` | 19.258190 | 250 iter, depth 4, leaf nodes 55, lr 0.0795, `max_features=0.6` |
| **XGBoost** | **0.195616** | 150 trees, depth 6, lr 0.0323, min child 7, subsample 0.9, colsample 0.6, alpha 4.5 | **19.190112** | 200 trees, depth 4, lr 0.0625, min child 6, subsample 0.7, colsample 0.6, alpha 1.0 |

Week 5 closeout ghi nhận: 6/6 study complete, `week5_final_status=PASS`, `ready_for_week_6=true`, weighted ensemble chưa bắt đầu. RF có provenance amendment phi thống kê vì cleanup-success return value lịch sử không được persist; statistical protocol và kết quả không bị thay đổi. HGB classification được adopt từ completed study sau lỗi materialization SQLite; không rerun/không thay đổi model result. XGBoost tuned OOF có một recovery do Week-4 ExperimentSpec cũ không nhận `method_id=xgboost`; recovery được version hóa và không rerun HPO.

### 4.3. Tuned development OOF 2016–2022

Đây là OOF từ frozen HPO params, vẫn chỉ là development diagnostic và chưa chọn champion/calibrator.

| Method | PR-AUC | ROC-AUC | Brier | Recall@0.5 | F1@0.5 | Reg MAE (min) | RMSE | R² |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Random Forest tuned | 0.1877 | 0.6100 | 0.2169 | 0.4148 | 0.2537 | 19.4625 | 44.6937 | 0.0023 |
| HistGradientBoosting tuned | **0.2022** | 0.6159 | 0.2064 | 0.4216 | 0.2626 | 19.4864 | 44.7361 | 0.0004 |
| XGBoost tuned | 0.2021 | **0.6177** | 0.2085 | **0.4282** | **0.2652** | **19.4080** | **44.6565** | **0.0039** |

Diễn giải: XGBoost tuned hiện là lựa chọn mạnh nhất cho regression và ROC-AUC/recall; HGB tuned nhỉnh hơn rất ít về pooled PR-AUC. Chênh lệch nhỏ và R² gần 0, nên chưa có bằng chứng rằng point regression dự đoán tốt phần tail.

### 4.4. Refactored robustness / Fold 4 năm 2022

Artifact mới nhất `phase4_model_leaderboard.json` đánh giá 40,000 mẫu validation Fold 4 sau refactor/loss experiments. Tất cả model đều có `Collapse_Warning=YES` với ngưỡng shrinkage severe-delay `< 0.30`.

| Model | Overall MAE | RMSE | Severe MAE (`>=60m`) | Mean severe prediction | Shrinkage |
|---|---:|---:|---:|---:|---:|
| **HGB Absolute + Weighted** | **20.37** | 52.19 | 161.41 | -7.90 | -0.0515 |
| XGBoost Huber + Weighted | 20.42 | 51.80 | 159.39 | -5.89 | -0.0383 |
| XGBoost baseline MSE | 23.25 | 51.12 | 148.82 | 4.70 | 0.0307 |
| XGBoost Quantile q=0.75 | 23.56 | **50.75** | **146.19** | 7.31 | 0.0476 |
| Hurdle hard gate p>=0.20 | 32.14 | 53.11 | **133.26** | 20.24 | 0.1319 |

Phase B mở rộng cho thấy trade-off rõ hơn: quantile q=0.95 đạt severe MAE **101.74** và shrinkage **0.3885**, nhưng overall MAE tăng lên **53.63**; đây là tail-oriented diagnostic, không thể gọi là model point prediction tốt nhất. Decision Gate A ghi nhận max ML skill score hồi quy khoảng **-6.07** so với carrier-hour baseline và chuyển trọng tâm sang probability/interval/quantile output cho CP-SAT.

### 4.5. Kết quả tốt nhất nên dùng để tham chiếu

Nếu chỉ cần một model reference hiện tại cho Core Arrival:

- **Classification reference:** XGBoost tuned, vì đạt HPO macro PR-AUC cao nhất (0.1956), tuned OOF ROC-AUC cao nhất (0.6177) và recall@0.5 cao nhất trong ba tuned method (0.4282).
- **Regression point reference:** XGBoost tuned, vì đạt HPO macro MAE thấp nhất (19.190) và tuned OOF MAE thấp nhất (19.408).
- **Overall MAE benchmark riêng của Fold 4 refactor:** HGB Absolute + Weighted (20.37 phút).
- **Tail-risk reference:** quantile/hurdle diagnostics cải thiện severe MAE nhưng đánh đổi mạnh overall MAE; chưa có model nào vượt cảnh báo collapse theo ngưỡng 0.30 trong leaderboard chính.

Các con số trên không được trộn thành một leaderboard duy nhất vì khác protocol, population sample, aggregation và objective.

## 5. Kiểm soát leakage, chất lượng và test

- Leakage rules fail closed đối với unknown task/column, actual fields, target/outcome, raw Weather, identifiers, constant ATL fields và conditional fields chưa được review.
- HPO guard cấm 2023/2024, random split, cross-fold preprocessing fit, feature-set/target/cutoff/threshold tuning ngoài protocol.
- Row/target parity giữa các model trong cùng fold đã PASS; OOF artifact chứa `flight_key`, target và prediction để trace.
- Weather contract kiểm tra availability-first (`publication_time`/`available_time` trước `valid_time`), timezone-aware UTC, deterministic tie-break, duplicate rejection và DEP-A/DEP-B row parity.
- Chain audit dùng không model result, không 2023 performance và không row-level 2024; không tạo `reconstructed_chain_features_v1`.
- Repository có bộ test bao phủ data contract, preprocessing, temporal split, leakage, HPO protocol/runner, recovery/provenance và refactored pipeline. Fresh verification bằng `python -m pytest -q --basetemp .pytest_tmp_summary_verification`: **399 passed, 2 warnings** trong 26.87 giây. Hai warning là giới hạn phát hiện CPU và cảnh báo prediction-collapse được test cố ý phát ra.

## 6. Trạng thái những phần chưa hoàn thành

1. **Final holdout 2024:** chưa mở cho model selection/retune; final end-to-end evaluation chưa được báo cáo trong repository.
2. **Weighted Ensemble:** nằm trong core methods nhưng Week 6 chưa bắt đầu, chưa có kết quả ensemble.
3. **Auxiliary Departure + external Weather:** provider `TBD`, chưa có data/join/model; chỉ chạy sau W1–W15 PASS.
4. **Chain ML ablation:** dataset reconstruction PASS ở mức artifact, nhưng feature-level availability không PASS; cần evidence snapshot/publication mới trước khi đưa feature vào `X`.
5. **Simulation/optimization/robustness end-to-end:** config và boundary có sẵn, nhưng chưa có evidence tương ứng để khẳng định giảm real flight delay. Gate plans/Aircraft Turns trong tương lai chỉ là synthetic simulation.
6. **V2 manifest integrity:** sửa ký tự `\n` literal cuối `artifacts/manifests/feature_manifest_arrival_v2.json` trước khi dùng làm input máy đọc.

## 7. Cây file quan trọng và nguồn bằng chứng

- Protocol/kiến trúc: `README.md`, `project_structure.md`, `configs/base.yaml`, `docs/decisions/decision_registry.md`, `docs/decisions/decision_dual_prediction_architecture_v4.md`.
- Dataset/schema: `docs/dataset_audit/data_inventory.md`, `data_dictionary_v1.md`, `canonical_schema_v1.md`, `schema_compatibility_matrix.md`, `artifacts/manifests/schema_audit/schema_2016.json` … `schema_2024.json`.
- Processed data: `artifacts/manifests/processed_data_manifest_v1.json`, `artifacts/manifests/temporal_folds_manifest.json`, `artifacts/manifests/split_manifest.json`.
- Feature/preprocessing: `artifacts/manifests/feature_manifest_arrival_v1.json`, `feature_pipeline_registry_arrival_v1.json`, `src/features/tabular_features.py`, `src/data/preprocessing.py`, `src/features/refactored_features.py`, `src/data/refactored_preprocessing.py`.
- Baseline/tuned OOF: `artifacts/manifests/week4_core_arrival_baselines_summary_v1.json`, `arrival_*_rolling_run_v1.json`, `arrival_*_tuned_rolling_run_v1_1.json`.
- HPO: `configs/week5_hpo_v1_1.yaml`, `artifacts/manifests/week5_core_arrival_xgboost_optuna_summary_v1.json`, sáu `week5_hpo_protocol_v1_1__*_result_v1.json`, các amendment/recovery manifest Week 5.
- Robustness: `configs/week6_robust_models.yaml`, `artifacts/manifests/phase4_model_leaderboard.json`, `refactored_models_evaluation_v2.json`, `phase_b_ablation_matrix.json`, `phase_b_pareto_frontier.json`, `phase_a_benchmark_report.json`.
- Dataset audit boundaries: `docs/dataset_audit/leakage_audit.md`, `weather_timing_audit.md`, `weather_point_in_time_contract_v1.md`, `reconstructed_chain_feature_availability_audit_v1.md`.

## 8. Một câu chốt

Pipeline Core Arrival đã có dữ liệu và HPO/OOf đủ để bước sang Week 6, với XGBoost tuned là reference mạnh nhất hiện tại cho cả classification và signed regression theo tiêu chí đã khóa; tuy nhiên regression point prediction vẫn có signal thấp và collapse ở delay nặng, nên mọi kết luận vận hành phải chờ calibration/interval-tail strategy, ensemble nếu được triển khai, và cuối cùng là final holdout 2024 sau freeze.
