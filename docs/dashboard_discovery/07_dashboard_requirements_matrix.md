# Phase P09.5 Technical Discovery: Dashboard Requirements & Traceability Matrix

**Document ID:** `DISC-07-REQ-MATRIX`  
**Phase:** `P09.5 — DASHBOARD DISCOVERY & TECHNICAL HANDOFF`  
**Audit Date:** 2026-10-09  
**Auditor Roles:** UI/UX Requirements Analyst, Operations Research Specialist, Thesis Auditor  

---

## 1. Candidate Pages Feasibility Analysis

We evaluated seven candidate dashboard pages against the current repository backend:

### Page A: Airport Operational Overview
- **Objective:** Executive summary for thesis committee showing the airport operational context (Hartsfield–Jackson Atlanta International Airport, `ATL`), volume of scheduled turns, predicted delay pressure, and high-level optimization summary.
- **Backend Data Status:** **READY.**
- **Key Metrics:** Total flights, contact gates, remote stands, mean predicted arrival/departure delay, initial vs optimized gate assignment stats.

### Page B: Flight Delay Prediction & ML Explainability
- **Objective:** Demonstrates the Machine Learning component of the thesis (prediction accuracy, uncertainty quantification, and TreeSHAP explainability).
- **Backend Data Status:** **READY.**
- **Key Visualizations:**
  - Classification metrics table (ROC-AUC, PR-AUC, Brier score) and regression metrics (MAE, RMSE, Bias).
  - Probabilistic metrics (CRPS, 80%/90% coverage).
  - Global TreeSHAP feature importance bar chart.
  - Interactive individual flight TreeSHAP waterfall explanation (using [`shap_case_studies.json`](file:///D:/Study/Code/Python/Aelous/artifacts/remediation/ml_validation/shap_outputs/shap_case_studies.json)).

### Page C: Dual-Core Aircraft Turn Dynamics
- **Objective:** Visualizes how inbound and outbound flight legs are synthesized into a physical aircraft turn enforcing the mandatory 45-minute ground turnaround time.
- **Backend Data Status:** **READY.**
- **Key Visualizations:** Interactive timeline diagram showing $A_{\text{sched}} \to A_{\text{pred}} \to T_{\text{min}} \to D_{\text{pred}} \to D_{\text{gate\_out}} \to T_{\text{release}}$. Allows examining slack tightness and turnaround buffer violations.

### Page D: Gate Assignment & Interactive Gantt Schedule
- **Objective:** The centerpiece operational demonstration of the thesis. Displays the spatial-temporal allocation of aircraft turns to physical gates.
- **Backend Data Status:** **READY.**
- **Key Visualizations:**
  - Interactive Plotly Gantt chart (X-axis: time in minutes / HH:MM; Y-axis: Gate IDs categorized into Contact Gates, Remote Stands, Overflow Apron).
  - Color encoding: Nominal vs Reassigned gate; Contact vs Remote.
  - Hover tooltips: Flight number, carrier, arrival delay, pushback time, turnaround slack.
  - Comparison mode: Timetable Schedule vs Optimized Gate Plan.

### Page E: Solver Benchmark & Scalability Evaluation
- **Objective:** Compares Deterministic Greedy, Google OR-Tools CP-SAT, Simulated Annealing, and Two-Stage Hybrid solvers.
- **Backend Data Status:** **READY.**
- **Key Visualizations:**
  - Multi-solver decision cost comparison bar chart.
  - Solver runtime breakdown (Model construction time vs search time vs validation time).
  - Scalability curve across problem sizes ($N = 100 \dots 1,500$ flights).
  - Optimality gap and solver status badges.

### Page F: Monte Carlo Robustness & Tail Risk
- **Objective:** Demonstrates the scientific evaluation of schedule resilience under 500 stochastic delay realizations.
- **Backend Data Status:** **READY.**
- **Key Visualizations:**
  - Comparative cost distribution histograms (Mode A Fixed Plan vs Mode B Reactive Recourse).
  - Cumulative distribution function (CDF) curves with CVaR-90 and CVaR-95 cutoffs.
  - Monte Carlo convergence trace ($N = 1 \dots 500$).
  - Scenario drill-down tool allowing inspection of specific simulated days.

### Page G: Research Governance, Provenance & Audit
- **Objective:** Provides transparency into model hashes, random seeds, protocol quality gates, and data leakage verification.
- **Backend Data Status:** **READY.**
- **Key Visualizations:** Model registry table with SHA-256 hashes, temporal split diagrams, quality gate certification logs.

---

## 2. Requirement Traceability Matrix (RTM)

The matrix below maps each functional requirement to its thesis necessity, data availability, implementation readiness, and remaining work for Phase P10:

| Req ID | Feature / Component | Classification | Source / Reference | Data Available | Implementation Readiness | Phase P10 Implementation Tasks |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **REQ-01** | Executive KPI cards (Flights, Gates, Delay, Cost) | **Mandatory** | Thesis Outline | Yes | **READY** | Build Streamlit KPI cards from `OptimizationResult`. |
| **REQ-02** | Interactive Gate Assignment Gantt Chart | **Mandatory** | Thesis Outline | Yes | **READY** | Build Plotly horizontal bar timeline with gate categorizations. |
| **REQ-03** | Original Schedule vs Optimized Schedule comparison | **Mandatory** | Thesis Outline | Yes | **READY** | Toggle between nominal assignments and optimized assignments. |
| **REQ-04** | Real-time / Live Solver Execution (Greedy, CP-SAT) | **Mandatory** | P07/P08 Scripts| Yes | **READY** | Connect UI inputs to `CPSatGateSolver` and `DeterministicGreedyGateSolver`. |
| **REQ-05** | Solver Configuration Controls (Weights, Time Budget)| **Mandatory** | `config.py` | Yes | **READY** | Build sidebar sliders mapped to `GateOptimizationConfig`. |
| **REQ-06** | Algorithm Comparison View (Cost, Runtime, Gap) | **Mandatory** | P05 Benchmark | Yes | **READY** | Ingest `solver_runs.csv` and render comparative Plotly charts. |
| **REQ-07** | Monte Carlo Cost Distribution (Mode A vs Mode B) | **Mandatory** | P09 Protocol | Yes | **READY** | Plot histograms and KDE curves from `fixed_plan_results.csv`. |
| **REQ-08** | Monte Carlo Tail Risk & CVaR Metrics | **Mandatory** | P09 Protocol | Yes | **READY** | Ingest `statistical_summary.json` and display CVaR metrics. |
| **REQ-09** | TreeSHAP Feature Importance & Local Attribution | **Mandatory** | P08 ML Audit | Yes | **READY** | Render global bar chart & local flight waterfall plots. |
| **REQ-10** | ML Classification & Regression Performance Metrics | **Mandatory** | P08 ML Audit | Yes | **READY** | Display formatted metric tables from `classification_metrics.csv`. |
| **REQ-11** | Physical Aircraft Turn Timeline Visualization | **Extended** | P07 Turn Engine| Yes | **READY** | Plot step timeline for individual turn pairs. |
| **REQ-12** | CP-SAT Scalability Curve (100 to 1,500 Flights) | **Extended** | P06 Scalability| Yes | **READY** | Ingest `scalability_results.csv` and plot runtime scaling. |
| **REQ-13** | Model Registry & Cryptographic Provenance View | **Extended** | P00 Audit | Yes | **READY** | Display registry table with SHA-256 validation status. |
| **REQ-14** | Custom Flight Schedule Upload (User CSV/Excel) | **Extended** | Ideation | Partial | **PARTIAL** | Requires CSV validation adapter and schema firewall. |
| **REQ-15** | Live 500-Scenario Monte Carlo Execution in UI | **Extended** | P09 Engine | Yes | **PARTIAL** | Runs in ~3.5s for 120 flights; requires progress bar and caching. |
| **REQ-16** | Export Assignment & Reports to PDF / Excel | **Extended** | Ideation | No | **MISSING** | Requires `reportlab` or pandas Excel exporter. |

---

## 3. Recommended Page Architecture (Consolidation Strategy)

To avoid an overwhelming navigation hierarchy during a 20–30 minute thesis presentation, we recommend consolidating the seven candidate views into **Five Clean Pages**:

```
Aeolus Demonstration Dashboard
├── 1. Overview & Operational Hub (Consolidates Pages A & C)
│   ├── Airport KPIs & Active Scenario Summary
│   ├── Aircraft Turn Timeline Decomposition
│   └── Quick Run Optimization Panel
├── 2. Gate Allocation & Gantt Schedule (Page D)
│   ├── Interactive Master Gantt Chart (Plotly)
│   ├── Schedule Comparison (Nominal vs Optimized Plan)
│   ├── Stand Capacity Utilization & Remote Overflow Breakdown
│   └── Flight Assignment Detail Inspector
├── 3. Flight Delay Prediction & Explainability (Page B)
│   ├── Model Performance Benchmarks (Point & Probabilistic)
│   ├── Global TreeSHAP Feature Attributions
│   └── Local Flight Explainability Waterfall Tool
├── 4. Solver Benchmark & Scalability (Page E)
│   ├── Algorithm Face-off (Greedy vs CP-SAT vs SA vs Hybrid)
│   ├── Multi-tier Runtime & Build Overheads Breakdown
│   └── Scalability Stress Curve (up to 1,500 Flights)
└── 5. Monte Carlo Robustness & Risk (Consolidates Pages F & G)
    ├── Mode A (Fixed Plan) vs Mode B (Recourse) Distribution
    ├── Risk Analysis & CVaR-95 Expected Shortfall
    ├── Monte Carlo Convergence & Scenario Drill-Down
    └── Scientific Provenance & Checkpoint Verifier
```
