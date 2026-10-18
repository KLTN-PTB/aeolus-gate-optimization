# 04. N=5 AND N=20 PILOT RUN RECONCILIATION & NUMERICAL AUDIT

**Protocol Reference:** AEOLUS-MC500-TOPOLOGY-GATE  
**Directory Isolation:** `artifacts/remediation/monte_carlo_mc500/topology_corrected/`  
**Base Seed:** 202601 (Canonical Deployment Seed)  
**Historical Artifacts:** Frozen baseline pilots `pilot_n5_run1`, `pilot_n20` preserved strictly untouched.  

---

## 1. Execution Ledger Accounting Comparison

| Chỉ số Kế toán Ledger | Pilot $N=5$ (Topology Corrected) | Pilot $N=20$ (Topology Corrected) | Sai lệch bảo toàn |
| :--- | :---: | :---: | :---: |
| **Realizations Yêu cầu ($N$)** | 5 | 20 | 0 |
| **Realizations Đã sinh ($N_{gen}$)** | 5 | 20 | 0 |
| **Lỗi phát sinh Realization** | 0 | 0 | 0 |
| **Slots Đánh giá Dự kiến ($11 \times N$)** | **55** | **220** | 0 |
| **Slots Đánh giá Hoàn tất** | **55** | **220** | 0 |
| **Slots Bị thiếu (Missing Slots)** | 0 | 0 | 0 |
| **Lỗi thực thi (Evaluation Failures)** | 0 | 0 | 0 |
| **Quá thời gian (Timeouts)** | 0 | 0 | 0 |
| **Tổng Lượt Khả thi (Feasible)** | **40** | **169** | 0 |
| **Tổng Lượt Không khả thi (Infeasible)**| **15** | **51** | 0 |
| **Phương trình bảo toàn tổng** | $40 + 15 = 55$ (PASS) | $169 + 51 = 220$ (PASS) | 0 |

---

## 2. Phân rã Khả thi theo Từng Chế độ & Thuật toán

### 2.1. Pilot $N=5$ (55 slots)
- **Mode A (Kế hoạch cố định không ứng phó):**
  - Greedy: $0/5$ khả thi ($5$ không khả thi do va chạm trễ).
  - CP-SAT: $0/5$ khả thi ($5$ không khả thi).
  - Hybrid: $0/5$ khả thi ($5$ không khả thi).
  - Tổng Mode A: $0/15$ khả thi ($15$ không khả thi).
- **Mode B1 (Ứng phó Hindsight Retrospective):** $15/15$ khả thi ($100\%$).
- **Mode B2 (Ứng phó Online Recourse Causal):** $15/15$ khả thi ($100\%$).
- **Mode C1 (Greedy Foresight Heuristic):** $5/5$ khả thi ($100\%$).
- **Mode C2 (CP-SAT Optimal Oracle):** $5/5$ khả thi ($100\%$).
- **Tổng cộng $N=5$:** $0 + 15 + 15 + 5 + 5 = 40$ khả thi $/ 55$ slots ($72.73\%$).

### 2.2. Pilot $N=20$ (220 slots)
- **Mode A (Kế hoạch cố định không ứng phó):**
  - Greedy: $3/20$ khả thi ($17$ không khả thi).
  - CP-SAT: $3/20$ khả thi ($17$ không khả thi).
  - Hybrid: $3/20$ khả thi ($17$ không khả thi).
  - Tổng Mode A: $9/60$ khả thi ($51$ không khả thi).
- **Mode B1 (Ứng phó Hindsight Retrospective):** $60/60$ khả thi ($100\%$).
- **Mode B2 (Ứng phó Online Recourse Causal):** $60/60$ khả thi ($100\%$) — *Trước sửa: $57/60$ do thiếu stand*.
- **Mode C1 (Greedy Foresight Heuristic):** $20/20$ khả thi ($100\%$).
- **Mode C2 (CP-SAT Optimal Oracle):** $20/20$ khả thi ($100\%$).
- **Tổng cộng $N=20$:** $9 + 60 + 60 + 20 + 20 = 169$ khả thi $/ 220$ slots ($76.82\%$).

---

## 3. Tỷ lệ Thất bại & Mẫu số Hợp đồng (Rate Denominators)

Theo quy định hợp đồng kỹ thuật nghiêm ngặt của dự án Aeolus:
1. **`generation_failure_rate`:** Mẫu số bắt buộc là $N$ requested realizations.
   - $N=5$: $\frac{0}{5} = 0.0\%$
   - $N=20$: $\frac{0}{20} = 0.0\%$
2. **`evaluation_failure_rate`:** Mẫu số bắt buộc là $11 \times N$ expected evaluations (KHÔNG PHẢI $N$).
   - $N=5$: $\frac{0}{55} = 0.0\%$ (mẫu số đúng $55$).
   - $N=20$: $\frac{0}{220} = 0.0\%$ (mẫu số đúng $220$).
3. **`composite_feasible_rate`:** Mẫu số là completed evaluations.
   - $N=5$: $\frac{40}{55} = 72.73\%$
   - $N=20$: $\frac{169}{220} = 76.82\%$

---

## 4. Thống kê Chi phí Mục tiêu (Objective Function Statistics)

| Chế độ Thực nghiệm | Thuật toán Solver | $N=5$ Chi phí TB | $N=5$ Độ lệch chuẩn | $N=20$ Chi phí TB | $N=20$ Độ lệch chuẩn |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Mode A** | Deterministic Greedy | 1107.32 | 9.67 | 1707.27 | 1144.41 |
| **Mode A** | CP-SAT Solver | 1107.32 | 9.67 | 1707.27 | 1144.41 |
| **Mode A** | Hybrid Solver | 1107.32 | 9.67 | 1707.27 | 1144.41 |
| **Mode B1** | Deterministic Greedy | 127.32 | 14.32 | 139.77 | 31.00 |
| **Mode B1** | CP-SAT Initial | 127.32 | 14.32 | 139.77 | 31.00 |
| **Mode B1** | Hybrid Initial | 127.32 | 14.32 | 139.77 | 31.00 |
| **Mode B2** | Causal Online (Greedy init) | 133.32 | 20.31 | 153.27 | 62.96 |
| **Mode B2** | Causal Online (CPSat init) | 133.32 | 20.31 | 153.27 | 62.96 |
| **Mode B2** | Causal Online (Hybrid init) | 133.32 | 20.31 | 153.27 | 62.96 |
| **Mode C1** | Foresight Greedy | 127.32 | 14.32 | 139.77 | 31.00 |
| **Mode C2** | Mathematical Oracle (CP-SAT)| **117.32** | **16.63** | **124.27** | **27.87** |

---

## 5. Xác minh Tái lập Tuyệt đối (Deterministic Replay Verification)

Hai lượt chạy độc lập $N=5$ (`pilot_n5_run1` và `pilot_n5_run2`) trên cùng seed $202601$ được so sánh từng bản ghi:
- **Số lượng cột khớp tuyệt đối:** $100\%$ các trường nội dung khoa học (`scenario_id`, `realization_hash`, `initial_plan_solver`, `recourse_mode`, `solver_status`, `composite_feasible`, `objective_value`).
- **Sai lệch nội dung khoa học:** Đúng **0** sai lệch.
- **Thời gian chạy trung bình:** Run 1 = $4.19$ giây; Run 2 = $4.27$ giây.
- **Pilot $N=20$:** Hoàn tất toàn bộ 20 kịch bản và 220 đánh giá trong $10.78$ giây (tương đương $\approx 49$ ms / evaluation slot), đảm bảo hiệu năng tối ưu sẵn sàng cho $N=500$.
