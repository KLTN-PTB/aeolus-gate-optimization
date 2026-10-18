"""Global Scenario Context Bar Component.

Displays pinned hub context, scenario selector, active execution mode, and solver status.
"""

from typing import Optional
import streamlit as st

from dashboard.core.contracts import ScenarioContext
from dashboard.core.state import SessionStateKeys


def render_context_bar(
    context: Optional[ScenarioContext] = None,
    solver_status_text: str = "TỐI ƯU TUYỆT ĐỐI (CP-SAT)",
    is_optimal: bool = True,
) -> None:
    """Render the pinned Global Scenario Context Bar.

    Args:
        context: Current active ScenarioContext.
        solver_status_text: Text describing current solver status.
        is_optimal: Whether the current solution is proven optimal.
    """
    is_research = st.session_state.get(SessionStateKeys.RESEARCH_MODE, False)
    mode_text = "NGHIÊN CỨU" if is_research else "BẢO VỆ / THUYẾT TRÌNH"
    mode_badge_class = "aeolus-badge-warning" if is_research else "aeolus-badge-info"
    status_badge_class = "aeolus-badge-success" if is_optimal else "aeolus-badge-info"

    scen_id = context.scenario_id if context else "SCEN_P09_CANONICAL_120"
    hub_name = "HARTSFIELD-JACKSON ATLANTA (ATL)"
    flight_count = context.flight_count if context else 120
    gate_count = context.gate_count if context else 26

    cols = st.columns([4, 2, 2, 2])
    with cols[0]:
        st.markdown(
            f"**✈️ TRUNG TÂM ĐIỀU HÀNH AEOLUS** &nbsp;|&nbsp; `{hub_name}`<br>"
            f"<span style='color: #94A3B8; font-size: 12px;'>Kịch bản: <code>{scen_id}</code> ({flight_count} chuyến • {gate_count} cổng)</span>",
            unsafe_allow_html=True,
        )
    with cols[1]:
        st.markdown(
            f"<div style='text-align: right;'>"
            f"<span style='color: #94A3B8; font-size: 11px;'>CHẾ ĐỘ GIAO DIỆN</span><br>"
            f"<span class='aeolus-badge {mode_badge_class}'>● {mode_text}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with cols[2]:
        st.markdown(
            f"<div style='text-align: right;'>"
            f"<span style='color: #94A3B8; font-size: 11px;'>TRẠNG THÁI BỘ GIẢI</span><br>"
            f"<span class='aeolus-badge {status_badge_class}'>🛡️ {solver_status_text}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with cols[3]:
        st.markdown(
            f"<div style='text-align: right;'>"
            f"<span style='color: #94A3B8; font-size: 11px;'>CÁCH LY 2024</span><br>"
            f"<span class='aeolus-badge aeolus-badge-success'>🔒 KHÓA BẢO VỆ V4</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
    st.markdown("<hr style='margin: 8px 0 16px 0; border-color: #263B5C;'>", unsafe_allow_html=True)
