# AEOLUS DASHBOARD — UI-R07 VISUAL REVIEW & QA STATUS
**Phase**: UI-R07 v2.0  
**Current Status**: `VISUAL_QA_PENDING` (Automated & Headless Tests 100% Passed)  

---

## 1. Honest Visual QA Declaration

In accordance with Aeolus Engineering Safety and Honesty Protocols:
- All data models, validation invariants, Plotly layout objects, DataFrame transforms, and Streamlit component structures have been rigorously validated via **35 automated headless tests**.
- However, visual verification through an active desktop browser window is flagged as **`VISUAL_QA_PENDING`** until human reviewer inspection or visual regression snapshotting.
- No subjective claims of "perfect visual design" are asserted without human sign-off.

---

## 2. Visual QA Manual Inspection Checklist

When running the application via `streamlit run dashboard/app.py` and navigating to Page 05:

### [ ] 1. Solver Selector & Observation Identity Banner
- [ ] Selector dropdown displays `CPSat` (Default), `Greedy`, `Hybrid`.
- [ ] Changing selector updates the observation banner indicating 500 scenarios × 3 solvers = 1,500 evaluations.
- [ ] No chart or metric flashes or takes more than 50 ms to update.

### [ ] 2. Protocol Definition Cards
- [ ] Mode A card has red top border (`#E47777`), displaying 0.0% static feasibility and 74.8% physical conflict.
- [ ] Mode B card has green top border (`#34C759`), displaying 100.0% operational feasibility.
- [ ] Mode C card has cyan top border (`#00D2FF`) with a prominent red badge: `NON-DEPLOYABLE (GREEDY BENCHMARK)`.

### [ ] 3. Executive Robustness Scorecards
- [ ] Mode A Cost: ~1469.2 pts (Status: error/red).
- [ ] Mode B Cost: ~130.7 pts (Status: success/green).
- [ ] Mean Reassignments: 2.56 turns (Status: info/cyan).
- [ ] Evaluated Scenarios: 500 / 500, Failed: 0 (Status: success/green).

### [ ] 4. Presentation vs Research Mode Behavior
- [ ] When Research Mode toggle is OFF:
  - [ ] Displays a single, clean histogram (`create_mc_cost_distribution_figure`).
  - [ ] Concise scientific summary callout is visible.
  - [ ] Research tabs and detailed export buttons are cleanly hidden.
- [ ] When Research Mode toggle is ON:
  - [ ] All 5 structured tabs appear (`📊 Phân phối`, `📈 Hành động & Hội tụ`, `⚖️ Phân tích Cặp`, `🔍 Truy vết`, `⚠️ Sổ tay Cảnh báo`).
  - [ ] Tab 1: Histogram and ECDF appear side-by-side without overflowing.
  - [ ] Tab 2: Boxplot and Convergence trace render cleanly.
  - [ ] Tab 3: CRN paired difference table renders with $p$-value and $t$-statistic.
  - [ ] Tab 4: Dynamic scenario dropdown displays all 500 scenario IDs (`MC500_S0000` to `MC500_S0499`).
  - [ ] Tab 5: Sổ tay Cảnh báo Khoa học details Findings D1 and D2.
  - [ ] Export buttons allow downloading CSV and JSON manifests.

### [ ] 5. Research Inspector Drawer
- [ ] Expands to show 5 tabs.
- [ ] Verifier, Leakage, Holdout, and Diagnostics default to `NOT_CHECKED`.
- [ ] No local Windows drive letters (`D:\...`, `C:\...`) or user directories are visible in output payloads.
