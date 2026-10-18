"""Shared Reusable UI Components for Aeolus Dashboard (Phase UI-R03).

Provides standardized PageHeader, SectionHeader, EmptyState, ErrorState,
StatusIndicator, and ChartPanel components adhering to the design system.
"""

from typing import Optional
import streamlit as st


def render_page_header(
    title: str,
    subtitle: Optional[str] = None,
    badge_text: Optional[str] = None,
    badge_type: str = "info",
    icon: Optional[str] = None,
    badge_status: Optional[str] = None,
) -> None:
    """Render a standardized page title banner with optional badge and subtitle."""
    effective_badge_type = badge_status or badge_type
    icon_str = f"{icon} " if icon else ""
    badge_html = (
        f'<span class="aeolus-badge aeolus-badge-{effective_badge_type}" style="margin-left: 12px; vertical-align: middle;">{badge_text}</span>'
        if badge_text
        else ""
    )
    subtitle_html = (
        f'<div style="color: #94A3B8; font-size: 14px; margin-top: 4px; margin-bottom: 12px;">{subtitle}</div>'
        if subtitle
        else ""
    )

    st.markdown(
        f"""
        <div class="aeolus-page-header" style="margin-bottom: 8px;">
            <div style="display: flex; align-items: center;">
                <h1 class="aeolus-page-title" style="margin: 0; display: inline;">{icon_str}{title}</h1>
                {badge_html}
            </div>
            {subtitle_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_header(
    title: str,
    subtitle: Optional[str] = None,
    badge_text: Optional[str] = None,
    badge_type: str = "info",
    description: Optional[str] = None,
    divider: bool = False,
) -> None:
    """Render a section header with consistent font scale (20px) and optional subtitle."""
    effective_subtitle = subtitle or description
    badge_html = (
        f'<span class="aeolus-badge aeolus-badge-{badge_type}" style="margin-left: 8px;">{badge_text}</span>'
        if badge_text
        else ""
    )
    subtitle_html = (
        f'<div style="color: #94A3B8; font-size: 13px; margin-top: 2px; margin-bottom: 8px;">{effective_subtitle}</div>'
        if effective_subtitle
        else ""
    )
    divider_html = "<hr style='border-color: #263B5C; margin: 12px 0;'>" if divider else ""

    st.markdown(
        f"""
        <div class="aeolus-section-header" style="margin-top: 16px; margin-bottom: 8px;">
            <div style="display: flex; align-items: center;">
                <h2 class="aeolus-section-title" style="margin: 0; display: inline; font-size: 20px;">{title}</h2>
                {badge_html}
            </div>
            {subtitle_html}
            {divider_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_empty_state(
    title: str,
    message: str,
    icon: str = "ℹ️",
    action_label: Optional[str] = None,
) -> None:
    """Render an aerospace-themed empty state card when data is absent or unexecuted."""
    action_html = (
        f'<div style="margin-top: 12px; font-size: 13px; color: #47C5C0; font-weight: 600;">👉 {action_label}</div>'
        if action_label
        else ""
    )
    st.markdown(
        f"""
        <div class="aeolus-card aeolus-empty-state" style="text-align: center; padding: 32px 16px; border-style: dashed; border-color: #263B5C;">
            <div style="font-size: 32px; margin-bottom: 8px;">{icon}</div>
            <div style="color: #F0F4F8; font-weight: 600; font-size: 16px; margin-bottom: 6px;">{title}</div>
            <div style="color: #94A3B8; font-size: 13px; max-width: 500px; margin: 0 auto;">{message}</div>
            {action_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_error_state(
    title: str,
    error_message: Optional[str] = None,
    icon: str = "⚠️",
    error_details: Optional[str] = None,
) -> None:
    """Render a high-contrast error boundary card for constraint or validation failures."""
    details = error_details or error_message or "Đã xảy ra lỗi không xác định."
    st.markdown(
        f"""
        <div class="aeolus-card aeolus-badge-error" style="padding: 20px; border-color: #E47777; background-color: rgba(228, 119, 119, 0.08);">
            <div style="display: flex; align-items: flex-start; gap: 12px;">
                <div style="font-size: 24px; line-height: 1;">{icon}</div>
                <div>
                    <div style="color: #E47777; font-weight: 700; font-size: 15px; margin-bottom: 4px;">{title}</div>
                    <div style="color: #F0F4F8; font-size: 13px; line-height: 1.4;">{details}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_status_indicator(
    status_text: Optional[str] = None,
    status_type: str = "info",
    icon: Optional[str] = None,
    status: Optional[str] = None,
    label: Optional[str] = None,
) -> None:
    """Render a dual-encoded status pill badge."""
    effective_text = label or status_text or ""
    effective_type = status or status_type
    icon_str = f"{icon} " if icon else ""
    st.markdown(
        f'<span class="aeolus-badge aeolus-badge-{effective_type}">{icon_str}{effective_text}</span>',
        unsafe_allow_html=True,
    )
