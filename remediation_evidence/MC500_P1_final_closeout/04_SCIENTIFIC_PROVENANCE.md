# AEOLUS-MC500-P1: SCIENTIFIC PROVENANCE & THEORETICAL CLAIMS VERIFICATION

**Date:** 2026-10-12  
**Auditor:** Scientific Reproducibility Engineer & Python Integration Verification Engineer  
**Sprint:** AEOLUS-MC500-P1-CLOSEOUT  
**Target Architecture:** Monte Carlo Simulation Pipeline, CRN Realizations, Information Regimes  
**Status:** **PASSED / SCIENTIFIC INTEGRITY FULLY CONFIRMED**

---

## 1. Executive Summary

Nhằm đảm bảo luận điểm khoa học của khóa luận thạc sĩ/tiến sĩ đứng vững trước mọi phản biện độc lập, tài liệu này tiến hành xác minh tính minh bạch nguồn gốc (Scientific Provenance) và chuẩn hóa ngôn từ học thuật (Scientific Claims) cho toàn bộ hệ thống mô phỏng Monte Carlo trước khi chạy quy mô lớn $N=500$.

---

## 2. Provenance Integrity Checklist

| Tiêu chuẩn Kiểm chứng Nguồn gốc | Trạng thái | Bằng chứng Thực nghiệm & Đối chiếu |
|---|:---:|---|
| **1. Run Source Hash khớp Current Source** | **VERIFIED (PASS)** | `simulation_manifest.json` trong cả hai pilot N=5 và N=20 ghi nhận `source_hash`: `49a78ecbac8313240c54713d7c30e11da9ce1b15243a959e6c314ee045208cf4`, khớp 100% với SHA-256 trên working tree của `src/simulation/monte_carlo_engine_v2.py`. |
| **2. Config Hash bao phủ toàn diện** | **VERIFIED (PASS)** | `config_hash` (`f44be71f5ad599b5d8fbf005b3b3f54d4e0246f6bcfe73be7142f2c527b37d93`) bao phủ 10 tham số cốt lõi: `n_flights` (120), `n_contact_gates` (25), `n_remote_stands` (5), `finite_remote_capacity` (5), `enforce_remote_capacity` (True), `allow_unbounded_overflow` (False), `time_limit_seconds` (1.5s), `random_seed` (202601), `copula_rho` (0.45), `base_seed` (202601). Ngoài ra, các tham số phân phối biên Student-t và Copula được lưu đầy đủ trong manifest. |
| **3. Source Manifest bao phủ toàn bộ thành phần lõi** | **VERIFIED (PASS)** | Bao gồm đầy đủ: Runner (`run_g2_monte_carlo_remediation.py`), Engine (`monte_carlo_engine_v2.py`), CP-SAT Solver (`cp_sat_solver.py`), Greedy Solver (`greedy_solver.py`), Hybrid Solver (`hybrid_solver.py`), SA Engine (`annealer.py`), Evaluator (`domain.py`, `evaluation.py`), Config (`config.py`), Scenario Generator (`monte_carlo_engine_p09.py`, `scalability_scenario.py`). |
| **4. Invariant CRN: Mỗi Realization có cùng Hash trên mọi Mode** | **VERIFIED (PASS)** | Kiểm chứng Python trên toàn bộ 220 dòng của N=20 và 55 dòng của N=5: Mỗi `scenario_id` có **đúng 1 giá trị `realization_hash` duy nhất** trên toàn bộ 11 slots đối chứng (Mode A [3 solvers], Mode B1 [3 solvers], Mode B2 [3 solvers], Mode C1, Mode C2). |
| **5. Trạng thái Nghiệm Mode C2 là OPTIMAL** | **VERIFIED (PASS)** | Kiểm chứng 100% bản ghi Mode C2 Foresight CP-SAT: Đều có `solver_status = "OPTIMAL"` (20/20 bản ghi tại N=20, 5/5 bản ghi tại N=5). Không có trường hợp nào dừng ở mức `FEASIBLE` do hết thời gian (timeout). |
| **6. Khẳng định Bản chất Dữ liệu Thử nghiệm** | **VERIFIED (PASS)** | Bộ dữ liệu được ghi nhận chính xác là **Synthetic Parametric Benchmark** (`SCEN_P09_CANONICAL_120`), sinh từ phân phối biên Student-t (Arrival: $\mu=5, \sigma=18, \nu=4.5$; Departure: $\mu=8, \sigma=22, \nu=4.0$) kết hợp Gaussian Copula ($\rho=0.45$). Không giả mạo là lịch sử khai thác thực tế nếu chưa qua pipeline G4. |
| **7. Tính Liên tục Kịch bản: N=20 là tập con tiền tố của N=500** | **VERIFIED (PASS)** | Thực nghiệm sinh đối chiếu đã chứng minh: 20 kịch bản đầu tiên của đợt chạy $N=500$ trùng khớp **100% bit-for-bit** về `realization_hash` và ma trận trễ so với 20 kịch bản của đợt chạy $N=20$ khi cùng sử dụng base seed `202601`. |

---

## 3. Chuẩn hóa Ngôn từ Khoa học (Scientific Claims Errata)

Để tránh các sai lầm học thuật phổ biến trong lý thuyết tối ưu ngẫu nhiên (Stochastic Programming):

### A. Không gọi Empirical Heuristic Gap là Formal EVPI:
- **Định nghĩa chuẩn toán học:** Expected Value of Perfect Information (EVPI) trong quy hoạch ngẫu nhiên 2 giai đoạn đòi hỏi bài toán recourse giai đoạn 2 phải được giải đến **nghiệm tối ưu toàn cục tuyệt đối (Global Mathematical Optimum)** trên toàn bộ không gian biến cố.
- **Thực tế trong hệ thống:**
  - Mode B2 sử dụng chính sách trực tuyến suy diễn tiến trình (`Rolling Online Recourse`) với heuristic tham lam có ghi nhận chi phí phạt tràn. Đây không phải là chính sách quy hoạch động tối ưu toàn cục (Bellman-optimal policy).
  - Mode C1 sử dụng thuật toán tham lam biết trước tương lai (`Heuristic Greedy Foresight`).
- **Quy chuẩn tuyên bố:** Khoảng cách giữa Mode B2 và Mode C2/C1 chỉ được gọi là **Empirical Information Value Gap** hoặc **Recourse Policy Heuristic Gap**, tuyệt đối **không được tuyên bố là Formal Theoretical EVPI**.

### B. Không gọi kết quả FEASIBLE là proven OPTIMAL:
- Trong bảng kết quả:
  - Mode A: Trạng thái nghiệm ghi nhận `FIXED_PLAN` (chỉ đánh giá tính khả thi thụ động).
  - Mode B1: Trạng thái nghiệm là `FEASIBLE` (nghiệm khả thi từ giải thuật tái phân bổ toàn cục Greedy).
  - Mode B2: Trạng thái nghiệm là `ONLINE_FEASIBLE` hoặc `ONLINE_INFEASIBLE_NO_CAPACITY`.
  - Mode C1: Trạng thái nghiệm là `FEASIBLE` (nghiệm khả thi từ giải thuật tham lam).
  - **CHỈ DUY NHẤT Mode C2** mới được cấp cờ `is_optimal_proven = True` và `solver_status = "OPTIMAL"` do được chứng minh bằng chứng chỉ tối ưu của Google OR-Tools CP-SAT Solver.
