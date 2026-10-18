# Page 05 Specification — Robustness Lab (Kiểm thử Bền vững Monte Carlo)

**Document ID:** `AEOLUS-P10-A-PAGE-05`  
**Phase:** P10-A (UI/UX Design Specification & Design Freeze)  
**Status:** DESIGN FROZEN  
**Target View:** Page 5 (`05_robustness_lab.py`)  

---

## 1. Executive Summary & Page Purpose

The **Robustness Lab** demonstrates the resilience of gate assignment strategies under real-world operational uncertainty. Using precomputed results from a comprehensive **500-scenario Monte Carlo stress simulation** (Phase P09), this page evaluates three distinct operational paradigms:
- **Mode A (Kế hoạch Cố định - Fixed Plan):** The nominal schedule is frozen; delayed flights occupy gates as they arrive without dynamic reassignment.
- **Mode B (Tái phân bổ Tức thời - Reactive Recourse):** Conflicts caused by arrival delays trigger minimal tactical greedy gate swaps.
- **Mode C (Chuẩn Greedy Thực tế - Realized Greedy Oracle Baseline):** A re-solve using greedy heuristics given perfect foresight of realized delays.

---

## 2. Page Wireframe & Layout Architecture (Desktop 1920 × 1080)

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ [🛡️] ROBUSTNESS LAB — ĐÁNH GIÁ ĐỘ BỀN VỮNG VẬN HÀNH QUA 500 KỊCH BẢN MONTE CARLO         [ATL 2023]    │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ THÔNG ĐIỆP HỌC THUẬT: MODE C = "PERFECT FORESIGHT — NON-DEPLOYABLE (CHUẨN GREEDY THỰC TẾ)"             │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ ┌──────────────────────────────────────────────────────────┐ ┌─────────────────────────────────────────┐ │
│ │ KẾT QUẢ TỔNG HỢP 500 KỊCH BẢN BIẾN ĐỘNG (STRESS MATRIX)   │ │ GIẢI THÍCH CHỈ SỐ KHOA HỌC (D1 & D2)    │ │
│ │                                                          │ │                                         │ │
│ │ ■ Mode A (Cố định):                                      │ │ ⚠️ Lưu ý D1 (Khả thi vs Va chạm):       │ │
│ │   • Tỷ lệ va chạm cổng thực tế: 74.8% (374/500 kịch bản) │ │   Tỷ lệ khả thi tĩnh là 0.0% vì 100%    │ │
│ │   • Tỷ lệ vi phạm lịch tĩnh: 100.0% (Lệch giờ bay kế hoạch)│   chuyến bay bị trễ giờ đến ban đầu.    │ │
│ │   • Chi phí trung bình: 22,130.0 (Phạt xung đột cực nặng)│   Tuy nhiên, chỉ 74.8% thực sự va chạm    │ │
│ │                                                          │ │   không gian-thời gian trên cùng 1 cổng.│ │
│ │ ■ Mode B (Tái phân bổ Recourse):                         │ │                                         │ │
│ │   • Tỷ lệ giải tỏa xung đột: 100.0% (0 va chạm tồn dư)   │ │ ℹ️ Lưu ý D2 (Mode B vs C Tương đương):   │ │
│ │   • Số lần đổi cổng trung bình: 2.556 chuyến / kịch bản  │ │   Do kế hoạch ban đầu chuẩn 120 chuyến  │ │
│ │   • Chi phí trung bình: 130.73 [🛡️ BỀN VỮNG CAO]         │ │   không có đổi cổng, cả Mode B và C đều │ │
│ │                                                          │ │   dùng Greedy nên đạt kết quả đồng nhất │ │
│ │ ■ Mode C (Oracle Baseline - Tham lam Thực tế):           │ │   (Mean Diff = 0.0, p-value = 1.0).     │ │
│ │   • Chi phí trung bình: 130.73 (Tương đương Mode B)      │ │                                         │ │
│ └──────────────────────────────────────────────────────────┘ └─────────────────────────────────────────┘ │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ ┌──────────────────────────────────────────────────────────┐ ┌─────────────────────────────────────────┐ │
│ │ ĐỒ THỊ HÀM PHÂN BỐ TÍCH LŨY CHI PHÍ (CDF - CHART-13)     │ │ PHÂN BỐ SỐ LẦN ĐỔI CỔNG (BOXPLOT - C-14)│ │
│ │ Xác suất P(Chi phí <= X)                                 │ │ Số chuyến đổi cổng                      │ │
│ │ 1.0 ┤      ╭──────────────────────── Mode B & Mode C     │ │  8 ┤              ┬                     │ │
│ │ 0.8 ┤     ╭╯                                             │ │  6 ┤              │ (Kịch bản cực đoan) │ │
│ │ 0.6 ┤    ╭╯                                              │ │  4 ┤          ┌───┴───┐                 │ │
│ │ 0.4 ┤   ╭╯                                               │ │  2 ┤ ───●───  │  TB=2.5│                 │ │
│ │ 0.2 ┤  ╭╯                    Mode A (Kéo dài > 20,000)   │ │  0 ┴──────────┴───┬───┴─────────────    │ │
│ │ 0.0 ┴──┴───────┴───────┴───────┴───────┴───────┴───────  │ │      Mode A     Mode B   Mode C         │ │
│ │     0         50      100     150     200     250 (Chi phí)│ │      (0 đổi)  (2.556)  (2.556)        │ │
│ └──────────────────────────────────────────────────────────┘ └─────────────────────────────────────────┘ │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ CHI TIẾT TỪNG KỊCH BẢN (SCENARIO DRILL-DOWN INSPECTOR)                                                 │
│ [ Chọn Kịch bản kiểm tra: ( ───●──────────────────────── ) #042 / 500 ]                                │
│ Kịch bản #042: Độ trễ trung bình = +24.5 min | Tàu bay trễ nặng nhất: DL1024 (+65m)                   │
│ • Mode A: Gặp 2 va chạm tại Cổng A04 & T02 (Chi phí phạt = 22,140.0)                                   │
│ • Mode B: Tự động đổi 4 chuyến sang cổng lân cận (A05, T03) ──► Chi phí = 140.0, 0 va chạm             │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Detailed Component Inventory & Data Contracts

| Component ID | Component Name | Data Source | Primary Fields | Presentation Visibility | Research Mode Extra |
| :--- | :--- | :--- | :--- | :---: | :--- |
| **C5-SUMMARY** | Tri-Mode Summary Matrix | `statistical_summary.json` | `mean_cost`, `conflict_prob`, `feasibility_rate` | Visible | Displays 95% Confidence Intervals & Standard Deviations |
| **C5-WARN-D1** | Finding D1 Clarification Card | Hardcoded Math Specs | Static explanation | Visible | Mathematical formulation of timeline vs spatial overlap |
| **C5-WARN-D2** | Finding D2 Quarantine Card | Hardcoded Math Specs | Static explanation | Visible | Greedy re-solve equivalence and thesis defense advice |
| **C5-CHART-13**| Empirical CDF Plot | `fixed_plan_results.csv`, `recourse_results.csv` | `objective_value`, empirical percentiles | Visible | High-density cumulative probability curve |
| **C5-CHART-14**| Reassignment Box Plot | `recourse_results.csv`, `oracle_results.csv` | `reassignment_count` (Q1, Median, Q3, Whiskers) | Visible | Outlier scenario points overlay |
| **C5-PAIRED** | Paired Comparison Card | `paired_comparison.csv` | $t$-stat ($0.0$), $p$-value ($1.0$), Mean Diff ($0.0$) | Visible | Full statistical hypothesis testing report |
| **C5-SLIDER** | Scenario Drill-Down Slider | `scenario_index.csv` | `scenario_id` ($1$ to $500$) | Visible | Interactive flight reassignment trace table |

---

## 4. Empirical Cumulative Distribution Function (CHART-13 Specification)

- **Plotly Type:** Empirical Cumulative Distribution Function (`go.Scatter` with `step="hv"`).
- **X-Axis:** Objective Decision Cost ($J_{\text{decision}}$, Range $[0, 300]$ for Modes B & C; inset note for Mode A extending to $25,000$).
- **Y-Axis:** Cumulative Probability $P(J \le x)$ ($0.0$ to $1.0$).
- **Traces:**
  - `Mode B (Recourse)`: Solid Aerodrome Cyan line (`#47C5C0`). Reaches $1.0$ at cost $250.0$.
  - `Mode C (Oracle Baseline)`: Dotted Clearance Green line (`#34C759`). Perfectly overlays Mode B.
  - `Mode A (Fixed Plan)`: Broken Alert Red marker indicating that $100\%$ of mass is situated at $J > 2,000$ due to heavy conflict penalties ($w_{\text{conflict}} = 1000.0$).
- **Hover Payload:**
  ```
  Chế độ: Mode B (Recourse)
  Chi phí quyết định (X): 140.0
  Tỷ lệ kịch bản có chi phí <= 140: 82.4% (412/500 kịch bản)
  ```

---

## 5. Scenario Drill-Down Interaction (Component C5-SLIDER)
- **Interaction:** A horizontal slider allows the user to drag across all 500 evaluated scenarios.
- **Immediate Response (< 15 ms):**
  - Renders a compact summary of that specific scenario perturbation.
  - Lists the exact flights that suffered severe arrival delays.
  - Displays the specific tactical gate reassignment moves executed by Mode B to resolve overlaps.
- **Default Scenario:** Scenario `#42` (a representative high-stress peak wave with 4 tactical reassignments and zero remote stand usage).
