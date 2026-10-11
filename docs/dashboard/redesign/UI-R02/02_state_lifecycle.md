# AEOLUS DASHBOARD — UI-R02 REPORT
# 02. SESSION STATE, LIFECYCLE MACHINE & AUTO-SOLVE ELIMINATION

## 1. Executive Summary

In the initial audit baseline, **ISSUE-R00-01** documented that `page_03_gate_operations.py` unconditionally executed `opt_service.solve(flights, gates, solver_name="cpsat")` whenever the page loaded or a scenario changed without a cached solution. This caused:
1. Significant latency and blocking on page navigation.
2. Inability for users to inspect the initial nominal plan without triggering solver computation.
3. Wasteful OR-Tools thread allocations.
4. Spurious "OPTIMAL" certifications displayed before any user action occurred.

UI-R02 v2.0 resolves this defect by eliminating automatic solve, introducing a formal `UIJobState` finite-state machine, and cleanly handling the `active_run is None` baseline.

---

## 2. Canonical UI Lifecycle State Machine (`UIJobState`)

The `UIJobState` enum in `dashboard/core/contracts.py` defines the frontend lifecycle:
```python
class UIJobState(str, Enum):
    IDLE = "IDLE"
    VALIDATING = "VALIDATING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    STALE_RESULT = "STALE_RESULT"
    INCOMPATIBLE_RESULT = "INCOMPATIBLE_RESULT"
    # Backwards-compatible legacy tokens
    INIT_LOADING = "INIT_LOADING"
    READY_IDLE = "READY_IDLE"
    PARAM_STALE = "PARAM_STALE"
    SOLVING_LIVE = "SOLVING_LIVE"
    SOLVE_SUCCESS = "SOLVE_SUCCESS"
    FALLBACK_USED = "FALLBACK_USED"
    ERROR_BOUNDARY = "ERROR_BOUNDARY"
```

### 2.1 State Transition Diagram

```
                 +-----------------------+
                 |       Session Init    |
                 +-----------+-----------+
                             |
                             v
+--------------------->   [ IDLE ]  <-----------------------+
|                            |                              |
| Scenario                   | User clicks 'TỐI ƯU HÓA'     | Scenario Change /
| Change                     v                              | Reset
|                     [ VALIDATING ]                        |
|                            |                              |
|                            v                              |
|                       [ RUNNING ]                         |
|                       /         \                         |
|          Solve passes/           \ Solve fails or error   |
|                     v             v                       |
|               [ COMPLETED ]    [ FAILED ] ----------------+
|                     |
| User changes params |
|                     v
+-------------- [ STALE_RESULT ]
```

---

## 3. Elimination of Auto CP-SAT Execution (ISSUE-R00-01)

### 3.1 Code Audit & Modification in `page_03_gate_operations.py`

#### Before (Vulnerable Auto-Solve Block):
```python
# Lines 100-113 (Old):
active_run = st.session_state.get(SessionStateKeys.ACTIVE_RESULT)
if active_run is None or active_run.scenario_id != active_scenario_id:
    opt_service = OptimizationService()
    initial_run, _, _ = opt_service.solve(
        flights=flights,
        gates=gates,
        solver_name="cpsat",
        scenario_id=active_scenario_id,
    )
    st.session_state[SessionStateKeys.ACTIVE_RESULT] = initial_run
    active_run = initial_run
```

#### After (Strict Decoupled Check):
```python
# UI-R02 Compliant:
active_run: Optional[SolverRunView] = st.session_state.get(SessionStateKeys.ACTIVE_RESULT)
if active_run is not None and active_run.scenario_id != active_scenario_id:
    st.session_state[SessionStateKeys.ACTIVE_RESULT] = None
    st.session_state[SessionStateKeys.JOB_STATE] = UIJobState.IDLE.value
    st.session_state[SessionStateKeys.IS_SOLUTION_STALE] = False
    active_run = None
```

### 3.2 UI Behavior When `active_run is None`
1. **Context Bar**:
   - Status badge displays `CHƯA PHÂN BỔ (IDLE)` with `is_optimal=False`.
   - Never claims `OPTIMAL` or `VERIFIED` on unexecuted scenarios.
2. **Gantt Plan Canvas**:
   - Radio selector defaults to `Danh định Gốc (Nominal)` instead of forcing an empty or non-existent optimized plan.
   - If the user explicitly selects `Tối ưu Hóa (Optimized)` while `active_run is None`, an informational prompt is rendered:
     `"ℹ️ Kịch bản chưa có kết quả tối ưu. Hiển thị kế hoạch danh định gốc (Nominal). Nhấn 'TỐI ƯU HÓA NGAY (RUN SOLVER)' trong bảng điều khiển bên phải để phân cổng."`
3. **Independent Verification Card**:
   - In nominal mode, shows conflict diagnostic for the baseline timetable.
   - In optimized mode with `active_run is None`, displays:
     `"ℹ️ CHƯA CÓ LỜI GIẢI ĐỂ KIỂM ĐỊNH. Hãy bấm 'TỐI ƯU HÓA NGAY (RUN SOLVER)' để phân cổng và kiểm định độc lập."`
4. **Execution Form**:
   - State badge displays `ℹ️ Sẵn sàng chạy giải thuật phân cổng`.
   - Explicit primary button `⚡ TỐI ƯU HÓA NGAY (RUN SOLVER)` triggers validation, spinner, solver invocation, and state update to `COMPLETED`.
