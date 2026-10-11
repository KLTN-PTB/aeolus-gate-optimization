# Visualization Contracts & Plotly Figure Specifications

**Document ID:** `AEOLUS-P10-A-VIS-CONTRACTS-10`  
**Phase:** P10-A (UI/UX Design Specification & Design Freeze)  
**Status:** DESIGN FROZEN  
**Total Figures Specified:** 16 Comprehensive Visualization Contracts  

---

## 1. Executive Summary

This document establishes the binding visualization contracts for all 16 interactive Plotly figures in the Aeolus dashboard. Each figure is defined with strict mathematical schemas, data sources, hover payloads, accessibility rules, performance budgets, and scientific interpretation boundaries.

---

## 2. Master Visualization Index

| Chart ID | Page | Figure Title | Plotly Trace Type | Data Source | Latency Budget |
| :---: | :---: | :--- | :--- | :--- | :---: |
| **CHART-01** | Page 1 | Operational Activity Timeline | `go.Bar` (Stacked) | Flight Leg Schedule | < 25 ms |
| **CHART-02** | Page 2 | Arrival Delay Distribution & KDE | `go.Histogram` + `go.Scatter` | `predictions_sample.csv` | < 20 ms |
| **CHART-03** | Page 2 | Aircraft Turn & Slack Dynamics | `go.Bar` (Horizontal Stacked) | `SimulationTurnResult` | < 15 ms |
| **CHART-04** | Page 2 | ML Model Validation Metrics Radar | `go.Scatterpolar` / `go.Bar` | `regression_metrics.csv` | < 10 ms |
| **CHART-05** | Page 2 | Global SHAP Feature Importance | `go.Bar` (Horizontal) | `global_importance.csv` | < 15 ms |
| **CHART-06** | Page 2 | Single-Flight Local SHAP Waterfall | `go.Waterfall` | `shap_case_studies.json` | < 25 ms |
| **CHART-07** | Page 3 | Master Interactive Gate Gantt | `go.Bar` (Horizontal Timeline) | `OptimizationResult` | < 60 ms |
| **CHART-08** | Page 1/3 | Gate Concourse Inventory & Utilization | `go.Bar` (Grouped Horizontal) | Gate Master + Assignments | < 15 ms |
| **CHART-09** | Page 4 | Solver Cost vs Runtime Pareto Frontier| `go.Scatter` (Bubble, Log-X) | `solver_runs.csv` | < 20 ms |
| **CHART-10** | Page 4 | Solver Component Runtime Breakdown | `go.Bar` (Stacked) | `solver_runs.csv` | < 15 ms |
| **CHART-11** | Page 4 | Mega-Hub Scalability Curve (1,500 N) | `go.Scatter` (Lines+Markers) | `stress_1500x50/results` | < 30 ms |
| **CHART-12** | Page 5 | Monte Carlo Objective Cost Histogram | `go.Histogram` (Grouped) | `fixed_plan / recourse.csv` | < 35 ms |
| **CHART-13** | Page 5 | Empirical Cumulative Distribution (CDF) | `go.Scatter` (`step="hv"`) | `fixed_plan / recourse.csv` | < 30 ms |
| **CHART-14** | Page 5 | Reassignment & Remote Gate Boxplot | `go.Box` | `recourse_results.csv` | < 20 ms |
| **CHART-15** | Page 5 | Monte Carlo Running Mean Convergence | `go.Scatter` (Lines) | `statistical_summary.json` | < 25 ms |
| **CHART-16** | Page 5 | Single Scenario Perturbation Trace | `go.Scatter` + `go.Bar` | `scenario_index.csv` | < 20 ms |

---

## 3. Exhaustive Chart Contracts (1 to 16)

### CHART-01: Operational Activity Timeline
- **Page:** Page 1 (Control Tower)
- **Purpose:** Display traffic volume distribution over the operational wave to identify peak congestion periods.
- **Data Source:** Scenario flight legs (`scheduled_arrival_min`, `scheduled_departure_min`).
- **Schema:** `time_bin_15m` (string, HH:MM), `inbound_count` (int), `outbound_count` (int).
- **Axes:** X: Local Time (HH:MM); Y: Movements per 15 minutes (Count).
- **Hover:** `Khung giờ: {time} | Hạ cánh: {in} | Cất cánh: {out} | Tổng cộng: {tot}`.
- **Acceptance:** Stacked bar chart, Aerodrome Cyan for inbound, Runway Blue for outbound. Clean zero-margins.

---

### CHART-02: Arrival Delay Distribution & KDE
- **Page:** Page 2 (Flight Intelligence)
- **Purpose:** Illustrate distribution of predicted arrival delays across the active flight cohort.
- **Data Source:** `artifacts/remediation/native_dual_core/predictions_sample.csv`.
- **Axes:** X: Predicted Arrival Delay (Minutes); Y: Frequency (Flight Count).
- **Hover:** `Khoảng trễ: {bin} min | Số lượng: {count} chuyến bay ({pct}%)`.
- **Threshold Annotations:** Vertical dashed amber line at $+15$ min (FAA on-time threshold).

---

### CHART-03: Aircraft Turn & Slack Dynamics
- **Page:** Page 2 (Flight Intelligence)
- **Purpose:** Deconstruct an individual aircraft turnaround into inbound delay, scheduled turn window, minimum turn requirement, slack absorption, and outbound propagation.
- **Data Source:** `SimulationTurnResult` instance from `DualTurnEngine`.
- **Trace Type:** Horizontal stacked bar (`go.Bar`).
- **Segments:** Inbound Leg $\to$ Absorbed Delay $\to$ Remaining Slack $\to$ Propagated Outbound Delay $\to$ 15m Buffer.
- **Formula Verification:** $T_{\text{slack\_remaining}} = \max(0, T_{\text{sched\_slack}} - \hat{d}_{\text{arr}})$.

---

### CHART-04: ML Model Validation Metrics Radar
- **Page:** Page 2 (Flight Intelligence - Research Mode)
- **Purpose:** Compare validation performance metrics across Model Iterations (Baseline vs XGBoost vs Quantile).
- **Data Source:** `artifacts/remediation/ml_validation/regression_metrics.csv`.
- **Axes:** Polar coordinates ($r$: Normalized Metric Score, $\theta$: MAE, RMSE, $R^2$, CRPS, Coverage 90%).

---

### CHART-05: Global SHAP Feature Importance
- **Page:** Page 2 (Flight Intelligence)
- **Purpose:** Rank top operational drivers influencing arrival delay predictions globally.
- **Data Source:** `artifacts/remediation/ml_validation/shap_outputs/global_importance.csv`.
- **Axes:** X: Mean Absolute SHAP Value ($|\phi_j|$, minutes); Y: Feature Name (sorted ascending).
- **Bar Color:** Solid Aerodrome Cyan with hover explanation of feature definitions.

---

### CHART-06: Single-Flight Local SHAP Waterfall
- **Page:** Page 2 (Flight Intelligence)
- **Purpose:** Explain individual flight delay prediction as a linear sum of feature contributions starting from base value $E[f(x)]$.
- **Data Source:** `artifacts/remediation/ml_validation/shap_outputs/shap_case_studies.json`.
- **Trace Type:** `go.Waterfall`.
- **Coloring:** Positive delay pushes in Alert Red / Caution Amber; negative delay reducers in Clearance Green.

---

### CHART-07: Master Interactive Gate Gantt
- **Page:** Page 3 (Gate Operations)
- **Purpose:** Core visualization of flight assignments, time windows, separation buffers, and conflict-free schedules.
- **Data Source:** `OptimizationResult.assignments` joined with `Flight` domain objects.
- **Geometry:** Horizontal stacked bar with base offsets:
  - Base $= T_{\text{arr}}$, Width $= T_{\text{dep}} - T_{\text{arr}}$
  - Buffer Base $= T_{\text{dep}}$, Buffer Width $= \text{buffer\_time\_min}$
- **Y-Axis Categories:** `T01` to `T10`, `A01` to `A15`, `REMOTE_OVERFLOW`.
- **Buffer Integrity:** Release buffer is visibly hatched; no overlap between distinct aircraft on same gate.

---

### CHART-08: Gate Concourse Inventory & Utilization
- **Page:** Page 1 / Page 3
- **Purpose:** Gauge peak simultaneous gate occupancy per concourse.
- **Data Source:** Gate assignments aggregated across 15-minute time steps.
- **Axes:** X: Peak Occupancy Count vs Capacity; Y: Concourse (`T`, `A`, `Remote`).
- **Thresholds:** Colored green ($<80\%$), amber ($80\text{--}99\%$), red ($100\%$).

---

### CHART-09: Solver Cost vs. Runtime Trade-off (Pareto Frontier)
- **Page:** Page 4 (Optimization Lab)
- **Purpose:** Demonstrate the Pareto frontier between algorithmic computational time and objective decision cost.
- **Data Source:** `artifacts/remediation/benchmarks/solver_runs.csv`.
- **Axes:** X: Solve Time in seconds (Log scale); Y: Decision Cost ($J_{\text{decision}}$).
- **Marker Styling:** Bubble size reflects remote apron usage; colors indicate algorithm families.

---

### CHART-10: Solver Component Runtime Breakdown
- **Page:** Page 4 (Optimization Lab)
- **Purpose:** Dissect CP-SAT and Hybrid runtimes into Model Building, Presolve, and Branch-and-Bound search phases.
- **Data Source:** `artifacts/remediation/benchmarks/solver_runs.csv`.
- **Trace Type:** Stacked Barchart (`go.Bar`).

---

### CHART-11: Mega-Hub Scalability Curve (1,500 Flights)
- **Page:** Page 4 (Optimization Lab)
- **Purpose:** Showcase algorithm scalability from canonical wave (120 flights) to full 24-hour mega-hub (1,500 flights).
- **Data Source:** `artifacts/stress_1500x50/solver_results.parquet`.
- **Axes:** X: Flight Scale $N$; Y: Runtimes in seconds.
- **Key Takeaway:** Greedy remains $<0.05$s; CP-SAT scales quadratically but completes within 35s.

---

### CHART-12: Monte Carlo Objective Cost Histogram
- **Page:** Page 5 (Robustness Lab)
- **Purpose:** Display frequency distribution of scenario costs under Mode A vs. Mode B across 500 stochastic runs.
- **Data Source:** `artifacts/remediation/monte_carlo/fixed_plan_results.csv` and `recourse_results.csv`.
- **Visual Distinction:** Mode B forms a compact bell curve around $130.0$; Mode A forms a heavy tail extending beyond $20,000.0$.

---

### CHART-13: Empirical Cumulative Distribution Function (CDF)
- **Page:** Page 5 (Robustness Lab)
- **Purpose:** Provide rigorous academic comparison of cost exceedance probabilities $P(J \le x)$.
- **Data Source:** Monte Carlo 500 scenario evaluation CSVs.
- **Trace Type:** `go.Scatter` with `line_shape="hv"`.
- **Traces:** Mode B (Cyan solid), Mode C (Green dotted), Mode A (Red dashed).

---

### CHART-14: Reassignment & Remote Gate Boxplot
- **Page:** Page 5 (Robustness Lab)
- **Purpose:** Show median, interquartile range (IQR), and outlier frequency of tactical gate reassignments.
- **Data Source:** `artifacts/remediation/monte_carlo/recourse_results.csv`.
- **Axes:** X: Operational Mode; Y: Number of Gate Reassignments.
- **Metrics:** Median $= 2.0$, Q3 $= 4.0$, Max $= 8.0$.

---

### CHART-15: Monte Carlo Running Mean Convergence
- **Page:** Page 5 (Robustness Lab - Research Mode)
- **Purpose:** Prove statistical convergence of Monte Carlo estimator across $N = 1$ to $500$ scenarios.
- **Data Source:** Cumulative mean of `recourse_results.csv`.
- **Plot:** Running Mean with $\pm 1.96 \cdot \text{SE}$ shaded confidence band converging tightly by scenario 200.

---

### CHART-16: Single Scenario Perturbation Trace
- **Page:** Page 5 (Robustness Lab)
- **Purpose:** Allow interactive drill-down into any specific scenario index from 1 to 500.
- **Data Source:** Selected slice from `artifacts/remediation/monte_carlo/scenario_index.csv`.
- **Visual:** Waterfall of delay deviations for the top-10 delayed flights in that scenario and the corresponding gate swaps executed.
