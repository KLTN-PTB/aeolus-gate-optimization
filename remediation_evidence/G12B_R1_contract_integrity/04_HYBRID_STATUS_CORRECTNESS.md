# AEOLUS-G12B-R1: Hybrid Solver Status Integrity & Optimality Proof Audit

## 1. Operations Research & Mathematical Foundations

In constraint programming and mathematical optimization:
$$\text{Search Space } \mathcal{S} = \prod_{f \in \mathcal{F}} \mathcal{G}_f, \quad \text{Feasible Subspace } \mathcal{F}_{\text{feas}} = \{x \in \mathcal{S} \mid \text{HardConstraints}(x) = \text{True}\}$$

There are three mutually exclusive terminal states for exact solvers:
1. **Proven Feasible / Optimal**: An assignment $x^* \in \mathcal{F}_{\text{feas}}$ is found. If lower bound equals upper bound, $x^*$ is mathematically optimal.
2. **Proven Infeasible**: The solver constructs a mathematical certificate that $\mathcal{F}_{\text{feas}} = \emptyset$.
3. **Inconclusive (Time Limit / Unknown)**: The solver exhausted its allotted computational budget without finding an element in $\mathcal{F}_{\text{feas}}$, but cannot prove $\mathcal{F}_{\text{feas}} = \emptyset$.

**The Scientific Invariant**: A heuristic failure (such as a greedy heuristic being unable to construct a valid schedule) **never** constitutes a proof of infeasibility. Conflating "solver gave up / timed out" with "proven infeasible" is an academic integrity error.

---

## 2. G12B Flaw & G12B-R1 Remediation

### 2.1 The Prior Defect in Hybrid Fallback
In G12B, when CP-SAT timed out without finding an incumbent, `HybridGateSolver` attempted a deterministic greedy fallback. If greedy also failed, lines 246–260 returned:
```python
# DEFECTIVE CODE (G12B):
return OptimizationResult(
    status="INFEASIBLE",  # VIOLATION: Claimed mathematical infeasibility!
    termination_reason=TerminationReason.NO_FEASIBLE_SOLUTION,
    ...
)
```

### 2.2 Corrected Status Taxonomy in G12B-R1
Under G12B-R1, the return status is strictly partitioned:
```python
if not fallback_used:
    # Both CP-SAT and fallback failed
    total_wall_clock_ms = (time.perf_counter() - t0) * 1000.0
    if cp_solver_status in ("TIMEOUT_NO_SOLUTION", "TIME_LIMIT"):
        fallback_status = "TIMEOUT_NO_SOLUTION"
        term_reason = TerminationReason.TIME_LIMIT
    else:
        fallback_status = "UNKNOWN"
        term_reason = TerminationReason.NO_FEASIBLE_SOLUTION

    return OptimizationResult(
        status=fallback_status,
        objective_value=float("inf"),
        objective_breakdown=greedy_result.objective_breakdown,
        feasible=False,
        runtime_ms=total_wall_clock_ms,
        optimality_gap=None,
        assignments={},
        constraint_diagnostics=greedy_result.constraint_diagnostics,
        solver_configuration={
            **self.config.to_dict(),
            **hybrid_trace,
        },
        termination_reason=term_reason,
    )
```

### 2.3 Incumbent Preservation & Optimality Proof Guard
The outer incumbent guard guarantees:
1. If CP-SAT discovered a valid incumbent $x_{\text{CP}}$:
   $$c(x_{\text{final}}) \le c(x_{\text{CP}})$$
   If Simulated Annealing proposes an inferior solution, an invalid assignment, or encounters an internal runtime error, $x_{\text{CP}}$ is unconditionally restored.
2. `optimality_proven` is inherited if and only if CP-SAT proved optimality **and** the final solution preserved that cost. A heuristic solution alone never fabricates an optimality proof or gap.

---

## 3. Empirical Test Verification

The test suite `tests/test_g12b_r1_contract_integrity.py` validates all 6 hybrid status invariants:

| Test ID | Condition Tested | Expected Status | Expected Termination Reason | Result |
| :--- | :--- | :--- | :--- | :--- |
| **HYB-STATUS-01** | CP-SAT UNKNOWN + Greedy fail | `UNKNOWN` (NOT `INFEASIBLE`) | `NO_FEASIBLE_SOLUTION` | **PASS** |
| **HYB-STATUS-02** | CP-SAT TIMEOUT + Greedy fail | `TIMEOUT_NO_SOLUTION` | `TIME_LIMIT` | **PASS** |
| **HYB-STATUS-03** | CP-SAT mathematically INFEASIBLE | `INFEASIBLE` | `PROVEN_INFEASIBLE` | **PASS** |
| **HYB-STATUS-04** | SA degradation with CP incumbent | `FEASIBLE` / `OPTIMAL` | Incumbent preserved | **PASS** |
| **HYB-STATUS-05** | Exact CP-SAT proof inheritance | `OPTIMAL` | `OPTIMAL_PROVEN` | **PASS** |
| **HYB-STATUS-06** | Heuristic without proof | `FEASIBLE` (Proof = False) | Gap is `None`, no false proof | **PASS** |

Regression suite `tests/test_sa_hybrid_correctness_p03.py::test_s18` was also reconciled to assert `res.status in ("UNKNOWN", "TIMEOUT_NO_SOLUTION")` in full alignment with G12B-R1.
