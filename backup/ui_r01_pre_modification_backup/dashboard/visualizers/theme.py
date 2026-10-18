"""Aeolus Plotly Visualization Theme Standard.

Applies the Professional Aviation Dark Theme defined in AEOLUS-P10-A-DESIGN-SYS-03.
"""

from typing import Any, Dict
import plotly.graph_objects as go

# Color Tokens
COLOR_BG_CANVAS = "#101B2A"
COLOR_BG_SURFACE = "#162338"
COLOR_BG_ELEVATED = "#1D2E49"
COLOR_BORDER_SUBTLE = "#263B5C"
COLOR_BORDER_ACTIVE = "#3B5780"

COLOR_ACCENT_PRIMARY = "#47C5C0"   # Aerodrome Cyan
COLOR_ACCENT_GLOW = "#00D2FF"      # Runway Blue / Cyan
COLOR_STATUS_SUCCESS = "#34C759"   # Clearance Green
COLOR_STATUS_WARNING = "#E5AD55"   # Caution Amber
COLOR_STATUS_ERROR = "#E47777"     # Alert Red
COLOR_APRON_REMOTE = "#A78BFA"     # Remote Stand Violet

COLOR_TEXT_PRIMARY = "#F0F4F8"
COLOR_TEXT_SECONDARY = "#94A3B8"
COLOR_TEXT_MUTED = "#64748B"

AEOLUS_PLOTLY_THEME: Dict[str, Any] = {
    "paper_bgcolor": COLOR_BG_SURFACE,
    "plot_bgcolor": COLOR_BG_CANVAS,
    "font": {
        "family": "Inter, Segoe UI, Roboto, system-ui, sans-serif",
        "color": COLOR_TEXT_PRIMARY,
        "size": 12,
    },
    "xaxis": {
        "gridcolor": COLOR_BORDER_SUBTLE,
        "linecolor": COLOR_BORDER_ACTIVE,
        "zerolinecolor": COLOR_BORDER_ACTIVE,
        "tickfont": {"color": COLOR_TEXT_SECONDARY, "size": 11},
        "title_font": {"color": COLOR_TEXT_PRIMARY, "size": 12},
    },
    "yaxis": {
        "gridcolor": COLOR_BORDER_SUBTLE,
        "linecolor": COLOR_BORDER_ACTIVE,
        "zerolinecolor": COLOR_BORDER_ACTIVE,
        "tickfont": {"color": COLOR_TEXT_SECONDARY, "size": 11},
        "title_font": {"color": COLOR_TEXT_PRIMARY, "size": 12},
    },
    "colorway": [
        COLOR_ACCENT_PRIMARY,
        COLOR_ACCENT_GLOW,
        COLOR_STATUS_SUCCESS,
        COLOR_STATUS_WARNING,
        COLOR_STATUS_ERROR,
        COLOR_APRON_REMOTE,
    ],
    "hoverlabel": {
        "bgcolor": COLOR_BG_ELEVATED,
        "bordercolor": COLOR_ACCENT_PRIMARY,
        "font": {
            "family": "JetBrains Mono, Consolas, monospace",
            "color": COLOR_TEXT_PRIMARY,
            "size": 12,
        },
    },
    "margin": {"l": 50, "r": 30, "t": 40, "b": 40},
}


def apply_aeolus_theme(fig: go.Figure) -> go.Figure:
    """Apply the frozen Aeolus dark theme layout to a Plotly figure."""
    fig.update_layout(
        paper_bgcolor=AEOLUS_PLOTLY_THEME["paper_bgcolor"],
        plot_bgcolor=AEOLUS_PLOTLY_THEME["plot_bgcolor"],
        font=AEOLUS_PLOTLY_THEME["font"],
        hoverlabel=AEOLUS_PLOTLY_THEME["hoverlabel"],
        margin=AEOLUS_PLOTLY_THEME["margin"],
    )
    fig.update_xaxes(
        gridcolor=AEOLUS_PLOTLY_THEME["xaxis"]["gridcolor"],
        linecolor=AEOLUS_PLOTLY_THEME["xaxis"]["linecolor"],
        zerolinecolor=AEOLUS_PLOTLY_THEME["xaxis"]["zerolinecolor"],
        tickfont=AEOLUS_PLOTLY_THEME["xaxis"]["tickfont"],
        title_font=AEOLUS_PLOTLY_THEME["xaxis"]["title_font"],
    )
    fig.update_yaxes(
        gridcolor=AEOLUS_PLOTLY_THEME["yaxis"]["gridcolor"],
        linecolor=AEOLUS_PLOTLY_THEME["yaxis"]["linecolor"],
        zerolinecolor=AEOLUS_PLOTLY_THEME["yaxis"]["zerolinecolor"],
        tickfont=AEOLUS_PLOTLY_THEME["yaxis"]["tickfont"],
        title_font=AEOLUS_PLOTLY_THEME["yaxis"]["title_font"],
    )
    return fig
