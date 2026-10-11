# Page 03 Specification — Gate Operations (Gantt Chart Tương tác)

**Document ID:** `AEOLUS-P10-A-PAGE-03`  
**Phase:** P10-A (UI/UX Design Specification & Design Freeze)  
**Status:** DESIGN FROZEN  
**Target View:** Page 3 (`03_gate_operations.py`)  

---

## 1. Executive Summary & Page Purpose

The **Gate Operations** page is the central visual centerpiece of the Aeolus thesis. It provides airside operations controllers with an interactive, high-density **Gate Gantt Chart**, enabling real-time visualization of aircraft occupancy, separation buffers, spatial conflicts, and automated CP-SAT gate reassignments.

> [!IMPORTANT] Operations Research Integrity Contract
> 1. **Occupancy Interval:** Aircraft occupancy MUST strictly follow the half-open interval $[T_{\text{arr}}, T_{\text{dep}} + \text{buffer}_{\text{min}})$.
> 2. **Buffer Policy:** The 15-minute release buffer must NEVER be omitted, nor counted twice. In the Gantt chart, the turnaround occupancy and separation buffer are rendered as contiguous segments with visual texture distinction.
> 3. **No Drag-and-Drop in v1:** To protect mathematical validity, manual flight dragging is disabled in P10 v1. Reallocations are computed strictly via proven solvers.

---

## 2. Page Wireframe & Layout Architecture (Desktop 1920 × 1080)

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ [✈] GATE OPERATIONS — ĐIỀU PHỐI VÀ TỐI ƯU HÓA CỔNG ĐỖ TÀU BAY                            [ATL 2023]    │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ [ Kế hoạch: (•) Tối ưu CP-SAT  ( ) Danh định gốc (Nominal)  ( ) So sánh Song song (Research) ]         │
│ Bộ lọc Cổng: [☑ Concourse T (10)] [☑ Concourse A (15)] [☑ Bãi đỗ từ xa (1)]  │ [🔍 Tìm chuyến bay...]   │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────────────────────┐ ┌─────────────────────────┐ │
│ │ BIỂU ĐỒ GANTT TƯƠNG TÁC PHÂN BỔ CỔNG (CHART-07)                         │ │ BẢNG ĐIỀU KHIỂN BỘ GIẢI │ │
│ │ Cổng  │ 06:00     07:00     08:00     09:00     10:00     11:00   12:00 │ │ (LIVE SOLVER CONTROLS)  │ │
│ │───────┼─────────────────────────────────────────────────────────────────│ │ Thuật toán:             │ │
│ │ T01   │ [DL1024 ▒]        [DL2210 ▒]              [DL0451 ▒]            │ │ [ CP-SAT (Sparse)   ▼ ] │ │
│ │ T02   │      [DL1502 ▒]            [DL1982 ▒]                           │ │                         │ │
│ │ ...   │                                                                 │ │ Phạt đổi cổng (w_pref): │ │
│ │ A01   │ [DL0882 ▒]    [DL1104 ▒]      [DL2315 ▒]                        │ │ [───●──────────] 10.0   │ │
│ │ A02   │   [DL0941 ▒]       [DL1422 ▒]              [DL1778 ▒]           │ │                         │ │
│ │ ...   │                                                                 │ │ Phạt cổng xa (w_remote):│ │
│ │ A15   │          [DL3321 ▒]           [DL0119 ▒]                        │ │ [───────●──────] 200.0  │ │
│ │ R_OVF │ (Trống - Không có tàu bay đỗ từ xa)                             │ │                         │ │
│ │───────┴─────────────────────────────────────────────────────────────────│ │ Đệm giãn cách (phút):   │ │
│ │ Chú giải: [■ Chiếm dụng bình thường] [■ Đổi cổng] [■ Cổng từ xa] [▒ Đệm]│ │ [────●─────────] 15 min │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │                         │
├───────────────────────────────────────────────────────────────────────────┤ │ [⚡ TỐI ƯU HÓA NGAY]     │ │
│ ┌──────────────────────────────────────────┐ ┌──────────────────────────┐ │ │ Thời gian giải: 65 ms   │ │
│ │ THÔNG TIN CHI TIẾT CHUYẾN BAY ĐƯỢC CHỌN  │ │ KIỂM CHỨNG TOÁN HỌC ĐỘC  │ │ │                         │ │
│ │ Chuyến bay: DL1024 (ORD → ATL)           │ │ LẬP (INDEPENDENT CHECK)  │ │ └─────────────────────────┘ │
│ │ Cổng phân bổ: T01 (Cổng danh định gốc)   │ │                          │                               │
│ │ Khung giờ: 06:45 ──► 07:45 (+15m buffer) │ │ [🛡️ HỢP LỆ — 0 VI PHẠM]  │                               │
│ │ Tàu bay: N3743H (Boeing 737-800)         │ │ ✓ Không trùng lịch cổng  │                               │
│ │ Slack quay vòng: 24.5 min (An toàn)      │ │ ✓ Tương thích kích thước │                               │
│ │ Chi phí đổi cổng phát sinh: 0.0          │ │ ✓ Không vượt sức chứa xa │                               │
│ └──────────────────────────────────────────┘ └──────────────────────────┘                               │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Master Interactive Gate Gantt (CHART-07 Specification)

### 3.1. Geometry & Coordinate System
- **X-Axis:** Continuous local timeline in 24-hour clock format (`06:00` to `12:00` for canonical morning wave).
- **Y-Axis:** Categorical gate rows sorted logically by concourse:
  - `T01, T02, ..., T10` (Concourse T — 10 gates)
  - `A01, A02, ..., A15` (Concourse A — 15 gates)
  - `REMOTE_OVERFLOW` (Separated by horizontal divider line)
- **Occupancy Box Coordinates:**
  - Flight Occupancy Block: $[T_{\text{arr\_real}}, T_{\text{dep\_real}})$
  - Release Separation Buffer Block: $[T_{\text{dep\_real}}, T_{\text{dep\_real}} + \text{buffer}_{\text{min}})$
- **Cross-Midnight Handling:** For flights extending past midnight ($t \ge 1440$ min), the bar continues past `23:59` with a subtle date watermark tag `(+1d 00:35)`.

### 3.2. Visual Styling & Color Encoding

| Flight & Gate State | Bar Fill Color | Border / Texture | Dual-Encoding Indicator |
| :--- | :---: | :---: | :---: |
| **Nominal Contact Assignment** | Aerodrome Cyan (`#47C5C0`) | Solid subtle border | Standard flight label text |
| **Reassigned Contact Gate** | Taxiway Amber (`#E5AD55`) | Solid bright border | Swap icon prefix: `⇄ DL1502` |
| **Remote Overflow Apron** | Apron Violet (`#A78BFA`) | Solid violet border | Bus icon prefix: `🚌 DL0882` |
| **Release Separation Buffer** | Patterned diagonal stripes | Semi-transparent (`opacity: 0.35`) | Hatched texture `▒` |
| **Physical Conflict (Nominal View)**| Alert Red (`#E47777`) | Thick red flashing outline | Warning icon prefix: `⚠️ XUNG ĐỘT` |

### 3.3. Hover Information Payload
Hovering over any aircraft block renders an instantaneous tooltip:
```
Chuyến bay: DL1024 (Đến từ: ORD | Đi tiếp: MCO)
Tàu bay: B738 (N3743H)
Cổng đỗ: GATE_T01 (Danh định)
Hạ cánh thực tế: 06:45 (+18.4m trễ)
Cất cánh dự kiến: 07:45
Khung chiếm dụng cổng: 06:45 - 07:45
Thời gian đệm an toàn: 15 phút (đến 08:00)
Trạng thái: HỢP LỆ — ĐÚNG CỔNG DANH ĐỊNH
```

---

## 4. Live Solver Controls & Real-Time Solving

The right-hand control drawer allows the user to test what-if scenarios on the Canonical 120 flights:

### Controls:
1. **Solver Algorithm Dropdown:**
   - `CP-SAT (Sparse Interval)` `[DEFAULT]`
   - `Deterministic Greedy`
   - `Hybrid Solver (Greedy Warm-Start + CP-SAT)`
   - `Simulated Annealing` *(Research Mode only)*
2. **Reassignment Penalty Slider (`w_pref`):** Range $[0.0, 50.0]$, Step $5.0$, Default $10.0$.
3. **Remote Apron Penalty Slider (`w_remote`):** Range $[50.0, 500.0]$, Step $25.0$, Default $200.0$.
4. **Separation Buffer Slider (`buffer_time_min`):** Range $[10, 30]$ min, Step $5$ min, Default $15$ min.
5. **Execution Trigger:** `[⚡ TỐI ƯU HÓA NGAY]`.
   - On click, invokes `solver.solve(...)` synchronously in backend.
   - For 120 flights, Greedy takes ~3 ms, CP-SAT takes ~65 ms.
   - Screen re-renders instantly with updated assignments.

---

## 5. Independent Mathematical Verification Card

Following every solve or view switch, `verify_hard_constraints_independently(...)` is called automatically:
- **Success State:**
  - Banner: `[🛡️ HỢP LỆ — 0 VI PHẠM TOÁN HỌC]` (Clearance Green).
  - Sub-items:
    - ✓ 120/120 chuyến bay được phân cổng duy nhất.
    - ✓ 0 trường hợp va chạm không gian - thời gian trên cổng tiếp xúc.
    - ✓ 100% chuyến bay tuân thủ giãn cách an toàn 15 phút.
    - ✓ Sức chứa bãi đỗ từ xa tuân thủ định mức.
- **Violation State (e.g. In Nominal View):**
  - Banner: `[⚠️ CẢNH BÁO: 13 VI PHẠM KHẢ THI]` (Alert Red).
  - Expandable list showing exact conflicting pairs (e.g., `GATE_A04: DL1024 và DL2219 trùng lịch từ 07:50 đến 08:15`).
