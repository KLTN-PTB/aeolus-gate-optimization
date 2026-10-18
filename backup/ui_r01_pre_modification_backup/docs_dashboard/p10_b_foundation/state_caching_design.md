# Session State & Cache Architecture Specification

**Document ID:** `AEOLUS-P10-B-STATE-CACHE`  
**Phase:** P10-B (Dashboard Foundation, Data Contracts & Safe Integration)  
**Status:** IMPLEMENTED & TESTED  
**Target Package:** `dashboard/core/state.py` and `dashboard/services/cache_service.py`  

---

## 1. Executive Summary

This document specifies the persistent session state architecture and fingerprint-based memory caching protocols for the Aeolus dashboard. 

The architecture guarantees:
1. **Zero Session Contamination:** No mutable global singletons are shared across distinct user sessions.
2. **Decoupled Lifecycle States:** Frontend UI Job States (`IDLE`, `STALE`, `SOLVING`) are cleanly decoupled from mathematical solver termination statuses (`OPTIMAL_PROVEN`, `FEASIBLE_FOUND`).
3. **Scenario-Scoped Cache Invalidation:** Cache keys strictly partition data by `scenario_id` and content hash, ensuring Scenario A never contaminates Scenario B.

---

## 2. Session State Registry (`dashboard/core/state.py`)

All session variables are registered in `SessionStateKeys` with strongly typed default initializers:

```python
class SessionStateKeys:
    CURRENT_PAGE = "current_page"              # Active page string: "01_control_tower", etc.
    IS_RESEARCH_MODE = "is_research_mode"      # Boolean: Presentation (False) vs Research (True)
    ACTIVE_SCENARIO_ID = "active_scenario_id"  # Active scenario: "SCEN_P09_CANONICAL_120"
    
    # Configurations
    DRAFT_CONFIGURATION = "draft_configuration"         # Working parameters adjusted by user
    EXECUTED_CONFIGURATION = "executed_configuration"   # Exact parameters used in active solution
    IS_SOLUTION_STALE = "is_solution_stale"             # True if draft != executed
    
    # Selections and filters
    SELECTED_FLIGHT_ID = "selected_flight_id"           # Active flight in Flight Intelligence / Gantt
    SELECTED_TURN_ID = "selected_turn_id"               # Active turnaround pair in Tab B
    SELECTED_GATE_ID = "selected_gate_id"               # Focused gate in Gate Operations
    SELECTED_MC_SCENARIO_ID = "selected_mc_scenario_id" # Active scenario slice in Robustness Lab
    CONCOURSE_FILTERS = "concourse_filters"             # List[str]: ["T", "A", "REMOTE"]
    
    # Execution and artifacts
    ACTIVE_RESULT = "active_result"                     # SolverRunView of current solution
    JOB_STATE = "job_state"                             # UIJobState enum value
    ARTIFACT_HEALTH = "artifact_health"                 # Dict of preflight check states
```

### Lifecycle Transition Rules
1. **Sidebar Navigation Transition:**
   - Updating `current_page` does NOT modify `active_result`, `scenario_cache`, or `executed_configuration`. The user can freely navigate back and forth without losing computed solutions.
2. **Draft Slider Adjustment:**
   - Modifying any mathematical slider (`w_pref`, `w_remote`, `buffer_time_min`) mutates `draft_configuration` and sets `is_solution_stale = True`.
   - The UI displays an amber badge: `[⚠️ THAM SỐ CHƯA CẬP NHẬT]`, informing the user that the displayed Gantt chart reflects the previous solve until `[⚡ TỐI ƯU HÓA NGAY]` is triggered.
3. **Visual Filter Adjustment:**
   - Changing presentation-only filters (e.g., toggling concourse filter `["T", "A"]` or typing in flight search) modifies `concourse_filters` but does **NOT** mutate `draft_configuration` or mark the solution as stale.

---

## 3. Fingerprint Cache Service (`dashboard/services/cache_service.py`)

To eliminate redundant disk I/O and expensive DataFrame parsing on every reactive Streamlit script rerun, the `CacheService` caches immutable artifacts using content fingerprints:

### 3.1. Hashing Mechanics
- **File Fingerprinting:** `compute_file_fingerprint(path)` computes a streaming SHA256 hex digest of the file on disk. If the file is modified externally, the fingerprint changes automatically, triggering a cache reload.
- **Dictionary Fingerprinting:** `compute_dict_fingerprint(data)` serializes dictionary keys in deterministic sorted order and computes SHA256.

### 3.2. Scenario-Scoped Key Generation
Cache keys enforce scenario namespace isolation:
```python
cache_key = CacheService.generate_cache_key(
    scenario_id="SCEN_P09_CANONICAL_120",
    resource_type="solver_solution",
    params={"w_pref": 10.0, "w_remote": 200.0, "buffer": 15}
)
# Result: "SCEN_P09_CANONICAL_120::solver_solution::a4f91b7e08..."
```
This guarantees that solutions computed for the 120-flight canonical scenario cannot be returned when the user is inspecting the 85-flight stress scenario.

---

## 4. UI Job States vs. Mathematical Statuses

The dashboard strictly separates frontend lifecycle state from mathematical solver statuses:

| Domain | Enum Type | Valid Values | Semantic Meaning |
| :--- | :--- | :--- | :--- |
| **Frontend UI** | `UIJobState` | `INIT_LOADING`, `READY_IDLE`, `PARAM_STALE`, `SOLVING_LIVE`, `SOLVE_SUCCESS`, `FALLBACK_USED`, `ERROR_BOUNDARY` | Controls spinner, button disablement, and stale alert badges. |
| **Operations Research** | `SolverStatus` | `OPTIMAL`, `FEASIBLE`, `INFEASIBLE`, `UNKNOWN`, `MODEL_INVALID`, `TIMEOUT_NO_SOLUTION` | Mathematical condition reported by the solver backend. |
| **Operations Research** | `TerminationReason` | `OPTIMAL_PROVEN`, `FEASIBLE_FOUND`, `TIME_LIMIT`, `ITERATION_LIMIT`, `HEURISTIC_STOP`, `PROVEN_INFEASIBLE` | Exact algorithmic stop condition. |

### Mapping Protocol:
- If `status == OPTIMAL` and `termination_reason == OPTIMAL_PROVEN`: UI Job State is `SOLVE_SUCCESS`, Badge is `TỐI ƯU TUYỆT ĐỐI (Green)`.
- If `status == FEASIBLE` and `solver_name == "Deterministic Greedy"`: UI Job State is `SOLVE_SUCCESS`, Badge is `HEURISTIC THAM LAM (Amber)`.
- If `status == INFEASIBLE`: UI Job State is `ERROR_BOUNDARY`, Badge is `KHÔNG KHẢ THI (Red)`.
