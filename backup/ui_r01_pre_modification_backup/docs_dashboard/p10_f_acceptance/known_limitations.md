# BẢNG TỔNG HỢP CÁC GIỚI HẠN NGHIÊN CỨU & KỸ THUẬT — PHASE P10-F
## Known Limitations, Operational Boundaries & Research Caveats

---

## 1. GIỚI HẠN VỀ MẶT THUẬT TOÁN & BỘ GIẢI TOÁN (SOLVER LIMITATIONS)

1. **Giới hạn Tìm kiếm Incumbent ở Quy mô 1,500 Chuyến bay:**
   - Trong thí nghiệm P06 với kịch bản Mega-Hub (1,500 chuyến bay × 50 tài nguyên cổng hữu hạn + 1 bãi đỗ không giới hạn), CP-SAT khởi tạo thành công mô hình bài toán nhưng không tìm thấy nghiệm hợp lệ đầu tiên (incumbent) trong ngân sách thời gian 10 giây.
   - *Quy cách xử lý:* Hệ thống hiển thị trung thực trạng thái `UNKNOWN`, không công bố đây là bài toán vô nghiệm và không tạo số liệu giả mạo.

2. **Giới hạn Chứng minh Tối ưu của Heuristic:**
   - Các thuật toán Deterministic Greedy và Metaheuristic (Simulated Annealing, Hybrid) có thể tìm ra phương án gán cổng rất nhanh (< 10 ms), nhưng về mặt toán học không thể chứng minh tính tối ưu toàn cục (Optimality Gap không xác định).
   - *Quy cách xử lý:* Các thuật toán này chỉ được gắn nhãn `FEASIBLE (Heuristic)`.

---

## 2. GIỚI HẠN VỀ DỮ LIỆU & MIỀN THỜI GIAN (DATA BOUNDARIES)

1. **Niêm phong Dữ liệu Kiểm định Năm 2024:**
   - Toàn bộ kết quả mô phỏng Monte Carlo và kiểm chứng ML được thực hiện trên lát cắt dữ liệu năm 2023 tại sân bay Atlanta (ATL).
   - Lát cắt dữ liệu năm 2024 được niêm phong hoàn toàn (`Temporal Quarantine`) để phục vụ kiểm định ngoại suy trong tương lai, không được nạp vào ứng dụng dashboard hiện hành.

2. **Quy mô Chạy Trực tiếp (Live Interactive Budget):**
   - Bộ giải toán tương tác trực tiếp trên giao diện chỉ cho phép chạy tối đa **120 chuyến bay**.
   - Các bài toán quy mô lớn hơn (300, 500, 1,000 chuyến bay) được đọc từ kết quả tiền tính toán để đảm bảo giao diện Streamlit không bị treo phản hồi.

---

## 3. GIỚI HẠN VỀ Ý NGHĨA KHOA HỌC (SCIENTIFIC CAVEATS)

1. **Tính Không Triển khai của Mode C (Non-Deployability):**
   - Mode C Oracle đạt chi phí thấp vì sử dụng thông tin tương lai (perfect foresight). Đây là mốc chặn lý thuyết, hoàn toàn không có khả năng triển khai thực tế trong điều hành bay.

2. **Đơn vị Chi phí là Điểm Phạt Quyết định (Decision Cost Points):**
   - Hàm mục tiêu tối ưu sử dụng điểm phạt toán học (`w_pref=10.0, w_remote=200.0, w_conflict=1000.0`). Các giá trị chi phí hiển thị là `Cost Points`, không quy đổi trực tiếp thành số tiền thiệt hại USD thương mại.
