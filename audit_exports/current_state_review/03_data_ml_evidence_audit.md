# BÁO CÁO KIỂM TOÁN 03: KIỂM TOÁN DỮ LIỆU, ĐẶC TRƯNG VÀ BẰNG CHỨNG HỌC MÁY P08 (DATA & ML EVIDENCE AUDIT)

**Dự án:** Aeolus Gate Optimization (`aeolus-gate-optimization`)  
**Khóa luận:** Cử nhân Công nghệ Thông tin  
**Thời điểm kiểm toán:** 2026-10-11T15:44:00+07:00  
**Vai trò thẩm định:** Senior Machine Learning Engineer, Scientific Reproducibility Auditor  

---

## 1. Toàn vẹn Dữ liệu & Phân chia Thời gian (Dataset & Temporal Integrity)

### 1.1. Phân vùng Thời gian và Quy tắc Bảo vệ Tập Holdout
* **Tập Huấn luyện & Phát triển (Development Years):** 2016, 2017, 2018, 2019, 2020, 2021, 2022.
* **Tập Lựa chọn Mô hình (Model Selection Year):** 2023 (Bộ dữ liệu `BTS_OTP_2023_CURATED` tại Hartsfield–Jackson Atlanta International Airport — KATL).
* **Tập Kiểm thử Khóa chặt (Final Holdout Year):** 2024.
* **Kiểm toán Rò rỉ Tập Holdout:** Kiểm toán xác nhận **KHÔNG CÓ** việc sử dụng dữ liệu năm 2024 để tinh chỉnh siêu tham số (HPO), lựa chọn đặc trưng hoặc đưa ra quyết định phương pháp luận. Toàn bộ cấu hình HPO trong `configs/` và test suite đều kích hoạt rào chắn fail-closed từ chối mọi truy cập vào năm 2024 trước khi hoàn tất nghiệm thu.

### 1.2. Bộ lọc Sân bay Trọng điểm (Hub Airport Atlanta ATL)
* **Chiều Đến (Inbound / Core Arrival):** Lọc nghiêm ngặt theo điều kiện `DEST == 'ATL'`.
* **Chiều Đi (Outbound / Core Departure):** Lọc nghiêm ngặt theo điều kiện `ORIGIN == 'ATL'`.
* **Quy mô Dữ liệu:**
  * Dữ liệu toàn quốc năm 2023 chứa ~7.2 triệu chuyến bay.
  * Phân vùng Outbound ATL năm 2023 chứa **332.734 dòng** hợp lệ.
  * Phân vùng Inbound ATL năm 2023 chứa **331.890 dòng** hợp lệ.

### 1.3. Hợp đồng Rào chắn Thời gian (Information Barrier tại Cutoff T-2h)
* Mọi đặc trưng đầu vào phục vụ dự báo phải được ghi nhận và sẵn sàng trước thời điểm:
  $$\tau(X) \le \text{CRS\_DEP\_TIME} - 2\text{ giờ}$$
* **Danh sách Cột Rò rỉ bị Loại bỏ Triệt để (Leaked Columns Dropped):**
  * Không cho phép các biến kết quả thực tế: `ARR_DELAY`, `DEP_DELAY`, `ARR_TIME`, `DEP_TIME`.
  * Không cho phép các mốc vận hành trên mặt đất: `TAXI_IN`, `TAXI_OUT`, `WHEELS_ON`, `WHEELS_OFF`, `ACTUAL_ELAPSED_TIME`, `AIR_TIME`.
  * Không cho phép các cờ trạng thái sau sự cố: `CANCELLED`, `DIVERTED`.
* **Lý do Khoa học cấm sử dụng Dữ liệu Thời tiết (Weather Policy):**
  * Dữ liệu thời tiết thô trong bộ Aeolus (`O_TEMP`, `O_PRCP`, `O_WSPD`, `D_TEMP`, `D_PRCP`, `D_WSPD`) thực chất là quan trắc bề mặt METAR/ASOS được đo tại thời điểm chuyến bay khởi hành hoặc hạ cánh thực tế, KHÔNG PHẢI là bản tin dự báo thời tiết số trị (NWP/HRRR forecast) được phát hành lúc $T-2\text{h}$. Sử dụng các cột này sẽ gây rò rỉ thông tin tương lai nghiêm trọng. Do đó, việc loại bỏ thời tiết là **hoàn toàn chính xác về mặt khoa học**.
* **Lý do Khoa học phong tỏa Chuỗi Hành trình Bay (Flight Chain Policy):**
  * Dữ liệu chuỗi bay tái dựng (`chain_length`, `legs_before_target`, `minutes_from_first_dep`) được nhóm dựa trên toàn bộ lịch bay trong ngày mà không có dấu vết thời gian phát hành chính thức (snapshot timestamp). Việc này có nguy cơ nhìn trước lịch bay tương lai. Do đó, chính sách phong tỏa `BLOCKED_PENDING_NEW_EVIDENCE` là quyết định thận trọng đúng đắn.

---

## 2. Kiểm toán Pháp y Script `scripts/generate_p08_validation_artifacts.py`

Kiểm toán đã phân tích chi tiết từng dòng mã nguồn của `scripts/generate_p08_validation_artifacts.py` để phân định rõ ràng giữa **chỉ số được tính toán thực tế từ dữ liệu** và **chỉ số được gán hằng số (hardcoded)**.

### 2.1. Bảng Phân loại Nguồn gốc Metric trong P08

| Metric / Bảng Dữ liệu | Hàm Sinh trong Script | Phương thức Tạo lập Thực tế | Đánh giá Pháp y |
| :--- | :--- | :--- | :--- |
| **Arrival Baseline Regression/Classification** | `generate_classification_metrics`, `generate_regression_metrics` | Đọc 4 fold OOF Parquet từ `artifacts/model_benchmark_v2/` và tính `roc_auc`, `pr_auc`, `mae`, `rmse`. | **DỰA TRÊN DỮ LIỆU THẬT (DYNAMIC OOF)** |
| **Arrival Tuned Variant (`arrival_xgboost_tuned_v1_1`)** | `generate_classification_metrics` (dòng 107–124) | Chèn trực tiếp từ điển giá trị cố định: `roc_auc: 0.60120`, `pr_auc: 0.19562`, `tp: 240`, `fp: 850`. | **HARDCODED (GÁN CỐ ĐỊNH TỪ BÁO CÁO CŨ)** |
| **Departure Point Models (Ridge, XGBoost)** | `generate_regression_metrics` (dòng 268–298) | Đọc tệp Parquet `departure_point_selection_2023_v1.parquet`, tính MAE, RMSE, sai số phân vị p10–p90. | **DỰA TRÊN DỮ LIỆU THẬT (DYNAMIC 2023)** |
| **Xác suất Trễ Outbound ($P(\text{delay} \ge 15)$)** | `generate_classification_metrics` (dòng 134–136) | Áp dụng công thức biến đổi Sigmoid tùy tiện: $\text{score} = \frac{1}{1 + \exp(-(\hat{y} - 15) / 10)}$. | **HEURISTIC TRANSFORMATION (CHƯA HIỆU CHUẨN)** |
| **Bảng Metric Xác suất (Probabilistic Metrics)** | `generate_probabilistic_metrics` (dòng 311–356) | Chèn danh sách tuple hằng số cố định: P1 ($13.1242$), P2 ($17.9776$), P3 ($17.5544$), P4 ($13.2590$), P5 ($13.1063$). | **HARDCODED (SAO CHÉP TỪ BÁO CÁO LỊCH SỬ)** |
| **Bảng Cắt bỏ Đặc trưng (Feature Ablation)** | `generate_feature_ablation` (dòng 367–420) | Chèn danh sách 3 từ điển cố định: A_tabular ($17.6017$), B_chain ($17.5840$), C_weather ($16.4210$). | **HARDCODED (BẢNG ĐỊNH SẴN, KHÔNG CHẠY LẠI)** |
| **Giải thích Mô hình TreeSHAP** | `generate_shap_outputs` (dòng 428–530) | Nạp mô hình XGBoost thật, tiền xử lý 1.000 dòng dữ liệu thật năm 2023, chạy `shap.TreeExplainer`. | **TÍNH TOÁN THỰC NGHIỆM ĐỘC LẬP (TRUE SHAP)** |

---

## 3. Các Phát hiện Kiểm toán Trọng yếu (Findings Register for ML Evidence)

### FINDING-P1-01: Xác suất Trễ Outbound được Suy diễn bằng Hàm Sigmoid Heuristic thay vì Mô hình Phân loại Độc lập
* **Severity:** `P1 (HIGH)`
* **Expected:** Theo đề cương khóa luận mục 2, hệ thống phải xây dựng mô hình phân loại (Logistic Regression, Random Forest, XGBoost Classifier) để dự báo $P(\text{delay} \ge 15\text{ phút})$.
* **Observed:** Trong `scripts/generate_p08_validation_artifacts.py` (dòng 134–136), xác suất trễ khởi hành không đến từ một mô hình phân loại được huấn luyện hay một hàm phân phối xác suất hiệu chuẩn, mà được tính toán bằng phép xấp xỉ sigmoid tùy tiện từ độ trễ hồi quy:
  $$\hat{P}(\text{delay} \ge 15) \approx \frac{1}{1 + e^{-(\hat{y}_{\text{reg}} - 15.0) / 10.0}}$$
* **Impact:** Metric ROC-AUC và PR-AUC của Departure trong báo cáo P08 phản ánh chất lượng xếp hạng của mô hình hồi quy thông qua hàm đơn điệu chứ không chứng minh hiệu năng của một mô hình phân loại nhị phân độc lập.
* **Proposed Resolution:** Ghi rõ trong phần báo cáo khóa luận rằng đây là điểm số rủi ro chuyển đổi từ hồi quy (risk score mapped from regression), hoặc huấn luyện bổ sung một mô hình phân loại nhị phân thực thụ cho Outbound nếu thời gian cho phép.
* **Confidence:** `HIGH`

### FINDING-P1-02: Bảng Cắt bỏ Đặc trưng Feature Ablation (A/B/C) là Bảng Hằng số Tĩnh
* **Severity:** `P1 (HIGH)`
* **Expected:** Thí nghiệm so sánh Tabular (A), Tabular + Chain (B), Tabular + Chain + Weather (C) theo yêu cầu 4 của đề cương phải có script huấn luyện/kiểm tra chạy trực tiếp trên dữ liệu.
* **Observed:** Tại dòng 367–425 của `scripts/generate_p08_validation_artifacts.py`, toàn bộ số liệu MAE, RMSE, CRPS của 3 kịch bản đều là hằng số được hardcode trực tiếp vào mã nguồn và xuất ra tệp `feature_ablation.csv`.
* **Impact:** Thiếu pipeline tự động hóa đầu-cuối để tái lập lại bảng ablation này từ dữ liệu thô.
* **Proposed Resolution:** Bổ sung ghi chú giải trình trong khóa luận: Bảng thực nghiệm này tổng hợp từ các kết quả nghiên cứu ở giai đoạn Feature Engineering tiền trạm (Week 4/5), được freeze lại làm bằng chứng chính sách (policy evidence) để cấm Weather và Chain do vi phạm rào chắn thời gian.
* **Confidence:** `HIGH`

### FINDING-P2-01: Biến thể Tinh chỉnh HPO Arrival XGBoost được Hardcode trong Bảng Metric
* **Severity:** `P2 (MEDIUM)`
* **Expected:** Mọi dòng trong `classification_metrics.csv` được suy ra từ các tệp dự báo OOF.
* **Observed:** Dòng dữ liệu cho `arrival_xgboost_tuned_v1_1` (dòng 107–124) được hardcode với các hằng số đếm ma trận nhầm lẫn (`tp: 240, fp: 850, tn: 13254, fn: 1656`).
* **Impact:** Không ảnh hưởng đến logic sản xuất hay bộ giải, nhưng làm giảm tính tự động hóa tái lập của riêng bảng phân loại P08.
* **Confidence:** `HIGH`
