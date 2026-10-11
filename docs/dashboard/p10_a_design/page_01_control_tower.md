# Page 01 Specification — Control Tower (Tổng quan Điều hành)

**Document ID:** `AEOLUS-P10-A-PAGE-01`  
**Phase:** P10-A (UI/UX Design Specification & Design Freeze)  
**Status:** DESIGN FROZEN  
**Target View:** Page 1 (`01_control_tower.py`)  

---

## 1. Executive Summary & Page Purpose

The **Control Tower** serves as the executive operational bridgehead. It delivers immediate, high-level situational awareness of airport hub dynamics at Atlanta (ATL). It summarizes incoming delay waves from the Machine Learning dual-core models, evaluates the physical gate infrastructure buffer, and showcases the high-level impact of the CP-SAT gate optimization engine.

---

## 2. Page Wireframe & Layout Architecture (Desktop 1920 × 1080)

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ [✈] TRUNG TÂM ĐIỀU HÀNH AEOLUS — HARTSFIELD-JACKSON ATLANTA (ATL)                      [Chế độ: BẢO VỆ] │
│ Kịch bản: [ SCEN_P09_CANONICAL_120 (Sáng cao điểm 120 chuyến) ▼ ]   Trạng thái: [● TỐI ƯU TUYỆT ĐỐI]    │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐ ┌────────────────┐ │
│ │ TỔNG CHUYẾN BAY  │ │ TRỄ ĐẾN DỰ BÁO   │ │ XUNG ĐỘT TĨNH    │ │ TỐI ƯU CP-SAT    │ │ CỔNG ĐỖ TỪ XA  │ │
│ │ 120 Chuyến       │ │ +18.4 min TB     │ │ 13 Cặp xung đột  │ │ 0 Xung đột       │ │ 0 Cổng sử dụng │ │
│ │ 60 Cặp quay vòng │ │ 38.2% trễ >15m   │ │ [⚠️ NGUY CƠ CAO] │ │ [🛡️ ĐÃ GIẢI TỎA] │ │ [100% Cổng ống]│ │
│ └──────────────────┘ └──────────────────┘ └──────────────────┘ └──────────────────┘ └────────────────┘ │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ ┌──────────────────────────────────────────────────────────┐ ┌─────────────────────────────────────────┐ │
│ │ BIỂU ĐỒ HOẠT ĐỘNG KHAI THÁC THEO KHUNG GIỜ (CHART-01)    │ │ SỨC CHỨA CỔNG & KHU VỰC ĐỖ (CHART-08)   │ │
│ │                                                          │ │                                         │ │
│ │ Số chuyến [ Cất cánh (Out) ■ | Hạ cánh (In) ■ ]          │ │ Concourse T: [██████████░░] 80% (8/10)  │ │
│ │ 25 ┤       ╭─╮                                           │ │ Concourse A: [████████████] 100% (15/15)│ │
│ │ 15 ┤   ╭─╮ │ │ ╭─╮                                       │ │ Remote Apron: [░░░░░░░░░░░░] 0% (0/1)   │ │
│ │  5 ┤ ╭─╯ ╰─╯ ╰─╯ ╰─╮                                     │ │                                         │ │
│ │  0 ┴─┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───            │ │ Cảnh báo áp lực: Concourse A chạm trần  │ │
│ │   06:00 07:00 08:00 09:00 10:00 11:00 12:00 (Giờ địa phương)│ └─────────────────────────────────────────┘ │
│ └──────────────────────────────────────────────────────────┘                                           │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ ┌──────────────────────────────────────────────────────────┐ ┌─────────────────────────────────────────┐ │
│ │ PHÂN BỔ SLACK QUAY VÒNG TÀU BAY (TURNAROUND SLACK HEALTH)│ │ HÀNH ĐỘNG NHANH & ĐIỀU HƯỚNG TÁC NGHIỆP  │ │
│ │                                                          │ │                                         │ │
│ │ Phân loại rủi ro thời gian đệm quay vòng:                │ │ [▶] Chạy Mô phỏng Kịch bản này          │ │
│ │ ■ An toàn (>20m): 42 cặp (70.0%)                         │ │ [📊] Mở Biểu đồ Gantt Chi tiết (Page 3) │ │
│ │ ■ Rủi ro TB (5-20m): 14 cặp (23.3%)                      │ │ [🔬] Xem Giải thích SHAP Delay (Page 2) │ │
│ │ ■ Nguy cơ trễ dây chuyền (<5m): 4 cặp (6.7%)             │ │                                         │ │
│ └──────────────────────────────────────────────────────────┘ └─────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Detailed Component Inventory & Data Contracts

| Component ID | Component Name | Data Source | Primary Fields | Presentation Visibility | Research Mode Extra |
| :--- | :--- | :--- | :--- | :---: | :--- |
| **C1-HERO** | Operational Hero Header | Static + Scenario Registry | `scenario_id`, `hub_iata`, `hub_name` | Visible | Displays scenario SHA256 checksum & source file |
| **C1-KPI-01** | Total Flights Card | Scenario flight list | `len(flights)`, `len(turn_pairs)` | Visible | Displays tail number count and fleet composition |
| **C1-KPI-02** | Predicted Delay Card | `predictions_sample.csv` | `mean(arr_delay)`, `% >= 15min` | Visible | Displays 90% confidence interval $[+8.2, +34.5]$ min |
| **C1-KPI-03** | Static Plan Conflict Card | `OptimizationResult` (Nominal) | `nominal_conflict_count` | Visible | Displays list of conflicting flight pairs |
| **C1-KPI-04** | CP-SAT Solved Status Card | `OptimizationResult` (CP-SAT) | `status`, `conflict_count` | Visible | Displays exact objective value ($J=0.0$) and gap ($0.0\%$) |
| **C1-KPI-05** | Remote Apron Utilization | `OptimizationResult` (CP-SAT) | `remote_count`, `finite_capacity` | Visible | Displays passenger bus transit penalty avoided |
| **C1-CHART-01** | Operational Activity Timeline | Flight Legs timestamps | `sched_arr_min`, `sched_dep_min` (15m bins) | Visible | Toggle to show predicted vs scheduled distributions |
| **C1-CHART-08** | Concourse Capacity Snapshot | Gate metadata + assignments | `concourse`, `gate_count`, `active_occupancy` | Visible | Peak simultaneous occupancy count per concourse |
| **C1-SLACK** | Turnaround Health Card | `SimulationTurnResult` | `slack_risk_index`, `slack_min` | Visible | Expandable table listing 4 high-risk flights |
| **C1-ACTIONS** | Quick Navigation Actions | Internal Streamlit state | Button triggers | Visible | Button to download raw scenario JSON package |

---

## 4. Operational Activity Timeline (CHART-01 Specification)

- **Plotly Type:** Stacked Barchart (`go.Bar`) with dual series (Arrivals in Aerodrome Cyan `#47C5C0`, Departures in Runway Blue `#00D2FF`).
- **X-Axis:** Local Time (HH:MM), binned into 15-minute intervals from `06:00` to `12:00`.
- **Y-Axis:** Number of Flight Movements (Integer count, 0 to 30).
- **Hover Information:**
  ```
  Khung giờ: 07:30 - 07:45
  Hạ cánh dự kiến: 14 chuyến
  Cất cánh dự kiến: 8 chuyến
  Tổng lưu lượng: 22 lượt tàu bay
  ```
- **Empty State:** If scenario contains no flights, renders empty chart outline with centered warning: `"Không có dữ liệu chuyến bay cho kịch bản đã chọn"`.

---

## 5. UI States & Exception Handling

1. **Loading State:** When user switches scenario from `SCEN_P09_CANONICAL_120` to `SCEN_2023_PEAK_01`, metric cards display pulsing skeleton badges (`Đang nạp dữ liệu...`) while CSV/JSON loads (< 20 ms).
2. **Missing Prediction Artifact:** If `predictions_sample.csv` is missing from `artifacts/`, KPI Card 2 gracefully displays `Dữ liệu lịch bay gốc` with an amber warning badge, rather than raising a Python file error.
3. **Zero Conflicts State:** If nominal schedule already has zero conflicts, Card 3 displays Clearance Green `[✓ LỊCH TĨNH KHẢ THI]` and notes that optimization confirms nominal stability.
