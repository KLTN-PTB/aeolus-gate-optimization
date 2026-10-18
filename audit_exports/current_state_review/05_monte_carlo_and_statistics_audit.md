# BÁO CÁO KIỂM TOÁN 05: KIỂM TOÁN PHÁP Y MÔ PHỎNG MONTE CARLO VÀ ĐỘ BỀN VỮNG TOÁN HỌC (MONTE CARLO FORENSIC AUDIT)

**Dự án:** Aeolus Gate Optimization (`aeolus-gate-optimization`)  
**Khóa luận:** Cử nhân Công nghệ Thông tin  
**Thời điểm kiểm toán:** 2026-10-11T15:44:00+07:00  
**Vai trò thẩm định:** Senior Operations Research Auditor, Mathematical Verifier  

---

## 1. Trả lời 13 Câu hỏi Pháp y Trọng tâm về Giai đoạn P09

Kiểm toán đã đối chiếu mã nguồn `src/simulation/monte_carlo_engine_p09.py`, script `scripts/run_p09_monte_carlo_validation.py` và toàn bộ dữ liệu trong `artifacts/remediation/monte_carlo/`:

### Q1: Có đúng 500 kịch bản ngẫu nhiên được tạo ra không?
* **Trả lời:** **ĐÚNG.** Tệp `scenario_index.csv` chứa chính xác **500 dòng**, tương ứng từ kịch bản `MC500_S0000` đến `MC500_S0499`, mỗi kịch bản có mã băm SHA-256 (`realization_hash`) riêng biệt để kiểm tra tính toàn vẹn.

### Q2: Có đúng $N_{\text{generated}} = N_{\text{evaluated}} = 500$ và không bỏ qua trường hợp lỗi nào không?
* **Trả lời:** **ĐÚNG.** Trong `statistical_summary.json` và `simulation_manifest.json`, cả 3 chế độ (Mode A, Mode B, Mode C) đều ghi nhận:
  $$N_{\text{requested}} = 500, \quad N_{\text{generated}} = 500, \quad N_{\text{evaluated}} = 500, \quad N_{\text{failed}} = 0$$
  Không có kịch bản nào bị nuốt lỗi (silent drop) hay bỏ qua.

### Q3: Các tham số ngẫu nhiên được học từ mô hình P4 hay cấu hình cố định?
* **Trả lời:** **CẤU HÌNH CỐ ĐỊNH (FIXED CONFIGURATION CONSTANTS).**
  * Trong `MonteCarloScenarioGenerator.__init__` (dòng 133–140), các tham số phân phối Student-T và Copula được thiết lập sẵn dưới dạng giá trị mặc định:
    * Chiều Đến (Arrival): $\mu = 5.0, \quad \sigma = 18.0, \quad \nu = 4.5$
    * Chiều Đi (Departure): $\mu = 8.0, \quad \sigma = 22.0, \quad \nu = 4.0$
    * Hệ số tương quan Gaussian Copula: $\rho = 0.45$
  * Các tham số này phản ánh ước lượng thống kê lịch sử của đợt trễ tại Atlanta nhưng **KHÔNG ĐƯỢC nạp động theo từng chuyến bay** từ đầu ra $\mu(x), \sigma(x)$ của mô hình NGBoost P4 tại thời điểm chạy.

### Q4: Kỹ thuật Biến Ngẫu nhiên Chung (Common Random Numbers - CRN) được áp dụng như thế nào?
* **Trả lời:** CRN được áp dụng **chuẩn xác và nhất quán tuyệt đối**.
  * Ma trận phân vị đồng thời $U \in (0, 1)^{500 \times N \times 2}$ được sinh một lần duy nhất từ bộ sinh số ngẫu nhiên cố định hạt giống (`seed = 202601`).
  * Tất cả các bộ giải (Greedy, CP-SAT, Hybrid) và tất cả các chế độ (Mode A, Mode B, Mode C) đều được đánh giá trên cùng một danh sách 500 realization cụ thể này.

### Q5: Mode A có thực sự giữ nguyên cổng không?
* **Trả lời:** **CÓ.** Hàm `evaluate_mode_a_fixed_plan` áp dụng kế hoạch phân bổ đã đóng băng (`frozen_assignments`) vào lịch bay đã phát sinh trễ thực tế với **0 lần phân bổ lại** (`reassignment_count = 0`).

### Q6: Mode B tái tối ưu hóa có đảm bảo tính phi dự đoán (Non-anticipative) không?
* **Trả lời:** **CÓ.** Khi phát sinh xung đột trong kịch bản trễ, Mode B kích hoạt bộ giải phản ứng (recourse solver). Bộ giải đặt cổng danh định mục tiêu là cổng đã được phân bổ trong kế hoạch ban đầu, ưu tiên tối đa việc giữ nguyên cổng và chỉ thay đổi cổng cho các chuyến bay bị xung đột trực tiếp hoặc vi phạm sức chứa.

### Q7: Mode C sử dụng Greedy hay bộ giải tối ưu toàn cục?
* **Trả lời:** **MODE C SỬ DỤNG DETERMINISTIC GREEDY.**
  * Tại dòng 446–447 của `src/simulation/monte_carlo_engine_p09.py`:
    ```python
    oracle_solver = DeterministicGreedyGateSolver(config=config)
    res_oracle = oracle_solver.solve(flights=realized_flights, gates=gates, allow_overflow=True)
    ```
  * Mode C (Perfect Foresight Oracle) trong mã nguồn P09 **KHÔNG PHẢI là CP-SAT giải tối ưu toàn cục**, mà là thuật toán Tham lam Heuristic chạy trên dữ liệu trễ đã biết trước! Đây là một điểm hạn chế lý thuyết cần lưu ý.

### Q8 & Q9: Vì sao Mode A Feasibility = 0% trong khi Physical Conflict Rate = 74.8%? Và trong 126 kịch bản không có xung đột, nguyên nhân Feasibility = False cụ thể là gì?
* **Trả lời — Phát hiện Pháp y Đột phá:**
  * Tỷ lệ xung đột vật lý thực tế trên cổng tiếp xúc (Physical Contact Gate Conflicts) là **74.8%** (374/500 kịch bản có ít nhất 2 chuyến bay đè khoảng thời gian lên nhau trên cùng một cổng).
  * Trong **126 kịch bản còn lại (25.2%)**, **HOÀN TOÀN KHÔNG CÓ XUNG ĐỘT VẬT LÝ NÀO** và không vi phạm sức chứa cổng từ xa (`remote_capacity_violation = False`).
  * **Tại sao hệ thống vẫn đánh dấu `feasible = False` cho cả 126 kịch bản này?**
    * Khi đánh giá nghiệm đóng băng, bộ kiểm chứng độc lập so sánh thời gian chiếm dụng cổng đã ghi trong kế hoạch ban đầu (`assign.occupancy_start_min`) với thời gian bay thực tế của chuyến bay (`f.time_window.start_min`).
    * Vì mọi chuyến bay đều bị trễ ngẫu nhiên dù chỉ 1 phút, xuất hiện lỗi **`timeline_mismatch_violation`** trên toàn bộ các chuyến bay:
      ```python
      if assign.occupancy_start_min != f.time_window.start_min:
          timeline_mismatch_violations.append(...)
      ```
    * Vì `hard_constraint_violations_count` bao gồm cả số lỗi lệch mốc thời gian này, `diag.is_valid` trả về `False`!
    * **Bản chất khoa học:** Đây là **sự không tương thích của khe thời gian tĩnh (Static Slot Timeline Infeasibility)** chứ **KHÔNG PHẢI là va chạm vật lý giữa hai máy bay (Physical Gate Collision)**!

### Q10: Vì sao Greedy, CP-SAT và Hybrid có chi phí trên từng kịch bản giống hệt nhau (Identical Costs) trong Mode A?
* **Trả lời:**
  * Kiểm toán đã chạy nghiệm thu độc lập trên kịch bản gốc `SCEN_P09_CANONICAL_120` (120 chuyến bay, 25 cổng tiếp xúc, 5 cổng từ xa).
  * **Kết quả:** Cả 3 bộ giải Greedy, CP-SAT và Hybrid đều tìm ra **cùng một kế hoạch phân bổ ban đầu giống hệt nhau 100%** với giá trị mục tiêu $J = 0.0$ (`g_assign == c_assign == h_assign: True`).
  * Vì kế hoạch ban đầu đưa vào đóng băng ở Mode A là cùng một phương án duy nhất, khi thử nghiệm trên 500 kịch bản trễ, kết quả đánh giá của cả 3 bộ giải tự nhiên trùng khít nhau 100%!

### Q11: Vì sao Mode B Greedy và Mode C có kết quả gần như giống nhau?
* **Trả lời:**
  * Trong Mode B khi áp dụng cho kế hoạch Greedy, bộ giải phản ứng chạy lại `DeterministicGreedyGateSolver`.
  * Mode C cũng chạy trực tiếp `DeterministicGreedyGateSolver` trên các chuyến bay thực tế.
  * Vì cả hai đều sử dụng cùng thuật toán Heuristic Tham lam sắp xếp theo thời gian đến, khi có biến động trễ lớn, kết quả phân bổ lại của Mode B Heuristic và Mode C Oracle Heuristic hội tụ về cùng một hành vi sắp xếp.

### Q12: Những kết luận cải thiện hiệu quả thuật toán nào thực sự được các con số hỗ trợ?
* **Được hỗ trợ:** Kế hoạch có cơ chế ứng phó chủ động (Mode B Recourse) giảm thiểu rủi ro vận hành từ 74.8% xung đột xuống **0.0% xung đột** và đưa khả năng vận hành thực tế đạt **100%**.
* **Được hỗ trợ:** Chi phí kỳ vọng của phương án phản ứng Mode B ($J \approx 133.5$) thấp hơn vượt bậc so với chi phí tổn thất do xung đột nếu giữ nguyên kế hoạch tĩnh Mode A ($J \approx 1469.2$).
* **KHÔNG ĐƯỢC hỗ trợ:** Bất kỳ tuyên bố nào cho rằng "CP-SAT có độ bền vững vượt trội hơn Greedy trong Mode A của P09" đều không có cơ sở dữ liệu hỗ trợ, vì cả 3 thuật toán đều đánh giá trên cùng một phương án ban đầu giống hệt nhau!

### Q13: Khoảng tin cậy (CI), kiểm định bắt cặp (Paired Test) và CVaR có dùng đúng đơn vị quan sát không?
* **Trả lời:** **CÓ.** Các chỉ số thống kê trong `paired_comparison.csv` và `statistical_summary.json` được tính trên từng cặp kịch bản đồng nhất $s \in \{0, \dots, 499\}$, đảm bảo bậc tự do $N-1 = 499$ và áp dụng chuẩn xác kiểm định Wilcoxon signed-rank / paired t-test.

---

## 2. Bảng Phân loại Chi tiết Năm Chiều Khả thi Vận hành (Operational Feasibility Dimensions)

Nhằm làm sáng tỏ báo cáo khoa học, kiểm toán lập bảng phân định rõ ràng giữa các khái niệm khả thi:

| Khái niệm Khả thi (Feasibility Dimension) | Định nghĩa Toán học & Vận hành | Tỷ lệ Đạt được trong P09 (Mode A) | Tỷ lệ Đạt được trong P09 (Mode B) |
| :--- | :--- | :---: | :---: |
| **`STATIC_SLOT_FEASIBILITY`** | Chuyến bay chiếm dụng đúng khe thời gian kế hoạch ban đầu $[T_{\text{in}}, T_{\text{out}}]$. | **0.0%** (Do trễ giờ ngẫu nhiên làm xê dịch mốc thời gian của mọi chuyến bay) | N/A (Được cập nhật động theo giờ trễ) |
| **`PHYSICAL_GATE_CONFLICT`** | Tồn tại $\ge 2$ chuyến bay cùng đỗ trên một cổng tiếp xúc trong cùng thời điểm. | **74.8% có xung đột** (25.2% hay 126 kịch bản hoàn toàn KHÔNG có xung đột vật lý) | **0.0% xung đột** (Triệt tiêu 100% xung đột vật lý) |
| **`BUFFER_VIOLATION`** | Khoảng cách giãn cách giữa hai chuyến bay liên tiếp trên cùng một cổng $< 15$ phút. | Xuất hiện kèm trong các kịch bản có xung đột vật lý. | **0.0% vi phạm** |
| **`CAPACITY_VIOLATION`** | Số lượng máy bay đồng thời đỗ tại cổng từ xa vượt quá sức chứa hữu hạn ($K = 5$). | **0.0% vi phạm** (Max concurrent remote luôn $\le 5$) | **0.0% vi phạm** |
| **`OPERATIONAL_RECOURSE_FEASIBILITY`** | Khả năng duy trì vận hành sân bay thông suốt sau khi áp dụng điều phối lại cổng. | **0.0%** (Do không thực hiện điều phối lại) | **100.0% Khả thi Vận hành** |

---

## 3. Các Phát hiện Kiểm toán Trọng yếu (Findings Register for Monte Carlo)

### FINDING-P0-01: Mode C Perfect Foresight Oracle Sử dụng Bộ giải Greedy thay vì CP-SAT Tối ưu Toàn cục
* **Severity:** `P0 (CRITICAL SCIENTIFIC DEVIATION)`
* **Expected:** Trong lý thuyết nghiên cứu Vận trù học (Operations Research) và đề cương khóa luận, nghiệm Oracle hoàn hảo (Perfect Foresight Lower Bound) phải là nghiệm tối ưu toàn cục được giải bằng CP-SAT hoặc MIP khi đã biết trước toàn bộ độ trễ thực tế.
* **Observed:** Tại dòng 446 của `src/simulation/monte_carlo_engine_p09.py`, Mode C được cài đặt trực tiếp bằng `DeterministicGreedyGateSolver`.
* **Impact:** Ngưỡng cận dưới của Oracle trong báo cáo P09 không phải là cận dưới tối ưu toán học (Optimal Lower Bound) mà chỉ là cận dưới đạt được bởi thuật toán tham lam khi có thông tin tương lai.
* **Proposed Resolution:** Nêu rõ sự thật này trong quyển khóa luận như một giới hạn thực nghiệm được thừa nhận: Mode C là "Greedy Foresight Benchmark" để đảm bảo thời gian tính toán trong 500 kịch bản; đề xuất hướng phát triển giải Mode C bằng CP-SAT phân tán trong tương lai.
* **Confidence:** `HIGH`

### FINDING-P1-04: Đánh đồng Infeasibility do Lệch Khe Thời gian Tĩnh với Xung đột Vật lý trong Mode A
* **Severity:** `P1 (HIGH)`
* **Expected:** Phân biệt rõ giữa việc "kế hoạch bị lệch giờ" và "máy bay bị va chạm cổng đỗ".
* **Observed:** Báo cáo P09 kết luận Mode A có Feasibility = 0% tạo cảm giác 100% kịch bản đều bị đụng độ cổng, trong khi thực tế có 126 kịch bản (25.2%) hoàn toàn không có xung đột vật lý nào xảy ra trên cổng.
* **Impact:** Làm trầm trọng hóa mức độ rủi ro vật lý của kế hoạch tĩnh, thiếu độ tinh tế trong phân tích học thuật.
* **Proposed Resolution:** Bổ sung bảng phân biệt 5 chiều khả thi như trên vào chương thực nghiệm của khóa luận để bảo vệ sự chính xác trước hội đồng chấm thi.
* **Confidence:** `HIGH`
