# AEOLUS DASHBOARD — UI-R02 REPORT
# 05. MULTI-SCENARIO ISOLATION, CACHE PURGE & ROUTING SPECIFICATION

## 1. Executive Summary

A critical state vulnerability in multi-page Streamlit applications is **cross-scenario pollution**: when a user solves a problem under Scenario A (e.g. 120 flights), switches scenarios to Scenario B (e.g. 85 flights), and navigates to another page, residual state from Scenario A (such as `active_result`, selected flight IDs, or stale Gantt charts) may persist and misrepresent Scenario B.

UI-R02 establishes strict multi-scenario isolation barriers in both `dashboard/app.py` and `dashboard/pages/page_03_gate_operations.py`.

---

## 2. Global Scenario Switching Isolation Barrier

Implemented in `dashboard/app.py`:
```python
selected_scen = st.selectbox(
    label="Kịch bản:",
    options=scen_options,
    index=scen_index,
    label_visibility="collapsed",
    format_func=lambda sid: f"{sid} ({'120 chuyến' if '120' in sid else '85 chuyến'})",
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
```

### 2.1 Verification Evidence
Verified in `test_r02_t28`: Simulating a scenario switch when `ACTIVE_RESULT` and `SELECTED_FLIGHT_ID` are populated causes both to be reset to `None` and sets `JOB_STATE = IDLE`.

---

## 3. Page-Level Incompatible Result Guard

In addition to the global sidebar switch handler, `page_03_gate_operations.py` includes a defensive scenario guard at top-of-page execution:
```python
active_run: Optional[SolverRunView] = st.session_state.get(SessionStateKeys.ACTIVE_RESULT)
if active_run is not None and active_run.scenario_id != active_scenario_id:
    st.session_state[SessionStateKeys.ACTIVE_RESULT] = None
    st.session_state[SessionStateKeys.JOB_STATE] = UIJobState.IDLE.value
    st.session_state[SessionStateKeys.IS_SOLUTION_STALE] = False
    active_run = None
```
Verified in `test_r02_t29`: Any residual `active_run` whose `scenario_id` does not match `active_scenario_id` is immediately discarded before rendering.

---

## 4. Canonical PageKeys Routing (ISSUE-R00-10)

### 4.1 Specification of Canonical `PageKeys`
In `dashboard/core/state.py`:
```python
class PageKeys(str, Enum):
    """Canonical page keys for routing and navigation (Task R02-F / ISSUE-R00-10)."""
    CONTROL_TOWER = "01_control_tower"
    FLIGHT_INTELLIGENCE = "02_flight_intelligence"
    GATE_OPERATIONS = "03_gate_operations"
    OPTIMIZATION_LAB = "04_optimization_lab"
    ROBUSTNESS_LAB = "05_robustness_lab"
```

### 4.2 Replacement of Free-Text Navigation in Control Tower
In `dashboard/pages/page_01_control_tower.py`:
```python
with btn_c1:
    if st.button("🔬 Xem Flight Intelligence", use_container_width=True):
        st.session_state[SessionStateKeys.CURRENT_PAGE] = PageKeys.FLIGHT_INTELLIGENCE.value
        st.rerun()
with btn_c2:
    if st.button("🛫 Xem Gate Operations", use_container_width=True):
        st.session_state[SessionStateKeys.CURRENT_PAGE] = PageKeys.GATE_OPERATIONS.value
        st.rerun()
```
Verified in `test_r02_t26` and `test_r02_t27`: Free-text strings `"Flight Intelligence"` and `"Gate Operations"` are completely eradicated from navigation button assignments.
