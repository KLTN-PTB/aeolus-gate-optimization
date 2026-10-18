# AEOLUS-G12B-R1: Finite Remote Capacity Semantics & Resource Model Audit

## 1. Airfield Topological Resource Architecture

In modern airport operations research, apron and gate resources possess fundamentally distinct physical, operational, and topological characteristics. The Aeolus system formalizes these via `GateResourceType`:

1. **`CONTACT_GATE`**:
   - Physical terminal boarding bridge.
   - Strictly mutually exclusive single-aircraft capacity: $C_g = 1$.
   - Bound by carrier compatibility, aircraft type compatibility, and maintenance availability windows.

2. **`FINITE_REMOTE_STAND`**:
   - Remote parking positions requiring bus passenger transport.
   - Possesses a strictly finite physical capacity $C_{\text{remote}} \in \mathbb{N}_{>0}$ (e.g., 5 aircraft).
   - Concurrent occupancy condition: $\sum_{f \in \mathcal{F}} \mathbb{I}(\text{gate}(f) = g, t \in [T_{\text{arr}}(f), T_{\text{dep}}(f)]) \le C_{\text{remote}}$.
   - Bound by carrier compatibility, aircraft type compatibility, and operational windows.

3. **`UNBOUNDED_OVERFLOW_APRON`**:
   - Pure mathematical/operational holding apron of unlimited capacity ($C = \infty$).
   - Used in offline optimization to guarantee initial feasibility or model emergency diversion holding areas.
   - Distinct from finite remote stands. Must be explicitly instantiated as a designated fallback apron.

---

## 2. G12B Vulnerability & Fallback Flaw

### The Defect Identified in G12B
In `GateOptimizationConfig`, the default parameters are:
```python
allow_unbounded_overflow: bool = True
enforce_remote_capacity: bool = False
```
Under Mode B2 in G12B, `make_causal_recourse_decision()` contained the following logic:
```python
# DEFECTIVE FALLBACK IN G12B:
if snapshot.current_remote_usage < snapshot.finite_remote_capacity:
    chosen_gate_id = remote_gate.gate_id
elif getattr(config, "allow_unbounded_overflow", True) and not getattr(config, "enforce_remote_capacity", False):
    chosen_gate_id = remote_gate.gate_id  # VIOLATION: treated FINITE stand as UNBOUNDED apron!
```
When all contact gates were blocked and the remote stand had reached its maximum capacity ($k \ge C_{\text{remote}}$), the solver silently overloaded the finite remote stand! In ex-post verification, this caused physical constraint violations or fabricated feasibility where capacity was in reality completely exhausted.

---

## 3. G12B-R1 Strict Remediation

### 3.1 Strict Finite Capacity Enforcement
Under G12B-R1, a `FINITE_REMOTE_STAND` cannot be overloaded under any configuration flag:
1. `remote_gate` is assigned if and only if:
   $$\text{current\_remote\_usage} < C_{\text{remote}}$$
   and the aircraft is compatible with carrier, aircraft type, and operational availability.
2. If `current_remote_usage} \ge C_{\text{remote}}$, fallback to apron is permitted **only** if an explicit `overflow_gate` of type `UNBOUNDED_OVERFLOW_APRON` is supplied in the topology and `allow_unbounded_overflow` is enabled.
3. If no unbounded apron exists or the apron is incompatible, the recourse policy strictly returns:
   $$(None, \text{"NO\_CAPACITY\_EXHAUSTED"})$$
4. The unassigned flight is removed from active assignments, incrementing `unassigned_flight_count`, resulting in:
   - `composite_feasible = False`
   - `solver_status = OnlineSolverStatus.ONLINE_INFEASIBLE_NO_CAPACITY`

### 3.2 Repaired Causal Policy Implementation
```python
# 4. If no contact gate free, fallback to remote stand if capacity, compatibility, and availability permit
if chosen_gate_id is None:
    if remote_gate is not None:
        remote_compatible = (
            remote_gate.is_compatible_aircraft(f_curr.aircraft_type)
            and remote_gate.is_compatible_carrier(f_curr.carrier)
            and remote_gate.is_available_during(time_window)
        )
        if not remote_compatible:
            return None, "REMOTE_INCOMPATIBLE"

        if snapshot.current_remote_usage < snapshot.finite_remote_capacity:
            chosen_gate_id = remote_gate.gate_id
        elif overflow_gate is not None and getattr(config, "allow_unbounded_overflow", True):
            overflow_compatible = (
                overflow_gate.is_compatible_aircraft(f_curr.aircraft_type)
                and overflow_gate.is_compatible_carrier(f_curr.carrier)
                and overflow_gate.is_available_during(time_window)
            )
            if overflow_compatible:
                return overflow_gate.gate_id, "OVERFLOW_APRON_RECOURSE"
            else:
                return None, "NO_CAPACITY_EXHAUSTED"
        else:
            return None, "NO_CAPACITY_EXHAUSTED"
    elif overflow_gate is not None and getattr(config, "allow_unbounded_overflow", True):
        ...
```

---

## 4. Empirical Test Verification

The test suite `tests/test_g12b_r1_contract_integrity.py` validates all 9 capacity invariants:

| Test ID | Property Tested | Scenario Configuration | Expected Behavior | Result |
| :--- | :--- | :--- | :--- | :--- |
| **CAP-01** | Default config rejection | Remote usage = 2, Cap = 2, default config | Returns `(None, "NO_CAPACITY_EXHAUSTED")` | **PASS** |
| **CAP-02** | Enforce flag rejection | Remote usage = 2, Cap = 2, `enforce=True` | Returns `(None, "NO_CAPACITY_EXHAUSTED")` | **PASS** |
| **CAP-03** | Total resource exhaustion | All contact & remote exhausted | Returns unassigned, no silent assignment | **PASS** |
| **CAP-04** | Simultaneous arrivals | Cap = 1, two consecutive arrivals | 1st assigned remote, 2nd rejected | **PASS** |
| **CAP-05** | Explicit unbounded apron | Remote full + explicit APRON present | Assigns `"APRON"`, reason `"OVERFLOW_APRON_RECOURSE"` | **PASS** |
| **CAP-06** | Remote compatibility | Remote restricted by carrier/closure | Returns `(None, "REMOTE_INCOMPATIBLE")` | **PASS** |
| **CAP-07** | End-to-end Mode B2 | 3 flights, 1 contact, 1 remote stand | `composite_feasible=False`, status `ONLINE_INFEASIBLE_NO_CAPACITY` | **PASS** |
| **CAP-08** | Decomposed accounting | Breakdown distinguishes apron & stand | Counts and labels separated in dict | **PASS** |
| **CAP-09** | Independent verification | Ex-post verification of finite stand | Verifier catches over-capacity independently | **PASS** |
