# AEOLUS-G12B-R1: Status Equality & Hash Remediation Audit

## 1. Executive Summary & Problem Formulation

In Python data structures (specifically `set` and `dict`), the fundamental language contract stipulates:
$$\forall a, b: a == b \implies \text{hash}(a) == \text{hash}(b)$$
When an object overrides `__eq__` without maintaining an invariant with `__hash__`, hash-based collections exhibit non-deterministic, corrupted, or silent failure modes.

In the prior G12B implementation, `OnlineSolverStatus(str)` introduced a custom equality operator:
```python
# DEFECTIVE CODE (G12B):
class OnlineSolverStatus(str):
    def __eq__(self, other: object) -> bool:
        if self == "ONLINE_FEASIBLE" and other == "ONLINE_SOLVED":
            return True
        ...
```
This resulted in:
1. `OnlineSolverStatus("ONLINE_FEASIBLE") == "ONLINE_SOLVED"` evaluated to `True`.
2. However, `hash(OnlineSolverStatus("ONLINE_FEASIBLE")) != hash("ONLINE_SOLVED")`.
3. Consequently:
   - A dictionary key lookup `d["ONLINE_SOLVED"]` failed when `d[OnlineSolverStatus.ONLINE_FEASIBLE]` was set.
   - Sets containing both objects retained two distinct elements despite `a == b` being true.
   - Transitivity was broken: `A == B` and `B == C` did not hold consistently across string representations.
   - Scientific integrity hazard: Legacy runs marked `ONLINE_SOLVED` were implicitly treated as feasible without explicit verification of constraint satisfaction breakdown.

---

## 2. Mathematical Contract & Canonicalization Design

### 2.1 Canonical Enum Specification
`OnlineSolverStatus` is re-engineered as a strict, standard `str, Enum`:
```python
class OnlineSolverStatus(str, Enum):
    """Canonical solver statuses for causal online simulation.

    Semantics:
    - ONLINE_FEASIBLE: Solution achieved composite feasibility without conflicts or capacity overruns.
    - ONLINE_INFEASIBLE_NO_CAPACITY: System capacity exhausted (finite remote stand full or no compatible gate open).
    - ONLINE_INFEASIBLE: Physical operational constraint violated ex-post.
    """

    ONLINE_FEASIBLE = "ONLINE_FEASIBLE"
    ONLINE_INFEASIBLE_NO_CAPACITY = "ONLINE_INFEASIBLE_NO_CAPACITY"
    ONLINE_INFEASIBLE = "ONLINE_INFEASIBLE"

    def __str__(self) -> str:
        return self.value
```

### 2.2 Mathematical Invariants Restored
1. **Reflexivity**: $\forall x: x == x$
2. **Symmetry**: $\forall x, y: x == y \iff y == x$
3. **Transitivity**: $\forall x, y, z: (x == y \land y == z) \implies x == z$
4. **Hash Parity**: $\forall x, y: x == y \implies \text{hash}(x) == \text{hash}(y)$
5. **No Conflation**: `ONLINE_FEASIBLE != "ONLINE_SOLVED"` and `ONLINE_FEASIBLE != ONLINE_INFEASIBLE_NO_CAPACITY`.

### 2.3 Explicit Migration Boundary Function
To bridge historical records and legacy logs without compromising current verification, the explicit boundary function `canonicalize_legacy_solver_status` was implemented:
```python
def canonicalize_legacy_solver_status(
    raw_status: str,
    feasibility: FeasibilityBreakdown | Mapping[str, Any] | None = None,
) -> str:
    s = str(raw_status).strip().upper()
    if s in (
        OnlineSolverStatus.ONLINE_FEASIBLE.value,
        OnlineSolverStatus.ONLINE_INFEASIBLE_NO_CAPACITY.value,
        OnlineSolverStatus.ONLINE_INFEASIBLE.value,
    ):
        return s

    if s == "ONLINE_SOLVED":
        if feasibility is not None:
            if isinstance(feasibility, FeasibilityBreakdown):
                is_feas = feasibility.composite_feasible
                no_cap = (
                    feasibility.unassigned_flight_count > 0
                    or feasibility.remote_capacity_violation
                )
            elif isinstance(feasibility, Mapping):
                is_feas = bool(feasibility.get("composite_feasible", False))
                no_cap = bool(
                    feasibility.get("unassigned_flight_count", 0) > 0
                    or feasibility.get("remote_capacity_violation", False)
                )
            else:
                is_feas = False
                no_cap = False

            if is_feas:
                return OnlineSolverStatus.ONLINE_FEASIBLE.value
            elif no_cap:
                return OnlineSolverStatus.ONLINE_INFEASIBLE_NO_CAPACITY.value
            else:
                return OnlineSolverStatus.ONLINE_INFEASIBLE.value
        return "LEGACY_ONLINE_SOLVED_UNVERIFIED"

    return s
```
**Safety Guarantee**: `ONLINE_SOLVED` is **never** presumed feasible unless backed by a mathematically verified `FeasibilityBreakdown.composite_feasible == True`. If unverified, it explicitly yields `"LEGACY_ONLINE_SOLVED_UNVERIFIED"`.

---

## 3. Empirical Test Verification

The test suite `tests/test_g12b_r1_contract_integrity.py` verifies all 7 status invariants:

| Test ID | Invariant Tested | Input Condition | Expected Result | Actual Result |
| :--- | :--- | :--- | :--- | :--- |
| **STATUS-01** | Equivalence properties | `s1 == s2`, symmetry, transitivity | Reflexive, Symmetric, Transitive | **PASS** |
| **STATUS-02** | Hash parity contract | `hash(s_feas) == hash(str(s_feas))` | Exact hash match | **PASS** |
| **STATUS-03** | Collection consistency | Sets & Dicts key deduplication | `len({s, str(s)}) == 1` | **PASS** |
| **STATUS-04** | Explicit migration boundary | `canonicalize_legacy_solver_status` | Correct decomposition & unverified quarantine | **PASS** |
| **STATUS-05** | No status conflation | Feasible vs Infeasible vs No Capacity | Mutual inequality strictly preserved | **PASS** |
| **STATUS-06** | Canonical string generation | `str(s)` and `s.value` | Serializes to canonical strings | **PASS** |
| **STATUS-07** | No silent equality hack | `OnlineSolverStatus.ONLINE_FEASIBLE != "ONLINE_SOLVED"` | Evaluates to `False` | **PASS** |

All tests execute with 100% pass rate in CI/verification pipeline.
