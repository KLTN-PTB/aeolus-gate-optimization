# AEOLUS APPLICATION SHELL & NAVIGATION SPECIFICATION (UI-R03 v2.0)
## Robust Navigation, State Isolation & Presentation Shell

**Phase:** UI-R03 v2.0  
**Status:** IMPLEMENTED & AUDITED  
**Entrypoint:** `dashboard/app.py`  

---

## 1. Kiến trúc Application Shell

Aeolus Application Shell được thiết kế theo mô hình desktop-first tối ưu cho màn hình Full HD (1920x1080) và máy chiếu hội đồng. Shell bao gồm hai thành phần cấu trúc chính:
1. **Sidebar cố định bên trái (Persistent Sidebar):** Điều hướng trang, chọn kịch bản vận hành, chuyển đổi chế độ và thẻ thông tin hệ thống.
2. **Main Canvas bên phải:** Chứa Global Context Bar ở trên cùng và phần nội dung động của từng trang được định tuyến theo khóa trang chuẩn hóa (`PageKeys`).

```
┌──────────────────────────────────────┬────────────────────────────────────────────────────────┐
│  ✈️ AEOLUS                           │  ✈️ TRUNG TÂM ĐIỀU HÀNH AEOLUS  |  HARTSFIELD-JACKSON  │
│  FLIGHT OPERATIONS INTELLIGENCE      │  Kịch bản: SCEN_P09_CANONICAL_120 (120 chuyến)         │
├──────────────────────────────────────┼────────────────────────────────────────────────────────┤
│  ĐIỀU HƯỚNG MÀN HÌNH                 │                                                        │
│  (o) 🗼 Control Tower (Tổng quan)    │  PAGE HEADER & KPI ROW (30px Tabular Numerals)         │
│  ( ) 🔬 Flight Intelligence (Dự báo) │  [KPI 1]      [KPI 2]      [KPI 3]      [KPI 4]        │
│  ( ) 🛫 Gate Operations (Phân cổng)  │                                                        │
│  ( ) ⚡ Optimization Lab (Tối ưu)    │  INTERACTIVE CHARTS & TABLES (Plotly / Streamlit Grid) │
│  ( ) 🎲 Robustness Lab (Độ vững)     │  ┌────────────────────────┐  ┌───────────────────────┐ │
├──────────────────────────────────────┤  │ Chart Area Left        │  │ Chart Area Right      │ │
│  KỊCH BẢN VẬN HÀNH (ATL)             │  │ (7 cols / width=stretch)│  │ (5 cols/width=stretch)│ │
│  [SCEN_P09_CANONICAL_120 (120 ch) ▼] │  └────────────────────────┘  └───────────────────────┘ │
├──────────────────────────────────────┤                                                        │
│  CHẾ ĐỘ TRẢI NGHIỆM                  │  RESEARCH INSPECTOR DRAWER                             │
│  [ ] Chế độ Nghiên cứu (Research)    │  [ ▶ KHU VỰC THANH TRA & KIỂM TOÁN KHOA HỌC         ]  │
├──────────────────────────────────────┤                                                        │
│  ● HỆ THỐNG SẴN SÀNG (P10-C)         │                                                        │
│  Hub: Atlanta (ATL) • Năm 2023       │                                                        │
└──────────────────────────────────────┴────────────────────────────────────────────────────────┘
```

---

## 2. Hệ Thống Định Tuyến 5 Trang (Canonical Page Routing)

Tất cả các liên kết điều hướng đều sử dụng `PageKeys` enum từ `dashboard.core.state`:

| Canonical PageKey | Tiêu đề hiển thị | Module xử lý | Vai trò chức năng |
| :--- | :--- | :--- | :--- |
| `01_control_tower` | 🗼 Control Tower (Tổng quan) | `page_01_control_tower` | Bảng điều hành tổng quan, timeline bay, concourse utilization, turnaround slack health |
| `02_flight_intelligence` | 🔬 Flight Intelligence (Dự báo Trễ) | `page_02_flight_intelligence` | Dự báo trễ Inbound/Outbound bằng Dual-Core ML, động lực học quay vòng tàu bay, TreeSHAP |
| `03_gate_operations` | 🛫 Gate Operations (Phân cổng & Gantt) | `page_03_gate_operations` | Biểu đồ Gantt phân cổng tương tác, bảng điều khiển bộ giải trực tiếp, kiểm định độc lập |
| `04_optimization_lab` | ⚡ Optimization Lab (Tối ưu) | `page_04_optimization_lab` | So sánh 4 thuật toán (Greedy, CP-SAT, SA, Hybrid), đường biên Pareto, khả năng mở rộng |
| `05_robustness_lab` | 🎲 Robustness Lab (Độ vững) | `page_05_robustness_lab` | Đánh giá Monte Carlo (n=500 kịch bản ngẫu nhiên), rủi ro đuôi ECDF, kiểm định giả thuyết |

---

## 3. Cách Ly Trạng Thái Kịch Bản (Scenario State Isolation)

Nhằm tuân thủ nguyên tắc an toàn dữ liệu từ UI-R02, khi người dùng thay đổi kịch bản tại Sidebar (`active_scenario_id`):
1. `SessionStateKeys.ACTIVE_RESULT` lập tức được reset về `None`.
2. Toàn bộ các lựa chọn chuyến bay, tàu bay, cổng đỗ (`SELECTED_FLIGHT_ID`, `SELECTED_TURN_ID`, `SELECTED_GATE_ID`) được xóa bỏ.
3. Cờ `IS_SOLUTION_STALE` được đưa về `False`.
4. `JOB_STATE` chuyển về `UIJobState.IDLE`.

Cơ chế này đảm bảo tuyệt đối rằng kết quả gán cổng của một kịch bản 85 chuyến sẽ **không bao giờ** xuất hiện nhầm lẫn dưới tiêu đề kịch bản 120 chuyến.

---

## 4. Phân Biệt Chế Độ Presentation vs Research

- **Presentation Mode (Mặc định):**
  - Giữ lại các thông tin trọng tâm: KPI tổng quan, Gantt tương tác, so sánh kết quả giải thuật.
  - Ẩn các bảng ma trận metrics khổng lồ, ẩn giải thích SHAP chi tiết và ẩn các phân rã sâu không cần thiết cho ban giám khảo thông thường.
  - Context Bar hiển thị huy hiệu màu lam: `● BẢO VỆ / THUYẾT TRÌNH (PRESENTATION)`.
- **Research Mode (Bật qua toggle tại Sidebar):**
  - Mở khóa tab C tại Flight Intelligence (TreeSHAP Waterfall, Global Feature Importance, bảng OOF validation metrics).
  - Mở khóa danh mục toàn bộ 95 lượt chạy thực nghiệm tại Optimization Lab kèm nút xuất bảng CSV.
  - Hiển thị đầy đủ phân rã Monte Carlo từng kịch bản và bảng dữ liệu mẫu tại Robustness Lab.
  - Context Bar hiển thị huy hiệu cảnh báo màu vàng: `● NGHIÊN CỨU (RESEARCH)`.

---

## 5. Tinh Gọn Sidebar (Sidebar Decluttering)

So với baseline trước UI-R03:
- Cỡ chữ nhãn điều hướng và phụ đề được nâng từ **11px lên 12px/13px** rõ ràng.
- Loại bỏ các đoạn văn bản dài dòng gây choán không gian.
- Footer card được đóng khung gọn gàng với viền `#263B5C` và trạng thái `● HỆ THỐNG SẴN SÀNG`.
