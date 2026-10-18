# BÁO CÁO KIỂM TOÁN 08: SỔ ĐĂNG KÝ VẤN ĐỀ VÀ PHÁT HIỆN PHÁP Y (MASTER ISSUE & FINDINGS REGISTER)

**Dự án:** Aeolus Gate Optimization (`aeolus-gate-optimization`)  
**Khóa luận:** Cử nhân Công nghệ Thông tin  
**Thời điểm kiểm toán:** 2026-10-11T15:44:00+07:00  
**Vai trò thẩm định:** Principal Software Architect, Operations Research Auditor, Thesis QA Lead  

---

## 1. Bảng Tổng hợp Mức độ Nghiêm trọng (Findings Severity Breakdown)

| Mức độ Nghiêm trọng (Severity) | Định nghĩa Nghiệp vụ / Học thuật | Số lượng Phát hiện |
| :--- | :--- | :---: |
| **`P0 (CRITICAL)`** | Lỗ hổng học thuật hoặc thiếu sót nghiêm trọng ảnh hưởng trực tiếp đến kết quả bảo vệ khóa luận. | **2** |
| **`P1 (HIGH)`** | Sai lệch phương pháp luận, thiếu hụt dữ liệu thực nghiệm hoặc cách tính toán chưa chuẩn hóa. | **5** |
| **`P2 (MEDIUM)`** | Giới hạn kỹ thuật, nhầm lẫn tài liệu hoặc thiếu bước kiểm thử thị giác người thật. | **4** |
| **TỔNG CỘNG** | | **11 Phát hiện** |

---

## 2. Chi tiết Toàn bộ Phát hiện Kiểm toán (Comprehensive Findings Catalog)

### FINDING-P0-01: Mode C Perfect Foresight Oracle Cài đặt bằng Thuật toán Greedy thay vì Bộ giải Tối ưu CP-SAT
* **Severity:** `P0 (CRITICAL)`
* **Expected:** Trong lý thuyết Vận trù học và đề cương khóa luận, cận dưới Oracle (Perfect Foresight Lower Bound) khi biết trước toàn bộ độ trễ thực tế phải là nghiệm tối ưu toàn cục được giải bằng CP-SAT hoặc MIP.
* **Observed:** Trong `src/simulation/monte_carlo_engine_p09.py` (dòng 446–447), Mode C được cài đặt trực tiếp bằng `DeterministicGreedyGateSolver`.
* **Evidence:** `src/simulation/monte_carlo_engine_p09.py#L446-L447`.
* **Reproduction Command:** `python -c "from src.simulation.monte_carlo_engine_p09 import evaluate_mode_c_perfect_foresight_oracle; import inspect; print(inspect.getsource(evaluate_mode_c_perfect_foresight_oracle))"`
* **Actual Result:** Mã nguồn khởi tạo `oracle_solver = DeterministicGreedyGateSolver(config=config)`.
* **Impact:** Ngưỡng cận dưới lý thuyết của Oracle trong báo cáo P09 không phải là nghiệm tối ưu toán học (Optimal Lower Bound) mà chỉ là nghiệm của thuật toán tham lam khi có thông tin tương lai.
* **Proposed Resolution:** Bổ sung luận giải trong phần báo cáo khóa luận: Mode C trong P09 là "Greedy Foresight Benchmark" để đảm bảo khả năng tính toán trong 500 kịch bản; đề xuất hướng nghiên cứu giải Mode C bằng CP-SAT trong tương lai.
* **Confidence:** `HIGH`

---

### FINDING-P0-02: Kho Lưu trữ Chưa Có Quyển Khóa luận và Slide Thuyết trình Chính thức
* **Severity:** `P0 (CRITICAL)`
* **Expected:** Đối với một đồ án tốt nghiệp cử nhân CNTT chuẩn bị bảo vệ, kho lưu trữ hoặc thư mục `reports/` phải có bản thảo quyển khóa luận (`.docx`, `.pdf` hoặc `.tex`) và slide thuyết trình (`.pptx`).
* **Observed:** Thư mục `reports/final` và `reports/development` hoàn toàn trống rỗng; không tìm thấy bất kỳ tệp văn bản luận văn hay slide báo cáo nào trong kho mã nguồn.
* **Evidence:** Thư mục `reports/final/` và `reports/development/`.
* **Reproduction Command:** `Get-ChildItem reports\final; Get-ChildItem reports\development`
* **Actual Result:** 0 files found.
* **Impact:** Mặc dù hệ thống kỹ thuật, mã nguồn và dữ liệu kiểm thử rất đồ sộ, sinh viên chưa có sản phẩm văn bản tốt nghiệp để nộp cho Hội đồng chấm thi.
* **Proposed Resolution:** Khẩn trương sử dụng các dữ liệu đã được chứng nhận và các báo cáo kiểm toán này để biên soạn Quyển Khóa luận và Slide Báo cáo.
* **Confidence:** `HIGH`

---

### FINDING-P1-01: Xác suất Trễ Khởi hành Outbound Được Tính Bằng Hàm Sigmoid Heuristic từ Hồi quy
* **Severity:** `P1 (HIGH)`
* **Expected:** Theo mục 2 của đề cương, $P(\text{delay} \ge 15\text{ phút})$ cần được dự báo bằng mô hình phân loại (Logistic Regression, Random Forest, XGBoost Classifier) có phân phối xác suất hiệu chuẩn.
* **Observed:** Trong `scripts/generate_p08_validation_artifacts.py` (dòng 134–136), xác suất trễ khởi hành được tính bằng công thức hàm Sigmoid tự tạo từ đầu ra hồi quy: $\text{score} = 1.0 / (1.0 + \exp(-(\text{pred} - 15.0) / 10.0))$.
* **Evidence:** `scripts/generate_p08_validation_artifacts.py#L134-L136`.
* **Reproduction Command:** Xem dòng 134–136 trong script P08.
* **Actual Result:** Xác suất không đến từ `predict_proba()` của một mô hình phân loại được huấn luyện độc lập.
* **Impact:** Metric phân loại (ROC-AUC, PR-AUC) của Outbound phản ánh khả năng xếp hạng của mô hình hồi quy chứ không chứng minh hiệu năng của bộ phân loại nhị phân riêng biệt.
* **Proposed Resolution:** Nêu rõ trong khóa luận đây là "Continuous Delay Risk Score Mapping", hoặc huấn luyện bổ sung một mô hình phân loại nhị phân thực thụ nếu có yêu cầu khắt khe từ hội đồng.
* **Confidence:** `HIGH`

---

### FINDING-P1-02: Bảng Cắt bỏ Đặc trưng Feature Ablation (A/B/C) là Bảng Hằng số Tĩnh
* **Severity:** `P1 (HIGH)`
* **Expected:** Thí nghiệm so sánh Tabular vs Tabular + Chain vs Weather phải có mã nguồn chạy trực tiếp trên tập dữ liệu.
* **Observed:** Trong `scripts/generate_p08_validation_artifacts.py` (dòng 367–420), toàn bộ các giá trị MAE, RMSE, CRPS của 3 kịch bản đều là hằng số hardcode trong từ điển Python và ghi thẳng ra CSV.
* **Evidence:** `scripts/generate_p08_validation_artifacts.py#L367-L420`.
* **Reproduction Command:** Xem định nghĩa hàm `generate_feature_ablation()`.
* **Actual Result:** Không có vòng lặp tính toán lỗi hay nạp dữ liệu trong hàm này.
* **Impact:** Thiếu pipeline tự động hóa đầu-cuối để tái lập lại bảng ablation này từ dữ liệu thô.
* **Proposed Resolution:** Bổ sung ghi chú giải trình trong khóa luận: Bảng thực nghiệm này được đóng băng từ pha nghiên cứu Feature Engineering trước đó và dùng làm bằng chứng chính sách để loại bỏ dữ liệu rò rỉ.
* **Confidence:** `HIGH`

---

### FINDING-P1-03: Lượt Chạy Chứng nhận P07 Chỉ Sử dụng 30 Chuyến bay và Toàn bộ là Cặp Giả lập
* **Severity:** `P1 (HIGH)`
* **Expected:** Pipeline P07 được kiểm chứng đầu-cuối trên 100–300 chuyến bay/ngày với các cặp luân chuyển máy bay thật (`VERIFIED_PAIR` theo tail number).
* **Observed:** Trong `artifacts/remediation/native_dual_core/run_manifest.json`, tổng số chuyến là 30, và có 30 `synthetic_pairs_count`, 0 `verified_pairs_count`.
* **Evidence:** `artifacts/remediation/native_dual_core/run_manifest.json#L38-L50`.
* **Reproduction Command:** Đọc nội dung `run_manifest.json`.
* **Actual Result:** `verified_pairs_count: 0`.
* **Impact:** Chưa có bằng chứng thực nghiệm tích hợp P07 chạy trên 300 chuyến bay thật với tail-number matching hoàn hảo.
* **Proposed Resolution:** Trình bày rõ ràng: Lượt chạy chứng nhận P07 là "Smoke Integration Baseline"; việc mở rộng quy mô lớn hơn đã được chứng minh riêng biệt trong bộ thử nghiệm CP-SAT Scalability (100–300 chuyến bay) và Monte Carlo P09 (120 chuyến bay).
* **Confidence:** `HIGH`

---

### FINDING-P1-04: Đánh đồng Infeasibility do Lệch Khe Thời gian Tĩnh với Xung đột Vật lý trong Mode A
* **Severity:** `P1 (HIGH)`
* **Expected:** Báo cáo cần phân biệt rạch ròi giữa việc "chuyến bay bị trễ giờ so với lịch" và "máy bay va chạm cổng đỗ".
* **Observed:** Báo cáo P09 kết luận Mode A có Feasibility = 0% tạo cảm giác 100% kịch bản đều bị đụng độ cổng, trong khi thực tế có 126 kịch bản (25.2%) hoàn toàn không có xung đột vật lý nào xảy ra trên cổng đỗ tiếp xúc.
* **Evidence:** `src/optimization/domain.py#L1223-L1232` và `artifacts/remediation/monte_carlo/fixed_plan_results.csv`.
* **Reproduction Command:** Đếm số dòng có `conflict_count == 0` trong `fixed_plan_results.csv` (126 dòng).
* **Actual Result:** Cả 126 dòng này đều bị gán `feasible: False` do lỗi `timeline_mismatch_violations`.
* **Impact:** Làm trầm trọng hóa mức độ rủi ro vật lý của kế hoạch tĩnh, thiếu độ tinh tế trong phân tích học thuật.
* **Proposed Resolution:** Đưa bảng phân loại 5 chiều khả thi vào khóa luận để chứng minh khả năng phân tích sâu sắc của sinh viên.
* **Confidence:** `HIGH`

---

### FINDING-P1-05: Tài liệu Dự án Thường xuyên Nhầm lẫn giữa Khóa luận Cử nhân và Luận văn Thạc sĩ
* **Severity:** `P1 (HIGH)`
* **Expected:** Nhãn học vị của khóa luận tốt nghiệp phải nhất quán là Cử nhân Công nghệ Thông tin (Bachelor of Science / Bachelor's Thesis).
* **Observed:** Trong nhiều tài liệu (ví dụ: `docs/dashboard_discovery/01_project_architecture.md`, `05_monte_carlo_capabilities.md`, `10_CHATGPT_HANDOFF_SUMMARY.md`, `docs/remediation/09_robustness_validation_report.md`), dự án được ghi là **"Master's Thesis"** (Luận văn Thạc sĩ).
* **Evidence:** `docs/dashboard_discovery/01_project_architecture.md#L4`, `docs/remediation/09_robustness_validation_report.md#L11`.
* **Reproduction Command:** `git grep -i "master's thesis" docs/`
* **Actual Result:** Xuất hiện hàng chục lần nhãn "Master's Thesis".
* **Impact:** Có thể gây hiểu lầm nghiêm trọng về cấp độ đề tài trước Hội đồng chấm thi đại học nếu đưa nguyên văn tài liệu này vào phụ lục.
* **Proposed Resolution:** Chuẩn hóa toàn bộ văn bản báo cáo và slide tốt nghiệp về đúng danh xưng "Khóa luận Tốt nghiệp Cử nhân CNTT".
* **Confidence:** `HIGH`

---

### FINDING-P2-01: Biến thể Tinh chỉnh HPO Arrival XGBoost Được Gán Hằng số Cố định trong Bảng Metric
* **Severity:** `P2 (MEDIUM)`
* **Expected:** Metric được suy ra từ các tệp dự báo OOF thực tế.
* **Observed:** Dòng dữ liệu cho `arrival_xgboost_tuned_v1_1` (dòng 107–124 trong script P08) được hardcode trực tiếp các giá trị số học.
* **Evidence:** `scripts/generate_p08_validation_artifacts.py#L107-L124`.
* **Impact:** Giảm tính tự động hóa tái lập của riêng bảng phân loại P08.
* **Proposed Resolution:** Lưu ý trong ghi chú phụ lục mã nguồn.
* **Confidence:** `HIGH`

---

### FINDING-P2-02: Bộ giải Lai Hybrid (CP-SAT + SA) Không Mang lại Cải thiện nào so với CP-SAT Thuần túy
* **Severity:** `P2 (MEDIUM)`
* **Expected:** Làm rõ vai trò thực tế của SA khi kết hợp với CP-SAT.
* **Observed:** 100% nghiệm của Hybrid trong `aggregate_metrics.json` có giá trị mục tiêu trùng khít với CP-SAT ($9351.6850$).
* **Evidence:** `artifacts/development_end_to_end/aggregate_metrics.json#L118-L217`.
* **Impact:** Khẳng định toán học: SA không cải thiện được CP-SAT khi CP-SAT đã tìm ra nghiệm tối ưu.
* **Proposed Resolution:** Nêu rõ trong khóa luận: SA đóng vai trò là giải pháp heuristic độc lập dự phòng, không phải là công cụ tối ưu hóa tiếp trên nghiệm của CP-SAT.
* **Confidence:** `HIGH`

---

### FINDING-P2-03: Kiểm thử Bảng điều khiển Mới Dừng lại ở Tầng Headless AppTest, Chưa Hoàn tất Human Visual QA trên Browser
* **Severity:** `P2 (MEDIUM)`
* **Expected:** Kiểm tra thực tế trên trình duyệt web, đảm bảo độ co giãn màn hình và tính tương tác.
* **Observed:** 359 bài test đều là kiểm thử headless thông qua `AppTest`. Báo cáo `UI-R08/05_visual_acceptance.md` ghi nhận `VISUAL_QA_PENDING`.
* **Evidence:** `docs/dashboard/redesign/UI-R08/05_visual_acceptance.md#L6`.
* **Impact:** Trạng thái kiểm toán thị giác là `VISUAL_QA_BLOCKED`.
* **Proposed Resolution:** Sinh viên chạy demo trực tiếp trên máy trước buổi bảo vệ.
* **Confidence:** `HIGH`

---

### FINDING-P2-04: Tham số Copula và Phân phối Monte Carlo là Hằng số Cấu hình Cố định
* **Severity:** `P2 (MEDIUM)`
* **Expected:** Tham số $\mu, \sigma, \nu$ được nạp trực tiếp từ đầu ra của mô hình học máy P4 cho từng chuyến bay cụ thể.
* **Observed:** Tham số phân phối Student-T và tương quan Copula ($\mu=5/8, \sigma=18/22, \nu=4.5/4.0, \rho=0.45$) là cấu hình hằng số mặc định trong bộ sinh kịch bản P09.
* **Evidence:** `src/simulation/monte_carlo_engine_p09.py#L133-L140`.
* **Impact:** Mô phỏng Monte Carlo phản ánh phân phối ngẫu nhiên chung của sân bay, chưa phản ánh đặc trưng cá thể hóa của từng chuyến bay từ mô hình P4.
* **Proposed Resolution:** Giải trình trong khóa luận: Đây là mô hình mô phỏng rủi ro tổng hợp cấp sân bay (Airport-level Aggregate Risk Simulation).
* **Confidence:** `HIGH`
