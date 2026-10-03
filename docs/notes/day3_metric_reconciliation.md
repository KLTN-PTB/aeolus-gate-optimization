# Day 3 — Metric reconciliation and temporal diagnostic

Ngày thực hiện: 2026-09-20  
Scope: chỉ dùng các partition 2016–2022; không mở row-level 2023/2024.

## 1. Kết luận blocker

`artifacts/manifests/phase_a_benchmark_mae_b2.json` không phải báo cáo rolling 4-fold. Runner `scripts/run_phase_a_benchmark_mae.py` gọi `run_config()` với `run_single_benchmark()` mặc định `train_years = [2016..2021]`, `val_year = 2022`; `_config_report()` ghi rõ protocol là `Fold 4 (Train 2016-2021, Val 2022)`. Vì vậy:

```text
summary.xgboost.skill_score_vs_carrier_hour.mean
= trung bình 5 seed trên Fold 4
= -0.2519280802513224%
```

`phase_a_benchmark_mae_per_fold.json` được tạo bởi nhánh `--per-fold`. Nhánh này lặp qua `LOCKED_FOLDS`, 4 fold × 5 seed, rồi `fold_summary` lấy trung bình skill của 5 seed trong từng fold. Đây là rolling-fold diagnostic, không phải cùng một scope với summary của B2.

## 2. Vì sao dãy +0.51, +1.45, +0.18, -0.25 không mâu thuẫn với B2?

Dãy được nêu trong câu hỏi khớp chính xác với config `a2`, không phải `b2`:

| Config | Feature | Objective | Fold 1 / 2019 | Fold 2 / 2020 | Fold 3 / 2021 | Fold 4 / 2022 | Macro 4-fold |
|---|---|---:|---:|---:|---:|---:|---:|
| A2 | V1 | `reg:absoluteerror` | +0.5100% | +1.4455% | +0.1841% | −0.2452% | +0.4736% |
| B2 | V1.1 | `reg:absoluteerror` | +0.4740% | +1.2444% | +0.1698% | −0.2519% | +0.4091% |

`b2` trong main artifact là V1.1 + frozen Week 5 parameters + `reg:absoluteerror`; per-fold artifact chứa cả A2 và B2. Do đó không có aggregation bug trong B2: số `−0.2519%` là Fold 4-only, còn macro B2 tính từ bốn fold là `+0.4091%`.

## 3. Ba câu hỏi cụ thể

### 3.1 `summary.xgboost.skill_score` đo trên fold nào?

Artifact dùng field đầy đủ `summary.xgboost.skill_score_vs_carrier_hour`. Code aggregation tại `aggregate_results()` chỉ nhận `seed_results` của một lần `run_config()`. `run_config()` không truyền `train_years`/`val_year` vào `run_single_benchmark()`, nên dùng Fold 4 mặc định. Kết luận: field này là Fold 4-only, trung bình 5 seed.

Metric canonical cho quyết định rolling của Day 3 là macro 4-fold; Fold 4 vẫn là stress test temporal bắt buộc và là headline của artifact B2 cũ. Hai scope phải được ghi cùng nhau, không được gọi Fold 4-only là macro.

### 3.2 Skill từng fold được tính thế nào?

Trong `_model_metrics()`:

```python
compute_skill_score(point["mae"], baseline_mae)
```

và `compute_skill_score()` trả về:

```text
(1 - model_MAE / baseline_MAE) × 100
= (baseline_MAE - model_MAE) / baseline_MAE × 100
```

`baseline_mae` là MAE của `NaiveDelayBaselines.predict_carrier_hour_median(X_val)`. Baseline được fit trước trên `X_train, y_train_reg` của chính fold đó; carrier-hour medians là train-side, kèm global fallback cho cell không thấy trong train. Đây là carrier-hour baseline fold-local.

Model A2/B2 được benchmark trên cùng sampling protocol 25K train mỗi năm + 25K validation, seeds `[42..46]`; B2 dùng V1.1, frozen Week 5 XGBoost parameters và `reg:absoluteerror`, `eval_metric=mae`.

### 3.3 Arithmetic

Với dãy được nêu trong câu hỏi:

```text
mean([0.5099942267, 1.4455200623, 0.1841317185, -0.2451916808])
= +0.4736135817 percentage points
≈ +0.47%
```

Với B2:

```text
mean([0.4739864757, 1.2443612076, 0.1698343496, -0.2519280803])
= +0.4090634882 percentage points
≈ +0.41%
```

Các giá trị trong `fold_summary` là trung bình skill theo seed, vì vậy macro 4-fold là trung bình bốn `skill_mean`. Chênh lệch cực nhỏ nếu tính lại từ `mean(model_MAE)` và `mean(baseline_MAE)` là do skill là tỷ số theo từng seed rồi mới aggregate; canonical aggregation hiện tại là mean của per-seed skill và không phải lỗi.

## 4. Canonical reporting rule cho Day 3

- `Fold 4 skill`: metric stress-test 2022, giữ để so sánh trực tiếp với artifact B2 (`−0.2519%`).
- `Macro 4-fold skill`: metric canonical cho rolling-protocol generalization (`+0.4091%` cho B2; `+0.4736%` cho A2).
- Không được dùng dãy A2 để kết luận cho B2.
- Việc supersede Decision Gate A chưa được ghi vào registry chỉ từ blocker này. Cần hoàn tất fold-2022/trend diagnostic và áp dụng cả ba điều kiện chặt hơn: macro dương, Fold 4 không thấp hơn −1pp, và không có degradation rõ từ 2021 sang 2022.

## 5. Fold 2022 diagnostic

Diagnostic được chạy bất kể macro dương hay âm, với artifact versioned:
`artifacts/manifests/day3_fold_diagnostics_v1.json`. Runner dùng V1.1, 25K train mỗi năm, 25K validation và seeds `[42..46]`; chỉ mở các fold 2019–2022. Baseline carrier-hour được fit riêng trên train side của từng fold.

### 5.1 PSI train-side → validation-side

PSI được tính theo category universe hợp nhất của train và validation. Ngưỡng: `<0.10` nhỏ, `0.10–0.25` moderate, `>0.25` lớn.

| Feature | Fold 1 / 2019 | Fold 2 / 2020 | Fold 3 / 2021 | Fold 4 / 2022 | Diễn giải Fold 4 |
|---|---:|---:|---:|---:|---|
| `OP_CARRIER` | 0.5381 | 0.4770 | 0.8914 | 0.5258 | lớn |
| `ORIGIN` | 0.0386 | 0.0783 | 0.1864 | 0.1599 | moderate |
| `scheduled_departure_hour` | 0.0127 | 0.0589 | 0.0112 | 0.0276 | nhỏ |
| `scheduled_arrival_hour` | 0.0076 | 0.0700 | 0.0194 | 0.0246 | nhỏ |
| `calendar_month` | 0.0000 | 0.0000 | 0.0000 | 0.0000 | nhỏ |
| `calendar_day_of_week` | 0.0002 | 0.0024 | 0.0029 | 0.0011 | nhỏ |

Kết luận drift: không có evidence cho seasonality drift trong month/day-of-week, và schedule-hour drift nhỏ. Có carrier-mix drift lớn ở mọi fold và route/origin drift tăng rõ ở Fold 3–4. Đây là evidence phù hợp với thay đổi carrier/route composition; PSI một mình không chứng minh quan hệ nhân quả, nhưng nó loại trừ seasonality là lời giải thích chính cho skill giảm.

### 5.2 Baseline stability trên Fold 4

Các số dưới đây là mean trên 5 seed; sparse được định nghĩa là train cell `(OP_CARRIER, scheduled_arrival_hour)` có `<100` rows.

| Metric | Fold 4 mean |
|---|---:|
| Baseline carrier-hour MAE | 19.8366 |
| Tổng train cells | 277.8 |
| Sparse train cells | 134.8 / 277.8 = 48.5% |
| Validation rows vào sparse cells | 1,349.8 / 25,000 = 5.4% |
| Validation rows vào dense cells | 23,627.4 / 25,000 = 94.5% |
| Validation rows vào unseen cells | 22.8 / 25,000 = 0.09% |
| Baseline MAE trên sparse rows | 28.4659 |
| Baseline MAE trên dense rows | 19.3468 |
| Baseline MAE trên unseen rows | 16.5331 |

Baseline 2022 không “mạnh lên bất thường” theo MAE tổng thể: baseline MAE Fold 4 là 19.8366, cao hơn Fold 1/2/3 lần lượt 18.1880/13.6556/15.8430. Tuy nhiên, baseline có instability cục bộ: gần một nửa số cell train là sparse và sparse rows có MAE cao hơn dense rows khoảng 9.12 phút. Vì chỉ 5.4% validation rows nằm trong sparse cells, đây là vấn đề baseline-tail/local coverage chứ không đủ để giải thích toàn bộ skill âm của Fold 4.

### 5.3 Trend 2019→2022 và tail behavior B2

| Fold / validation year | Baseline MAE | B2 MAE | B2 skill | B2 severe MAE | B2 shrinkage |
|---|---:|---:|---:|---:|---:|
| Fold 1 / 2019 | 18.1880 | 18.1019 | +0.4740% | 151.7674 | −0.0394 |
| Fold 2 / 2020 | 13.6556 | 13.4858 | +1.2444% | 163.2323 | −0.0539 |
| Fold 3 / 2021 | 15.8430 | 15.8161 | +0.1698% | 160.8920 | −0.0728 |
| Fold 4 / 2022 | 19.8366 | 19.8864 | −0.2519% | 163.0096 | −0.0614 |

Skill không giảm đơn điệu từ 2019: nó tăng từ 2019 lên 2020, rồi giảm trong 2021 và 2022. Sau đỉnh 2020, degradation là `−1.0745pp` tới 2021 và thêm `−0.4218pp` từ 2021 tới 2022. Fold 4 severe MAE cao hơn Fold 1 và Fold 3 nhưng thấp hơn Fold 2; shrinkage Fold 4 xấu hơn Fold 1/2 nhưng tốt hơn Fold 3. Vì vậy tail behavior có đóng góp, nhưng Fold 4 không phải tail outlier duy nhất; mean degradation gắn chặt hơn với carrier/route composition drift.

### 5.4 Case classification và gate

Quy tắc Day 3:

- Case A: macro dương, Fold 4 ≥ −1pp, và không có temporal/drift warning.
- Case B: macro dương, Fold 4 ≥ −1pp, nhưng còn temporal hoặc drift warning.
- Case C: macro không dương hoặc Fold 4 < −1pp.

Kết quả:

```text
macro 4-fold skill       = +0.4091%
Fold 4 skill             = -0.2519%
2021 → 2022 change       = -0.4218pp
Fold 4 max PSI            = 0.5258 (OP_CARRIER)
Case                      = B
registry gate             = NOT PASS
```

Đây là Case B: được phép thử model class mới vì point gate đạt và Fold 4 không thấp hơn −1pp, nhưng chưa được supersede Decision Gate A trong registry vì còn temporal degradation và carrier/route drift. LightGBM chỉ được chạy sau checkpoint này, với cùng V1.1/25K/seeds `[42..46]`.
### 5.5 OP_CARRIER ablation trước LightGBM

Đã chạy artifact mới `artifacts/manifests/day3_carrier_ablation_v1.json` để phân biệt carrier drift với carrier signal. Chỉ `OP_CARRIER` bị loại khỏi model matrix; carrier-hour baseline vẫn fit trên X train gốc của từng fold. Objective, frozen Week 5 parameters, 25K/year, 25K validation và seeds `[42..46]` giữ nguyên.

| Fold / year | B2 skill | B2 − OP_CARRIER skill | Delta ablation − B2 |
|---|---:|---:|---:|
| Fold 1 / 2019 | +0.4740% | +0.1255% | −0.3485pp |
| Fold 2 / 2020 | +1.2444% | +1.1669% | −0.0775pp |
| Fold 3 / 2021 | +0.1698% | +0.3259% | +0.1561pp |
| Fold 4 / 2022 | −0.2519% | −0.6483% | −0.3964pp |
| Macro 4-fold | +0.4091% | +0.2425% | −0.1666pp |

Kết luận carrier: `carrier_signal_is_useful`. Bỏ carrier làm tệ rõ ở Fold 4 và tệ nhẹ trên macro; PSI cao của `OP_CARRIER` phản ánh drift composition nhưng không cho thấy carrier là feature gây hại. LightGBM nên giữ `OP_CARRIER` native categorical ở config đầu tiên; không loại carrier chỉ vì PSI cao. Regularization/rare-category handling chỉ nên đưa vào HPO sau khi có reference LightGBM.
