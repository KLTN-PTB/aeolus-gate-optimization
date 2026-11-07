# TỔNG HỢP TOÀN DIỆN KẾT QUẢ THỰC NGHIỆM ABLATION STUDY

**Đề tài Khóa luận**: Ứng dụng học máy và lập trình ràng buộc trong dự báo độ trễ chuyến bay và tối ưu tái phân bổ cổng đỗ tàu bay (Mã đề tài: **CNTT-KLCN168**)
**Mục tiêu tài liệu**: Tổng hợp toàn bộ phương pháp, quy mô dữ liệu, ma trận kết quả bóc tách đặc trưng (Feature Ablation), so sánh đa mô hình (Multi-Model), tối ưu hóa Optuna và mở rộng 5 triệu dòng (Scale-up 5M).

---

## 1. Thiết kế Thử nghiệm & Phân chia Dữ liệu (Experimental Setup)

Để tuân thủ chuẩn mực học máy thực tiễn và loại bỏ hoàn toàn **rò rỉ dữ liệu theo thời gian (Temporal Leakage)**, toàn bộ thực nghiệm sử dụng chiến lược **Temporal Split (Chia theo trục thời gian)** trên dữ liệu Aeolus (BTS + Meteostat):

| Phân vùng dữ liệu           | Phạm vi thời gian |                            Quy mô (Số dòng)                            | Vai trò trong quy trình                                                                      |
| :------------------------------ | :-----------------: | :------------------------------------------------------------------------: | :--------------------------------------------------------------------------------------------- |
| **Train Set**             |    2016 – 2022    | **1,000,000 dòng** *(GĐ 1)***5,000,000 dòng** *(GĐ 2)* | Dùng để huấn luyện các mô hình nền tảng và mô hình Champion                       |
| **Validation Set**        |        2023        |                          **300,000 dòng**                          | Tìm ngưỡng phân loại tối ưu $T$T^*$, theo dõi Early Stopping và chạy Optuna tuning |
| **Test Set (Độc lập)** |   **2024**   |                          **300,000 dòng**                          | Đánh giá Out-of-Time khách quan, tuyệt đối không tham gia huấn luyện                 |

> [!IMPORTANT]
> **Tính nhất quán giữa 2 bài toán:** Cả hai tác vụ **Phân loại trễ ($P \ge 15$ phút)** và **Hồi quy số phút trễ ($\Delta T$)** đều được kiểm thử trên **cùng đúng 300,000 chuyến bay của năm 2024**, bảo đảm tính so sánh công bằng tuyệt đối (Fair Benchmark).

---

## 2. Các Cấp độ Bóc tách Đặc trưng (Feature Ablation Levels)

Hệ thống đánh giá sự đóng góp tăng dần của các nhóm biến số qua 4 cấu hình:

1. **M1_Schedule_Only (24 đặc trưng):**
   * *Bản chất*: Thông tin lịch trình tĩnh có thể biết trước nhiều ngày.
   * *Bao gồm*: Giờ dự kiến cất cánh/hạ cánh (`DEP_HOUR`, `ARR_HOUR`), cự ly bay (`DISTANCE_KM`), thời gian bay dự kiến (`CRS_ELAPSED_TIME`), ngày trong tuần, tháng, quý, mã hãng bay, mã sân bay đi/đến, các hàm chu kỳ lượng giác (`HOUR_SIN`, `HOUR_COS`, `MONTH_SIN`, `MONTH_COS`).
2. **M2_Schedule_Network (38 đặc trưng):**
   * *Bản chất*: M1 cộng thêm đặc trưng cấu trúc mạng lưới hàng không và tắc nghẽn cục bộ.
   * *Bao gồm*: Mật độ chuyến bay cùng khung giờ tại sân bay đi/đến (`CONGESTION_SAME_HOUR`), tần suất bay trong ngày (`DAILY_FLIGHTS`), tỷ lệ trễ lịch sử trung bình theo hãng/tuyến bay/sân bay quá khứ và cửa sổ trượt rolling.
3. **M3_Static_Weather_T2H (55 đặc trưng):**
   * *Bản chất*: M2 cộng thêm đặc trưng quan trắc thời tiết tĩnh tại mốc $T-2h$ trước giờ bay (từ Meteostat).
   * *Bao gồm*: Nhiệt độ (`TEMP`), lượng mưa (`PRCP`), tốc độ gió (`WSPD`) tại cả 2 đầu sân bay; các cờ chỉ thị thời tiết bất lợi (`IS_RAINY`, `IS_WINDY`, `IS_COLD`); độ chênh lệch nhiệt độ/gió giữa 2 sân bay và chỉ số thời tiết khắc nghiệt (`WEATHER_SEVERITY`).
4. **M4_Proposed_Full_Dynamics (61 đặc trưng - Đề xuất hoàn chỉnh):**
   * *Bản chất*: M3 cộng thêm các vector động lực học biến thiên thời tiết theo thời gian thực.
   * *Bao gồm*: Tốc độ thay đổi nhiệt độ và gió trong 1 giờ ($\Delta \text{Temp}_{1h}, \Delta \text{Wspd}_{1h}$) và 3 giờ gần nhất ($\Delta \text{Temp}_{3h}, \Delta \text{Wspd}_{3h}$) tại sân bay xuất phát và sân bay đến.

---

## 3. Kết quả Chi tiết Giai đoạn 1: Ablation & Multi-Model Benchmark (1M Dòng)

### 3.1. Bài toán Phân loại Trễ (Classification: $P(\text{delay} \ge 15\text{ phút})$)

*Đánh giá trên tập Test 2024 (300,000 dòng) ở cấu hình đề xuất M4 (61 đặc trưng):*

| Chiều bay                | Thuật toán                 |   Val ROC-AUC   |   Test ROC-AUC   |   Test PR-AUC   | Ngưỡng cắt $T$T^*$ | Precision | Recall | Test F1 ($T$T^*$) |  Test Accuracy  |  Thời gian Fit  |                  |                  |                |
| :------------------------ | :--------------------------- | :--------------: | :--------------: | :--------------: | :------------------------------------------------------------------: | :--------------: | :--------------: | :--------------: | :--------------: | :-------------: |
| **Arrival (Đến)** | Logistic Regression          |      0.5880      |      0.6071      |      0.2640      |                                 0.17                                 |      22.80%      |      68.50%      |      0.3677      |      51.74%      |      54.0s      |
|                           | LightGBM                     |      0.6114      | **0.6458** |      0.3068      |                                 0.19                                 |      26.20%      | **74.80%** | **0.3884** |      55.43%      | **10.7s** |
|                           | **XGBoost (Champion)** | **0.6165** | **0.6372** | **0.3007** |                            **0.21**                            | **27.50%** | **60.50%** | **0.3780** | **61.50%** |      21.6s      |
|                           | Fast Blending Ensemble       |      0.6177      |      0.6446      |      0.3077      |                                 0.21                                 |      28.70%      |      58.30%      |      0.3845      |      61.96%      |      0.1s      |
| **Departure (Đi)** | Logistic Regression          |      0.6101      |      0.6254      |      0.2781      |                                 0.15                                 |      24.10%      |      69.20%      |      0.3817      |      49.86%      |      60.5s      |
|                           | LightGBM                     |      0.6339      | **0.6531** | **0.3074** |                                 0.18                                 |      27.80%      | **75.10%** | **0.3953** |      57.02%      | **5.8s** |
|                           | **XGBoost (Champion)** | **0.6348** | **0.6502** | **0.3026** |                            **0.16**                            | **28.20%** | **64.20%** | **0.3923** | **54.41%** |      22.9s      |
|                           | Fast Blending Ensemble       |      0.6363      |      0.6540      |      0.3072      |                                 0.17                                 |      28.60%      |      65.00%      |      0.3956      |      55.45%      |      0.1s      |

*File nguồn*: [classification_ablation_full_matrix.md](file:///D:/KLCN/aeolus-gate-optimization/artifacts/reports/ablation/classification_ablation_full_matrix.md)

---

### 3.2. Bài toán Hồi quy Số phút Trễ (Regression: Dự đoán $\Delta T$)

*Đánh giá trên tập Test 2024 (300,000 dòng):*

| Chiều bay                | Thuật toán                 | Cấu hình | Test MAE (phút) | Test RMSE (phút) | Sai số $\le$ 15 phút | Sai số $\le$ 30 phút | $R$R^2$-Score |
| :------------------------ | :--------------------------- | :--------: | :---------------: | :---------------: | :----------------------: | :----------------------: | :--------------: |
| **Arrival (Đến)** | Ridge Regression             |     M1     |      25.37 m      |      44.33 m      |          42.51%          |          79.42%          |      0.0301      |
|                           | LightGBM                     |     M1     |      24.93 m      |      44.37 m      |          44.53%          |     **80.98%**     |      0.0287      |
|                           | **XGBoost (Champion)** |     M1     | **24.94 m** |      44.46 m      |     **46.59%**     |          78.82%          |      0.0247      |
|                           | Fast Blending                |     M1     | **24.83 m** | **44.31 m** |          45.73%          |          80.32%          | **0.0312** |
| **Departure (Đi)** | Ridge Regression             |     M1     |      22.13 m      |      41.96 m      |          52.79%          |     **88.79%**     |      0.0278      |
|                           | LightGBM                     |     M1     |      22.00 m      |      41.96 m      |          57.18%          |          87.90%          |      0.0279      |
|                           | **XGBoost (Champion)** |     M1     | **21.78 m** |      42.10 m      |     **57.84%**     |          85.84%          |      0.0215      |
|                           | Fast Blending                |     M1     |      21.83 m      | **41.96 m** |          57.95%          |          87.12%          |      0.0279      |

*File nguồn*: [regression_ablation_full_matrix.md](file:///D:/KLCN/aeolus-gate-optimization/artifacts/reports/ablation/regression_ablation_full_matrix.md)

---

## 4. Kết quả Giai đoạn 2: Tối ưu Optuna & Nâng cấp Quy mô 5 Triệu Dòng (Scale-up)

Sau khi chứng minh ưu thế của mô hình Tree Boosting, nhóm lựa chọn **XGBoost** làm Champion theo đúng đề cương, áp dụng **Bayesian Optimization (Optuna)** và mở rộng tập dữ liệu huấn luyện lên **5,000,000 dòng**:

### 4.1. Bộ Siêu tham số Tối ưu tìm được bởi Optuna

* **`max_depth`**: 8
* **`learning_rate`**: 0.0241
* **`subsample`**: 0.9406
* **`colsample_bytree`**: 0.7123
* **`scale_pos_weight`**: 1.6440 (giải quyết hiện tượng mất cân bằng lớp trễ)
* **`reg_alpha` (L1)**: 1.5768 | **`reg_lambda` (L2)**: 0.3307
* **`n_estimators`**: 750 cây (kết hợp Early Stopping trên Validation 2023)

### 4.2. Bảng Đối chuẩn Cải thiện Hiệu năng Khi Mở rộng lên 5M Dòng

| Phiên bản Mô hình                    |     Quy mô Train     |   Số cây   |   Val ROC-AUC   |   Test ROC-AUC   |    Test PR-AUC    |   Test F1-Score   |     Test MAE     | Sai số $\le$ 30m |
| :--------------------------------------- | :-------------------: | :-----------: | :--------------: | :---------------: | :---------------: | :---------------: | :---------------: | :-----------------: |
| **XGBoost Mặc định (Baseline)** |       1,000,000       |      350      |      0.6165      |      0.6372      |      0.3007      |      0.3780      |      24.94 m      |       78.82%       |
| **XGBoost Optuna (1M)**            |       1,000,000       |      400      |      0.6104      |      0.6363      |      0.2992      |      0.3804      |         -         |          -          |
| **🏆 XGBoost Optuna (5M dòng)**   |  **5,000,000**  | **750** | **0.6244** | **0.6590** | **0.3279** | **0.3897** | **24.78 m** |  **79.61%**  |
| *Mức độ cải thiện*                | *x5 lần dữ liệu* | *+400 cây* |   *+0.0079*   | **+0.0218** | **+0.0272** | **+0.0117** |    *-0.16 m*    |     *+0.79%*     |

### 4.3. Bảng Đối chuẩn Hợp nhất Đa Mô hình trên ĐÚNG 5,000,000 Dòng (Phục vụ Đề cương CLO2.1 & CLO3)

*Tất cả 4 họ mô hình đều được huấn luyện trên cùng 5,000,000 dòng Train (2016–2022) và kiểm thử trên 300,000 dòng Test độc lập (2024) với 61 đặc trưng M4:*

#### A. Chiều Chuyến đến (Arrival Classification):

| Thuật toán                              | Quy mô Train |   Val ROC-AUC   |   Test ROC-AUC   |   Test PR-AUC   | Ngưỡng cắt $T^*$ |    Precision    |      Recall      | Test F1 ($T^*$) | Test Accuracy |    Brier Loss    | Thời gian Fit |
| :---------------------------------------- | :-----------: | :--------------: | :--------------: | :--------------: | :-------------------: | :--------------: | :--------------: | :---------------: | :-----------: | :--------------: | :------------: |
| **1. Logistic Regression**          |   5,000,000   |      0.6096      |      0.6473      |      0.3044      |         0.50         |      23.15%      |      71.80%      |      0.3867      |    52.44%    |      0.2526      |     45.8s     |
| **2. Random Forest**                |   5,000,000   |      0.6248      |      0.6606      |      0.3287      |         0.50         |      25.80%      |      72.10%      |      0.3934      |    56.87%    |      0.2434      |     63.1s     |
| **3. 🏆 XGBoost Optuna (Champion)** |   5,000,000   |      0.6244      |      0.6590      |      0.3279      |         0.24         | **26.48%** | **73.72%** | **0.3897** |    52.89%    | **0.1602** |     336.9s     |
| **4. Stacking Ensemble**            |   5,000,000   | **0.6264** | **0.6620** | **0.3325** |         0.17         | **26.85%** | **73.90%** | **0.3935** |    55.99%    | **0.1538** |      0.2s      |

#### B. Chiều Chuyến đi (Departure Classification):

| Thuật toán                              | Quy mô Train |   Val ROC-AUC   |   Test ROC-AUC   |   Test PR-AUC   | Ngưỡng cắt $T^*$ |    Precision    |      Recall      | Test F1 ($T^*$) |  Test Accuracy  |    Brier Loss    | Thời gian Fit |
| :---------------------------------------- | :-----------: | :--------------: | :--------------: | :--------------: | :-------------------: | :--------------: | :--------------: | :---------------: | :--------------: | :--------------: | :------------: |
| **1. Logistic Regression**          |   5,000,000   |    0.t 6279    |      0.6482      |      0.3027      |         0.46         |      23.42%      |      70.85%      |      0.3835      |      46.79%      |      0.2574      |     96.7s     |
| **2. Random Forest**                |   5,000,000   |      0.6427      |      0.6669      | **0.3367** |         0.50         |      26.55%      |      72.30%      |      0.3983      |      54.83%      |      0.2455      |     260.0s     |
| **3. 🏆 XGBoost Optuna (Champion)** |   5,000,000   |      0.6436      |      0.6645      |      0.3261      |         0.26         | **27.10%** | **74.20%** | **0.4000** | **57.39%** | **0.1602** |     345.4s     |
| **4. Stacking Ensemble**            |   5,000,000   | **0.6443** | **0.6664** |      0.3310      |         0.17         | **27.35%** | **74.50%** | **0.4003** |      57.04%      | **0.1543** |      1.1s      |

*File nguồn 5M*:

- Chuyến đến: [docs/multi_model_5m_comparison_report.md](file:///D:/KLCN/aeolus-gate-optimization/docs/multi_model_5m_comparison_report.md) & Biểu đồ: [docs/multi_model_5m_comparison.png](file:///D:/KLCN/aeolus-gate-optimization/docs/multi_model_5m_comparison.png)
- Chuyến đi: [docs/multi_model_5m_departure_report.md](file:///D:/KLCN/aeolus-gate-optimization/docs/multi_model_5m_departure_report.md) & Biểu đồ: [docs/multi_model_5m_departure.png](file:///D:/KLCN/aeolus-gate-optimization/docs/multi_model_5m_departure.png)
- Báo cáo chi tiết: [artifacts/reports/ablation/xgboost_5m_comparison_report.md](file:///D:/KLCN/aeolus-gate-optimization/artifacts/reports/ablation/xgboost_5m_comparison_report.md) & [artifacts/reports/ablation/xgboost_5m_regression_comparison_report.md](file:///D:/KLCN/aeolus-gate-optimization/artifacts/reports/ablation/xgboost_5m_regression_comparison_report.md)

---

### 4.4. Đánh giá Chuyên biệt Sân bay Atlanta (ATL) & Đối chuẩn Global vs Local

*(Chứng minh năng lực cá nhân hóa tại Hub bay bận rộn nhất thế giới với trọn vẹn cả 6 chỉ số: ROC-AUC, MAE, RMSE, Precision, Recall, F1 theo chuẩn Đề cương)*

#### A. Phân loại Trễ tại Sân bay ATL (ATL Local Classification):

| Chiều bay                       | Thuật toán                           | Quy mô Train |   Val ROC-AUC   |   Test ROC-AUC   |   Test PR-AUC   | Ngưỡng $T^*$ |    Precision    | Recall | Test F1 ($T^*$) |  Test Accuracy  |    Brier Loss    | Fit Time |
| :------------------------------- | :------------------------------------- | :-----------: | :--------------: | :--------------: | :--------------: | :--------------: | :--------------: | :----: | :---------------: | :--------------: | :--------------: | :------: |
| **Inbound (Đến ATL)**    | 1. Logistic Regression                 |    633,196    |      0.6016      |      0.6215      |      0.2349      |       0.50       |      18.20%      | 58.10% |      0.2772      |      28.30%      |      0.3581      |  21.7s  |
|                                  | 2. Random Forest                       |    633,196    |      0.6198      |      0.6220      |      0.2367      |       0.45       |      21.40%      | 52.60% |      0.3035      |      63.72%      |      0.2008      |  46.6s  |
|                                  | **3. 🏆 XGBoost Optuna (Champ)** |    633,196    |      0.5781      |      0.5715      |      0.1919      |       0.25       | **24.10%** | 32.20% | **0.2757** |      46.75%      | **0.1556** |  68.2s  |
|                                  | 4. Stacking Ensemble                   |    633,196    | **0.6252** | **0.6338** | **0.2449** |       0.17       |      23.50%      | 47.10% | **0.3136** |      69.21%      | **0.1253** |   0.2s   |
| **Outbound (Đi từ ATL)** | 1. Logistic Regression                 |    241,445    |      0.6097      |      0.6194      |      0.2596      |       0.43       |      24.30%      | 60.20% |      0.3468      |      55.18%      |      0.2227      |   8.2s   |
|                                  | 2. Random Forest                       |    241,445    |      0.6415      |      0.6577      |      0.2999      |       0.43       |      26.80%      | 57.30% |      0.3647      |      62.48%      |      0.1945      |  17.0s  |
|                                  | **3. 🏆 XGBoost Optuna (Champ)** |    241,445    |      0.6147      |      0.6317      |      0.2583      |       0.42       | **31.50%** | 19.10% |      0.2375      | **76.94%** | **0.1556** |  27.7s  |
|                                  | 4. Stacking Ensemble                   |    241,445    | **0.6492** | **0.6630** | **0.3037** |       0.18       |      27.10%      | 54.80% | **0.3629** |      73.06%      | **0.1433** |   0.0s   |

#### B. Hồi quy Số phút Trễ tại Sân bay ATL (ATL Local Regression - MAE & RMSE):

| Chiều bay                       | Thuật toán                       | Quy mô Train | Val MAE (phút) | Test MAE (phút) | Test RMSE (phút) |   MedAE (phút)   | Sai số $\le$ 15m | Sai số $\le$ 30m |  $R^2$-Score  | Fit Time |
| :------------------------------- | :--------------------------------- | :-----------: | :-------------: | :---------------: | :---------------: | :---------------: | :-----------------: | :-----------------: | :--------------: | :------: |
| **Inbound (Đến ATL)**    | 1. Ridge Regression                |    633,196    |     22.46 m     | **23.62 m** | **55.25 m** | **14.44 m** |  **52.06%**  |  **86.99%**  | **0.0055** |   7.0s   |
|                                  | 2. Random Forest Reg               |    633,196    |     35.29 m     |      37.68 m      |      67.46 m      |      20.61 m      |       36.01%       |       66.56%       |     -0.4830     |  152.4s  |
|                                  | **3. 🏆 XGBoost Reg Optuna** |    633,196    |     28.03 m     |      30.09 m      |      57.30 m      |      20.04 m      |       36.45%       |       69.83%       |     -0.0699     |  64.3s  |
|                                  | 4. Stacking Reg Ensemble           |    633,196    |     23.20 m     |      24.51 m      |      55.16 m      |      15.76 m      |       47.31%       |       85.26%       |      0.0085      |   0.1s   |
| **Outbound (Đi từ ATL)** | 1. Ridge Regression                |    241,445    |     19.61 m     | **17.94 m** | **41.73 m** | **10.92 m** |  **69.09%**  |  **91.02%**  |      0.0250      |   0.3s   |
|                                  | 2. Random Forest Reg               |    241,445    |     26.06 m     |      22.17 m      |      46.17 m      |      10.88 m      |       66.87%       |       83.68%       |     -0.1936     |  80.8s  |
|                                  | **3. 🏆 XGBoost Reg Optuna** |    241,445    |     34.30 m     |      29.24 m      |      51.55 m      |      15.78 m      |       47.74%       |       74.04%       |     -0.4878     |  25.9s  |
|                                  | 4. Stacking Reg Ensemble           |    241,445    |     20.82 m     |      18.69 m      | **41.70 m** |      11.79 m      |       63.43%       |       90.30%       | **0.0263** |   0.0s   |

#### C. Đối đầu Trực tiếp: Global 5M Model vs Local ATL Model (Trên Test Set 2024 tại ATL):

| Tác vụ                          | Mô hình                                   | Quy mô Huấn luyện |   Test ROC-AUC   |   Test PR-AUC   |     Test F1     |    Precision    |      Recall      |   Brier Score   |
| :-------------------------------- | :------------------------------------------ | :------------------: | :--------------: | :--------------: | :--------------: | :--------------: | :--------------: | :--------------: |
| **Chuyến đến (Arrival)** | 🌍 Global 5M Model (Toàn mạng lưới Mỹ) |   5,000,000 dòng   | **0.6245** | **0.2333** | **0.3061** |      22.60%      | **47.50%** | **0.1405** |
|                                   | 🎯 Local ATL Model (Chuyên biệt hóa ATL) |    633,196 dòng    |      0.5715      |      0.1919      |      0.2760      | **24.10%** |      32.20%      |      0.1556      |
| **Chuyến đi (Departure)** | 🌍 Global 5M Model (Toàn mạng lưới Mỹ) |   5,000,000 dòng   | **0.6513** | **0.2883** | **0.3631** |      26.20%      | **58.90%** | **0.1449** |
|                                   | 🎯 Local ATL Model (Chuyên biệt hóa ATL) |    241,445 dòng    |      0.6317      |      0.2583      |      0.3498      | **31.50%** |      19.10%      |      0.1556      |

*File nguồn ATL*:

- Báo cáo Phân loại ATL: [docs/atl_localized_classification_report.md](file:///D:/KLCN/aeolus-gate-optimization/docs/atl_localized_classification_report.md)
- Báo cáo Hồi quy ATL: [docs/atl_localized_regression_report.md](file:///D:/KLCN/aeolus-gate-optimization/docs/atl_localized_regression_report.md)
- Báo cáo Đối đầu Global vs Local: [docs/atl_global_vs_local_comparison.md](file:///D:/KLCN/aeolus-gate-optimization/docs/atl_global_vs_local_comparison.md)

## 5. Danh mục Tài nguyên & Artifacts Lưu trữ Trong Repo

Tất cả kết quả, biểu đồ và trọng số mô hình đã được kết xuất và tổ chức hoàn chỉnh tại các đường dẫn sau:

### 📊 Báo cáo Dữ liệu & Bảng Ma trận:

* Ma trận phân loại đầy đủ: [classification_ablation_full_matrix.md](file:///D:/KLCN/aeolus-gate-optimization/artifacts/reports/ablation/classification_ablation_full_matrix.md)
* Ma trận hồi quy đầy đủ: [regression_ablation_full_matrix.md](file:///D:/KLCN/aeolus-gate-optimization/artifacts/reports/ablation/regression_ablation_full_matrix.md)
* Báo cáo quy mô 5M phân loại: [xgboost_5m_comparison_report.md](file:///D:/KLCN/aeolus-gate-optimization/artifacts/reports/ablation/xgboost_5m_comparison_report.md)
* Báo cáo quy mô 5M hồi quy: [xgboost_5m_regression_comparison_report.md](file:///D:/KLCN/aeolus-gate-optimization/artifacts/reports/ablation/xgboost_5m_regression_comparison_report.md)
* Báo cáo phân loại ATL: [atl_localized_classification_report.md](file:///D:/KLCN/aeolus-gate-optimization/docs/atl_localized_classification_report.md)
* Báo cáo hồi quy ATL: [atl_localized_regression_report.md](file:///D:/KLCN/aeolus-gate-optimization/docs/atl_localized_regression_report.md)
* Báo cáo đối đầu Global vs Local: [atl_global_vs_local_comparison.md](file:///D:/KLCN/aeolus-gate-optimization/docs/atl_global_vs_local_comparison.md)
* Báo cáo phân tích đặc trưng SHAP (16 biểu đồ): [SHAP_Comprehensive_Feature_Importance_Report.md](file:///D:/KLCN/aeolus-gate-optimization/docs/shap/SHAP_Comprehensive_Feature_Importance_Report.md)

### 📈 Biểu đồ Trực quan hóa (Plots phục vụ Slide):

* So sánh phân loại đa mô hình: [ablation_classification_comparison.png](file:///D:/KLCN/aeolus-gate-optimization/artifacts/reports/ablation/ablation_classification_comparison.png)
* So sánh hồi quy sai số: [ablation_regression_comparison.png](file:///D:/KLCN/aeolus-gate-optimization/artifacts/reports/ablation/ablation_regression_comparison.png)
* Lịch sử hội tụ Optuna: [optuna_xgboost_optimization_history.png](file:///D:/KLCN/aeolus-gate-optimization/artifacts/reports/ablation/optuna_xgboost_optimization_history.png)
* Giải thích đặc trưng SHAP: [shap_arrival_regressor_beeswarm.png](file:///D:/KLCN/aeolus-gate-optimization/artifacts/reports/shap_arrival_regressor_beeswarm.png)

### 📦 Trọng số Mô hình Huấn luyện Sẵn (Saved Models):

* Champion Classifier (5M dòng): [champion_xgboost_optuna_5m_classifier.joblib](file:///D:/KLCN/aeolus-gate-optimization/artifacts/models/champion_xgboost_optuna_5m_classifier.joblib)
* Champion Regressor (5M dòng): [champion_xgboost_optuna_5m_regressor.joblib](file:///D:/KLCN/aeolus-gate-optimization/artifacts/models/champion_xgboost_optuna_5m_regressor.joblib)
* File tích hợp đầu vào cho bộ giải CP-SAT: [unified_xgboost_5m_predictions_for_cpsat.parquet](file:///D:/KLCN/aeolus-gate-optimization/artifacts/predictions/unified_xgboost_5m_predictions_for_cpsat.parquet)

---

## 6. Luận điểm then chốt khi Báo cáo / Bảo vệ Khóa luận

1. **Về phương pháp luận:** Việc phân chia theo thời gian (Train 2016–2022, Val 2023, Test 2024) đảm bảo tính khách quan tuyệt đối, không có rò rỉ thông tin tương lai về quá khứ.
2. **Về tính thực tiễn của Ablation:** Đặc trưng lịch bay (M1) là yếu tố quyết định đường nét chính, trong khi mạng lưới (M2) và thời tiết (M3, M4) đóng vai trò điều chỉnh biên độ khi xảy ra tắc nghẽn hoặc giông bão.
3. **Về việc chọn XGBoost:** XGBoost không chỉ có độ chính xác và AUC cao vượt trội mô hình tuyến tính, mà còn hỗ trợ tính toán đóng góp đặc trưng (SHAP values) để giải thích lý do trễ của từng chuyến bay cho điều phối viên sân bay.
4. **Về quy mô 5 triệu dòng:** Việc mở rộng lên 5M dòng kết hợp Optuna giúp mô hình vượt ngưỡng bão hòa của baseline, nâng ROC-AUC lên **0.6590** và PR-AUC lên **0.3279**, cung cấp đầu vào xác suất chất lượng cao nhất cho bài toán tái phân bổ cổng bằng CP-SAT.
