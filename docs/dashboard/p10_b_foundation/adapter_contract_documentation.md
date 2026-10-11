# Adapter & View Model Contract Documentation

**Document ID:** `AEOLUS-P10-B-ADAPTER-DOC`  
**Phase:** P10-B (Dashboard Foundation, Data Contracts & Safe Integration)  
**Status:** IMPLEMENTED & TESTED  
**Target Package:** `dashboard/core/` and `dashboard/adapters/`  

---

## 1. Executive Summary

This document specifies the concrete contracts and mapping mechanisms governing data transformation between Aeolus backend domain objects/persistent artifacts and the frontend **View Models**.

By introducing these strongly typed View Models, the dashboard layer is completely decoupled from backend internals, preventing breaking changes, guaranteeing zero ground-truth data leakage during planning mode, and maintaining numerical precision without premature rounding.

---

## 2. View Models Specification (`dashboard/core/contracts.py`)

### 2.1. `ScenarioContext`
Represents the global operational scenario metadata rendered in the header and context bars.
- `scenario_id`: `str` (e.g. `"SCEN_P09_CANONICAL_120"`).
- `hub_iata`: `str` (`"ATL"`).
- `flight_count`: `int` ($120$).
- `gate_count`: `int` ($25$).
- `remote_capacity`: `int` ($1$).
- `scenario_hash`: `str` (SHA256 fingerprint).
- `provenance`: `ProvenanceType.SCHEDULE_BASELINE`.

### 2.2. `FlightPredictionView`
Represents flight-level delay predictions in planning mode.
- `flight_id`: `str` (e.g. `"DL1024"`).
- `carrier`, `origin`, `destination`: `str`.
- `sched_arr_time_min`: `int` (Minutes from midnight, $0 \le t \le 2880$).
- `predicted_arr_delay_min`: `float` (Signed delay, e.g. `+18.4`).
- `lower_bound_delay_min`, `upper_bound_delay_min`: `Optional[float]` ($90\%$ confidence interval).
- `confidence_score`: `Optional[float]` ($0.0 \le c \le 1.0$).
- `risk_category`: `RiskCategory` (`LOW` if $<15$m, `MODERATE` if $15\text{--}30$m, `HIGH` if $\ge 30$m).
- `top_shap_features`: `Dict[str, float]` (Top positive/negative SHAP attributions).
- `provenance`: `ProvenanceType.PRECOMPUTED_PREDICTION` or `NATIVE_INFERENCE`.
- **Anti-Leakage Guard:** Prohibits ground-truth columns (`arr_delay`, `actual_arr_delay`, etc.).

### 2.3. `AircraftTurnView`
Represents the physical turnaround connection between an inbound and outbound leg.
- `turn_id`: `str` (e.g. `"TURN_DL1024_DL1502"`).
- `inbound_flight_id`, `outbound_flight_id`: `str`.
- `sched_turn_window_min`: `int` (Scheduled turnaround duration, e.g. $75$ min).
- `min_turn_time_min`: `int` (Minimum required service time, e.g. $45$ min).
- `sched_slack_min`: `int` ($T_{\text{window}} - T_{\text{min\_turn}} = 30$ min).
- `inbound_delay_absorbed_min`: `float` ($\min(T_{\text{slack}}, \hat{d}_{\text{arr}})$).
- `remaining_slack_min`: `float` ($\max(0, T_{\text{slack}} - \hat{d}_{\text{arr}})$).
- `propagated_outbound_delay_min`: `float` ($\max(0, \hat{d}_{\text{arr}} - T_{\text{slack}})$).
- `slack_risk_index`: `RiskCategory` (`HIGH` if remaining slack $< 5$ min).
- `gate_occupancy_start_min`, `gate_occupancy_end_min`: `int`.
- `buffer_min`: `int = 15`.
- **Property:** `total_blocked_end_min` $= \text{gate\_occupancy\_end\_min} + 15$.

### 2.4. `GateTimelineView`
Represents an individual aircraft occupancy block on the interactive Gate Gantt chart.
- `assignment_id`: `str` (`"ASN_FLIGHT_GATE_START"`).
- `flight_id`, `gate_id`, `concourse`: `str`.
- `start_min`, `end_min`: `int`.
- `buffer_min`: `int = 15`.
- `is_reassigned`: `bool`.
- `is_remote`: `bool`.
- `has_conflict`: `bool`.
- **Properties:**
  - `occupancy_interval`: `(start_min, end_min)`
  - `total_blocked_interval`: `(start_min, end_min + buffer_min)`

### 2.5. `SolverRunView`
Represents the complete solution output from an optimization solver run.
- `solver_name`: `str` (`"CP-SAT (Sparse Interval)"`, `"Deterministic Greedy"`, etc.).
- `scenario_id`: `str`.
- `objective_value`: `Optional[float]`.
- `decision_cost`: `float` ($w_{\text{pref}} \cdot N_{\text{reassign}} + w_{\text{remote}} \cdot N_{\text{remote}} + w_{\text{conflict}} \cdot N_{\text{conflict}}$).
- `reporting_cost`: `float` (Exogenous airspace delay cost).
- `reassignment_count`, `remote_gate_count`, `conflict_count`: `int`.
- `solve_time_sec`: `float` (Accurate wall-clock time).
- `status`: `str` (`"OPTIMAL"`, `"FEASIBLE"`, `"INFEASIBLE"`, etc.).
- `termination_reason`: `str`.
- `is_optimal_proven`: `bool` (Only `True` for CP-SAT with `OPTIMAL_PROVEN`).
- `optimality_gap`: `Optional[float]`.
- `assignments`: `List[GateTimelineView]`.

### 2.6. `RobustnessView`
Represents the aggregate statistical metrics across the 500-scenario Monte Carlo stress tests.
- `mode_name`: `str` (`"MODE_A_FIXED_PLAN"`, `"MODE_B_REACTIVE_RECOURSE"`, `"MODE_C_ORACLE_BASELINE"`).
- `scenario_count`: `int = 500`.
- `mean_cost`, `median_cost`, `std_cost`, `cvar_95_cost`: `float`.
- `physical_conflict_rate`: `float` ($74.8\%$ for Mode A, $0.0\%$ for Mode B).
- `static_invalidation_rate`: `float` ($100.0\%$ for Mode A due to delayed timeline shifts).
- `mean_reassignments`: `float` ($2.556$ for Mode B and Mode C).
- `is_deployable`: `bool` (`False` for Mode C oracle).
- `academic_notes`: `str` (Documents Findings D1 & D2).

---

## 3. Adapters Architecture (`dashboard/adapters/`)

| Adapter Function | Source Input | Target Output View Model | Key Validation / Rule Enforced |
| :--- | :--- | :--- | :--- |
| `adapt_prediction_row_to_view` | Raw prediction dict / CSV row | `FlightPredictionView` | Rejects forbidden actual delay columns (`arr_delay`). |
| `adapt_turn_to_view` | `SimulationTurnResult` | `AircraftTurnView` | Validates turnaround slack absorption algebra. |
| `adapt_assignment_to_view` | `GateAssignment` domain object | `GateTimelineView` | Extracts concourse prefix, computes 15m buffer interval. |
| `adapt_solver_result_to_view`| `OptimizationResult` domain object | `SolverRunView` | Deconstructs decision cost vs reporting cost, locks `is_optimal_proven`. |
| `adapt_monte_carlo_to_views` | `statistical_summary.json` dict | `Dict[str, RobustnessView]` | Injects Finding D1 & D2 scientific disclaimers. |

---

## 4. Safe Artifact Loader (`dashboard/adapters/artifact_loader.py`)

The `ArtifactLoader` enforces:
1. **Path Traversal Protection:** Every input path is resolved and checked via `DashboardConfig.is_path_allowlisted`. Attempting `../../` raises `PermissionError`.
2. **Schema Integrity:**
   - JSON files are checked for mandatory keys (`required_keys`).
   - CSV / Parquet files are checked for mandatory columns (`required_columns`).
   - Corrupt files raise `ArtifactValidationError`. Missing files raise `ArtifactNotFoundError`.
3. **Zero Untrusted Code Execution:** No `eval()`, `exec()`, or unverified pickle/joblib deserialization.
