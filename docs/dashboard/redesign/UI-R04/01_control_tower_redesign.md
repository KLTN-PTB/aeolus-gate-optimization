# AEOLUS DASHBOARD — UI-R04
# CONTROL TOWER REDESIGN SPECIFICATION & AUDIT

**Tài liệu:** `docs/dashboard/redesign/UI-R04/01_control_tower_redesign.md`  
**Giai đoạn:** Phase UI-R04 v2.0  
**Tác giả:** Principal Scientific Software Engineer, Aviation Operations Specialist  
**Ngày phê duyệt:** 2026-10-11  
**Trạng thái:** COMPLETED & VERIFIED  

---

## 1. MỤC TIÊU & TỔNG QUAN THIẾT KẾ

Trang 01 **Control Tower (Tổng quan Điều hành)** đóng vai trò là bảng điều khiển chỉ huy trung tâm (Executive Cockpit) cho các hoạt động khai thác tại Trung tâm Hàng không Atlanta (ATL). Trước giai đoạn UI-R04, trang này gặp phải những hạn chế nghiêm trọng về tính toàn vẹn khoa học:
1. Số cặp quay vòng bị suy diễn cẩu thả từ công thức `len(flights) // 2`.
2. Biểu đồ sức chứa concourse (`CHART-08`) mặc định bị hardcode số lượng chiếm dụng giả `occupied: 8, occupied: 15` ngay cả khi chưa kích hoạt thuật toán giải.
3. Trạng thái tối ưu hóa có thể hiển thị sai thành `OPTIMAL` hoặc bị đóng khung cố định.
4. Thiếu một Scenario Launcher Banner đồng bộ hiển thị rõ hạ tầng cổng đỗ và chính sách vận hành bãi đỗ xa.

Trong UI-R04, toàn bộ trang 01 đã được tái cấu trúc thành một giao diện điều hành hàng không chuyên nghiệp, loại bỏ 100% dữ liệu bịa đặt và phản ánh đúng nguồn gốc dữ liệu.

---

## 2. CẤU TRÚC GIAO DIỆN MỚI

### 2.1. Scenario Launcher Banner
Đặt tại đầu trang, cung cấp ngữ cảnh tác nghiệp đầy đủ và bất biến:
- **Trung tâm Hàng không:** Hartsfield-Jackson Atlanta International Airport (ATL).
- **Mã Kịch bản:** `SCEN_P09_CANONICAL_120`, `SCEN_2023_PEAK_01`, hoặc `SCEN_P07_DUAL_CORE_30`.
- **Hạ tầng Cổng:** Số cổng ống lồng (Contact Gates) + Bãi đỗ xa (Remote Stands) + Bãi tràn (Overflow Apron).
- **Ngày Khai thác:** 2023-07-15 (chuẩn BTS OTP 2023 curated baseline).
- **Chính sách Sức chứa:** Bãi đỗ xa hữu hạn (Finite Remote Capacity = 1) và Cho phép bãi tràn (Unbounded Overflow Apron).
- **Định danh Dữ liệu (Fingerprint):** SHA-256 Digest hiển thị 16 ký tự đầu để đối soát tính tái lập.

### 2.2. Bốn Thẻ KPI Chỉ huy Tối cao (Primary Executive KPIs)

| Thẻ KPI | Tiêu đề | Giá trị Hiển thị | Phụ đề & Huy hiệu | Tính Trung thực Khoa học |
| :--- | :--- | :--- | :--- | :--- |
| **KPI 1** | LƯỢT TÀU BAY & QUAY VÒNG | `{len(flights)} Lượt bay` | `N/A (Chưa ghép cặp)` hoặc `{N} Cặp quay vòng` | **LOẠI BỎ** `// 2`. Kịch bản đơn lẻ báo `N/A`. |
| **KPI 2** | TÀI NGUYÊN CỔNG ĐỖ | `{contact} Ống lồng + {remote} Đỗ xa` | Sức chứa đỗ xa: 1 tàu bay \| Bãi tràn: Cho phép | Phản ánh chính xác phân bổ hạ tầng từ domain model. |
| **KPI 3** | DỰ BÁO ĐỘ TRỄ ML | `{avg_delay:+.1f} min` | `{pct_ge_15:.1f}% trễ ≥ 15m` | Giữ nguyên dấu âm (vd: `-9.1 min`). Không làm tròn về 0. |
| **KPI 4** | TRẠNG THÁI TỐI ƯU HÓA | `CHƯA CHẠY [NOT_RUN]` hoặc `{SOLVER} ({STATUS})` | Số xung đột & số lượt ra bãi đỗ xa | Tuyệt đối không giả lập `OPTIMAL` khi chưa chạy. |

### 2.3. Hàng Biểu đồ Khai thác (Operational Charts Row)

- **Biểu đồ Hoạt động Khai thác theo Khung giờ (`create_activity_timeline_figure`):**
  - Phân bổ số lượt hạ cánh (Inbound) và cất cánh (Outbound) theo các bin 15 phút.
  - Sử dụng bảng màu chuẩn: *Aerodrome Cyan* cho hạ cánh và *Runway Blue* cho cất cánh.
  - Xử lý mốc thời gian vượt nửa đêm: định dạng `+1d HH:MM` thay vì hiển thị các giờ bất thường `25:00` hay `26:00`.
  - Tiêu đề làm sạch: `BIỂU ĐỒ HOẠT ĐỘNG KHAI THÁC THEO KHUNG GIỜ` (loại bỏ mã kỹ thuật `(CHART-01)`).

- **Biểu đồ Sức chứa Cổng & Khu vực Đỗ (`create_concourse_utilization_figure`):**
  - Tiếp nhận danh sách `gates` thực tế từ kịch bản và `assignments` từ phiên chạy tối ưu đang hoạt động.
  - **Quy tắc Bất biến:** Khi chưa kích hoạt giải thuật (`assignments is None`), toàn bộ số cổng đang sử dụng (`occupied`) **bắt buộc bằng 0**.
  - Không còn hiện tượng bịa đặt 8/10 tại Concourse T hay 15/15 tại Concourse A.

### 2.4. Khu vực Sức khỏe Tác nghiệp & Điều hướng Nhanh
- **Phân bổ Slack Quay vòng (Turnaround Slack Health):**
  - Tính toán động từ các lượt bay hoặc cặp quay vòng thực tế: An toàn (>20m), Rủi ro trung bình (5-20m), Nguy cơ cao (<5m).
  - Với kịch bản chưa ghép cặp (`unpaired`), hiển thị thông báo rõ ràng thay vì giả lập chỉ số 42/14/4.
- **Điều hướng Nhanh (Quick Actions):**
  - Chuyển trang trực tiếp sang *Flight Intelligence* (Dự báo ML) hoặc *Gate Operations* (Điều phối Cổng).

---

## 3. BẢNG SO SÁNH TRƯỚC VÀ SAU REDESIGN

| Hạng mục | Trước UI-R04 (Baseline) | Sau UI-R04 (Redesign Hoàn tất) |
| :--- | :--- | :--- |
| **Cặp quay vòng (Turn Count)** | Tự động tính `len(flights) // 2` cho mọi kịch bản. | Tải từ `turn_pairing_audit.json`; nếu kịch bản không ghép cặp thì báo `N/A`. |
| **Sức chứa Concourse (CHART-08)** | Hardcoded `occupied: 8, occupied: 15`. | Tính động; khi chưa chạy solver thì `occupied = 0` (100% trung thực). |
| **Dự báo Trễ Trung bình** | Ép kiểu dương hoặc lấy mẫu không rõ nguồn gốc. | Tải từ mô hình Dual-Core ML; giữ nguyên độ trễ âm thực tế (vd: `-9.1m`). |
| **Trạng thái Solver KPI** | Dễ gây hiểu nhầm thành CP-SAT OPTIMAL mặc định. | Phản ánh chính xác `CHƯA CHẠY [NOT_RUN]` cho đến khi solver thực sự chạy. |
| **Tiêu đề Biểu đồ** | Chứa mã kỹ thuật thô: `(CHART-01)`, `(CHART-08)`. | Tiêu đề nghiệp vụ sạch, chuẩn Aviation Dark UI. |
| **Timeline Khung giờ** | Nhãn trục hoành có thể lỗi khi chuyến bay qua ngày. | Nhãn chuẩn hóa `+1d HH:MM` khi vượt mốc 1440 phút. |
