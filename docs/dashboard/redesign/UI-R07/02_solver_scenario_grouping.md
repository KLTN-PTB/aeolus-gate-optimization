# AEOLUS DASHBOARD — SOLVER & SCENARIO GROUPING POLICY
**Phase**: UI-R07 v2.0  
**Implementation**: `dashboard/core/validation.py` & `dashboard/visualizers/robustness_charts.py`  

---

## 1. Problem Statement: Multi-Solver Contamination

In the legacy dashboard prototype (audited in UI-R00), several charts plotted distributions directly from `fixed_plan_results.csv` and `recourse_results.csv` without filtering by `solver_name`.
This resulted in:
1. **Sample Size Distortion**: Charts rendered histograms of 1,500 data points while the page title proclaimed "500 Stochastic Scenarios".
2. **Artificial Multimodality**: Mixing results from Greedy, CP-SAT, and Hybrid into a single density plot created artificial variance and distorted percentiles.
3. **Statistical Inconsistency**: Boxplots and convergence traces exhibited erratic steps due to alternating solver records.

---

## 2. Inviolable Single-Solver Homogeneity Rule

Phase UI-R07 mandates that **every empirical statistical visualizer receives data from exactly one solver at a time**:

$$\forall \text{ Chart } C \in \{\text{Histogram}, \text{ECDF}, \text{Boxplot}, \text{Convergence}\}, \quad |\text{unique}(\text{solver\_name})| \equiv 1$$

### Enforcement Mechanism (`ScientificValidator.validate_single_solver_dataframe`)
```python
def validate_single_solver_dataframe(
    df: pd.DataFrame,
    target_solver: Optional[str] = "CPSat",
    allow_filter: bool = True,
) -> pd.DataFrame:
    if "solver_name" not in df.columns:
        return df
    unique_solvers = df["solver_name"].dropna().unique()
    if len(unique_solvers) <= 1:
        return df
    if not allow_filter:
        raise IncompatibleComparisonError(
            f"Multi-solver contamination detected: {list(unique_solvers)}"
        )
    return df[df["solver_name"] == target_solver].copy()
```

---

## 3. UI Selector Architecture

On Page 05 (Robustness Lab), the **Robustness Baseline Solver Selector** sits prominently at the top:
- **Options**: `CPSat` (Default), `Greedy`, `Hybrid`.
- **Reactive Propagation**:
  - Changing the selector immediately filters `fixed_df` (1,500 $\rightarrow$ 500) and `recourse_df` (1,500 $\rightarrow$ 500).
  - All downstream components (Scorecards, Histogram, ECDF, Boxplot, Convergence, Paired Testing, Drill-down) reflect **exclusively the 500 realizations for that chosen solver**.
  - No background simulation is re-run; filtering is purely in-memory ($< 5\text{ ms}$).
