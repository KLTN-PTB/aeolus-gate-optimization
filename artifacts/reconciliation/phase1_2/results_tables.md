# Kết quả được tính lại từ bằng chứng đã lưu

Phạm vi: phép tính trên dự báo/ledger đã lưu; không phải tái huấn luyện hoặc nghiệm thu của GVHD.
Giá trị JSON giữ độ chính xác đầy đủ; bảng dưới làm tròn 5 chữ số. IDs liên kết metric_registry.csv.

## Phân loại departure trên selection 2023

| Model | N | ROC-AUC | PR-AUC | Precision | Recall | F1 | Brier | ECE |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| constant_prevalence_baseline | 332734 | 0.50000 | 0.20625 | 0.00000 | 0.00000 | 0.00000 | 0.16776 | 0.06360 |
| outbound_logistic_raw_v1 | 332734 | 0.61343 | 0.29708 | 0.47587 | 0.00417 | 0.00826 | 0.16196 | 0.05507 |
| outbound_logistic_calibrated_v1 | 332734 | 0.61336 | 0.29381 | 0.45246 | 0.03931 | 0.07234 | 0.15892 | 0.01047 |
| outbound_xgboost_raw_v1 | 332734 | 0.64289 | 0.32916 | 0.51934 | 0.03815 | 0.07107 | 0.15891 | 0.05644 |
| outbound_xgboost_calibrated_v1 | 332734 | 0.64289 | 0.32915 | 0.49262 | 0.04862 | 0.08851 | 0.15637 | 0.01192 |

Ngưỡng phân loại = 0,5. Probability từ bộ phân loại được phân biệt với biến đổi sigmoid của hồi quy.

## Hồi quy departure trên selection 2023

| Model | N | MAE phút | RMSE phút | MAE trễ ≥15 | MAE trễ ≥60 |
|---|---:|---:|---:|---:|---:|
| baseline_zero | 332734 | 15.61723 | 45.21267 | 60.33140 | 130.54118 |
| baseline_median | 332734 | 15.60280 | 45.76176 | 62.33140 | 132.54118 |
| departure_ridge_baseline_v1 | 332734 | 17.94460 | 43.30792 | 49.82919 | 118.95395 |
| departure_xgboost_baseline_v1 | 332734 | 17.60169 | 43.00055 | 48.90865 | 117.18392 |

Median là dự báo đã lưu; tính lại sai số chưa chứng minh median được fit chỉ trên train.

## Arrival và cách tổng hợp

| Model | Task | Population | N | Pooled AUC hoặc MAE | Macro AUC hoặc MAE |
|---|---|---|---:|---:|---:|
| arrival_linear_baseline_v1 | arrival_classification | development_oof_2019_2022_sample | 16000 | 0.57088 | 0.58691 |
| arrival_linear_baseline_v1 | arrival_regression | development_oof_2019_2022_sample | 16000 | 20.24207 | 20.24207 |
| arrival_random_forest_baseline_v1 | arrival_classification | development_oof_2019_2022_sample | 16000 | 0.57911 | 0.59199 |
| arrival_random_forest_baseline_v1 | arrival_regression | development_oof_2019_2022_sample | 16000 | 19.74298 | 19.74298 |
| arrival_hist_gradient_boosting_baseline_v1 | arrival_classification | development_oof_2019_2022_sample | 16000 | 0.58249 | 0.58783 |
| arrival_hist_gradient_boosting_baseline_v1 | arrival_regression | development_oof_2019_2022_sample | 16000 | 19.43202 | 19.43202 |
| arrival_xgboost_baseline_v1 | arrival_classification | development_oof_2019_2022_sample | 16000 | 0.58235 | 0.58895 |
| arrival_xgboost_baseline_v1 | arrival_regression | development_oof_2019_2022_sample | 16000 | 20.21795 | 20.21795 |
| arrival_weighted_ensemble_v1 | arrival_classification | development_oof_2019_2022_sample | 16000 | 0.58456 | 0.59179 |
| arrival_weighted_ensemble_v1 | arrival_regression | development_oof_2019_2022_sample | 16000 | 19.62002 | 19.62002 |
| arrival_xgboost_tuned_v1_1 | arrival_classification | development_full_oof_2019_2022 | 1254518 | 0.61768 | 0.61933 |
| arrival_xgboost_tuned_v1_1 | arrival_regression | development_full_oof_2019_2022 | 1254518 | 19.40800 | 19.19011 |

Không suy ra mức cải thiện giữa baseline 16.000 dòng và tuned OOF 1.254.518 dòng.
Macro là trung bình metric từng fold; pooled tính một lần trên toàn bộ dòng gộp.

## MC500 chính thức

| Mode | Initial solver | N | Mean objective điểm | Feasible | Conflicts | Buffer violations |
|---|---|---:|---:|---:|---:|---:|
| A | CPSat | 500 | 1469.17023 | 126/500 | 682 | 0 |
| A | Greedy | 500 | 1469.17023 | 126/500 | 682 | 0 |
| A | Hybrid | 500 | 1469.17023 | 126/500 | 682 | 0 |
| B1 | CPSat | 500 | 130.73023 | 500/500 | 0 | 0 |
| B1 | Greedy | 500 | 130.73023 | 500/500 | 0 | 0 |
| B1 | Hybrid | 500 | 130.73023 | 500/500 | 0 | 0 |
| B2 | CPSat | 500 | 139.49023 | 500/500 | 0 | 0 |
| B2 | Greedy | 500 | 139.49023 | 500/500 | 0 | 0 |
| B2 | Hybrid | 500 | 139.49023 | 500/500 | 0 | 0 |
| C1 | NONE | 500 | 130.73023 | 500/500 | 0 | 0 |
| C2 | NONE | 500 | 120.39023 | 500/500 | 0 | 0 |

Mẫu số 500 thuộc từng initial solver. Cộng các initial solver của A/B1/B2 thành 1.500 lượt, không phải 1.500 kịch bản độc lập.
C2 có 499 OPTIMAL và 1 FEASIBLE. Full-day retrospective web recourse khác B2 causal online.
Objective là điểm theo cấu hình mô phỏng. Marginals và copula MC500 là tham số cấu hình, không phải kết quả suy luận trên file upload.

## So sánh ghép cặp MC500

| Chênh lệch | N | Mean delta điểm | 95% CI Student t | p-value |
|---|---:|---:|---|---:|
| A-B2 | 500 | 1329.68000 | [1229.91249, 1429.44751] | 9.6252e-96 |
| B1-B2 | 500 | -8.76000 | [-11.63281, -5.88719] | 3.9961e-09 |
| C1-C2 | 500 | 10.34000 | [9.18488, 11.49512] | 3.1295e-54 |
| B2-C2 | 500 | 19.10000 | [15.93198, 22.26802] | 1.0705e-28 |

A/B dùng initial plan Greedy trong bảng ghép cặp. Đã kiểm tra cùng scenario_index và realization_hash.
Khoảng tin cậy Student t ở đây khác xấp xỉ normal 1,96 trong paired_comparison.csv lịch sử; không thay file gốc.
B2−C2 được mô tả là khoảng cách chính sách với foresight, không khẳng định formal EVPI.

## Benchmark G5 được tổng hợp lại

| Solver | Runs | Feasible | Proven optimal | Mean objective điểm | Max runtime ms |
|---|---:|---:|---:|---:|---:|
| CP_SAT_STANDALONE | 5 | 5 | 2 | 408.02666 | 5436.44 |
| GREEDY_STANDALONE | 5 | 5 | 0 | 508.02666 | 18.44 |
| HYBRID_STANDALONE | 5 | 5 | 2 | 454.02666 | 12500.92 |
| SA_STANDALONE | 5 | 5 | 0 | 502.02666 | 9215.35 |

Cùng scenario hash chưa đủ để chứng minh ngân sách wall-clock bằng nhau. Không khẳng định Hybrid luôn bằng hoặc tốt hơn CP-SAT.

## Sai lệch và giới hạn cần giữ trong báo cáo

- {"computed": 0.06360484621349188, "field": "ece", "kind": "summary_difference", "model_id": "constant_prevalence_baseline", "saved": 0.06361}
- {"computed": 0.05643654552067171, "field": "ece", "kind": "summary_difference", "model_id": "outbound_xgboost_raw_v1", "saved": 0.05643}
- {"computed": 0.32915364806108205, "field": "pr_auc", "kind": "summary_difference", "model_id": "outbound_xgboost_calibrated_v1", "saved": 0.32916}
- {"kind": "aggregation_label", "message": "P08 arrival rows are pooled, not macro. Its hardcoded tuned row is superseded by full stored OOF metrics with a different population."}

SHAP được kiểm tra riêng trong shap_audit.json. Tên model và quyền downstream lấy từ model_identity.json.
Flight Chain/Weather ablation có số liệu ghi cứng được phân loại trong lineage_audit.json.
