# Integration Examples & Developer Recipes

**Document ID:** `AEOLUS-P10-B-INTEGRATION-RECIPES`  
**Phase:** P10-B (Dashboard Foundation, Data Contracts & Safe Integration)  
**Status:** IMPLEMENTED & TESTED  
**Audience:** Frontend Application Engineers implementing UI Pages (P10-C, P10-D)  

---

## 1. Executive Summary

This document provides concrete, copy-pasteable Python code recipes demonstrating how subsequent UI page modules consume the data contracts, adapters, and execution services implemented in Phase P10-B.

---

## 2. Recipe 1: Control Tower (Page 1) — Scenario Context & KPIs

```python
from dashboard.services.scenario_service import ScenarioService
from dashboard.adapters.artifact_loader import ArtifactLoader

# 1. Fetch active scenario metadata
scen_service = ScenarioService()
context = scen_service.get_scenario_context("SCEN_P09_CANONICAL_120")
print(f"Hub: {context.hub_iata} | Chuyến bay: {context.flight_count} | Cổng: {context.gate_count}")

# 2. Load precomputed benchmark KPIs
loader = ArtifactLoader()
benchmarks_df = loader.load_solver_benchmarks()
cpsat_row = benchmarks_df[benchmarks_df["solver_variant"].str.contains("sparse")].iloc[0]

print(f"Chi phí CP-SAT: {cpsat_row['objective_value']} | Đổi cổng: {cpsat_row['reassignment_count']}")
```

---

## 3. Recipe 2: Flight Intelligence (Page 2) — Predictions & SHAP

```python
from dashboard.adapters.artifact_loader import ArtifactLoader
from dashboard.adapters.prediction_adapter import adapt_prediction_row_to_view

loader = ArtifactLoader()

# 1. Load flight prediction rows and adapt to typed View Models
raw_df = loader.load_csv(
    "artifacts/remediation/native_dual_core/predictions_sample.csv",
    required_columns={"flight_id", "predicted_arr_delay_min"}
)

views = [adapt_prediction_row_to_view(row) for _, row in raw_df.iterrows()]
print(f"Loaded {len(views)} flight prediction views without data leakage.")

# 2. Load local SHAP case studies for selected flight
case_studies = loader.load_shap_case_studies()
target_flight = case_studies[0]
print(f"Flight: {target_flight['flight_id']} | Base: {target_flight['base_value']} | Features: {len(target_flight['features'])}")
```

---

## 4. Recipe 3: Gate Operations (Page 3) — Live CP-SAT Solving & Gantt

```python
from dashboard.services.scenario_service import ScenarioService
from dashboard.services.optimization_service import OptimizationService

# 1. Load flights and gates from ScenarioService
scen_service = ScenarioService()
flights, gates = scen_service.load_scenario("SCEN_P09_CANONICAL_120")

# 2. Trigger live solve with custom parameters
opt_service = OptimizationService()
solution_view, is_valid, violations = opt_service.solve(
    flights=flights,
    gates=gates,
    solver_name="cpsat",
    scenario_id="SCEN_P09_CANONICAL_120",
    params={"w_pref": 15.0, "w_remote": 250.0, "buffer_time_min": 15}
)

# 3. Verify independent constraint check
if is_valid:
    print(f"✅ Nghiệm hợp lệ! Trạng thái: {solution_view.status} | Thời gian giải: {solution_view.solve_time_sec * 1000:.1f} ms")
    print(f"Số lượng vạch Gantt: {len(solution_view.assignments)}")
else:
    print(f"⚠️ Phát hiện {len(violations)} vi phạm ràng buộc!")
```

---

## 5. Recipe 4: Optimization Lab (Page 4) — Fair Multi-Solver Ranking

```python
from dashboard.services.experiment_service import ExperimentService
from dashboard.adapters.solver_result_adapter import adapt_solver_result_to_view
from dashboard.core.contracts import SolverRunView

# Prepare two solver views from the same scenario
run_greedy = SolverRunView(
    solver_name="Deterministic Greedy",
    scenario_id="SCEN_P09_CANONICAL_120",
    objective_value=0.0,
    decision_cost=0.0,
    reporting_cost=0.0,
    reassignment_count=0,
    remote_gate_count=0,
    conflict_count=0,
    solve_time_sec=0.003,
    status="FEASIBLE",
    termination_reason="HEURISTIC_STOP",
    is_optimal_proven=False,
    solver_config={"w_pref": 10.0, "w_remote": 200.0}
)

run_cpsat = SolverRunView(
    solver_name="CP-SAT (Sparse Interval)",
    scenario_id="SCEN_P09_CANONICAL_120",
    objective_value=0.0,
    decision_cost=0.0,
    reporting_cost=0.0,
    reassignment_count=0,
    remote_gate_count=0,
    conflict_count=0,
    solve_time_sec=0.065,
    status="OPTIMAL",
    termination_reason="OPTIMAL_PROVEN",
    is_optimal_proven=True,
    solver_config={"w_pref": 10.0, "w_remote": 200.0}
)

# Rank with fair comparison check (raises IncompatibleComparisonError if mismatched)
ranked_runs = ExperimentService.rank_solver_runs([run_cpsat, run_greedy])
print(f"Top Solver: {ranked_runs[0].solver_name} (Cost: {ranked_runs[0].decision_cost})")
```

---

## 6. Recipe 5: Robustness Lab (Page 5) — Monte Carlo 500 Stress Matrix

```python
from dashboard.adapters.artifact_loader import ArtifactLoader
from dashboard.adapters.monte_carlo_adapter import adapt_monte_carlo_to_views

loader = ArtifactLoader()
raw_summary = loader.load_monte_carlo_statistical_summary()

views = adapt_monte_carlo_to_views(raw_summary, solver_key="CPSat")

mode_a = views["mode_a"]
mode_b = views["mode_b"]
mode_c = views["mode_c"]

print(f"Mode A: Va chạm thực tế = {mode_a.physical_conflict_rate * 100:.1f}% | Vi phạm lịch tĩnh = {mode_a.static_invalidation_rate * 100:.1f}%")
print(f"Mode B: Đổi cổng trung bình = {mode_b.mean_reassignments:.3f} | Chi phí TB = {mode_b.mean_cost:.2f}")
print(f"Mode C: Chi phí TB = {mode_c.mean_cost:.2f} | Trạng thái triển khai = {mode_c.is_deployable} (Oracle Baseline)")
```
