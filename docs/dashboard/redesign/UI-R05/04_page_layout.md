# UI-R05: Page Layout & Interactive Workspace Architecture

## 1. Tái Cấu Trúc Bố Cục Không Gian (Spatial Re-architecture)
Trong phiên bản trước, biểu đồ Gantt bị ép vào cột tỉ lệ `[8.5, 3.5]` bên cạnh bảng điều khiển solver. Cách bố trí này khiến vùng hiển thị biểu đồ quá hẹp, các thanh thời gian bị co cụm khó đọc, thanh cuộn ngang xuất hiện thường xuyên và gây khó khăn cho việc quan sát lịch trình sân bay.

UI-R05 tái cấu trúc bố cục thành **Không Gian Làm Việc Trọng Tâm Toàn Chiều Ngang (Full-Width Primary Workspace)**:

```
┌────────────────────────────────────────────────────────────────────────┐
│ 1. HEADER & CONTEXT BAR (Scenario, Hash, Solver Status, Badges)       │
├────────────────────────────────────────────────────────────────────────┤
│ 2. VIEW MODE SELECTOR: [Nominal] | [Optimized] | [Side-by-Side (Res)]  │
├────────────────────────────────────────────────────────────────────────┤
│ 3. COMPACT FILTER TOOLBAR (Concourse, Carrier, ResType, Search, Zoom)  │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│ 4. MASTER INTERACTIVE GANTT WORKSPACE (Full-Width Canvas)              │
│    - Rendered via st.plotly_chart(fig, width="stretch")                │
│    - Dynamic height based on gate count (min 540px)                    │
│                                                                        │
├────────────────────────────────────────────────────────────────────────┤
│ 5. EXPANDABLE LIVE SOLVER CONTROLS (st.expander - Collapsed by default)│
│    - Left: Solver choice, weights/buffers, staleness warning, run btn  │
│    - Right: Execution performance metrics, run digest, fallback badge  │
├────────────────────────────────────────────────────────────────────────┤
│ 6. BOTTOM OPERATIONAL GRID [Columns: 7, 5]                             │
│    - Left (7): FLIGHT INSPECTOR (Dropdown fallback, operational audit) │
│    - Right (5): INDEPENDENT VERIFICATION CARD + CSV/JSON EXPORT BUTTONS │
├────────────────────────────────────────────────────────────────────────┤
│ 7. RESEARCH INSPECTOR (Drawer at bottom - Audit metadata & raw digests)│
└────────────────────────────────────────────────────────────────────────┘
```

## 2. Các Thành Phần Chi Tiết

### A. Compact Filter Toolbar
Đặt gọn gàng trong container viền nhẹ (`st.container(border=True)`), gồm:
- Cột 1 (4/12): Nhóm checkbox concourse đếm động (Concourse T, Concourse A, Remote, Overflow).
- Cột 2 (2/12): Hộp chọn hãng hàng không (ALL + danh sách các hãng trong kịch bản).
- Cột 3 (2/12): Hộp chọn loại tài nguyên (ALL, CONTACT_GATE, FINITE_REMOTE_STAND, UNBOUNDED_OVERFLOW_APRON).
- Cột 4 (4/12): Ô tìm kiếm mã chuyến bay tức thì.
- Thanh trượt thời gian: Zoom cửa sổ hiển thị theo giờ từ nửa đêm.

### B. Master Gantt Canvas
- Chiếm trọn 100% chiều ngang màn hình (`width="stretch"`).
- Tiêu đề sạch sẽ, loại bỏ hoàn toàn các mã kỹ thuật như `(CHART-07)`.
- Thứ tự cổng đảo ngược để cổng đầu tiên ($G\_01$) luôn nằm ở hàng đầu trên cùng.
- Trong Chế độ Nghiên cứu khi chọn "So sánh Song song", hiển thị cả 2 biểu đồ Gantt: Kế hoạch Danh định Gốc ở trên và Kế hoạch Tối ưu ở dưới.

### C. Expandable Live Solver Control Panel
- Sử dụng `st.expander("⚡ BẢNG ĐIỀU KHIỂN BỘ GIẢI TRỰC TIẾP (LIVE SOLVER)", expanded=(active_run is None))`.
- Khi đã có kết quả tối ưu, bảng tự động thu gọn để nhường toàn bộ không gian cho biểu đồ Gantt.
- Tích hợp cảnh báo quy mô kịch bản: cảnh báo nếu số chuyến bay $> 150$.

### D. Bottom Operational Grid
- **Flight Inspector (7/12):** Hiển thị chi tiết chuyến bay được chọn, bao gồm: cổng phân bổ, khung giờ lịch trình, dự báo trễ, cửa sổ chiếm dụng, thời điểm giải phóng (+đệm), đệm slack quay vòng, và các huy hiệu trạng thái (Tái phân bổ, Xung đột, Loại cổng).
- **Independent Verification Card (5/12):** Trực quan hóa kết quả kiểm chứng ràng buộc cứng độc lập từ `verify_hard_constraints_independently`. Nếu là kế hoạch danh định có xung đột, hiển thị thẻ cảnh báo màu đỏ với số lượng vi phạm. Nếu là kế hoạch tối ưu hợp lệ, hiển thị thẻ xanh chứng nhận 0 vi phạm ràng buộc cứng.
- **Nút xuất báo cáo:** Tải phân cổng (CSV) và Tải manifest thực thi (JSON).
