# Page 04 Specification — Optimization Lab (Phòng thí nghiệm Tối ưu hóa)

**Document ID:** `AEOLUS-P10-A-PAGE-04`  
**Phase:** P10-A (UI/UX Design Specification & Design Freeze)  
**Status:** DESIGN FROZEN  
**Target View:** Page 4 (`04_optimization_lab.py`)  

---

## 1. Executive Summary & Page Purpose

The **Optimization Lab** is the comparative operations research proving ground of the Aeolus suite. It contrasts four distinct algorithmic approaches:
1. **Deterministic Greedy:** Instantaneous priority-ordered heuristic.
2. **CP-SAT (Sparse Interval):** Exact Constraint Programming using Google OR-Tools interval algebra.
3. **CP-SAT (Dense Time-Indexed):** Classical discrete time-grid baseline.
4. **Simulated Annealing (SA):** Stochastic meta-heuristic with geometric cooling.
5. **Hybrid Solver:** Greedy warm-start injection followed by CP-SAT neighborhood search.

It demonstrates mathematical proof of optimality on canonical operations and exhibits mega-hub scalability on 1,500 flights.

---

## 2. Page Wireframe & Layout Architecture (Desktop 1920 × 1080)

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ [⚗️] OPTIMIZATION LAB — PHÒNG THÍ NGHIỆM SO SÁNH THUẬT TOÁN TỐI ƯU HÓA                   [ATL 2023]    │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ [ Kịch bản: SCEN_P09_CANONICAL_120 (120 chuyến) ]  │ [✓] Kích hoạt Chế độ Nghiên cứu Chuyên sâu        │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ BẢNG SO SÁNH HIỆU NĂNG ĐA THUẬT TOÁN (CANONICAL 120 CHUYẾN BAY)                                        │
│ ┌──────────────────────┬─────────────┬──────────┬──────────┬──────────┬──────────────┬───────────────┐ │
│ │ Thuật toán           │ Chi phí (J) │ Đổi cổng │ Cổng xa  │ Thời gian│ Trạng thái   │ Optimality Gap│ │
│ ├──────────────────────┼─────────────┼──────────┼──────────┼──────────┼──────────────┼───────────────┤ │
│ │ CP-SAT (Sparse)      │ 0.0         │ 0        │ 0        │ 0.065s   │ OPTIMAL_PROV │ 0.00% [🏆]    │ │
│ │ Hybrid (Greedy+CP)   │ 0.0         │ 0        │ 0        │ 0.088s   │ OPTIMAL_PROV │ 0.00%         │ │
│ │ Deterministic Greedy │ 0.0         │ 0        │ 0        │ 0.003s   │ HEURISTIC    │ N/A (Tham lam)│ │
│ │ Simulated Annealing  │ 10.0        │ 1        │ 0        │ 0.850s   │ HEURISTIC    │ ~10.0%        │ │
│ │ CP-SAT (Dense Grid)  │ 0.0         │ 0        │ 0        │ 1.420s   │ OPTIMAL_PROV │ 0.00% (Chậm)  │ │
│ └──────────────────────┴─────────────┴──────────┴──────────┴──────────┴──────────────┴───────────────┘ │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ ┌──────────────────────────────────────────────────────────┐ ┌─────────────────────────────────────────┐ │
│ │ ĐÁNH ĐỔI CHI PHÍ QUYẾT ĐỊNH VS THỜI GIAN GIẢI (CHART-09) │ │ BÓC TÁCH MÔ HÌNH HÓA CP-SAT             │ │
│ │ Chi phí (J)                                              │ │ (SPARSE INTERVAL VS DENSE GRID)         │ │
│ │ 20 ┤                                                     │ │                                         │ │
│ │ 10 ┤                ● SA (0.85s, J=10)                   │ │ ■ Mô hình Rời rạc Lưới (Dense Grid):    │ │
│ │    │                                                     │ │   Biến nhị phân: 288,000 biến           │ │
│ │  0 ┼──● Greedy     ● CP-SAT     ● Dense Grid             │ │   RAM tiêu thụ: 185 MB | Thời gian: 1.4s│ │
│ │    ┴──┴────────────┴────────────┴────────────────        │ │ ■ Mô hình Khoảng rời rạc (Sparse):      │ │
│ │     1ms           100ms         1s       (Log scale)     │ │   Biến khoảng: 3,000 biến interval      │ │
│ │                                                          │ │   RAM tiêu thụ: 18 MB  | Thời gian: 65ms│ │
│ │ Kích thước bóng: Số cổng xa sử dụng                      │ │   ► Tốc độ vượt trội: Nhanh hơn 21.8 lần│ │
│ └──────────────────────────────────────────────────────────┘ └─────────────────────────────────────────┘ │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ KHẢ NĂNG MỞ RỘNG QUY MÔ MEGA-HUB: 1,500 CHUYẾN BAY (CHART-11 & BENCHMARK P08)                          │
│ ┌────────────────────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ [Bằng chứng tiền tính toán - Precomputed P08] Kịch bản 24h toàn sân bay ATL: 1,500 Chuyến | 50 Cổng│ │
│ │ • CP-SAT Sparse Interval: Giải thành công trong 34.2s (Đạt cận gap < 1.5% với 1,482 cổng tiếp xúc) │ │
│ │ • Deterministic Greedy: Hoàn thành trong 0.021s (Dự phòng khẩn cấp khi hệ thống mất điện)          │ │
│ └────────────────────────────────────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Component Details & Data Contracts

### 3.1. Multi-Algorithm Benchmark Comparison Table
- **Data Source:** `artifacts/remediation/benchmarks/solver_runs.csv` & `aggregate_metrics.json`.
- **Columns & Formatting:**
  1. `solver_name`: Styled name with algorithm badge.
  2. `objective_value` ($J_{\text{decision}}$): Float with 1 decimal place.
  3. `reassignment_count`: Integer count.
  4. `remote_gate_count`: Integer count.
  5. `solve_time_sec`: Formatted in milliseconds (`ms`) or seconds (`s`).
  6. `termination_reason`: Exact domain enum string (`OPTIMAL_PROVEN`, `FEASIBLE_FOUND`, `HEURISTIC_STOP`).
  7. `optimality_gap`: Percentage gap to proven lower bound (or `N/A` for heuristics).

---

### 3.2. Cost vs. Runtime Trade-off Scatter Plot (CHART-09)
- **Plotly Type:** Scatter Bubble Chart (`go.Scatter`).
- **X-Axis:** Solve Time in seconds (Logarithmic Scale `type="log"`, range `[0.001, 10.0]`).
- **Y-Axis:** Objective Decision Cost ($J_{\text{decision}}$, range `[-1, 25]`).
- **Marker Styling:**
  - Size: Scaled by remote apron usage count.
  - Color: Mapped to solver category (CP-SAT in Cyan, Heuristic in Amber, SA in Purple).
- **Hover Payload:**
  ```
  Thuật toán: CP-SAT (Sparse Interval)
  Thời gian giải: 0.065 s (65 ms)
  Chi phí quyết định (J): 0.0
  Đổi cổng: 0 | Cổng xa: 0
  Trạng thái: TỐI ƯU TUYỆT ĐỐI (OPTIMAL_PROVEN)
  ```

---

### 3.3. Mega-Hub Scalability Curve (CHART-11)
- **Data Source:** `artifacts/stress_1500x50/solver_results.parquet` and `artifacts/stress_1500x50/aggregate_metrics.json`.
- **Plotly Type:** Multi-line plot with markers (`go.Scatter`).
- **X-Axis:** Flight Count ($N \in \{120, 300, 600, 1000, 1500\}$).
- **Y-Axis:** Solve Time in seconds.
- **Series:**
  - `Greedy`: Flat near-zero curve ($t \approx 0.02\text{s}$ at $N=1500$).
  - `CP-SAT (Sparse)`: Polynomial trajectory reaching $34.2\text{s}$ at $N=1500$.
- **Callout Banner:**
  > *"Khuyến nghị Vận hành: Đối với đợt cao điểm tức thời (< 300 chuyến), CP-SAT mang lại giải pháp tối ưu tuyệt đối trong dưới 1 giây. Đối với kế hoạch 24 giờ toàn sân bay (1,500 chuyến), CP-SAT chạy ngầm định kỳ 30 giây, kết hợp Greedy làm phương án dự phòng tức thì khi có biến động khẩn cấp."*

---

## 4. Experiment Comparison Fairness Guardrails
To prevent misleading comparisons:
- Runs conducted with different penalty weights ($w_{\text{remote}} = 200$ vs $w_{\text{remote}} = 500$) or different scenarios are never averaged or ranked together.
- A prominent badge indicates: `"Dữ liệu đối sánh được chuẩn hóa trên kịch bản SCEN_P09_CANONICAL_120 với bộ trọng số mặc định (w_pref=10, w_remote=200, buffer=15m)"`.
