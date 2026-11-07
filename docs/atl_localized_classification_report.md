# BÁO CÁO ĐA MÔ HÌNH CHUYÊN BIỆT SÂN BAY ATLANTA (ATL CLASSIFICATION)
**Thời gian thực thi**: 2026-10-21 17:39:00  
**Phương pháp**: Temporal Split (Train 2016–2022, Valid 2023, Test 2024 Out-of-Time)  
**Đặc trưng**: 61 đặc trưng M4_Proposed_Full_Dynamics

| Task              | Chiều bay            | Mô hình                         |   Số dòng Train |   Val ROC-AUC |   Test ROC-AUC |   Test PR-AUC |   Ngưỡng T* |   Test F1 (T*) | Test Accuracy   |   Brier Loss |   Fit Time (s) |
|:------------------|:---------------------|:--------------------------------|----------------:|--------------:|---------------:|--------------:|------------:|---------------:|:----------------|-------------:|---------------:|
| ATL Arrival Cls   | Inbound (Đến ATL)    | 1. Logistic Regression          |          633196 |        0.6016 |         0.6215 |        0.2349 |        0.5  |         0.2772 | 28.30%          |       0.3581 |           21.7 |
| ATL Arrival Cls   | Inbound (Đến ATL)    | 2. Random Forest                |          633196 |        0.6198 |         0.622  |        0.2367 |        0.45 |         0.3035 | 63.72%          |       0.2008 |           46.6 |
| ATL Arrival Cls   | Inbound (Đến ATL)    | 3. 🏆 XGBoost Optuna (Champion) |          633196 |        0.5781 |         0.5715 |        0.1919 |        0.25 |         0.2757 | 46.75%          |       0.1556 |           68.2 |
| ATL Arrival Cls   | Inbound (Đến ATL)    | 4. Stacking Ensemble            |          633196 |        0.6252 |         0.6338 |        0.2449 |        0.17 |         0.3136 | 69.21%          |       0.1253 |            0.2 |
| ATL Departure Cls | Outbound (Đi từ ATL) | 1. Logistic Regression          |          241445 |        0.6097 |         0.6194 |        0.2596 |        0.43 |         0.3468 | 55.18%          |       0.2227 |            8.2 |
| ATL Departure Cls | Outbound (Đi từ ATL) | 2. Random Forest                |          241445 |        0.6415 |         0.6577 |        0.2999 |        0.43 |         0.3647 | 62.48%          |       0.1945 |           17   |
| ATL Departure Cls | Outbound (Đi từ ATL) | 3. 🏆 XGBoost Optuna (Champion) |          241445 |        0.6147 |         0.6317 |        0.2583 |        0.42 |         0.2375 | 76.94%          |       0.1556 |           27.7 |
| ATL Departure Cls | Outbound (Đi từ ATL) | 4. Stacking Ensemble            |          241445 |        0.6492 |         0.663  |        0.3037 |        0.18 |         0.3629 | 73.06%          |       0.1433 |            0   |
