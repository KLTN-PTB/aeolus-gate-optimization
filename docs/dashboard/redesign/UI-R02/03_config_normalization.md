# AEOLUS DASHBOARD — UI-R02 REPORT
# 03. CONFIGURATION NORMALIZATION & PARAMETER STALENESS SPECIFICATION

## 1. Executive Summary

Prior to UI-R02, **ISSUE-R00-08** revealed that `ExperimentService.is_stale()` contained critical loopholes:
1. It omitted keys present in `draft_config` if absent from `executed_config` (due to `draft_val is not None and exec_val is not None` guard).
2. It ignored `scenario_id` modifications, meaning that changing the active scenario while keeping solver sliders identical did not flag the solution as stale.
3. It omitted `time_limit_sec` from `SOLVER_IDENTITY_KEYS`.
4. It lacked canonical type coercion (e.g., float vs integer weights, leading whitespace, string casing).
5. It returned a boolean without diagnostic information about which keys differed.

UI-R02 implements `normalize_optimization_config` and `check_staleness_detailed` to provide exhaustive, transparent staleness detection.

---

## 2. Solver Identity Key Registry

The authoritative list of parameters that mathematically impact optimization outcomes is defined in `ExperimentService`:
```python
SOLVER_IDENTITY_KEYS: List[str] = [
    "scenario_id",
    "solver_name",
    "w_pref",
    "w_remote",
    "w_conflict",
    "buffer_time_min",
    "time_limit_sec",
    "allow_overflow",
    "finite_remote_capacity",
    "cp_sat_formulation",
]
```

### 2.1 Separation of Visual Filters (`CHART_ONLY_FILTER_KEYS`)
To ensure user interactivity (panning, filtering concourses, searching flight numbers) never flags mathematical solutions as stale:
```python
CHART_ONLY_FILTER_KEYS: List[str] = [
    "concourse_filter",
    "search_query",
    "time_zoom_start",
    "time_zoom_end",
    "highlight_carrier",
    "view_mode",
]
```
Verified in `test_r02_t20`: mutating `concourse_filter` or `view_mode` returns `True` for `is_presentation_filter_mutation()`, but generates an identical `compute_configuration_hash()`.

---

## 3. Canonical Configuration Normalization (`normalize_optimization_config`)

Implemented in `dashboard/services/experiment_service.py`:
```python
@classmethod
def normalize_optimization_config(cls, raw_config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Normalize raw or draft optimization configuration into canonical types and defaults."""
    if not raw_config:
        return {}
    cfg = dict(raw_config)
    norm: Dict[str, Any] = {}

    if "scenario_id" in cfg and cfg["scenario_id"] is not None:
        norm["scenario_id"] = str(cfg["scenario_id"]).strip()

    if "solver_name" in cfg and cfg["solver_name"] is not None:
        norm["solver_name"] = str(cfg["solver_name"]).lower().strip()

    for float_key in ("w_pref", "w_remote", "w_conflict", "time_limit_sec"):
        if float_key in cfg and cfg[float_key] is not None:
            norm[float_key] = float(cfg[float_key])

    for int_key in ("buffer_time_min", "solver_seed"):
        if int_key in cfg and cfg[int_key] is not None:
            norm[int_key] = int(cfg[int_key])

    for bool_key in ("allow_overflow", "finite_remote_capacity", "warm_start"):
        if bool_key in cfg and cfg[bool_key] is not None:
            norm[bool_key] = bool(cfg[bool_key])

    for str_key in ("cp_sat_formulation", "objective_version", "prediction_source"):
        if str_key in cfg and cfg[str_key] is not None:
            norm[str_key] = str(cfg[str_key]).strip()

    return norm
```

---

## 4. Detailed Staleness Inspection (`check_staleness_detailed`)

```python
@classmethod
def check_staleness_detailed(
    cls,
    draft_config: Optional[Dict[str, Any]],
    executed_config: Optional[Dict[str, Any]],
) -> Tuple[bool, List[str]]:
    """Detailed staleness comparison between draft parameters and executed solution configuration."""
    if executed_config is None:
        return True, ["executed_config_missing"]
    if draft_config is None:
        return False, []

    norm_draft = cls.normalize_optimization_config(draft_config)
    norm_exec = cls.normalize_optimization_config(executed_config)

    differing_keys: List[str] = []
    for key in cls.SOLVER_IDENTITY_KEYS:
        if key in norm_draft:
            draft_val = norm_draft[key]
            exec_val = norm_exec.get(key)
            if exec_val is None or draft_val != exec_val:
                differing_keys.append(key)

    return len(differing_keys) > 0, differing_keys
```

### 4.1 UI Presentation of Staleness
When `is_stale == True` in `page_03_gate_operations.py`:
- `st.session_state[SessionStateKeys.JOB_STATE]` is set to `UIJobState.STALE_RESULT.value`.
- A warning badge is rendered dynamically specifying the exact differing parameters:
  `⚠️ Tham số đã đổi (w_pref, buffer_time_min) — Nhấn Tối ưu hóa để chạy lại`
