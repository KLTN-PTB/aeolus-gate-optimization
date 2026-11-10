"""Global Scenario Context Bar Component (Phase UI-R03).

Displays pinned hub context, active scenario, interface execution mode,
and contextual solver or prediction model status with accessible typography.
"""

from typing import Optional
import streamlit as st

from dashboard.core.contracts import ScenarioContext
from dashboard.core.state import PageKeys, SessionStateKeys


def render_context_bar(
    context: Optional[ScenarioContext] = None,
    solver_status_text: str = "LỊCH CƠ SỞ (CANONICAL BASELINE)",
    is_optimal: bool = False,
    show_solver_status: Optional[bool] = None,
    scenario_id: Optional[str] = None,
    current_page_key: Optional[str] = None,
) -> None:
    """Render the pinned Global Scenario Context Bar.

    Args:
        context: Current active ScenarioContext.
        solver_status_text: Text describing current solver status.
        is_optimal: Whether the current solution is proven optimal.
        show_solver_status: Explicit flag to show solver status. If None,
            automatically detects whether the active page is Flight Intelligence.
        scenario_id: Optional scenario ID override string.
        current_page_key: Optional current page key override.
    """
    is_research = st.session_state.get(SessionStateKeys.RESEARCH_MODE, False)
    current_page = current_page_key or st.session_state.get(SessionStateKeys.CURRENT_PAGE, PageKeys.CONTROL_TOWER.value)

    mode_text = "NGHIÊN CỨU (RESEARCH)" if is_research else "BẢO VỆ / THUYẾT TRÌNH (PRESENTATION)"
    mode_badge_class = "aeolus-badge-warning" if is_research else "aeolus-badge-info"
    status_badge_class = "aeolus-badge-success" if is_optimal else "aeolus-badge-info"

    scen_id = scenario_id or (context.scenario_id if context else "SCEN_P09_CANONICAL_120")
    hub_name = "HARTSFIELD-JACKSON ATLANTA (ATL)"
    flight_count = context.flight_count if context else 120
    gate_count = context.gate_count if context else 26

    # Contextual middle-right panel: determine whether to show solver or prediction status (Task R03-E)
    if show_solver_status is False or (show_solver_status is None and current_page == PageKeys.FLIGHT_INTELLIGENCE.value):
        context_status_title = "MÔ HÌNH DỰ BÁO TRỄ"
        context_status_html = '<span class="aeolus-badge aeolus-badge-info">🔬 DUAL-CORE ML (NGBoost + XGBoost)</span>'
    else:
        context_status_title = "TRẠNG THÁI BỘ GIẢI"
        context_status_html = f'<span class="aeolus-badge {status_badge_class}">🛡️ {solver_status_text}</span>'

    cols = st.columns([4, 2, 2, 2])
    with cols[0]:
        st.markdown(
            f"**✈️ TRUNG TÂM ĐIỀU HÀNH AEOLUS** &nbsp;|&nbsp; `{hub_name}`<br>"
            f"<span style='color: #94A3B8; font-size: 13px;'>Kịch bản: <code>{scen_id}</code> ({flight_count} chuyến • {gate_count} cổng)</span>",
            unsafe_allow_html=True,
        )
    with cols[1]:
        st.markdown(
            f"<div style='text-align: right;'>"
            f"<span style='color: #94A3B8; font-size: 12px; font-weight: 600;'>CHẾ ĐỘ GIAO DIỆN</span><br>"
            f"<span class='aeolus-badge {mode_badge_class}'>● {mode_text}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with cols[2]:
        st.markdown(
            f"<div style='text-align: right;'>"
            f"<span style='color: #94A3B8; font-size: 12px; font-weight: 600;'>{context_status_title}</span><br>"
            f"{context_status_html}"
            f"</div>",
            unsafe_allow_html=True,
        )
    with cols[3]:
        st.markdown(
            f"<div style='text-align: right;'>"
            f"<span style='color: #94A3B8; font-size: 12px; font-weight: 600;'>CÁCH LY 2024</span><br>"
            f"<span class='aeolus-badge aeolus-badge-success'>🔒 KHÓA BẢO VỆ V4</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
    st.markdown("<hr style='margin: 8px 0 16px 0; border-color: #263B5C;'>", unsafe_allow_html=True)
