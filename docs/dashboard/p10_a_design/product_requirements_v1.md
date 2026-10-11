# Aeolus Thesis Dashboard — Product Requirements Document (PRD v1.0)

**Document ID:** `AEOLUS-P10-A-PRD-01`  
**Phase:** P10-A (UI/UX Design Specification & Design Freeze)  
**Status:** DESIGN FROZEN  
**Target Application:** Streamlit + Plotly Demonstration & Research Dashboard  
**Thesis Topic:** *"Ứng dụng học máy và lập trình ràng buộc trong dự báo độ trễ chuyến bay và tối ưu tái phân bổ cổng đỗ tàu bay"*

---

## 1. Executive Summary & Product Vision

The **Aeolus Thesis Demonstration Dashboard** is the interactive capstone application of the Aeolus Gate Optimization research project. It bridges complex machine learning models, Operations Research (OR) constraint programming solvers, and large-scale Monte Carlo robustness simulations into a unified, professional, aviation-grade user interface.

The application serves a dual mission:
1. **Thesis Defense Showcase (Presentation Mode):** Deliver an intuitive, high-impact, executive-level demonstration for the graduation evaluation committee and airline operations managers, proving that machine learning delay predictions combined with CP-SAT gate allocation significantly reduce airport congestion and gate conflicts.
2. **Deep Scientific Audit (Research Mode):** Provide an exhaustive, transparent scientific workbench for academic researchers to inspect dual-core turnaround slack, SHAP explainability, mathematical solver formulations, optimality gaps, and stochastic distributions across 500 perturbation scenarios.

---

## 2. Target Personas & Core Use Cases

### Persona 1: The Thesis Examination Committee (Hội đồng Đánh giá Khóa luận)
- **Profile:** Professors and academic reviewers in Computer Science, Operations Research, and Software Engineering.
- **Key Goals:** Verify methodological rigor, validate mathematical formulation correctness (CP-SAT interval constraints vs. soft penalties), check for data leakage prevention, inspect explainability (SHAP), and verify scalability.
- **Primary Mode:** Presentation Mode for the narrative flow, toggling to Research Mode to inspect hard constraint verification and Monte Carlo distribution tails.

### Persona 2: The Hub Operations Dispatcher (Điều phối viên Khai thác Cảng Hàng không)
- **Profile:** Airport gate planning specialist at major hubs (e.g., Hartsfield-Jackson Atlanta International Airport - ATL).
- **Key Goals:** Gain instant situational awareness of inbound delay waves, monitor apron and contact gate capacity bottlenecks, view conflict-free Gantt schedules, and trigger rapid heuristic re-allocation during severe disruptions.
- **Primary Mode:** Presentation Mode (Control Tower and Gate Operations).

### Persona 3: The Operations Research Auditor (Kiểm toán viên Hệ thống Tối ưu)
- **Profile:** Research engineer evaluating algorithm behavior, solve times, memory footprint, and reproducibility.
- **Key Goals:** Inspect exact objective values ($J_{\text{decision}}$ vs. exogenous delay costs), analyze formulation performance (Sparse Interval vs. Dense Time-Indexed), examine solver termination reasons, and verify Monte Carlo statistical tests.
- **Primary Mode:** Research Mode & Research Inspector drawer.

---

## 3. High-Level Functional Requirements (FR)

| Req ID | Domain | Requirement Statement | Traceability | Priority |
| :--- | :--- | :--- | :---: | :---: |
| **FR-01** | Global Navigation | Provide seamless tab/page switching across 5 core views without losing loaded scenario data or active solver solution state. | P10-00 Architecture | P0 |
| **FR-02** | Presentation/Research Tiering | Provide a global switch toggling between Presentation Mode (executive clean view) and Research Mode (academic deep-dive). | P09.5 Discovery | P0 |
| **FR-03** | Scenario Context | Provide a Global Context Bar displaying active airport hub (ATL), active scenario ID, flight count, gate count, and dataset provenance badge. | P10-00 Finding D3 | P0 |
| **FR-04** | Executive Overview | Render Page 1 (Control Tower) displaying high-level operational KPIs, delay pressure gauges, gate inventory, and 15-minute activity timelines. | P09.5 Req Matrix | P0 |
| **FR-05** | ML Delay Intelligence | Render Page 2 (Flight Intelligence) displaying inbound/outbound XGBoost predictions, turnaround slack synthesis, and delay risk classifications. | DualTurnEngine Contract | P0 |
| **FR-06** | Model Explainability | Provide global feature importance rankings and single-flight local SHAP waterfall charts with zero ground-truth leakage in planning mode. | P06 Validation | P1 |
| **FR-07** | Interactive Gate Gantt | Render Page 3 (Gate Operations) featuring a Plotly Gantt chart showing aircraft occupancy $[T_{\text{arr}}, T_{\text{dep}} + \text{buffer})$, gate categories, and reassignment indicators. | P04/P07 Optimization | P0 |
| **FR-08** | Schedule Comparison | Allow switching the Gantt view between Nominal Plan (Original), Optimized Plan (Current Solved), and optional Side-by-Side comparison in Research Mode. | P10-00 Req | P1 |
| **FR-09** | Live Solver Execution | Provide interactive parameter sliders (`w_pref`, `w_remote`, `buffer_time_min`) and a live trigger for Greedy, CP-SAT, and Hybrid solvers on scenarios $\le 150$ flights. | P10-00 Runtime Profile | P0 |
| **FR-10** | Independent Verification | Automatically validate every gate schedule using `verify_hard_constraints_independently(...)` and display a prominent mathematical safety badge. | Evaluation Engine | P0 |
| **FR-11** | Multi-Algorithm Benchmarking | Render Page 4 (Optimization Lab) comparing Greedy, CP-SAT, SA, and Hybrid solvers across decision cost, runtime, remote usage, and optimality gap. | P07 Benchmarks | P0 |
| **FR-12** | Scalability Showcase | Present precomputed 1,500 flights mega-hub scalability benchmarks from P08 without executing heavy live jobs. | P08 Scalability | P1 |
| **FR-13** | Monte Carlo Robustness | Render Page 5 (Robustness Lab) displaying 500-scenario stress test results across Mode A (Fixed), Mode B (Recourse), and Mode C (Oracle Baseline). | P09 Engine | P0 |
| **FR-14** | Scientific Transparency | Explicitly document and differentiate D1 (Mode A 74.8% collision rate vs. 100% timeline mismatch) and D2 (Mode B vs. C greedy parity). | P10-00 Findings D1, D2 | P0 |
| **FR-15** | Research Inspector | Provide an expandable inspector panel displaying run manifests, model checksums, solver seeds, and relative artifact file paths. | Research Auditor Spec | P1 |

---

## 4. Non-Functional Requirements (NFR)

| Req ID | Category | Requirement Specification | Measurement & Target |
| :--- | :--- | :--- | :--- |
| **NFR-01** | **Performance & Latency** | First contentful render of any precomputed page must be sub-second. Interactive slider adjustments on 120 flights must re-render within 300 ms. | Time-to-Interactive < 500 ms (Cached), Live Solve < 150 ms (CP-SAT 120). |
| **NFR-02** | **Memory Footprint** | Total memory consumption must remain bounded and leak-free across prolonged user sessions. | Peak RAM < 350 MB; Idle RAM < 200 MB. |
| **NFR-03** | **Visual Aesthetics** | Comply strictly with the Professional Aviation Dark Theme (`#101B2A` canvas) with high contrast and aerodrome cyan accents. | Contrast ratio $\ge 4.5:1$ (WCAG AA compliant). |
| **NFR-04** | **Typography & Localization** | Primary Vietnamese interface text with full diacritic support, retaining standard international aviation/ML technical terminology. | UTF-8 encoded, clean tabular numerals (`font-variant-numeric: tabular-nums`). |
| **NFR-05** | **Screen Responsiveness** | Desktop-first optimization supporting full-screen projectors (1920×1080) and standard presentation laptops (1366×768) without horizontal scroll. | Breakpoint support at 1366px, 1600px, 1920px. |
| **NFR-06** | **Graceful Degradation** | Missing model files or corrupted scenario records must render clear warning callouts without unhandled Python stack traces crashing the app. | Zero unhandled UI exceptions; graceful fallback cards. |
| **NFR-07** | **Zero Data Leakage** | Year 2024 data must remain completely sealed. Actual arrival delay ground-truth must never be displayed in planning or prediction input views. | Verified against `src/data/leakage_rules.py`. |
| **NFR-08** | **Accessibility (a11y)** | Data visualizations must not rely exclusively on color to convey status; use dual encoding (icons, borders, badges, hatch patterns). | Color-blind safe palettes (Deuteranopia/Protanopia tested). |
| **NFR-09** | **Reproducibility** | Every rendered metric, table, and graph must trace back to an exact artifact file or deterministic calculation seed. | Provenance tag on every data card. |
| **NFR-10** | **Deployment Isolation** | Self-contained execution within the local Python virtual environment without external cloud API dependencies. | 100% offline functional execution. |

---

## 5. Architectural Boundaries & Phase Scope

### What Phase P10 Delivers
- Fully functional 5-page Streamlit application using pre-existing backend modules (`src/optimization/`, `src/simulation/`, `src/models/`).
- Seamless Plotly interactive figures for Gantt, CDFs, Box Plots, and Timelines.
- Interactive live solving for Canonical 120 flights.
- Complete precomputed rendering for 1,500 flights and 500 Monte Carlo scenarios.

### Explicitly Excluded (Out of Scope for P10 v1.0)
- Manual drag-and-drop Gantt assignment re-scheduling.
- Live retraining of XGBoost or neural delay models.
- Live execution of 1,500-flight CP-SAT solvers or 500-scenario Monte Carlo runs inside the browser.
- External multi-airport live flight radar API integrations (FlightAware/ADS-B live streams).
