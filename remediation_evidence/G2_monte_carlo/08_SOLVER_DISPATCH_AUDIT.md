# AEOLUS-G2 — DELIVERABLE 08: SOLVER DISPATCH AUDIT

## 1. Forensic Root Cause Analysis of Legacy P09 Solver Behavior

A central paradox discovered during Gate G0 and G1 audits was why legacy P09 reported:
- Greedy, CP-SAT, and Hybrid achieving identical costs in Mode B across 500 scenarios.
- All paired comparison deltas in `paired_comparison.csv` evaluating to identically $0.0 \pm 0.0$ with $p = 1.0$.

Forensic inspection of `scripts/run_p09_monte_carlo_validation.py` and `src/simulation/monte_carlo_engine_p09.py` identified two distinct compounding causes:

### Cause 1: Benchmark Scenario Slack & Identical Initial Solutions
In `scripts/run_p09_monte_carlo_validation.py`, the benchmark scenario was configured as:
- $N_{flights} = 120$ flights
- $N_{contact} = 25$ contact gates
- $N_{remote} = 5$ finite remote stands
- Seed $= 202601$

When the initial planned assignments were solved at prediction cutoff $T-2$h:
```python
res_greedy = solver_greedy.solve(base_flights, all_gates)  # obj = 0.0, feas = True
res_cpsat  = solver_cpsat.solve(base_flights, all_gates)   # obj = 0.0, feas = True
res_hybrid = solver_hybrid.solve(base_flights, all_gates)  # obj = 0.0, feas = True
```
Because 120 flights spread across 25 contact gates over 24 hours provide ample temporal slack (average 4.8 flights per gate per day), all 120 flights could be placed on their nominal contact gates without a single conflict or remote overflow.
As a result:
$$\text{assignments}_{Greedy} \equiv \text{assignments}_{CPSat} \equiv \text{assignments}_{Hybrid}$$
The three initial plans were 100% bit-exact identical.

### Cause 2: Hardcoded Recourse Solver in Legacy Mode B
In `src/simulation/monte_carlo_engine_p09.py`, the recourse function was implemented as:
```python
def evaluate_mode_b_reactive_recourse(
    initial_assignments: Mapping[str, GateAssignment],
    realized_flights: Sequence[Flight],
    gates: Sequence[Gate],
    config: GateOptimizationConfig,
    realization: RealizedScenario,
    solver_name: str,
) -> tuple[RealizationResult, list[dict[str, Any]]]:
    ...
    solver = DeterministicGreedyGateSolver(config=config)
    res_recourse = solver.solve(flights=recourse_flights, gates=gates, allow_overflow=True)
```
Notice that regardless of the argument `solver_name` ("Greedy", "CPSat", or "Hybrid"), the solver instance instantiated was **always `DeterministicGreedyGateSolver`**.

### The Compounding Effect
1. Greedy, CP-SAT, and Hybrid produced identical initial plans.
2. In Mode B, the exact same `DeterministicGreedyGateSolver` was executed on those identical initial plans.
3. Therefore, for every scenario $s \in \{0, \dots, 499\}$:
   $$\text{Cost}_{Greedy, B}(s) \equiv \text{Cost}_{CPSat, B}(s) \equiv \text{Cost}_{Hybrid, B}(s)$$
4. The paired delta $\Delta_s = \text{Cost}_{CPSat, B}(s) - \text{Cost}_{Greedy, B}(s) \equiv 0.0$.
5. The sample variance $s^2_{\Delta} = 0.0$, yielding $\text{SE} = 0.0$, $t = 0.0$, and $p = 1.0$.

## 2. Remediated Architecture in G2

In Gate G2, the solver dispatching was repaired at multiple levels:

1. **Dynamic Recourse Solver Dispatching (Mode B1):**
   In `evaluate_mode_b1_retrospective_recourse()`, the recourse solver is instantiated dynamically based on `recourse_solver_name`:
   ```python
   if "cpsat" in solver_key or "cp_sat" in solver_key:
       solver_instance = CPSatGateSolver(config=config)
   elif "hybrid" in solver_key:
       solver_instance = HybridGateSolver(config=config)
   else:
       solver_instance = DeterministicGreedyGateSolver(config=config)
   ```
2. **Online Recourse Dispatching (Mode B2):**
   Uses `RollingOnlineGreedy` for real-time sequential conflict resolution.
3. **Foresight Oracle Dispatching (Mode C1 vs C2):**
   Separated into `evaluate_mode_c_greedy_foresight()` (Greedy heuristic) and `evaluate_mode_c_optimal_foresight()` (`CPSatGateSolver` with proof of optimality).
4. **Honest Scientific Reporting:**
   The G2 reports explicitly document that on `SCEN_P09_CANONICAL_120`, initial plan solver differences are zero due to schedule sparsity, correctly framing this as a property of the benchmark scenario rather than solver equivalence.
