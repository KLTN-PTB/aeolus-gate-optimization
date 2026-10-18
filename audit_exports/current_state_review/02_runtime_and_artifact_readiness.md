# BÁO CÁO KIỂM TOÁN 02: TÍNH SẴN SÀNG CỦA MÔI TRƯỜNG THỰC THI VÀ ARTIFACT CHECKPOINT

**Dự án:** Aeolus Gate Optimization (`aeolus-gate-optimization`)  
**Khóa luận:** Cử nhân Công nghệ Thông tin  
**Thời điểm kiểm toán:** 2026-10-11T15:44:00+07:00  
**Vai trò thẩm định:** Senior Machine Learning Engineer, Forensic Artifact Auditor  

---

## 1. Kiểm kê Checkpoint Mô hình Vật lý (Physical Checkpoint Inventory)

Kiểm toán đã thực hiện quét trực tiếp trên hệ thống tệp, tính toán kích thước, chữ ký băm SHA-256 và kiểm tra khả năng nạp thực tế vào bộ nhớ (load compatibility) thông qua `joblib.load()` trong Python 3.11.

### 1.1. Bảng Chi tiết Checkpoint Đã Xác minh

| Checkpoint Path | Loại Đối tượng (Object Class) | Kích thước (Bytes) | SHA-256 Checksum | Trạng thái Nạp (Load Test) | Vai trò Vận hành |
| :--- | :--- | :---: | :--- | :---: | :--- |
| `artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib` | `src.models.probabilistic.baselines.B5NGBoostStudentT` | 243,595 | `E7E7462F17B65B276EBDEE9C7BECED15E090F69B088A18896D5A91AAA8CB062F` | **PASS** | Role C (Arrival Continuous Simulation Engine) |
| `artifacts/dual_core/models/departure_xgboost_baseline_v1.joblib` | `xgboost.sklearn.XGBRegressor` | 498,135 | `E483DF5FD03CE4D0EEFE7B431FC289B6804589C62EDA17B48FB8051849F4F6E1` | **PASS** | Departure Non-linear Point Champion & SHAP Explainer |
| `artifacts/dual_core/models/departure_tree_preprocessor_v1.joblib` | `src.data.departure_preprocessing.DeparturePreprocessingPipeline` | 207,187 | `CE2BB0F6F0E0ED650DF3AE82306013360DE5C0FAFAC5814307E99DFB69F62017` | **PASS** | Preprocessor cây quyết định Outbound |
| `artifacts/dual_core/models/departure_ridge_baseline_v1.joblib` | `sklearn.linear_model._ridge.Ridge` | 2,217 | `A9A9834AECD1AF10CC3967CB1108C750B200A6802586E5EB41180285CBDE5AAE` | **PASS** | Role A (Departure Point Champion: Ridge) |
| `artifacts/dual_core/models/departure_linear_preprocessor_v1.joblib` | `src.data.departure_preprocessing.DeparturePreprocessingPipeline` | 212,590 | `377A2AEAFBE1969E01EF86038EC6AAD974FD83EE871107E39412DA7D9902E7D2` | **PASS** | Preprocessor tuyến tính Outbound |

*Kết quả kiểm tra mã lệnh:* Lệnh thực thi nạp cả 5 checkpoint bằng Python 3.11 đều trả về Exit Code 0, các lớp đối tượng khớp chính xác với định nghĩa trong mã nguồn.

---

## 2. Thẩm định Tình trạng Mô hình P5 (P5 Quantile Regression Forensic Audit)

Một câu hỏi cốt lõi trong kiểm toán là: **P5 Quantile Regression có checkpoint hay không, và đây là một thiếu sót chưa giải quyết hay là giới hạn đã được phê duyệt chủ động?**

### 2.1. Phát hiện Thực tế
* **Sự tồn tại của tệp:** Trên đĩa **HOÀN TOÀN KHÔNG CÓ** tệp checkpoint serialized trọng số mô hình cho `P5_quantile_regression` (không có tệp `.joblib` hay `.pkl` nào trong `artifacts/probabilistic/` hoặc `artifacts/models/`).
* **Bằng chứng văn bản:**
  * Tại `docs/remediation/00_issue_register.md` (`ISSUE-09`): *"P5 was fitted in earlier research phases and only its evaluation predictions were retained in Parquet/JSON artifacts; the raw model weights were never serialized to disk."*
  * Tại `docs/decisions/decision_registry.md` (Quyết định `D027 - Decoupled Model Selection & Capabilities`): Thiết lập nguyên tắc phân tách vai trò:
    1. **Role A (Point Champion):** Ridge / Ensemble (độ lệch tuyệt đối trung bình tối ưu trên dòng dữ liệu).
    2. **Role B (Marginal Quantile Champion):** `P5_quantile_regression` / `P1_empirical` (đạt CRPS hình thang xấp xỉ thấp nhất là $16.77$ phút, loss pinball $6.82$ phút trên 9 phân vị định trước).
    3. **Role C (Continuous Downstream Engine):** `P4_ngboost_student_t` (có hàm mật độ xác suất liên tục $f(y|x)$ và hỗ trợ lấy mẫu nghịch đảo phân phối cho Monte Carlo).
  * Tại `docs/handover.md`: P5 được phân loại chính thức là **Forecast-only**, không có hàm mật độ liên tục, không hỗ trợ sinh mẫu liên tục và không cần huấn luyện lại.

### 2.2. Kết luận Thẩm định về P5
* Đây là một **giới hạn kiến trúc đã được chủ động phê duyệt (Approved Architectural Boundary)** trong các pha chứng nhận P14/P08, KHÔNG PHẢI là lỗi vô tình bị bỏ quên.
* **Hệ quả vận hành:** P5 **không thể tham gia vào suy luận bản địa trực tiếp (Native Online Inference)** tại thời gian chạy (runtime) mà chỉ có thể hiển thị kết quả từ các tệp dự báo ngoại tuyến đã lưu trữ sẵn trong nghiên cứu lịch sử.

---

## 3. Khả năng Tái lập và Vận hành Ngoại tuyến (Offline Readiness & Reproducibility)

### 3.1. Phụ thuộc Môi trường & Yêu cầu Mạng
* Toàn bộ mã nguồn, dữ liệu huấn luyện, mô hình học máy và bộ giải CP-SAT được lưu trữ cục bộ trên ổ cứng máy tính (`D:\Study\Code\Python\Aelous`).
* Ứng dụng Streamlit Dashboard và các script suy luận đều có khả năng chạy hoàn toàn ở chế độ **OFFLINE** mà không cần kết nối Internet hoặc gọi API bên ngoài (đã kiểm tra qua cờ `--offline` và test `test_r08_t37_offline_startup` PASS).
* Không có phụ thuộc vào các dịch vụ đám mây (Cloud storage, SaaS database hay GPU cluster chuyên biệt). Tất cả thuật toán học máy và CP-SAT đều tương thích CPU 64-bit chuẩn.

### 3.2. Kiểm kê Dung lượng Bộ nhớ Lưu trữ (Storage Footprint)
* **Dữ liệu Thô (`data/raw/tabular/`):** 9 tệp CSV (2016–2024), tổng dung lượng khoảng **14.8 GB** (mỗi năm từ 1.2 GB đến 1.99 GB).
* **Dữ liệu Đã xử lý (`data/processed/`):** Phân vùng Parquet nén cho Inbound và Outbound ATL khoảng **3.2 GB**.
* **Dữ liệu Chuỗi bay (`data/raw/chain/`):** Tensor PyTorch `.pt` theo năm khoảng **450 MB**.
* **Thư mục Bản sao lưu Tạm thời (`backup/`):** Chứa 8 thư mục sao lưu tiền chỉnh sửa giao diện (`ui_r01` đến `ui_r08`), tổng cộng **796 tệp, dung lượng 6.77 MB**. Thư mục này đã được cấu hình loại trừ an toàn trong `.gitignore` để không làm ô nhiễm kho lưu trữ Git.
* **Các Artifact Thực nghiệm (`artifacts/`):** Khoảng **2.1 GB** bao gồm các bảng OOF Parquet, mô hình, cơ sở dữ liệu Optuna SQLite và các báo cáo JSON.
