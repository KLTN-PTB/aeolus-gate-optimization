# AEOLUS DASHBOARD — UI-R02 REPORT
# 04. SOLVER EXECUTION SAFETY, REJECTION & PROVENANCE REPAIR

## 1. Executive Summary

During baseline audit, multiple solver-level provenance vulnerabilities were identified:
1. **Silent Fallback to CP-SAT**: Passing any unrecognized string or invalid solver name silently executed CP-SAT due to a permissive `else: solver = CPSatGateSolver` branch.
2. **Ambiguous Solver Identity on CP-SAT Timeout**: When CP-SAT timed out without finding an incumbent, it internally fell back to Greedy (`cp_sat_fallback_to_greedy=True`), but the presentation layer could still report "CP-SAT".
3. **Misattributed Provenance**: Solver executions were defaulted to `NATIVE_INFERENCE` even when operating over synthetic scalability scenarios or precomputed baselines.
4. **Stripped Constraint Diagnostics**: Independent verifier diagnostics were reduced to a flat integer count, losing the diagnostic breakdown.

UI-R02 repairs these vulnerabilities across `OptimizationService`, `adapt_solver_result_to_view`, and `SolverRunView`.

---

## 2. Strict Solver Name Validation & Rejection

Implemented in `dashboard/services/optimization_service.py`:
```python
name_lower = solver_name.lower().strip()
if "greedy" in name_lower:
    solver = DeterministicGreedyGateSolver(opt_config)
    requested_solver_canonical = "greedy"
    actual_solver_name = "Deterministic Greedy"
elif "hybrid" in name_lower:
    solver = HybridGateSolver(opt_config)
    requested_solver_canonical = "hybrid"
    actual_solver_name = "Hybrid (Greedy+CP-SAT)"
elif "cpsat" in name_lower or "cp-sat" in name_lower or "cp_sat" in name_lower:
    solver = CPSatGateSolver(opt_config)
    requested_solver_canonical = "cpsat"
    actual_solver_name = "CP-SAT (Sparse Interval)"
else:
    raise ValueError(
        f"Unsupported or unknown solver: '{solver_name}'. "
        "Supported solvers: ['cpsat', 'greedy', 'hybrid']. "
        "Silent fallback to CP-SAT is rejected under UI-R02 safety rules."
    )
```

### 2.1 Verification Evidence
Verified in `test_r02_t21`:
- Invoking `OptimizationService.solve(..., solver_name="genetic_algorithm_v1")` raises `ValueError`.
- Invoking `OptimizationService.solve(..., solver_name="random_search")` raises `ValueError`.

---

## 3. Fallback Tracking & Requested vs Effective Solver

In `dashboard/core/contracts.py`, `SolverRunView` was augmented with dedicated provenance fields:
```python
@dataclass(frozen=True)
class SolverRunView:
    ...
    requested_solver: Optional[str] = None
    effective_solver: Optional[str] = None
    fallback_used: bool = False
    problem_digest: Optional[str] = None
    execution_digest: Optional[str] = None
    run_id: Optional[str] = None
    verifier_diagnostics: Optional[Dict[str, Any]] = None
```

### 3.1 Fallback Certification Rules
In `dashboard/adapters/solver_result_adapter.py`:
```python
raw_cfg = getattr(result, "solver_configuration", {})
if fallback_used is None:
    fallback_used = bool(raw_cfg.get("fallback_used", False) if isinstance(raw_cfg, dict) else False)

# Enforce scientific rule: Only OPTIMAL_PROVEN gets is_optimal_proven = True.
# Heuristics (Greedy, Simulated Annealing) or fallback executions can NEVER be certified as optimal proven.
s_upper = solver_name.upper()
if "GREEDY" in s_upper or "SIMULATED" in s_upper or s_upper.startswith("SA") or fallback_used:
    is_opt_proven = False

eff_solver = effective_solver
if eff_solver is None:
    eff_solver = "Deterministic Greedy" if fallback_used else solver_name
```

Verified in `test_r02_t25`: When `fallback_used == True`, `effective_solver` is guaranteed to be `"Deterministic Greedy"`, and `is_optimal_proven` is strictly `False`.

---

## 4. Preservation of Independent Verifier Diagnostics

The independent hard-constraint verifier (`verify_hard_constraints_independently`) produces a `ConstraintDiagnostic` object with comprehensive violation details (contact collisions, remote capacity limits, turnaround violations, availability mismatches).

In UI-R02:
1. `OptimizationService.solve` captures `diag.to_dict()` and embeds it into `view.verifier_diagnostics`.
2. All violation categories (including unknown gate allocations and unassigned flights) are tracked without loss of precision.
3. Verified in `test_r02_t24`.
