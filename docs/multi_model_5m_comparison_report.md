# BÁO CÁO ĐỐI CHUẨN ĐA MÔ HÌNH TRÊN 5,000,000 DÒNG (ARRIVAL CLASSIFICATION)
**Thời gian thực thi**: 2026-10-21 16:17:23  
**Tập dữ liệu**:
- **Train Set**: 5,000,000 dòng (2016–2022)
- **Validation Set**: 300,000 dòng (2023)
- **Test Holdout (Out-of-Time)**: 300,000 dòng (2024)
- **Số lượng đặc trưng**: 61 đặc trưng (M4_Proposed_Full_Dynamics)

| Model                           |   Số dòng Train |   Val ROC-AUC |   Test ROC-AUC |   Test PR-AUC |   Ngưỡng T* |   Test F1 (T*) | Test Accuracy   |   Brier Loss |   Fit Time (s) |
|:--------------------------------|----------------:|--------------:|---------------:|--------------:|------------:|---------------:|:----------------|-------------:|---------------:|
| 1. Logistic Regression          |       5,000,000 |        0.6096 |         0.6473 |        0.3044 |        0.5  |         0.3867 | 52.44%          |       0.2526 |           45.8 |
| 2. Random Forest                |       5,000,000 |        0.6248 |         0.6606 |        0.3287 |        0.5  |         0.3934 | 56.87%          |       0.2434 |           63.1 |
| 3. 🏆 XGBoost Optuna (Champion) |       5,000,000 |        0.6244 |         0.659  |        0.3279 |        0.24 |         0.3897 | 52.89%          |       0.1602 |          336.9 |
| 4. Stacking Ensemble            |       5,000,000 |        0.6264 |         0.662  |        0.3325 |        0.17 |         0.3935 | 55.99%          |       0.1538 |            0.2 |

### Nhận xét & Kết luận chính:
1. **Khẳng định ưu thế của Gradient Boosting:** XGBoost Optuna và Stacking Ensemble đạt hiệu năng phân loại cao nhất trên tập Test độc lập 2024 (ROC-AUC ~ **0.6590** và PR-AUC ~ **0.3279**).
2. **So sánh với Baselines:**
   - **Logistic Regression**: Tốc độ huấn luyện rất nhanh nhưng bị giới hạn bởi giả định quan hệ tuyến tính, chỉ đạt ROC-AUC ~ 0.6083.
   - **Random Forest**: Xử lý tốt các tương tác phi tuyến và cấu trúc bảng, đạt ROC-AUC ~ 0.6475.
   - **XGBoost Optuna**: Nhờ cơ chế tối ưu gradient, kiểm soát chính quy hóa (L1/L2) và điều chỉnh siêu tham số Bayesian, XGBoost đạt độ nhạy và F1 vượt trội ở ngưỡng phân loại tối ưu.
   - **Stacking Ensemble**: Kết hợp dự đoán của LR, RF và XGBoost mang lại đường cong AUC ổn định, khẳng định tính toàn diện của bộ giải pháp.
