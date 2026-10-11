# AEOLUS COMPONENT CONTRACTS SPECIFICATION (UI-R03 v2.0)
## Standardized Presentation & State Isolation Components

**Phase:** UI-R03 v2.0  
**Status:** IMPLEMENTED & AUDITED  
**Module Location:** `dashboard/components/`  

---

## 1. Danh mục Thành phần Chuẩn hóa (Standard Component Catalog)

Tất cả thành phần giao diện dùng chung trong Aeolus tuân thủ nghiêm ngặt các hợp đồng dữ liệu, ngăn ngừa lỗi runtime khi gặp giá trị null/rỗng, và bảo toàn trải nghiệm nhất quán trên cả 5 trang.

```
dashboard/components/
├── common.py                 # PageHeader, SectionHeader, EmptyState, ErrorState, StatusIndicator
├── context_bar.py            # Global Scenario Context Bar (Pinned top navigation context)
├── kpi_card.py               # Standardized Executive KPI Card with tabular numerals
├── research_inspector.py     # Research Inspector Drawer & JSON audit export
└── styles.py                 # Centralized CSS stylesheet injector
```

---

## 2. Hợp đồng Chi tiết Từng Thành phần (Component Contracts)

### 2.1. `render_kpi_card` (`dashboard/components/kpi_card.py`)
Hiển thị chỉ số điều hành then chốt với giá trị số nổi bật, tiêu đề, phụ đề và huy hiệu phân loại trạng thái.

- **Chữ ký hàm:**
  ```python
  def render_kpi_card(
      title: str,
      value: Any,
      subtitle: Optional[str] = None,
      badge_text: Optional[str] = None,
      badge_type: str = "info",
      status: Optional[str] = None,
      help_text: Optional[str] = None,
  ) -> None
  ```
- **Hợp đồng & Xử lý An toàn:**
  - `value`: Nếu nhận giá trị `None` hoặc chuỗi rỗng `""`, thành phần tự động fallback về hiển thị `"N/A"`, ngăn chặn việc hiển thị `None` hay lỗi sập trang.
  - `tabular-nums`: Lớp CSS `.tabular-nums` được áp dụng trực tiếp lên phần tử giá trị (30px), ngăn ngừa hiện tượng dịch chuyển layout khi các chữ số nhảy liên tục.
  - `help_text`: Gắn vào thuộc tính `title` HTML của thẻ tiêu đề và hiển thị icon `ℹ️` nếu có.
  - `aria-label`: Thẻ bọc ngoài gắn thuộc tính `role="region"` và `aria-label="{title}"` phục vụ trợ năng.

---

### 2.2. `render_context_bar` (`dashboard/components/context_bar.py`)
Thanh trạng thái gắn cố định trên đầu trang phản ánh toàn bộ ngữ cảnh vận hành của hệ thống.

- **Chữ ký hàm:**
  ```python
  def render_context_bar(
      context: Optional[ScenarioContext] = None,
      solver_status_text: str = "LỊCH CƠ SỞ (CANONICAL BASELINE)",
      is_optimal: bool = False,
      show_solver_status: Optional[bool] = None,
      scenario_id: Optional[str] = None,
      current_page_key: Optional[str] = None,
  ) -> None
  ```
- **Hợp đồng & Xử lý An toàn:**
  - `context`: Nếu là `None`, tự động sử dụng kịch bản mặc định `SCEN_P09_CANONICAL_120`.
  - `show_solver_status`: Nếu là `False`, hoặc khi người dùng đang ở trang `02_flight_intelligence` (nơi không chạy bộ giải gán cổng), thanh ngữ cảnh tự động chuyển đổi từ hiển thị bộ giải sang hiển thị **"MÔ HÌNH DỰ BÁO TRỄ: DUAL-CORE ML (NGBoost + XGBoost)"**. Điều này ngăn chặn triệt để lỗi logic báo "Solver unrun" ở trang dự báo độ trễ.
  - Typography: Nhãn phụ đề kích thước $\ge 12\text{px}$ và $13\text{px}$, không sử dụng nhãn 11px.

---

### 2.3. `render_page_header` (`dashboard/components/common.py`)
Tiêu đề đầu trang chuẩn hóa theo thang đo 28px, kèm huy hiệu ngữ cảnh và icon tùy chọn.

- **Chữ ký hàm:**
  ```python
  def render_page_header(
      title: str,
      subtitle: Optional[str] = None,
      badge_text: Optional[str] = None,
      badge_type: str = "info",
      icon: Optional[str] = None,
      badge_status: Optional[str] = None,
  ) -> None
  ```
- **Hợp đồng & Xử lý An toàn:**
  - `badge_status`: Hỗ trợ alias linh hoạt thay thế `badge_type`.
  - `title`: Hiển thị bằng thẻ `<h1>` với class `.aeolus-page-title` và font-weight 700.

---

### 2.4. `render_section_header` (`dashboard/components/common.py`)
Tiêu đề phân đoạn cấp 2 (20px), phân tách trực quan các luồng công việc trên trang.

- **Chữ ký hàm:**
  ```python
  def render_section_header(
      title: str,
      subtitle: Optional[str] = None,
      badge_text: Optional[str] = None,
      badge_type: str = "info",
      description: Optional[str] = None,
      divider: bool = False,
  ) -> None
  ```
- **Hợp đồng & Xử lý An toàn:**
  - Chấp nhận `description` thay cho `subtitle` nếu caller sử dụng tên biến này.
  - Nếu `divider=True`, tự động chèn đường ngăn cách mảnh `<hr>` màu `#263B5C`.

---

### 2.5. `render_empty_state` (`dashboard/components/common.py`)
Trạng thái rỗng khi bộ lọc không có dữ liệu hoặc solver chưa được thực thi.

- **Chữ ký hàm:**
  ```python
  def render_empty_state(
      title: str,
      message: str,
      icon: str = "ℹ️",
      action_label: Optional[str] = None,
  ) -> None
  ```
- **Hợp đồng:** Hiển thị viền nét đứt (dashed border) màu `#263B5C` trên nền canvas tối, căn giữa nội dung, kèm gợi ý tác vụ hành động cụ thể cho người dùng (ví dụ: "Nhấn nút 'Tối ưu hóa ngay' để chạy bộ giải").

---

### 2.6. `render_error_state` (`dashboard/components/common.py`)
Thẻ bao bọc lỗi ranh giới (error boundary card) khi xảy ra ngoại lệ kiểm định hoặc lỗi bộ giải.

- **Chữ ký hàm:**
  ```python
  def render_error_state(
      title: str,
      error_message: Optional[str] = None,
      icon: str = "⚠️",
      error_details: Optional[str] = None,
  ) -> None
  ```
- **Hợp đồng:** Sử dụng màu cảnh báo `#E47777` với độ tương phản cao, nền mờ `rgba(228, 119, 119, 0.08)`, hiển thị chi tiết lỗi kỹ thuật mà không làm lộ stack trace nguy hiểm.

---

### 2.7. `render_status_indicator` (`dashboard/components/common.py`)
Huy hiệu viên thuốc (pill badge) chuẩn hóa mã hóa kép (dual-encoding).

- **Chữ ký hàm:**
  ```python
  def render_status_indicator(
      status_text: Optional[str] = None,
      status_type: str = "info",
      icon: Optional[str] = None,
      status: Optional[str] = None,
      label: Optional[str] = None,
  ) -> None
  ```
- **Hợp đồng:** Ánh xạ các kiểu trạng thái chuẩn:
  - `"success"`: Viền và nền xanh lục `#34C759`.
  - `"warning"`: Viền và nền hổ phách `#E5AD55`.
  - `"error"`: Viền và nền đỏ `#E47777`.
  - `"info"`: Viền và nền cyan `#47C5C0`.
  - `"neutral"`: Viền và nền xám `#94A3B8`.

---

### 2.8. `render_research_inspector` (`dashboard/components/research_inspector.py`)
Khu vực mở rộng (collapsible drawer) dành riêng cho kiểm toán viên và hội đồng khoa học.

- **Chữ ký hàm:**
  ```python
  def render_research_inspector(
      metadata: Dict[str, Any],
      title: str = "RESEARCH AUDIT & SCIENTIFIC PROVENANCE",
      raw_data: Optional[Any] = None,
      status: Optional[str] = None,
  ) -> None
  ```
- **Hợp đồng:**
  - Không hardcode trạng thái `"PASSED"`. Nếu không chỉ định, trạng thái mặc định là `"AUDITED"`.
  - Chuẩn hóa cấu trúc manifest JSON tải về theo lược đồ `aeolus_schema_version: "2.0"`.
  - Nút tải JSON sử dụng `width="stretch"` tuân thủ Streamlit 1.65.0.
