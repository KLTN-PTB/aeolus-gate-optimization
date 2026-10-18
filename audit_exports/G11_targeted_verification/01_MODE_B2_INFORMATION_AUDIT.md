# AEOLUS-G11 — DELIVERABLE 01: MODE B2 INFORMATION SET, PRECOMPUTED GATE-OUT & LOCK HORIZON AUDIT

---

**Audit Gate:** `AEOLUS-G11` — Targeted Causality, Hybrid Invariant & Snapshot Verification  
**Date of Audit:** 2026-10-12  
**Auditor Role:** Independent Scientific Software Verification Engineer  
**Audit Scope:** `src/simulation/monte_carlo_engine_v2.py` — `evaluate_mode_b2_rolling_online_recourse` & `src/simulation/monte_carlo_engine_p09.py`  
**Classification:** STRICT READ-ONLY SCIENTIFIC AUDIT  

---

## 1. MỤC TIÊU VÀ BỐI CẢNH KIỂM TOÁN

Trong báo cáo G10 (`audit_exports/G10_independent_verification/03_G2_CAUSAL_MONTE_CARLO_AUDIT.md`), chế độ mô phỏng **Mode B2 (Rolling Online Recourse)** được phân loại là **STRICTLY CAUSAL** với lập luận rằng thuật toán duyệt các sự kiện theo trình tự thời gian đến thực tế và khóa cứng các chuyến bay đã đỗ.

Tuy nhiên, kiểm tra độc lập cấu trúc mã nguồn phát hiện hai nghi vấn cốt lõi:
1. `evaluate_mode_b2_rolling_online_recourse()` tại các dòng 421, 432, 450 truy cập trực tiếp trường `precomputed_gate_out_min` từ danh sách `realized_flights`. Trường này chứa mốc thời gian rời cổng thực tế (departure time) vốn thuộc về tương lai đối với thời điểm quyết định tiếp nhận (arrival epoch $t$).
2. Tham số `lock_horizon_minutes: int = 45` được khai báo trong chữ ký hàm và được mô tả trong docstring như một bất biến phi dự đoán (non-anticipativity invariant), nhưng có dấu hiệu không được sử dụng trong thân hàm.

Báo cáo này cung cấp kết quả rà soát chi tiết mã nguồn, phân tích tập thông tin (Information Set), và thẩm định tính phi dự đoán toán học.

---

## 2. RÀ SOÁT MÃ NGUỒN VÀ NGUỒN GỐC DỮ LIỆU CỦA `precomputed_gate_out_min`

### 2.1. Nguồn gốc khởi tạo tại `monte_carlo_engine_p09.py`

Khi kịch bản Monte Carlo được khởi tạo, hàm `apply_delays_to_flights()` trong `src/simulation/monte_carlo_engine_p09.py` (dòng 208–239) biến đổi các chuyến bay cơ sở thành danh sách `realized_flights`:

```python
# File: src/simulation/monte_carlo_engine_p09.py (lines 215-238)
for i, f in enumerate(base_flights):
    realized_arr = int(f.scheduled_arrival_min + round(arr_delays[i]))
    realized_dep = int(f.scheduled_departure_min + round(dep_delays[i]))
    min_dep = realized_arr + f.min_turnaround_min
    if realized_dep < min_dep:
        realized_dep = min_dep
    realized_flights.append(
        Flight(
            ...
            predicted_arrival_min=realized_arr,
            nominal_gate_id=f.nominal_gate_id,
            aircraft_type=f.aircraft_type,
            min_turnaround_min=f.min_turnaround_min,
            default_dwell_min=f.default_dwell_min,
            buffer_min=f.buffer_min,
            is_paired=f.is_paired,
            precomputed_gate_out_min=realized_dep,  # <--- GÁN TRỰC TIẾP REALIZED DEPARTURE
        )
    )
```

**Nhận xét:**
- `realized_dep` là mốc thời gian hoàn tất chặng đỗ và khởi hành thực tế của kịch bản, đã tính gộp độ trễ khởi hành ngẫu nhiên `dep_delays[i]`.
- Giá trị này được tính toán trước (precomputed) ngay từ đầu kịch bản và được đính kèm vào đối tượng `Flight` dưới trường `precomputed_gate_out_min`.

---

### 2.2. Vị trí và Cơ chế đọc `precomputed_gate_out_min` trong Mode B2

Trong `src/simulation/monte_carlo_engine_v2.py`, hàm `evaluate_mode_b2_rolling_online_recourse()` thực hiện vòng lặp biến cố theo thời gian đến thực tế:

```python
# File: src/simulation/monte_carlo_engine_v2.py
event_order = sorted(realized_flights, key=lambda f: (f.predicted_arrival_min, f.flight_index))

for current_flight in event_order:
    current_time = current_flight.predicted_arrival_min  # <--- THỜI ĐIỂM QUYẾT ĐỊNH t
    ...
```

Tại thời điểm $t = \text{current\_flight.predicted\_arrival\_min}$, thuật toán kiểm tra xung đột và gán cổng như sau:

1. **Dòng 420–421 (Xác định thời điểm kết thúc chiếm dụng của chuyến bay hiện tại):**
   ```python
   current_start = current_flight.predicted_arrival_min
   current_end = current_flight.precomputed_gate_out_min or (current_start + current_flight.default_dwell_min)
   ```
2. **Dòng 430–432 (Xác định thời điểm giải phóng cổng của các chuyến bay đã đỗ trước đó `locked_fl`):**
   ```python
   l_start = locked_fl.predicted_arrival_min
   l_end = locked_fl.precomputed_gate_out_min or (l_start + locked_fl.default_dwell_min)
   l_release = l_end + locked_fl.buffer_min
   # Kiểm tra chồng lấn:
   if max(current_start, l_start) < min(current_end + current_flight.buffer_min, l_release):
       has_conflict = True
       break
   ```
3. **Dòng 448–452 (Kiểm tra xung đột khi quét các cổng tiếp xúc ứng viên `cand_gate`):**
   ```python
   l_start = l_fl.predicted_arrival_min
   l_end = l_fl.precomputed_gate_out_min or (l_start + l_fl.default_dwell_min)
   l_release = l_end + l_fl.buffer_min
   if max(current_start, l_start) < min(current_end + current_flight.buffer_min, l_release):
       cand_conflict = True
       break
   ```

---

## 3. PHÂN TÍCH TẬP THÔNG TIN (INFORMATION SET) & CAUSALITY

Trong lý thuyết quá trình ngẫu nhiên và điều phối thời gian thực:
- **Tập thông tin tại thời điểm $t$ ($\mathcal{F}_t$):** Chỉ bao gồm các biến cố đã diễn ra trước hoặc tại $t$, cùng các dự báo được đưa ra dựa trên dữ liệu tới $t$.
- **Thời điểm khởi hành thực tế ($T_{\text{dep}}$):** Nằm ở tương lai đối với thời điểm hạ cánh ($T_{\text{dep}} > t$). Tại thời điểm hạ cánh $t$, chuyến bay mới bắt đầu cập cổng, thời gian thực tế rời cổng chưa xảy ra.
- Nếu thuật toán tại thời điểm $t$ sử dụng $T_{\text{dep}}$ thực tế thay vì dự báo khởi hành $\hat{T}_{\text{dep}|t}$ hoặc thời gian quay đầu quy chuẩn ($t + \text{dwell}_{\text{sched}}$), hệ thống đã thực hiện **truy cập thông tin tương lai (Future Information Access)**.

### Phân loại mức độ vi phạm:

| Khía cạnh | Hiện trạng trong Mode B2 | Đánh giá Tính Nhân quả |
| :--- | :--- | :---: |
| **Dự báo trễ đến (`predicted_arrival_min`)** | Sắp xếp biến cố theo thời gian đến thực tế $t$. | **HỢP LỆ (CAUSAL)** |
| **Khóa tàu bay đã đỗ (`locked_flights`)** | Khóa các tàu bay có $T_{\text{arr}} < t$ không cho đổi cổng. | **HỢP LỆ (CAUSAL)** |
| **Thời gian giải phóng cổng của tàu bay đã đỗ (`l_release`)** | Tính từ `precomputed_gate_out_min` (= $T_{\text{dep}}$ thực tế). | **FUTURE INFORMATION ACCESS** |
| **Thời gian chiếm dụng của tàu bay đang xét (`current_end`)** | Tính từ `precomputed_gate_out_min` (= $T_{\text{dep}}$ thực tế). | **FUTURE INFORMATION ACCESS** |

---

## 4. KIỂM TOÁN THAM SỐ `lock_horizon_minutes`

Trong chữ ký hàm tại dòng 371–380 của `src/simulation/monte_carlo_engine_v2.py`:
```python
def evaluate_mode_b2_rolling_online_recourse(
    initial_assignments: Mapping[str, GateAssignment],
    realized_flights: Sequence[Flight],
    base_scheduled_flights: Sequence[Flight],
    gates: Sequence[Gate],
    config: GateOptimizationConfig,
    realization: RealizedScenario,
    initial_solver_name: str,
    lock_horizon_minutes: int = 45,  # <--- KHAI BÁO THAM SỐ
) -> RemediatedRealizationResult:
```

Trong docstring của hàm (dòng 387):
```text
4. Only uncommitted future flights (> t + lock_horizon) can be moved to resolve conflicts.
```

### Kết quả kiểm toán tĩnh (Static AST Audit):
Kiểm toán viên đã thực hiện quét toàn bộ thân hàm `evaluate_mode_b2_rolling_online_recourse` (từ dòng 381 đến 540):
- **Số lần tham số `lock_horizon_minutes` xuất hiện trong thân hàm:** **0 LẦN**.
- **Ảnh hưởng logic:** Hoàn toàn bằng không. Biến `lock_horizon_minutes` là **mã chết (Unused Parameter / Dead Code)**.
- Docstring tuyên bố quy tắc *"Chỉ những chuyến bay tương lai ngoài khoảng t + lock_horizon mới được điều chuyển"* là một **tuyên bố không có thực thi (Unimplemented Invariant)**. Trên thực tế, thuật toán điều chuyển chính chuyến bay đang xét tại thời điểm $t$ nếu cổng của nó bị xung đột.

---

## 5. KẾT LUẬN KIỂM TOÁN BƯỚC ĐẦU CHO TASK 1

1. **FUTURE_INFORMATION_ACCESS:** **ĐÃ XÁC MINH (VERIFIED)**. Thuật toán đọc trực tiếp `precomputed_gate_out_min` vốn chứa thời điểm khởi hành thực tế của kịch bản Monte Carlo tại thời điểm tiếp nhận $t$.
2. **lock_horizon_minutes:** **THẤT BẠI (FAILED)**. Tham số này không được tích hợp vào logic điều độ rolling horizon; hoàn toàn là dead code.
3. **DECISION_LEAKAGE:** Cần được kiểm chứng thực nghiệm bằng kịch bản phản chứng (Counterexample) tại Deliverable 02 để xác định liệu việc thay đổi độ trễ đi tương lai có trực tiếp làm biến đổi quyết định điều chuyển cổng tại thời điểm $t$ hay không.
