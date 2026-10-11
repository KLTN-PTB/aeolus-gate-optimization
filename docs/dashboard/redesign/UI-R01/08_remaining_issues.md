# UI-R01 — 08. REMAINING ISSUES & DEFERRED WORK REGISTER

## 1. NGUYÊN TẮC PHÂN ĐỊNH RANH GIỚI (PHASE BOUNDARY PRINCIPLES)

Theo điều lệ **UI-R01 v2.0**:
- Mục tiêu duy nhất của UI-R01 là: **Bảo vệ mã nguồn, loại bỏ dữ liệu giả/sai ngữ cảnh, ngăn chặn biểu đồ thống kê sai, chuẩn hóa provenance và ngăn chặn các tuyên bố khoa học không được kiểm chứng.**
- UI-R01 **KHÔNG redesign giao diện toàn diện**.
- UI-R01 **KHÔNG tự ý chuyển sang hoặc triển khai UI-R02**.

Báo cáo này phân loại rõ các vấn đề đã được khắc phục hoàn toàn trong UI-R01 và các vấn đề còn lại được bàn giao có kiểm soát sang **UI-R02** và **UI-R03**.

---

## 2. TRẠNG THÁI DANH MỤC VẤN ĐỀ TỪ UI-R00

| Mã Issue | Tên Vấn đề | Mức độ | Trạng thái sau UI-R01 | Ghi chú & Kế hoạch bàn giao |
| :--- | :--- | :--- | :--- | :--- |
| **ISSUE-R00-01** | Automatic Solver Execution on Page Enter | **P0** | **DEFERRED TO UI-R02** | Thuộc về kiến trúc lifecycle điều hành luồng chạy trang Gate Operations. Việc loại bỏ hoàn toàn auto-run CP-SAT khi mở trang và chuyển sang nút bấm Run rõ ràng sẽ được xử lý trong UI-R02. |
| **ISSUE-R00-02** | Fabricated Prediction Metadata | **P0** | **RESOLVED (ĐÃ KHẮC PHỤC 100%)** | Đã loại bỏ hoàn toàn dummy defaults (DL, ORD, ATL, 480). View models hỗ trợ None và "N/A". Đã kiểm chứng bằng R01-T01..T05. |
| **ISSUE-R00-03** | Monte Carlo Multi-Solver Contamination | **P0** | **RESOLVED (ĐÃ KHẮC PHỤC 100%)** | Đã thêm solver validation guard và selector; cô lập triệt để 500 dòng CP-SAT trên cả 4 biểu đồ Plotly và drill-down. Đã kiểm chứng bằng R01-T10..T16. |
| **ISSUE-R00-04** | Hardcoded KPIs & Static Fallbacks | **P1** | **RESOLVED (ĐÃ KHẮC PHỤC 100%)** | Đã chuyển xung đột danh định (Page 01) thành tính toán động; thẻ tối ưu hiển thị `CHƯA CHẠY [NOT_RUN]`; Page 04 liên kết động với bảng benchmark; Page 05 loại bỏ fallback giả. |
| **ISSUE-R00-05** | False CP-SAT Optimality Claims | **P1** | **RESOLVED (ĐÃ KHẮC PHỤC 100%)** | Context Bar mặc định đổi thành `CANONICAL BASELINE`, `is_optimal=False`. Page 01, 02, 04, 05 chỉ nhận diện optimal khi có run thực sự hợp lệ. |
| **ISSUE-R00-06** | Incomplete Scenario Hash | **P1** | **DEFERRED TO UI-R02** | Mở rộng thuật toán băm SHA-256 để bao trùm ma trận trọng số chi phí và cấu hình solver sẽ được hoàn thiện trong UI-R02 (Scenario & State Refactor). |
| **ISSUE-R00-07** | Inconsistent Mode C Oracle Semantics | **P1** | **RESOLVED (ĐÃ KHẮC PHỤC 100%)** | Đã chuẩn hóa thành "Realized Greedy Oracle Baseline", cấm triển khai thực tế (`is_deployable=False`), dán nhãn non-deployable rõ ràng. |
| **ISSUE-R00-08** | Stale-Result Detection Weakness | **P1** | **DEFERRED TO UI-R02** | Cơ chế so sánh sâu giữa draft config và executed config để kích hoạt stale banner tức thời thuộc kiến trúc State & Service của UI-R02. |
| **ISSUE-R00-09** | Concourse Filter Gate Dropping Risk | **P2** | **MONITORED** | Bộ lọc concourse đã bảo toàn các cổng rỗng trong Gantt chart; sẽ được tối ưu hóa giao diện trong UI-R03. |
| **ISSUE-R00-10** | Presentation vs Research Semantic Inconsistency | **P2** | **RESOLVED (ĐÃ KHẮC PHỤC 100%)** | Nhãn chế độ hiển thị trung thực trên Context Bar, các thẻ drawer inspector phản ánh đúng provenance. |
| **ISSUE-R00-11** | Dense Layout & Small Typography | **P2** | **DEFERRED TO UI-R03** | Cải thiện cỡ chữ, padding thẻ, khoảng cách trực quan và theme CSS nâng cao thuộc scope UI-R03 Visual Redesign. |
| **ISSUE-R00-12** | Lengthy Unstructured Research Blocks | **P2** | **DEFERRED TO UI-R03** | Tổ chức lại cấu trúc layout, accordion và visual hierarchy cho nội dung nghiên cứu sâu thuộc scope UI-R03. |
| **ISSUE-R00-13** | Visual Baseline Screenshots Incomplete | **P2** | **DEFERRED TO POST-AUDIT** | Cần môi trường headless browser / webdriver để tự động chụp screenshot 5 màn hình. Không ảnh hưởng đến data integrity logic. |
| **ISSUE-R00-14** | Inconsistent Monte Carlo Labels (Median vs Mean) | **P2** | **RESOLVED (ĐÃ KHẮC PHỤC 100%)** | Sửa nhãn "SỐ LƯỢT ĐỔI CỔNG TRUNG VỊ" thành "SỐ LƯỢT ĐỔI CỔNG TRUNG BÌNH" trên Page 05. |

---

## 3. PHẠM VI CHÍNH THỨC CỦA CÁC PHASE KẾ TIẾP

### UI-R02 — State, Lifecycle & Scenario Integrity
1. Loại bỏ tự động chạy CP-SAT khi mở trang Gate Operations (ISSUE-R00-01).
2. Chuẩn hóa thuật toán băm Scenario Hash bao hàm toàn bộ cấu hình bài toán (ISSUE-R00-06).
3. Hoàn thiện phát hiện nghiệm lỗi thời Stale-State và quản lý cấu hình nháp / đã thực thi (ISSUE-R00-08).

### UI-R03 — Visual & UX Redesign
1. Tái thiết kế bố cục giao diện 5 trang theo phong cách hàng không cao cấp (Aviation Control Deck).
2. Cải thiện typography, contrast ratio, spacing, và mobile/desktop responsive.
3. Tối ưu biểu đồ Gantt (zoom, pan, gate density).
