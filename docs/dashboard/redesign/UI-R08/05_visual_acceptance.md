# UI-R08 Deliverable 05: Visual Acceptance & UI Rehearsal Protocol

**Audit Date:** 2026-10-11  
**Auditor:** Principal UX Designer & Scientific Visual Acceptance Specialist  
**Headless Verification Status:** **100% PASSED** (10 / 10 AppTest page-mode scenarios executed cleanly)  
**Human Browser Verification Status:** **PARTIAL / VISUAL_QA_PENDING** (Documented checklist prepared for live browser inspection)

---

## 1. Visual Verification Declaration

### 1.1. Methodological Integrity Notice
In automated development environments without an active human visual rendering viewport, automated headless suites (`streamlit.testing.v1.AppTest`) verify that:
1. All page scripts execute to completion.
2. All widgets, columns, tabs, charts, metrics, and markdown blocks are created.
3. Zero unhandled exceptions or syntax errors occur.

However, physical visual attributes—such as aesthetic font rendering, exact pixel spacing on diverse projector resolutions, color contrast under ambient conference lighting, and human readability—require live human observation in a web browser. We transparently declare the status as **`PARTIAL / VISUAL_QA_PENDING`** and provide the complete 40-point inspection protocol below.

---

## 2. 40-Point Live Visual Acceptance Checklist

### 2.1. Page 01: Control Tower (Checks 01–08)
- [ ] **V-01:** Context header displays scenario name, active hub ("ATL"), flight count ("120"), and gate count ("25") cleanly without text overflow.
- [ ] **V-02:** Provenance badge displays `BTS_OTP_2023_CURATED` in subdued slate blue tag.
- [ ] **V-03:** Four KPI cards (Flights, Active Gates, Peak Concourse, Solver Health) align evenly in a 4-column horizontal layout.
- [ ] **V-04:** Inbound Delay Wave histogram renders with dual colors (on-time vs delayed flights) and readable axis labels.
- [ ] **V-05:** Concourse Gate Utilization chart displays horizontal bars comparing Concourse T, A, and Remote occupancy.
- [ ] **V-06:** Mode toggle in sidebar seamlessly switches between Presentation Mode (compact) and Research Mode (extended).
- [ ] **V-07:** Live solving status badge reflects unrun state on fresh launch without showing premature "OPTIMAL" badge.
- [ ] **V-08:** Scenario switcher dropdown updates all KPIs and charts within 500ms without page flicker.

### 2.2. Page 02: Dual-Core Flight Intelligence (Checks 09–16)
- [ ] **V-09:** Tab A (Dự báo Đến & Đi) displays dual-core prediction distributions for inbound and outbound flights.
- [ ] **V-10:** Airline carrier distribution displays genuine carriers (Delta, United, Southwest) without dummy fallback rows.
- [ ] **V-11:** Tab B (Động lực học Quay vòng) renders aircraft turn pairing timeline with clean title (no raw `CHART-03` token).
- [ ] **V-12:** Aircraft turn chart visually illustrates 45-min minimum technical dwell, slack absorption, and 15-min buffer clearance.
- [ ] **V-13:** Cross-midnight turnaround flights display clock times seamlessly (e.g. 23:20 -> 01:00 (+1)) without negative dwell bars.
- [ ] **V-14:** Tab C (Giải thích Mô hình TreeSHAP) renders global feature importance horizontal bar chart.
- [ ] **V-15:** Feature importance displays legitimate operational variables (`origin_delay`, `scheduled_dwell`, `route_distance`).
- [ ] **V-16:** Research Inspector expander displays model checksums, training sample sizes, and anti-leakage audit confirmation.

### 2.3. Page 03: Gate Operations & Master Gantt (Checks 17–24)
- [ ] **V-17:** Master Gantt chart displays gate inventory along Y-axis in natural ascending order (Concourse T, A, Remote, Apron).
- [ ] **V-18:** Timeline intervals accurately show half-open occupancy $[start, release)$ including the 15-minute separation buffer.
- [ ] **V-19:** Apron overflow stands (`APRON_*`) are color-coded in amber/red and grouped under `OVERFLOW`, never Concourse A.
- [ ] **V-20:** Finite remote stands display pooled capacity and highlight simultaneous occupancy without visual overlapping.
- [ ] **V-21:** Concourse filter checkboxes display dynamic gate counts (e.g. "Concourse T (10)", "Concourse A (15)").
- [ ] **V-22:** "Chạy Phân Cổng CP-SAT" button requires explicit click; zero unsolicited solves occur upon page entry.
- [ ] **V-23:** Independent verifier badge shows `XÁC MINH HỢP LỆ (VERIFIED)` with physical conflict count ($0$ for optimal solutions).
- [ ] **V-24:** Flight Inspector drawer opens smoothly upon selecting a flight, detailing carrier, tail number, and gate release timestamp.

### 2.4. Page 04: Optimization Lab (Checks 25–32)
- [ ] **V-25:** Multi-solver comparison table displays Greedy, CP-SAT, SA, and Hybrid metrics side-by-side with identical workload sizes.
- [ ] **V-26:** Objective value is clearly distinguished into Decision Cost ($J_{\text{decision}}$) and Reporting Cost ($J_{\text{reporting}}$).
- [ ] **V-27:** Solver status badges show `OPTIMAL (PROVEN)` in emerald green for CP-SAT and `FEASIBLE (HEURISTIC)` in blue for Greedy/SA.
- [ ] **V-28:** Pareto Frontier scatter plot plots Objective Value against Solve Time with clearly labeled solver points.
- [ ] **V-29:** Runtime breakdown stacked chart illustrates model setup, presolve, search, and validation times.
- [ ] **V-30:** CP-SAT Scalability Curve plots flight count up to 1,500 flights.
- [ ] **V-31:** $N=1500$ point displays dashed marker and explicit annotation: `UNKNOWN (Hết giờ 30s)`.
- [ ] **V-32:** Attempting to rank incompatible scenarios displays an amber educational warning rather than an unhandled traceback.

### 2.5. Page 05: Robustness Lab & Monte Carlo (Checks 33–37)
- [ ] **V-33:** Robustness Lab is organized into 5 intuitive tabs (Tổng quan, Phân phối, Rủi ro Đuôi, So sánh Cặp, Thanh tra Nghiên cứu).
- [ ] **V-34:** Mode A violin plot highlights 74.8% conflict rate under fixed schedules with explanatory note on recourse necessity.
- [ ] **V-35:** Mode B vs Mode A comparison demonstrates elimination of gate conflicts under dynamic recourse.
- [ ] **V-36:** Tail Risk chart clearly plots both $p95$ and $CVaR_{95}$, demonstrating $CVaR_{95} \ge p95$.
- [ ] **V-37:** Mode C Oracle section carries bold callout declaring it a non-deployable perfect-foresight research reference.

### 2.6. System-Wide Accessibility, Typography & Performance (Checks 38–40)
- [ ] **V-38:** All body text is rendered at $\ge 13$px with high contrast against the `#0B0F19` dark aviation background (WCAG AA).
- [ ] **V-39:** Vietnamese diacritics render crisply without missing font glyphs or unicode substitution artifacts (`?` or square boxes).
- [ ] **V-40:** Dashboard resizes responsively between 1366×768 (standard projector) and 1920×1080 (HD display) without horizontal overflow.
