# Day 2 — Objective mismatch và sample size

Ngày thực hiện: 2026-09-20  
Protocol: Phase A Fold 4, train 2016–2021, validation 2022, stratified theo
tháng, validation cố định 25.000 dòng. Chỉ dùng V1/V1.1, Week 5 tuned
parameters, và seeds `[42, 43, 44, 45, 46]` trừ stability scan ghi rõ
`[42..51]`.

## 1. Xác nhận objective mismatch

Artifact HPO
`artifacts/manifests/week5_hpo_protocol_v1_1__xgboost_regression_result_v1.json`
chọn theo:

- `objective_name = mean_mae_across_locked_folds`;
- `best_objective = 19.1901123652`;
- fixed XGBoost training objective trong
  `configs/week5_hpo_v1_1.yaml` là `reg:squarederror`;
- Phase A V1.1 cũng dùng `reg:squarederror`.

Vì vậy mismatch được xác nhận: HPO chọn tham số theo MAE nhưng loss khi train
XGBoost là squared error. Hôm nay kiểm tra trực tiếp `reg:absoluteerror`, không
thay đổi tuned parameters.

## 2. Objective A/B

| Config | Feature | Objective | Skill mean | Skill std | MAE mean |
|---|---|---|---:|---:|---:|
| A1 | V1 | `reg:squarederror` | −3.2253% | 0.1511 pp | 20.4776 |
| A2 | V1 | `reg:absoluteerror` | **−0.2452%** | 0.0467 pp | 19.8863 |
| B1 | V1.1 | `reg:squarederror` | −3.3357% | 0.2022 pp | 20.4981 |
| B2 | V1.1 | `reg:absoluteerror` | **−0.2519%** | 0.0907 pp | 19.8864 |

So với control cùng feature:

- A2 cải thiện `+2.9801` điểm phần trăm so với A1.
- B2 cải thiện `+3.0838` điểm phần trăm so với B1.
- Chưa config nào đạt skill `≥ 0%`; Gate 2.1 chưa đóng hoàn toàn.
- HGB H1/H2 không chạy vì lever objective của XGBoost đã đủ rõ và sample
  scan quan trọng hơn trong phạm vi ngày này.

### Per-fold follow-up

Vì A2/B2 cải thiện hơn 1 điểm phần trăm, đã chạy 4 locked folds × 5 seeds
trong `phase_a_benchmark_mae_per_fold.json`.

| Fold | Validation year | A2 skill | B2 skill |
|---|---:|---:|---:|
| fold_1 | 2019 | +0.5100% | +0.4740% |
| fold_2 | 2020 (COVID) | **+1.4455%** | **+1.2444%** |
| fold_3 | 2021 | +0.1841% | +0.1698% |
| fold_4 | 2022 | −0.2452% | −0.2519% |

Cải thiện mạnh nhất ở fold 2020 nhưng không chỉ xuất hiện ở đó; fold 2019 và
2021 cũng dương nhẹ. Fold 2022 vẫn là phần khó nhất và không có evidence rằng
COVID là nguyên nhân duy nhất.

## 3. Sample-size scan

25K/năm được chọn ban đầu để giữ benchmark nhanh, giữ footprint bộ nhớ thấp,
và khớp protocol Phase A/Day 1: sáu năm train tương đương 150K dòng, validation
25K dòng cố định. Scan hôm nay dùng V1.1 + `reg:absoluteerror` và không đổi
validation population.

| Train sample/năm | Tổng train rows | Skill mean | Skill std | MAE mean | Thời gian 5 seed |
|---:|---:|---:|---:|---:|---:|
| 25K | 150K | −0.2519% | 0.0907 pp | 19.8864 | 72.9 s |
| 75K | 450K | −0.3204% | 0.0956 pp | 19.8746 | 179.5 s |
| 150K | 900K | −0.3120% | 0.1090 pp | 19.8625 | 325.7 s |
| 250K | 1.5M | **−0.2252%** | 0.0831 pp | 19.8370 | 556.0 s |

250K/năm khả thi trong môi trường hiện tại: 1.5M train rows chạy thành công.
Peak RAM chưa được instrument riêng; ước lượng working set ở mức hàng trăm MB
đến thấp vài GB do pandas + dense tree matrix + XGBoost histogram. Thời gian
thực tế 250K là khoảng 9.3 phút cho 5 seed và 18.6 phút cho 10 seed.

Kết quả không tăng đơn điệu: 75K và 150K tệ hơn 25K, còn 250K chỉ tốt hơn
25K khoảng `0.0267` điểm phần trăm. Vì vậy sample size không phải lever chính,
dù 250K là mức tốt nhất theo mean của scan.

### Fold 4 stability tại mức tốt nhất

Report `phase_a_benchmark_sample_250k_10seed.json` dùng seeds `[42..51]`:

- skill mean: **−0.1975%**;
- skill std: **0.0800 điểm phần trăm**;
- MAE mean: 19.7560;
- Gate ổn định: PASS, vì std `< 1.0` điểm phần trăm.

## 4. Quyết định

### Objective mismatch

Có, và đây là lever lớn. Trên V1.1, đổi MSE loss sang MAE loss cải thiện khoảng
`3.08` điểm phần trăm, từ −3.3357% xuống −0.2519% ở 25K. Đây gần như đóng hết
gap của Phase A tuned control, nhưng còn âm nhẹ.

### Sample size

Có tác động nhỏ nhưng không phải lever chính. Từ 25K lên 250K chỉ cải thiện
mean khoảng `0.0267` điểm phần trăm trong scan 5 seed; stability 10 seed vẫn
cho −0.1975%, chưa đạt 0%.

### Cộng dồn có đóng hết 3.23% còn lại không?

Chưa. Objective correction đóng khoảng 3.08 điểm phần trăm của gap V1.1 và
sample-size correction đóng thêm dưới 0.1 điểm phần trăm tùy seed set, nhưng
skill vẫn khoảng −0.20%. Không nên tuyên bố point-regression gap đã đóng.

## 5. Đề xuất Day 3

Không chạy full HPO ngay. Dùng V1.1 + `reg:absoluteerror` làm control đúng loss,
và ưu tiên các lever chưa thử:

1. Thử model class có categorical/interaction native, trước hết CatBoost hoặc
   LightGBM, với cùng protocol và cùng feature policy.
2. Thêm interaction schedule-only point-in-time safe: route × day-of-week,
   carrier × month, carrier × day-of-week, và các tương tác với scheduled
   arrival/departure hour; tuyệt đối không dùng actual-operation/outcome.
3. Thử segment model có kiểm soát cho carrier lớn hoặc route lớn, có ngưỡng
   số dòng và fallback về global V1.1 model cho segment thưa.
4. Sau khi có model class/feature candidate tốt hơn, chạy focused HPO theo MAE
   loss trên V1.1; không quay lại HPO trên `reg:squarederror`.

## 6. Artifact và compliance

- Objective reports: `phase_a_benchmark_mae_a1.json`, `a2.json`, `b1.json`,
  `b2.json`.
- Per-fold diagnostic: `phase_a_benchmark_mae_per_fold.json`.
- Sample reports: `phase_a_benchmark_sample_25k.json`, `75k.json`, `150k.json`,
  `250k.json`.
- Stability/selection: `phase_a_benchmark_sample_250k_10seed.json` và
  `phase_a_benchmark_sample_scan_selection.json`.
- Không ghi đè report Day 1; manifest V1/V1.1/V1.2 không bị sửa.
- Tất cả report mới ghi timestamp, hash của feature manifest, HPO result,
  HPO protocol và runner/input metadata.
- Artifact flags xác nhận `row_level_2023_accessed = false` và
  `row_level_2024_accessed = false`.
- Không dùng weather, Flight Chain, actual-operation fields, hay outcome fields
  làm predictor; không chạy HPO trong Day 2.
