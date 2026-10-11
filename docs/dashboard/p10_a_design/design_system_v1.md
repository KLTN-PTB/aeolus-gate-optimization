# Aeolus Design System Specification (v1.0)

**Document ID:** `AEOLUS-P10-A-DESIGN-SYS-03`  
**Phase:** P10-A (UI/UX Design Specification & Design Freeze)  
**Status:** DESIGN FROZEN  
**Theme:** Professional Aviation Dark Theme  

---

## 1. Executive Summary

This document specifies the visual design tokens, color scales, typographic hierarchy, spatial grid, component states, and accessibility rules for the Aeolus dashboard. It establishes an immersive, high-contrast, professional aviation control aesthetic tailored for academic defense and operations center environments.

---

## 2. Color System & Semantic Tokens

### 2.1. Surface & Background Palette
The application employs an aerospace-grade deep charcoal/navy layered palette to reduce eye fatigue and maximize high-contrast data readability:

| Token Name | Hex Code | Purpose & Application |
| :--- | :--- | :--- |
| `--color-bg-canvas` | `#101B2A` | Primary application canvas and main window background |
| `--color-bg-surface` | `#162338` | Card containers, widget backgrounds, sidebar panel |
| `--color-bg-elevated`| `#1D2E49` | Popovers, tooltips, dialogs, active dropdown items |
| `--color-border-subtle`| `#263B5C` | Default card borders, table dividers, chart grid lines |
| `--color-border-active`| `#3B5780` | Hover states, active tabs, focused input boundaries |

### 2.2. Brand & Semantic Accent Palette

| Semantic Token | Hex Code | Visual Association | Usage in Dashboard |
| :--- | :--- | :--- | :--- |
| `--color-accent-primary` | `#47C5C0` | Aerodrome Cyan | Primary buttons, active tabs, nominal gate bars |
| `--color-accent-glow` | `#00D2FF` | Runway Lighting Cyan | Focus rings, highlight glows, hero KPI values |
| `--color-status-success`| `#34C759` | Clearance Green | On-time flights, verified 0-violation badges, feasible status |
| `--color-status-warning`| `#E5AD55` | Taxiway Caution Amber | Moderate delay ($15\text{--}30$m), tight slack turns, stale state |
| `--color-status-error` | `#E47777` | Runway Alert Red | Severe delay ($>30$m), gate overlap conflicts, infeasible status |
| `--color-apron-remote` | `#A78BFA` | Apron Stand Violet | Remote overflow apron assignments, auxiliary parking stands |

### 2.3. Neutral & Typography Palette

| Token Name | Hex Code | Contrast Ratio vs Canvas | Usage |
| :--- | :--- | :---: | :--- |
| `--color-text-primary` | `#F0F4F8` | **12.4 : 1** (AAA) | Headings, primary metrics, table values |
| `--color-text-secondary`| `#94A3B8` | **6.1 : 1** (AA) | Labels, axis titles, secondary descriptions |
| `--color-text-muted` | `#64748B` | **3.8 : 1** | Watermarks, disabled options, timestamp footers |

### 2.4. Accessibility & Dual-Encoding Policy (Chính sách Trợ năng)
> [!IMPORTANT] Non-Reliance on Color Alone
> Under WCAG 2.1 Level AA, color must NEVER be the sole carrier of critical information. All operational alerts and gate statuses MUST be dual-encoded with distinct icons and explicit textual badges:
> - **Conflict / Collision:** Red color (`#E47777`) + Warning Triangle Icon (`⚠️`) + Text `[XUNG ĐỘT]`.
> - **Optimal / Verified:** Green color (`#34C759`) + Shield Check Icon (`🛡️`) + Text `[HỢP LỆ — 0 LỖI]`.
> - **Remote Apron:** Violet color (`#A78BFA`) + Bus/Apron Icon (`🚌`) + Text `[BÃI ĐỖ TỪ XA]`.
> - **Reassigned Gate:** Cyan outline (`#47C5C0`) + Arrow Swap Icon (`⇄`) + Text `[ĐÃ ĐỔI CỔNG]`.

---

## 3. Typography System

### 3.1. Font Families
- **Primary Interface Font:** `Inter`, `Segoe UI`, `SF Pro Display`, `Roboto`, `system-ui, sans-serif`.
  - Full native support for Vietnamese UTF-8 diacritics (ă, â, đ, ê, ô, ơ, ư and tonal marks).
- **Tabular & Code Font:** `JetBrains Mono`, `Fira Code`, `Consolas`, `monospace`.
  - Applied to all Flight Numbers (`DL1024`), Gate Identifiers (`GATE_A12`), Solvers Times, and Mathematical Expressions.

### 3.2. Type Scale & Hierarchy

| Level | Size (px) | Line Height | Weight | Letter Spacing | Context / Component |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Display Hero** | 28px | 36px | 700 (Bold) | -0.5px | Page Hero Titles, Main System Header |
| **Heading 1** | 22px | 28px | 600 (Semi-bold) | -0.2px | Major Section Headers |
| **Heading 2** | 18px | 24px | 600 (Semi-bold) | 0.0px | Card Headers, Tab Titles |
| **Heading 3** | 15px | 20px | 500 (Medium) | 0.0px | Sub-card labels, Metric Group Titles |
| **Body Large** | 15px | 22px | 400 (Regular) | 0.0px | Explanatory callouts, Research notes |
| **Body Regular**| 14px | 20px | 400 (Regular) | 0.0px | General UI text, descriptions, table cells |
| **Caption / Meta**| 12px | 16px | 400 (Regular) | +0.2px | Timestamps, provenance notes, axis ticks |
| **Monospace Tag**| 12px | 16px | 600 (Semi-bold) | 0.0px | Gate IDs, Flight IDs, Solver Badges |

### 3.3. Numeric & Tabular Formatting Rules
All numbers presented in tables, cards, and charts must enforce `font-variant-numeric: tabular-nums` to prevent layout jitter:
- **Signed Delays:** Always display sign: `+24.5 min`, `-4.0 min`, `0.0 min`.
- **Probabilities & Rates:** Display with 1 decimal place: `84.2%`, `74.8%`, `0.0%`.
- **Objective Values & Costs:** Display with 1 decimal place: `130.7`, `22,130.0`.
- **Solve Runtimes:** Display in milliseconds if $< 1$s (`65 ms`), or 2 decimals if $\ge 1$s (`1.42 s`).
- **Timestamps:** ISO 24-hour clock format: `08:35`, `14:15` or Local Minutes from Midnight (`515 min`).

---

## 4. Spacing Scale, Grid & Container Architecture

### 4.1. 4px / 8px Baseline Grid
- `--space-1`: 4px (micro-spacing between icon and text)
- `--space-2`: 8px (compact gap between inline tags, padding inside buttons)
- `--space-3`: 12px (form input spacing, compact card margins)
- `--space-4`: 16px (standard card padding, grid row gutter)
- `--space-6`: 24px (section margins, main layout gutter)
- `--space-8`: 32px (major section vertical rhythm)
- `--space-12`: 48px (page bottom breathing room)

### 4.2. Corner Radii & Borders
- `--radius-sm`: `4px` (Status badges, inline tags, tooltips)
- `--radius-md`: `8px` (Standard cards, buttons, text inputs, dropdowns)
- `--radius-lg`: `12px` (Modal dialogues, hero containers, floating drawers)
- `--border-width`: `1px` solid `--color-border-subtle` (expands to `2px` on focus/active)

### 4.3. Standard Container Heights
To prevent jarring layout shifts during data loading:
- **Master Gantt Container:** Fixed minimum height `540px` (accommodates 26 gates + time axis).
- **Distribution / CDF Charts:** Minimum height `380px`.
- **Executive Metric Cards:** Fixed height `115px`.
- **Data Tables:** Scrollable viewport with height `420px`.

---

## 5. Screen Layout & Responsive Breakpoints

### Desktop-First Viewport Specifications
- **Large Presentation Screen (1920 × 1080):** 
  - Full 4-column KPI grid on Page 1.
  - Side-by-side comparative views in Research Mode.
  - Wide 24-hour Gantt timeline canvas.
- **Presentation Laptop (1366 × 768):**
  - 2-column KPI grid on Page 1.
  - Horizontally scrollable Gantt with time-window slider default set to 6-hour morning peak (06:00 to 12:00).
  - Compact sidebar collapsible via Streamlit native toggle.
- **Tablet / Fallback (> 768px):**
  - Single-column stacked cards. Full reading and inspection capabilities.

---

## 6. Plotly Chart Theme Standard (Aviation Dark Figure Template)

All Plotly figures generated by the application must apply the unified `AeolusDarkTemplate`:

```python
AEOLUS_PLOTLY_THEME = {
    "layout": {
        "paper_bgcolor": "#162338",
        "plot_bgcolor": "#101B2A",
        "font": {
            "family": "Inter, Segoe UI, sans-serif",
            "color": "#F0F4F8",
            "size": 12,
        },
        "xaxis": {
            "gridcolor": "#263B5C",
            "linecolor": "#3B5780",
            "zerolinecolor": "#3B5780",
        },
        "yaxis": {
            "gridcolor": "#263B5C",
            "linecolor": "#3B5780",
            "zerolinecolor": "#3B5780",
        },
        "colorway": [
            "#47C5C0",  # Aerodrome Cyan
            "#E5AD55",  # Caution Amber
            "#E47777",  # Alert Red
            "#34C759",  # Clearance Green
            "#A78BFA",  # Stand Violet
            "#00D2FF",  # Runway Cyan
        ],
        "hoverlabel": {
            "bgcolor": "#1D2E49",
            "bordercolor": "#47C5C0",
            "font": {"family": "JetBrains Mono, monospace", "color": "#F0F4F8"},
        },
    }
}
```
