# Dashboard Integration Decisions & Architecture Lock

**Document ID:** `AEOLUS-P10-00-INTEGRATION-DECISIONS`  
**Phase:** P10-00 (Repository & Scientific Readiness Audit)  
**Audit Timestamp:** 2026-10-09T17:17:00+07:00  
**Verification Method:** Cross-Domain Architecture Harmonization and UX Boundary Locking

---

## 1. Executive Summary

This document locks the structural, operational, and presentation decisions for Phase P10 (Thesis Demonstration Dashboard). It codifies the division between **Presentation Mode** (clean executive aviation view) and **Research Mode** (in-depth academic validation inspector), establishes the boundaries between live computation and precomputed artifact rendering, and defines safeguards against scientific misinterpretation.

---

## 2. Global Architecture & Navigation Framework

The application is structured as a multi-page Streamlit application using a unified **Professional Aviation Dark Theme**:
- **Background:** Deep Navy / Carbon Slate (`#0B1118` to `#16202C`)
- **Accents:** Aerodrome Cyan (`#00D2FF`), Taxiway Amber (`#FFB300`), Alert Red (`#FF3B30`), Safety Green (`#34C759`)
- **Language:** Primary Vietnamese (Tiếng Việt) with international aviation/ML standard terms (On-time Departure, Slack, SHAP, CP-SAT, Gantt, Monte Carlo).

### The Five Canonical Pages

```
AEOLUS CONTROL SYSTEM
├── 1. Control Tower (Tổng quan Điều hành Trung tâm)
├── 2. Flight Intelligence (Dự báo Trễ & Giải thích Mô hình)
├── 3. Gate Operations (Gantt Chart & Phân bổ Cổng)
├── 4. Optimization Lab (Phòng thí nghiệm Tối ưu hóa)
└── 5. Robustness Lab (Kiểm thử Bền vững Monte Carlo)
```

---

## 3. Presentation Mode vs. Research Mode Specification

A persistent sidebar switch allows switching between the two viewing tiers:

| Dimension | Presentation Mode (Default) | Research Mode (Academic Toggle) |
| :--- | :--- | :--- |
| **Primary Audience** | Thesis Evaluation Jury, Airline Operations Managers | Machine Learning Researchers, Operations Research Auditors |
| **KPI Granularity** | High-level metrics: On-time %, Gate reassignments, Total delay saved | Mathematical formulations, duality gaps, loss functions, p-values |
| **Visual Emphasis** | High-impact Plotly Gantt charts, status scorecards, flight cards | SHAP waterfall breakdowns, solver iteration graphs, CDF distributions |
| **Algorithmic Detail**| Explains *what* the system decided and operational benefits | Explains *how* constraint programming and ML interact mathematically |
| **Inspector Area** | Hidden by default | Unfolds `st.expander` sections containing raw JSONs and diagnostic logs |

---

## 4. Execution Capability Partitioning

To protect application responsiveness and prevent browser freezes, algorithmic execution is strictly classified into three tiers:

### Tier 1: Unlocked Live Execution
These operations run directly inside Streamlit sessions because their latencies are under 150 ms:
1. **Interactive Gate Solving (Canonical 120 flights):**
   - User adjusts: `w_pref` (penalty per reassignment), `w_remote` (remote apron cost), `buffer_time_min` (separation buffer).
   - Solvers supported live: `DeterministicGreedyGateSolver`, `CPSatGateSolver` (sparse interval formulation), `HybridGateSolver`.
2. **Single-Flight ML Inference & SHAP Breakdown:**
   - User selects an inbound flight from the active schedule.
   - Live prediction of arrival delay and local SHAP feature waterfall breakdown (< 120 ms).
3. **Single Monte Carlo Scenario Stress Test:**
   - User injects a custom delay vector or selects a specific perturbation seed from 1 to 500.
   - Interactive live re-evaluation of gate conflicts and greedy recourse (< 10 ms).

### Tier 2: Precomputed Artifact Rendering
These operations exceed interactive UI budgets (10 s to 60 s) and are rendered from pre-verified research artifacts:
1. **1,500 Flights Scalability Stress Test (P08):**
   - Loaded from `artifacts/stress_1500x50/solver_results.parquet` and `aggregate_metrics.json`.
   - Visualizes multi-solver scalability, solve times, and gate utilization curves for a 24-hour mega-hub wave.
2. **500-Scenario Monte Carlo Robustness Matrix (P09):**
   - Loaded from `artifacts/remediation/monte_carlo/fixed_plan_results.csv`, `recourse_results.csv`, `oracle_results.csv`.
   - Visualizes empirical Cumulative Distribution Functions (CDFs), box plots, and paired statistical differences.
3. **Global SHAP Feature Importance:**
   - Loaded from `artifacts/remediation/ml_validation/shap_outputs/global_importance.csv`.

### Tier 3: Quarantined & Blocked Operations
Strictly disallowed from dashboard execution:
1. **Model Retraining & Optuna Hyperparameter Optimization:** Fully blocked.
2. **Dataset Modifications:** All source tables in `data/` are treated as read-only.
3. **2024 Operations Data:** Completely hidden from scenario selection to uphold the holdout seal (Finding D3).

---

## 5. Page-by-Page Integration Matrix

### Page 1: Control Tower (Tổng quan Điều hành)
- **Status:** **UNLOCKED (PRECOMPUTED + LIVE SWITCH)**
- **Header:** Hub Status, Active Schedule (`SCEN_P09_CANONICAL_120`), Operations Date.
- **Executive Metric Cards:**
  - Tổng số chuyến bay: `120`
  - Tỷ lệ đúng giờ dự kiến: `84.2%` (tăng từ `71.5%` so với kế hoạch tĩnh)
  - Số cổng đỗ sử dụng: `25 Cổng tiếp xúc + 1 Cổng từ xa`
  - Số chuyến đổi cổng (CP-SAT): `0` (kế hoạch danh định tối ưu)
- **Live Action:** Scenario Selector dropdown to switch between Canonical 120 and Historical Peak 2023.

### Page 2: Flight Intelligence (Dự báo Trễ & ML)
- **Status:** **UNLOCKED (LIVE INFERENCE + CACHED TEST DATA)**
- **Features:**
  - Flight Schedule Table with sortable predicted delay and turnaround risk flags.
  - Interactive Flight Selector: displays flight details, tail number, route (e.g., ORD $\to$ ATL $\to$ MCO).
  - Dual Prediction Card: Inbound delay prediction vs. Outbound departure risk.
  - SHAP Explainability Pane: Top positive/negative delay contributors.
  - Research Mode: Displays model evaluation metrics (MAE = 12.4 min, $R^2 = 0.41$, CRPS = 8.12).

### Page 3: Gate Operations (Gantt Chart Tương tác)
- **Status:** **UNLOCKED (PLOTLY INTERACTIVE GANTT)**
- **Features:**
  - Primary Visual: Plotly Gantt chart with time on x-axis (06:00 to 12:00) and Gates on y-axis (A01 to A25, Remote).
  - Hover Tooltips: Flight ID, Tail, Time Window, Turnaround Slack, Reassignment status.
  - Visual Indicators: Color by flight status (Green: Normal, Amber: Medium Risk, Red: High Risk, Purple: Remote Apron).
  - Filter Controls: Concourse multi-select, Time-window zoom, Delay threshold slider.

### Page 4: Optimization Lab (Phòng thí nghiệm Thuật toán)
- **Status:** **UNLOCKED (LIVE COMPARATIVE SOLVING)**
- **Features:**
  - Algorithm Comparison Matrix: Deterministic Greedy vs. CP-SAT vs. Hybrid vs. Simulated Annealing.
  - Live Solve Button: Runs selected solver in real-time, displays solve time, objective cost, and status badge.
  - Interactive Weight Sliders: `w_pref` ($[0, 50]$), `w_remote` ($[50, 500]$), `buffer_time_min` ($[10, 30]$).
  - Verification Badge: Direct call to `verify_hard_constraints_independently(...)` showing `"0 Violations - Mathematically Proven"`.
  - Research Mode Expander: Displays 1,500 flights scalability benchmarks from P08.

### Page 5: Robustness Lab (Kiểm thử Bền vững Monte Carlo)
- **Status:** **UNLOCKED (PRECOMPUTED 500 SCENARIOS + LIVE SINGLE SCENARIO)**
- **Features:**
  - Mode A (Fixed Plan) vs. Mode B (Recourse) vs. Mode C (Oracle Baseline) Comparison.
  - Scientific Disclaimers (Addressing D1 and D2):
    - Explains D1: 74.8% Physical Conflict Rate vs. 100% Static Schedule Mismatch.
    - Explains D2: Parity between Mode B and Mode C on Canonical 120 flights.
  - Interactive Distribution Visualizations: Empirical CDF of Objective Cost, Reassignment Box Plots.
  - Scenario Deep-Dive: Slider to select any scenario index from 1 to 500 to inspect flight-level reassignment traces.

---

## 6. Scenario Registry Contract

To ensure consistent flight data across all pages, scenarios will be loaded via a centralized `ScenarioRegistry`:
```python
# src/dashboard/scenario_registry.py
class ScenarioRegistry:
    @staticmethod
    def get_canonical_120() -> Tuple[List[Flight], List[Gate]]: ...
    
    @staticmethod
    def list_available_scenarios() -> List[Dict[str, str]]:
        return [
            {"id": "SCEN_P09_CANONICAL_120", "name": "Atlanta Peak Morning (120 Flights, 25 Gates)", "source": "BTS 2023"},
            {"id": "SCEN_2023_PEAK_01", "name": "Atlanta Concourse T Stress (85 Flights, 15 Gates)", "source": "BTS 2023"},
        ]
```
No 2024 scenario IDs will ever be registered.

---

## 7. Architecture Sign-Off
All integration decisions documented above are frozen and will serve as the invariant technical requirements for the upcoming Phase P10 implementation.
