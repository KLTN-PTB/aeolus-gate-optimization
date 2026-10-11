# AEOLUS DASHBOARD — ROBUSTNESS LAB UI/UX REDESIGN SPECIFICATION
**Phase**: UI-R07 v2.0  
**File**: `dashboard/pages/page_05_robustness_lab.py`  

---

## 1. Architectural Layout & Progressive Disclosure

Page 05 has been redesigned with a clean, desktop-first responsive structure supporting two distinct user journeys:

```
[ Context Bar: Active Scenario & MC Evaluated Badge ]
       │
[ Robustness Baseline Solver Selector (CPSat / Greedy / Hybrid) ]
       │
[ Observation Identity Banner (500 Scenarios x 3 Solvers = 1,500 Evaluations) ]
       │
[ 3 Protocol Definition Cards: Mode A (Red) | Mode B (Green) | Mode C (Cyan/Non-deployable) ]
       │
[ 4 Executive Scorecards: Mode A Cost | Mode B Cost | Reassignments | Evaluated Count ]
       │
┌────────────────────────────────────────────────────────┐
│ If Presentation Mode:                                  │
│   • Single Cost Distribution Histogram (Overlay)       │
│   • Core Scientific Takeaway Callout                   │
└────────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────────┐
│ If Research Mode:                                      │
│   • Tab 1: 📊 Phân phối Chi phí & Rủi ro Đuôi (Hist + ECDF) │
│   • Tab 2: 📈 Hành động & Hội tụ (Boxplot + Running Mean)│
│   • Tab 3: ⚖️ Phân tích Cặp & Thống kê (CRN Paired Table)│
│   • Tab 4: 🔍 Truy vết Kịch bản (Dynamic Dropdown)     │
│   • Tab 5: ⚠️ Sổ tay Cảnh báo Khoa học (D1, D2, 2024)   │
│   • Research Mode Export Buttons (CSV / JSON)          │
└────────────────────────────────────────────────────────┘
       │
[ Research Inspector Audit Drawer (NOT_CHECKED Default) ]
```

---

## 2. Dynamic Scenario Drill-Down Architecture

In accordance with Task R07-I:
- **Zero Hardcoded Scenarios**: Eliminated the static 6-element mock list `["MC500_S0000", ...]`.
- **Dynamic Derivation**: Dropdown options derive at runtime directly from `fixed_sub["realization_id"].unique()`, giving access to all 500 actual scenarios.
- **Transparent Disclosure**: Clearly declares `flight_level_assignments_available = False`, preventing fake flight-level Gantt synthesis while reporting complete scenario-level metrics (costs, conflicts, reassignments, realization hash).
