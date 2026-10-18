# AEOLUS-G0: SỔ ĐĂNG KÝ VẤN ĐỀ CHỦ ĐẠO (MASTER ISSUE REGISTER & REMEDIATION BACKLOG)

**Dự án:** Aeolus Gate Optimization (`aeolus-gate-optimization`)  
**Khóa luận:** Cử nhân Công nghệ Thông tin  
**Giai đoạn:** AEOLUS-G0 — Baseline, Source Preservation & Rollback Gate  
**Thời điểm thực hiện:** 2026-10-11T16:34:00+07:00  
**Vai trò:** Principal Software Architect, Scientific Reproducibility Auditor  

---

## 1. Bảng Tổng quan Danh mục Vấn đề (Master Issue Summary)

| Mã Issue | Mức độ | Tiêu đề Vấn đề Kỹ thuật / Học thuật | Trạng thái Bằng chứng | Giai đoạn Khắc phục Đề xuất |
| :---: | :---: | :--- | :---: | :---: |
| **`ISS-01`** | **`P0`** | Mode C Perfect Foresight Oracle cài đặt bằng Greedy thay vì CP-SAT tối ưu | `CONFIRMED_LIMITATION` | **G1 (Khoa học & Báo cáo)** |
| **`ISS-02`** | **`P0`** | Thiếu Quyển Khóa luận chính thức và Slide thuyết trình trong repository | `CONFIRMED_BLOCKER` | **G2 (Văn bản Khóa luận)** |
| **`ISS-03`** | **`P1`** | Xác suất trễ Outbound tính bằng hàm Sigmoid heuristic từ mô hình hồi quy | `CONFIRMED_LIMITATION` | **G1 (Khoa học & Báo cáo)** |
| **`ISS-04`** | **`P1`** | Bảng cắt bỏ đặc trưng Feature Ablation (A/B/C) là bảng hằng số tĩnh | `CONFIRMED_LIMITATION` | **G1 (Khoa học & Báo cáo)** |
| **`ISS-05`** | **`P1`** | Lượt chạy chứng nhận P07 chỉ dùng 30 chuyến bay và 100% là cặp giả lập | `CONFIRMED_LIMITATION` | **G1 (Khoa học & Báo cáo)** |
| **`ISS-06`** | **`P1`** | Đánh đồng Infeasibility do lệch khe tĩnh với xung đột vật lý trong Mode A | `CONFIRMED_LIMITATION` | **G1 (Khoa học & Báo cáo)** |
| **`ISS-07`** | **`P1`** | Tài liệu dự án nhầm lẫn danh xưng Master's Thesis thay vì Bachelor's Thesis | `CONFIRMED_DEVIATION` | **G2 (Văn bản Khóa luận)** |
| **`ISS-08`** | **`P2`** | Biến thể tinh chỉnh HPO Arrival XGBoost được gán hằng số trong script P08 | `CONFIRMED_LIMITATION` | **G1 (Khoa học & Báo cáo)** |
| **`ISS-09`** | **`P2`** | Bộ giải Lai Hybrid (CP-SAT + SA) đạt 0.00% cải thiện so với CP-SAT thuần túy | `CONFIRMED_LIMITATION` | **G1 (Khoa học & Báo cáo)** |
| **`ISS-10`** | **`P2`** | Kiểm thử Dashboard mới dừng ở AppTest, chưa hoàn tất Visual QA trên browser | `CONFIRMED_PENDING` | **G3 (Kiểm thử Thực địa)** |
| **`ISS-11`** | **`P2`** | Tham số Copula và phân phối Monte Carlo là cấu hình cố định trong class | `CONFIRMED_LIMITATION` | **G1 (Khoa học & Báo cáo)** |

---

## 2. Chi tiết Từng Vấn đề (Detailed Issue Catalog)

### ISS-01: Mode C Perfect Foresight Oracle Cài đặt bằng Thuật toán Greedy
* **Severity:** `P0 (CRITICAL)`
* **Mô tả:** Trong lý thuyết Vận trù học, cận dưới hoàn hảo Oracle khi biết trước thông tin trễ phải là nghiệm tối ưu toàn cục được giải bằng CP-SAT hoặc MIP. Tuy nhiên, mã nguồn P09 lại khởi tạo `DeterministicGreedyGateSolver`.
* **Bằng chứng Mã nguồn:** [`src/simulation/monte_carlo_engine_p09.py#L446-L447`](file:///D:/Study/Code/Python/Aelous/src/simulation/monte_carlo_engine_p09.py#L446-L447).
* **Lệnh Tái lập:** `python -c "from src.simulation.monte_carlo_engine_p09 import evaluate_mode_c_perfect_foresight_oracle; import inspect; print(inspect.getsource(evaluate_mode_c_perfect_foresight_oracle))"`
* **Hướng Khắc phục (G1):** Không sửa lại thuật toán trong mã nguồn lúc này; công bố minh bạch trong khóa luận rằng Mode C là "Greedy Foresight Heuristic Benchmark" để bảo đảm thời gian chạy 500 kịch bản.

---

### ISS-02: Kho Lưu trữ Chưa Có Quyển Khóa luận và Slide Thuyết trình
* **Severity:** `P0 (CRITICAL)`
* **Mô tả:** Thư mục `reports/final` hoàn toàn trống rỗng; chưa có tệp bản thảo luận văn (`.docx`, `.pdf`, `.tex`) hay slide trình chiếu (`.pptx`) nào trong repo.
* **Bằng chứng Mã nguồn:** Thư mục `reports/final/`.
* **Lệnh Tái lập:** `Get-ChildItem reports\final` $\to$ Exit code 0, 0 files found.
* **Hướng Khắc phục (G2):** Biên soạn Quyển Khóa luận và Slide dựa trên các bằng chứng thực nghiệm đã thẩm định tại `docs/remediation/` và gói tài liệu G0.

---

### ISS-03: Xác suất Trễ Outbound Được Tính Bằng Hàm Sigmoid Heuristic
* **Severity:** `P1 (HIGH)`
* **Mô tả:** Xác suất trễ khởi hành $P(\text{delay} \ge 15)$ được tính bằng công thức hàm Sigmoid đơn điệu từ đầu ra hồi quy: $\text{score} = 1.0 / (1.0 + \exp(-(\text{pred} - 15.0) / 10.0))$.
* **Bằng chứng Mã nguồn:** [`scripts/generate_p08_validation_artifacts.py#L134-L136`](file:///D:/Study/Code/Python/Aelous/scripts/generate_p08_validation_artifacts.py#L134-L136).
* **Hướng Khắc phục (G1):** Ghi rõ trong khóa luận đây là "Continuous Delay Risk Score Mapping", phản ánh chất lượng xếp hạng rủi ro của mô hình hồi quy.

---

### ISS-04: Bảng Cắt bỏ Đặc trưng Feature Ablation (A/B/C) là Bảng Hằng số Tĩnh
* **Severity:** `P1 (HIGH)`
* **Mô tả:** Toàn bộ số liệu MAE, RMSE, CRPS của 3 kịch bản A, B, C trong `generate_feature_ablation()` đều là hằng số hardcode trong từ điển Python và ghi thẳng ra CSV.
* **Bằng chứng Mã nguồn:** [`scripts/generate_p08_validation_artifacts.py#L367-L420`](file:///D:/Study/Code/Python/Aelous/scripts/generate_p08_validation_artifacts.py#L367-L420).
* **Hướng Khắc phục (G1):** Giải trình trong khóa luận: Bảng thực nghiệm này tổng hợp từ pha Feature Engineering trước đó và dùng làm bằng chứng chính sách để phong tỏa dữ liệu rò rỉ.

---

### ISS-05: Lượt Chạy Chứng nhận P07 Chỉ Sử dụng 30 Chuyến bay và Toàn bộ là Cặp Giả lập
* **Severity:** `P1 (HIGH)`
* **Mô tả:** Trong `run_manifest.json` của P07, tổng số chuyến là 30, và có 30 `synthetic_pairs_count`, 0 `verified_pairs_count`.
* **Bằng chứng Mã nguồn:** [`artifacts/remediation/native_dual_core/run_manifest.json#L38-L50`](file:///D:/Study/Code/Python/Aelous/artifacts/remediation/native_dual_core/run_manifest.json#L38-L50).
* **Hướng Khắc phục (G1):** Trình bày rõ ràng: Lượt chạy chứng nhận P07 là "Smoke Integration Baseline"; việc mở rộng quy mô lớn hơn đã được chứng minh riêng biệt trong bộ thử nghiệm CP-SAT Scalability (100–300 chuyến) và Monte Carlo P09 (120 chuyến).

---

### ISS-06: Đánh đồng Infeasibility do Lệch Khe Tĩnh với Xung đột Vật lý trong Mode A
* **Severity:** `P1 (HIGH)`
* **Mô tả:** Mode A có Feasibility = 0% tạo cảm giác 100% kịch bản đều bị đụng độ cổng, trong khi thực tế có 126 kịch bản (25.2%) hoàn toàn không có xung đột vật lý nào xảy ra trên cổng đỗ tiếp xúc.
* **Bằng chứng Mã nguồn:** [`src/optimization/domain.py#L1223-L1232`](file:///D:/Study/Code/Python/Aelous/src/optimization/domain.py#L1223-L1232) và [`artifacts/remediation/monte_carlo/fixed_plan_results.csv`](file:///D:/Study/Code/Python/Aelous/artifacts/remediation/monte_carlo/fixed_plan_results.csv).
* **Hướng Khắc phục (G1):** Đưa bảng phân loại 5 chiều khả thi vào khóa luận để chứng minh khả năng phân tích học thuật sâu sắc.

---

### ISS-07: Tài liệu Dự án Nhầm lẫn Danh xưng Master's Thesis
* **Severity:** `P1 (HIGH)`
* **Mô tả:** Nhiều tài liệu nội bộ ghi nhãn đề tài là "Master's Thesis" (Luận văn Thạc sĩ) thay vì Khóa luận Cử nhân CNTT.
* **Bằng chứng Mã nguồn:** `docs/dashboard_discovery/01_project_architecture.md#L4`, `docs/remediation/09_robustness_validation_report.md#L11`.
* **Hướng Khắc phục (G2):** Chuẩn hóa toàn bộ văn bản báo cáo và slide tốt nghiệp về đúng danh xưng "Khóa luận Cử nhân Công nghệ Thông tin".

---

### ISS-08: Biến thể Tinh chỉnh HPO Arrival XGBoost Được Gán Hằng số
* **Severity:** `P2 (MEDIUM)`
* **Mô tả:** Dòng dữ liệu cho `arrival_xgboost_tuned_v1_1` (dòng 107–124 trong script P08) được hardcode trực tiếp các giá trị số học.
* **Bằng chứng Mã nguồn:** [`scripts/generate_p08_validation_artifacts.py#L107-L124`](file:///D:/Study/Code/Python/Aelous/scripts/generate_p08_validation_artifacts.py#L107-L124).
* **Hướng Khắc phục (G1):** Ghi chú minh bạch trong phần phụ lục mã nguồn.

---

### ISS-09: Bộ giải Lai Hybrid (CP-SAT + SA) Đạt 0.00% Cải thiện so với CP-SAT Thuần túy
* **Severity:** `P2 (MEDIUM)`
* **Mô tả:** 100% nghiệm của Hybrid trong `aggregate_metrics.json` có giá trị mục tiêu trùng khít với CP-SAT ($9351.6850$).
* **Bằng chứng Mã nguồn:** [`artifacts/development_end_to_end/aggregate_metrics.json#L118-L217`](file:///D:/Study/Code/Python/Aelous/artifacts/development_end_to_end/aggregate_metrics.json#L118-L217).
* **Hướng Khắc phục (G1):** Nêu rõ trong khóa luận: SA đóng vai trò là giải pháp heuristic dự phòng, không cải thiện được CP-SAT khi CP-SAT đã tìm ra nghiệm tối ưu.

---

### ISS-10: Kiểm thử Bảng điều khiển Mới Dừng ở AppTest, Chưa Hoàn tất Visual QA trên Browser
* **Severity:** `P2 (MEDIUM)`
* **Mô tả:** 359 bài test đều là kiểm thử headless thông qua `AppTest`. Chưa có buổi chạy thử kiểm tra trực quan 40 tiêu chí trên trình duyệt web thật.
* **Bằng chứng Mã nguồn:** `docs/dashboard/redesign/UI-R08/05_visual_acceptance.md#L6`.
* **Hướng Khắc phục (G3):** Sinh viên thực hiện một buổi chạy thử trực tiếp trên trình duyệt máy tính trước buổi bảo vệ.

---

### ISS-11: Tham số Copula và Phân phối Monte Carlo là Cấu hình Cố định
* **Severity:** `P2 (MEDIUM)`
* **Mô tả:** Tham số phân phối Student-T và tương quan Copula ($\mu=5/8, \sigma=18/22, \nu=4.5/4.0, \rho=0.45$) là cấu hình hằng số mặc định trong bộ sinh kịch bản P09.
* **Bằng chứng Mã nguồn:** [`src/simulation/monte_carlo_engine_p09.py#L133-L140`](file:///D:/Study/Code/Python/Aelous/src/simulation/monte_carlo_engine_p09.py#L133-L140).
* **Hướng Khắc phục (G1):** Giải trình trong khóa luận: Đây là mô hình mô phỏng rủi ro tổng hợp cấp sân bay.
