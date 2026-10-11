# BÁO CÁO KIỂM THỬ BẢO MẬT & PHỤC HỒI LỖI — PHASE P10-F
## Security Auditing, Error Boundaries & Failure Recovery Report

---

## 1. KIỂM TOÁN BẢO MẬT HỆ THỐNG (SECURITY AUDITING)

### A. Chống Duyệt Thư mục Trái phép (Path Traversal Protection)
- **Cơ chế:** Lớp `ArtifactLoader` sử dụng phương thức `_resolve_and_verify_path` để kiểm tra mọi đường dẫn tệp tin đối chiếu với danh sách trắng (`allowlist`) được định nghĩa trong `DashboardConfig`.
- **Thử nghiệm:**
  - Yêu cầu đọc tệp: `loader.load_json("../../../windows/system32/cmd.exe")`.
  - Kết quả: Bị chặn đứng với ngoại lệ `PermissionError: Path traversal or unapproved directory access blocked`.
  - Mã test: `test_group_h_01_path_traversal_blocked` **PASS**.

### B. Khử Sạch Đường dẫn Cục bộ & Khóa Bí mật Hệ thống (Path & Secret Sanitization)
- **Cơ chế:** Hàm `sanitize_provenance_data` trong `dashboard/components/research_inspector.py` tự động quét và lọc:
  - Các ký tự ổ đĩa Windows: `D:\Study\Code\...` -> chỉ giữ lại tên tệp tin tương đối.
  - Các thư mục người dùng Unix: `/home/user/...` -> thay bằng `[REDACTED_LOCAL_PATH]`.
  - Các khóa API, token, mật khẩu: `api_key`, `token`, `secret`, `password` -> lọc bỏ khỏi dictionary hoặc thay bằng `[REDACTED_SECRET]`.
- **Mã test:** `test_group_h_02_path_and_secrets_sanitization` **PASS**.

### C. Ngăn Chặn Tải Mã Python Độc hại (Zero Pickling Ingestion)
- Toàn bộ giao diện Streamlit chỉ nạp dữ liệu qua các định dạng cấu trúc chuẩn: CSV (`pandas.read_csv`), JSON (`json.load`), và Parquet (`pandas.read_parquet`).
- Không cung cấp bất kỳ ô nhập liệu nào cho phép người dùng truyền đường dẫn đến tệp `.pkl` hoặc `.joblib` tùy ý, triệt tiêu hoàn toàn nguy cơ thực thi mã từ xa (RCE).

---

## 2. PHỤC HỒI LỖI & RÀO CHẮN NGOẠI LỆ (ERROR BOUNDARIES & FAULT TOLERANCE)

### A. Tệp Tin Artifact Bị Thiếu hoặc Bị Hỏng
- **Tình huống 1:** Tệp CSV/JSON bị xóa hoặc không tìm thấy trên đĩa.
  - Xử lý: Ném ra ngoại lệ có cấu trúc `ArtifactNotFoundError`. Giao diện hiển thị cảnh báo `st.warning("Hồ sơ kết quả chưa khả dụng trên đĩa")` thay vì làm sập ứng dụng (Crash).
- **Tình huống 2:** Tệp CSV/JSON bị hỏng cú pháp (Corrupt JSON/CSV).
  - Xử lý: Ném ra ngoại lệ `ArtifactValidationError` với thông báo vị trí dòng lỗi cụ thể.
  - Mã test: `test_p10e_26_missing_corrupt_artifact_does_not_crash_whole_app` **PASS**.

### B. Giới Hạn Tải Kịch bản Trực tiếp (Scenario Size Limit Guard)
- **Tình huống:** Người dùng cố tình chạy thuật toán CP-SAT trực tiếp trên kịch bản vượt quá giới hạn an toàn (> 120 chuyến bay).
- **Xử lý:** Lớp `OptimizationService` chặn lại với ngoại lệ `ScenarioSizeLimitExceeded`, hướng dẫn người dùng chuyển sang xem kết quả tiền tính toán để bảo vệ luồng tương tác của giao diện.
- **Mã test:** `test_optimization_service_size_limit_guard` **PASS**.

### C. Bảo Toàn Trạng Thái Phiên & Cách Ly Cache (Session Isolation)
- `CacheService` tạo khóa lưu trữ kết hợp chặt chẽ giữa `scenario_id` + `resource_type` + `param_hash`.
- Khi người dùng chuyển đổi giữa các kịch bản bay, bộ nhớ đệm của kịch bản A tuyệt đối không làm ô nhiễm (cross-contaminate) kết quả của kịch bản B.
- Mã test: `test_foundation.py::test_p10b_14_cache_cannot_cross_contaminate_scenarios` **PASS**.
