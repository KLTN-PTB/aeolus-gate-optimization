# 04_HYBRID_IMPLEMENTATION_REPORT.md

## AEOLUS-G12B Hybrid Solver Implementation Report

**Author:** Principal Python Software Engineer, Operations Research Specialist  
**Date:** October 12, 2026  
**Repository:** `aeolus-gate-optimization`  
**Modified Source Files:**
1. `src/optimization/sa/annealer.py`
2. `src/optimization/solvers/hybrid_solver.py`

---

### 1. Modifications in `src/optimization/sa/annealer.py`

#### 1.1 Method Signature Update
Added `deadline_perf_counter: float | None = None` keyword argument to `SimulatedAnnealingGateSolver.solve()`:
```python
def solve(
    self,
    flights: Sequence[Flight],
    gates: Sequence[Gate],
    *,
    initial_assignments: Mapping[str, GateAssignment] | None = None,
    allow_overflow: bool = True,
    deadline_perf_counter: float | None = None,
) -> OptimizationResult:
```

#### 1.2 Automatic Deadline Calculation
If no explicit `deadline_perf_counter` is supplied by the caller, the solver automatically calculates one from the configuration:
```python
t0 = time.perf_counter()

if deadline_perf_counter is None:
    budget_s = getattr(self.config, "total_wall_clock_budget_seconds", None)
    if budget_s is None or budget_s <= 0:
        budget_s = getattr(self.config, "time_limit_seconds", None)
    if budget_s is not None and budget_s > 0:
        deadline_perf_counter = t0 + budget_s
```

#### 1.3 Wall-Clock Interruption in SA Iteration Loop
At the start of each cooling iteration $k$, the solver tests whether the wall-clock deadline has elapsed:
```python
term_reason = TerminationReason.ITERATION_LIMIT
for k in range(1, self.sa_config.iterations + 1):
    if deadline_perf_counter is not None and time.perf_counter() >= deadline_perf_counter:
        term_reason = TerminationReason.TIME_LIMIT
        break
```

#### 1.4 Dynamic Termination Reason Transmission
`term_reason` is passed to the authoritative evaluation function `evaluate_gate_assignment(..., termination_reason=term_reason)` and stored in `extra_metadata["termination_reason"]`.

---

### 2. Modifications in `src/optimization/solvers/hybrid_solver.py`

#### 2.1 Global Wall-Clock Deadline & Budget Allocation
```python
total_budget_s = getattr(self.config, "total_wall_clock_budget_seconds", None)
if total_budget_s is None or total_budget_s <= 0:
    total_budget_s = getattr(self.config, "time_limit_seconds", 30.0)
global_deadline = t0 + total_budget_s

cp_budget_seconds = max(0.01, min(total_budget_s * self.cp_ratio, total_budget_s))
cp_config = replace(self.config, time_limit_seconds=cp_budget_seconds)
```

#### 2.2 Independent Certification of Stage 1 Incumbent
Before invoking Stage 2, the incumbent solution (obtained from CP-SAT or deterministic greedy fallback) is independently verified and evaluated:
```python
incumbent_diag = verify_hard_constraints_independently(
    flights=flights,
    gates=gate_list,
    assignments=incumbent_assignments,
)
incumbent_eval = evaluate_gate_assignment(
    assignments=incumbent_assignments,
    flights=flights,
    gates=gate_list,
    config=self.config,
    runtime_ms=(time.perf_counter() - t0) * 1000.0,
    solver_status="FEASIBLE" if incumbent_diag.is_valid else "INFEASIBLE",
    solver_name="IncumbentStage1",
)
initial_cost = float(incumbent_eval.objective_value)
```

#### 2.3 Exception-Guarded SA Execution & Remaining Budget Check
```python
final_assignments = dict(incumbent_assignments)
final_diag = incumbent_diag
final_eval = incumbent_eval

now = time.perf_counter()
remaining_budget_s = global_deadline - now

if remaining_budget_s > 0.005:
    sa_solver = SimulatedAnnealingGateSolver(config=self.config, sa_config=self.sa_config)
    t_sa0 = time.perf_counter()
    try:
        sa_result = sa_solver.solve(
            flights=flights,
            gates=gate_list,
            initial_assignments=incumbent_assignments,
            allow_overflow=allow_overflow,
            deadline_perf_counter=global_deadline,
        )
        sa_wall_clock_ms = (time.perf_counter() - t_sa0) * 1000.0
        sa_executed = True
```

#### 2.4 Outer Incumbent Guard Logic
```python
        sa_candidate_diag = verify_hard_constraints_independently(
            flights=flights,
            gates=gate_list,
            assignments=sa_result.assignments,
        )
        sa_candidate_eval = evaluate_gate_assignment(
            assignments=sa_result.assignments,
            flights=flights,
            gates=gate_list,
            config=self.config,
            runtime_ms=(time.perf_counter() - t0) * 1000.0,
            solver_status="FEASIBLE" if sa_candidate_diag.is_valid else "INFEASIBLE",
            solver_name="HybridCPSatSA",
        )

        candidate_feasible = bool(
            sa_candidate_diag.is_valid and len(sa_result.assignments) == len(flights)
        )
        tol = 1e-6
        if not candidate_feasible:
            sa_accepted = False
            sa_rejection_reason = "SA_PRODUCED_INFEASIBLE_SOLUTION"
        elif sa_candidate_eval.objective_value > incumbent_eval.objective_value + tol:
            sa_accepted = False
            sa_rejection_reason = "SA_DEGRADED_INCUMBENT_OBJECTIVE"
        else:
            sa_accepted = True
            final_assignments = dict(sa_result.assignments)
            final_diag = sa_candidate_diag
            final_eval = sa_candidate_eval
            if sa_candidate_eval.objective_value < incumbent_eval.objective_value - tol:
                sa_improved = True
    except Exception as e:
        sa_wall_clock_ms = (time.perf_counter() - t_sa0) * 1000.0
        sa_executed = True
        sa_accepted = False
        sa_rejection_reason = f"SA_EXCEPTION_{type(e).__name__}"
else:
    sa_rejection_reason = "BUDGET_EXHAUSTED_BEFORE_STAGE2"
```

---

### 3. Verification Summary

1. **`tests/test_g12b_hybrid_incumbent.py`:** All 16 targeted tests PASSED.
2. **`tests/test_sa_hybrid_correctness_p03.py`:** All 27 tests PASSED.
3. **`tests/test_g5_solver_correctness.py`:** All 25 tests PASSED.
4. **`tests/test_simulated_annealing.py`:** All 25 tests PASSED.
Total solver tests passing: **93/93 tests (100%)**.
