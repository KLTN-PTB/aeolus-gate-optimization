"""Aeolus Custom CSS Styles and Theme Injection (Phase UI-R03).

Centralized styling engine consuming theme tokens from dashboard.core.theme_tokens.
Ensures accessibility, consistent typography scale, and responsive surfaces.
"""

import streamlit as st

from dashboard.core.theme_tokens import (
    COLOR_ACCENT_PRIMARY,
    COLOR_ACCENT_PRIMARY_HOVER,
    COLOR_ACCENT_SECONDARY,
    COLOR_APRON_REMOTE,
    COLOR_BORDER_ACTIVE,
    COLOR_BORDER_FOCUS,
    COLOR_BORDER_SUBTLE,
    COLOR_CANVAS_BG,
    COLOR_STATUS_ERROR,
    COLOR_STATUS_INFO,
    COLOR_STATUS_SUCCESS,
    COLOR_STATUS_WARNING,
    COLOR_SURFACE_BG,
    COLOR_SURFACE_ELEVATED,
    COLOR_SURFACE_HOVER,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    FONT_FAMILY_BASE,
    FONT_FAMILY_MONO,
    FONT_SIZE_BADGE,
    FONT_SIZE_BODY,
    FONT_SIZE_CARD_TITLE,
    FONT_SIZE_KPI_VALUE,
    FONT_SIZE_PAGE_TITLE,
    FONT_SIZE_SECONDARY_LABEL,
    FONT_SIZE_SECTION_TITLE,
    RADIUS_LG,
    RADIUS_MD,
    RADIUS_SM,
)


CUSTOM_CSS = f"""
<style>
/* ==========================================================================
   1. BASE APP & TYPOGRAPHY FOUNDATIONS
   ========================================================================== */
.stApp {{
    background-color: {COLOR_CANVAS_BG} !important;
    color: {COLOR_TEXT_PRIMARY} !important;
    font-family: {FONT_FAMILY_BASE} !important;
    font-size: {FONT_SIZE_BODY};
    line-height: 1.5;
}}

/* Headings Hierarchy (Task R03-C) */
h1 {{
    font-size: {FONT_SIZE_PAGE_TITLE} !important;
    color: {COLOR_TEXT_PRIMARY} !important;
    font-weight: 700 !important;
    letter-spacing: -0.5px;
    margin-bottom: 8px !important;
}}

h2 {{
    font-size: {FONT_SIZE_SECTION_TITLE} !important;
    color: {COLOR_TEXT_PRIMARY} !important;
    font-weight: 600 !important;
    letter-spacing: -0.3px;
    margin-top: 16px !important;
    margin-bottom: 8px !important;
}}

h3 {{
    font-size: 18px !important;
    color: {COLOR_TEXT_PRIMARY} !important;
    font-weight: 600 !important;
}}

h4, h5, h6 {{
    font-size: {FONT_SIZE_CARD_TITLE} !important;
    color: {COLOR_TEXT_PRIMARY} !important;
    font-weight: 600 !important;
}}

p, span, label {{
    color: {COLOR_TEXT_PRIMARY};
}}

/* ==========================================================================
   2. SIDEBAR REFINEMENT (TASK R03-E)
   ========================================================================== */
section[data-testid="stSidebar"] {{
    background-color: {COLOR_SURFACE_BG} !important;
    border-right: 1px solid {COLOR_BORDER_SUBTLE} !important;
}}

section[data-testid="stSidebar"] .stRadio label {{
    color: {COLOR_TEXT_PRIMARY} !important;
    font-size: {FONT_SIZE_BODY} !important;
    font-weight: 500;
    padding: 4px 0;
}}

/* ==========================================================================
   3. CARD & CONTAINER SYSTEM (TASK R03-D)
   ========================================================================== */
.aeolus-card {{
    background-color: {COLOR_SURFACE_BG};
    border: 1px solid {COLOR_BORDER_SUBTLE};
    border-radius: {RADIUS_LG};
    padding: 16px;
    margin-bottom: 16px;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
    transition: border-color 0.15s ease-in-out;
}}

.aeolus-card:hover {{
    border-color: {COLOR_BORDER_ACTIVE};
}}

/* Streamlit Native Bordered Containers */
div[data-testid="stVerticalBlockBorderWrapper"] > div {{
    background-color: {COLOR_SURFACE_BG} !important;
    border: 1px solid {COLOR_BORDER_SUBTLE} !important;
    border-radius: {RADIUS_LG} !important;
}}

/* Global Context Bar */
.aeolus-context-bar {{
    background-color: {COLOR_SURFACE_BG};
    border: 1px solid {COLOR_BORDER_SUBTLE};
    border-radius: {RADIUS_LG};
    padding: 12px 20px;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}}

/* ==========================================================================
   4. KPI SCORECARD COMPONENT (TASK R03-C & R03-D)
   ========================================================================== */
.aeolus-kpi-card {{
    background-color: {COLOR_SURFACE_BG};
    border: 1px solid {COLOR_BORDER_SUBTLE};
    border-radius: {RADIUS_LG};
    padding: 14px 16px;
    min-height: 110px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
    transition: border-color 0.15s ease-in-out;
}}

.aeolus-kpi-card:hover {{
    border-color: {COLOR_BORDER_ACTIVE};
}}

.aeolus-kpi-title {{
    font-size: {FONT_SIZE_SECONDARY_LABEL};
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: {COLOR_TEXT_SECONDARY};
    font-weight: 600;
}}

.aeolus-kpi-value {{
    font-size: {FONT_SIZE_KPI_VALUE};
    font-weight: 700;
    color: {COLOR_TEXT_PRIMARY};
    font-variant-numeric: tabular-nums;
    margin: 4px 0;
}}

.aeolus-kpi-subtitle {{
    font-size: {FONT_SIZE_SECONDARY_LABEL};
    color: {COLOR_TEXT_SECONDARY};
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
}}

/* ==========================================================================
   5. DUAL-ENCODED STATUS BADGES (TASK R03-B & R03-I)
   ========================================================================== */
.aeolus-badge {{
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 8px;
    border-radius: {RADIUS_SM};
    font-size: {FONT_SIZE_BADGE};
    font-weight: 600;
    font-family: {FONT_FAMILY_MONO};
    line-height: 1.2;
}}

.aeolus-badge-success {{
    background-color: rgba(52, 199, 89, 0.15);
    color: {COLOR_STATUS_SUCCESS};
    border: 1px solid {COLOR_STATUS_SUCCESS};
}}

.aeolus-badge-warning {{
    background-color: rgba(229, 173, 85, 0.15);
    color: {COLOR_STATUS_WARNING};
    border: 1px solid {COLOR_STATUS_WARNING};
}}

.aeolus-badge-error {{
    background-color: rgba(228, 119, 119, 0.15);
    color: {COLOR_STATUS_ERROR};
    border: 1px solid {COLOR_STATUS_ERROR};
}}

.aeolus-badge-info {{
    background-color: rgba(71, 197, 192, 0.15);
    color: {COLOR_STATUS_INFO};
    border: 1px solid {COLOR_STATUS_INFO};
}}

.aeolus-badge-remote {{
    background-color: rgba(167, 139, 250, 0.15);
    color: {COLOR_APRON_REMOTE};
    border: 1px solid {COLOR_APRON_REMOTE};
}}

/* ==========================================================================
   6. INTERACTIVE CONTROLS & ACCESSIBILITY
   ========================================================================== */
/* Tabular Numbers */
.tabular-nums, table, .stDataFrame {{
    font-variant-numeric: tabular-nums;
}}

/* High Contrast Focus Rings (Accessibility WCAG AA) */
button:focus-visible, input:focus-visible, select:focus-visible {{
    outline: 2px solid {COLOR_BORDER_FOCUS} !important;
    outline-offset: 2px !important;
}}

/* Streamlit Tabs Styling */
button[data-baseweb="tab"] {{
    font-size: {FONT_SIZE_BODY} !important;
    color: {COLOR_TEXT_SECONDARY} !important;
}}

button[data-baseweb="tab"][aria-selected="true"] {{
    color: {COLOR_ACCENT_PRIMARY} !important;
    font-weight: 600 !important;
    border-bottom-color: {COLOR_ACCENT_PRIMARY} !important;
}}

/* Custom Aviation Scrollbar */
::-webkit-scrollbar {{
    width: 6px;
    height: 6px;
}}
::-webkit-scrollbar-track {{
    background: {COLOR_CANVAS_BG};
}}
::-webkit-scrollbar-thumb {{
    background: {COLOR_BORDER_SUBTLE};
    border-radius: 3px;
}}
::-webkit-scrollbar-thumb:hover {{
    background: {COLOR_BORDER_ACTIVE};
}}
</style>
"""


def get_custom_css() -> str:
    """Return the raw CSS styling string for testing and inspection."""
    return CUSTOM_CSS


def inject_custom_styles() -> None:
    """Inject the dark theme styles into the current Streamlit app session."""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
