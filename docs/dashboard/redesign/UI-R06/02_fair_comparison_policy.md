# AEOLUS DASHBOARD — FAIR SCIENTIFIC BENCHMARKING POLICY
**Phase**: UI-R06 v2.0  
**Enforcement Module**: `dashboard/core/validation.py` (`ScientificValidator`)  

---

## 1. Rationale & Problem Statement

In academic and operations research publications, benchmarking disparate algorithms requires strict control of environmental and structural conditions. Prior dashboard prototypes exhibited scientific validity risks:
1. **Cross-Scenario Averaging**: Averaging objective values across `10F_3G` and `300F_50G`, producing meaningless aggregate scores.
2. **False Global Ranking**: Declaring a solver as "best overall" by mixing runtimes on 10 flights with runtimes on 300 flights.
3. **Incompatible Objective Comparison**: Comparing runs solved under different penalty weightings or resource capacities.

Phase UI-R06 establishes an inviolable **Fair Comparison Policy** enforced by code.

---

## 2. The 6 Inviolable Rules of Comparison

To compare or rank any two benchmark records $R_A$ and $R_B$, all six conditions must evaluate to `True`:

```
                       [ Record A ]            [ Record B ]
                            |                       |
                            +-----------+-----------+
                                        |
                 1. Scenario ID:   R_A.scen == R_B.scen ?
                                        | Yes
                 2. Turn Count:    R_A.N == R_B.N ?
                                        | Yes
                 3. Gate Count:    R_A.M == R_B.M ?
                                        | Yes
                 4. Capacity:      R_A.policy == R_B.policy ?
                                        | Yes
                 5. Objective:     R_A.obj_def == R_B.obj_def ?
                                        | Yes
                 6. Prediction:    R_A.pred_src == R_B.pred_src ?
                                        | Yes
                              [ FAIR COMPARISON PERMITTED ]
```

If any condition fails, `ScientificValidator.validate_benchmark_record_compatibility(rec_a, rec_b)` raises `IncompatibleComparisonError`, halting invalid comparisons.

---

## 3. Exclusion of Infeasible & Unknown Runs from Scorecards

1. **Infeasible Runs**:
   - Any run where `feasible == False` or `solver_status == INFEASIBLE` violates hard operational constraints (overlap, gate suitability, buffer).
   - **Policy**: Infeasible runs cannot be assigned an objective score and are strictly excluded from comparative cost ranking.
2. **Unknown Runs (Time Limit Exceeded Without Incumbent)**:
   - When a solver times out before discovering a feasible incumbent solution, the mathematical objective value is undefined.
   - **Policy**: The objective cost is rendered as `None` / `N/A`. Under no circumstances is it imputed as `0.0`, $\infty$, or any fabricated default.
   - Such runs are excluded from Pareto non-dominated sets and are displayed with informative `UNKNOWN (TIME LIMIT)` status badges.

---

## 4. Distinction Between Heuristic Quality and Proven Optimality

- **CP-SAT**: When `termination_reason == OPTIMAL_PROVEN` and `optimality_gap == 0.0%`, CP-SAT is certified with `is_optimal = True` ("TỐI ƯU TUYỆT ĐỐI").
- **Greedy / Simulated Annealing**: Standalone heuristic solvers cannot mathematically prove global optimality, even if their solution cost numerically matches the lower bound.
- **Policy**: `optimality_proven` is strictly `False` for standalone heuristics. The UI explicitly displays "KHẢ THI (FEASIBLE)" or "HEURISTIC INCUMBENT", prohibiting misleading claims of optimality.
