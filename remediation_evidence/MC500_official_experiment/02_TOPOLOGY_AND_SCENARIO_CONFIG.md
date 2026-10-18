# 02. TOPOLOGY SPECIFICATION & STOCHASTIC SCENARIO CONFIGURATION

**Protocol:** AEOLUS-MC500-PRODUCTION  
**Scenario Specification:** `SCEN_P09_CANONICAL_120` (120 flights Inbound Atlanta Hub)  
**Topology Architecture:** 25 Physical Contact Gates + 1 Pooled Finite Remote Stand (Capacity 5)  

---

## 1. Cấu Hình Tài Nguyên Hạ Tầng Sân Bay (Ramp Resource Inventory)

Cấu hình tài nguyên được áp dụng đồng nhất và bất biến cho toàn bộ 500 kịch bản ngẫu nhiên:

| Phân nhóm Tài nguyên | Số lượng | Cổng định danh | Kiểu thực thể (`resource_type`) | Sức chứa (`capacity`) | Ràng buộc hoạt động |
| :--- | :---: | :--- | :--- | :---: | :--- |
| **Physical Contact Gates** | 25 | `G_01` đến `G_25` | `CONTACT_GATE` | 1 mỗi cổng | 1 tàu bay tại một thời điểm, đệm an toàn 15 phút giữa 2 chuyến. |
| **Pooled Remote Stand** | 1 | `REMOTE_STAND_01` | `FINITE_REMOTE_STAND` | **5** tàu bay | Dung lượng tập trung tối đa 5 tàu bay đồng thời trên toàn bộ bãi đỗ từ xa. |
| **Unbounded Overflow Apron**| 0 | *Không có* | `UNBOUNDED_OVERFLOW_APRON` | 0 | Bị cấm tuyệt đối theo hợp đồng thí nghiệm nghiêm ngặt. |

### Các tham số cấu hình vận hành:
- `allow_unbounded_overflow`: `False` (Cấm bãi tràn vô hạn).
- `enforce_remote_capacity`: `True` (Thực thi kiểm tra dung lượng từ xa bằng 5).
- `finite_remote_capacity`: `5`.
- `min_turnaround_minutes`: `45` phút.
- `default_dwell_minutes`: `60` phút.
- `separation_buffer_minutes`: `15` phút.
- `time_limit_seconds`: `1.5` giây (ngân sách thời gian solver CP-SAT trên mỗi kịch bản).

---

## 2. Mô Hình Phát Sinh Kịch Bản Ngẫu Nhiên (Stochastic Scenario Generator)

Quá trình sinh 500 kịch bản ngẫu nhiên tuân thủ phương pháp luận Parametric Copula đã được kiểm chứng tại G2:

1. **Hạt giống ngẫu nhiên (Base Random Seed):** `202601` (Predetermined Deployment Seed).
2. **Mô hình phụ thuộc đồng thời (Joint Dependence):** Gaussian Copula hai chiều với hệ số tương quan:
   $$\rho = 0.45$$
   Ma trận hiệp phương sai dương xác định với các trị riêng: $\lambda_1 = 0.55$, $\lambda_2 = 1.45$.
3. **Phân phối biên Trễ Đến (Arrival Delay Marginal):** Phân phối Student-$t$ tham số:
   - Bậc tự do (Degrees of Freedom): $\nu_{arr} = 4.5$
   - Vị trí trung tâm (Location): $\mu_{arr} = 5.0$ phút
   - Độ co dãn (Scale): $\sigma_{arr} = 18.0$ phút
4. **Phân phối biên Trễ Đi (Departure Delay Marginal):** Phân phối Student-$t$ tham số:
   - Bậc tự do: $\nu_{dep} = 4.0$
   - Vị trí trung tâm: $\mu_{dep} = 8.0$ phút
   - Độ co dãn: $\sigma_{dep} = 22.0$ phút
5. **Ràng buộc Thời gian Quay vòng Tối thiểu (Physical Turnaround Invariant):**
   Mỗi realization được kiểm tra và hiệu chỉnh cưỡng bức thời điểm khởi hành thực tế:
   $$\text{Realized Departure} \ge \text{Realized Arrival} + 45\text{ phút}$$
   đảm bảo tính hợp lệ vật lý trước khi chuyển sang các solver đánh giá.

---

## 3. Mã Băm Cấu Hình Thực Nghiệm (Config Provenance)

Toàn bộ tham số cấu hình bộ giải, trọng số mục tiêu và mô hình ngẫu nhiên được tuần tự hóa chuẩn hóa theo định dạng JSON có thứ tự:
```json
{
  "allow_unbounded_overflow": false,
  "base_seed": 202601,
  "conflict_weight": 1000.0,
  "copula_rho": 0.45,
  "default_dwell_minutes": 60,
  "delay_weight": 1.0,
  "enforce_remote_capacity": true,
  "finite_remote_capacity": 5,
  "min_turnaround_minutes": 45,
  "n_contact_gates": 25,
  "n_flights": 120,
  "n_remote_stands": 5,
  "overflow_weight": 200.0,
  "random_seed": 202601,
  "reassignment_weight": 10.0,
  "risk_weight": 2.0,
  "separation_buffer_minutes": 15,
  "time_limit_seconds": 1.5
}
```
Mã băm SHA-256 của cấu hình thực nghiệm:
`cf657dfdd3f6959b8a3e7eeb4c1f93f18a245fc2ca77ef17df6631ad02e96434`
Mã băm này được ghi trực tiếp vào từng bản ghi của Execution Ledger.
