# AEOLUS DESIGN SYSTEM SPECIFICATION (UI-R03 v2.0)
## Professional Aviation Dark & High-Integrity Presentation Shell

**Phase:** UI-R03 v2.0  
**Status:** IMPLEMENTED & AUDITED  
**Theme:** Professional Aviation Dark  
**Primary Framework:** Streamlit 1.65.0 + Plotly 7.1.0  
**Single Source of Truth:** `dashboard/core/theme_tokens.py`  

---

## 1. Mục tiêu & Nguyên lý Thiết kế (Design Principles)

Aeolus Design System được thiết kế nhằm phục vụ đồng thời hai ngữ cảnh:
1. **Presentation Mode (Bảo vệ luận văn / Trình diễn điều hành):** Giao diện súc tích, độ tương phản cao, KPI rõ ràng, không hiển thị các thông tin nhiễu hoặc các khối debug phức tạp.
2. **Research Mode (Nghiên cứu khoa học & Kiểm toán mô hình):** Cung cấp khả năng thanh tra chuyên sâu (TreeSHAP waterfall, OOF validation metrics, Monte Carlo tail risk, Solver run manifest) một cách có cấu trúc mà không làm vỡ bố cục chung.

### Nguyên lý cốt lõi:
- **Tập trung vào dữ liệu hàng không (Aviation-First):** Màu sắc được chuẩn hóa theo hệ thống đèn tín hiệu và bảng hiển thị điều hành bay (Air Traffic Control & Flight Operations Center).
- **Không nhầm lẫn trạng thái (Dual-Encoding):** Mọi chỉ báo trạng thái (Feasible, Optimal, Stale, Warning, Collision) đều được mã hóa kép bằng cả huy hiệu màu và văn bản/icon tường minh. Tuyệt đối không dùng màu sắc đơn thuần để biểu đạt trạng thái.
- **Dễ đọc trên màn hình lớn & máy chiếu (Accessibility & Legibility):** Xóa bỏ hoàn toàn cỡ chữ 11px trên các nhãn chức năng; thiết lập hệ số tương phản WCAG 2.1 AA tối thiểu 4.5:1 đối với văn bản thông thường và 3:1 đối với văn bản kích thước lớn/thứ cấp.
- **Đồng bộ hóa tuyệt đối (Unified Token Architecture):** Tất cả thành phần Streamlit và biểu đồ Plotly đều chia sẻ chung một nguồn tham chiếu token (`theme_tokens.py`).

---

## 2. Bảng Mã Màu Chuẩn (Color Palette & Semantic Tokens)

| Token Name | Hex Code | Tỉ lệ tương phản (vs Canvas/Surface) | Mục đích sử dụng |
| :--- | :--- | :--- | :--- |
| `COLOR_CANVAS_BG` | `#101B2A` | Background | Nền canvas toàn bộ ứng dụng |
| `COLOR_SURFACE_BG` | `#162338` | Container Base | Nền card, widget containers, Plotly paper |
| `COLOR_SURFACE_ELEVATED` | `#1D2E49` | Elevated Base | Nền hover, tooltip, dropdown popovers |
| `COLOR_BORDER_SUBTLE` | `#263B5C` | 3.2:1 | Đường viền card, ngăn cách phần tử, đường lưới biểu đồ |
| `COLOR_BORDER_ACTIVE` | `#3B5780` | 4.8:1 | Viền khi hover, trục tọa độ biểu đồ |
| `COLOR_BORDER_FOCUS` | `#47C5C0` | 7.5:1 | Vòng nét đứt focus-visible hỗ trợ trợ năng bàn phím |
| `COLOR_ACCENT_PRIMARY` | `#47C5C0` | 8.2:1 (với Canvas) | Aerodrome Cyan / Teal: Tác vụ chính, nút primary, biểu đồ chính |
| `COLOR_ACCENT_SECONDARY`| `#38BDF8` | 7.9:1 (với Canvas) | Runway Sky Blue: Tác vụ phụ, biểu đồ Outbound / Departure |
| `COLOR_ACCENT_GLOW` | `#00D2FF` | 8.8:1 (với Canvas) | Cyan Glow: Điểm nhấn dữ liệu, backward compatibility |
| `COLOR_APRON_REMOTE` | `#A78BFA` | 6.5:1 (với Canvas) | Remote Apron Violet: Phân biệt vị trí bãi đỗ xa (Overflow) |
| `COLOR_STATUS_SUCCESS` | `#34C759` | 6.1:1 (với Surface) | Xanh lục: Nghiệm tối ưu đã chứng minh, kiểm định đạt 100% |
| `COLOR_STATUS_WARNING` | `#E5AD55` | 7.2:1 (với Surface) | Vàng hổ phách: Tham số bị thay đổi (stale), đệm rủi ro trung bình |
| `COLOR_STATUS_ERROR` | `#E47777` | 5.8:1 (với Surface) | Đỏ: Xung đột vật lý (collision), ràng buộc bị vi phạm, lỗi tải |
| `COLOR_STATUS_INFO` | `#47C5C0` | 8.2:1 (với Surface) | Teal: Thông tin vận hành, lịch cơ sở, Dual-Core ML |
| `COLOR_STATUS_NEUTRAL` | `#94A3B8` | 5.1:1 (với Surface) | Xám bạc: Trạng thái chờ, nhãn mô tả phụ |
| `COLOR_TEXT_PRIMARY` | `#F0F4F8` | 11.2:1 (với Canvas) | Văn bản chính, tiêu đề, giá trị dữ liệu |
| `COLOR_TEXT_SECONDARY`| `#94A3B8` | 5.1:1 (với Surface) | Nhãn phụ, đơn vị đo, phụ đề |
| `COLOR_TEXT_MUTED` | `#64748B` | 3.2:1 (với Surface) | Chú thích chân trang, ghi chú toán học mờ |

---

## 3. Thang Đo Typography (Typography Scale)

Aeolus quy định thang đo kích thước phông chữ chặt chẽ, loại bỏ hoàn toàn tình trạng chữ li ti khó đọc:

```
28px (700) ─── Page Title (H1 / PageHeader)
   │
20px (600) ─── Section Title (H2 / SectionHeader)
   │
15px (600) ─── Card Title (H3 / Widget Titles / Plotly Titles)
   │
14px (400) ─── Body Text (Paragraphs, Tables, Form Labels)
   │
13px (500) ─── Secondary Labels (Subtitles, Units, Captions)
   │
12px (600) ─── Badge & Tags (Minimum legal functional font size)
```

### Đặc tính Số học Bảng biểu (Tabular Numerals):
- Mọi giá trị KPI định lượng, thời gian, số chuyến bay và chi phí quyết định đều được ép kiểu `font-variant-numeric: tabular-nums;`.
- Quy chuẩn hiển thị KPI: **30px, 700 weight, màu trắng (`#F0F4F8`) hoặc accent tương ứng**, giúp các chữ số căn hàng dọc chính xác khi dữ liệu cập nhật theo thời gian thực.

---

## 4. Hệ Thống Spacing & Border Radius

- **Radius:**
  - `RADIUS_SM`: `4px` (Pill badges, tag nhỏ).
  - `RADIUS_MD`: `6px` (Buttons, input selectors, dropdowns).
  - `RADIUS_LG`: `8px` (Cards, metrics containers, Plotly containers).
  - `RADIUS_XL`: `12px` (Context bar, modal dialogs).
- **Spacing:**
  - `SPACING_XS`: `4px`
  - `SPACING_SM`: `8px`
  - `SPACING_MD`: `16px`
  - `SPACING_LG`: `24px`
  - `SPACING_XL`: `32px`

---

## 5. CSS Styling Engine Architecture

Toàn bộ CSS tùy biến được tập trung tại `dashboard/components/styles.py` và nạp tự động tại entrypoint `dashboard/app.py`:
- Không viết CSS inline rải rác trong các trang.
- Sử dụng class chuẩn `.aeolus-card`, `.aeolus-kpi-card`, `.aeolus-badge`, `.aeolus-empty-state`.
- Đồng bộ hóa container border gốc của Streamlit thông qua bộ chọn `div[data-testid="stVerticalBlockBorderWrapper"]`.
- Khai báo quy tắc trợ năng bàn phím `:focus-visible` với outline `2px solid #47C5C0`.
