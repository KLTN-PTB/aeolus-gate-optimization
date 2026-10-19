"""Aeolus Gate Optimization Dashboard Application Shell (Phase P10-C).

Main entrypoint controlling routing, sidebar navigation, theme tokens,
preflight verification, and presentation/research mode states.
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from dashboard.components.styles import inject_custom_styles
from dashboard.core.contracts import UIJobState
from dashboard.core.state import PageKeys, SessionStateKeys, get_initial_session_state
from dashboard.pages import (
    page_01_control_tower,
    page_02_flight_intelligence,
    page_03_gate_operations,
    page_04_optimization_lab,
    page_05_robustness_lab,
)
from dashboard.services.preflight_service import PreflightService
from dashboard.services.scenario_service import ScenarioService


PAGES = {
    PageKeys.CONTROL_TOWER.value: {
        "title": "🗼 Control Tower (Tổng quan)",
        "module": page_01_control_tower,
    },
    PageKeys.FLIGHT_INTELLIGENCE.value: {
        "title": "🔬 Flight Intelligence (Dự báo Trễ)",
        "module": page_02_flight_intelligence,
    },
    PageKeys.GATE_OPERATIONS.value: {
        "title": "🛫 Gate Operations (Phân cổng & Gantt)",
        "module": page_03_gate_operations,
    },
    PageKeys.OPTIMIZATION_LAB.value: {
        "title": "⚡ Optimization Lab (Tối ưu)",
        "module": page_04_optimization_lab,
    },
    PageKeys.ROBUSTNESS_LAB.value: {
        "title": "🎲 Robustness Lab (Độ vững)",
        "module": page_05_robustness_lab,
    },
}


def init_session() -> None:
    """Initialize session state defaults if not already set."""
    defaults = get_initial_session_state()
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def render_sidebar(scenario_service: ScenarioService) -> str:
    """Render the persistent sidebar navigation and configuration controls."""
    with st.sidebar:
        st.markdown(
            """
            <div style="padding: 4px 0 16px 0;">
                <div style="font-size: 22px; font-weight: 700; color: #47C5C0; letter-spacing: -0.5px;">
                    ✈️ AEOLUS
                </div>
                <div style="font-size: 12px; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.5px;">
                    Flight Operations Intelligence
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("<p style='font-size: 12px; font-weight: 600; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;'>ĐIỀU HƯỚNG MÀN HÌNH</p>", unsafe_allow_html=True)
        
        # Navigation Radio
        page_keys = list(PAGES.keys())
        current_page_key = st.session_state.get(SessionStateKeys.CURRENT_PAGE, PageKeys.CONTROL_TOWER.value)
        
        # Normalize in case page title was set instead of key
        if current_page_key not in page_keys:
            if "Control" in current_page_key or "01" in current_page_key:
                current_page_key = PageKeys.CONTROL_TOWER.value
            elif "Flight" in current_page_key or "02" in current_page_key:
                current_page_key = PageKeys.FLIGHT_INTELLIGENCE.value
            elif "Gate" in current_page_key or "03" in current_page_key:
                current_page_key = PageKeys.GATE_OPERATIONS.value
            elif "Optimization" in current_page_key or "04" in current_page_key:
                current_page_key = PageKeys.OPTIMIZATION_LAB.value
            elif "Robustness" in current_page_key or "05" in current_page_key:
                current_page_key = PageKeys.ROBUSTNESS_LAB.value
            else:
                current_page_key = PageKeys.CONTROL_TOWER.value

        navigation_key = "sidebar_page_navigation"
        if navigation_key not in st.session_state or current_page_key != st.session_state.get("last_sidebar_page", current_page_key):
            st.session_state[navigation_key] = current_page_key
        selected_key = st.radio(
            label="Chọn trang:",
            options=page_keys,
            index=page_keys.index(current_page_key),
            format_func=lambda k: PAGES[k]["title"],
            label_visibility="collapsed",
            key=navigation_key,
        )
        st.session_state[SessionStateKeys.CURRENT_PAGE] = selected_key
        st.session_state["last_sidebar_page"] = selected_key

        st.markdown("<hr style='border-color: #263B5C; margin: 16px 0;'>", unsafe_allow_html=True)

        # Scenario Selector
        st.markdown("<p style='font-size: 12px; font-weight: 600; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;'>KỊCH BẢN VẬN HÀNH (ATL)</p>", unsafe_allow_html=True)
        scenarios = scenario_service.list_scenarios()
        scen_options = [s["id"] for s in scenarios]
        scen_labels = {
            s["id"]: s.get("name") or f"{s['id']} ({s['flights']} chuyến, {s['gates']} vị trí đỗ)"
            for s in scenarios
        }
        
        current_scen = st.session_state.get(SessionStateKeys.ACTIVE_SCENARIO_ID, "SCEN_P09_CANONICAL_120")
        scen_index = scen_options.index(current_scen) if current_scen in scen_options else 0
        
        selected_scen = st.selectbox(
            label="Kịch bản:",
            options=scen_options,
            index=scen_index,
            label_visibility="collapsed",
            format_func=lambda sid: scen_labels[sid],
        )
        if selected_scen != current_scen:
            st.session_state[SessionStateKeys.ACTIVE_SCENARIO_ID] = selected_scen
            # Reset active result and selection state to guarantee scenario isolation (Task R02-G)
            st.session_state[SessionStateKeys.ACTIVE_RESULT] = None
            st.session_state[SessionStateKeys.SELECTED_FLIGHT_ID] = None
            st.session_state[SessionStateKeys.SELECTED_TURN_ID] = None
            st.session_state[SessionStateKeys.SELECTED_GATE_ID] = None
            st.session_state[SessionStateKeys.IS_SOLUTION_STALE] = False
            st.session_state[SessionStateKeys.JOB_STATE] = UIJobState.IDLE.value
        else:
            st.session_state[SessionStateKeys.ACTIVE_SCENARIO_ID] = selected_scen
        st.caption(f"Mã kịch bản: `{selected_scen}`")

        st.markdown("<hr style='border-color: #263B5C; margin: 16px 0;'>", unsafe_allow_html=True)

        # Mode Switch
        st.markdown("<p style='font-size: 12px; font-weight: 600; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;'>CHẾ ĐỘ TRẢI NGHIỆM</p>", unsafe_allow_html=True)
        
        is_research = st.toggle(
            "Chế độ Nghiên cứu (Research Mode)",
            value=st.session_state.get(SessionStateKeys.IS_RESEARCH_MODE, False),
            help="Bật để xem các chỉ số thống kê thực nghiệm, TreeSHAP toàn cục và phân rã kỹ thuật sâu.",
        )
        st.session_state[SessionStateKeys.IS_RESEARCH_MODE] = is_research

        st.markdown("<div style='margin-top: 32px;'></div>", unsafe_allow_html=True)

        # Footer Status Card
        selected_year = next(s["year"] for s in scenarios if s["id"] == selected_scen)
        st.markdown(
            f"""
            <div style="background-color: #101B2A; border: 1px solid #263B5C; border-radius: 6px; padding: 12px; font-size: 12px; line-height: 1.5; color: #94A3B8;">
                <div style="color: #34C759; font-weight: 600; margin-bottom: 4px;">
                    ● HỆ THỐNG SẴN SÀNG (P10-C)
                </div>
                <div>Khóa luận Thạc sĩ / Kỹ sư</div>
                <div>Hub: Atlanta (ATL) • Năm {selected_year}</div>
                <div>Phiên bản: v1.0-frozen</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    return selected_key


def main() -> None:
    """Main application lifecycle controller."""
    st.set_page_config(
        page_title="Aeolus — Flight Operations Intelligence",
        page_icon="✈️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    init_session()
    inject_custom_styles()

    scenario_service = ScenarioService()
    active_page_key = render_sidebar(scenario_service)

    # Route to page
    page_module = PAGES[active_page_key]["module"]
    page_module.render_page()


if __name__ == "__main__":
    main()
