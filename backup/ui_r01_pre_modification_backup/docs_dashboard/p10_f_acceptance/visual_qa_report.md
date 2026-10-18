# BÁO CÁO KIỂM ĐỊNH THỊ GIÁC & GIAO DIỆN — PHASE P10-F
## Visual Quality Audit & Accessibility Verification Report

**Thiết bị kiểm thử:**
- Màn hình Desktop: 1920×1080 (Full HD, Tỷ lệ 100%)
- Màn hình Laptop: 1366×768 (Tỷ lệ 100% & 125%)
- Trình duyệt: Google Chrome 129+, Microsoft Edge 129+
- Thiết lập Streamlit: Theme Dark cố định (`#101B2A`), Sidebar tự động thu gọn/mở rộng.

---

## 1. BẢNG KIỂM ĐỊNH CHI TIẾT THEO TIÊU CHUẨN THỊ GIÁC

| Tiêu chuẩn Kiểm toán | Chi tiết Xác minh | Trạng thái | Ghi chú Trực quan |
| :--- | :--- | :---: | :--- |
| **Độ tương phản màu sắc (Contrast Ratio)** | Màu văn bản (`#F0F4F8`) trên nền mặt kính (`#162338` & `#101B2A`) đạt chuẩn WCAG AAA (> 7:1) | **PASS** | Chữ hiển thị sắc nét, không lóa mắt trong môi trường tối |
| **Mã hóa Kép (Dual Encoding)** | Trạng thái không chỉ dựa vào màu; có kèm biểu tượng hình học và chữ (Pill Badge) | **PASS** | Xanh (`circle`), Vàng (`diamond`), Tím (`square`), Đỏ (`X`) hỗ trợ người khiếm thị màu |
| **Hiển thị Tiếng Việt (Typography)** | Không lỗi font các ký tự có dấu: `ă, â, đ, ê, ô, ơ, ư`, các dấu ngã/hỏi/nặng | **PASS** | Sử dụng font Inter / Segoe UI mượt mà, không lệch dòng |
| **Bố cục Thẻ KPI (KPI Cards)** | Các con số hiển thị chữ số bảng (tabular figures), không bị tràn ô ở màn hình nhỏ | **PASS** | Giữ tỷ lệ cố định 4 cột trên 1920x1080 và 2 cột trên 1366x768 |
| **Biểu đồ Gantt (Interactive Plotly)** | Thanh chiếm dụng hiển thị rõ ràng, khoảng đệm buffer phân biệt bằng hoa văn/màu nhạt | **PASS** | Tooltip hiển thị đầy đủ Chuyến bay, Cổng, Giờ vào, Giờ rời cổng |
| **Chú thích Trục & Đơn vị đo** | 100% biểu đồ có đơn vị rõ ràng trên trục X và trục Y (`ms`, `pts`, `min`, `lượt`) | **PASS** | Không có đồ thị nào thiếu đơn vị hoặc thiếu nhãn legend |
| **Nhãn Cảnh báo Mode C** | Mode C Oracle có nhãn đỏ `NON-DEPLOYABLE` tại Header, Scorecard và Legend | **PASS** | Nhãn nổi bật, không thể gây hiểu lầm là giải thuật vận hành |
| **Đánh dấu UNKNOWN ở N=1,500** | Ký hiệu chữ X màu đỏ kèm hộp callout nổi bật giải thích quá giới hạn 10s | **PASS** | Không vẽ cột hay giả định nghiệm tối ưu cho bài toán chưa giải được |
| **Thu gọn Research Inspector** | Mặc định đóng gọn ở Presentation Mode, chỉ mở ra khi bật Research Mode | **PASS** | Giữ không gian thuyết trình gọn gàng, không làm phân tâm hội đồng |

---

## 2. KẾT QUẢ XÁC NHẬN TRỰC QUAN 5 TRANG ỨNG DỤNG

1. **Page 01 — Control Tower:**
   - Scorecard 4 chỉ số chính (Tổng chuyến, Đúng giờ dự báo, Xung đột cổng, Trễ TB) cân đối.
   - Hoạt động chuyến bay theo khung giờ 24h và phân phối trễ hiển thị trực quan.
2. **Page 02 — Flight Intelligence:**
   - Đồ thị trễ âm/dương thể hiện rõ các chuyến đến sớm.
   - SHAP Waterfall bóc tách minh bạch đóng góp của từng thuộc tính thời tiết và hãng bay.
3. **Page 03 — Gate Operations:**
   - Gantt tương tác cho phép phóng to, lọc concourse, lọc hãng bay.
   - Nhấp chọn chuyến bay cập nhật tức thì panel thông tin chi tiết (Flight Inspector).
4. **Page 04 — Optimization Lab:**
   - Đường cong Pareto so sánh rõ nét sự đánh đổi giữa thời gian giải và chi phí phạt.
   - Biểu đồ phân rã thời gian tách bạch Build / Search / Validation.
5. **Page 05 — Robustness Lab:**
   - Biểu đồ phân phối chi phí Mode A vs Mode B vs Mode C trực quan, sắc nét.
   - Vết hội tụ Monte Carlo với dải tin cậy $\pm 1.96 \cdot \text{MCSE}$ thu hẹp chuẩn mực.
