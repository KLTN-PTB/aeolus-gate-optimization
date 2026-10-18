# AEOLUS-G6: Source-to-UI Traceability Matrix

**Gate Identifier:** `AEOLUS-G6`  
**Gate Title:** Dashboard Scientific Integrity, Runtime Validation & Visual QA  
**Audit Date:** 2026-10-11  
**Target Branch:** `remediation/g6-dashboard`  

---

## 1. Traceability Principles & Architecture

To guarantee absolute scientific integrity and reproducibility during the thesis defense, every UI metric, chart, and badge must map directly to an authoritative backend contract, scenario definition, or mathematical formula. No UI component is permitted to display unverified, hardcoded, or disconnected values.

---

## 2. Comprehensive 5-Page Traceability Matrix

| Page | UI Element / Component | Backend Data Contract | Data Origin Tag | Model / Solver Identity | Mathematical Formula / Derivation | Export Destination |
|:---|:---|:---|:---|:---|:---|:---|
| **01. Control Tower** | Scenario Context Banner | `ScenarioContext` | `REAL_DERIVED` / `SYNTHETIC` | Scenario Loader | `N_flights = len(scenario.flights)`, `M_gates = len(scenario.gates)` | Session State |
| **01. Control Tower** | KPI: Total Flights | `ScenarioContext.flight_count` | `REAL_DERIVED` / `SYNTHETIC` | Backend Registry | Count of flights in active scenario | UI Display |
| **01. Control Tower** | KPI: Active Gates | `ScenarioContext.gate_count` | `REAL_DERIVED` / `SYNTHETIC` | Backend Registry | Count of gates in active scenario | UI Display |
| **01. Control Tower** | Inbound Delay Wave | `Sequence[FlightPredictionView]` | `REAL_DERIVED` | NGBoost Student-t / Precomputed | Hourly binned histogram: $\sum \mathbf{1}_{t_{\text{arr}} \in [h, h+1)}$ | Plotly Figure |
| **01. Control Tower** | Concourse Load Bars | `Sequence[GateTimelineView]` | `REAL_DERIVED` / `SYNTHETIC` | Baseline Schedule | Peak concurrency per concourse: $\max_t \sum_{i \in C} \mathbf{1}_{t \in [s_i, r_i)}$ | Plotly Figure |
| **02. Flight Intel** | Inbound Delay CDF ($P_{15}$) | `FlightPredictionView.probability_delay_15` | `REAL_DERIVED` | P4 NGBoost Student-t Checkpoint | $P(\text{delay} \ge 15) = 1 - F_{t(\nu, \mu, \sigma)}(15)$ | UI Metric Card |
| **02. Flight Intel** | Outbound Risk Score | `FlightPredictionView.confidence_score` | `REAL_DERIVED` | P8 XGBoost Regressor | $\sigma(z) = \frac{1}{1 + e^{-z}}$ (Risk Score, labeled `"N/A"` for CDF) | UI Metric Card |
| **02. Flight Intel** | Aircraft Turn Dynamics | `AircraftTurnView` | `REAL_DERIVED` / `SYNTHETIC` | Turn Pairing Engine | $dwell = t_{\text{dep}} - t_{\text{arr}} \ge 45\text{m}$, $slack = dwell - 45\text{m}$ | Plotly Timeline |
| **02. Flight Intel** | Cross-Midnight Timeline | `AircraftTurnView` | `REAL_DERIVED` / `SYNTHETIC` | Turn Pairing Engine | Normalized minutes $t \in [0, 2880)$ with $(+1)$ day tag | Plotly Timeline |
| **02. Flight Intel** | Global TreeSHAP Bar | Precomputed SHAP Artifacts | `REAL_DERIVED` | TreeSHAP Explainer | Mean absolute SHAP value: $\frac{1}{N} \sum_{i=1}^N \|\phi_{i,j}\|$ | Plotly Bar Chart |
| **03. Gate Ops** | Master Gantt Timeline | `Sequence[GateTimelineView]` | `REAL_DERIVED` / `SYNTHETIC` | CP-SAT / Greedy / SA / Hybrid | Half-open intervals: $[start_i, release_i)$, $release_i = out_i + 15$ | Plotly Gantt / CSV Export |
| **03. Gate Ops** | Apron Stand Grouping | `GateTimelineView.concourse` | `SYNTHETIC` | Solver Resource Model | Filter: `concourse == 'OVERFLOW'` for `APRON_*` | Master Gantt Axis |
| **03. Gate Ops** | Remote Capacity Utilization | `GateTimelineView.is_remote` | `REAL_DERIVED` / `SYNTHETIC` | Solver Resource Model | Max concurrent remote flights: $\max_t \sum_{i \in R} \mathbf{1}_{t \in [s_i, r_i)} \le K$ | Verifier Card |
| **03. Gate Ops** | Independent Verifier Badge | `VerifierDiagnostics` | `REAL_DERIVED` / `SYNTHETIC` | `verify_hard_constraints_independently()` | Hard conflicts $= 0 \implies \text{VERIFIED}$; conflicts $> 0 \implies \text{INVALID}$ | UI Status Badge |
| **03. Gate Ops** | Flight Inspector Drawer | Selected `GateTimelineView` | `REAL_DERIVED` / `SYNTHETIC` | Active Assignment View | Attributes: Carrier, Tail, Gate, Start, Release, Buffer | Slide-over Drawer |
| **03. Gate Ops** | Export Assignment CSV | `GateTimelineView` List | `REAL_DERIVED` / `SYNTHETIC` | `export_assignments_to_csv()` | Leakage-free schema (zero actual delays) | Download Button |
| **03. Gate Ops** | Export Run Manifest | `SolverRunView` | `REAL_DERIVED` / `SYNTHETIC` | `export_run_manifest_to_json()` | Full solver configuration, hash digests, timing, run_id | Download Button |
| **04. Optimization Lab** | Multi-Solver Comparison | `Sequence[SolverRunView]` | `REAL_DERIVED` / `SYNTHETIC` | Multi-Solver Benchmark Engine | Parallel runs on identical SHA-256 scenario digest | Comparison Table |
| **04. Optimization Lab** | Objective Decomposition | `SolverRunView` | `REAL_DERIVED` / `SYNTHETIC` | Canonical Evaluator | $J = J_{\text{decision}} + J_{\text{reporting}}$, where $J_{\text{dec}} = w_r N_r + w_p N_p + \dots$ | Table & Chart |
| **04. Optimization Lab** | Status Badges | `StatusBadge` | `REAL_DERIVED` / `SYNTHETIC` | `map_solver_status_to_badge()` | `OPTIMAL_PROVEN` (CP-SAT gap 0.0%) vs `FEASIBLE` (Greedy/SA) | Badge Column |
| **04. Optimization Lab** | Pareto Frontier Plot | Benchmark Dataframe | `REAL_DERIVED` / `SYNTHETIC` | Benchmark Runs | Scatter: Objective Value vs Solve Time (seconds) | Plotly Scatter |
| **04. Optimization Lab** | Scalability Curve | Benchmark Dataframe | `SYNTHETIC` | Scalability Harness | Flight scale $N \in [50, 1500]$; $N=1500$ marked `UNKNOWN (Timeout)` | Plotly Line Plot |
| **05. Robustness Lab** | Mode A Conflict Rate | `RecourseEvaluationView` | `REAL_DERIVED` | Static Plan Evaluation | Conflict rate: $\frac{1}{R} \sum_{r=1}^R \mathbf{1}_{\text{conflicts}_r > 0} = 74.8\%$ | Metric & Violin Plot |
| **05. Robustness Lab** | Mode B Conflict Resolution | `RecourseEvaluationView` | `REAL_DERIVED` | Causal Reactive Recourse | Post-recourse conflict rate $= 0.0\%$; Avg reassignments $= 2.56$ | Metric & Paired Plot |
| **05. Robustness Lab** | Mode C Oracle Callout | `RecourseEvaluationView` | `REAL_DERIVED` | Retrospective Greedy Benchmark | Explicit warning: `NON-DEPLOYABLE (GREEDY BENCHMARK)` | Educational Callout |
| **05. Robustness Lab** | Tail Risk (p95 & CVaR95) | Monte Carlo Realizations | `REAL_DERIVED` | Risk Analytics Engine | $p95 = F^{-1}(0.95)$, $CVaR_{95} = \mathbb{E}[J \mid J \ge p95]$; $CVaR_{95} \ge p95$ | Tail Risk Chart |

---

## 3. Data Leakage Barrier Enforcement

The dashboard guarantees that during planning mode:
1. Ground-truth actual delays (`ARR_DELAY`, `DEP_DELAY`, `ARR_DELAY_NEW`, `DEP_DELAY_NEW`) are strictly excluded from all dataframes passed to UI rendering and solver adapters.
2. In `dashboard/adapters/export_adapter.py`, `ScientificValidator.check_prediction_data_leakage()` validates all exported columns before generating downloadable CSV files. Any attempt to export ground-truth actual columns raises an immediate `DataLeakageError`.
