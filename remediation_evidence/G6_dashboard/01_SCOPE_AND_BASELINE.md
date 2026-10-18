# AEOLUS-G6: Scope and Technical Baseline

**Gate Identifier:** `AEOLUS-G6`  
**Gate Title:** Dashboard Scientific Integrity, Runtime Validation & Visual QA  
**Role:** Senior Frontend/Streamlit Engineer, Data Visualization Engineer, UI Quality Assurance Engineer, Scientific Communication Reviewer  
**Audit Date:** 2026-10-11  
**Target Branch:** `remediation/g6-dashboard`  

---

## 1. UI Scope & Architectural Overview

The Aeolus Gate Optimization Dashboard is a high-performance interactive aviation operations cockpit built with Python and Streamlit. It connects probabilistic machine learning predictions (Dual-Core ML for inbound arrival delays and outbound departure delays) with combinatorial gate reallocation solvers (Greedy, CP-SAT, Simulated Annealing, Hybrid) and dynamic Monte Carlo recourse simulations.

```
+-----------------------------------------------------------------------------------+
|                        AEOLUS STREAMLIT DASHBOARD ARCHITECTURE                   |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  [Entrypoint: app.py] ---> [Sidebar Navigation & Shared Session State]           |
|                                     |                                             |
|        +----------------------------+----------------------------+                |
|        |                            |                            |                |
|  [Page 01: Control Tower]   [Page 02: Flight Intel]    [Page 03: Gate Operations] |
|   - Real-time KPIs           - Dual-Core ML CDFs        - Master Gantt [start,rel)|
|   - Concourse load           - TreeSHAP explanations    - Manual solver trigger   |
|   - Inbound delay wave       - Aircraft turnaround      - Verifier badge & drawer |
|        |                            |                            |                |
|        +----------------------------+----------------------------+                |
|        |                                                         |                |
|  [Page 04: Optimization Lab]                            [Page 05: Robustness Lab] |
|   - Multi-solver comparison                              - Mode A (74.8% conflict)|
|   - Decision vs Reporting cost                           - Mode B Causal Recourse |
|   - Pareto Frontier & Scalability                        - Mode C Oracle Reference|
|                                                                                   |
+-----------------------------------------------------------------------------------+
|               CORE SERVICES, ADAPTERS & SCIENTIFIC SECURITY BARRIER              |
+-----------------------------------------------------------------------------------+
|  [Scenario Loader] <---> [Config & Path Allowlist] <---> [Preflight Engine]      |
|  [Export Adapter]  <---> [Scientific Validator]    <---> [Solver Service]        |
+-----------------------------------------------------------------------------------+
```

### 1.1. Five Dedicated Functional Pages

1. **Page 01: Control Tower (`dashboard/pages/page_01_control_tower.py`)**
   - High-level hub situational awareness for Atlanta Hartsfield-Jackson (ATL).
   - Inbound delay distribution wave, concourse load (T, A, Remote), active flight and gate KPIs.
   - Dynamic scenario switcher with instantaneous state reactivity.

2. **Page 02: Dual-Core Flight Intelligence (`dashboard/pages/page_02_flight_intelligence.py`)**
   - Dual-Core ML intelligence for Arrival (NGBoost Student-t predictive distribution CDF $P(\text{delay} \ge 15)$) and Departure (XGBoost/Ridge risk score).
   - Aircraft turnaround dynamics: minimum 45-minute technical turn, inbound delay absorption, slack propagation, cross-midnight turnaround handling.
   - Global and local TreeSHAP explanations (`origin_delay`, `scheduled_dwell`, `route_distance`).
   - Anti-leakage verification panel confirming zero ground-truth actual delay exposure during planning.

3. **Page 03: Gate Operations & Master Gantt (`dashboard/pages/page_03_gate_operations.py`)**
   - Authoritative Master Gantt chart rendering half-open intervals $[start, release)$ including the mandatory 15-minute buffer.
   - Strict manual trigger constraint: zero unsolicited solver invocations upon page entry or filter adjustment.
   - Concourse filtering with dynamic stand counts, apron overflow containment (`APRON_*` categorized as `OVERFLOW`, never Concourse A).
   - Independent verification badge (`XÁC MINH HỢP LỆ`) and slide-over flight inspector drawer.

4. **Page 04: Optimization Lab (`dashboard/pages/page_04_optimization_lab.py`)**
   - Fair multi-solver comparative benchmark across Greedy, CP-SAT, Simulated Annealing, and Hybrid.
   - Explicit separation of Decision Cost ($J_{\text{decision}}$) from Reporting Cost ($J_{\text{reporting}}$).
   - Pareto Frontier visualization (Cost vs Time), runtime breakdown, and CP-SAT scalability curve up to 1,500 flights (with $N=1500$ annotated as `UNKNOWN / Timeout 30s`).

5. **Page 05: Robustness Lab & Monte Carlo (`dashboard/pages/page_05_robustness_lab.py`)**
   - 500-realization Gaussian Copula and Student-t uncertainty simulation.
   - Mode A (Fixed Plan Baseline) showing 74.8% empirical conflict rate and 100% static schedule invalidation under real weather.
   - Mode B (Causal Reactive Recourse) demonstrating 100% conflict elimination with minimal reassignments ($2.56$ avg).
   - Mode C (Perfect Foresight Oracle) explicitly badged as `NON-DEPLOYABLE (GREEDY BENCHMARK)`, never misrepresented as global optimum.
   - Tail risk quantification confirming $CVaR_{95} \ge p95$.

---

## 2. Presentation Mode vs Research Mode

The dashboard provides a global mode toggle in the sidebar:

| Mode | Target Audience | Display Characteristics | Information Density |
|:---|:---|:---|:---|
| **Presentation Mode** | Thesis Committee, Defense Audience | High-level executive KPIs, clean Gantt chart, multi-solver summary tables, prominent clearance status badges | Streamlined, focus on core operational metrics and visual clarity |
| **Research Mode** | Auditors, ML Engineers, OR Reviewers | Full mathematical diagnostics, SHA-256 scenario digests, parameter fingerprints, TreeSHAP force plots, preflight health logs, raw latency breakdowns | Deep auditability, technical reproducibility, and contract transparency |

---

## 3. Preflight Diagnostic Engine

The dashboard implements a resilient preflight diagnostic subsystem (`dashboard/services/preflight.py` and `dashboard/components/preflight_banner.py`) executing before page rendering:

1. **Model Checkpoint Integrity:** Checks existence and readability of frozen model checkpoints (`artifacts/models/p4_arrival_ngboost/`, `artifacts/models/p8_outbound_xgb/`).
2. **Benchmark Artifact Verification:** Verifies presence of certified benchmark runs, Monte Carlo realizations, and scenario JSONs.
3. **Data Provenance Check:** Confirms that claimed data origins match underlying data contracts.
4. **Graceful UI Degradation:** If optional components (such as local SHAP tree explainer weights) are absent, the dashboard does not crash with an unhandled traceback; instead, it renders an educational diagnostic banner with clear remediation instructions.
