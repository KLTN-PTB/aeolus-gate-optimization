# BÁO CÁO TOÀN DIỆN TIẾN TRÌNH & KẾT QUẢ THỰC HIỆN CÁC BƯỚC TỐI ƯU HÓA TỪ STEP 1 ĐẾN STEP 7
## DỰ ÁN AEOLUS GATE OPTIMIZATION RESEARCH

**Sân bay nghiên cứu**: Hartsfield–Jackson Atlanta International Airport (`DEST = KATL`)  
**Khung dữ liệu**: 2016 — 2024 (2016–2022 Development Rolling Folds, 2023 Development Model Selection / Benchmark, 2024 Historical Final Holdout)  
**Trạng thái hệ thống**: `POST_HOLDOUT_STABILIZED` & `FAIL_CLOSED_CERTIFIED`  
**Hệ thống phân tầng kiểm định**: **115 / 115 tests passed (100%)** trên 6 phân tầng kiểm định (9 test files)  
**Tình trạng 7 bước**: **7 / 7 STEPS PASSED (100%)**

---

## MỤC LỤC
1. [TỔNG QUAN TIẾN ĐỘ 7 BƯỚC (EXECUTIVE SUMMARY)](#1-tổng-quan-tiến-độ-7-bước-executive-summary)
2. [CHI TIẾT NỘI DUNG YÊU CẦU, THỰC THI & KẾT QUẢ TỪNG BƯỚC (STEPS 1 — 7)](#2-chi-tiết-nội-dung-yêu-cầu-thực-thi--kết-quả-từng-bước-steps-1--7)
   - [Step 1: Monte Carlo Audit & Correctness (Pha G)](#step-1-monte-carlo-audit--correctness-pha-g)
   - [Step 2: CP-SAT Objective Audit & Validity (Pha D)](#step-2-cp-sat-objective-audit--validity-pha-d)
   - [Step 3: SA Time-Limited Benchmark & Role Validation (Pha F)](#step-3-sa-time-limited-benchmark--role-validation-pha-f)
   - [Step 4: Holdout & Fold Guard Correction / Temporal Protocol (Pha H)](#step-4-holdout--fold-guard-correction--temporal-protocol-pha-h)
   - [Step 5: Dependence Contract Consistency / Phase C & H Sync](#step-5-dependence-contract-consistency--phase-c--h-sync)
   - [Step 6: Aircraft Turn / Timeline Semantics Audit](#step-6-aircraft-turn--timeline-semantics-audit)
   - [Step 7: Broader Development End-to-End Benchmark](#step-7-broader-development-end-to-end-benchmark)
3. [BẢNG TỔNG HỢP SỐ LIỆU ĐỐI SOÁNH THỰC NGHIỆM ĐA PHƯƠNG PHÁP (STEP 7 BENCHMARK)](#3-bảng-tổng-hợp-số-liệu-đối-soánh-thực-nghiệm-đa-phương-pháp-step-7-benchmark)
4. [HỆ THỐNG PHÂN TẦNG KIỂM ĐỊNH TOÀN DIỆN 6 TEST SUITES (115 TESTS)](#4-hệ-thống-phân-tầng-kiểm-định-toàn-diện-6-test-suites-115-tests)
5. [DANH MỤC ARTIFACTS & MANIFESTS ĐÃ BAN HÀNH](#5-danh-mục-artifacts--manifests-đã-ban-hành)
6. [TUÂN THỦ NGUYÊN TẮC AN TOÀN BẤT BIẾN & KHUYẾN CÁO KHOA HỌC](#6-tuân-thủ-nguyên-tắc-an-toàn-bất-biến--khuyến-cáo-khoa-học)

---

## 1. TỔNG QUAN TIẾN ĐỘ 7 BƯỚC (EXECUTIVE SUMMARY)

Bảng dưới đây tổng hợp tiến trình thực hiện toàn bộ 7 bước theo yêu cầu của giao thức nghiên cứu Aeolus Gate Optimization:

| Bước thực hiện | Trọng tâm nghiên cứu & kiểm định | Hiện trạng trước kiểm định | Giải pháp kỹ thuật & Chuẩn hóa | Kết quả kiểm thử | Trạng thái |
| :--- | :--- | :--- | :--- | :---: | :---: |
| **Step 1: Monte Carlo Audit** | Kiểm toán hội tụ mô phỏng Monte Carlo | Bị cắt nhánh sớm ở 100 kịch bản (`min(n_scen, 100)`), số liệu giống hệt nhau ở mọi $N \ge 100$. | Đánh giá trọn vẹn toàn bộ $N$ kịch bản ($N \in [100, 2500]$), xác nhận ma trận có hash phân biệt và phương sai thực tế. | 6 / 6 tests PASS | **PASS** |
| **Step 2: CP-SAT Objective** | Kiểm toán hàm mục tiêu của bộ giải chính xác CP-SAT | Trộn lẫn chi phí quyết định với chi phí ngoại sinh bất biến (delay, rủi ro). | Tách bạch `total_cost = decision_cost + reporting_cost`, tối ưu hóa trực tiếp trên `decision_cost`. | 3 / 3 tests PASS | **PASS** |
| **Step 3: SA Benchmark** | Khảo sát vai trò SA dưới trần thời gian sub-second | Thiếu khảo sát đối sánh đa nhánh khi CP-SAT bị giới hạn thời gian. | Thiết lập benchmark 5 nhánh đối đầu trên 4 mốc thời gian $[0.1\text{s}, 0.3\text{s}, 1.0\text{s}, 3.0\text{s}]$. | 5 / 5 tests PASS | **PASS** |
| **Step 4: Temporal Guards** | Hiệu chỉnh chốt an toàn nếp huấn luyện và kiểm định | Dùng đường tắt $\max(\text{train\_year}) \le 2021$ chặn nhầm tiền huấn luyện 2016–2022 và lỏng lẻo ở Fold 1. | Tái cấu trúc thành Role-based Validation (`validate_dataset_role_and_years`), ủy quyền 2016–2022, chặn đứng 2024. | 10 / 10 tests PASS | **PASS** |
| **Step 5: Dependence Sync** | Đồng bộ hợp đồng số chiều ma trận Copula $d$ | Check 6 giới hạn cứng $d \in [1, 110]$, trong khi cao điểm ATL đạt $d=420$. | Đồng bộ Phase C & H: kiểm tra $d \in \{1, 5, 23, 77, 150, 420\}$, stress test $d=500$, kiểm định 8 thuộc tính toán học. | 12 / 12 tests PASS | **PASS** |
| **Step 6: Timeline Semantics** | Ngữ nghĩa dòng thời gian và dòng quay đầu máy bay | Nguy cơ cộng dồn trùng lặp giữa turnaround, dwell và buffer; lệch logic biên. | Chuẩn hóa $D_{\text{sim}} = \max(D_{\text{sched}}, A_{\text{sim}} + T_{\text{turn}})$, chứng minh zero double counting, bao phủ 6 ca biên. | 9 / 9 tests PASS | **PASS** |
| **Step 7: Broader E2E Bench** | Khảo sát đối sánh mở rộng trên tập phát triển 2023 | Thiếu kiểm chứng trên nhiều ngày với cấp độ nhu cầu vận hành biến thiên. | Vận hành chu trình khép kín trên 4 ngày phát triển (40 kịch bản, 4 cấp nhu cầu), 0 lỗi, xác nhận tái lập xác định. | 9 / 9 tests PASS | **PASS** |

---

## 2. CHI TIẾT NỘI DUNG YÊU CẦU, THỰC THI & KẾT QUẢ TỪNG BƯỚC (STEPS 1 — 7)

### Step 1: Monte Carlo Audit & Correctness (Pha G)
* **Yêu cầu của Người dùng**:
  - Kiểm toán và khắc phục hiện tượng số liệu hội tụ Monte Carlo bị trùng lặp ở mọi cấp $N \in [100, 250, 500, 1000, 2500]$ ($P95 = 666.15$ phút, Chi phí = $108.76$).
  - Gỡ bỏ giới hạn cắt nhánh sớm, thực hiện Uncapped Evaluation trọn vẹn toàn bộ $N$ kịch bản.
  - Chứng minh mỗi kịch bản là độc nhất, ma trận có mã băm phân biệt và phương sai thực tế lan truyền đến các chỉ số hạ nguồn.
* **Nguyên nhân Kỹ thuật Phát hiện**:
  - Trong tệp [`scripts/run_phase_g_pipeline.py`](file:///D:/Study/Code/Python/Aelous/scripts/run_phase_g_pipeline.py), vòng lặp thu thập số liệu bị chặn bởi biểu thức `eval_count = min(n_scen, 100)`. Do đó, dù người dùng chỉ định $N=2500$, hệ thống chỉ đánh giá lặp lại đúng 100 kịch bản đầu tiên.
* **Giải pháp Kỹ thuật Đã Thực thi**:
  - Gỡ bỏ giới hạn: Thiết lập `eval_count = n_scen` để đánh giá toàn diện $100\%$ số kịch bản sinh ra.
  - Tích hợp kiểm tra tính duy nhất (uniqueness check) của từng hàng kịch bản và mã băm SHA-256 của ma trận độ trễ.
  - Xây dựng bài kiểm thử độc lập [`tests/test_monte_carlo_audit.py`](file:///D:/Study/Code/Python/Aelous/tests/test_monte_carlo_audit.py) kiểm chứng 6 tính chất ngẫu nhiên.
* **Kết quả Thực nghiệm Đạt được**:
  - Toàn bộ $N$ kịch bản ở mỗi cấp là duy nhất $100\%$, mã băm ma trận hoàn toàn phân biệt.
  - Số liệu hội tụ thực tế phản ánh dao động thống kê chân thực:
    - $N=100$: P95 xung đột $= 660.25$m, Chi phí kỳ vọng $= 108.75$ ($\sigma^2 = 313.49$)
    - $N=250$: P95 xung đột $= 656.55$m, Chi phí kỳ vọng $= 109.13$ ($\sigma^2 = 370.34$)
    - $N=500$: P95 xung đột $= 658.10$m, Chi phí kỳ vọng $= 108.83$ ($\sigma^2 = 344.60$)
    - $N=1000$: P95 xung đột $= 665.00$m, Chi phí kỳ vọng $= 109.81$ ($\sigma^2 = 395.15$)
    - $N=2500$: P95 xung đột $= 664.00$m, Chi phí kỳ vọng $= 110.28$ ($\sigma^2 = 392.98$)
  - Test suite: **6 / 6 tests PASS**.
  - Artifacts: [`artifacts/end_to_end/aggregate_metrics.json`](file:///D:/Study/Code/Python/Aelous/artifacts/end_to_end/aggregate_metrics.json).

---

### Step 2: CP-SAT Objective Audit & Validity (Pha D)
* **Yêu cầu của Người dùng**:
  - Kiểm toán cấu trúc hàm mục tiêu của Google OR-Tools CP-SAT Solver.
  - Phân tách tường minh giữa chi phí quyết định (`decision_cost`) và chi phí ngữ cảnh ngoại sinh (`reporting_cost`).
  - Đảm bảo tính nhất quán tuyệt đối giữa bộ giải CP-SAT và bộ đánh giá khách quan chung (Common Evaluator `evaluate_gate_assignment`).
* **Nguyên nhân Kỹ thuật Phát hiện**:
  - Trong triển khai ban đầu, hàm mục tiêu cộng dồn chi phí đổi cổng và tràn bãi đỗ với chi phí trễ lịch trình (`delay_cost`) và chi phí rủi ro (`risk_cost`). Vì hai thành phần sau hoàn toàn bất biến đối với quyết định gán cổng $x_{f,g}$, việc gộp chung gây nhiễu loạn phân tích biên và cản trở việc đối sánh công bằng.
* **Giải pháp Kỹ thuật Đã Thực thi**:
  - Định nghĩa lớp dữ liệu [`ObjectiveBreakdown`](file:///D:/Study/Code/Python/Aelous/src/optimization/domain.py) phân loại rõ:
    $$\text{Total Cost} = \text{Decision Cost} (\text{Reassignment} + \text{Overflow} + \text{Conflict}) + \text{Reporting Cost} (\text{Delay} + \text{Risk})$$
  - Cập nhật [`CPSatGateSolver`](file:///D:/Study/Code/Python/Aelous/src/optimization/solvers/cp_sat_solver.py): Bộ giải tối ưu hóa trực tiếp trên `decision_cost` ở dạng số nguyên mở rộng (scaling integer factor) và cộng lại `reporting_cost` để đối soát.
  - Cập nhật [`evaluate_gate_assignment`](file:///D:/Study/Code/Python/Aelous/src/optimization/evaluation.py) xuất bản cấu trúc chi phí đồng bộ.
  - Xây dựng bài kiểm thử [`tests/test_objective_audit.py`](file:///D:/Study/Code/Python/Aelous/tests/test_objective_audit.py).
* **Kết quả Thực nghiệm Đạt được**:
  - Sai số giữa điểm mục tiêu của CP-SAT và Common Evaluator bằng $0.0000$ trên $100\%$ các bài toán thử nghiệm.
  - Test suite: **3 / 3 tests PASS**.
  - Artifacts: [`artifacts/audit/phase_d_cp_sat_objective_audit_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/phase_d_cp_sat_objective_audit_manifest_v1.json).

---

### Step 3: SA Time-Limited Benchmark & Role Validation (Pha F)
* **Yêu cầu của Người dùng**:
  - Khảo sát vai trò thực tiễn của Simulated Annealing (SA) khi CP-SAT bị giới hạn thời gian chạy (Time-limited sub-second latency budgets).
  - So sánh đối đầu 5 nhánh: Greedy (A), Time-limited CP-SAT (B), CP-SAT Incumbent (C), CP-SAT Incumbent + SA (D), Greedy + SA (E) trên các ngưỡng thời gian: $[0.1\text{s}, 0.3\text{s}, 1.0\text{s}, 3.0\text{s}]$.
  - Chứng minh bất biến: SA `best_so_far` không bao giờ làm giảm chất lượng nghiệm khởi tạo, luôn thỏa mãn $100\%$ ràng buộc cứng (0 xung đột).
* **Giải pháp Kỹ thuật Đã Thực thi**:
  - Xây dựng kịch bản benchmark độc lập [`scripts/run_phase_f_time_limited_sa_benchmark.py`](file:///D:/Study/Code/Python/Aelous/scripts/run_phase_f_time_limited_sa_benchmark.py).
  - Khảo sát 3 kịch bản chuẩn: `F100_G20`, `F150_G15_CONGESTED`, `F200_G20_SCALE`.
  - Xây dựng bài kiểm thử [`tests/test_time_limited_sa_benchmark.py`](file:///D:/Study/Code/Python/Aelous/tests/test_time_limited_sa_benchmark.py).
* **Kết quả Thực nghiệm Đạt được**:
  1. *Chế độ thời gian siêu ngặt ($TL = 0.1\text{s}$)*: CP-SAT chưa kịp hoàn tất presolve, trả về trạng thái `UNKNOWN` (không có nghiệm khả thi). Trong khi đó, Greedy chạy trong $0.9 - 4.3$ ms, và Greedy + SA tiếp tục cải thiện điểm mục tiêu mà vẫn bảo đảm 0 xung đột cổng tiếp xúc.
  2. *Chế độ Incumbent sơ bộ ($TL = 0.3\text{s}$ trên bài toán tắc nghẽn)*: CP-SAT tìm được nghiệm khả thi sơ bộ, SA nhận vào và bảo toàn nghiệm mà không suy giảm.
  3. *Chế độ Tối ưu toàn cục ($TL \ge 1.0\text{s}$)*: CP-SAT chứng minh được nghiệm `OPTIMAL` (gap = 0.0), SA bảo toàn tối ưu tuyệt đối ($+0.00$ improvement).
  - Test suite: **5 / 5 tests PASS**.
  - Artifacts: [`artifacts/audit/phase_f_time_limited_sa_benchmark_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/phase_f_time_limited_sa_benchmark_manifest_v1.json).

---

### Step 4: Holdout & Fold Guard Correction / Temporal Protocol (Pha H)
* **Yêu cầu của Người dùng**:
  - Phát hiện và sửa lỗi biểu thức đường tắt $\max(\text{train\_year}) \le 2021$ trong [`src/audit/protocol_guards.py`](file:///D:/Study/Code/Python/Aelous/src/audit/protocol_guards.py).
  - Tái cấu trúc thành cơ chế xác thực dựa trên vai trò phân vùng dữ liệu (**Role-Based Dataset Guard**).
  - Ủy quyền tường minh cho huấn luyện tiền kiểm định cuối cùng (Final Pre-Holdout Training trên 2016–2022 tại Stage 10 Freeze) theo Protocol Mục 2.2, đồng thời cấm tuyệt đối 2024 trong tập train/calibration/selection.
* **Nguyên nhân Kỹ thuật Phát hiện**:
  - Biểu thức cũ đồng nhất sai lệch giữa nếp ngoài cùng Fold 4 (train 2016–2021, val 2022) với quy tắc huấn luyện sản xuất tổng thể, khiến hệ thống chặn nhầm giai đoạn huấn luyện hoàn chỉnh 2016–2022 đã được giao thức phê duyệt. Đồng thời, biểu thức này quá lỏng lẻo ở các fold trước (cho phép năm 2019 lọt vào Fold 1 train).
* **Giải pháp Kỹ thuật Đã Thực thi**:
  - Xây dựng hàm chuẩn hóa [`validate_dataset_role_and_years`](file:///D:/Study/Code/Python/Aelous/src/audit/protocol_guards.py) kiểm định chặt chẽ:
    - Fold 1: train $\le 2018$ (val 2019)
    - Fold 2: train $\le 2019$ (val 2020)
    - Fold 3: train $\le 2020$ (val 2021)
    - Fold 4: train $\le 2021$ (val 2022)
    - Final Pre-Holdout Training: train $\le 2022$ (ủy quyền 2016–2022)
    - 2023: Chỉ dùng cho Model Selection / Benchmark một lần. Cấm train/calibration.
    - 2024: Fail-closed tuyệt đối. Cấm train/calibration/selection.
    - Năm tương lai $> 2024$: Fail-closed chặn đứng.
  - Cập nhật [`ProtocolComplianceGuard`](file:///D:/Study/Code/Python/Aelous/src/audit/protocol_guards.py) áp dụng quy tắc role-based.
  - Xây dựng test suite [`tests/test_holdout_and_fold_guards.py`](file:///D:/Study/Code/Python/Aelous/tests/test_holdout_and_fold_guards.py).
* **Kết quả Thực nghiệm Đạt được**:
  - Toàn bộ 7 chốt an toàn giao thức đều đạt trạng thái `PASS`.
  - Test suite: **10 / 10 tests PASS** (100%).
  - Artifacts: [`artifacts/audit/phase_h_holdout_fold_guard_correction_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/phase_h_holdout_fold_guard_correction_manifest_v1.json).

---

### Step 5: Dependence Contract Consistency / Phase C & H Sync
* **Yêu cầu của Người dùng**:
  - Đồng bộ hợp đồng số chiều ma trận $d$ giữa Phase C (Dynamic PSD Projection) và Phase H (Protocol Guards).
  - Trước đó: Phase C hỗ trợ $d$ động, nhưng Check 6 trong Phase H chỉ kiểm tra cố định $d \in [1, 110]$. Trong khi đó, giờ cao điểm tại KATL đạt tới $d = 420$ chuyến bay/ngày, và giới hạn $O(d^3)$ cho phép tới $d = 1500$.
  - Đồng bộ hợp đồng hỗ trợ $d \in \{1, 5, 23, 77, 150, 420\}$, stress test $d=500$, kiểm tra 8 thuộc tính toán học (kích thước, đối xứng, đường chéo 1.0, hữu hạn, PSD với sàn $\lambda_{\min} \ge 10^{-6}$, variates trong $(0,1)$, tính tái lập xác định).
* **Giải pháp Kỹ thuật Đã Thực thi**:
  - Bổ sung hằng số chuẩn hóa trong [`src/audit/protocol_guards.py`](file:///D:/Study/Code/Python/Aelous/src/audit/protocol_guards.py):
    `MIN_DEPENDENCE_DIMENSION = 1`, `PEAK_OPERATIONAL_HUB_DIMENSION = 420`, `RECOMMENDED_MAX_DIMENSION = 1500`.
  - Cập nhật hàm [`verify_dependence_dimension_properties`](file:///D:/Study/Code/Python/Aelous/src/audit/protocol_guards.py).
  - Xây dựng kịch bản kiểm toán [`scripts/run_phase_c_dependence_contract_audit.py`](file:///D:/Study/Code/Python/Aelous/scripts/run_phase_c_dependence_contract_audit.py).
  - Xây dựng test suite [`tests/test_dependence_contract_consistency.py`](file:///D:/Study/Code/Python/Aelous/tests/test_dependence_contract_consistency.py).
* **Kết quả Thực nghiệm Đạt được**:
  - Toàn bộ các chiều $d \in \{1, 5, 23, 77, 150, 420\}$ và stress test $d=500$ đều thỏa mãn $100\%$ các thuộc tính toán học với giá trị riêng nhỏ nhất $\lambda_{\min} \ge 10^{-6}$.
  - Test suite: **12 / 12 tests PASS**.
  - Artifacts: [`artifacts/audit/phase_c_dependence_contract_consistency_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/phase_c_dependence_contract_consistency_manifest_v1.json).

---

### Step 6: Aircraft Turn / Timeline Semantics Audit
* **Yêu cầu của Người dùng**:
  - Kiểm toán toàn diện dòng thời gian vận hành: `scheduled arrival → sampled delay → simulated arrival → gate-in → turnaround/dwell → gate-out → gate-release`.
  - Phân định rõ ngữ nghĩa của:
    - `min_turnaround` ($T_{\text{turn}}$, 45m): Thời lượng quay đầu vật lý tối thiểu.
    - `scheduled_dwell` ($T_{\text{dwell}}$, 60m): Thời lượng đỗ kế hoạch theo lịch trình ($D_{\text{sched}} - A_{\text{sched}}$).
    - `buffer` ($B_{\text{buffer}}$, 15m): Khoảng đệm an toàn phân cách giữa 2 tàu bay liên tiếp tại cùng 1 cổng tiếp xúc.
  - Xác lập công thức: $\text{gate\_out} = D_{\text{sim}} = \max(D_{\text{sched}}, A_{\text{sim}} + T_{\text{turn}})$ và chứng minh không xảy ra double counting.
  - Bao phủ 6 kịch bản biên: `delay=0`, `delay=10`, `dwell < turnaround`, `dwell > turnaround`, `buffer > 0`, `back-to-back flights`.
  - Đồng bộ $100\%$ logic khoảng nửa mở $[s, e)$ giữa mô phỏng (`AircraftTurn`), bộ phát hiện xung đột (`ConflictDetector`), bộ xác minh độc lập (`verify_hard_constraints_independently`), và bộ giải tối ưu (`CPSatGateSolver`).
* **Giải pháp Kỹ thuật Đã Thực thi**:
  - [`src/simulation/aircraft_turn.py`](file:///D:/Study/Code/Python/Aelous/src/simulation/aircraft_turn.py) & [`src/optimization/domain.py`](file:///D:/Study/Code/Python/Aelous/src/optimization/domain.py): Bổ sung các thuộc tính tường minh `gate_in_min`, `gate_out_min`, `physical_dwell_min`, `scheduled_dwell_min`, `turnaround_slack_min`. Sửa lỗi `synthesize_turn` và `synthesize_batch` để tôn trọng `scheduled_departure_min`.
  - Chứng minh không cộng dồn: $T_{\text{turn}}$ và $T_{\text{dwell}}$ kết hợp qua toán tử $\max$, tuyệt đối không cộng gộp. $B_{\text{buffer}}$ chỉ được cộng đúng 1 lần vào $D_{\text{sim}}$ tại mốc giải phóng cổng.
  - Xây dựng bài kiểm thử [`tests/test_timeline_semantics.py`](file:///D:/Study/Code/Python/Aelous/tests/test_timeline_semantics.py).
  - Xây dựng script kiểm toán [`scripts/run_phase_g_timeline_semantics_audit.py`](file:///D:/Study/Code/Python/Aelous/scripts/run_phase_g_timeline_semantics_audit.py).
* **Kết quả Thực nghiệm Đạt được**:
  - Toàn bộ 6 kịch bản kiểm thử thủ công và kiểm tra tương đương logic khoảng thời gian đều đạt kết quả chính xác tuyệt đối.
  - Test suite: **9 / 9 tests PASS**.
  - Artifacts: [`artifacts/audit/phase_g_timeline_semantics_audit_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/phase_g_timeline_semantics_audit_manifest_v1.json).

---

### Step 7: Broader Development End-to-End Benchmark
* **Yêu cầu của Người dùng**:
  - Điều kiện tiên quyết: Step 1–6 phải đều đạt PASS.
  - Sử dụng dữ liệu phát triển độc lập (2016–2023 development data), tuyệt đối cấm truy cập dữ liệu 2024.
  - Tuyển chọn nhiều ngày phát triển xác định với các cấp độ nhu cầu vận hành biến thiên (Varying Demand Levels) tại KATL.
  - Chạy chu trình khép kín: B5 Student-T đông băng → Copula D2 → Monte Carlo → Turn Model → Conflict Detection → Greedy → CP-SAT → SA Time-Limited Benchmark.
  - Báo cáo phân phối thống kê đa phương pháp (Method-Wise Distributions) thay vì tuyên bố một người chiến thắng duy nhất.
  - Bảo toàn thất bại trong `failures.json` (không âm thầm loại bỏ kịch bản lỗi).
  - Tạo 7 artifacts chuẩn trong `artifacts/development_end_to_end/`.
  - Chạy kiểm định lặp lại xác định (Deterministic Repetition Check) xác nhận kết quả khớp $100\%$.
  - Cảnh báo bắt buộc: Không gọi kết quả này là hiệu năng thực tế tại sân bay (non-real-world performance disclaimer).
* **Giải pháp Kỹ thuật Đã Thực thi**:
  - Xây dựng [`scripts/run_development_end_to_end_benchmark.py`](file:///D:/Study/Code/Python/Aelous/scripts/run_development_end_to_end_benchmark.py) tích hợp trọn vẹn chu trình.
  - Tuyển chọn 4 ngày phát triển đặc trưng năm 2023:
    1. `DAY_LOW` (`2023-11-23` Thanksgiving Day): 40 flights, 12 contact gates (nhu cầu thấp).
    2. `DAY_MEDIUM` (`2023-07-03` Pre-holiday Summer): 70 flights, 18 contact gates (nhu cầu trung bình).
    3. `DAY_HIGH` (`2023-07-13` Peak Summer Weekday): 100 flights, 24 contact gates (nhu cầu đỉnh).
    4. `DAY_WEATHER_DISRUPTED` (`2023-08-07` Severe Convective Storm): 70 flights, 18 contact gates (trễ đuôi nặng do bão).
  - Thực thi $4 \times 10 = 40$ kịch bản ngẫu nhiên qua cả 4 phương pháp: Greedy, CP-SAT, SA (CP-SAT+SA), SA (Greedy+SA).
  - Tích hợp kiểm định lặp lại xác định: Re-solve 8 kịch bản và đối soát mã băm cùng điểm số mục tiêu.
  - Xây dựng bài kiểm thử [`tests/test_development_end_to_end_benchmark.py`](file:///D:/Study/Code/Python/Aelous/tests/test_development_end_to_end_benchmark.py).
* **Kết quả Thực nghiệm Đạt được**:
  - $100\%$ nghiệm khả thi cứng trên cả 40 kịch bản, **0 xung đột cổng tiếp xúc**.
  - `failures_count = 0`, xác nhận kiểm định lặp lại đạt tính xác định $100\%$.
  - Test suite: **9 / 9 tests PASS**.
  - Phân tầng kiểm thử toàn hệ thống đạt **115 / 115 tests PASSED (100%)**.
  - Artifacts: Toàn bộ 7 tệp được lưu trữ tại [`artifacts/development_end_to_end/`](file:///D:/Study/Code/Python/Aelous/artifacts/development_end_to_end/).

---

## 3. BẢNG TỔNG HỢP SỐ LIỆU ĐỐI SOÁNH THỰC NGHIỆM ĐA PHƯƠNG PHÁP (STEP 7 BENCHMARK)

*Nguồn dữ liệu: [`artifacts/development_end_to_end/aggregate_metrics.json`](file:///D:/Study/Code/Python/Aelous/artifacts/development_end_to_end/aggregate_metrics.json)*

### Bảng 1: Phân phối Hiệu năng Tổng thể trên 40 Kịch bản Ngẫu nhiên (Overall Distributions)

| Chỉ số Thống kê | Greedy Baseline | Exact CP-SAT | SA (Greedy Warm-Start) | SA (CP-SAT Incumbent) |
| :--- | :---: | :---: | :---: | :---: |
| **Số kịch bản đánh giá** | 40 | 40 | 40 | 40 |
| **Tỷ lệ Khả thi Cứng (Hard Feasibility)** | **100.0%** | **100.0%** | **100.0%** | **100.0%** |
| **Số nghiệm Tối ưu Toàn cục (OPTIMAL)** | N/A (Heuristic) | **40 / 40 (100%)** | N/A (Metaheuristic) | **40 / 40 (Preserved)** |
| **Xung đột Cổng Tiếp xúc (Contact Conflicts)** | **0** | **0** | **0** | **0** |
| **Chi phí Mục tiêu Trung bình (Mean Obj)** | $9,430.44 \pm 3,163.33$ | **$9,351.69 \pm 3,137.82$** | $9,416.19 \pm 3,158.79$ | **$9,351.69 \pm 3,137.82$** |
| **Trung vị Chi phí Mục tiêu (Median Obj)** | $9,540.15$ | **$9,520.15$** | $9,540.15$ | **$9,520.15$** |
| **Khoảng Tứ phân vị Chi phí (IQR)** | $4,116.97$ | **$4,083.42$** | $4,081.97$ | **$4,083.42$** |
| **Chi phí Quyết định Trung bình (Decision Cost)** | $9,409.50$ | **$9,330.75$** | $9,395.25$ | **$9,330.75$** |
| **Chi phí Báo cáo Ngoại sinh (Reporting Cost)** | $20.94$ | $20.94$ | $20.94$ | $20.94$ |
| **Số lần Đổi cổng Trung bình (Reassignments)** | $53.95$ | **$48.08$** | $52.53$ | **$48.08$** |
| **Số chuyến Tràn bãi Đỗ xa (Overflow Stand)** | $44.35$ | **$44.25$** | $44.35$ | **$44.25$** |
| **Thời gian Giải Trung bình (Mean Runtime)** | **$1.28$ ms** | $1,082.53$ ms | $214.47$ ms | $1,298.78$ ms |
| **Trung vị Thời gian Giải (Median Runtime)** | **$1.15$ ms** | $851.61$ ms | $215.94$ ms | $1,056.55$ ms |
| **Dải Thời gian Giải (Min — Max Runtime)** | $0.46$ ms — $3.11$ ms | $172.18$ ms — $2,789.00$ ms | $96.59$ ms — $365.00$ ms | $282.41$ ms — $3,041.26$ ms |
| **Hệ số Tận dụng Cổng (Gate Utilization)** | $8.19\%$ | $8.05\%$ | $8.15\%$ | $8.05\%$ |

---

### Bảng 2: Phân tích Chi tiết theo 4 Cấp độ Nhu cầu Vận hành (Demand Level Breakdown)

| Cấp độ Nhu cầu (Demand Level) | Ngày khảo sát & Quy mô | Greedy Chi phí (Thời gian) | CP-SAT Chi phí (Thời gian) | SA Greedy+SA Chi phí (Thời gian) | Nhận xét Khoa học |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **LOW** | `2023-11-23` (Thanksgiving)<br>40 flights / 12 gates | $5,315.25$<br>($0.52$ ms) | **$5,291.25$**<br>($187.22$ ms) | $5,308.25$<br>($115.47$ ms) | Mật độ thấp, CP-SAT giải tối ưu trong $187$ms, tiết kiệm $24$ điểm chi phí. |
| **MEDIUM** | `2023-07-03` (Pre-holiday)<br>70 flights / 18 gates | $8,684.63$<br>($1.13$ ms) | **$8,620.63$**<br>($832.81$ ms) | $8,678.63$<br>($230.41$ ms) | Mật độ trung bình, CP-SAT giải trong $833$ms, giảm $64$ điểm chi phí. |
| **HIGH** | `2023-07-13` (Peak Summer)<br>100 flights / 24 gates | $13,596.73$<br>($2.25$ ms) | **$13,445.73$**<br>($2,470.58$ ms) | $13,582.73$<br>($315.51$ ms) | Giờ cao điểm, CP-SAT tiết kiệm tới $151$ điểm chi phí, thời gian giải $2.47$s. |
| **WEATHER_DISRUPTED** | `2023-08-07` (Convective Storm)<br>70 flights / 18 gates | $10,125.14$<br>($1.24$ ms) | **$10,049.14$**<br>($839.50$ ms) | $10,095.14$<br>($196.48$ ms) | Trễ đuôi bão đối lưu, chi phí tăng vọt; CP-SAT tiết kiệm $76$ điểm chi phí. |

---

## 4. HỆ THỐNG PHÂN TẦNG KIỂM ĐỊNH TOÀN DIỆN 6 TEST SUITES (115 TESTS)

*Nguồn dữ liệu: [`artifacts/final_code_audit/test_summary.json`](file:///D:/Study/Code/Python/Aelous/artifacts/final_code_audit/test_summary.json)*

Toàn bộ hệ thống kiểm thử tự động phân tầng đã được thực thi và chứng thực thông qua [`scripts/run_final_code_audit.py`](file:///D:/Study/Code/Python/Aelous/scripts/run_final_code_audit.py):

| Phân tầng Kiểm định (Test Suite) | Tệp kiểm thử thành phần | Số lượng Tests | Thời gian thực thi | Trạng thái |
| :--- | :--- | :---: | :---: | :---: |
| **1. Unit Tests (Simulation & Turn)** | [`tests/test_simulation_pipeline.py`](file:///D:/Study/Code/Python/Aelous/tests/test_simulation_pipeline.py)<br>[`tests/test_timeline_semantics.py`](file:///D:/Study/Code/Python/Aelous/tests/test_timeline_semantics.py) | 19 | $3.91$s | **100% PASS** |
| **2. Probabilistic Tests** | [`tests/test_student_t_correctness.py`](file:///D:/Study/Code/Python/Aelous/tests/test_student_t_correctness.py)<br>[`tests/test_unified_evaluation.py`](file:///D:/Study/Code/Python/Aelous/tests/test_unified_evaluation.py) | 12 | $3.96$s | **100% PASS** |
| **3. Dependence Tests** | [`tests/test_dependence_hardening.py`](file:///D:/Study/Code/Python/Aelous/tests/test_dependence_hardening.py)<br>[`tests/test_dependence_contract_consistency.py`](file:///D:/Study/Code/Python/Aelous/tests/test_dependence_contract_consistency.py) | 39 | $5.86$s | **100% PASS** |
| **4. CP-SAT & Greedy Tests** | [`tests/test_cp_sat_solver.py`](file:///D:/Study/Code/Python/Aelous/tests/test_cp_sat_solver.py)<br>[`tests/test_greedy_and_adversarial.py`](file:///D:/Study/Code/Python/Aelous/tests/test_greedy_and_adversarial.py) | 19 | $0.84$s | **100% PASS** |
| **5. Simulated Annealing Tests** | [`tests/test_simulated_annealing.py`](file:///D:/Study/Code/Python/Aelous/tests/test_simulated_annealing.py) | 15 | $4.03$s | **100% PASS** |
| **6. End-to-End & Dev Benchmark** | [`tests/test_end_to_end_pipeline.py`](file:///D:/Study/Code/Python/Aelous/tests/test_end_to_end_pipeline.py)<br>[`tests/test_development_end_to_end_benchmark.py`](file:///D:/Study/Code/Python/Aelous/tests/test_development_end_to_end_benchmark.py) | 11 | $3.53$s | **100% PASS** |
| **TỔNG HỢP TOÀN HỆ THỐNG** | **6 Phân tầng (9 Test Files)** | **115** | **22.13s** | **100% PASS** |

---

## 5. DANH MỤC ARTIFACTS & MANIFESTS ĐÃ BAN HÀNH

Tất cả các artifacts đã được ký duyệt và xuất bản có cấu trúc rõ ràng:

1. **Step 1 (Monte Carlo Audit)**:
   - [`artifacts/end_to_end/aggregate_metrics.json`](file:///D:/Study/Code/Python/Aelous/artifacts/end_to_end/aggregate_metrics.json)
   - [`artifacts/manifests/probabilistic_stage9_gate_simulation_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/manifests/probabilistic_stage9_gate_simulation_v1.json)
2. **Step 2 (CP-SAT Objective Audit)**:
   - [`artifacts/audit/phase_d_cp_sat_objective_audit_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/phase_d_cp_sat_objective_audit_manifest_v1.json)
3. **Step 3 (SA Time-Limited Benchmark)**:
   - [`artifacts/audit/phase_f_time_limited_sa_benchmark_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/phase_f_time_limited_sa_benchmark_manifest_v1.json)
4. **Step 4 (Temporal Protocol / Fold Guard Correction)**:
   - [`artifacts/audit/phase_h_holdout_fold_guard_correction_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/phase_h_holdout_fold_guard_correction_manifest_v1.json)
5. **Step 5 (Dependence Contract Consistency)**:
   - [`artifacts/audit/phase_c_dependence_contract_consistency_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/phase_c_dependence_contract_consistency_manifest_v1.json)
6. **Step 6 (Aircraft Turn / Timeline Semantics Audit)**:
   - [`artifacts/audit/phase_g_timeline_semantics_audit_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/phase_g_timeline_semantics_audit_manifest_v1.json)
7. **Step 7 (Broader Development End-to-End Benchmark)**:
   - [`artifacts/development_end_to_end/run_manifest.json`](file:///D:/Study/Code/Python/Aelous/artifacts/development_end_to_end/run_manifest.json)
   - [`artifacts/development_end_to_end/scenario_registry.parquet`](file:///D:/Study/Code/Python/Aelous/artifacts/development_end_to_end/scenario_registry.parquet)
   - [`artifacts/development_end_to_end/greedy_results.parquet`](file:///D:/Study/Code/Python/Aelous/artifacts/development_end_to_end/greedy_results.parquet)
   - [`artifacts/development_end_to_end/cp_sat_results.parquet`](file:///D:/Study/Code/Python/Aelous/artifacts/development_end_to_end/cp_sat_results.parquet)
   - [`artifacts/development_end_to_end/sa_results.parquet`](file:///D:/Study/Code/Python/Aelous/artifacts/development_end_to_end/sa_results.parquet)
   - [`artifacts/development_end_to_end/aggregate_metrics.json`](file:///D:/Study/Code/Python/Aelous/artifacts/development_end_to_end/aggregate_metrics.json)
   - [`artifacts/development_end_to_end/failures.json`](file:///D:/Study/Code/Python/Aelous/artifacts/development_end_to_end/failures.json)
8. **Phân tầng Kiểm định Chung (Final Code Audit & Packaging)**:
   - [`artifacts/final_code_audit/test_summary.json`](file:///D:/Study/Code/Python/Aelous/artifacts/final_code_audit/test_summary.json)
   - [`artifacts/final_code_audit/protocol_compliance.json`](file:///D:/Study/Code/Python/Aelous/artifacts/final_code_audit/protocol_compliance.json)
   - [`artifacts/final_code_audit/integration_report.json`](file:///D:/Study/Code/Python/Aelous/artifacts/final_code_audit/integration_report.json)
   - [`artifacts/final_code_audit/reproducibility_manifest.json`](file:///D:/Study/Code/Python/Aelous/artifacts/final_code_audit/reproducibility_manifest.json)

---

## 6. TUÂN THỦ NGUYÊN TẮC AN TOÀN BẤT BIẾN & KHUYẾN CÁO KHOA HỌC

### 6.1. Tuân thủ Nguyên tắc An toàn Bất biến (Non-Negotiable Rules)
1. **Dữ liệu thô bất biến (Raw Data Immutability)**: Toàn bộ 9 tệp dữ liệu thô trong `data/raw/tabular/` nguyên vẹn 100%, không bị sửa đổi, đổi tên hay ghi đè.
2. **Kỷ luật Thời gian & Điểm cắt thông tin (Point-in-Time Cutoff)**: Mọi biến đầu vào phục vụ dự báo chỉ được lấy tại thời điểm $T-2$h trước giờ khởi hành dự kiến (`CRS_DEP_TIME - 2h`).
3. **Cách ly Tuyệt đối Năm 2024**: Năm 2024 đã được mở trong lịch sử tại Stage 11. Toàn bộ các thay đổi trong 7 bước trên đều là `POST_HOLDOUT_STABILIZED`. Tuyệt đối không dùng 2024 cho huấn luyện, căn chỉnh hay lựa chọn phương án.
4. **Đối xứng Đánh giá Khách quan (Common Evaluator Symmetry)**: Tất cả các bộ giải (Greedy, CP-SAT, SA) đều được đánh giá thông qua cùng một hàm đánh giá chuẩn hóa duy nhất.
5. **Ràng buộc cứng không vi phạm**: $100\%$ các bài toán đều được độc lập xác minh đạt 0 xung đột trên cổng tiếp xúc.

### 6.2. Khuyến cáo Khoa học Bắt buộc (Mandatory Scientific Disclaimer)
> [!IMPORTANT]
> Việc hoàn thành xuất sắc toàn bộ 7 bước kỹ thuật kiểm toán trên là minh chứng cho **tính đúng đắn của việc cài đặt thuật toán, tính nhất quán toán học của dòng thời gian và tính tái lập xác định của mã nguồn**.
> 
> Tuyệt đối **không** được tự ý kết luận rằng:
> 1. *"Thành công khoa học tuyệt đối"* hay *"Không bị overfitting"* — Các kết luận này đòi hỏi các nghiên cứu độc lập trên các sân bay và dải thời gian khác ngoài KATL.
> 2. *"Đạt tính tối ưu tuyệt đối trong khai thác thực tế tại sân bay"* — Môi trường thử nghiệm dựa trên mô phỏng độ trễ tổng hợp/tham số. Thực tế điều hành tại KATL còn chịu sự chi phối của các yếu tố luồng hành khách, xe kéo đẩy (towing), cổng đa kích thước (MARS), phân bổ quầy thủ tục và hiệp đồng kiểm soát không lưu (ATC CDM) chưa được đưa vào mô hình.
> 3. *"Thuật toán SA vượt trội hơn toàn diện"* — SA thể hiện tính ưu việt ở vai trò tìm kiếm cục bộ dưới trần thời gian sub-second, trong khi CP-SAT là bộ giải chính xác duy nhất chứng minh được tính tối ưu toàn cục toán học.
> 4. *"Mô phỏng Monte Carlo đã hội tụ tuyệt đối về chân lý mặt đất"* — Sự hội tụ ở đây là sự ổn định phương sai mẫu trong khuôn khổ phân phối tham số Student-T và Copula, không đồng nhất với thực tế khai thác vật lý.
