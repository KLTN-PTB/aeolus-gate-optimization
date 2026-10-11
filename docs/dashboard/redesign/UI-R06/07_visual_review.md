# AEOLUS DASHBOARD — UI-R06 VISUAL REVIEW & QA STATUS
**Phase**: UI-R06 v2.0  
**Current Status**: `VISUAL_QA_PENDING` (Automated & Headless Tests 100% Passed)  

---

## 1. Honest Visual QA Declaration

In accordance with Aeolus Engineering Safety and Honesty Protocols:
- All data models, validation invariants, Plotly layout objects, DataFrame transforms, and Streamlit component structures have been rigorously validated via **28 automated headless tests**.
- However, visual verification through an active desktop browser window is flagged as **`VISUAL_QA_PENDING`** until human reviewer inspection or visual regression snapshotting.
- No subjective claims of "perfect visual design" are asserted without human sign-off.

---

## 2. Visual QA Manual Inspection Checklist

When running the dashboard via `streamlit run dashboard/app.py`:

### [ ] 1. Workload Selector & Executive Header
- [ ] Workload selector dropdown correctly shows all 5 benchmark tiers (`SCEN_TIER_A_10F_3G` to `SCEN_TIER_B_300F_50G`).
- [ ] Switching between workloads immediately updates the executive summary card with turn count, gate count, and repetition counts.
- [ ] Fairness Assurance banner is clearly visible with cyan aviation border and lock icon.

### [ ] 2. Solver Scorecard Table
- [ ] All 5 solver variants appear with proper mathematical statuses (`TỐI ƯU TUYỆT ĐỐI` for CP-SAT when optimal, `KHẢ THI` for heuristics).
- [ ] No standalone Greedy or SA solver displays a false claim of proven global optimality.
- [ ] Objectives are displayed with 2 decimal places (`pts`), or `N/A` if undefined.
- [ ] Runtimes are displayed in milliseconds (`ms`) with proper formatting.

### [ ] 3. Pareto Frontier Chart (Cost vs Runtime)
- [ ] X-axis uses a clean logarithmic scale (`log`) with label "Thời gian chạy (ms, Log Scale)".
- [ ] Y-axis has label "Chi phí Mục tiêu Quyết định (Decision Cost)".
- [ ] Dashed line connects **only true non-dominated points** (Pareto efficient).
- [ ] Dominated points appear as isolated scatter dots above the curve.
- [ ] No unhandled `None` or `NaN` points distort the chart axes.

### [ ] 4. Runtime Breakdown Stacked Bar Chart
- [ ] Stacked bars cleanly partition into Model Build (Indigo), Search (Cyan), and Validation (Green).
- [ ] Hover tooltips report precise millisecond values for each execution phase.

### [ ] 5. Mega-Hub Scalability Curve & Formulation Comparison
- [ ] Curve from $N=100$ to $N=1,500$ flights correctly displays execution time trajectory.
- [ ] $N=1,500$ point displays a hollow red diamond or distinct marker indicating `UNKNOWN (TIMEOUT)`.
- [ ] Dashed line indicates the 300-second wall-clock time limit.
- [ ] Formulation comparison chart cleanly contrasts Dense Pairwise ($F_0$) vs Sparse Interval ($F_2$).

### [ ] 6. Research Inspector & Provenance Card
- [ ] Expandable Research Inspector reveals raw filtered benchmark records.
- [ ] SHA-256 provenance card renders artifact path, row count (95), and validation timestamp.
