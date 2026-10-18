# AEOLUS-G6: Limitations and Operational Risks

**Gate Identifier:** `AEOLUS-G6`  
**Gate Title:** Dashboard Scientific Integrity, Runtime Validation & Visual QA  
**Audit Date:** 2026-10-11  
**Target Branch:** `remediation/g6-dashboard`  

---

## 1. Streamlit Framework & Frontend Architecture Limitations

### 1.1. Single-Threaded Event Loop per Session
- **Limitation:** Streamlit executes pages procedurally from top to bottom on each user interaction. While `@st.cache_data` and `@st.cache_resource` mitigate recomputation overhead for data loading and model inference, running computationally intensive solvers in the same thread as UI rendering can momentarily pause browser interactivity.
- **Mitigation in Aeolus:** Solver executions enforce a strict 30-second wall-clock timeout (`time_limit_sec = 30.0`), preventing indefinite UI freezing. Furthermore, precomputed benchmark runs are available in the dropdowns for instantaneous zero-latency demonstrations during presentations.

### 1.2. DOM Element Scaling on Massive Problem Instances
- **Limitation:** Rendering the Master Gantt chart using Plotly creates interactive SVG/WebGL DOM nodes for every flight interval, label, and hover tooltip. For problem instances exceeding 500 flights, browser client rendering latency can reach 1.5–2.5 seconds depending on client GPU hardware.
- **Mitigation in Aeolus:** Page 03 provides dynamic Concourse filters (e.g. Concourse T, Concourse A, Remote) allowing users to filter the visual Gantt timeline to specific airport zones, keeping DOM elements well under the performance threshold while preserving full data integrity in the tabular exports.

---

## 2. Headless Verification vs Human Visual Acceptance

### 2.1. The Boundary of Headless Testing (`AppTest`)
Automated test suites utilizing Streamlit's official testing framework (`streamlit.testing.v1.AppTest`) perform authoritative functional verification:
1. Every page module imports and executes without throwing Python exceptions.
2. Every UI component (tabs, columns, metric cards, Plotly charts, dataframes, buttons, markdown blocks) is properly populated in memory.
3. State mutations, scenario switching, and parameter modifications trigger correct reactive cache invalidations.

However, automated headless testing **cannot** evaluate:
- The human aesthetic quality of font kerning and typographic rendering.
- Color contrast legibility under conference room ambient lighting or substandard projector hardware.
- Subtle horizontal overflow artifacts on legacy 4:3 projector ratios (1024×768).

### 2.2. Declaration of Inspection Status
In adherence to scientific honesty:
- **Headless Testing Status:** **100% PASSED** (All 10 AppTest scenarios and 359 unit/integration tests pass).
- **Human Visual Status:** **PARTIAL / VISUAL_QA_PENDING** (A comprehensive 40-point visual acceptance checklist is provided in `docs/dashboard/redesign/UI-R08/05_visual_acceptance.md` for human verification prior to defense).

---

## 3. Large-Scale Solver Timeouts & Degraded Execution

### 3.1. CP-SAT at $N=1,500$ Flights
- As proven in Gate G5, exact constraint programming via CP-SAT achieves proven global optimality for small and medium instances ($N \le 300$). However, on mega-scale instances ($N = 1,500$), CP-SAT exceeds its 30-second time budget.
- **Scientific Integrity Guard:** The Optimization Lab does not hide or fake this outcome. The scalability curve explicitly marks the $N=1500$ data point with a dashed marker and the clear label: `UNKNOWN (Hết giờ 30s)`. The deterministic greedy heuristic remains available as a feasible fallback.

### 3.2. Missing Optional Model Artifacts
- In deployment environments where heavy model weights (e.g., local SHAP TreeExplainer trees) are omitted to conserve storage, Page 02 handles this via graceful degradation.
- The preflight banner informs the user that feature explanations are temporarily offline, while core delay predictions and turnaround dynamics continue functioning without interruption.

---

## 4. Operational Recommendations for Thesis Defense

1. **Preset Scenarios:** Utilize `SCEN_P09_CANONICAL_120` or `SCEN_P07_DUAL_CORE_30` during the live defense to ensure instant sub-second response times.
2. **Display Resolution:** Configure the presentation laptop display to 1920×1080 (16:9) or 1366×768. The dashboard layout has been calibrated to eliminate horizontal scrolling at these standard resolutions.
3. **Mode Selection:** Present initial results using **Presentation Mode** for visual clarity; switch to **Research Mode** if the thesis committee requests examination of TreeSHAP features or mathematical formulation parameters.
