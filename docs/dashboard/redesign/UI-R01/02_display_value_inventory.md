# UI-R01 — 02. DISPLAY VALUE INVENTORY & METRIC TRUTHFULNESS AUDIT

## 1. TỔNG QUAN

Báo cáo này cung cấp danh mục kiểm kê đầy đủ toàn bộ các chỉ số hiển thị, thẻ KPI, số đo thống kê và nhãn trạng thái trên tất cả 5 màn hình của dashboard Aeolus. Mỗi giá trị được phân loại rõ ràng:
- **Nguyên nhân phân loại:** Hardcoded / Fallback giả / Truy xuất động từ artifact / Tính toán thời gian thực từ state.
- **Hiện trạng trước sửa đổi (Pre-R01).**
- **Giải pháp xử lý triệt để trong UI-R01.**

---

## 2. BẢNG KIỂM KÊ CHỈ SỐ THEO TỪNG MÀN HÌNH

### 2.1. Page 01: Control Tower (Tổng quan Điều hành)

| Vị trí / Component | Nhãn hiển thị | Giá trị Pre-R01 | Bản chất Pre-R01 | Xử lý Triệt để trong UI-R01 |
| :--- | :--- | :--- | :--- | :--- |
| **Context Bar** | Trạng thái bộ giải | `TỐI ƯU TUYỆT ĐỐI (CP-SAT)` | **SAI NGỮ CẢNH (False Optimality)**: solver chưa hề chạy khi vừa tải trang. | Đổi thành `LỊCH DANH ĐỊNH GỐC (NOMINAL)` nếu chưa có nghiệm; hoặc lấy đúng trạng thái từ `active_run` trong session. |
| **KPI Card 1** | TỔNG CHUYẾN BAY | `{len(flights)} Chuyến` | Động từ scenario | Giữ nguyên (tính động từ scenario). |
| **KPI Card 2** | TRỄ ĐẾN DỰ BÁO | `+18.4 min` (nếu lỗi load) | **HARDCODED FALLBACK**: tự điền 18.4m và 38.2% nếu file lỗi. | Bỏ hoàn toàn fallback. Nếu không có file dự báo, hiển thị `N/A`, `Chưa có dự báo ML`. |
| **KPI Card 3** | XUNG ĐỘT TĨNH | `13 Cặp xung đột` | **HARDCODED STRING**: ghi cứng chuỗi 13 cặp. | **TÍNH TOÁN ĐỘNG**: lặp qua `flights` và phát hiện va chạm không gian - thời gian thực tế trên `nominal_gate_id`. Kịch bản chuẩn 120 chuyến scheduled có 0 va chạm danh định. |
| **KPI Card 4** | TỐI ƯU CP-SAT | `0 Xung đột` | **FALSE OPTIMALITY**: báo 0 xung đột đã giải tỏa khi solver chưa chạy. | **HONEST STATE**: Nếu `active_run is None`, hiển thị `CHƯA CHẠY [NOT_RUN]`, badge `[CHƯA CHẠY]`. Nếu đã chạy, hiển thị `active_run.conflict_count`. |
| **KPI Card 5** | CỔNG ĐỖ TỪ XA | `0 Cổng` | **HARDCODED POST-SOLVER**: tự tuyên bố 0 cổng xa khi chưa chạy solver. | **HONEST STATE**: Nếu `active_run is None`, hiển thị `CHƯA CHẠY [NOT_RUN]`. Nếu đã chạy, hiển thị `active_run.remote_gate_count`. |
| **Bot Card 1** | TURNAROUND SLACK HEALTH | `42 cặp (70%), 14 cặp (23.3%), 4 cặp (6.7%)` | **HARDCODED HTML**: các con số bị ghi chết trong mã HTML tĩnh. | **TÍNH TOÁN ĐỘNG**: phân loại động từ thuộc tính `turnaround_slack_min` của tập `flights`. Toàn bộ 120 chuyến có slack 15m (100% nằm trong khoảng 5–20m). |

---

### 2.2. Page 02: Flight Intelligence (Dự báo Trễ & Học máy)

| Vị trí / Component | Nhãn hiển thị | Giá trị Pre-R01 | Bản chất Pre-R01 | Xử lý Triệt để trong UI-R01 |
| :--- | :--- | :--- | :--- | :--- |
| **Context Bar** | Trạng thái bộ giải | `TỐI ƯU TUYỆT ĐỐI (CP-SAT)` | **SAI NGỮ CẢNH**: trang này chỉ làm ML inference. | Đổi thành `DỰ BÁO HỌC MÁY (ML INFERENCE)`, `is_optimal=False`. |
| **Tab A: Table** | Hãng hàng không | `DL` | **FABRICATED DUMMY DEFAULT**: gán cứng hãng DL cho các chuyến không khớp ID. | Bỏ gán giả; gán nghiêm ngặt `N/A`. |
| **Tab A: Table** | Tuyến bay | `ORD➔ATL` | **FABRICATED DUMMY DEFAULT**: gán cứng tuyến bay ORD-ATL. | Bỏ gán giả; gán nghiêm ngặt `N/A➔N/A`. |
| **Tab A: Table** | Giờ hạ cánh | `08:00` | **FABRICATED DUMMY DEFAULT**: gán cứng phút 480 (08:00). | `sched_arr_time_min=None`; hiển thị dạng chuỗi `N/A`. |
| **Tab B** | Sample Turns | 3 Turnarounds | Dữ liệu mô hình hóa minh họa | Bổ sung caption khai báo rõ ràng đây là mô hình minh họa toán học chuẩn P06. |

---

### 2.3. Page 03: Gate Operations (Điều hành Cổng & Gantt)

| Vị trí / Component | Nhãn hiển thị | Giá trị Pre-R01 | Bản chất Pre-R01 | Ghi chú & Trạng thái |
| :--- | :--- | :--- | :--- | :--- |
| **Context Bar** | Trạng thái bộ giải | Trạng thái từ `active_run` | Lấy từ `active_run` | Thuộc ISSUE-R00-01 (tự chạy solver lúc vào trang); việc gỡ bỏ auto-trigger hoàn toàn được bàn giao cho UI-R02. |
| **Gantt Chart** | Contact & Remote gates | 26 gates | Động từ scenario | Bộ lọc concourse đã giữ lại các cổng rỗng (không xóa nhầm cổng). |

---

### 2.4. Page 04: Optimization Lab (Phòng thí nghiệm Tối ưu)

| Vị trí / Component | Nhãn hiển thị | Giá trị Pre-R01 | Bản chất Pre-R01 | Xử lý Triệt để trong UI-R01 |
| :--- | :--- | :--- | :--- | :--- |
| **Context Bar** | Trạng thái bộ giải | `BENCHMARK SO SÁNH 4 THUẬT TOÁN (VERIFIED)` | `is_optimal=True` | Chuyển `is_optimal=False` vì benchmark là so sánh đa thuật toán. |
| **Scorecard Card 1** | DETERMINISTIC GREEDY | `130.00 pts`, `1.8 ms` | **HARDCODED KPI**: ghi cứng 130.00 pts. | **ĐỒNG BỘ ĐỘNG**: liên kết trực tiếp với dữ liệu aggregate của `GREEDY_STANDALONE` (chi phí thực: `530.19 pts`, runtime: `29.5 ms`). |
| **Scorecard Card 2** | CP-SAT | `130.00 pts`, `65.2 ms` | **HARDCODED KPI**: ghi cứng 130.00 pts. | **ĐỒNG BỘ ĐỘNG**: liên kết trực tiếp với aggregate `CP_SAT_STANDALONE` (chi phí thực: `323.50 pts`, runtime: `3,244.8 ms`). |
| **Scorecard Card 3** | SIMULATED ANNEALING | `130.00 pts`, `182.4 ms` | **HARDCODED KPI**: ghi cứng 130.00 pts. | **ĐỒNG BỘ ĐỘNG**: liên kết trực tiếp với aggregate `SA_STANDALONE` (chi phí thực: `497.56 pts`, runtime: `24,163.9 ms`). |
| **Scorecard Card 4** | HYBRID | `130.00 pts`, `68.5 ms` | **HARDCODED KPI**: ghi cứng 130.00 pts. | **ĐỒNG BỘ ĐỘNG**: liên kết trực tiếp với aggregate `HYBRID_STANDALONE` (chi phí thực: `489.14 pts`, runtime: `34,815.2 ms`). |

---

### 2.5. Page 05: Robustness Lab (Độ vững Monte Carlo)

| Vị trí / Component | Nhãn hiển thị | Giá trị Pre-R01 | Bản chất Pre-R01 | Xử lý Triệt để trong UI-R01 |
| :--- | :--- | :--- | :--- | :--- |
| **Context Bar** | Trạng thái bộ giải | `MONTE CARLO 500 SCENARIOS`, `is_optimal=True` | **FALSE CLAIM**: mô phỏng thống kê không phải là single optimal run. | Đổi thành `is_optimal=False`. |
| **KPI Card 1** | MODE A — CHI PHÍ KỲ VỌNG | Fallback `1,469.2 pts` | Fallback giá trị cứng khi thiếu dict | Sử dụng `view_a.mean_cost` hoặc `N/A`. |
| **KPI Card 2** | MODE B — CHI PHÍ KỲ VỌNG | Fallback `130.7 pts` | Fallback giá trị cứng khi thiếu dict | Sử dụng `view_b.mean_cost` hoặc `N/A`. |
| **KPI Card 3** | SỐ LƯỢT ĐỔI CỔNG TRUNG VỊ | `2.56 lượt` | **SAI NHÃN**: hiển thị số trung bình (mean 2.56) nhưng dán nhãn là trung vị (median). | Đổi tên nhãn chuẩn xác thành `SỐ LƯỢT ĐỔI CỔNG TRUNG BÌNH`. |
| **KPI Card 4** | QUY MÔ KỊCH BẢN KIỂM ĐỊNH | `500 / 500` | Ghi cứng chuỗi | Lấy động từ `n_evaluated / n_requested` trong summary dict. |
| **CHART-12 đến 15** | Phân phối & Hội tụ | Trộn lẫn 1.500 dòng (3 thuật toán) | **MULTI-SOLVER CONTAMINATION**: làm biến dạng phân phối và vết hội tụ. | **LỌC ĐƠN THUẬT TOÁN (SINGLE-SOLVER)**: mặc định lọc `CPSat` (hoặc solver được chọn), ngăn ngừa triệt để việc trộn mẫu. |
