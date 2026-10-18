# BÁO CÁO 01: XÁC MINH VÀ ĐÓNG BĂNG DỮ LIỆU THÔ MC500
## AEOLUS-G12C — SCIENTIFIC RECONCILIATION & HISTORICAL AUDIT

**Dự án:** Aeolus Gate Optimization  
**Giai đoạn:** G12C — Scientific Reconciliation, Historical Regression & Thesis Readiness  
**Run ID Chính thức:** `mc500_20261012_173538_afa5db`  
**Hạt giống ngẫu nhiên (Seed):** `202601`  
**Nhánh Git & Commit:** `remediation/g7-regression` (`c95caef53808a561b1a7d3a5a09399cc52f754f5`)  
**Thư mục Artifacts Bất biến:** `artifacts/remediation/monte_carlo_mc500/mc500_20261012_173538_afa5db/`  

---

## 1. ĐỊNH DANH VÀ BẢO TOÀN NGUỒN GỐC THÍ NGHIỆM CHÍNH THỨC

Toàn bộ artifacts thuộc đợt chạy chính thức `mc500_20261012_173538_afa5db` được đóng băng tuyệt đối (immutable), không bị ghi đè hay sửa đổi.

### 1.1. Bảng Kiểm Tra Mã Băm Checksum Các Tệp Kết Quả Thô
Mã băm SHA-256 được tính toán trực tiếp từ các tệp trên đĩa:

| Tên Tệp Dữ Liệu Thô | Kích thước (Bytes) | SHA-256 Checksum Thực Tế | Trạng Thái Toàn Vẹn |
|:---|:---:|:---|:---:|
| `execution_ledger_entries.csv` | 1,499,490 | `6b186e3c950af416bd66ef1b5e42c48c4d74aa5692fb06228cec18125eb0c108` | **FROZEN / PASS** |
| `execution_ledger_generation.csv` | 138,525 | `b567fe8a78daf070472927135c38a104434dac05c6796c1531027fd1b43671a9` | **FROZEN / PASS** |
| `execution_ledger_summary.json` | 980 | `ee10fd9544121e8e26ac7276c7c80b96d5e11ba20a509e9bb739b8cf63a99a60` | **FROZEN / PASS** |
| `gate_inventory.json` | 7,032 | `362728e8b70ab6258de9b6486588cfecf279dc5242f7fd2dd8674f20107421ab` | **FROZEN / PASS** |
| `fixed_plan_results.csv` | 338,107 | `0654921e65b0cd75f9b6fb8eacca91014ceacd72c76d7cd5f21e8bc56efd72cf` | **FROZEN / PASS** |
| `recourse_b1_retrospective_results.csv` | 383,111 | `d2e8f051f5d6032f04e17f6189d1b4e141cacdaccf3f302d9cde3353ac13354f` | **FROZEN / PASS** |
| `recourse_b2_online_results.csv` | 396,683 | `f091254a89888e02db928c870acf7ad6f90959ec26489678beb10d71fb65cb5c` | **FROZEN / PASS** |
| `foresight_c1_greedy_results.csv` | 126,159 | `2d6b957f959bddde258f2f3e62b03f6e692283d1089ed928e48ae948a715c398` | **FROZEN / PASS** |
| `foresight_c2_optimal_results.csv` | 124,653 | `9256da975e606f5f5dadcf1ab2d2978f53f96616599389e7d3455a53b7fa644b` | **FROZEN / PASS** |
| `failures.json` | 537 | `f4510833b209a6f5fde617e09d81cdd21c84fc16bd2bf0c6a5c3ad5ae0b10972` | **FROZEN / PASS** |
| `paired_comparison.csv` | 1,207 | `3b47fb04ce04fe744d63be75090cb9acdd43f07cba4bd863fb17a249d21ea7d2` | **FROZEN / PASS** |
| `scenario_index.csv` | 55,797 | `fcd9a5d7cf4055ff1c5744944e798c82996a6537248edb807f369e005669d1ce` | **FROZEN / PASS** |
| `simulation_manifest.json` | 2,707 | `76ef322030e6366f7d125f1d59754c8bf4b078e9fdb89407658f850456281237` | **FROZEN / PASS** |
| `statistical_summary.json` | 15,651 | `533b214cc6e72f20bc5c95514594c9c37a32102af8de327b574095ffd7620e36` | **FROZEN / PASS** |

---

## 2. KIỂM TOÁN TÁI LẬP TỪ DỮ LIỆU THÔ (RE-COMPUTED RAW METRICS)

Toàn bộ các số liệu dưới đây được tính toán trực tiếp bằng script kiểm toán độc lập `scripts/verify_g12c_mc500_raw.py` dựa trên các tệp CSV gốc:

### 2.1. Phân Biệt Thực Thể Kịch Bản và Lượt Đánh Giá
- **Số lượng kịch bản ngẫu nhiên độc lập ($N_{\text{scenarios}}$):** Đúng **500 realizations**.
- **Mã băm kịch bản duy nhất (`realization_hash`):** 500 giá trị băm duy nhất ($0$ va chạm hash).
- **Tổng số lượt đánh giá bộ giải (Evaluation Slots):** **5,500 slots** ($500 \text{ scenarios} \times 11 \text{ canonical protocol slots/scenario}$).
- **Số lượng lượt trên mỗi kịch bản:** Đúng **11 slots** cho toàn bộ 500 kịch bản ($\min = 11, \max = 11$).
- **Khóa chính duy nhất (Primary Key):** Cặp `(run_id, scenario_id, recourse_mode, initial_plan_solver)` có $5,500$ dòng duy nhất, **0 dòng trùng lặp (0 duplicates)**.

> [!NOTE]
> **Lưu ý về tính độc lập thống kê:**
> $N=500$ là cỡ mẫu của các biến cố ngẫu nhiên ngoại sinh (realizations). Trong mỗi kịch bản, 3 bộ giải khởi tạo (Greedy, CP-SAT, Hybrid) được đánh giá song song trên cùng một tập độ trễ nhận được (Common Random Numbers - CRN). Do đó, 5,500 evaluations không phải là 5,500 mẫu độc lập mà gồm 11 nhóm có tương quan phụ thuộc trong từng kịch bản.

---

### 2.2. Kiểm Toán Tính Khả Thi Phân Bổ (Feasibility Accounting)

| Chế độ Khắc phục (Recourse Mode) | Bộ giải Kế hoạch Ban đầu (Initial Solver) | Tổng Số Lượt Đánh Giá | Khả Thi (Feasible) | Không Khả Thi (Infeasible) | Tỷ Lệ Khả Thi (%) |
|:---|:---|:---:|:---:|:---:|:---:|
| **MODE_A (Fixed Plan)** | Greedy | 500 | 126 | 374 | 25.20% |
| **MODE_A (Fixed Plan)** | CP-SAT | 500 | 126 | 374 | 25.20% |
| **MODE_A (Fixed Plan)** | Hybrid | 500 | 126 | 374 | 25.20% |
| **MODE_B1 (Retrospective)** | Greedy | 500 | 500 | 0 | 100.00% |
| **MODE_B1 (Retrospective)** | CP-SAT | 500 | 500 | 0 | 100.00% |
| **MODE_B1 (Retrospective)** | Hybrid | 500 | 500 | 0 | 100.00% |
| **MODE_B2 (Online Recourse)** | Greedy | 500 | 500 | 0 | 100.00% |
| **MODE_B2 (Online Recourse)** | CP-SAT | 500 | 500 | 0 | 100.00% |
| **MODE_B2 (Online Recourse)** | Hybrid | 500 | 500 | 0 | 100.00% |
| **MODE_C1 (Foresight Greedy)** | ForesightGreedy | 500 | 500 | 0 | 100.00% |
| **MODE_C2 (Optimal Oracle)** | ForesightCPSat | 500 | 500 | 0 | 100.00% |
| **TỔNG CỘNG HỆ THỐNG** | — | **5,500** | **4,378** | **1,122** | **79.60%** |

- **Bảo toàn số học hoàn hảo:** $4,378 + 1,122 = 5,500$ (Sai lệch $= 0$).
- **Lỗi sinh kịch bản (Generation Failures):** $0 / 500$ ($0.0\%$).
- **Lỗi ngoại lệ thực thi (Evaluation Exceptions):** $0 / 5,500$ ($0.0\%$).
- **Solver Timeouts:** $0 / 5,500$ ($0.0\%$).

---

### 2.3. Bảng Giá Trị Thống Kê Hàm Mục Tiêu và Thời Gian Chạy Đã Được Kiểm Chứng (Verified Benchmark Values)

Các giá trị sau đây là căn cứ chuẩn mực bắt buộc cho toàn bộ báo cáo phân tích:

| Nhóm Đánh Giá | Cỡ Mẫu ($N$) | Mean Obj | Std Dev | Median (P50) | Min Obj | Max Obj | P90 Obj | P95 Obj | P99 Obj | CVaR90 | CVaR95 | Mean Runtime (ms) | P95 Runtime (ms) | Max Runtime (ms) |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Mode A (Greedy Init)** | 500 | 1469.17 | 1161.92 | 1109.96 | 80.92 | 6092.80 | **3106.27** | 3125.41 | **5106.08** | **3751.65** | 4388.35 | 1.51 ms | 1.59 ms | 2.94 ms |
| **Mode A (Toàn bộ 3 Solvers)** | 1,500 | 1469.17 | 1161.14 | 1109.96 | 80.92 | 6092.80 | **3106.27** | 3125.41 | **5106.08** | **3751.65** | 4388.35 | 1.50 ms | 1.58 ms | 2.94 ms |
| **Mode B1 (Toàn bộ 3 Solvers)** | 1,500 | 130.73 | 25.35 | 126.29 | 80.92 | 248.80 | 163.48 | 177.37 | 203.25 | 182.45 | 195.56 | 3.12 ms | 3.42 ms | 48.10 ms |
| **Mode B2 (Toàn bộ 3 Solvers)** | 1,500 | 139.49 | 44.51 | 132.30 | 80.92 | 536.23 | 175.67 | 195.30 | **356.02** | 230.98 | 275.67 | 3.95 ms | 4.19 ms | 7.50 ms |
| **Mode C1 (Foresight Greedy)** | 500 | 130.73 | 25.37 | 126.29 | 80.92 | 248.80 | 163.48 | 177.37 | 203.25 | 182.45 | 195.56 | 2.65 ms | 2.91 ms | 4.76 ms |
| **Mode C2 (Optimal Oracle)** | 500 | 120.39 | 16.61 | 118.12 | 80.92 | 179.30 | 142.89 | 149.94 | **165.79** | 153.27 | 160.23 | 360.26 ms | **443.26 ms** | **1572.82 ms** |

---

### 2.4. Xác Minh Xung Đột Cổng và Vi Phạm Buffer của Mode A
- **Số cặp xung đột vật lý tiếp xúc (Physical Contact Conflicts):**
  - Tổng số trên 1,500 lượt đánh giá Mode A: $2,046$ xung đột.
  - Trung bình trên mỗi kịch bản của 1 initial solver: **$1.364$ xung đột / kịch bản** ($682 / 500$).
  - Lưu ý diễn giải: $1.364$ là số xung đột trung bình trên **mỗi kịch bản**, KHÔNG PHẢI trên mỗi chuyến bay.
- **Số vi phạm vùng đệm (Buffer Violations):**
  - Tổng số vi phạm buffer trong dữ liệu thô: **0 vi phạm**.
  - Trung bình vi phạm buffer: **0.00**.
  - **Khẳng định khoa học:** Dữ liệu thô không có vi phạm buffer riêng biệt mà chỉ ghi nhận trực tiếp các xung đột đè chồng thời gian tiếp xúc (physical contact overlaps) bị phạt $1,000$ điểm mỗi lần. Tuyên bố trước đây về "vi phạm buffer 13.2 phút" là không có cơ sở trong raw CSV.

---

### 2.5. Xác Minh Bãi Đỗ Xa (Remote Stand Verification)
- **Tên định danh tài nguyên bãi đỗ xa thực tế:** `REMOTE_STAND_01` (Sức chứa $= 5.0$, loại `FINITE_REMOTE_STAND`), không phải `REMOTE_APRON_01`.
- **Số kịch bản có chuyến bay điều động ra bãi đỗ xa trong Mode B2:** Đúng **10 / 500 kịch bản** ($2.0\%$).
  - Danh sách kịch bản (scenario index): `9, 35, 152, 183, 205, 253, 336, 359, 413, 442`.
- **Xác minh kịch bản có số lượng điều động remote = 2:**
  - Kịch bản duy nhất có `remote_count = 2` và `max_concurrent_remote_usage = 2` là **`MC_REM_S0442` (kịch bản số 442)**.
  - Kịch bản `MC_REM_S0183` chỉ có `remote_count = 1` và `max_concurrent_remote_usage = 1`.
- **Đỉnh điểm đồng thời (Peak Concurrent Remote Usage):** Tối đa là **2 tàu bay đồng thời** tại `REMOTE_STAND_01` (trong kịch bản 442), hoàn toàn nằm trong giới hạn sức chứa 5 tàu bay. Số vi phạm sức chứa bãi đỗ xa bằng **0**.

---

### 2.6. Xác Minh Trạng Thái Tối Ưu Mode C2
- **Số kịch bản đạt chứng chỉ tối ưu toán học (Status `OPTIMAL`, `is_optimal_proven=True`):** **499 / 500 kịch bản** ($99.8\%$).
- **Số kịch bản dừng ở nghiệm khả thi do chạm giới hạn thời gian (Status `FEASIBLE`, `is_optimal_proven=False`):** **1 / 500 kịch bản** ($0.2\%$).
  - Kịch bản cụ thể: **`MC_REM_S0183` (scenario index 183)**.
  - Runtime ghi nhận: **1,572.82 ms** (chạm ngưỡng deadline 1,500 ms).
  - Giá trị hàm mục tiêu tìm được: **168.80** (Nghiệm khả thi chất lượng cao, đóng vai trò cận trên cho nghiệm tối ưu).
