# Navigation Architecture & User Journeys Specification

**Document ID:** `AEOLUS-P10-A-NAV-02`  
**Phase:** P10-A (UI/UX Design Specification & Design Freeze)  
**Status:** DESIGN FROZEN  
**Target Application:** Streamlit Demonstration & Research Dashboard  

---

## 1. Executive Summary

This document specifies the global navigation hierarchy, user journeys, persistent session state architecture, and view transitions across the Aeolus application. It ensures a frictionless experience for both high-stakes thesis defense presentations and deep academic research sessions.

---

## 2. Navigation Sitemap & Information Hierarchy

```mermaid
flowchart TD
    AppRoot["AEOLUS GATE OPTIMIZATION SUITE"] --> ContextBar["Global Context Bar<br/>(Hub: ATL | Scenario Selector | Active Solver | Mode Toggle)"]
    
    ContextBar --> SidebarNav["Sidebar Navigation"]
    
    SidebarNav --> P1["01. Control Tower<br/>(Tổng quan Điều hành Trung tâm)"]
    SidebarNav --> P2["02. Flight Intelligence<br/>(Dự báo Trễ & ML Explainability)"]
    SidebarNav --> P3["03. Gate Operations<br/>(Gantt Chart & Phân bổ Cổng)"]
    SidebarNav --> P4["04. Optimization Lab<br/>(Phòng thí nghiệm Thuật toán)"]
    SidebarNav --> P5["05. Robustness Lab<br/>(Kiểm thử Bền vững Monte Carlo)"]
    
    P1 -.-> P3
    P2 -.-> P3
    P3 -.-> P4
    P4 -.-> P5

    P1 --- Inspector["Research Inspector Drawer<br/>(Persistent Expandable Bottom/Sidebar Panel)"]
    P2 --- Inspector
    P3 --- Inspector
    P4 --- Inspector
    P5 --- Inspector
```

---

## 3. Global Context Bar Specification

The **Global Context Bar** is pinned at the top of the interface across all five pages, rendering critical operational metadata in a unified horizontal status bar:

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ ✈ AEOLUS HUB: ATL (Atlanta) │ Kịch bản: [ SCEN_P09_CANONICAL_120 ▼ ] │ Chuyến bay: 120 │ Cổng đỗ: 25+1 │
│ Thuật toán: [ CP-SAT (Sparse) ▼ ] │ Trạng thái: ● TỐI ƯU TUYỆT ĐỐI │ [✓] Chế độ Nghiên cứu (Research)  │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Context Bar Components
1. **Hub Identifier:** `ATL (Hartsfield-Jackson Atlanta Int'l Airport)`.
2. **Scenario Selector Dropdown:**
   - Option A: `SCEN_P09_CANONICAL_120` (Canonical Peak Morning Wave — 120 flights, 25 gates) `[DEFAULT]`.
   - Option B: `SCEN_2023_PEAK_01` (Concourse T Intensive Stress — 85 flights, 15 gates).
   - *(Note: 2024 scenarios are quarantined and excluded from this selector).*
3. **Operational Scale Badge:** `120 Chuyến bay | 25 Cổng tiếp xúc + 1 Cổng từ xa`.
4. **Active Solver Indicator:** Reflects current solver algorithm (`CP-SAT`, `Greedy`, `Hybrid`).
5. **Global Solution Status Badge:** Real-time indicator of current solution state (`TỐI ƯU TUYỆT ĐỐI`, `KHẢ THI`, `ĐANG TÍNH TOÁN`, `CHƯA GIẢI`).
6. **Mode Toggle Switch:** `[ ] Chế độ Nghiên cứu (Research Mode)` — default is unchecked (`Presentation Mode`).

---

## 4. User Journeys

### User Journey 1: The 15-Minute Thesis Defense Walkthrough (Hành trình Bảo vệ Khóa luận)
- **Actor:** Graduate Student presenting to the Thesis Evaluation Committee.
- **Goal:** Deliver an airtight, compelling demonstration proving the scientific hypothesis and software engineering quality.
- **Mode:** Presentation Mode (clean, high-contrast, zero clutter).

```mermaid
sequenceDiagram
    autonumber
    actor Presenter as Sinh viên Thuyết trình
    actor Jury as Hội đồng Chấm thi
    participant P1 as Page 1: Control Tower
    participant P2 as Page 2: Flight Intelligence
    participant P3 as Page 3: Gate Operations
    participant P4 as Page 4: Optimization Lab
    participant P5 as Page 5: Robustness Lab

    Presenter->>P1: Mở Control Tower (Phút 1-3)
    Note over P1: Giới thiệu bức tranh khai thác ATL:<br/>120 chuyến bay sáng cao điểm, 13 xung đột tiềm tàng
    P1-->>Jury: Hiển thị áp lực trễ tích lũy và hạ tầng cổng

    Presenter->>P2: Chuyển sang Flight Intelligence (Phút 4-6)
    Note over P2: Giải thích mô hình dự báo trễ 2 lõi:<br/>XGBoost đến/đi và cơ chế hấp thụ slack quay vòng
    Presenter->>P2: Bấm chọn 1 chuyến bay trễ nặng -> Mở SHAP waterfall
    P2-->>Jury: Chứng minh mô hình giải thích được nguyên nhân trễ

    Presenter->>P3: Chuyển sang Gate Operations (Phút 7-10) [TRỌNG TÂM]
    Note over P3: Trình diễn biểu đồ Gantt tương tác:<br/>Bật kế hoạch danh định (nhiều xung đột đỏ)<br/>-> Bật kế hoạch CP-SAT (100% sạch xung đột)
    Presenter->>P3: Thử nghiệm đổi trọng số phạt cổng xa và bấm "Tối ưu hóa ngay"
    P3-->>Jury: CP-SAT giải lại trong 65ms, độc lập kiểm chứng 0 vi phạm

    Presenter->>P4: Chuyển sang Optimization Lab (Phút 11-12)
    Note over P4: So sánh 4 thuật toán:<br/>Greedy vs CP-SAT vs SA vs Hybrid và dữ liệu 1500 chuyến
    P4-->>Jury: Minh chứng CP-SAT Sparse Interval tối ưu tuyệt đối

    Presenter->>P5: Chuyển sang Robustness Lab (Phút 13-15)
    Note over P5: Kiểm thử độ bền 500 kịch bản Monte Carlo:<br/>Giải thích D1 (74.8% va chạm thực tế)<br/>và hiệu quả của Recourse (Mode B)
    P5-->>Jury: Kết luận đề tài đạt chuẩn khoa học và thực tiễn vận hành
```

---

### User Journey 2: The Operations Dispatcher (Hành trình Điều phối viên Cảng)
- **Actor:** Airline Hub Operations Dispatcher managing a tactical delay wave.
- **Workflow:**
  1. Opens **Control Tower** to monitor predicted delay pressure ($> 25$ min threshold).
  2. Navigates to **Gate Operations** to review affected aircraft turns on Concourse A.
  3. Uses **Concourse Filter** to isolate gates `A01` to `A15`.
  4. Identifies 2 inbound aircraft delayed by 45 minutes that will violate the 15-minute gate separation buffer.
  5. Selects `HybridGateSolver` for immediate tactical recourse.
  6. Adjusts `w_remote` to 300 to minimize towing passengers to remote stands.
  7. Clicks **"Tối ưu hóa ngay (Live Solve)"**.
  8. Reviews the updated Gantt chart: 1 flight reassigned to adjacent gate `A08`, 0 remote stands used, 0 buffer violations.
  9. Verifies the **Independent Safety Badge** displays `"HỢP LỆ — 0 VI PHẠM"`.

---

### User Journey 3: The Research Software Auditor (Hành trình Nhà Nghiên cứu / Kiểm toán viên)
- **Actor:** Research Auditor validating algorithmic invariants and empirical distributions.
- **Workflow:**
  1. Activates **Research Mode** toggle in the Global Context Bar.
  2. Inspects the **Research Inspector** drawer: checks model training provenance, XGBoost commit hash, and scenario random seed (`42`).
  3. Navigates to **Flight Intelligence** $\to$ Tab C (Model Explainability): reviews global feature importance, CRPS metric ($8.12$), and out-of-fold residuals.
  4. Navigates to **Optimization Lab**: opens CP-SAT formulation comparison card, observing memory reduction and 12x speedup of `sparse_interval` vs `dense_grid`.
  5. Navigates to **Robustness Lab**: inspects Mode A vs. Mode B vs. Mode C empirical CDF curves.
  6. Reads the **Academic Research Note** on Mode B/C parity ($p = 1.0$), confirming scientific honesty regarding the greedy baseline.
  7. Uses the **Scenario Drill-Down Slider** to inspect Scenario `#42` (worst-case tail disruption with 8 reassignments).

---

## 5. Persistent Session State Schema (`st.session_state`)

To prevent loss of computational results during page transitions, the application maintains a strict, strongly-typed session state contract:

```python
# Session State Key Registry
SESSION_STATE_DEFAULTS = {
    # Navigation & Mode
    "current_page": "01_control_tower",
    "is_research_mode": False,
    
    # Scenario Context
    "active_scenario_id": "SCEN_P09_CANONICAL_120",
    "scenario_cache": {},          # Loaded scenario flights and gates
    
    # Active Optimization Result
    "active_solver_name": "cpsat", # "greedy" | "cpsat" | "sa" | "hybrid"
    "active_solution": None,       # Instance of OptimizationResult
    "is_solution_stale": False,    # True if user changed params without re-solving
    
    # Solver Hyperparameters (Draft & Committed)
    "param_w_pref": 10.0,
    "param_w_remote": 200.0,
    "param_buffer_time_min": 15,
    "param_allow_overflow": True,
    "param_time_limit_sec": 30.0,
    
    # View Filters
    "gantt_concourse_filter": ["T", "A", "REMOTE"],
    "gantt_search_query": "",
    "selected_flight_id": None,
    "selected_mc_scenario_id": 42,
}
```

### State Transition Rules
1. **Page Switching Rule:** Navigating between pages via the sidebar modifies only `current_page`. All data in `active_solution`, `scenario_cache`, and filter settings **MUST persist unaltered**.
2. **Parameter Adjustment Rule:** Moving slider controls updates `param_*` and sets `is_solution_stale = True`. The existing Gantt chart continues rendering the last valid solution, but displays a subtle amber badge: `"Tham số đã thay đổi — Vui lòng bấm Tối ưu hóa để cập nhật"`.
3. **Scenario Switch Rule:** Selecting a different scenario in the dropdown prompts a confirmation check, invalidates `active_solution`, loads the new scenario data into `scenario_cache`, and auto-loads the precomputed baseline solution for that scenario.
4. **Crash Recovery Rule:** If an individual plot fails to render, an inline error card is shown inside that specific container, leaving the rest of the page and session state intact.
