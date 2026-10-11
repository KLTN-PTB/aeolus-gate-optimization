# AEOLUS RESPONSIVE GRID & LAYOUT RULES (UI-R03 v2.0)
## Grid Architecture, Column Ratios & Container Boundaries

**Phase:** UI-R03 v2.0  
**Status:** IMPLEMENTED & AUDITED  
**Design Approach:** Desktop-First Responsive Grid  

---

## 1. Nguyên Tắc Phân Bổ Lưới (Grid Principles)

Giao diện Aeolus được xây dựng dựa trên hệ thống lưới cột linh hoạt của Streamlit kết hợp với token giao diện tập trung:
- **Tỉ lệ vàng cho màn hình điều hành:** Sử dụng các cặp tỉ lệ bất đối xứng cân bằng (như `[7, 5]`, `[1.1, 0.9]`, `[1.2, 0.8]`) để ưu tiên hiển thị biểu đồ không gian/thời gian ở cột rộng hơn, trong khi bảng điều khiển hoặc bảng thông số phụ trợ nằm ở cột hẹp hơn.
- **Loại bỏ hoàn toàn lỗi vỡ cấu trúc DOM (HTML Container Anti-Pattern Elimination):**
  - Trước UI-R03, tại `page_03_gate_operations.py`, bảng điều khiển solver controls được bọc bởi thẻ mở `<div class="aeolus-card">` tại dòng 247 và thẻ đóng `</div>` tại dòng 335. Giữa hai thẻ này chứa hàng loạt widget Streamlit tương tác (`st.selectbox`, `st.slider`, `st.checkbox`, `st.button`). Do cơ chế render phân mảnh của React Fiber/Streamlit, việc chèn HTML thô này làm gãy cây DOM, khiến CSS không áp dụng đồng đều và sinh lỗi rendering.
  - Tại UI-R03, cấu trúc trên đã được thay thế triệt để bằng container gốc có viền của Streamlit: `with st.container(border=True):`. Khối này được tự động định kiểu bởi CSS engine qua selector `div[data-testid="stVerticalBlockBorderWrapper"]`.

---

## 2. Ma Trận Tỉ Lệ Cột Trên Từng Trang (Page Column Matrix)

| Trang | Vị trí phân bổ | Tỉ lệ cột | Nội dung cột trái | Nội dung cột phải |
| :--- | :--- | :--- | :--- | :--- |
| **All Pages** | Context Bar | `[4, 2, 2, 2]` | Thông tin Hub & Kịch bản (40%) | Chế độ giao diện (20%), Trạng thái bộ giải/ML (20%), Khóa an toàn 2024 (20%) |
| **Page 01** | Hàng biểu đồ | `[7, 5]` | Timeline hoạt động hạ/cất cánh (CHART-01) | Tỉ lệ sử dụng Concourse (CHART-08) |
| **Page 01** | Hàng tác nghiệp | `[7, 5]` | Phân bổ Slack quay vòng (Turnaround Slack Health) | Điều hướng tác nghiệp nhanh đến Page 02 & 03 |
| **Page 02** | Tab A (Dự báo) | `[7, 5]` | Bảng danh sách chuyến bay & rủi ro | Phân phối độ trễ hạ cánh (Histogram) |
| **Page 02** | Tab C (TreeSHAP)| `[6, 6]` | SHAP Global Feature Importance (Top 8) | SHAP Waterfall phân rã đóng góp cục bộ |
| **Page 03** | Hàng Gantt & Solver| `[7, 5]` | Biểu đồ Gantt phân cổng tương tác | Bảng điều khiển bộ giải trực tiếp (Live Solver) |
| **Page 03** | Hàng chi tiết dưới | `[7, 5]` | Flight Inspector chi tiết chuyến bay đã chọn | Independent Hard-Constraint Verifier |
| **Page 04** | Hàng Pareto & Runtime| `[1.1, 0.9]` | Đường biên tối ưu Pareto (Cost vs Runtime) | Phân rã thời gian giải thuật (Preprocessing vs Core) |
| **Page 04** | Hàng Scalability | `[1.2, 0.8]` | Đường cong mở rộng 100 → 1,500 chuyến | Khối so sánh Sparse Interval vs Dense Grid |
| **Page 05** | Hàng Phân phối | `[1, 1]` | Phân phối chi phí (Mode A vs Mode B vs Oracle) | Hàm phân phối tích lũy thực nghiệm (ECDF) |
| **Page 05** | Hàng Vận hành | `[1, 1]` | Boxplot số lượt đổi cổng & đỗ bãi xa | Đường cong hội tụ kỳ vọng & sai số MCSE |

---

## 3. Quy Tắc Chiều Rộng Biểu Đồ & Widget (Streamlit 1.65.0 Compliance)

Trong phiên bản Streamlit 1.65.0:
- Tham số `use_container_width=True` đã bị **deprecated** trên `st.button`, `st.download_button`, `st.plotly_chart` và `st.dataframe`.
- UI-R03 đã di chuyển toàn bộ 100% các thành phần này sang chuẩn mới:
  - `st.plotly_chart(fig, width="stretch")`
  - `st.dataframe(df, width="stretch")`
  - `st.button(label, width="stretch")`
  - `st.download_button(label, width="stretch")`
- Kết quả: Không còn bất kỳ cảnh báo deprecation nào trong log khi render giao diện.

---

## 4. Ngưỡng Phân Giải Hỗ Trợ (Resolution Guidelines)

- **Độ phân giải tối ưu (Optimal Display):** `1920 × 1080` (Full HD, 100% DPI scaling).
- **Độ phân giải tối thiểu hỗ trợ (Minimum Supported Resolution):** `1366 × 768`.
- **Máy chiếu hội đồng (Projector Presentation):** Đã được hiệu chuẩn hệ số tương phản để các biểu đồ Gantt và thanh phân bổ màu sắc không bị chìm hoặc lóa trên nền tối.
