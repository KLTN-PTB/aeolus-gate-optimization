# AEOLUS-MC500-P1: PILOT N=20 ARITHMETIC AUDIT & FEASIBILITY RECONCILIATION

**Date:** 2026-10-12  
**Auditor:** Scientific Reproducibility Engineer & Python Integration Verification Engineer  
**Dataset Scale:** 120 flights, 25 contact gates, 5 remote stands (`SCEN_P09_CANONICAL_120`)  
**Base Random Seed:** `202601`  
**Execution Path:** `artifacts/remediation/monte_carlo_mc500/pilot_n20/`  
**Audited Artifact:** `execution_ledger_entries.csv` (220 rows) & `execution_ledger_summary.json`  
**Status:** **PASSED / 100% MATHEMATICAL & CONSERVATION RECONCILIATION**

---

## 1. Executive Summary

Báo cáo kiểm toán độc lập đã chỉ ra mâu thuẫn số học nghiêm trọng trong báo cáo cũ `07_PILOT_N20_RESULTS.md`:
- Tại Bảng mục 2: Báo cáo ghi nhận MODE_A khả thi 5/20 cho cả 3 solvers (15 feasible) và 100% khả thi ở 8 nhóm còn lại ($8 \times 20 = 160$ feasible), suy ra tổng số lần chạy khả thi phải là **175** (và 45 infeasible).
- Tại Mục 3: Bản tóm tắt ledger được báo cáo lại ghi **166 feasible** và **54 infeasible**.
- Thuyết minh mục 3 còn khẳng định sai lầm rằng *"tất cả 54 ca không khả thi đều thuộc về Mode A"*.

Kiểm toán viên đã sử dụng Python và thư viện Pandas để đọc trực tiếp toàn bộ 220 dòng dữ liệu thô tại tệp thực tế:  
`artifacts/remediation/monte_carlo_mc500/pilot_n20/execution_ledger_entries.csv`.

**Kết quả xác nhận:** Dữ liệu thô và bản tóm tắt json của hệ thống luôn ghi nhận chính xác **166 feasible** và **54 infeasible**. Mâu thuẫn 175 hoàn toàn là lỗi do con người tự soạn thảo sai bảng Markdown mà không đối chiếu với file thô. Không có lỗi logic nào trong mã nguồn ledger liên quan đến số đếm này.

---

## 2. Recomputed Statistical Breakdown per Mode and Solver

Kết quả tính toán độc lập 100% bằng Python/Pandas trên 220 bản ghi thô:

| Chế độ Recourse (`recourse_mode`) | Solver Kế hoạch Ban đầu (`initial_plan_solver`) | Tổng Slots (`count`) | Số Ca Khả thi (`feasible`) | Tỷ lệ Khả thi (%) | Số Ca Không Khả thi (`infeasible`) | Mean Obj | Std Dev | Min Obj | Max Obj |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **MODE_A** | `Greedy` | 20 | **3** | **15.0%** | **17** (85.0%) | 1,707.27 | 1,144.41 | 89.68 | 4,104.15 |
| **MODE_A** | `CPSat` | 20 | **3** | **15.0%** | **17** (85.0%) | 1,707.27 | 1,144.41 | 89.68 | 4,104.15 |
| **MODE_A** | `Hybrid` | 20 | **3** | **15.0%** | **17** (85.0%) | 1,707.27 | 1,144.41 | 89.68 | 4,104.15 |
| **MODE_B1** | `Greedy` | 20 | **20** | **100.0%** | **0** (0.0%) | 139.77 | 31.00 | 89.68 | 195.78 |
| **MODE_B1** | `CPSat` | 20 | **20** | **100.0%** | **0** (0.0%) | 139.77 | 31.00 | 89.68 | 195.78 |
| **MODE_B1** | `Hybrid` | 20 | **20** | **100.0%** | **0** (0.0%) | 139.77 | 31.00 | 89.68 | 195.78 |
| **MODE_B2** | `Greedy` | 20 | **19** | **95.0%** | **1** (5.0%) | 162.75 | 101.92 | 89.68 | 574.63 |
| **MODE_B2** | `CPSat` | 20 | **19** | **95.0%** | **1** (5.0%) | 162.75 | 101.92 | 89.68 | 574.63 |
| **MODE_B2** | `Hybrid` | 20 | **19** | **95.0%** | **1** (5.0%) | 162.75 | 101.92 | 89.68 | 574.63 |
| **MODE_C1** | `ForesightGreedy` | 20 | **20** | **100.0%** | **0** (0.0%) | 139.77 | 31.00 | 89.68 | 195.78 |
| **MODE_C2** | `ForesightCPSat` | 20 | **20** | **100.0%** | **0** (0.0%) | 124.27 | 18.28 | 89.68 | 165.78 |

---

## 3. Chi tiết Phân tích Ca Khả thi và Không Khả thi

### A. Phân tích Mode A (Fixed Plan):
- Mode A chỉ có duy nhất **3 kịch bản** giữ được tính khả thi sau khi xuất hiện trễ ngẫu nhiên:
  - `MC_REM_S0005`
  - `MC_REM_S0012`
  - `MC_REM_S0016`
- **17 kịch bản còn lại** bị vi phạm ràng buộc vùng đệm tách biệt (separation buffer) do chuyến bay bị trễ đè lên chuyến bay tiếp theo tại cùng một cổng.
- Do mỗi kịch bản được đánh giá độc lập trên 3 solver ban đầu (Greedy, CP-SAT, Hybrid), tổng số slots của Mode A là:
  - Slots khả thi: $3 \text{ kịch bản} \times 3 \text{ solvers} = \mathbf{9\text{ slots}}$.
  - Slots không khả thi: $17 \text{ kịch bản} \times 3 \text{ solvers} = \mathbf{51\text{ slots}}$.

### B. Phân tích Mode B2 (Online Recourse):
- Mode B2 đạt tỷ lệ khả thi **19/20 kịch bản (95.0%)**.
- Có duy nhất **1 kịch bản** bị không khả thi: `MC_REM_S0009`.
  - Lý do: Vào thời điểm cao điểm, số lượng chuyến bay trễ vượt quá sức chứa hữu hạn của 5 bãi đỗ xa (`finite_remote_capacity = 5`), thuật toán kích hoạt mã trạng thái `ONLINE_INFEASIBLE_NO_CAPACITY` và ghi nhận chi phí phạt tràn cổng (objective = 574.63).
  - Vì kịch bản này được đánh giá trên 3 solver kế hoạch ban đầu, tổng số slots không khả thi của Mode B2 là:
    $$1 \text{ kịch bản} \times 3 \text{ solvers} = \mathbf{3\text{ slots}}.$$
  - Số slots khả thi của Mode B2 là:
    $$19 \text{ kịch bản} \times 3 \text{ solvers} = \mathbf{57\text{ slots}}.$$

### C. Phân tích Mode B1, C1, C2:
- Toàn bộ 20 kịch bản đều đạt khả thi 100% nhờ khả năng tái phân bổ toàn cục:
  - Mode B1: $20 \times 3 = \mathbf{60\text{ slots}}$.
  - Mode C1: $20 \times 1 = \mathbf{20\text{ slots}}$.
  - Mode C2: $20 \times 1 = \mathbf{20\text{ slots}}$.

---

## 4. Giải quyết Triệt để Mâu thuẫn Số học: 175/45 vs 166/54

Tổng hợp hạch toán bảo toàn trên toàn bộ 220 evaluation slots:

$$\begin{aligned}
N_{\text{feasible}} &= N_{\text{Mode A}} + N_{\text{Mode B1}} + N_{\text{Mode B2}} + N_{\text{Mode C1}} + N_{\text{Mode C2}} \\
&= 9 + 60 + 57 + 20 + 20 = \mathbf{166}
\end{aligned}$$

$$\begin{aligned}
N_{\text{infeasible}} &= N_{\text{Mode A (infeasible)}} + N_{\text{Mode B2 (infeasible)}} \\
&= 51 + 3 = \mathbf{54}
\end{aligned}$$

$$\mathbf{166\text{ (Khả thi)} + 54\text{ (Không khả thi)} = 220\text{ Slots (Bảo toàn 100\%)}}$$

### Nguồn gốc của con số 175/45 trong báo cáo cũ:
1. Người soạn thảo văn bản Markdown cũ đã gõ nhầm số liệu của Mode A từ $3/20$ thành $5/20$ (nghĩ rằng có 5 ca khả thi $\rightarrow 15$ slots).
2. Người soạn thảo đã bỏ qua ca vi phạm sức chứa bãi đỗ xa của kịch bản `MC_REM_S0009` trong Mode B2, giả định Mode B2 đạt 100% (60 slots thay vì 57 slots).
3. Khi cộng dồn: $15 \text{ (Mode A)} + 60 \text{ (Mode B1)} + 60 \text{ (Mode B2)} + 20 \text{ (Mode C1)} + 20 \text{ (Mode C2)} = \mathbf{175\text{ slots}}$.
4. Sau đó, khi copy `execution_ledger_summary.json` vào Mục 3, họ giữ nguyên số liệu thật của ledger là 166 và 54, nhưng lại tự viết thêm dòng chú thích sai: *"Tất cả thuộc về Mode A"* (trong khi thực tế có 51 ca từ Mode A và 3 ca từ Mode B2).

**Kết luận kiểm toán:**  
Dữ liệu ledger thô và mã nguồn runner hoàn toàn chính xác và trung thực. Không có bất kỳ lỗi lập trình nào trong khâu tổng hợp ledger. Lỗi hoàn toàn nằm ở khâu soạn thảo bảng báo cáo Markdown bằng tay và đã được đính chính triệt để tại tài liệu này.
