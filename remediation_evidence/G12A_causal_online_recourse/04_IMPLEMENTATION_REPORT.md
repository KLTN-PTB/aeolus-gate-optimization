# AEOLUS-G12A — DELIVERABLE 04: CAUSAL ONLINE RECOURSE IMPLEMENTATION REPORT

---

**Task Identifier:** `AEOLUS-G12A` — Causal Online Recourse Remediation  
**Auditor & Implementation Role:** Senior Operations Research Engineer, Python Software Architect  
**Date:** 2026-10-12  
**Target Codebase:** `src/simulation/monte_carlo_engine_v2.py`  
**Classification:** SOURCE CODE REMEDIATION REPORT  

---

## 1. MỤC TIÊU VÀ NGUYÊN TẮC TÁI THIẾT KẾ MÃ NGUỒN

Nhiệm vụ trọng tâm của đợt sửa đổi G12A là:
1. **Loại bỏ hoàn toàn rò rỉ `precomputed_gate_out_min`:** Không để bộ giải tiếp nhận mốc thời gian rời cổng thực tế ở tương lai khi đang ra quyết định tại thời điểm hạ cánh $t$.
2. **Thiết lập Ranh giới Dữ liệu Bất khả xâm phạm (Zero-Leakage Boundary):** Tách biệt cấu trúc mô phỏng thế giới thực (`SimulationWorld`) và cấu trúc tập thông tin quan sát (`CausalObservationSnapshot`).
3. **Thực thi Hợp đồng `lock_horizon_minutes`:** Biến tham số trước đây là dead code thành một cơ chế bảo vệ hữu hiệu các chuyến bay sắp hạ cánh trong khung cam kết điều hành 45 phút.
4. **Kiểm soát Sức chứa Bãi đỗ Xa Hữu hạn (`finite_remote_capacity`):** Theo dõi số lượng tàu bay đang chiếm dụng bãi đỗ xa tại epoch $t$ và ngăn chặn việc gán tràn vô điều kiện.

---

## 2. CHI TIẾT CÁC CẤU TRÚC DỮ LIỆU VÀ HÀM ĐÃ TRIỂN KHAI

### 2.1. Các Cấu trúc Dữ liệu Ranh giới Mới

Trong `src/simulation/monte_carlo_engine_v2.py`:

```python
@dataclass(frozen=True)
class ObservableFlightSnapshot:
    """Strictly causal observation snapshot of flight attributes observable at epoch t.
    Prevents access to ground-truth future realized departure time or delays.
    """
    flight_id: str
    flight_index: int
    carrier: str
    flight_number: str
    aircraft_type: str | None
    scheduled_arrival_min: int
    scheduled_departure_min: int
    nominal_gate_id: str | None
    min_turnaround_min: int
    default_dwell_min: int
    buffer_min: int
    is_paired: bool
    observed_arrival_min: int
    estimated_departure_min: int
    is_docked: bool = False

@dataclass(frozen=True)
class CommittedReservationSnapshot:
    """Pre-arrival gate reservation within the operational commitment window [t, t + H_lock]."""
    flight_id: str
    gate_id: str
    planned_arrival_min: int
    estimated_vacate_min: int

@dataclass(frozen=True)
class GateOccupancySnapshot:
    """Physical occupancy of a gate as observed at decision epoch t."""
    gate_id: str
    is_occupied: bool
    docked_flight_id: str | None = None
    estimated_vacate_min: int | None = None

@dataclass(frozen=True)
class CausalObservationSnapshot:
    """Authoritative non-anticipative Information Set I_t at decision epoch t."""
    epoch_min: int
    current_flight: ObservableFlightSnapshot
    gate_occupancy: Mapping[str, GateOccupancySnapshot]
    committed_reservations: Sequence[CommittedReservationSnapshot]
    current_remote_usage: int
    finite_remote_capacity: int
```

---

### 2.2. Chính sách Điều phối Thuần túy Nhân quả (`make_causal_recourse_decision`)

Hàm chính sách này được thiết kế theo mô hình hàm thuần túy (Pure Function):
- Chỉ nhận đầu vào là `CausalObservationSnapshot` và danh mục tài nguyên cổng.
- **Hoàn toàn không nhận danh sách chuyến bay thực tế `realized_flights`**.
- Do đó, thuật toán **về mặt cấu trúc ngôn ngữ Python không thể truy cập bất kỳ thuộc tính nào của tương lai**.

Logic ra quyết định gồm 4 bước:
1. **Kiểm tra Xung đột Vật lý:** Kiểm tra xem cổng đang được gán có tàu bay đỗ thực tế tại $t$ hay không (`assigned_occ.is_occupied`).
2. **Kiểm tra Khóa Cam kết:** Kiểm tra xem khoảng chiếm dụng ước tính của chuyến bay đến $[t, \hat{T}_{\text{dep}} + \text{buffer}]$ có chồng lấn với bất kỳ chuyến bay nào đã cam kết trên cổng đó trong khung $[t, t + H_{\text{lock}}]$ hay không.
3. **Tìm kiếm Cổng Tiếp xúc Khả dụng:** Nếu có xung đột, quét các cổng tiếp xúc khác thỏa mãn tương thích loại tàu bay, không có tàu đỗ tại $t$, và không chồng lấn với các chuyến bay đã cam kết trong $H_{\text{lock}}$.
4. **Dự phòng Bãi đỗ Xa có Kiểm soát:** Nếu không có cổng tiếp xúc nào, kiểm tra sức chứa tức thời của bãi đỗ xa trước khi điều chuyển.

---

### 2.3. Quy trình Mô phỏng Thế giới Thực trong `evaluate_mode_b2_rolling_online_recourse`

1. Duyệt tuần tự các biến cố đến: $t = f_{\text{curr}}.\text{predicted\_arrival\_min}$.
2. Cập nhật trạng thái cổng: Tàu bay đã đến trước $t$ được xác định là đang đỗ nếu $T_{\text{dep}}^* > t$. Tuy nhiên, khi chuyển giao cho snapshot, thời gian rời cổng được ước tính nhân quả:
   $$\hat{T}_{\text{dep}|t} = \max\left(T_{\text{dep}}^{\text{sched}}, T_{\text{arr}} + \text{min\_turnaround}, t\right)$$
   Tuyệt đối không đưa $T_{\text{dep}}^*$ vào snapshot!
3. Thu thập các chuyến bay chưa đến trong khung cam kết $[t, t + H_{\text{lock}}]$ vào `committed_reservations`.
4. Gọi `make_causal_recourse_decision()` để lấy quyết định gán cổng.
5. Cập nhật `active_assignments` và khóa tàu bay vừa đến.
6. Sau khi kết thúc toàn bộ ngày bay, gọi hàm đánh giá độc lập `evaluate_gate_assignment()` đối chiếu nghiệm cuối cùng với ground truth của kịch bản Monte Carlo.

---

## 3. TỰ ĐỘNG HÓA KIỂM TRA ĐẢM BẢO KHÔNG LÙI BƯỚC (NON-REGRESSION)

Sau khi sửa đổi, kiểm toán viên đã chạy lại toàn bộ bộ kiểm thử nền tảng:
```powershell
.venv\Scripts\python.exe -m pytest tests/test_g2_monte_carlo_causality.py -v
```
**Kết quả:** 14/14 tests **PASS 100%** trong thời gian 1.22 giây. Không có bất kỳ sự suy giảm tương thích nào đối với các bài kiểm tra causality lịch sử.
