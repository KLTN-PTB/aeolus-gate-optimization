# AEOLUS-MC500-P1: PILOT N=5 EXPERIMENTAL EXECUTION & REPRODUCIBILITY RESULTS

**Date:** 2026-10-12  
**Auditor:** Principal Scientific Software Engineer, Monte Carlo Reproducibility Engineer  
**Dataset Scale:** 120 flights, 25 contact gates, 5 remote stands (`SCEN_P09_CANONICAL_120`)  
**Base Random Seed:** `202601`  
**Execution Runs:**
- Run 1: `artifacts/remediation/monte_carlo_mc500/pilot_n5_run1/` (`run_id: mc500_20261012_124032_b425ab`)
- Run 2 (Replay): `artifacts/remediation/monte_carlo_mc500/pilot_n5_run2/` (`run_id: mc500_20261012_124044_b6beb1`)
**Status:** **PASSED / 100% CONSERVATION & REPRODUCIBILITY VERIFIED**

---

## 1. Executive Summary

Thử nghiệm **Pilot N=5** đã được thực thi thành công thông qua production runner chính thức [`scripts/run_g2_monte_carlo_remediation.py`](file:///D:/Study/Code/Python/Aelous/scripts/run_g2_monte_carlo_remediation.py) với cấu hình chuẩn của khóa luận:
- Sinh ra chính xác **5 stochastic realizations**.
- Thực thi đầy đủ **55 solver evaluations** qua 5 chế độ đối chứng (Mode A, B1, B2, C1, C2).
- Không có bất kỳ kịch bản nào bị bỏ sót (Zero silent drops, $N_{\text{missing\_evaluations}} = 0$).
- Kiểm chứng tái lập tất định (Deterministic replay) giữa Run 1 và Run 2 cho độ lệch $\Delta = 0.000000$ trên toàn bộ 55 evaluations.

---

## 2. Quantitative Results & Evaluation Statistics (Computed from Raw CSV)

Số liệu dưới đây được tính toán trực tiếp từ `execution_ledger_entries.csv`:

| Recourse Mode | Initial Solver / Variant | Evaluations | Mean Objective | Std Dev | Min Objective | Max Objective | Trạng thái Khả thi |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **MODE_A** | `Greedy` | 5 | **1,107.32** | 8.65 | 1,095.55 | 1,120.67 | Infeasible (Buffer penalty) |
| **MODE_A** | `CPSat` | 5 | **1,107.32** | 8.65 | 1,095.55 | 1,120.67 | Infeasible (Buffer penalty) |
| **MODE_A** | `Hybrid` | 5 | **1,107.32** | 8.65 | 1,095.55 | 1,120.67 | Infeasible (Buffer penalty) |
| **MODE_B1** | `Greedy` | 5 | **127.32** | 12.80 | 115.55 | 150.67 | Feasible |
| **MODE_B1** | `CPSat` | 5 | **127.32** | 12.80 | 115.55 | 150.67 | Feasible |
| **MODE_B1** | `Hybrid` | 5 | **127.32** | 12.80 | 115.55 | 150.67 | Feasible |
| **MODE_B2** | `Greedy` | 5 | **133.32** | 18.16 | 111.00 | 160.67 | Feasible |
| **MODE_B2** | `CPSat` | 5 | **133.32** | 18.16 | 111.00 | 160.67 | Feasible |
| **MODE_B2** | `Hybrid` | 5 | **133.32** | 18.16 | 111.00 | 160.67 | Feasible |
| **MODE_C1** | `ForesightGreedy` | 5 | **127.32** | 12.80 | 115.55 | 150.67 | Feasible |
| **MODE_C2** | `ForesightCPSat` | 5 | **117.32** | 8.65 | 105.55 | 130.67 | Feasible (Optimal Oracle) |

### Nhận xét về Thứ bậc Giá trị Mục tiêu (Mathematical Hierarchy):
$$\mathbf{\text{Mode C2 (Oracle: 117.32)} \le \text{Mode B1 (Hindsight: 127.32)} \le \text{Mode B2 (Online: 133.32)} \ll \text{Mode A (Fixed: 1107.32)}}$$
Thứ bậc này phản ánh chính xác bản chất lý thuyết quyết định:
1. **Mode C2** đạt cận dưới tối ưu toán học thấp nhất vì biết trước tương lai hoàn hảo và tối ưu toàn cục.
2. **Mode B1** tái phân bổ toàn cục sau khi biết toàn bộ trễ nên cho nghiệm tốt hơn Mode B2.
3. **Mode B2** chỉ dùng thông tin nhân quả tại thời điểm hiện tại nên chi phí phạt (133.32) cao hơn Mode B1 một lượng nhỏ nhưng vượt trội hoàn toàn so với việc giữ nguyên kế hoạch ban đầu (Mode A: 1,107.32).

---

## 3. Rigorous Accounting Ledger Summary (`execution_ledger_summary.json`)

```json
{
  "run_id": "mc500_20261012_124032_b425ab",
  "accounting": {
    "n_requested": 5,
    "n_generated": 5,
    "n_generation_failures": 0,
    "n_evaluated": 55,
    "n_evaluation_failures": 0,
    "n_timeouts": 0,
    "n_feasible": 40,
    "n_infeasible": 15,
    "n_requested_realizations": 5,
    "n_generated_realizations": 5,
    "n_expected_evaluations": 55,
    "n_completed_evaluations": 55,
    "n_feasible_evaluations": 40,
    "n_infeasible_evaluations": 15,
    "n_missing_evaluations": 0
  },
  "rates": {
    "generation_failure_rate": { "numerator": 0, "denominator": 5, "rate": 0.0 },
    "evaluation_failure_rate": { "numerator": 0, "denominator": 5, "rate": 0.0 },
    "composite_feasible_rate": { "numerator": 40, "denominator": 55, "rate": 0.7272727272727273 }
  },
  "total_generation_records": 5,
  "total_evaluation_records": 55
}
```

---

## 4. Real Wall-Clock Timing Breakdown

Đo lường thời gian thực thi end-to-end từ `simulation_manifest.json`:
- **Mode A (15 evaluations):** 0.0241 giây (~1.6 ms/eval)
- **Mode B1 (15 evaluations):** 0.0665 giây (~4.4 ms/eval)
- **Mode B2 (15 evaluations):** 0.0834 giây (~5.6 ms/eval)
- **Mode C1 (5 evaluations):** 0.0210 giây (~4.2 ms/eval)
- **Mode C2 CP-SAT Oracle (5 evaluations):** 2.0588 giây (~411.8 ms/eval)
- **Tổng thời gian toàn bộ Pipeline:** **4.4737 giây**.

---

## 5. Deterministic Replay Verification

Đối chiếu 55 dòng kết quả giữa `pilot_n5_run1` và `pilot_n5_run2`:
- Realization hashes: **Trùng khớp 100%**.
- Objective values:
  $$\max | \text{Obj}_{\text{run1}} - \text{Obj}_{\text{run2}} | = 0.000000$$
- Trạng thái nghiệm và solver status: **Trùng khớp 100%**.
