# Day 1 — Feature Gap Closure

Ngày thực hiện: 2026-09-20 UTC  
Dự án: Aeolus Gate Optimization — Core Arrival, inbound `DEST=ATL`, cutoff
`CRS_DEP_TIME - 2 hours`

## 1. Scope and data guard

- Row-level benchmark chỉ đọc train 2016–2021 và validation 2022.
- Không mở hoặc dùng raw Flight Chain `.pt`, Weather, actual-operation
  fields, 2023 cho tuning/feature engineering, hoặc bất kỳ dữ liệu 2024 nào.
- Manifest V1 không bị ghi đè. SHA-256 sau thay đổi:
  `CB352A56D194E9F39EE9477FDBC5DA7929BA03B5BA089100CBD88B01DEC09E85`.
- Các report mới có timestamp và SHA-256 của parent manifest và HPO result
  manifest.

## 2. Xác nhận Phase A gốc

### Baseline

`NaiveDelayBaselines._extract_carrier_and_hour()` trước thay đổi đi vào nhánh:

```python
elif "scheduled_departure_hour" in X.columns and "CRS_ELAPSED_TIME" in X.columns:
    elapsed_hours = CRS_ELAPSED_TIME // 60
    hour = (scheduled_departure_hour + elapsed_hours) % 24
```

Median được tính từ train side, với fallback:

```text
(carrier, hour) median → carrier median → global median
```

Phase A gốc dùng XGBoost objective `reg:squarederror` (MSE), không phải
`reg:absoluteerror`, với seeds `[42, 43, 44, 45, 46]`.

Tại seed 42:

```text
carrier-hour baseline MAE = 19.71344
XGBoost MAE                = 20.9126706
skill score                = -6.083315%
```

Mean XGBoost skill score gốc là `-6.073035%`.

Nguồn: `scripts/run_phase_a_benchmark.py` và
`artifacts/manifests/phase_a_benchmark_report.json`.

## 3. Thay đổi đã triển khai

### V1.1 exact scheduled-arrival clock

Đã thêm:

- `scheduled_arrival_hour`
- `scheduled_arrival_minute`

Nguồn duy nhất là `CRS_ARR_TIME`; raw `CRS_ARR_TIME` không đi vào ma trận X.
Parser hỗ trợ canonical timestamp của Aeolus và HHMM fixture, kiểm tra:

- hour trong `[0, 23]`;
- minute trong `[0, 59]`;
- không NaN/negative;
- không suy luận rollover, duration, hoặc overnight feature.

Đường benchmark V1.1 dùng 13 predictor: 11 predictor V1 + hai cột schedule
arrival mới. Pipeline V2 cũng expose hai cột exact này nhưng vẫn giữ contract
không có `calendar_year`; đường benchmark V1.1 được dùng để khớp với feature
contract và tuned HPO Week 5 của V1.

### V1.2 target encoding

Đã thêm helper stateless:

```python
compute_carrier_arrhour_median(
    train_df, apply_df, k=30, smoothing=True
) -> (median_values, cell_counts)
```

Feature chính:

```text
carrier_arrhour_train_median
carrier_arrhour_train_count
```

Mapping chỉ fit trên train side của seed/fold hiện tại và được áp dụng riêng
cho train/validation của chính fold đó. Target của `apply_df` bị bỏ qua.
Fallback:

```text
carrier × scheduled_arrival_hour → carrier → global
```

Smoothing dùng:

```text
(n_cell × median_cell + k × median_carrier) / (n_cell + k), k = 30
```

Unit test xác nhận feature không đổi khi hoán vị/thay đổi target của validation
rows và không có NaN sau fallback.

## 4. Benchmark comparison

Tất cả kết quả dưới đây là XGBoost tuned params từ
`week5_hpo_protocol_v1_1__xgboost_regression_result_v1.json`, nhưng giữ nguyên
objective Phase A là `reg:squarederror`. Mỗi report dùng 5 seed và Fold 4:
train 2016–2021, validation 2022.

| Config | Feature set | Mean skill score | Per-seed skill score `[42,43,44,45,46]` |
|---|---|---:|---|
| Phase A gốc | V2, default Phase A model | `-6.073035%` | `[-6.083315, -5.827691, -5.957063, -6.139516, -6.357589]` |
| V1 tuned control | V1, không exact arrival | `-3.225318%` | `[-3.242357, -3.228432, -3.220302, -2.979356, -3.456145]` |
| V1.1 | V1 + exact scheduled arrival | `-3.335706%` | `[-3.147095, -3.194464, -3.628830, -3.177547, -3.530592]` |
| V1.2a | V1.1 + raw target encoding | `-3.629773%` | `[-3.505390, -3.242005, -3.745524, -3.739467, -3.916480]` |
| V1.2b | V1.1 + smoothing `k=30` | `-3.518021%` | `[-3.268604, -3.344928, -3.576196, -3.732747, -3.667629]` |

Artifact reports:

- `artifacts/manifests/phase_a_benchmark_report_v1_1.json`
- `artifacts/manifests/phase_a_benchmark_report_v1_2a.json`
- `artifacts/manifests/phase_a_benchmark_report_v1_2b.json`
- `artifacts/manifests/phase_a_benchmark_report_v1_tuned_control.json`

## 5. Gate decisions

### Gate 1.1 — exact arrival hour

Đạt ngưỡng `skill >= -4.5%` với V1.1 ở `-3.335706%`.

Control công bằng với cùng tuned params cho thấy:

```text
V1 control  = -3.225318%
V1.1        = -3.335706%
chênh lệch  = -0.110387 percentage points
```

Vì vậy, exact arrival hour **không chứng minh được đóng góp dương** trong
thiết lập này; V1.1 tốt hơn Phase A gốc chủ yếu do đổi sang V1 feature
contract/tuned model, không nên quy toàn bộ cải thiện cho arrival hour.

### Gate 1.2 — target encoding

Không đóng gap hoàn toàn vì best skill vẫn `< 0%` và vẫn `< -2%`:

- raw: `-3.629773%`;
- smoothing `k=30`: `-3.518021%`.

Smoothing tốt hơn raw khoảng `0.111752` điểm phần trăm, nhưng vẫn kém V1.1
`0.182315` điểm phần trăm. Target encoding không cải thiện XGBoost trong
benchmark này.

## 6. Feature set chọn cho Ngày 2

Chọn **V1.1 (exact scheduled-arrival clock, không target encoding)** làm
điểm xuất phát Ngày 2 vì có mean XGBoost skill tốt nhất trong ba cấu hình mới
(`-3.335706%`). Target encoding vẫn được giữ trong code/manifests để làm
ablation đã ghi nhận, nhưng chưa được chọn làm default.

Giả thuyết ưu tiên cho Ngày 2: **objective mismatch / model loss mismatch**
giữa MSE đang dùng trong Phase A và tiêu chí đánh giá MAE/skill score. Không
chạy full HPO trong Day 1.

## 7. Verification

- Focused tests: `45 passed`.
- Python compile check cho các module đã sửa: exit code `0`.
- Benchmark V1.1, V1.2a, V1.2b và V1 tuned control: mỗi cấu hình đủ 5 seed,
  exit code `0`.
- V1 manifest giữ nguyên; không có diff.
- Không có row-level access tới 2023/2024 trong các benchmark Day 1.

## 8. Bất thường và giới hạn

- Repo có thông báo access guard tổng quát “allowed for 2016-2023”, nhưng các
  lần load thực tế của Day 1 chỉ gọi các năm 2016–2022.
- Phase A gốc dùng V2 không có `calendar_year`, trong khi HPO Week 5 tham chiếu
  V1 có `calendar_year`. Vì vậy bảng đã thêm V1 tuned control để tránh gán
  chênh lệch V1.1 hoàn toàn cho hai cột arrival mới.
- Phase A benchmark hiện fit target encoding từ toàn bộ train side của fold rồi
  áp dụng cho train/validation; validation không tham gia mapping. Đây là
  đúng policy per-fold của Day 1, nhưng nếu Ngày 2 cần strict sequential
  online encoding cho từng training timestamp thì phải thiết kế protocol riêng.
