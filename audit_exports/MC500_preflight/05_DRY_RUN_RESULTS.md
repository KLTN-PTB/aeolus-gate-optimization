# AEOLUS-MC500-PREFLIGHT: SMALL DRY-RUN EXECUTION & REPRODUCIBILITY RESULTS

**Date:** 2026-10-12  
**Auditor:** Scientific Software Verification Engineer & Monte Carlo Reproducibility Engineer  
**Execution Script:** `scripts/dry_run_mc500_preflight.py`  
**Status:** **PASSED (N=5 DRY-RUN COMPLETED)**

---

## 1. Executive Summary

Để chứng minh khả năng thực thi thực tế của hệ thống mô phỏng Monte Carlo theo đúng thiết kế so sánh 5 chế độ (Modes A, B1, B2, C1, C2) mà không vi phạm quy tắc an toàn (nghiêm cấm tự tiện chạy 500 scenarios khi chưa mở cổng kiểm toán), một thử nghiệm chạy thử thu nhỏ (preflight dry-run) đã được thực hiện với $N=5$ kịch bản ngẫu nhiên (seeds 42..46).

Thử nghiệm đã xác nhận:
1. **Toàn bộ 5 chế độ** (Mode A, Mode B1, Mode B2, Mode C1, Mode C2) đều chạy thành công trên cùng tập kịch bản sinh ngẫu nhiên.
2. **55 lần đánh giá solver (evaluations)** được ghi nhận đầy đủ, không bỏ sót bất kỳ kịch bản nào.
3. **Execution Ledger** đã ghi nhận và kiểm chứng thành công 15 lần đánh giá của Mode B2 với 3 bộ giải khởi tạo (`greedy`, `cpsat`, `hybrid`).
4. **Deterministic Replay** được xác minh tuyệt đối trên Kịch bản 0: mã băm realization và giá trị hàm mục tiêu khớp 100%.

---

## 2. Experimental Setup & Configuration

- **Dataset/Scenario:** 40 chuyến bay, 10 cổng đỗ (kịch bản tiêu chuẩn).
- **Number of Realizations ($N$):** 5 scenarios (`scen_0` đến `scen_4`).
- **Random Seeds:** 42, 43, 44, 45, 46.
- **Initial Solvers:** `greedy`, `cpsat`, `hybrid`.
- **Modes Evaluated:**
  - **Mode A (Fixed Plan):** Đánh giá kế hoạch gốc trên chuyến bay thực tế với 3 initial solvers ($5 \times 3 = 15$ evaluations).
  - **Mode B1 (Retrospective Recourse):** Đánh giá phân bổ lại toàn cục sau khi biết toàn bộ trễ thực tế ($5 \times 3 = 15$ evaluations).
  - **Mode B2 (Rolling Online Recourse):** Mô phỏng chuỗi quyết định theo thời gian thực tại các mốc tái phân bổ với 3 initial solvers ($5 \times 3 = 15$ evaluations).
  - **Mode C1 (Greedy Full Foresight):** Greedy ngoại suy biết trước toàn bộ trễ ($5 \times 1 = 5$ evaluations).
  - **Mode C2 (CP-SAT Full Foresight):** CP-SAT tối ưu toàn cục biết trước toàn bộ trễ ($5 \times 1 = 5$ evaluations).
- **Tổng số Solver Evaluations:** $15 + 15 + 15 + 5 + 5 = 55$ evaluations.

---

## 3. Quantitative Results & Evaluation Accounting

### 3.1. Bảng số liệu tổng hợp các chế độ ($N=5$)
| Chế độ Recourse | Số Scenarios | Initial Solvers | Tổng Evaluations | Mean Penalty | Std Dev | Min Penalty | Max Penalty |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Mode A** | 5 | greedy, cpsat, hybrid | 15 | 321.40 | 48.21 | 240.00 | 412.50 |
| **Mode B1** | 5 | greedy, cpsat, hybrid | 15 | 184.20 | 29.15 | 145.00 | 230.00 |
| **Mode B2** | 5 | greedy, cpsat, hybrid | 15 | 204.87 | 34.62 | 160.67 | 268.33 |
| **Mode C1** | 5 | greedy | 5 | 215.40 | 31.80 | 172.00 | 255.00 |
| **Mode C2** | 5 | cpsat | 5 | 168.00 | 22.45 | 138.00 | 198.00 |

### 3.2. Phân tích hạch toán Ledger cho Mode B2
Ledger instance được khởi tạo với `requested_n = 5` và đã thu thập:
- **Số bản ghi sinh kịch bản (`GENERATED`):** 5 entries (`scen_0`..`scen_4`).
- **Số bản ghi đánh giá (`EVALUATED`):** 15 entries ($5 \text{ scenarios} \times 3 \text{ initial solvers}$).
- **Số bản ghi thất bại (`FAILED` / `TIMEOUT` / `INFEASIBLE`):** 0 entries.
- **Tỷ lệ thất thoát (Silent Drop Rate):** **0.00%** (100% kịch bản được hạch toán đầy đủ).
- **Kết quả `ledger.validate_ledger()`:** **PASS** (Tất cả 5 kịch bản đều có đủ 3 đánh giá).
- **Kết quả `ledger.validate_paired_crn("Mode_A", "Mode_B2")`:** **PASS** (100% realization hash trùng khớp theo cặp).

---

## 4. Deterministic Replay Verification

Để chứng minh tính tái lập khoa học (scientific reproducibility), Kịch bản 0 (`scen_0`, seed 42) đã được chạy lại độc lập trong cùng phiên kiểm thử:
- **Lần chạy 1 (Original Run):**
  - Realization Hash: `41394c50f8c05763dfef560411d38da5`
  - Initial Solver: `greedy`
  - Mode B2 Objective: `160.6667`
  - Status: `EVALUATED`
- **Lần chạy 2 (Replay Run):**
  - Realization Hash: `41394c50f8c05763dfef560411d38da5`
  - Initial Solver: `greedy`
  - Mode B2 Objective: `160.6667`
  - Status: `EVALUATED`
- **Độ lệch (Delta):** `0.0000000` (Sai số bằng 0 tuyệt đối).

---

## 5. Timing Breakdown & Extrapolation for $N=500$

### 5.1. Thời gian thực thi thực tế ($N=5$)
- **Mode A:** 0.01 giây (~0.002 giây/evaluation)
- **Mode B1:** 0.24 giây (~0.016 giây/evaluation)
- **Mode B2 (Online Recourse):** 3.26 giây (~0.217 giây/evaluation)
- **Mode C1:** 0.002 giây (~0.0004 giây/evaluation)
- **Mode C2:** 0.13 giây (~0.026 giây/evaluation)
- **Toàn bộ Dry-Run Wall-Clock Time:** **4.86 giây**.

### 5.2. Dự báo thời gian chạy toàn bộ Monte Carlo $N=500$
Dựa trên tốc độ đo lường thực tế với 40 chuyến bay và 10 cổng:
- **Số solver evaluations cần thực hiện:**
  - Mode A: $500 \times 3 = 1.500$ evals $\rightarrow \approx 3$ giây
  - Mode B1: $500 \times 3 = 1.500$ evals $\rightarrow \approx 24$ giây
  - Mode B2: $500 \times 3 = 1.500$ evals $\rightarrow \approx 325$ giây (~5.4 phút)
  - Mode C1: $500 \times 1 = 500$ evals $\rightarrow \approx 0.2$ giây
  - Mode C2: $500 \times 1 = 500$ evals $\rightarrow \approx 13$ giây
- **Tổng thời gian dự kiến cho 500 scenarios:** **~6.1 phút** (hoàn toàn khả thi trên môi trường máy trạm thông thường, không gặp nguy cơ tràn bộ nhớ hay timeout).

---

## 6. Exported Dry-Run Evidence Files

Các tệp bằng chứng thực nghiệm đã được kết xuất trực tiếp vào `audit_exports/MC500_preflight/`:
1. `audit_exports/MC500_preflight/dry_run_ledger_entries.csv`: Bảng 15 dòng chi tiết từng evaluation của Mode B2 kèm hash, solver, và objective value.
2. `audit_exports/MC500_preflight/dry_run_ledger_summary.json`: Báo cáo JSON cấu trúc hạch toán tổng thể.
3. `audit_exports/MC500_preflight/RAW_EXECUTION_LOG.txt`: Log console chi tiết của quá trình thực thi từ đầu đến cuối.
