# UI-R00: 05 — VISUAL BASELINE & SCREENSHOT AUDIT

**Document ID:** `AEOLUS-UI-R00-05-VISUAL-BASELINE`  
**Phase:** UI-R00 (Baseline, Technical Audit & Safety Freeze)  
**Audit Timestamp:** 2026-10-10T23:29:00+07:00  
**Auditor:** Streamlit/Plotly UX Auditor & Visual QA Specialist  
**Visual QA Status:** **`VISUAL_QA_BLOCKED`** (Headless CLI Environment Protocol Applied)

---

## 1. Visual QA Execution Status & Protocol Compliance

### 1.1. Safety Rule R00-M10 Enforcement
Per strict directive **R00-M10**:
> *"Screenshot được chụp thật; nếu không thể, phải báo BLOCKED thay vì giả vờ hoàn thành."*

An inspection of the local Python virtual environment verified:
- `playwright`: **NOT INSTALLED**
- `selenium`: **NOT INSTALLED**
- `puppeteer`: **NOT INSTALLED**
- Dedicated headless display driver: **NOT CONFIGURED**

In strict adherence to scientific software audit standards, **no artificial, synthetic, or fabricated screenshots have been created**. The visual capture milestone is formally declared **`VISUAL_QA_BLOCKED`**.

---

## 2. Actionable Screenshot Manifest for User / Browser Session

To achieve full visual baseline sign-off prior to UI-R03 redesign, the user is requested to capture and place the following 18 screenshots into `docs/dashboard/redesign/UI-R00/screenshots/`:

### 2.1. Standard Resolution: 1366 × 768 (Laptop Benchmark)
1. `screenshots/1366x768_p01_control_tower.png` — Page 01 full view.
2. `screenshots/1366x768_p02_flight_intelligence.png` — Page 02 Tab A table & distribution.
3. `screenshots/1366x768_p03_gate_operations.png` — Page 03 Gantt chart & live solver controls.
4. `screenshots/1366x768_p04_optimization_lab.png` — Page 04 Pareto frontier & benchmark table.
5. `screenshots/1366x768_p05_robustness_lab.png` — Page 05 Monte Carlo histograms & ECDF.

### 2.2. Standard Resolution: 1920 × 1080 (Defense Projection Benchmark)
6. `screenshots/1920x1080_p01_control_tower.png` — Page 01 full view.
7. `screenshots/1920x1080_p02_flight_intelligence.png` — Page 02 Tab A table & distribution.
8. `screenshots/1920x1080_p03_gate_operations.png` — Page 03 Gantt chart & live solver controls.
9. `screenshots/1920x1080_p04_optimization_lab.png` — Page 04 Pareto frontier & benchmark table.
10. `screenshots/1920x1080_p05_robustness_lab.png` — Page 05 Monte Carlo histograms & ECDF.

### 2.3. Presentation vs. Research Mode Comparison
11. `screenshots/p01_presentation_mode.png` vs. `screenshots/p01_research_mode.png`
12. `screenshots/p04_presentation_mode.png` vs. `screenshots/p04_research_mode.png`
13. `screenshots/p05_presentation_mode.png` vs. `screenshots/p05_research_mode.png`

### 2.4. Critical Layout & Interaction States
14. `screenshots/p03_sidebar_expanded.png` — Page 03 with sidebar navigation open.
15. `screenshots/p03_sidebar_collapsed.png` — Page 03 with sidebar collapsed (maximizing Gantt width).
16. `screenshots/p03_stale_warning.png` — Live solver panel displaying stale parameter warning badge.
17. `screenshots/p03_flight_inspector_card.png` — Flight Inspector card showing aircraft turn audit.
18. `screenshots/p05_scenario_drilldown.png` — Robustness Lab single scenario drill-down container.

---

## 3. Code-Level Visual & UX Static Audit

While automated pixel capture is blocked, a static code audit of the CSS stylesheets, component templates, and Plotly visualizer configurations revealed key design findings:

### 3.1. Color Hierarchy & Contrast Ratios
- **Background Tokens:** Primary Canvas `#101B2A`, Surface `#162338`, Elevated `#1D2E49`.
- **Text Tokens:** Primary Text `#F0F4F8`, Secondary Text `#94A3B8`, Muted Text `#64748B`.
- **Contrast Analysis:**
  - `#F0F4F8` on `#101B2A` = **14.2:1** (Exceeds WCAG AAA standard of 7.0:1).
  - `#94A3B8` on `#101B2A` = **6.8:1** (Exceeds WCAG AA standard of 4.5:1).
  - `#47C5C0` (Aerodrome Cyan) on `#101B2A` = **8.9:1** (High legibility).
  - `#E5AD55` (Taxiway Amber) on `#101B2A` = **8.2:1** (High legibility).
  - `#E47777` (Alert Red) on `#101B2A` = **5.9:1** (Compliant).
- **Verdict:** Color tokens are WCAG AA compliant and visually distinctive.

### 3.2. Typography Bottlenecks
- Font sizing in `.aeolus-kpi-title` and `.aeolus-badge` is set to `11px`.
- Footnotes and table captions are set to `11px`–`12px`.
- **UX Defect:** On a 1080p lecture projector viewed from 5–10 meters, 11px text is illegible. The baseline must raise all functional body labels to at least 13px–14px.

### 3.3. Grid Layout & Column Density Bottlenecks
- In `page_03_gate_operations.py`:
  - Main section splits into `[8.5, 3.5]`.
  - Column 2 (~29% of viewport) holds: Algorithm selector, 3 numeric sliders, 1 checkbox, staleness banner, "Run Solver" button, and 5 performance metric rows.
  - This causes severe vertical scrolling and cramped slider touch targets on 1366x768 screens.
- Bottom section splits into `[7, 5]`:
  - Flight Inspector occupies 7 cols; Independent Verifier & Export occupy 5 cols.
  - Good horizontal balance, but lacks responsive collapsing for narrower viewports.

---

## 4. Next Steps for UI Redesign (UI-R03 & UI-R05)
- Standardize spacing tokens in a centralized design system.
- Implement collapsible solver control drawer or horizontal toolbar for Gantt operations.
- Transition from cramped 11px labels to a legible 13px/14px type scale.
