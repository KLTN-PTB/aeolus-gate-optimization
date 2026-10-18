# UI/UX Acceptance Matrix & Verification Criteria

**Document ID:** `AEOLUS-P10-A-ACCEPTANCE-13`  
**Phase:** P10-A (UI/UX Design Specification & Design Freeze)  
**Status:** DESIGN FROZEN  
**Target Milestone:** Quality Assurance & Functional Sign-Off for Phase P10  

---

## 1. Executive Summary

This matrix establishes the authoritative, binary (PASS/FAIL) acceptance criteria governing the implementation of the Aeolus Demonstration Dashboard in Phase P10. Every criterion defines an observable user behavior, an underlying data condition, and a concrete verification method.

---

## 2. Global Navigation & Session State Acceptance Criteria

| ID | Feature / Component | Acceptance Criterion | Verification Method | Status Target |
| :---: | :--- | :--- | :--- | :---: |
| **AC-NAV-01** | Page Transitions | Switching between any of the 5 pages via the sidebar takes $< 300$ ms and preserves `active_solution` in session state. | Manual Navigation Audit | **PASS** |
| **AC-NAV-02** | Mode Switch | Toggling the "Chế độ Nghiên cứu" switch reveals/hides advanced inspect expanders without triggering page reload or losing solver results. | Session State Inspection | **PASS** |
| **AC-NAV-03** | Context Bar Integrity | Global Context Bar displays active hub (`ATL`), scenario ID, total flight count, and solution status badge on all 5 pages. | Visual Regression Check | **PASS** |
| **AC-NAV-04** | Scenario Switching | Selecting `SCEN_2023_PEAK_01` updates flight counts and refreshes all metric cards and Gantt bars without unhandled exceptions. | Dropdown Interaction Test | **PASS** |
| **AC-NAV-05** | Stale State Badge | Modifying any slider in Gate Operations before clicking solve renders an amber badge: `[⚠️ THAM SỐ CHƯA CẬP NHẬT]`. | Slider State Mutation Test | **PASS** |
| **AC-NAV-06** | Error Boundary | In case of a corrupted data record, the failing widget renders an inline warning card while the rest of the page remains fully operable. | Mock Fault Injection | **PASS** |

---

## 3. Design System & Theme Acceptance Criteria

| ID | Feature / Component | Acceptance Criterion | Verification Method | Status Target |
| :---: | :--- | :--- | :--- | :---: |
| **AC-THEME-01**| Background Canvas | Application background is set to `#101B2A` and card surfaces to `#162338`. | CSS Computed Style Check | **PASS** |
| **AC-THEME-02**| Contrast Ratio | All body and metric text adheres to WCAG 2.1 AA contrast ratio ($\ge 4.5:1$ against dark background). | Lighthouse / a11y Audit | **PASS** |
| **AC-THEME-03**| Typography Encoding | Vietnamese diacritics (ă, â, đ, ê, ô, ơ, ư) render cleanly with zero font substitution artifacts or character displacement. | Visual Linguistic Audit | **PASS** |
| **AC-THEME-04**| Tabular Numerals | Numeric values in tables and scorecards enforce `tabular-nums` alignment, preventing horizontal width jitter. | CSS Property Audit | **PASS** |
| **AC-THEME-05**| Dual-Encoding (a11y)| Gate conflict indicators and status cards combine color with text labels and distinct geometric icons. | Monochrome Display Test | **PASS** |
| **AC-THEME-06**| Plotly Dark Palette | All Plotly figures apply `AeolusDarkTemplate` with dark plot canvas and cyan/amber/red colorway. | JSON Layout Inspection | **PASS** |

---

## 4. Page-Specific Functional Acceptance Criteria

### Page 01: Control Tower
| ID | Acceptance Criterion | Verification Method | Status Target |
| :---: | :--- | :--- | :---: |
| **AC-P1-01** | Five metric KPI cards render with non-null values for active scenario. | DOM Inspection | **PASS** |
| **AC-P1-02** | CHART-01 renders 15-minute operational timeline with dual inbound/outbound stacked bars. | Plotly Traces Count | **PASS** |
| **AC-P1-03** | Gate Concourse utilization bars display current percentage load for Concourse T, A, and Remote. | Metric Calculation Check | **PASS** |
| **AC-P1-04** | Turnaround Slack Health card identifies turns with $<5$ min slack as high risk. | Threshold Logic Test | **PASS** |

### Page 02: Flight Intelligence
| ID | Acceptance Criterion | Verification Method | Status Target |
| :---: | :--- | :--- | :---: |
| **AC-P2-01** | Tab A renders sortable table of all 120 flights with signed delay values (e.g., `+24.5 min`). | Data Table Audit | **PASS** |
| **AC-P2-02** | Selecting a flight row in Tab A updates selected flight context in Tab B and Tab C. | State Synchronization Test | **PASS** |
| **AC-P2-03** | Tab B renders aircraft turnaround timeline showing $[T_{\text{arr}}, T_{\text{dep}} + \text{buffer})$ synthesis. | Visual Segment Audit | **PASS** |
| **AC-P2-04** | Tab C renders Global SHAP importance ranking (CHART-05) matching precomputed CSV. | Data Parity Check | **PASS** |
| **AC-P2-05** | Tab C renders Local SHAP waterfall (CHART-06) for verified case studies. | Waterfall Summation Test | **PASS** |
| **AC-P2-06** | Zero actual historical delay labels are displayed in planning mode (Finding D3). | Data Privacy Audit | **PASS** |

### Page 03: Gate Operations (Gantt Chart & Solving)
| ID | Acceptance Criterion | Verification Method | Status Target |
| :---: | :--- | :--- | :---: |
| **AC-P3-01** | Master Gantt (CHART-07) renders all gates on Y-axis grouped by Concourse T, A, and Remote. | Axis Ticks Inspection | **PASS** |
| **AC-P3-02** | Aircraft occupancy intervals strictly follow $[T_{\text{arr}}, T_{\text{dep}} + \text{buffer}_{\text{min}})$. | Mathematical Boundary Audit | **PASS** |
| **AC-P3-03** | 15-minute release buffer is explicitly rendered with hatched pattern without double counting. | Texture & Width Audit | **PASS** |
| **AC-P3-04** | Radio toggle switches seamlessly between Nominal (showing conflicts) and CP-SAT (conflict-free). | View Switch Audit | **PASS** |
| **AC-P3-05** | Clicking `[⚡ TỐI ƯU HÓA NGAY]` triggers backend solver and completes in $< 150$ ms for 120 flights. | Latency Timer Check | **PASS** |
| **AC-P3-06** | Independent Verifier badge confirms `0 Vi phạm` on CP-SAT solution. | Function Call Audit | **PASS** |
| **AC-P3-07** | Concourse multi-select filter dynamically isolates selected concourse gates on the Gantt. | Filter Callback Audit | **PASS** |

### Page 04: Optimization Lab
| ID | Acceptance Criterion | Verification Method | Status Target |
| :---: | :--- | :--- | :---: |
| **AC-P4-01** | Multi-solver table renders comparative rows for Greedy, CP-SAT Sparse, CP-SAT Dense, SA, Hybrid. | Table Integrity Audit | **PASS** |
| **AC-P4-02** | CHART-09 Pareto bubble chart correctly applies logarithmic scale on X-axis (runtime). | Plotly Axis Type Check | **PASS** |
| **AC-P4-03** | CP-SAT formulation card details exact variable count and 21x speedup of sparse interval. | Content Accuracy Check | **PASS** |
| **AC-P4-04** | Mega-hub scalability section renders precomputed 1,500-flight results from P08 without running live. | Static Load Verification | **PASS** |

### Page 05: Robustness Lab
| ID | Acceptance Criterion | Verification Method | Status Target |
| :---: | :--- | :--- | :---: |
| **AC-P5-01** | Tri-mode summary table reports Mode A, Mode B, and Mode C metrics across 500 scenarios. | Data Parity with P09 CSV | **PASS** |
| **AC-P5-02** | Mode C is explicitly labeled `PERFECT FORESIGHT — NON-DEPLOYABLE (Chuẩn Greedy Thực tế)`. | Text Label Audit | **PASS** |
| **AC-P5-03** | Mode A displays both Physical Collision Rate (74.8%) and Static Mismatch (100.0%) (Finding D1). | Metric Display Audit | **PASS** |
| **AC-P5-04** | CHART-13 renders Empirical CDF curves with step function interpolation. | Trace Geometry Audit | **PASS** |
| **AC-P5-05** | Scenario drill-down slider enables interactive inspection across scenario indices 1 to 500. | Slider Event Test | **PASS** |

### Research Inspector
| ID | Acceptance Criterion | Verification Method | Status Target |
| :---: | :--- | :--- | :---: |
| **AC-INSP-01** | Persistent expander at page footer expands/collapses cleanly without page jitter. | UI Interaction Test | **PASS** |
| **AC-INSP-02** | Zero absolute local Windows paths are displayed; all paths sanitized to project roots. | Regex Path Audit | **PASS** |
| **AC-INSP-03** | Copy Manifest button transfers complete valid JSON payload to system clipboard. | Clipboard API Test | **PASS** |
| **AC-INSP-04** | Displays active model hashes, solver seeds (42), and independent verification state. | Data Integrity Audit | **PASS** |

---

## 5. Performance & Resource Budgets

| Metric | Threshold Limit | Measurement Tool | Target Status |
| :--- | :---: | :--- | :---: |
| **Initial App Load (Warm)** | $< 800\text{ ms}$ | Chrome DevTools Network Tab | **PASS** |
| **Page Navigation Latency** | $< 300\text{ ms}$ | Streamlit Rerun Timer | **PASS** |
| **Live CP-SAT Solve (120 Flights)**| $< 150\text{ ms}$ | Python `time.perf_counter()` | **PASS** |
| **Plotly Figure Render** | $< 60\text{ ms}$ | Plotly WebGL/SVG Profiler | **PASS** |
| **Peak Memory Consumption** | $< 350\text{ MB}$ | Python `tracemalloc` / Task Manager | **PASS** |
| **Unhandled UI Exceptions** | **0 Errors** | Streamlit Console Logs | **PASS** |
