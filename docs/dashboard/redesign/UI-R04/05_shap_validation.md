# AEOLUS DASHBOARD — UI-R04
# TREESHAP EXPLAINABILITY & OOF VALIDATION REPORT

**Tài liệu:** `docs/dashboard/redesign/UI-R04/05_shap_validation.md`  
**Giai đoạn:** Phase UI-R04 v2.0  
**Tác giả:** Explainable AI Specialist, Scientific QA Lead  
**Ngày phê duyệt:** 2026-10-11  
**Trạng thái:** VERIFIED & PASSED  

---

## 1. NGUYÊN LÝ KHOA HỌC CỦA TREESHAP TRONG AEOLUS

Hệ thống Aeolus áp dụng thuật toán TreeSHAP (Lundberg et al., Nature Machine Intelligence 2020) để giải thích các dự báo độ trễ của mô hình NGBoost và Gradient Boosting/XGBoost. 

TreeSHAP thỏa mãn các tiên đề toán học khắt khe:
1. **Tính Hiệu quả (Efficiency):**
   $$\sum_{i=1}^{M} \phi_i(x) = f(x) - \mathbb{E}[f(X)]$$
   Tổng các giá trị đóng góp Shapley bằng hiệu số giữa dự báo thực tế và giá trị kỳ vọng nền tảng.
2. **Tính Đối xứng (Symmetry):** Hai đặc trưng có đóng góp tương đương trong mọi liên minh sẽ nhận giá trị Shapley bằng nhau.
3. **Tính Đơn điệu (Monotonicity):** Nếu một mô hình được thay đổi sao cho đóng góp biên của một đặc trưng luôn tăng, giá trị Shapley của đặc trưng đó không bao giờ giảm.

---

## 2. KIỂM ĐỊNH ARTIFACTS TREESHAP

Trong UI-R04, trang Flight Intelligence (Tab C) tải trực tiếp các tệp chứng minh SHAP đã được đóng băng từ giai đoạn huấn luyện:

### 2.1. Đóng góp Toàn cục (Global Feature Importance)
- **Đường dẫn Artifact:** `artifacts/models/inbound_arrival/shap_summary/global_importance.csv`
- **Kết quả Kiểm định:** Tệp tồn tại, gồm 40 đặc trưng được sắp xếp theo `mean_abs_shap` giảm dần.
- **Top 5 Đặc trưng Hàng đầu:**
  1. `CRS_ARR_TIME_MIN`: Khung giờ hạ cánh theo lịch trình (thể hiện đỉnh sóng ùn tắc sân bay).
  2. `DISTANCE`: Khoảng cách bay (phản ánh khả năng tích lũy trễ hoặc bù giờ trên đường bay).
  3. `DEP_DELAY_PRIOR_EST`: Ước lượng trễ cất cánh từ sân bay xuất phát.
  4. `CARRIER_HISTORICAL_MEAN`: Tỷ lệ trễ trung bình lịch sử của hãng hàng không.
  5. `TAIL_DELAY_ROLLING`: Trễ tích lũy trên các chặng bay trước đó của tàu bay.

### 2.2. Phân rã Cục bộ Từng Chuyến bay (Local Case Studies)
- **Đường dẫn Artifact:** `docs/dashboard_discovery/samples/shap_case_studies.json`
- **Kết quả Kiểm định:** Tệp chứa danh sách các trường hợp nghiên cứu điển hình (`On-Time Flight`, `Severe Delay Flight`, `Moderate Delay Flight`).
- **Cấu trúc Mỗi Bản ghi:**
  - `flight_metadata`: Thông tin nhận diện chuyến bay (hãng, số hiệu, tuyến bay).
  - `base_expected_value_minutes`: Giá trị kỳ vọng $\mathbb{E}[f(X)]$.
  - `model_predicted_delay_minutes`: Dự báo $f(x)$.
  - `feature_attributions_ordered`: Mảng các cặp `(feature_name, shap_value)`.
  - `interpretation`: Lời giải thích định tính cho người điều phối bay.

---

## 3. BẢNG ĐÁNH GIÁ KIỂM ĐỊNH NGOÀI MẪU (OOF VALIDATION METRICS)

Khi người dùng kích hoạt **Research Mode**, Tab C hiển thị bảng đánh giá kiểm định chéo Out-Of-Fold (OOF) 5-Fold Stratified Cross-Validation từ tệp `regression_metrics.csv`:

| Tên Mô hình | Họ Thuật toán | Fold | MAE (Phút) | RMSE (Phút) | $R^2$ Score | Trạng thái Chứng chỉ |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| `b5_ngboost_student_t` | NGBoost (Student-t) | 5-Fold | 11.24 | 19.82 | 0.285 | CERTIFIED_PRIMARY (Core Inbound) |
| `departure_xgboost_v1` | Extreme Gradient Boosting | 5-Fold | 12.05 | 21.14 | 0.264 | CERTIFIED_PRIMARY (Core Outbound) |
| `lightgbm_regressor` | LightGBM GBDT | 5-Fold | 11.45 | 20.12 | 0.278 | CERTIFIED_BENCHMARK |
| `random_forest_baseline` | Random Forest | 5-Fold | 13.10 | 22.80 | 0.210 | HISTORICAL_BASELINE |

Toàn bộ dữ liệu hiển thị đều liên kết trực tiếp với các artifacts nghiên cứu chính thức, không có bất kỳ con số nào bị hardcode trong mã giao diện.
