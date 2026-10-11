# UI-R01 — 05. SCIENTIFIC CLAIM AUDIT & THEORETICAL BOUNDS REPORT

## 1. MỤC TIÊU KIỂM TOÁN TÍNH CHÍNH XÁC KHOA HỌC

Trong môi trường phần mềm khoa học hàng không, việc đưa ra các tuyên bố không được kiểm chứng (Unverified claims), nhầm lẫn giữa mốc tham chiếu thực nghiệm với nghiệm tối ưu toán học toàn cục, hoặc khai báo sai trạng thái nghiệm đã được chứng minh (Proven Optimality) là những sai phạm học thuật nghiêm trọng.

Báo cáo này lập hồ sơ kiểm toán và giải pháp khắc phục triệt để đối với các tuyên bố khoa học trong dashboard Aeolus.

---

## 2. KẾT QUẢ KIỂM TOÁN & HÀNH ĐỘNG KHẮC PHỤC

### 2.1. Tuyên bố False CP-SAT Optimality trong Context Bar & Các Trang
- **Hiện trạng Pre-R01:**
  - Component `render_context_bar` ([`dashboard/components/context_bar.py`](file:///D:/Study/Code/Python/Aelous/dashboard/components/context_bar.py)) có giá trị mặc định là `solver_status_text="TỐI ƯU TUYỆT ĐỐI (CP-SAT)"` và `is_optimal=True`.
  - Hậu quả: Ngay khi người dùng mở trang Control Tower (01), Flight Intelligence (02), Optimization Lab (04), hay Robustness Lab (05) mà chưa hề kích hoạt bất kỳ thuật toán giải tối ưu nào, thanh Context Bar ghim trên đầu trang đã vội vã tuyên bố hệ thống đang ở trạng thái "TỐI ƯU TUYỆT ĐỐI (CP-SAT)" với huy hiệu Clearance Green!
- **Khắc phục UI-R01:**
  - Giá trị mặc định của `render_context_bar` được đổi thành `solver_status_text="LỊCH CƠ SỞ (CANONICAL BASELINE)"` và `is_optimal=False`.
  - Trên Page 01: Chỉ hiển thị trạng thái tối ưu nếu `active_run` thực sự tồn tại trong session và khớp với kịch bản hiện hành. Nếu không có run, hiển thị trung thực `LỊCH DANH ĐỊNH GỐC (NOMINAL)`.
  - Trên Page 02: Khai báo đúng bản chất `DỰ BÁO HỌC MÁY (ML INFERENCE)`, `is_optimal=False`.
  - Trên Page 04: Khai báo đúng bản chất `BENCHMARK SO SÁNH 4 THUẬT TOÁN (AUDITED)`, `is_optimal=False`.
  - Trên Page 05: Khai báo đúng bản chất `MONTE CARLO 500 SCENARIOS (EVALUATED & AUDITED)`, `is_optimal=False`.

---

### 2.2. Tuyên bố về Mode C: Perfect Foresight Oracle
- **Hiện trạng Pre-R01:**
  - Một số mô tả sơ bộ đã gọi Mode C là "Nghiệm tối ưu toán học tuyệt đối (Mathematical Global Optimum)" hoặc "Cận dưới toàn cục".
  - Trong thực tế mã nguồn P09, Mode C được tạo ra bằng thuật toán **Deterministic Greedy** chạy trên ma trận thời gian hạ cánh thực tế (Realized times).
- **Khắc phục UI-R01:**
  - Chuẩn hóa lại tên gọi và bản chất học thuật trong `RobustnessView.academic_notes` ([`dashboard/adapters/monte_carlo_adapter.py`](file:///D:/Study/Code/Python/Aelous/dashboard/adapters/monte_carlo_adapter.py)):
    > *"Lưu ý học thuật: Mode C sử dụng thuật toán Deterministic Greedy làm mốc tham chiếu thực tế (Realized Greedy Oracle Baseline). Đây KHÔNG phải là nghiệm tối ưu toán học toàn cục (Mathematical Global Optimum) hay cận dưới lý thuyết tuyệt đối."*
  - Khẳng định tính phi thực tế trong vận hành: Thuộc tính `is_deployable` của Mode C được đóng băng cứng thành `False`.
  - Trên giao diện Page 05, Mode C luôn luôn đi kèm huy hiệu cảnh báo đỏ/hồng nổi bật: `NON-DEPLOYABLE (THEORETICAL BENCHMARK)`.

---

### 2.3. Giải trình Khoa học Finding D1: Tỷ lệ Khả thi 0.0% vs Xung đột Vật lý 74.8%
- **Hiện trạng:**
  - Trong Mode A (Fixed Plan), tỷ lệ khả thi tĩnh (Static Feasibility) được báo cáo là **0.0%** (100% kịch bản không khả thi), trong khi xác suất va chạm vật lý trên cùng cổng chỉ là **74.8%**.
- **Giải trình Toán học chuẩn hóa trên Dashboard:**
  - Đã đưa nguyên lý vào khung lưu ý học thuật của `RobustnessView` và Section 6 của Page 05:
    - Ở 74.8% số kịch bản, có ít nhất hai chuyến bay va chạm không gian - thời gian thực tế trên cùng một vị trí đỗ ống lồng.
    - Ở 25.2% số kịch bản còn lại, dù không có 2 tàu bay nào đỗ đè lên nhau cùng lúc, nhưng thời gian trễ đã ăn mòn toàn bộ khoảng đệm an toàn 15 phút (`buffer_min`), vi phạm ràng buộc phân cách nghiêm ngặt giữa hai lượt phục vụ liên tiếp. Do đó, theo định nghĩa toán học của bài toán quy hoạch tĩnh, 100% kịch bản đều mất tính khả thi tĩnh ban đầu.

---

### 2.4. Giải trình Khoa học Finding D2: Trùng hợp Chi phí Mode B và Mode C (130.73 pts)
- **Hiện trạng:**
  - Chi phí kỳ vọng của Mode B (Reactive Recourse) và Mode C (Oracle Baseline) trong tập 500 kịch bản đều đạt đúng **130.73 pts**.
- **Cảnh báo Bản quyền & Phạm vi:**
  - Đã đưa cảnh báo vào hệ thống: Hiện tượng chi phí Mode B bằng Mode C là do cấu trúc dung lượng cổng tại Hub Atlanta trong kịch bản sóng sáng 120 chuyến có độ linh hoạt đủ lớn để thuật toán tham lam tái phân bổ theo thời gian thực giải tỏa được toàn bộ xung đột mà không phải đẩy thêm chuyến nào ra bãi đỗ xa.
  - Tuyệt đối cấm người thuyết trình hoặc giao diện phát ngôn rằng "Recourse tối ưu ngang bằng Oracle trong mọi trường hợp tổng quát".

---

### 2.5. Niêm phong Dữ liệu Kiểm thử BTS 2024 (Holdout Quarantine)
- **Cam kết đạo đức:**
  - Toàn bộ mô hình học máy và kết quả phân tích trong dashboard Aeolus được huấn luyện và kiểm thử trên tập dữ liệu lịch sử năm 2023.
  - Toàn bộ tập dữ liệu BTS 2024 được niêm phong độc lập (Quarantined Holdout) theo Protocol V4.
  - Thẻ `CÁCH LY 2024: 🔒 KHÓA BẢO VỆ V4` được giữ cố định trên thanh Context Bar ở tất cả các trang nhằm bảo đảm không có hiện tượng rò rỉ dữ liệu (Data Leakage).
