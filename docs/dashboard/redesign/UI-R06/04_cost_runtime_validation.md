# AEOLUS DASHBOARD — COST & RUNTIME MATHEMATICAL VALIDATION
**Phase**: UI-R06 v2.0  
**Mathematical Implementation**: `dashboard/core/validation.py` & `dashboard/visualizers/optimization_charts.py`  

---

## 1. Dual Cost Semantics (Decision vs Reporting)

Aeolus gate scheduling differentiates between two levels of cost evaluation:
1. **Decision Cost ($J_{\text{decision}}$)**:
   - Penalty function actively minimized by the solver during search.
   - Combines gate preference penalties, remote apron tow penalties, transit distances, and unassigned overflow costs.
2. **Reporting / Ground-Truth Cost ($J_{\text{reporting}}$)**:
   - Evaluated post-hoc on the generated assignment schedule.
   - Includes real operational delay risk, turn duration buffer violations, and downstream impact.

**Invariant**: Neither cost can be 0.0 unless mathematically proven. For UNKNOWN or INFEASIBLE runs, both costs evaluate to `None` (rendered as `N/A`), eliminating fabricated fallback scores.

---

## 2. Biobjective Pareto Frontier Mathematics

A point $(T_1, C_1)$ dominates $(T_2, C_2)$ if and only if:
$$T_1 \le T_2 \quad \text{and} \quad C_1 \le C_2 \quad \text{and} \quad (T_1 < T_2 \lor C_1 < C_2)$$
where $T$ represents total wall-clock runtime (ms) and $C$ represents decision cost.

### Algorithmic Definition (`ScientificValidator.compute_pareto_frontier`)
```python
def compute_pareto_frontier(
    points: Sequence[Mapping[str, Any]],
    cost_key: str = "objective_value",
    time_key: str = "total_wall_clock_ms",
) -> list[Mapping[str, Any]]:
    # 1. Filter only points with finite positive time and finite cost
    valid = [p for p in points if is_valid_point(p)]
    # 2. Sort primary by runtime ascending, secondary by cost ascending
    sorted_pts = sorted(valid, key=lambda x: (x[time_key], x[cost_key]))
    # 3. Compute non-dominated set (monotonically decreasing cost)
    pareto = []
    min_cost = float("inf")
    for pt in sorted_pts:
        c = pt[cost_key]
        if c < min_cost:
            pareto.append(pt)
            min_cost = c
    return pareto
```

### Pareto Invariants
- Heuristics with ultra-fast runtimes (e.g., Greedy: 5 ms, cost 180 pts) establish the high-speed end of the frontier.
- Exact solvers with longer runtimes (e.g., CP-SAT: 1,200 ms, cost 45 pts) establish the high-quality end of the frontier.
- Solvers with higher runtime and higher cost than any frontier point (dominated) are plotted as scatter markers but **excluded from the frontier curve**.
- Runs with status `UNKNOWN` or `INFEASIBLE` have undefined cost and are **strictly excluded** from Pareto computation.

---

## 3. Runtime Decomposition Invariant

For every benchmark execution record, the timing satisfies:
$$T_{\text{total}} \ge T_{\text{search}} \ge 0$$
$$T_{\text{total}} \approx T_{\text{build}} + T_{\text{search}} + T_{\text{validation}}$$

The runtime breakdown chart in Optimization Lab renders a stacked bar displaying:
- **Model Build Time (ms)**: Problem formulation, decision variables, interval constraints.
- **Search Time (ms)**: Solver branch-and-bound / local search execution.
- **Validation Time (ms)**: Independent verification of all hard constraints.

All values are expressed in milliseconds with finite positive numeric bounds.
