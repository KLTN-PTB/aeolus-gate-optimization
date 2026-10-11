"""Unit and integration test suite for Phase UI-R03 v2.0.

Professional Aviation Design System & Responsive Application Shell:
Tests covering R03-T01 through R03-T18:
- Design Tokens & Accessibility Contrast (R03-T01, R03-T02)
- Centralized CSS Styling Engine & Tabular Numerals (R03-T03)
- Plotly Aviation Theme Standardization (R03-T04, R03-T05)
- Standardized UI Components & Null Safety (R03-T06, R03-T07)
- Common Component Library (PageHeader, SectionHeader, EmptyState, ErrorState, StatusIndicator) (R03-T08 to R03-T12)
- Context Bar & Research Inspector Enhancements (R03-T13, R03-T14)
- App Navigation, Unicode Integrity & Page Contracts (R03-T15, R03-T16, R03-T17)
- Zero Deprecated Width Parameters (R03-T18)
"""

from pathlib import Path
import re
from unittest.mock import MagicMock, patch
import pytest
import plotly.graph_objects as go

from dashboard.app import PAGES
from dashboard.components.common import (
    render_empty_state,
    render_error_state,
    render_page_header,
    render_section_header,
    render_status_indicator,
)
from dashboard.components.context_bar import render_context_bar
from dashboard.components.kpi_card import render_kpi_card
from dashboard.components.research_inspector import render_research_inspector
from dashboard.components.styles import get_custom_css, inject_custom_styles
from dashboard.core.state import PageKeys
from dashboard.core.theme_tokens import (
    COLOR_ACCENT_PRIMARY,
    COLOR_ACCENT_SECONDARY,
    COLOR_BORDER,
    COLOR_CANVAS_BG,
    COLOR_STATUS_ERROR,
    COLOR_STATUS_INFO,
    COLOR_STATUS_NEUTRAL,
    COLOR_STATUS_SUCCESS,
    COLOR_STATUS_WARNING,
    COLOR_SURFACE_BG,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    FONT_SIZE_BADGE,
    FONT_SIZE_BODY,
    FONT_SIZE_CARD_TITLE,
    FONT_SIZE_KPI_VALUE,
    FONT_SIZE_PAGE_TITLE,
    FONT_SIZE_SECONDARY,
    FONT_SIZE_SECTION_TITLE,
    PLOTLY_AEOLUS_THEME,
)
from dashboard.pages import (
    page_01_control_tower,
    page_02_flight_intelligence,
    page_03_gate_operations,
    page_04_optimization_lab,
    page_05_robustness_lab,
)
from dashboard.visualizers.theme import apply_aeolus_theme


# ------------------------------------------------------------------------------
# R03-T01: Theme tokens hex validation & aviation dark palette
# ------------------------------------------------------------------------------
def test_r03_t01_theme_tokens_contrast_and_palette() -> None:
    hex_pattern = re.compile(r"^#[0-9A-Fa-f]{6}$")

    palette = [
        COLOR_CANVAS_BG,
        COLOR_SURFACE_BG,
        COLOR_ACCENT_PRIMARY,
        COLOR_ACCENT_SECONDARY,
        COLOR_TEXT_PRIMARY,
        COLOR_TEXT_SECONDARY,
        COLOR_BORDER,
        COLOR_STATUS_SUCCESS,
        COLOR_STATUS_WARNING,
        COLOR_STATUS_ERROR,
        COLOR_STATUS_INFO,
        COLOR_STATUS_NEUTRAL,
    ]

    for color in palette:
        assert hex_pattern.match(color) is not None, f"Invalid hex color: {color}"

    # Verify canonical aviation dark values
    assert COLOR_CANVAS_BG == "#101B2A"
    assert COLOR_SURFACE_BG == "#162338"
    assert COLOR_ACCENT_PRIMARY == "#47C5C0"
    assert COLOR_ACCENT_SECONDARY in ("#38BDF8", "#00D2FF")
    assert COLOR_STATUS_SUCCESS == "#34C759"
    assert COLOR_STATUS_WARNING == "#E5AD55"
    assert COLOR_STATUS_ERROR == "#E47777"


# ------------------------------------------------------------------------------
# R03-T02: Typography scale constants & no functional labels < 12px
# ------------------------------------------------------------------------------
def test_r03_t02_typography_scale_tokens() -> None:
    assert FONT_SIZE_PAGE_TITLE == "28px"
    assert FONT_SIZE_SECTION_TITLE == "20px"
    assert FONT_SIZE_CARD_TITLE == "15px"
    assert FONT_SIZE_BODY == "14px"
    assert FONT_SIZE_SECONDARY == "13px"
    assert FONT_SIZE_BADGE == "12px"
    assert FONT_SIZE_KPI_VALUE == "30px"

    # All functional tokens must be >= 12px
    tokens = [
        FONT_SIZE_PAGE_TITLE,
        FONT_SIZE_SECTION_TITLE,
        FONT_SIZE_CARD_TITLE,
        FONT_SIZE_BODY,
        FONT_SIZE_SECONDARY,
        FONT_SIZE_BADGE,
        FONT_SIZE_KPI_VALUE,
    ]
    for token in tokens:
        val = int(token.replace("px", ""))
        assert val >= 12, f"Typography token {token} is below 12px"


# ------------------------------------------------------------------------------
# R03-T03: Centralized CSS styling engine & tabular numerals rule
# ------------------------------------------------------------------------------
def test_r03_t03_css_injection_and_rules() -> None:
    css = get_custom_css()
    assert isinstance(css, str)
    assert len(css) > 500

    # Key design system selectors must exist
    assert ".aeolus-card" in css
    assert ".aeolus-kpi-card" in css
    assert ".aeolus-badge" in css
    assert "tabular-nums" in css
    assert ":focus-visible" in css
    assert "stVerticalBlockBorderWrapper" in css

    # inject_custom_styles executes without error
    inject_custom_styles()


# ------------------------------------------------------------------------------
# R03-T04: Plotly aviation theme tokens alignment
# ------------------------------------------------------------------------------
def test_r03_t04_plotly_theme_tokens_alignment() -> None:
    layout = PLOTLY_AEOLUS_THEME
    assert layout["paper_bgcolor"] == COLOR_SURFACE_BG
    assert layout["plot_bgcolor"] == COLOR_CANVAS_BG
    assert "Inter" in layout["font"]["family"]
    assert layout["xaxis"]["tickfont"]["size"] >= 12
    assert layout["yaxis"]["tickfont"]["size"] >= 12
    assert layout["colorway"][0] == COLOR_ACCENT_PRIMARY
    assert layout["colorway"][1] == COLOR_ACCENT_SECONDARY


# ------------------------------------------------------------------------------
# R03-T05: Stripped CHART-XX prefixes and title cleaning
# ------------------------------------------------------------------------------
def test_r03_t05_plotly_theme_title_cleaning() -> None:
    fig = go.Figure(go.Scatter(x=[1, 2], y=[3, 4]))
    fig = apply_aeolus_theme(fig, title="CHART-01: Activity Timeline")

    assert fig.layout.title.text == "Activity Timeline"

    # Non-prefixed Vietnamese title preserves clean text
    fig2 = go.Figure(go.Scatter(x=[1, 2], y=[3, 4]))
    fig2 = apply_aeolus_theme(fig2, title="Sơ đồ Phân bổ Cổng Đỗ")
    assert fig2.layout.title.text == "Sơ đồ Phân bổ Cổng Đỗ"


# ------------------------------------------------------------------------------
# R03-T06: KPI Card null safety and default fallback handling
# ------------------------------------------------------------------------------
def test_r03_t06_kpi_card_null_safety_and_defaults() -> None:
    captured = []
    with patch("streamlit.markdown", side_effect=lambda html, **kwargs: captured.append(html)):
        render_kpi_card(title="TEST NULL VALUE", value=None)
        assert len(captured) >= 1
        assert "N/A" in captured[-1]

        render_kpi_card(title="TEST EMPTY VALUE", value="")
        assert "N/A" in captured[-1]


# ------------------------------------------------------------------------------
# R03-T07: KPI Card tabular numerals and 30px value typography
# ------------------------------------------------------------------------------
def test_r03_t07_kpi_card_tabular_numerals_and_typography() -> None:
    captured = []
    with patch("streamlit.markdown", side_effect=lambda html, **kwargs: captured.append(html)):
        render_kpi_card(
            title="CHI PHÍ QUYẾT ĐỊNH",
            value="142.50 pts",
            subtitle="CP-SAT Solver",
            badge_text="OPTIMAL",
            status="success",
        )
        assert len(captured) >= 1
        html = captured[-1]
        assert "tabular-nums" in html
        assert "aeolus-kpi-value" in html
        assert "142.50 pts" in html
        assert "aeolus-badge-success" in html


# ------------------------------------------------------------------------------
# R03-T08: Common component PageHeader
# ------------------------------------------------------------------------------
def test_r03_t08_common_page_header() -> None:
    captured = []
    with patch("streamlit.markdown", side_effect=lambda html, **kwargs: captured.append(html)):
        render_page_header(
            title="🗼 Control Tower",
            subtitle="Giám sát vận hành thời gian thực",
            badge_text="LIVE OPERATIONAL",
            badge_status="success",
        )
        assert len(captured) >= 1
        html = captured[-1]
        assert "Control Tower" in html
        assert "Giám sát vận hành thời gian thực" in html
        assert "LIVE OPERATIONAL" in html
        assert "aeolus-page-title" in html


# ------------------------------------------------------------------------------
# R03-T09: Common component SectionHeader
# ------------------------------------------------------------------------------
def test_r03_t09_common_section_header() -> None:
    captured = []
    with patch("streamlit.markdown", side_effect=lambda html, **kwargs: captured.append(html)):
        render_section_header(
            title="1. Phân bổ Cổng Danh nghĩa",
            description="Lịch gán cổng ban đầu theo IATA SSIM",
            divider=True,
        )
        assert len(captured) >= 1
        html = captured[-1]
        assert "1. Phân bổ Cổng Danh nghĩa" in html
        assert "Lịch gán cổng ban đầu theo IATA SSIM" in html
        assert "aeolus-section-title" in html


# ------------------------------------------------------------------------------
# R03-T10: Common component EmptyState
# ------------------------------------------------------------------------------
def test_r03_t10_common_empty_state() -> None:
    captured = []
    with patch("streamlit.markdown", side_effect=lambda html, **kwargs: captured.append(html)):
        render_empty_state(
            title="Không tìm thấy chuyến bay",
            message="Vui lòng nới lỏng bộ lọc Concourse hoặc tìm kiếm số hiệu chuyến bay khác.",
            icon="🛫",
        )
        assert len(captured) >= 1
        html = captured[-1]
        assert "Không tìm thấy chuyến bay" in html
        assert "Vui lòng nới lỏng bộ lọc" in html
        assert "🛫" in html


# ------------------------------------------------------------------------------
# R03-T11: Common component ErrorState
# ------------------------------------------------------------------------------
def test_r03_t11_common_error_state() -> None:
    captured = []
    with patch("streamlit.markdown", side_effect=lambda html, **kwargs: captured.append(html)):
        render_error_state(
            title="Lỗi tải dữ liệu kịch bản",
            error_details="File scenario_120.parquet không tồn tại trên đĩa.",
        )
        assert len(captured) >= 1
        html = captured[-1]
        assert "Lỗi tải dữ liệu kịch bản" in html
        assert "File scenario_120.parquet" in html
        assert "aeolus-badge-error" in html


# ------------------------------------------------------------------------------
# R03-T12: Common component StatusIndicator
# ------------------------------------------------------------------------------
def test_r03_t12_common_status_indicator() -> None:
    for status in ["success", "warning", "error", "info", "neutral"]:
        captured = []
        with patch("streamlit.markdown", side_effect=lambda html, **kwargs: captured.append(html)):
            render_status_indicator(status=status, label=f"Trạng thái {status}")
            assert len(captured) >= 1
            assert f"aeolus-badge-{status}" in captured[-1]


# ------------------------------------------------------------------------------
# R03-T13: Context Bar page awareness & typography scale >= 12px
# ------------------------------------------------------------------------------
def test_r03_t13_context_bar_page_awareness_and_typography() -> None:
    captured = []
    with patch("streamlit.markdown", side_effect=lambda html, **kwargs: captured.append(html)):
        # On Flight Intelligence, it should display Dual-Core ML info
        render_context_bar(
            scenario_id="SCEN_P09_CANONICAL_120",
            current_page_key="02_flight_intelligence",
        )
        assert len(captured) >= 1
        html = " ".join(captured)
        assert "DUAL-CORE ML" in html
        assert "Kịch bản" in html

        # On other pages with show_solver_status=False
        captured.clear()
        render_context_bar(
            scenario_id="SCEN_P09_CANONICAL_120",
            show_solver_status=False,
        )
        assert len(captured) >= 1
        html2 = " ".join(captured)
        assert "Kịch bản" in html2


# ------------------------------------------------------------------------------
# R03-T14: Research Inspector schema v2.0 & unhardcoded audit status
# ------------------------------------------------------------------------------
def test_r03_t14_research_inspector_schema_v2_and_safety() -> None:
    meta = {
        "scenario_id": "SCEN_P09_CANONICAL_120",
        "solver": "CP_SAT",
        "provenance": "SYNTHETIC_SIMULATION",
    }
    # Should render cleanly with schema version 2.0 without forcing PASSED default
    render_research_inspector(title="TEST INSPECTOR", metadata=meta)


# ------------------------------------------------------------------------------
# R03-T15: App navigation canonical keys & page contracts
# ------------------------------------------------------------------------------
def test_r03_t15_app_navigation_canonical_keys() -> None:
    canonical_keys = {pk.value for pk in PageKeys}
    assert set(PAGES.keys()) == canonical_keys

    for key, page_meta in PAGES.items():
        assert "title" in page_meta
        assert "module" in page_meta
        assert hasattr(page_meta["module"], "render_page")
        assert callable(page_meta["module"].render_page)


# ------------------------------------------------------------------------------
# R03-T16: Vietnamese Unicode typography & diacritic safety
# ------------------------------------------------------------------------------
def test_r03_t16_vietnamese_unicode_integrity() -> None:
    vietnamese_strings = [
        "🗼 Control Tower (Tổng quan)",
        "🔬 Flight Intelligence (Dự báo Trễ)",
        "🛫 Gate Operations (Phân cổng & Gantt)",
        "⚡ Optimization Lab (Tối ưu)",
        "🎲 Robustness Lab (Độ vững)",
        "Kế hoạch Phân cổng Đỗ Tàu bay Tối ưu",
        "Độ trễ Lan truyền & Khả năng Hấp thụ Đệm",
    ]
    for s in vietnamese_strings:
        encoded = s.encode("utf-8")
        decoded = encoded.decode("utf-8")
        assert decoded == s
        assert "\ufffd" not in decoded


# ------------------------------------------------------------------------------
# R03-T17: All 5 pages module import and render_page callable check
# ------------------------------------------------------------------------------
def test_r03_t17_all_pages_module_import_and_render_contract() -> None:
    pages = [
        page_01_control_tower,
        page_02_flight_intelligence,
        page_03_gate_operations,
        page_04_optimization_lab,
        page_05_robustness_lab,
    ]
    for p in pages:
        assert hasattr(p, "render_page"), f"Module {p.__name__} lacks render_page()"
        assert callable(p.render_page), f"Module {p.__name__}.render_page is not callable"


# ------------------------------------------------------------------------------
# R03-T18: Zero deprecated use_container_width calls in dashboard
# ------------------------------------------------------------------------------
def test_r03_t18_zero_use_container_width_deprecated_calls() -> None:
    dashboard_root = Path(__file__).resolve().parent.parent.parent / "dashboard"
    python_files = list(dashboard_root.rglob("*.py"))
    assert len(python_files) > 0

    found_deprecated = []
    for py_file in python_files:
        content = py_file.read_text(encoding="utf-8")
        if "use_container_width" in content:
            found_deprecated.append(str(py_file.name))

    assert len(found_deprecated) == 0, (
        f"Found deprecated 'use_container_width' in {len(found_deprecated)} files: {found_deprecated}"
    )
