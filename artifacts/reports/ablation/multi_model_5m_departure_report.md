# BÁO CÁO ĐỐI CHUẨN ĐA MÔ HÌNH TRÊN 5,000,000 DÒNG (DEPARTURE CLASSIFICATION)
**Thời gian thực thi**: 2026-10-21 16:52:16  
**Tập dữ liệu**:
- **Train Set**: 5,000,000 dòng (2016–2022)
- **Validation Set**: 300,000 dòng (2023)
- **Test Holdout (Out-of-Time)**: 300,000 dòng (2024)
- **Số lượng đặc trưng**: 61 đặc trưng (M4_Proposed_Full_Dynamics)

| Model                           | Chiều bay      |   Số dòng Train |   Val ROC-AUC |   Test ROC-AUC |   Test PR-AUC |   Ngưỡng T* |   Test F1 (T*) | Test Accuracy   |   Brier Loss |   Fit Time (s) |
|:--------------------------------|:---------------|----------------:|--------------:|---------------:|--------------:|------------:|---------------:|:----------------|-------------:|---------------:|
| 1. Logistic Regression          | Departure (Đi) |       5,000,000 |        0.6279 |         0.6482 |        0.3027 |        0.46 |         0.3835 | 46.79%          |       0.2574 |           96.7 |
| 2. Random Forest                | Departure (Đi) |       5,000,000 |        0.6427 |         0.6669 |        0.3367 |        0.5  |         0.3983 | 54.83%          |       0.2455 |          260   |
| 3. 🏆 XGBoost Optuna (Champion) | Departure (Đi) |       5,000,000 |        0.6436 |         0.6645 |        0.3261 |        0.26 |         0.4    | 57.39%          |       0.1602 |          345.4 |
| 4. Stacking Ensemble            | Departure (Đi) |       5,000,000 |        0.6443 |         0.6664 |        0.331  |        0.17 |         0.4003 | 57.04%          |       0.1543 |            1.1 |
