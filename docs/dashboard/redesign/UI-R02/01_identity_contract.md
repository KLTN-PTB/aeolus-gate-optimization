# AEOLUS DASHBOARD — UI-R02 REPORT
# 01. 3-TIER SCENARIO & PROBLEM IDENTITY CONTRACT SPECIFICATION

## 1. Executive Summary

Prior to UI-R02, the Aeolus dashboard relied on a trivial, hardcoded token for scenario hashing (`compute_scenario_hash` generated `hashlib.sha256(f"{scenario_id}::ATL::BTS_2023::SEED_42")`), identified in technical audit as **ISSUE-R00-06**. This failed to capture data modifications, flight timing shifts, gate capacity changes, or parameter alterations.

UI-R02 v2.0 establishes a mathematically rigorous, deterministic **3-Tier Identity Architecture**:
1. **Tier 1 — Dataset Identity (`ScenarioDataIdentity`)**: Cryptographic digest of the underlying flight and gate timetable.
2. **Tier 2 — Mathematical Problem Identity (`ProblemIdentity`)**: Formulation digest capturing objective weights, buffer rules, and overflow policies.
3. **Tier 3 — Execution Identity (`ExecutionIdentity`)**: Solver invocation digest tracking requested vs effective solver, formulation, limits, seeds, and execution run ID.

---

## 2. Tier 1: Authoritative Scenario Dataset Identity (`ScenarioDataIdentity`)

### 2.1 View Model Contract
Implemented in `dashboard/core/contracts.py`:
```python
@dataclass(frozen=True)
class ScenarioDataIdentity:
    scenario_id: str
    scenario_digest: str
    flight_count: int
    gate_count: int
    remote_capacity: int = 1
    hub_iata: str = "ATL"
    dataset_version: str = "BTS_2023_V1"
    generator_seed: Optional[int] = None
    schema_version: str = "2.0"
```

### 2.2 Canonical Scenario Serialization & Digest Formula
The function `compute_canonical_scenario_digest(flights, gates, scenario_id, generator_seed)` in `dashboard/services/scenario_service.py` provides permutation-invariant hashing:

$$\text{Digest} = \text{SHA-256}\Big(\text{JSON}_{\text{canonical}}\big(\text{ScenarioPayload}\big)\Big)$$

Where:
- Flights are sorted strictly by `flight_id` (lexicographical).
- Gates are sorted strictly by `gate_id` (lexicographical).
- Extracted Flight properties:
  - `flight_id`: string
  - `carrier`: string
  - `aircraft_type`: string
  - `scheduled_arrival_min`: int
  - `scheduled_departure_min`: int
  - `predicted_arrival_min`: int
  - `simulated_departure_min`: int
  - `min_turnaround_min`: int
  - `buffer_min`: int
  - `nominal_gate_id`: string
- Extracted Gate properties:
  - `gate_id`: string
  - `gate_index`: int
  - `is_overflow`: bool
  - `resource_type`: string
  - `capacity`: float or `"unbounded"`
  - `allowed_carriers`: sorted list or None
  - `allowed_aircraft_types`: sorted list or None
- JSON encoding parameters: `sort_keys=True, separators=(",", ":")` ensuring zero whitespace variance.

### 2.3 Verification Properties
- **Permutation Invariance**: Verified in `test_r02_t02`. Shuffling flight or gate sequences produces an identical SHA-256 digest.
- **Timing Sensitivity**: Verified in `test_r02_t03`. A 1-minute delta in scheduled/predicted arrival alters the digest.
- **Capacity Sensitivity**: Verified in `test_r02_t04`. Modifying remote gate capacity alters the digest.

---

## 3. Tier 2: Mathematical Problem Identity (`ProblemIdentity`)

### 3.1 View Model Contract
```python
@dataclass(frozen=True)
class ProblemIdentity:
    scenario_digest: str
    objective_version: str = "P10_STANDARD"
    w_pref: float = 10.0
    w_remote: float = 200.0
    w_conflict: float = 1000.0
    buffer_time_min: int = 15
    allow_overflow: bool = True
    finite_remote_capacity: bool = True
    prediction_source: str = "SCHEDULE_BASELINE"
    schema_version: str = "2.0"
```

### 3.2 Formulation Digest Formula
```python
@property
def problem_digest(self) -> str:
    payload = {
        "scenario_digest": self.scenario_digest,
        "objective_version": self.objective_version,
        "w_pref": float(self.w_pref),
        "w_remote": float(self.w_remote),
        "w_conflict": float(self.w_conflict),
        "buffer_time_min": int(self.buffer_time_min),
        "allow_overflow": bool(self.allow_overflow),
        "finite_remote_capacity": bool(self.finite_remote_capacity),
        "prediction_source": self.prediction_source,
        "schema_version": self.schema_version,
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
```

### 3.3 Verification Properties
- Tested under `test_r02_t06`, `test_r02_t07`, and `test_r02_t08`.
- Any modification to penalty weights ($w_{\text{pref}}$, $w_{\text{remote}}$, $w_{\text{conflict}}$) or physical separation buffer ($B$) immediately invalidates the problem digest, preventing stale comparisons.

---

## 4. Tier 3: Solver Execution Identity (`ExecutionIdentity`)

### 4.1 View Model Contract
```python
@dataclass(frozen=True)
class ExecutionIdentity:
    problem_digest: str
    requested_solver: str
    effective_solver: str
    formulation: str = "sparse_interval"
    time_limit_sec: float = 30.0
    warm_start: bool = False
    solver_seed: Optional[int] = 42
    fallback_policy: str = "greedy_fallback"
    run_id: str = ""
    schema_version: str = "2.0"
```

### 4.2 Execution Digest Formula
```python
@property
def execution_digest(self) -> str:
    payload = {
        "problem_digest": self.problem_digest,
        "requested_solver": str(self.requested_solver).lower(),
        "effective_solver": str(self.effective_solver),
        "formulation": self.formulation,
        "time_limit_sec": float(self.time_limit_sec),
        "warm_start": bool(self.warm_start),
        "solver_seed": self.solver_seed,
        "fallback_policy": self.fallback_policy,
        "schema_version": self.schema_version,
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
```

### 4.3 Verification Properties
- Tested under `test_r02_t09` and `test_r02_t10`.
- Differentiates execution runs even when the mathematical problem formulation is identical (e.g. running CP-SAT with 30s limit vs 60s limit, or Deterministic Greedy vs CP-SAT).
