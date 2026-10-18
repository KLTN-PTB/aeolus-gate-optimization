"""Aeolus Custom CSS Styles and Theme Injection.

Adheres strictly to AEOLUS-P10-A-DESIGN-SYS-03.
Injects dark mode rules, high-contrast borders, typography, and card tokens.
"""

import streamlit as st


CUSTOM_CSS = """
<style>
/* Base Streamlit App Styling */
.stApp {
    background-color: #101B2A !important;
    color: #F0F4F8 !important;
    font-family: 'Inter', 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

/* Sidebar styling */
section[data-testid="stSidebar"] {
    background-color: #162338 !important;
    border-right: 1px solid #263B5C !important;
}

section[data-testid="stSidebar"] .stRadio label {
    color: #F0F4F8 !important;
    font-weight: 500;
}

/* Typography */
h1, h2, h3, h4, h5, h6 {
    color: #F0F4F8 !important;
    font-weight: 600 !important;
    letter-spacing: -0.2px;
}

/* Card Container */
.aeolus-card {
    background-color: #162338;
    border: 1px solid #263B5C;
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 16px;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
}

.aeolus-card:hover {
    border-color: #3B5780;
}

/* Global Context Bar */
.aeolus-context-bar {
    background-color: #162338;
    border: 1px solid #263B5C;
    border-radius: 8px;
    padding: 12px 20px;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

/* KPI Scorecard */
.aeolus-kpi-card {
    background-color: #162338;
    border: 1px solid #263B5C;
    border-radius: 8px;
    padding: 14px 16px;
    min-height: 110px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}

.aeolus-kpi-title {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #94A3B8;
    font-weight: 600;
}

.aeolus-kpi-value {
    font-size: 24px;
    font-weight: 700;
    color: #F0F4F8;
    font-variant-numeric: tabular-nums;
    margin: 4px 0;
}

.aeolus-kpi-subtitle {
    font-size: 12px;
    color: #94A3B8;
    display: flex;
    align-items: center;
    gap: 4px;
}

/* Status Badges */
.aeolus-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
    font-family: 'JetBrains Mono', Consolas, monospace;
}

.aeolus-badge-success {
    background-color: rgba(52, 199, 89, 0.15);
    color: #34C759;
    border: 1px solid #34C759;
}

.aeolus-badge-warning {
    background-color: rgba(229, 173, 85, 0.15);
    color: #E5AD55;
    border: 1px solid #E5AD55;
}

.aeolus-badge-error {
    background-color: rgba(228, 119, 119, 0.15);
    color: #E47777;
    border: 1px solid #E47777;
}

.aeolus-badge-info {
    background-color: rgba(71, 197, 192, 0.15);
    color: #47C5C0;
    border: 1px solid #47C5C0;
}

.aeolus-badge-remote {
    background-color: rgba(167, 139, 250, 0.15);
    color: #A78BFA;
    border: 1px solid #A78BFA;
}

/* Tabular number styling */
.tabular-nums {
    font-variant-numeric: tabular-nums;
}

/* Custom Scrollbar */
::-webkit-scrollbar {
    width: 6px;
    height: 6px;
}
::-webkit-scrollbar-track {
    background: #101B2A;
}
::-webkit-scrollbar-thumb {
    background: #263B5C;
    border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
    background: #3B5780;
}
</style>
"""


def inject_custom_styles() -> None:
    """Inject the dark theme styles into the current Streamlit app session."""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
