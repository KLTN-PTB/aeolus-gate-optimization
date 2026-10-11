"""Aeolus dashboard reusable components."""

from dashboard.components.common import (
    render_empty_state,
    render_error_state,
    render_page_header,
    render_section_header,
    render_status_indicator,
)
from dashboard.components.context_bar import render_context_bar
from dashboard.components.flight_inspector import render_flight_inspector
from dashboard.components.kpi_card import render_kpi_card
from dashboard.components.research_inspector import render_research_inspector
from dashboard.components.styles import inject_custom_styles

__all__ = [
    "inject_custom_styles",
    "render_context_bar",
    "render_empty_state",
    "render_error_state",
    "render_flight_inspector",
    "render_kpi_card",
    "render_page_header",
    "render_research_inspector",
    "render_section_header",
    "render_status_indicator",
]
