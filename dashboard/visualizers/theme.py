"""Aeolus Plotly Visualization Theme Standard (Phase UI-R03).

Applies the Professional Aviation Dark Theme defined in dashboard.core.theme_tokens.
Standardizes chart backgrounds, axis scales, tick fonts (>=12px), and legends.
"""

from typing import Any, Dict, Optional
import plotly.graph_objects as go

from dashboard.core.theme_tokens import (
    COLOR_ACCENT_PRIMARY,
    COLOR_ACCENT_SECONDARY,
    COLOR_ACCENT_GLOW,
    COLOR_APRON_REMOTE,
    COLOR_BORDER_ACTIVE,
    COLOR_BORDER_SUBTLE,
    COLOR_CANVAS_BG,
    COLOR_STATUS_ERROR,
    COLOR_STATUS_SUCCESS,
    COLOR_STATUS_WARNING,
    COLOR_SURFACE_BG,
    COLOR_SURFACE_ELEVATED,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    FONT_FAMILY_BASE,
    FONT_FAMILY_MONO,
    FONT_SIZE_PLOTLY_TICKS,
    FONT_SIZE_PLOTLY_TITLE,
    PLOTLY_AEOLUS_THEME,
)

# Backwards-compatible aliases for visualizer modules
COLOR_BG_CANVAS = COLOR_CANVAS_BG
COLOR_BG_SURFACE = COLOR_SURFACE_BG
COLOR_BG_ELEVATED = COLOR_SURFACE_ELEVATED
COLOR_ACCENT_GLOW = COLOR_ACCENT_GLOW

AEOLUS_PLOTLY_THEME: Dict[str, Any] = PLOTLY_AEOLUS_THEME


def apply_aeolus_theme(
    fig: go.Figure,
    title: Optional[str] = None,
    xaxis_title: Optional[str] = None,
    yaxis_title: Optional[str] = None,
) -> go.Figure:
    """Apply the unified Aeolus dark theme layout to a Plotly figure."""
    layout_updates: Dict[str, Any] = {
        "paper_bgcolor": AEOLUS_PLOTLY_THEME["paper_bgcolor"],
        "plot_bgcolor": AEOLUS_PLOTLY_THEME["plot_bgcolor"],
        "font": AEOLUS_PLOTLY_THEME["font"],
        "hoverlabel": AEOLUS_PLOTLY_THEME["hoverlabel"],
        "margin": AEOLUS_PLOTLY_THEME["margin"],
        "colorway": AEOLUS_PLOTLY_THEME["colorway"],
    }

    if title:
        # Strip internal CHART-XX prefix if present for clean user-facing titles
        clean_title = title
        if title.startswith("CHART-") and ":" in title:
            clean_title = title.split(":", 1)[1].strip()
        layout_updates["title"] = {
            "text": clean_title,
            "font": {"size": FONT_SIZE_PLOTLY_TITLE, "color": COLOR_TEXT_PRIMARY},
        }

    fig.update_layout(**layout_updates)
    fig.update_xaxes(
        gridcolor=AEOLUS_PLOTLY_THEME["xaxis"]["gridcolor"],
        linecolor=AEOLUS_PLOTLY_THEME["xaxis"]["linecolor"],
        zerolinecolor=AEOLUS_PLOTLY_THEME["xaxis"]["zerolinecolor"],
        tickfont=AEOLUS_PLOTLY_THEME["xaxis"]["tickfont"],
        title_font=AEOLUS_PLOTLY_THEME["xaxis"]["title_font"],
        title_text=xaxis_title if xaxis_title is not None else None,
    )
    fig.update_yaxes(
        gridcolor=AEOLUS_PLOTLY_THEME["yaxis"]["gridcolor"],
        linecolor=AEOLUS_PLOTLY_THEME["yaxis"]["linecolor"],
        zerolinecolor=AEOLUS_PLOTLY_THEME["yaxis"]["zerolinecolor"],
        tickfont=AEOLUS_PLOTLY_THEME["yaxis"]["tickfont"],
        title_font=AEOLUS_PLOTLY_THEME["yaxis"]["title_font"],
        title_text=yaxis_title if yaxis_title is not None else None,
    )
    return fig
