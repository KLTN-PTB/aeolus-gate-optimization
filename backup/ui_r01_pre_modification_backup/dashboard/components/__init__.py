"""Aeolus dashboard reusable components."""

from dashboard.components.context_bar import render_context_bar
from dashboard.components.flight_inspector import render_flight_inspector
from dashboard.components.kpi_card import render_kpi_card
from dashboard.components.research_inspector import render_research_inspector
from dashboard.components.styles import inject_custom_styles

__all__ = [
    "inject_custom_styles",
    "render_context_bar",
    "render_flight_inspector",
    "render_kpi_card",
    "render_research_inspector",
]
