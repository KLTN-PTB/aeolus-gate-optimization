# AEOLUS VISUAL BEFORE & AFTER SPECIFICATION (UI-R03 v2.0)
## Component Transformations, DOM Sanitization & Visual QA Protocol

**Phase:** UI-R03 v2.0  
**Status:** IMPLEMENTED — VISUAL QA PENDING HUMAN VERIFICATION  
**Visual Tooling Status:** Playwright / Selenium NOT installed in `.venv` (Zero synthetic screenshots generated)  

---

## 1. Tuyên Bố Trung Thực Về Kiểm Định Thị Giác (Honest Visual QA Disclosure)

> [!IMPORTANT]
> **Tuyên bố Minh bạch Kỹ thuật:**  
> Môi trường thực thi hiện tại (`.venv\Scripts\python.exe`) không cài đặt thư viện browser headless (`playwright`, `selenium`, `pyppeteer`). Nhằm tuân thủ tuyệt đối quy định an toàn của dự án và cam kết trung thực học thuật:
> - **KHÔNG** tự tạo screenshot giả hoặc dùng ảnh placeholder ngụy tạo.
> - **KHÔNG** tự ý cài thêm package lạ ngoài yêu cầu.
> - Trạng thái kiểm định thị giác được phân loại chính thức là **`VISUAL_QA_PENDING`**.
> - Tài liệu này cung cấp ma trận đối chiếu Before/After chi tiết và quy trình kiểm thử thị giác thủ công từng bước (Manual Visual QA Checklist) để người dùng nghiệm thu trực tiếp trên trình duyệt.

---

## 2. Ma Trận Đối Chiếu Trực Quan Before vs After

### 2.1. Thanh Điều Hướng Sidebar (`dashboard/app.py`)
| Đặc điểm | Trước UI-R03 (Baseline) | Sau UI-R03 (Remediated) |
| :--- | :--- | :--- |
| **Typography Tiêu đề & Nhãn** | Nhãn nhỏ 11px mờ nhạt (`font-size: 11px`), khó nhìn trên màn hình cách xa | Tăng lên **12px / 13px**, in hoa, font-weight 600, khoảng cách chữ `0.5px` |
| **Thẻ Logo Thương hiệu** | Cỡ chữ 20px, phụ đề 11px | Nâng lên **22px**, phụ đề 12px chuẩn màu `#94A3B8` |
| **Độ gọn gàng** | Nhiều đoạn văn giải thích dài dòng chiếm diện tích | Bố cục súc tích, phân đoạn rõ ràng bằng thẻ `<hr style='border-color: #263B5C;'>` |
| **Thẻ Footer** | Thẻ viền mỏng xám, chữ 11px | Thẻ viền chuẩn `#263B5C`, bo góc 6px, cỡ chữ 12px, line-height 1.5 |

---

### 2.2. Thanh Ngữ Cảnh Toàn Cục (`dashboard/components/context_bar.py`)
| Đặc điểm | Trước UI-R03 (Baseline) | Sau UI-R03 (Remediated) |
| :--- | :--- | :--- |
| **Độ nhận biết Trang (Page Awareness)** | Luôn hiển thị trạng thái bộ giải (Solver Status), gây hiểu lầm "chưa chạy giải" khi ở trang Flight Intelligence | **Tự động nhận diện trang**: Khi ở trang Flight Intelligence, tự động hiển thị `MÔ HÌNH DỰ BÁO TRỄ: 🔬 DUAL-CORE ML (NGBoost + XGBoost)` |
| **Cỡ chữ Nhãn** | Nhãn nhỏ 11px | Nhãn chuẩn **12px** (tiêu đề nhỏ) và **13px** (thông tin kịch bản/hub) |
| **Huy hiệu Chế độ** | Màu sắc đơn lẻ | Huy hiệu nổi bật có icon: `● BẢO VỆ / THUYẾT TRÌNH (PRESENTATION)` (Xanh lam) hoặc `● NGHIÊN CỨU (RESEARCH)` (Vàng) |

---

### 2.3. Khối Điều Khiển Bộ Giải Trực Tiếp (`page_03_gate_operations.py`)
| Đặc điểm | Trước UI-R03 (Baseline) | Sau UI-R03 (Remediated) |
| :--- | :--- | :--- |
| **Cấu trúc HTML DOM** | Dùng thẻ mở `<div class="aeolus-card">` và đóng `</div>` bao bọc các widget Streamlit tương tác ➔ Gây vỡ DOM | Thay bằng container gốc chuẩn của Streamlit: `with st.container(border=True):` ➔ DOM hoàn toàn chuẩn mực, không lỗi nesting |
| **Nút Run Solver** | Dùng `use_container_width=True` sinh cảnh báo deprecation | Chuyển sang `width="stretch"` chuẩn Streamlit 1.65.0 |
| **Trạng thái Thay đổi Tham số** | Không có thông báo trực quan cụ thể | Huy hiệu cảnh báo rõ ràng: `⚠️ Tham số đã đổi ({keys}) — Nhấn Tối ưu hóa để chạy lại` |

---

### 2.4. Thẻ KPI Điều Hành (`dashboard/components/kpi_card.py`)
| Đặc điểm | Trước UI-R03 (Baseline) | Sau UI-R03 (Remediated) |
| :--- | :--- | :--- |
| **Giá trị Null / Rỗng** | Hiển thị chuỗi `None` hoặc lỗi định dạng | Tự động hiển thị fallback chuẩn **`N/A`** an toàn |
| **Cỡ chữ & Định dạng Số** | 24–28px, chữ số biến thiên độ rộng làm lệch cột | Đạt chuẩn **30px**, áp dụng thuộc tính **`font-variant-numeric: tabular-nums;`** giúp các chữ số thẳng hàng tuyệt đối |
| **Trợ năng** | Thẻ div trơn | Gắn `role="region"` và `aria-label` cho screen reader |

---

### 2.5. Biểu Đồ Plotly Tương Tác (`dashboard/visualizers/theme.py`)
| Đặc điểm | Trước UI-R03 (Baseline) | Sau UI-R03 (Remediated) |
| :--- | :--- | :--- |
| **Tiền tố Tiêu đề (Prefixes)** | Xuất hiện mã code kỹ thuật: `CHART-01:`, `CHART-08:`, v.v. | Tự động loại bỏ bằng bộ lọc regex, giữ lại tiêu đề chuyên nghiệp chuẩn hội đồng |
| **Cỡ chữ Ticks trục X/Y** | 10px – 11px khó đọc | Tối thiểu **12px** trên toàn bộ các biểu đồ |
| **Nền biểu đồ** | Nền canvas và nền card không khớp nhau | Khớp 100% với token: `paper_bgcolor = #162338`, `plot_bgcolor = #101B2A` |

---

## 3. Quy Trình Kiểm Thử Thị Giác Thủ Công (Manual Visual QA Checklist)

Người dùng hoặc kiểm toán viên có thể chạy lệnh sau trong terminal để mở trình duyệt kiểm tra thực tế:
```powershell
d:\Study\Code\Python\Aelous\.venv\Scripts\streamlit run dashboard\app.py
```

### Bảng Kiểm Tra (Checklist 10 Điểm):
- [ ] **1. Sidebar:** Tiêu đề `✈️ AEOLUS` nổi bật, cỡ chữ nhãn điều hướng to rõ (12px), không có chữ li ti 11px.
- [ ] **2. Context Bar:** Nằm cố định ở đầu trang, hiển thị đầy đủ thông tin Hub ATL, kịch bản đang chọn, và chế độ vận hành.
- [ ] **3. Chuyển Trang:** Nhấp chọn lần lượt 5 trang trong radio navigation, trang chuyển mượt mà không có lỗi Exception.
- [ ] **4. Context Bar Page 02:** Chuyển sang `Flight Intelligence`, kiểm tra thấy Context Bar tự động hiển thị `MÔ HÌNH DỰ BÁO TRỄ: DUAL-CORE ML`.
- [ ] **5. Thẻ KPI:** Kiểm tra các thẻ KPI tại Control Tower và Optimization Lab: số liệu to rõ 30px, căn thẳng hàng, không có hiện tượng vỡ khối.
- [ ] **6. Biểu đồ Timeline & Gantt:** Các thanh phân bổ thời gian hiển thị màu sắc tương phản, nền biểu đồ hòa hợp với nền thẻ bao ngoài.
- [ ] **7. Live Solver Box (Page 03):** Hộp điều khiển Live Solver hiển thị viền bo gọn gàng, không bị lỗi thụt lề hay vỡ layout.
- [ ] **8. Thay đổi Tham số (Page 03):** Kéo slider phạt đổi cổng hoặc đệm giãn cách, xuất hiện ngay huy hiệu vàng `⚠️ Tham số đã đổi`.
- [ ] **9. Toggle Chế độ Nghiên cứu:** Bật toggle `Chế độ Nghiên cứu` ở sidebar, huy hiệu Context Bar chuyển sang màu vàng `NGHIÊN CỨU (RESEARCH)`, các tab học thuật (TreeSHAP, Metrics OOF) xuất hiện đầy đủ.
- [ ] **10. Terminal Log:** Quan sát cửa sổ console terminal, xác nhận không xuất hiện bất kỳ cảnh báo `use_container_width is deprecated`.
