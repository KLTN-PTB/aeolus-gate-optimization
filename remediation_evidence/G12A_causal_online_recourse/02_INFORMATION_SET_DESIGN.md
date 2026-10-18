# AEOLUS-G12A — DELIVERABLE 02: INFORMATION SET & TEMPORAL BOUNDARY DESIGN

---

**Task Identifier:** `AEOLUS-G12A` — Causal Online Recourse Remediation  
**Auditor & Implementation Role:** Senior Operations Research Engineer, Causal Simulation Engineer  
**Date:** 2026-10-12  
**Document Classification:** FORMAL MATHEMATICAL SPECIFICATION & INFORMATION BOUNDARY CONTRACT  

---

## 1. BỐI CẢNH VÀ NGUYÊN LÝ NON-ANTICIPATIVITY

Trong lý thuyết quá trình ngẫu nhiên và điều phối thời gian thực, một chính sách điều phối trực tuyến (Online Recourse Policy) $\pi$ được gọi là **phi dự đoán nghiêm ngặt (Strictly Non-anticipative / Causal)** nếu tại mỗi thời điểm ra quyết định (decision epoch) $t$, quyết định điều chuyển cổng $u_t = \pi(\mathcal{I}_t)$ chỉ là một hàm phụ thuộc duy nhất vào **Tập thông tin quan sát được (Information Set)** $\mathcal{I}_t$.

$$\mathcal{I}_t = \sigma\left( \{ X_s \mid s \le t \}, \{ \hat{Y}_{s' \mid s} \mid s \le t, s' \ge s \} \right)$$

Nếu bất kỳ biến ngẫu nhiên $Y_{s^*}$ nào của tương lai ($s^* > t$) bị đọc trực tiếp mà không thông qua mô hình dự báo hợp lệ được phát hành tại $\le t$, hệ thống đã vi phạm tính nhân quả và mắc lỗi **Information Leakage / Perfect Foresight**.

---

## 2. PHÂN ĐỊNH RẠCH RÒI 7 THÀNH PHẦN THÔNG TIN TẠI EPOCH $t$

Để khắc phục triệt để sai lầm của kiến trúc cũ (truyền toàn bộ đối tượng `Flight` chứa `precomputed_gate_out_min`), hệ thống mới phân tách rạch ròi 7 khái niệm:

```
+---------------------------------------------------------------------------------------+
|                                SIMULATION WORLD                                       |
|  Sở hữu Ground-Truth Realization của cả kịch bản: T*_arr(f), T*_dep(f)                |
+---------------------------------------------------------------------------------------+
                                           |
                  Lọc biến cố qua ranh giới thời gian t (Filter at epoch t)
                                           |
                                           v
+---------------------------------------------------------------------------------------+
|                               OBSERVATION SNAPSHOT (I_t)                              |
|  1. Scheduled Timetable:        T_arr^sched(f), T_dep^sched(f)                        |
|  2. Observed Arrivals (<= t):   t_arr^obs(f) = T*_arr(f) cho các chuyến có T*_arr <= t|
|  3. Observed Gate-Outs (<= t):  Tàu đã rời cổng thực tế trước t                       |
|  4. Docked Aircraft at t:       Tàu đang chiếm cổng tại t, T*_dep(f) CHƯA XẢY RA      |
|  5. Estimated Future Departure: T_dep^est(f|t) tính từ lịch/quay đầu, KHÔNG PHẢI T*_dep|
|  6. Committed Reservations:     Các chuyến sắp đến trong khung [t, t + H_lock]        |
|  7. Remote Stand Occupancy:     Số lượng vị trí bãi đỗ xa đang bị chiếm dụng tại t    |
+---------------------------------------------------------------------------------------+
                                           |
                               Truyền duy nhất I_t vào Policy
                                           |
                                           v
+---------------------------------------------------------------------------------------+
|                           CAUSAL RECOURSE DECISION POLICY                             |
|  Chỉ đọc I_t -> Ra quyết định gán cổng cho chuyến bay đến tại epoch t                 |
+---------------------------------------------------------------------------------------+
```

### Chi tiết 7 thành phần:

1. **Lịch trình công bố (Scheduled Timetable):**
   - $T_{\text{arr}}^{\text{sched}}(f), T_{\text{dep}}^{\text{sched}}(f)$.
   - Được công bố trước ngày khai thác, khả dụng tại mọi thời điểm $t$.
2. **Biến cố đến đã quan sát (Observed Arrivals):**
   - Chỉ các chuyến bay có thời điểm hạ cánh thực tế $T_{\text{arr}}^*(f) \le t$ mới có trạng thái $t_{\text{arr}}^{\text{obs}}(f) = T_{\text{arr}}^*(f)$.
   - Các chuyến bay có $T_{\text{arr}}^*(f) > t$ được coi là chưa đến; thời điểm đến thực tế của chúng là **nghiêm cấm truy cập**.
3. **Biến cố rời cổng đã quan sát (Observed Gate-Outs):**
   - Một chuyến bay đã cập cổng trước đó ($T_{\text{arr}}^*(f) < t$) chỉ được coi là đã rời cổng nếu thời điểm bay đi thực tế $T_{\text{dep}}^*(f) \le t$.
   - Khi đó, cổng được giải phóng tại mốc $T_{\text{dep}}^*(f) + \text{buffer}$.
4. **Tàu bay đang chiếm dụng cổng tại epoch $t$ (Docked Aircraft):**
   - Nếu $T_{\text{arr}}^*(f) \le t$ và $T_{\text{dep}}^*(f) > t$, tàu bay đang hiện diện vật lý tại cổng.
   - Ranh giới quan sát: Người điều hành nhìn thấy tàu bay đang đỗ, nhưng **KHÔNG BIẾT TRƯỚC** thời điểm $T_{\text{dep}}^*(f)$ ở tương lai.
5. **Ước tính thời gian rời cổng tương lai ($\hat{T}_{\text{dep}|t}$):**
   - Không được đọc `precomputed_gate_out_min`!
   - Sử dụng công thức ước tính hợp lệ theo hợp đồng vận hành:
     $$\hat{T}_{\text{dep}|t}(f) = \max\left( T_{\text{dep}}^{\text{sched}}(f), t_{\text{arr}}^{\text{obs}}(f) + f.\text{min\_turnaround\_min}, t \right)$$
   - Nếu tàu bay bị trễ quá giờ lịch trình ($t > T_{\text{dep}}^{\text{sched}}(f)$) nhưng vẫn chưa đẩy lùi, người điều hành cập nhật ước tính ít nhất bằng thời điểm hiện tại $t$.
6. **Đặt chỗ đã cam kết (Committed Reservations within Lock Horizon):**
   - Các chuyến bay dự kiến hạ cánh trong khoảng $t < T_{\text{arr}} \le t + H_{\text{lock}}$ (với $H_{\text{lock}} = 45$ phút).
   - Được bảo vệ để hạn chế xáo trộn vận hành.
7. **Tải trọng bãi đỗ xa tức thời (Current Remote Usage):**
   - Số lượng tàu bay đang chiếm dụng các vị trí bãi đỗ xa tại epoch $t$.
   - Ngăn chặn việc gán tràn vào bãi đỗ xa khi số lượng tàu bay vượt quá `finite_remote_capacity`.

---

## 3. THIẾT KẾ CẤU TRÚC DỮ LIỆU ĐÓNG BĂNG (FROZEN DATACLASS ARCHITECTURE)

Để bảo đảm mã nguồn không thể vô tình đọc lậu thuộc tính tương lai, chúng ta định nghĩa các cấu trúc dữ liệu mới với ranh giới hẹp:

```python
@dataclass(frozen=True)
class ObservableFlightSnapshot:
    """Snapshot of flight data strictly accessible at decision epoch t."""
    flight_id: str
    flight_index: int
    carrier: str
    flight_number: str
    aircraft_type: str
    scheduled_arrival_min: int
    scheduled_departure_min: int
    nominal_gate_id: str
    min_turnaround_min: int
    default_dwell_min: int
    buffer_min: int
    is_paired: bool
    observed_arrival_min: int          # Realized arrival time (since t_arr <= t)
    estimated_departure_min: int       # Causal estimate as-of epoch t (NO FUTURE LEAKAGE)
    is_docked: bool                    # True if currently occupying a gate at t

@dataclass(frozen=True)
class GateOccupancySnapshot:
    """Physical state of a gate as observed at decision epoch t."""
    gate_id: str
    is_occupied: bool
    docked_flight_id: str | None
    estimated_vacate_min: int | None   # estimated_dep + buffer (None if free)

@dataclass(frozen=True)
class CausalObservationSnapshot:
    """Authoritative Information Set I_t at decision epoch t."""
    epoch_min: int
    current_flight: ObservableFlightSnapshot
    gate_occupancy: Mapping[str, GateOccupancySnapshot]
    committed_gate_reservations: Mapping[str, str]  # flight_id -> gate_id within lock horizon
    current_remote_stand_occupancy: int
    finite_remote_capacity: int
```

**Khẳng định kiến trúc:**  
Đối tượng `CausalObservationSnapshot` **HOÀN TOÀN KHÔNG CÓ** trường `precomputed_gate_out_min` hoặc `actual_departure_delays`. Quyết định của bộ giải (Policy) chỉ có thể được tính toán dựa trên các trường được đóng gói trong snapshot này.
