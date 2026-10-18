"""Centralized Design Tokens and Theme Standards for the Aeolus Dashboard.

Single authoritative source of truth for colors, typography, surfaces,
spacing, and semantic state indicators across Streamlit CSS and Plotly visualizers.
"""

from typing import Any, Dict


# ==============================================================================
# 1. COLOR TOKENS (PROFESSIONAL AVIATION DARK PALETTE)
# ==============================================================================

# Surface & Canvas Tokens
COLOR_CANVAS_BG = "#101B2A"        # Deep airspace obsidian canvas
COLOR_SURFACE_BG = "#162338"       # Primary card, sidebar, and container surface
COLOR_SURFACE_ELEVATED = "#1D2E49" # Dropdown, modal, drawer, and hover surface
COLOR_SURFACE_HOVER = "#223554"    # Interactive surface hover state

# Border Tokens
COLOR_BORDER_SUBTLE = "#263B5C"    # Standard divider and container outline
COLOR_BORDER = COLOR_BORDER_SUBTLE
COLOR_BORDER_ACTIVE = "#3B5780"    # Hover / active container outline
COLOR_BORDER_FOCUS = "#47C5C0"     # Keyboard focus and highlight border

# Accent Tokens
COLOR_ACCENT_PRIMARY = "#47C5C0"   # Aerodrome Cyan / Teal (Primary interaction)
COLOR_ACCENT_PRIMARY_HOVER = "#5EEAD4"
COLOR_ACCENT_SECONDARY = "#38BDF8" # Runway Sky Blue (Secondary action)
COLOR_ACCENT_GLOW = "#00D2FF"      # Cyan Glow (Charts and legacy contrast)
COLOR_APRON_REMOTE = "#A78BFA"     # Remote Stand / Apron Violet (Resource distinction)

# Semantic Status Tokens (Dual-encoded with icons and explicit text)
COLOR_STATUS_SUCCESS = "#34C759"   # Verified / Proven Optimal / Feasible
COLOR_STATUS_WARNING = "#E5AD55"   # Caution / Constrained / Stale Parameter
COLOR_STATUS_ERROR = "#E47777"     # Critical / Physical Collision / Violation
COLOR_STATUS_INFO = "#47C5C0"      # Informational / Baseline Timetable / Neutral
COLOR_STATUS_NEUTRAL = "#94A3B8"   # Inactive / Default badge

# Text & Foreground Tokens (All meet WCAG AA contrast ratios)
COLOR_TEXT_PRIMARY = "#F0F4F8"     # Main body & header text (~10.9:1 against surface)
COLOR_TEXT_SECONDARY = "#94A3B8"   # Secondary labels & metadata (~5.1:1 against surface)
COLOR_TEXT_MUTED = "#64748B"       # Captions, footnotes, and disabled elements (>3:1)
COLOR_TEXT_INVERSE = "#101B2A"     # High contrast on light badge backgrounds


# ==============================================================================
# 2. TYPOGRAPHY SCALE (TASK R03-C)
# ==============================================================================

FONT_FAMILY_BASE = "'Inter', 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif"
FONT_FAMILY_MONO = "'JetBrains Mono', 'SF Mono', Consolas, monospace"

FONT_SIZE_PAGE_TITLE = "28px"
FONT_SIZE_SECTION_TITLE = "20px"
FONT_SIZE_CARD_TITLE = "15px"
FONT_SIZE_BODY = "14px"
FONT_SIZE_SECONDARY_LABEL = "13px"  # Eradicated 11px on critical functional labels
FONT_SIZE_SECONDARY = FONT_SIZE_SECONDARY_LABEL
FONT_SIZE_KPI_VALUE = "30px"
FONT_SIZE_BADGE = "12px"            # Minimum size for badges and tags
FONT_SIZE_PLOTLY_TICKS = 12         # Integer for Plotly layout dictionaries
FONT_SIZE_PLOTLY_TITLE = 15         # Integer for Plotly layout dictionaries


# ==============================================================================
# 3. SPACING & RADIUS TOKENS
# ==============================================================================

RADIUS_SM = "4px"
RADIUS_MD = "6px"
RADIUS_LG = "8px"
RADIUS_XL = "12px"

SPACING_XS = "4px"
SPACING_SM = "8px"
SPACING_MD = "16px"
SPACING_LG = "24px"
SPACING_XL = "32px"


# ==============================================================================
# 4. PLOTLY THEME DICTIONARY SPECIFICATION (TASK R03-G)
# ==============================================================================

PLOTLY_AEOLUS_THEME: Dict[str, Any] = {
    "paper_bgcolor": COLOR_SURFACE_BG,
    "plot_bgcolor": COLOR_CANVAS_BG,
    "font": {
        "family": FONT_FAMILY_BASE,
        "color": COLOR_TEXT_PRIMARY,
        "size": FONT_SIZE_PLOTLY_TICKS,
    },
    "xaxis": {
        "gridcolor": COLOR_BORDER_SUBTLE,
        "linecolor": COLOR_BORDER_ACTIVE,
        "zerolinecolor": COLOR_BORDER_ACTIVE,
        "tickfont": {"color": COLOR_TEXT_SECONDARY, "size": FONT_SIZE_PLOTLY_TICKS},
        "title_font": {"color": COLOR_TEXT_PRIMARY, "size": FONT_SIZE_PLOTLY_TICKS + 1},
    },
    "yaxis": {
        "gridcolor": COLOR_BORDER_SUBTLE,
        "linecolor": COLOR_BORDER_ACTIVE,
        "zerolinecolor": COLOR_BORDER_ACTIVE,
        "tickfont": {"color": COLOR_TEXT_SECONDARY, "size": FONT_SIZE_PLOTLY_TICKS},
        "title_font": {"color": COLOR_TEXT_PRIMARY, "size": FONT_SIZE_PLOTLY_TICKS + 1},
    },
    "colorway": [
        COLOR_ACCENT_PRIMARY,
        COLOR_ACCENT_SECONDARY,
        COLOR_STATUS_SUCCESS,
        COLOR_STATUS_WARNING,
        COLOR_STATUS_ERROR,
        COLOR_APRON_REMOTE,
    ],
    "hoverlabel": {
        "bgcolor": COLOR_SURFACE_ELEVATED,
        "bordercolor": COLOR_ACCENT_PRIMARY,
        "font": {
            "family": FONT_FAMILY_MONO,
            "color": COLOR_TEXT_PRIMARY,
            "size": FONT_SIZE_PLOTLY_TICKS,
        },
    },
    "margin": {"l": 50, "r": 30, "t": 44, "b": 44},
}
