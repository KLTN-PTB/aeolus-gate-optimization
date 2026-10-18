# Page 02 Specification — Flight Intelligence (Dự báo Trễ & ML)

**Document ID:** `AEOLUS-P10-A-PAGE-02`  
**Phase:** P10-A (UI/UX Design Specification & Design Freeze)  
**Status:** DESIGN FROZEN  
**Target View:** Page 2 (`02_flight_intelligence.py`)  

---

## 1. Executive Summary & Page Purpose

The **Flight Intelligence** page reveals the predictive core of the Aeolus architecture. It demonstrates how machine learning transforms raw flight schedules into delay-aware gate occupancy profiles. 

The page is organized into three dedicated tabs:
- **Tab A — Flight Predictions:** Fleet-wide arrival and departure delay forecasts with uncertainty ranges.
- **Tab B — Aircraft Turn Dynamics:** The synthesis of turnaround slack, delay propagation from inbound to outbound legs, and $[T_{\text{arr}}, T_{\text{dep}} + \text{buffer}]$ occupancy windows.
- **Tab C — Model Explainability:** Scientific interpretability using TreeSHAP global importance and local single-flight waterfall plots.

> [!CAUTION] Zero Data Leakage Mandate (Finding D3)
> In planning mode, this page NEVER displays actual historical delay labels ($y_{\text{true}}$). The dispatcher and optimizer operate strictly on predicted distributions ($\hat{y}$) and prior network features to reflect real-world decision conditions.

---

## 2. Page Wireframe & Layout Architecture (Desktop 1920 × 1080)

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ [🔬] FLIGHT INTELLIGENCE — DỰ BÁO ĐỘ TRỄ & GIẢI THÍCH MÔ HÌNH HỌC MÁY                   [Hub: ATL 2023] │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ [ Tab A: Dự báo Trễ Chuyến bay ] │ [ Tab B: Động lực học Quay vòng ] │ [ Tab C: Giải thích SHAP ]      │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ TAB A CONTENT:                                                                                         │
│ ┌────────────────────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ [🔍 Tìm chuyến bay: DL1024...] [Hãng: Tất cả ▼] [Mức trễ: Trễ >15m ▼] [Sắp xếp: Trễ giảm dần ▼]     │ │
│ ├────────────────────────────────────────────────────────────────────────────────────────────────────┤ │
│ │ ┌────────────────────────────────────────────────────┐ ┌──────────────────────────────────────────┐ │ │
│ │ │ DANH SÁCH CHUYẾN BAY DỰ BÁO TRỄ (BẢNG TƯƠNG TÁC)   │ │ PHÂN BỐ ĐỘ TRỄ DỰ BÁO (CHART-02)        │ │ │
│ │ │ Mã CB   │ Đường bay │ Giờ hạ cánh │ Trễ dự báo     │ │ Tần suất                                 │ │ │
│ │ │─────────┼───────────┼─────────────┼────────────────│ │  30 ┤       ╭─╮                          │ │ │
│ │ │ DL1024  │ ORD→ATL   │ 07:45       │ +24.5 min [⚠️] │ │  20 ┤     ╭─╯ ╰─╮                        │ │ │
│ │ │ DL1502  │ LGA→ATL   │ 08:10       │ +18.2 min [⚠️] │ │  10 ┤   ╭─╯     ╰─╮                      │ │ │
│ │ │ DL0882  │ MCO→ATL   │ 08:15       │  +2.1 min [✓]  │ │   0 ┴───┴───┴───┴───┴───┴───             │ │ │
│ │ │ DL2219  │ DFW→ATL   │ 08:30       │ -4.0 min [✓]   │ │     -10   0  +10 +20 +30 +40 (Phút)      │ │ │
│ │ └────────────────────────────────────────────────────┘ └──────────────────────────────────────────┘ │ │
│ └────────────────────────────────────────────────────────────────────────────────────────────────────┘ │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ TAB B CONTENT (KHI CHỌN TAB B):                                                                        │
│ ┌────────────────────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ CẶP QUAY VÒNG: TURN_DL1024_DL1502 (Tàu bay: N3743H | B738)                                         │ │
│ │ ┌────────────────────────────────────────────────────────────────────────────────────────────────┐ │ │
│ │ │ SƠ ĐỒ ĐỘNG LỰC HỌC QUAY VÒNG & HẤP THỤ BUFFER (CHART-03)                                       │ │ │
│ │ │ Inbound: 07:45 ──[+24.5m Trễ]──► Đến thực: 08:09                                               │ │ │
│ │ │ Turn Window Sched: 75m  |  Min Turn Required: 45m  |  Đệm Slack khả dụng: 30m                  │ │ │
│ │ │ Slack hấp thụ: 24.5m    |  Slack còn lại: 5.5m [⚠️ RỦI RO TRUNG BÌNH]                          │ │ │
│ │ │ Outbound Depart Sched: 09:00 ──► Dự kiến khởi hành mới: 09:00 (Không bị trễ lan truyền)        │ │ │
│ │ │ Khung chiếm dụng cổng tổng hợp: [08:09 ── 09:15) (Bao gồm 15 phút giãn cách an toàn)           │ │ │
│ │ └────────────────────────────────────────────────────────────────────────────────────────────────┘ │ │
│ └────────────────────────────────────────────────────────────────────────────────────────────────────┘ │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ TAB C CONTENT (KHI CHỌN TAB C):                                                                        │
│ ┌──────────────────────────────────────────────────────────┐ ┌─────────────────────────────────────────┐ │
│ │ XẾP HẠNG TÍNH NĂNG TOÀN CỤC SHAP (CHART-05)              │ │ THÁC NƯỚC SHAP CỤC BỘ CHUYẾN DL1024     │ │
│ │ arr_delay_prior_network : [████████████████] +8.45m      │ │ Giá trị kỳ vọng nền: +4.2 min           │ │
│ │ crs_dep_time_hour       : [████████████] +5.12m          │ │ + arr_delay_prior (+8.45m) ──► +12.65m  │ │
│ │ scheduled_elapsed_time  : [██████] -2.10m                │ │ + crs_dep_time_hour (+6.12m) ──► +18.77m│ │
│ │ carrier_arrival_trend   : [████] +1.80m                  │ │ - scheduled_elapsed (-1.20m) ──► +17.57m│ │
│ │                                                          │ │ = Dự báo cuối cùng: +24.5 min [⚠️]       │ │
│ └──────────────────────────────────────────────────────────┘ └─────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Tab-by-Tab Detailed Component Specifications

### 3.1. Tab A — Flight Predictions
- **Component ID:** `C2-TAB-A-TABLE` (Interactive Prediction Table)
  - Data Source: `artifacts/remediation/native_dual_core/predictions_sample.csv`.
  - Columns:
    - `flight_id` (Monospace link)
    - `carrier` (`DL`)
    - `origin` $\to$ `destination` (`ORD` $\to$ `ATL`)
    - `sched_arr_time` (`07:45`)
    - `predicted_arr_delay` (`+24.5 min`, colored badge)
    - `uncertainty_range` (`[+15.2, +35.8] min`)
    - `risk_flag` (`NORMAL`, `MODERATE_DELAY`, `SEVERE_DELAY`)
  - Selection Interaction: Clicking a row sets `selected_flight_id` in session state, automatically synchronizing with Tab B and Tab C.
- **Component ID:** `C2-CHART-02` (Delay Distribution Histogram)
  - Plotly Type: `go.Histogram` with KDE line overlay.
  - X-Axis: Predicted Arrival Delay (minutes).
  - Annotations: Vertical dashed line at `+15 min` threshold.

---

### 3.2. Tab B — Aircraft Turn Dynamics
- **Component ID:** `C2-CHART-03` (Turnaround Gantt / Timeline)
  - Visual Representation: Horizontal stacked interval bar showing:
    1. Inbound flight leg segment.
    2. Scheduled turnaround window $[T_{\text{arr}}^{\text{sched}}, T_{\text{dep}}^{\text{sched}}]$.
    3. Minimum required turnaround service time ($T_{\text{min\_turn}} = 45\text{ min}$).
    4. Scheduled Turnaround Slack ($T_{\text{slack}} = T_{\text{window}} - T_{\text{min\_turn}}$).
    5. Absorbed Delay segment (colored in Warning Amber).
    6. Remaining buffer or Propagated Outbound Delay (colored in Alert Red if negative).
    7. 15-minute gate release separation buffer added to the tail.
  - Formula Display:
    $$T_{\text{slack\_remain}} = \max\left(0, \; (T_{\text{dep}}^{\text{sched}} - T_{\text{arr}}^{\text{sched}} - T_{\text{min\_turn}}) - \hat{d}_{\text{arr}}\right)$$
    $$d_{\text{dep\_propagated}} = \max\left(0, \; \hat{d}_{\text{arr}} - (T_{\text{dep}}^{\text{sched}} - T_{\text{arr}}^{\text{sched}} - T_{\text{min\_turn}})\right)$$

---

### 3.3. Tab C — Model Explainability (SHAP)
- **Component ID:** `C2-CHART-05` (Global SHAP Feature Importance)
  - Data Source: `artifacts/remediation/ml_validation/shap_outputs/global_importance.csv`.
  - Plotly Type: Horizontal Barchart (`go.Bar`), sorted by mean absolute SHAP value $|\phi_j|$.
- **Component ID:** `C2-CHART-06` (Local Single-Flight Waterfall Plot)
  - Data Source: `artifacts/remediation/ml_validation/shap_outputs/shap_case_studies.json`.
  - Plotly Type: `go.Waterfall`.
  - Traces the transformation from base value $E[f(X)]$ to final predicted delay $\hat{y}$.
  - Features positive pushing forces (red/amber) and delay-reducing forces (cyan/green).
- **Academic Model Metrics Card (Research Mode):**
  - Displays out-of-fold validation metrics:
    - $\text{MAE} = 12.4\text{ phút}$
    - $\text{RMSE} = 18.2\text{ phút}$
    - $R^2 = 0.412$
    - $\text{CRPS} = 8.12\text{ phút}$ (Probabilistic Calibration)

---

## 4. UI Acceptance & Fallback Rules
1. **Fallback for Missing SHAP Values:** If user selects a flight ID that does not have a precomputed local SHAP breakdown, render a clean informative banner: `"Biểu đồ SHAP cục bộ hiển thị cho các chuyến bay mẫu đại diện (Case Studies 1-5). Xem biểu đồ toàn cục bên trái để nắm quy luật chung."`
2. **Negative Delay Handling:** Negative delay (early arrival) must be clearly formatted as `-4.0 min (Đến sớm)` in Clearance Green without confusing users.
