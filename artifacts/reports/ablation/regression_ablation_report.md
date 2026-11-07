# BÁO CÁO THỰC NGHIỆM ABLATION STUDY (REGRESSION)
**Thời gian**: 2026-10-20 18:34:31

| Task               | Cấu hình                  |   Số Feat |   MAE (phút) |   RMSE (phút) |   MedAE (phút) |   R2-Score |   Thời gian (s) |
|:-------------------|:--------------------------|----------:|-------------:|--------------:|---------------:|-----------:|----------------:|
| Arrival Reg (Đến)  | M1_Schedule_Only          |        24 |        24.93 |         44.37 |          16.69 |     0.0287 |             1.8 |
| Arrival Reg (Đến)  | M2_Schedule_Network       |        38 |        25.06 |         44.48 |          16.85 |     0.0239 |             1.9 |
| Arrival Reg (Đến)  | M3_Static_Weather_T2H     |        55 |        25.06 |         44.48 |          16.85 |     0.0239 |             2.7 |
| Arrival Reg (Đến)  | M4_Proposed_Full_Dynamics |        61 |        25.06 |         44.48 |          16.85 |     0.0239 |             3.6 |
| Departure Reg (Đi) | M1_Schedule_Only          |        24 |        22    |         41.96 |          13.61 |     0.0279 |             9   |
| Departure Reg (Đi) | M2_Schedule_Network       |        38 |        22.24 |         42.06 |          14.08 |     0.0231 |             8.3 |
| Departure Reg (Đi) | M3_Static_Weather_T2H     |        55 |        22.24 |         42.06 |          14.08 |     0.0231 |             8.4 |
| Departure Reg (Đi) | M4_Proposed_Full_Dynamics |        61 |        22.24 |         42.06 |          14.08 |     0.0231 |             9.5 |
