"""Session state key registry and initialization helpers for Streamlit.

Ensures session persistence across page reruns without cross-session mutable singletons.
"""

from typing import Any, Dict

from dashboard.core.contracts import UIJobState


class SessionStateKeys:
    """Strongly typed session state key registry."""

    CURRENT_PAGE = "current_page"
    IS_RESEARCH_MODE = "is_research_mode"
    RESEARCH_MODE = "is_research_mode"
    ACTIVE_SCENARIO_ID = "active_scenario_id"
    SELECTED_SCENARIO_ID = "active_scenario_id"

    # Configurations
    DRAFT_CONFIGURATION = "draft_configuration"
    EXECUTED_CONFIGURATION = "executed_configuration"
    IS_SOLUTION_STALE = "is_solution_stale"

    # Selections and filters
    SELECTED_FLIGHT_ID = "selected_flight_id"
    SELECTED_TURN_ID = "selected_turn_id"
    SELECTED_GATE_ID = "selected_gate_id"
    SELECTED_MC_SCENARIO_ID = "selected_mc_scenario_id"
    CONCOURSE_FILTERS = "concourse_filters"

    # Execution and artifacts
    ACTIVE_RESULT = "active_result"
    JOB_STATE = "job_state"
    ARTIFACT_HEALTH = "artifact_health"


def get_initial_session_state() -> Dict[str, Any]:
    """Provide the default dictionary to initialize st.session_state cleanly."""
    return {
        SessionStateKeys.CURRENT_PAGE: "01_control_tower",
        SessionStateKeys.IS_RESEARCH_MODE: False,
        SessionStateKeys.ACTIVE_SCENARIO_ID: "SCEN_P09_CANONICAL_120",
        SessionStateKeys.DRAFT_CONFIGURATION: {
            "solver_name": "cpsat",
            "w_pref": 10.0,
            "w_remote": 200.0,
            "buffer_time_min": 15,
            "allow_overflow": True,
            "time_limit_sec": 30.0,
        },
        SessionStateKeys.EXECUTED_CONFIGURATION: {
            "solver_name": "cpsat",
            "w_pref": 10.0,
            "w_remote": 200.0,
            "buffer_time_min": 15,
            "allow_overflow": True,
            "time_limit_sec": 30.0,
        },
        SessionStateKeys.IS_SOLUTION_STALE: False,
        SessionStateKeys.SELECTED_FLIGHT_ID: None,
        SessionStateKeys.SELECTED_TURN_ID: None,
        SessionStateKeys.SELECTED_GATE_ID: None,
        SessionStateKeys.SELECTED_MC_SCENARIO_ID: 42,
        SessionStateKeys.CONCOURSE_FILTERS: ["T", "A", "REMOTE"],
        SessionStateKeys.ACTIVE_RESULT: None,
        SessionStateKeys.JOB_STATE: UIJobState.READY_IDLE.value,
        SessionStateKeys.ARTIFACT_HEALTH: {},
    }
