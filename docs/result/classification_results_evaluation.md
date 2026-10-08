# BÁO CÁO KẾT QUẢ THỰC NGHIỆM MÔ HÌNH PHÂN LOẠI (TABULAR CLASSIFICATION)
**Dự án**: Aeolus Gate Optimization (Tối ưu hóa Phân bổ Cổng Máy bay tại Sân bay Atlanta)  
**File nguồn**: `src/notebooks/tabular_classification_notebook.ipynb`  
**Thời gian hoàn thành**: 03/10/2026 17:00:53  
**Mục tiêu bài toán**: Dự báo xác suất chuyến bay đến bị trễ $\ge 15$ phút (`IS_ARR_DELAY >= 15`) tại thời điểm trước khi cất cánh ($T - 2\text{h}$) phục vụ tính toán Safety Buffer cho bộ giải tối ưu hóa cổng CP-SAT.

---

## 1. TÌNH TRẠNG THỰC THI (EXECUTION STATUS)

* **Trạng thái**: **HOÀN THÀNH 100% THÀNH CÔNG (SUCCESSFUL FULL EXECUTION)**.
* **Đánh giá tổng quan**:
  * Đã khắc phục triệt để lỗi tràn bộ nhớ (`MemoryError`) trước đây nhờ thay thế Scikit-learn Random Forest bằng bộ ba Gradient Boosting chuẩn công nghiệp (**LightGBM**, **XGBoost**, **CatBoost**) kết hợp lấy mẫu an toàn **5,000,000 dòng Train** và **1,000,000 dòng Valid/Test**.
  * Cả 2 bài toán (Đến trễ cốt lõi và Khởi hành trễ đối chứng) cùng mô hình kết hợp **Fast Blending Ensemble** đã hoàn thành trọn vẹn và tự động xuất đầy đủ Artifacts sang thư mục `artifacts/`.

---

## 2. BẢNG TỔNG HỢP KẾT QUẢ SO SÁNH CÁC MÔ HÌNH

Dữ liệu huấn luyện: 5,000,000 dòng Train (2016–2022).  
Tập đánh giá: 1,000,000 dòng Validation (2023) và 1,000,000 dòng Test (2024 - Sealed Holdout).

### Bảng 1: Benchmark Chi tiết Toàn bộ Thuật toán

| Bài toán (Task) | Mô hình (Model) | Thời gian Fit (s) | Val ROC-AUC (2023) | Test ROC-AUC (2024) | Test PR-AUC | Ngưỡng cắt $T^*$ | Test F1 ($T^*$) | Test Acc ($T^*$) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **IS_ARR_DELAY $\ge$ 15 (CỐT LÕI)** | **LightGBM (LGBM)** | **14.6s** | 0.6701 | 0.6710 | 0.3511 | 0.2484 | 0.4056 | 63.78% |
| **IS_ARR_DELAY $\ge$ 15 (CỐT LÕI)** | **XGBoost (XGB)** | 708.0s | **0.6887** | 0.6873 | 0.3723 | 0.3480 | 0.4201 | 65.07% |
| **IS_ARR_DELAY $\ge$ 15 (CỐT LÕI)** | **CatBoost** | 679.9s | 0.6805 | 0.6810 | 0.3634 | 0.5438 | 0.4151 | 63.89% |
| **IS_ARR_DELAY $\ge$ 15 (CỐT LÕI)** | **Logistic Regression** | 6.7s | 0.6615 | 0.6659 | 0.3354 | 0.5669 | 0.4063 | 61.41% |
| **IS_ARR_DELAY $\ge$ 15 (CỐT LÕI)** | **FAST BLENDING ENSEMBLE** | **0.1s** | 0.6885 | **0.6876** | **0.3730** | **0.2054** | **0.4204** | **65.59%** |
| *IS_DEP_DELAY $\ge$ 15 (PHỤ TRỢ)* | *LightGBM (LGBM)* | 42.9s | 0.6825 | 0.6778 | 0.3454 | 0.2574 | 0.4127 | 66.83% |
| *IS_DEP_DELAY $\ge$ 15 (PHỤ TRỢ)* | *XGBoost (XGB)* | 532.2s | **0.6984** | **0.6964** | **0.3766** | 0.3814 | **0.4253** | **68.40%** |

---

## 3. PHÂN TÍCH HIỆU NĂNG MÔ HÌNH KẾT HỢP (FAST BLENDING ENSEMBLE)

### 3.1. Trọng số đóng góp của các Base Model
Mô hình Meta-Learner (`LogisticRegression`) đã học cách kết hợp xác suất từ 3 mô hình cơ sở trên tập Validation (2023) với các trọng số tối ưu:
* **XGBoost**: **`+3.6388`** (Đóng vai trò trụ cột dẫn dắt, chiếm ưu thế áp đảo)
* **CatBoost**: **`+0.8537`** (Bổ trợ đắc lực nhờ khả năng biểu diễn biến phân loại hãng bay/sân bay)
* **LightGBM**: **`+0.1509`** (Cân bằng phân phối dự đoán nhanh)

### 3.2. Điểm nổi bật của Fast Blending
* **Tốc độ huấn luyện siêu tốc**: Chỉ tốn **0.1 giây** nhờ tái sử dụng ma trận dự đoán từ Cache (`PRED_CACHE_CLS`).
* **Độ chính xác toàn diện cao nhất trên tập Test (2024)**:
  * **Test ROC-AUC**: Đạt **`0.6876`** (cao nhất trong toàn bộ các mô hình bài toán Đến trễ).
  * **Test PR-AUC**: Đạt **`0.3730`** (cao nhất).
  * **Test F1-Score**: Đạt **`0.4204`** tại ngưỡng tối ưu $T^* = 0.2054$.
  * **Accuracy**: Đạt **`65.59%`**.

---

## 4. TOP ĐẶC TRƯNG QUAN TRỌNG NHẤT (FEATURE IMPORTANCE)

Phân tích Feature Importance bình quân trên cả 3 mô hình cây (LGBM, XGB, CatBoost) cho thấy:

| Hạng | Tên Đặc Trưng | LGBM (%) | XGB (%) | CatBoost (%) | Trung Bình (%) | Ý Nghĩa Thực Tế |
| :---: | :--- | :---: | :---: | :---: | :---: | :--- |
| **1** | `IS_COVID_PERIOD` | 5.28 | 18.56 | 14.54 | **12.79%** | Tác động bất đối xứng của giai đoạn dịch bệnh 2020 |
| **2** | `WEATHER_SEVERITY_TOTAL` | 7.04 | 10.97 | 5.49 | **7.83%** | Chỉ số thời tiết tổng hợp tại sân bay đi và đến |
| **3** | `OP_CARRIER_CODE` | 11.14 | 1.41 | 8.18 | **6.91%** | Hãng hàng không vận hành chuyến bay |
| **4** | `DEP_HOUR` | 2.64 | 5.72 | 8.65 | **5.67%** | Giờ cất cánh trong ngày (tích tụ trễ dây chuyền) |
| **5** | `HOUR_SIN` | 2.64 | 7.88 | 5.76 | **5.43%** | Đặc trưng chu kỳ giờ trong ngày (Cyclical Encoding) |
| **6** | `ORIGIN_CODE` | 12.32 | 0.70 | 1.07 | **4.70%** | Mã sân bay khởi hành |
| **7** | `DEST_CODE` | 10.12 | 0.69 | 1.62 | **4.14%** | Mã sân bay đến |
| **8** | `D_PRCP` | 7.18 | 3.59 | 1.49 | **4.09%** | Lượng mưa tại sân bay đến |
| **9** | `MONTH_COS` | 3.08 | 2.43 | 5.17 | **3.56%** | Tính mùa vụ trong năm (Seasonal Encoding) |
| **10**| `IS_DEST_RAINY` | 1.17 | 7.24 | 1.42 | **3.27%** | Trạng thái mưa tại sân bay đến |

---

## 5. CÁC ARTIFACTS ĐÃ ĐƯỢC XUẤT THÀNH CÔNG CHO CP-SAT

Hệ thống đã tự động xuất và đóng gói hoàn tất các file artifacts phục vụ bước Tối ưu hóa cổng:

1. **Mô hình Champion (`artifacts/models/champion_arrival_classifier.joblib`)**:
   * Dung lượng: **4.56 MB**.
   * Mô hình được chọn: **XGBoost (XGB)** — được lựa chọn tự động theo tiêu chí nghiêm ngặt **Validation ROC-AUC 2023 cao nhất (0.6887)**.
2. **Metadata Mô hình (`artifacts/models/champion_arrival_classifier_meta.json`)**:
   * Lưu trữ toàn bộ tham số, ngưỡng cắt tối ưu $T^* = 0.3480$, danh sách đặc trưng phục vụ truy xuất.
3. **Bảng xác suất dự báo (`artifacts/predictions/arrival_classification_predictions.parquet`)**:
   * Dung lượng: **6.47 MB**, chứa đầy đủ **1,000,000 dòng** kiểm thử năm 2024.
   * Cột cốt lõi: **`p_arr_delay_15`** — sẵn sàng nạp trực tiếp vào tham số **Safety Buffer** của bộ giải CP-SAT.
4. **Báo cáo tổng kết Metrics (`artifacts/reports/classification_metrics_summary.csv` & `.json`)**:
   * Lưu trữ chi tiết toàn bộ các chỉ số kiểm thử để phục vụ viết luận văn và báo cáo khoa học.
