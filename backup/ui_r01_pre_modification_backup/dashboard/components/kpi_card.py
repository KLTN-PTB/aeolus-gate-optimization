"""KPI Card UI Component for Aviation Operations Dashboard.

Implements high-contrast, dual-encoded metric scorecards with tabular numerals.
"""

from typing import Optional
import streamlit as st


def render_kpi_card(
    title: str,
    value: str,
    subtitle: str,
    badge_text: Optional[str] = None,
    badge_type: str = "info",
    icon: Optional[str] = None,
    help_tooltip: Optional[str] = None,
    status: Optional[str] = None,
    help_text: Optional[str] = None,
) -> None:
    """Render an aerospace-grade KPI metric card with dual-encoding.

    Args:
        title: Metric title (e.g. 'TỔNG CHUYẾN BAY').
        value: Prominent numeric metric value (e.g. '120 Chuyến', '+18.4 min').
        subtitle: Secondary descriptive text.
        badge_text: Text inside the status pill (e.g. '[🛡️ ĐÃ GIẢI TỎA]').
        badge_type: One of 'success', 'warning', 'error', 'info', 'remote'.
        icon: Optional leading icon for title.
        help_tooltip: Optional tooltip explanation.
        status: Optional alias for badge_type.
        help_text: Optional alias for help_tooltip.
    """
    effective_badge_type = status or badge_type
    effective_tooltip = help_text or help_tooltip
    badge_class = f"aeolus-badge-{effective_badge_type}"
    badge_html = f'<span class="aeolus-badge {badge_class}">{badge_text or effective_badge_type.upper()}</span>' if (badge_text or status) else ""
    icon_html = f"{icon} " if icon else ""

    html = f"""
    <div class="aeolus-kpi-card">
        <div class="aeolus-kpi-title" title="{help_tooltip or ''}">
            {icon_html}{title}
        </div>
        <div class="aeolus-kpi-value">
            {value}
        </div>
        <div class="aeolus-kpi-subtitle">
            <span>{subtitle}</span>
            {badge_html}
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
