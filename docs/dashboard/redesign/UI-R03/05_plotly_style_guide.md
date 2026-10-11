# AEOLUS PLOTLY VISUALIZATION STYLE GUIDE (UI-R03 v2.0)
## Plotly 7.1.0 Aviation Theme & Academic Visualization Standards

**Phase:** UI-R03 v2.0  
**Status:** IMPLEMENTED & AUDITED  
**Theme Module:** `dashboard/visualizers/theme.py`  
**Theme Specification:** `dashboard/core/theme_tokens.py`  

---

## 1. Mục tiêu Chuẩn Hóa Biểu Đồ

Các biểu đồ tương tác của Aeolus (từ Gantt phân cổng, biểu đồ động lực học quay vòng, đường biên Pareto đến đường cong hội tụ Monte Carlo) phải đáp ứng đồng thời hai tiêu chuẩn khắt khe:
1. **Tính thẩm mỹ & chuyên nghiệp hàng không (Aviation Aesthetics):** Trực quan, sắc nét, đồng bộ màu sắc với toàn bộ giao diện Streamlit.
2. **Tính chuẩn mực học thuật (Academic Rigor):** Trục tọa độ có đơn vị rõ ràng, font chữ $\ge 12\text{px}$, loại bỏ các tiền tố mã code kỹ thuật thô thiển (`CHART-01:`, `CHART-02:`), và tooltip hiển thị số liệu chính xác với font đơn cách (monospace).

---

## 2. Đặc Tả Theme Biểu Đồ (`PLOTLY_AEOLUS_THEME`)

```python
PLOTLY_AEOLUS_THEME = {
    "paper_bgcolor": "#162338",       # Trùng COLOR_SURFACE_BG của Card Streamlit
    "plot_bgcolor": "#101B2A",        # Trùng COLOR_CANVAS_BG của App Canvas
    "font": {
        "family": "'Inter', 'Segoe UI', -apple-system, sans-serif",
        "color": "#F0F4F8",           # Màu chữ chính độ tương phản cao
        "size": 12,                   # Kích thước chữ cơ sở >= 12px
    },
    "xaxis": {
        "gridcolor": "#263B5C",       # Đường lưới phụ mờ, không gây nhiễu
        "linecolor": "#3B5780",       # Trục tọa độ rõ nét
        "zerolinecolor": "#3B5780",
        "tickfont": {"color": "#94A3B8", "size": 12},  # Ticks font >= 12px
        "title_font": {"color": "#F0F4F8", "size": 13},
    },
    "yaxis": {
        "gridcolor": "#263B5C",
        "linecolor": "#3B5780",
        "zerolinecolor": "#3B5780",
        "tickfont": {"color": "#94A3B8", "size": 12},  # Ticks font >= 12px
        "title_font": {"color": "#F0F4F8", "size": 13},
    },
    "colorway": [
        "#47C5C0",  # Aerodrome Cyan (Inbound / Primary)
        "#38BDF8",  # Runway Sky Blue (Outbound / Secondary)
        "#34C759",  # Feasible / Verified Optimal
        "#E5AD55",  # Medium Risk / Warning
        "#E47777",  # Violation / Physical Collision
        "#A78BFA",  # Remote Stand Apron Violet
    ],
    "hoverlabel": {
        "bgcolor": "#1D2E49",         # Nền tooltip elevated
        "bordercolor": "#47C5C0",     # Viền cyan nổi bật
        "font": {
            "family": "'JetBrains Mono', 'SF Mono', Consolas, monospace",
            "color": "#F0F4F8",
            "size": 12,
        },
    },
}
```

---

## 3. Quy Tắc Loại Bỏ Tiền Tố Code Kỹ Thuật (CHART Prefix Stripping)

Trước UI-R03, các biểu đồ thường mang tiêu đề dạng debug kỹ thuật như:
- `CHART-01: Timeline hoạt động bay`
- `CHART-03: Động lực học quay vòng tàu bay`
- `CHART-09: Đường biên Pareto tối ưu`

Việc này làm giảm tính chuyên nghiệp khi trình bày trước hội đồng và người dùng cuối. Hàm `apply_aeolus_theme()` trong `dashboard/visualizers/theme.py` đã được tích hợp bộ lọc regex tự động:
```python
clean_title = re.sub(r"^CHART-\d{1,2}:\s*", "", raw_title)
```
- Nếu truyền vào `"CHART-01: Activity Timeline"`, tiêu đề tự động làm sạch thành `"Activity Timeline"`.
- Nếu truyền vào tiêu đề tiếng Việt chuẩn `"Sơ đồ Phân bổ Cổng Đỗ"`, tiêu đề được bảo toàn nguyên vẹn.

---

## 4. Chuẩn Hóa Tooltip & Tương Tác Trực Quan

- **Cấu trúc Monospace:** Mọi giá trị số trong tooltip (thời gian khởi hành, thời gian gán cổng, số phút trễ, chi phí) sử dụng font monospace để số liệu thẳng hàng.
- **Biểu đồ Gantt Phân Cổng:**
  - Chuyến bay khả thi: Khối chữ nhật màu Teal `#47C5C0` với nhãn chuyến bay rõ ràng.
  - Chuyến bay vi phạm xung đột: Khối chữ nhật màu Đỏ `#E47777` kèm icon cảnh báo `⚠️`.
  - Vị trí đỗ bãi xa (Remote): Đường viền màu Tím `#A78BFA`.
- **Đường biểu diễn Phân vị & Kỳ vọng:**
  - Điểm trung vị / kỳ vọng: Nét liền đậm (Solid line, 2px).
  - Khoảng tin cậy 95% ($\pm 1.96 \cdot \text{MCSE}$): Vùng phủ bóng bán minh bạch (Opacity 0.15).
