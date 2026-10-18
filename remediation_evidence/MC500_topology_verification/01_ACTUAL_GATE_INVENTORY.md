# 01. ACTUAL GATE INVENTORY AUDIT & TOPOLOGY SPECIFICATION

**Protocol Reference:** AEOLUS-MC500-TOPOLOGY-GATE  
**Execution Context:** Canonical Benchmark Scenario `SCEN_P09_CANONICAL_120` (120 flights, Atlanta Hartsfield-Jackson Inbound Bank)  
**Verification Date:** 2026-10-12  

---

## 1. Executive Summary

Kiểm toán độc lập tài nguyên topology của pipeline Monte Carlo Gate Optimization phát hiện rằng cấu hình thực nghiệm `25 contact gates + 5 remote stands` ban đầu bị sai lệch cấu trúc dữ liệu do hàm baseline `build_scenario_gates()` gán nhầm cổng tràn thành `UNBOUNDED_OVERFLOW_APRON` (`REMOTE_APRON_01`, dung lượng vô hạn). Đồng thời, runner lại kích hoạt cấm apron vô hạn (`allow_unbounded_overflow=False`), khiến tổng số vị trí đỗ từ xa hữu hạn thực tế bằng **0**.

Sau hiệu chỉnh có kiểm soát, toàn bộ hệ thống được đồng bộ hóa với đúng 26 thực thể tài nguyên xác định:
- **25 Cổng tiếp xúc vật lý (`CONTACT_GATE`)**: Dung lượng mỗi cổng là $1$, không cho phép tràn (`is_overflow=False`).
- **1 Vị trí đỗ từ xa tập trung (`FINITE_REMOTE_STAND`)**: `REMOTE_STAND_01`, dung lượng tập trung hữu hạn bằng đúng **5** tàu bay đồng thời, cờ tràn `is_overflow=True`.
- **0 Bãi tràn vô hạn (`UNBOUNDED_OVERFLOW_APRON`)**: Không có cổng vô hạn nào tồn tại trong tập tài nguyên khi `allow_unbounded_overflow=False`.

---

## 2. Gate Resource Inventory Table

| Gate ID | Index | Resource Type | Capacity | is_overflow | Allowed Carriers | Aircraft Types | Operating Windows |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| `G_01` | 0 | `CONTACT_GATE` | 1 | `False` | ALL | ALL | `[0, 1440]` |
| `G_02` | 1 | `CONTACT_GATE` | 1 | `False` | ALL | ALL | `[0, 1440]` |
| `G_03` | 2 | `CONTACT_GATE` | 1 | `False` | ALL | ALL | `[0, 1440]` |
| `G_04` | 3 | `CONTACT_GATE` | 1 | `False` | ALL | ALL | `[0, 1440]` |
| `G_05` | 4 | `CONTACT_GATE` | 1 | `False` | ALL | ALL | `[0, 1440]` |
| `G_06` | 5 | `CONTACT_GATE` | 1 | `False` | ALL | ALL | `[0, 1440]` |
| `G_07` | 6 | `CONTACT_GATE` | 1 | `False` | ALL | ALL | `[0, 1440]` |
| `G_08` | 7 | `CONTACT_GATE` | 1 | `False` | ALL | ALL | `[0, 1440]` |
| `G_09` | 8 | `CONTACT_GATE` | 1 | `False` | ALL | ALL | `[0, 1440]` |
| `G_10` | 9 | `CONTACT_GATE` | 1 | `False` | ALL | ALL | `[0, 1440]` |
| `G_11` | 10 | `CONTACT_GATE` | 1 | `False` | ALL | ALL | `[0, 1440]` |
| `G_12` | 11 | `CONTACT_GATE` | 1 | `False` | ALL | ALL | `[0, 1440]` |
| `G_13` | 12 | `CONTACT_GATE` | 1 | `False` | ALL | ALL | `[0, 1440]` |
| `G_14` | 13 | `CONTACT_GATE` | 1 | `False` | ALL | ALL | `[0, 1440]` |
| `G_15` | 14 | `CONTACT_GATE` | 1 | `False` | ALL | ALL | `[0, 1440]` |
| `G_16` | 15 | `CONTACT_GATE` | 1 | `False` | ALL | ALL | `[0, 1440]` |
| `G_17` | 16 | `CONTACT_GATE` | 1 | `False` | ALL | ALL | `[0, 1440]` |
| `G_18` | 17 | `CONTACT_GATE` | 1 | `False` | ALL | ALL | `[0, 1440]` |
| `G_19` | 18 | `CONTACT_GATE` | 1 | `False` | ALL | ALL | `[0, 1440]` |
| `G_20` | 19 | `CONTACT_GATE` | 1 | `False` | ALL | ALL | `[0, 1440]` |
| `G_21` | 20 | `CONTACT_GATE` | 1 | `False` | ALL | ALL | `[0, 1440]` |
| `G_22` | 21 | `CONTACT_GATE` | 1 | `False` | ALL | ALL | `[0, 1440]` |
| `G_23` | 22 | `CONTACT_GATE` | 1 | `False` | ALL | ALL | `[0, 1440]` |
| `G_24` | 23 | `CONTACT_GATE` | 1 | `False` | ALL | ALL | `[0, 1440]` |
| `G_25` | 24 | `CONTACT_GATE` | 1 | `False` | ALL | ALL | `[0, 1440]` |
| `REMOTE_STAND_01` | 25 | `FINITE_REMOTE_STAND` | 5 | `True` | ALL | ALL | `[0, 1440]` |

---

## 3. Topology Accounting Verification

1. **Số lượng Cổng tiếp xúc (`CONTACT_GATE`):**
   $$\sum_{g \in \mathcal{G}, \text{type}(g) = \text{CONTACT\_GATE}} 1 = 25$$
2. **Tổng sức chứa vị trí đỗ từ xa hữu hạn (`FINITE_REMOTE_STAND`):**
   $$\sum_{g \in \mathcal{G}, \text{type}(g) = \text{FINITE\_REMOTE\_STAND}} \text{Cap}(g) = 5$$
3. **Số lượng bãi tràn vô hạn (`UNBOUNDED_OVERFLOW_APRON`):**
   $$\sum_{g \in \mathcal{G}, \text{type}(g) = \text{UNBOUNDED\_OVERFLOW\_APRON}} 1 = 0$$
4. **Cờ cấu hình nghiêm ngặt (`allow_unbounded_overflow`):**
   $$\text{allow\_unbounded\_overflow} = \text{False}$$
   Tất cả chuyến bay không thể gán vào bất kỳ bãi đỗ nào nếu vượt quá sức chứa 5 của `REMOTE_STAND_01`.

---

## 4. Resource Allocation & Selection Policies Across Modes

| Solver / Evaluation Mode | Tập tài nguyên khả dụng | Ràng buộc sức chứa áp dụng | Phản ứng khi đầy 25 Contact | Phản ứng khi đầy 5 Remote |
| :--- | :--- | :--- | :--- | :--- |
| **Deterministic Greedy** | Cả 26 cổng (`G_01`–`G_25`, `REMOTE_STAND_01`) | Contact: $Cap=1$; Remote: Event sweep $\le 5$ | Gán vào `REMOTE_STAND_01` nếu tải $< 5$ | Báo Unassigned / Infeasible |
| **CP-SAT Solver** | Cả 26 cổng | Contact: `AddNoOverlap`; Remote: `AddCumulative(demands=1, cap=5)` | Gán vào `REMOTE_STAND_01` | Infeasible / Unassigned |
| **Hybrid Solver** | Cả 26 cổng | Kết hợp Greedy seed + CP-SAT / SA cải tiến | Gán vào `REMOTE_STAND_01` | Infeasible / Unassigned |
| **Mode A (Fixed Plan)** | Đánh giá lại nghiệm ban đầu | Kiểm toán va chạm vật lý sau thực tế | Va chạm contact bị phạt cứng | Vượt 5 remote bị phạt cứng |
| **Mode B1 (Retrospective)** | Cả 26 cổng (tái tối ưu toàn diện) | Sức chứa thực tế không vi phạm | Chuyển sang `REMOTE_STAND_01` | Giữ nguyên giới hạn 5 |
| **Mode B2 (Rolling Online)** | Cả 26 cổng (Causal Event-Driven) | Causal snapshot: $\text{usage}(t) < 5$ | Chuyển sang `REMOTE_STAND_01` | Từ chối: `NO_CAPACITY_EXHAUSTED` |
| **Mode C1 (Greedy Foresight)**| Cả 26 cổng với trễ đã biết | Thuật toán tham lam trên timeline thực tế | Phân bổ vào `REMOTE_STAND_01` | Infeasible nếu vượt quá 5 |
| **Mode C2 (Optimal Oracle)** | Cả 26 cổng với trễ đã biết | CP-SAT toàn cục trên timeline thực tế | Phân bổ tối ưu vào `REMOTE_STAND_01` | Infeasible nếu vượt quá 5 |
