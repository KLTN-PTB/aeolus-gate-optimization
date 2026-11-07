# BÁO CÁO THỰC NGHIỆM ABLATION STUDY (CLASSIFICATION)
**Thời gian**: 2026-10-20 18:32:55

| Task           | Cấu hình                  |   Số Feat |   ROC-AUC |   PR-AUC |   F1-Score |   Brier Score |   Thời gian (s) |
|:---------------|:--------------------------|----------:|----------:|---------:|-----------:|--------------:|----------------:|
| Arrival (Đến)  | M1_Schedule_Only          |        24 |    0.6469 |   0.309  |     0.0005 |        0.1554 |             2.2 |
| Arrival (Đến)  | M2_Schedule_Network       |        38 |    0.6458 |   0.3068 |     0      |        0.1557 |             2.5 |
| Arrival (Đến)  | M3_Static_Weather_T2H     |        55 |    0.6458 |   0.3068 |     0      |        0.1557 |             2.1 |
| Arrival (Đến)  | M4_Proposed_Full_Dynamics |        61 |    0.6458 |   0.3068 |     0      |        0.1557 |             2.1 |
| Departure (Đi) | M1_Schedule_Only          |        24 |    0.6528 |   0.3079 |     0.0082 |        0.1564 |             2.2 |
| Departure (Đi) | M2_Schedule_Network       |        38 |    0.6531 |   0.3074 |     0.011  |        0.1564 |             3.6 |
| Departure (Đi) | M3_Static_Weather_T2H     |        55 |    0.6531 |   0.3074 |     0.011  |        0.1564 |             2.8 |
| Departure (Đi) | M4_Proposed_Full_Dynamics |        61 |    0.6531 |   0.3074 |     0.011  |        0.1564 |             3   |
