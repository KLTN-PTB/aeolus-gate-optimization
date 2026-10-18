# AEOLUS-G9 — Ma Trận Bằng Chứng Thực Nghiệm Cho Từng Chương Luận Văn

## 1. MỤC TIÊU CỦA MA TRẬN BẰNG CHỨNG (EVIDENCE MATRIX)

Ma trận này thiết lập liên kết trực tiếp giữa:
- **Từng chương / tiểu mục trong bản thảo khóa luận**
- **Yêu cầu tương ứng trong đề cương chính thức**
- **Nguồn bằng chứng thực nghiệm (CSV/JSON/Log)**
- **Bảng biểu / Hình vẽ đại diện**
- **Giới hạn khoa học bắt buộc phải thuyết minh**

Đảm bảo nguyên tắc học thuật: *Mọi số liệu công bố trong khóa luận đều có nguồn gốc kiểm chứng rõ ràng, không có số liệu ước lượng hoặc không thể truy vết.*

---

## 2. BẢNG MA TRẬN TRUY VẾT CHI TIẾT THEO CHƯƠNG

| Chương / Tiểu mục Luận văn | Yêu cầu Đề cương | Nguồn Bằng chứng (Evidence Source Path) | Bảng biểu / Hình vẽ Đại diện | Giới hạn Khoa học & Diễn giải Bắt buộc | Trạng thái Bằng chứng |
|:---|:---:|:---|:---|:---|:---:|
| **Chương 1** (1.3, 1.4) | `REQ-01`, `REQ-10` | `remediation_evidence/G8_scientific_release/06_GATE_REPORT.md` | Bảng 1.1: Bảng phân loại mục tiêu và phạm vi nghiên cứu | Khóa luận Cử nhân CNTT tập trung vào mô phỏng và tối ưu toán học; không có kết nối hệ thống radar sân bay thời gian thực. | **VERIFIED** |
| **Chương 2** (2.1–2.6) | Toàn bộ | `docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md` | Hình 2.1: Khung kiến trúc Predict-then-Optimize trong AGAP | Tổng quan tài liệu học thuật quốc tế (2018–2025); chỉ trích dẫn tài liệu thật đã kiểm chứng. | **VERIFIED** |
| **Chương 3 (Mục 3.1, 3.2)**: Dữ liệu & Phân vùng | `REQ-01`, `REQ-03` | `data/processed/`, `remediation_evidence/G1_data_contracts/04_EVIDENCE_MANIFEST.json` | Bảng 3.1: Tổng quan phân vùng thời gian CSDL Aeolus ATL (2016–2024) | Tập 2024 là vùng cấm bảo lưu; tập 2023 là tập benchmark chọn mô hình chính thức. | **VERIFIED** |
| **Chương 3 (Mục 3.3)**: Rào chắn thời gian | `REQ-01`, `REQ-04` | `src/contracts/temporal.py`, `artifacts/remediation/ml_validation/leakage_audit.json` | Hình 3.1: Sơ đồ rào chắn thông tin $T-2\text{h}$ và phân loại tính khả dụng đặc trưng | Flight Chain và METAR bị loại trừ khỏi pipeline chính do rủi ro rò rỉ thông tin tương lai tại $T-2\text{h}$. | **VERIFIED** |
| **Chương 3 (Mục 3.4)**: Mô hình ML Hai lõi | `REQ-02` | `artifacts/dual_core/models/`, `artifacts/probabilistic/ngboost_student_t/` | Hình 3.2: Sơ đồ luồng dự báo trễ Hai lõi (Dual-Core ML Pipeline) | Inbound dùng NGBoost Student-t; Outbound dùng Calibrated XGBoost và Logistic Regression. | **VERIFIED** |
| **Chương 3 (Mục 3.5)**: Mô hình CP-SAT | `REQ-05` | `src/optimization/domain.py`, `src/optimization/solvers/cp_sat_solver.py` | Bảng 3.2: Danh mục biến và tham số mô hình tối ưu hóa AGAP | Tách biệt hoàn toàn Decision Cost ($J_{\text{decision}}$) và Reporting Cost ($J_{\text{reporting}}$). | **VERIFIED** |
| **Chương 3 (Mục 3.6)**: Mô phỏng Monte Carlo | `REQ-08` | `src/simulation/monte_carlo_engine_v2.py`, `artifacts/remediation/monte_carlo_remediated/` | Hình 3.3: Sơ đồ kiến trúc 3 chế độ mô phỏng Monte Carlo (Mode A, B, C) | Mode B2 là online event-driven causal recourse; Mode C-Oracle là CP-SAT optimal lower bound. | **VERIFIED** |
| **Chương 4 (Mục 4.1–4.4)**: Thiết kế Hệ thống | `REQ-05`, `REQ-07` | `src/simulation/verified_pairing.py`, `src/optimization/solvers/` | Hình 4.1: Sơ đồ kiến trúc tổng thể 4 tầng của hệ thống Aeolus | Động cơ ghép cặp tuân thủ nguyên tắc không bịa số hiệu đuôi máy bay; Fail-closed trên dữ liệu khuyết. | **VERIFIED** |
| **Chương 4 (Mục 4.5)**: Dashboard Vận hành | `REQ-09` | `dashboard/`, `docs/dashboard/redesign/UI-R08/` | Hình 4.2: Sơ đồ kiến trúc 5 trang của bảng điều khiển Streamlit | Phân tách Presentation Mode và Research Mode; bảo vệ chống tấn công đường dẫn Path Traversal. | **VERIFIED** |
| **Chương 5 (Mục 5.1)**: Kết quả Dự báo ML | `REQ-02` | `artifacts/remediation/outbound_classification/calibrated_metrics.json`, `artifacts/remediation/ml_validation/regression_metrics.csv` | Bảng 5.1: Đánh giá phân loại trễ Outbound ($P \ge 15$m)<br>Bảng 5.2: Đánh giá hồi quy trễ khởi hành trên tập 2023 | Median Baseline thắng MAE do cực tiểu hóa hàm mất mát $L_1$ trên phân phối lệch; ML thắng RMSE và sai số đuôi nặng $\ge 15, \ge 60$m. | **VERIFIED** |
| **Chương 5 (Mục 5.2)**: Mô hình Xác suất P4 | `REQ-02` | `artifacts/probabilistic/ngboost_student_t/`, `artifacts/remediation/ml_validation/probabilistic_metrics.csv` | Bảng 5.3: Tham số phân phối Student-t và độ bao phủ phân vị | Model P4 có checkpoint nhị phân native phục vụ lấy mẫu mô phỏng; Model P5 chỉ là baseline ngoại tuyến. | **VERIFIED** |
| **Chương 5 (Mục 5.3)**: Cắt bỏ đặc trưng | `REQ-04` | `artifacts/remediation/ml_validation/feature_ablation.csv` | Bảng 5.4: Kết quả nghiên cứu cắt bỏ đặc trưng (Feature Ablation Study) | Trình bày như Nghiên cứu Khám phá; giải thích khoa học về nguyên nhân phong tỏa Flight Chain. | **VERIFIED** |
| **Chương 5 (Mục 5.4)**: Benchmark CP-SAT | `REQ-05`, `REQ-10` | `artifacts/remediation/cp_sat/parity_results.json`, `artifacts/remediation/benchmarks/g5_fair_benchmark/fair_benchmark_results.json` | Bảng 5.5: Kiểm chứng toán học CP-SAT đối chiếu Exhaustive Combinatorial Oracle<br>Bảng 5.6: Hiệu năng tối ưu CP-SAT so với Greedy (100–300 chuyến) | CP-SAT giảm chi phí từ $14.8\%$ đến $25.8\%$ so với Greedy; nghiệm khớp Oracle với sai số $< 10^{-4}$. | **VERIFIED** |
| **Chương 5 (Mục 5.5)**: SA và Hybrid | `REQ-06`, `REQ-07` | `artifacts/development_end_to_end/aggregate_metrics.json`, `artifacts/remediation/benchmarks/g5_fair_benchmark/` | Bảng 5.7: So sánh đa bộ giải trên tập kịch bản chuẩn (Greedy, CP-SAT, SA, Hybrid) | Định lý toán học: Hybrid đạt 0.00% cải thiện khi CP-SAT đã tối ưu toàn cục; SA là bộ giải dự phòng. | **VERIFIED** |
| **Chương 5 (Mục 5.6)**: Mô phỏng Monte Carlo | `REQ-08` | `artifacts/remediation/monte_carlo_remediated/remediated_statistical_summary.json`, `...paired_comparison.csv` | Bảng 5.8: So sánh thống kê 3 chế độ mô phỏng Monte Carlo (100 kịch bản ngẫu nhiên) | Mode A có 76.0% xung đột vật lý và 0% khả thi lịch trình tĩnh; Mode B2 online recourse tiết kiệm $1,459.0$ điểm chi phí ($p < 10^{-20}$). | **VERIFIED** |
| **Chương 5 (Mục 5.7)**: Luồng Dữ liệu Thật | `REQ-10` | `artifacts/remediation/native_dual_core_g4_pilot/run_manifest.json` | Bảng 5.9: Kết quả chạy tích hợp luồng dữ liệu thật Thanksgiving 2023 ATL (200 chuyến) | CSDL mở BTS khuyết cột `TAIL_NUM`; hệ thống giải tối ưu 200 chuyến độc lập hoặc suy diễn 59 cặp quay đầu. | **VERIFIED** |
| **Chương 5 (Mục 5.8)**: Đánh giá Dashboard | `REQ-09` | `docs/dashboard/redesign/UI-R08/`, `tests/dashboard/` | Bảng 5.10: Kết quả kiểm thử tự động 359 test và checklist thị giác | 359 AppTest tests đạt 100%; kiểm tra thị giác tương tác trực tiếp ghi nhận `VISUAL_QA_PENDING` (sẵn sàng demo live). | **VERIFIED** |
| **Chương 6** (6.1–6.4) | Tổng kết | `remediation_evidence/G8_scientific_release/12_DISCLOSURES_FOR_DEFENSE.md` | Bảng 6.1: Tổng kết mức độ đáp ứng 10 yêu cầu đề cương khóa luận | Công bố đầy đủ 10 giới hạn khoa học và chuẩn bị cẩm nang phản biện bảo vệ luận văn. | **VERIFIED** |
