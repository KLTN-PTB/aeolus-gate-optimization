# BÁO CÁO TỔNG HỢP TOÀN DIỆN: CHUỖI FORENSIC REPAIR & CERTIFICATION R25 – R31

**Dự án**: Aeolus Probabilistic Core Arrival & Gate Optimization — V4  
**Ngày thực hiện**: 03/10/2026  
**Môi trường thực thi**: Python 3.11.15, Windows 10 AMD64, Git Commit `c99b3e84`  
**Phán quyết kiểm định cuối cùng**: **`CERTIFIED_WITH_LIMITATIONS`**  
**Trạng thái kiểm thử toàn hệ thống**: **194/194 Tests PASS (100%)**

---

## I. TỔNG QUAN VÀ MỤC TIÊU CỦA CHUỖI R25 – R31

Chuỗi nhiệm vụ **R25 → R31** là quy trình **Forensic Audit, Targeted Repair và Final Certification** nghiêm ngặt nhất của dự án Aeolus V4. 

Mục tiêu cốt lõi:
1. Giải quyết triệt để các bất cập và blocker còn tồn đọng từ các vòng R13–R24.
2. Xóa bỏ hoàn toàn các tuyên bố phóng đại (overclaims), xác lập ranh giới khoa học trung thực và có bằng chứng định lượng kiểm chứng được.
3. Đảm bảo tính toán công bằng (equal compute budget) giữa các thuật toán tối ưu hóa điều phối cổng.
4. Chuyển đổi toàn bộ test kiểm định thành test bằng chứng byte-level SHA-256 (không dựa vào sidecar hay text-presence).
5. Phân định rõ ràng năng lực xác suất giữa Continuous Density (P4) và Quantile Forecasting (P5).
6. Khóa chặt tính toàn vẹn thời gian: 2024 là tập post-holdout được đánh giá sau khi freeze hệ thống, tuyệt đối không có sự can thiệp/tuning/training nào.
7. Ban hành gói chứng nhận cuối cùng (**Final V4 Certification Package**) với tính minh bạch và độ tin cậy tuyệt đối.

---

## II. CHI TIẾT TỪNG GIAI ĐOẠN: YÊU CẦU, THỰC HIỆN, KẾT QUẢ VÀ FILE CHỨNG MINH

---

### 1. Giai đoạn R25: Point Model Selection Consistency & Claim Reconciliation

#### A. Yêu cầu của người dùng
- Kiểm tra tính nhất quán số học trong việc lựa chọn mô hình điểm (Point Model Champion) giữa hai năm:
  - Năm 2023 (Development / Model Selection): Linear/Ridge và Weighted Ensemble có hòa nhau trong khoảng dung sai định trước ($0.10$ phút) hay không?
  - Năm 2024 (Post-Holdout): Hai mô hình này có hòa nhau không? Hay có sự chênh lệch rõ ràng?
- Chặn hoặc sửa đổi claim "Single Overall Champion" nếu không có bằng chứng khoa học nhất quán giữa các năm.

#### B. Những gì đã thực hiện
- Tiến hành đối chiếu số học độc lập giữa tập dữ liệu 2023 development slice ($N=1500$) và 2024 post-holdout ($N=5000$).
- Kiểm tra quy tắc biên dung sai định trước (`indifference band = 0.10 min`):
  - **Trên tập 2023 Selection**: Ridge MAE = $24.618133$ phút, Weighted Ensemble MAE = $24.617684$ phút. Khoảng cách tuyệt đối $|\Delta| = 0.000449$ phút $\le 0.10$ phút $\to$ **Chính thức hòa nhau (Tied)**. Cả hai mô hình là co-champions trên tập phát triển.
  - **Trên tập 2024 Post-Holdout**: Ridge MAE = $22.9125$ phút, Weighted Ensemble MAE = $23.3175$ phút. Khoảng cách tuyệt đối $|\Delta| = 0.4050$ phút $> 0.10$ phút $\to$ **Không hòa nhau (Not Tied)**. Ridge tốt hơn Ensemble $0.4050$ phút.
- Khóa chặt định nghĩa và câu chữ của `CLAIM_02_POINT_CHAMPION_SELECTION`: Thừa nhận hai mô hình hòa nhau trên 2023 dev theo quy tắc indifference band, nhưng không hòa nhau trên 2024; không được tuyên bố "Single overall point champion" trên toàn bộ các năm.
- Khóa chặn hoàn toàn `CLAIM_05_SINGLE_OVERALL_CHAMPION` (`BLOCKED`).

#### C. Kết quả đạt được
- Loại bỏ mâu thuẫn số học giữa dev và holdout.
- Bộ test R25: **7/7 PASS (100%)**.

#### D. Các file chứng minh
- Báo cáo kiểm định số học: [`artifacts/audit/r25_point_selection_consistency.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r25_point_selection_consistency.json)
- Bảng điều chỉnh claim số học: [`artifacts/audit/r25_claim_numeric_reconciliation.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r25_claim_numeric_reconciliation.json)
- Tài liệu kiểm định chi tiết: [`docs/audit/R25_POINT_SELECTION_CONSISTENCY.md`](file:///D:/Study/Code/Python/Aelous/docs/audit/R25_POINT_SELECTION_CONSISTENCY.md)
- Test suite kiểm định: [`tests/test_r25_point_selection_consistency.py`](file:///D:/Study/Code/Python/Aelous/tests/test_r25_point_selection_consistency.py)

---

### 2. Giai đoạn R26: Solver Equal-Total-Compute Re-Certification

#### A. Yêu cầu của người dùng
- Giải quyết triệt để blocker từ R15 về việc so sánh thuật toán điều phối cổng (Gate Assignment Solver):
  - Nghiêm cấm việc cho CP-SAT chạy 5 giây, SA chạy 500 vòng lặp, rồi Hybrid = CP-SAT 5 giây + SA 300 vòng lặp (vì Hybrid nhận tổng compute lớn hơn các thuật toán đơn lẻ).
- Thiết lập và chứng minh một ngân sách tính toán công bằng tuyệt đối (**Equal Total Compute Budget**) cho: Greedy, CP-SAT, Standalone SA, và CP-SAT + SA Hybrid.
- Chạy benchmark trên 28 kịch bản mô phỏng, ghi nhận thời gian, vi phạm ràng buộc cứng (hard constraint violations) và xung đột cổng (conflicts).

#### B. Những gì đã thực hiện
- Thiết lập hợp đồng tính toán công bằng chính xác: **Tổng thời gian cho phép $T_{\text{total}} = 2.0$ giây** cho mỗi bài toán:
  - **Deterministic Greedy**: Baseline heuristic siêu nhanh ($< 2$ ms).
  - **CP-SAT**: Đúng $2.0$ giây wall-clock time limit.
  - **Standalone SA**: Đúng $2.0$ giây wall-clock time limit.
  - **CP-SAT + SA Hybrid**: Phân bổ chính xác $1.0$ giây CP-SAT $+ 1.0$ giây SA $\to$ Tổng cộng $= 2.0$ giây.
- Thực thi benchmark trên 28 scenarios $\times$ 4 solvers $= 112$ runs với seed cố định $202601$.
- Phân tích kết quả:
  - $100\%$ các lượt chạy ($112/112$) đạt tính khả thi cứng, $0$ vi phạm ràng buộc, $0$ xung đột cổng.
  - Điểm mục tiêu trung bình (mean objective penalty): CP-SAT đạt $7167.17$, Hybrid đạt $7167.17$ (bằng nhau tuyệt đối). Điều này chứng minh rằng khi CP-SAT đã được cấp đủ tài nguyên ban đầu, bước tinh chỉnh SA phía sau mang lại **$0.0$ marginal gain**.
  - Standalone SA đạt $7167.88$ (tiệm cận CP-SAT).
  - Greedy đạt $7653.64$.

#### C. Kết quả đạt được
- Chứng minh tính toán công bằng với dữ liệu thực nghiệm 112 runs.
- Bộ test R26: **12/12 PASS (100%)**.

#### D. Các file chứng minh
- Hợp đồng tính toán công bằng: [`artifacts/audit/r26_solver_compute_contract.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r26_solver_compute_contract.json)
- Bảng kết quả 112 runs chi tiết (Parquet): [`artifacts/audit/r26_solver_equal_compute_results.parquet`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r26_solver_equal_compute_results.parquet)
- Báo cáo đối soát ngân sách: [`artifacts/audit/r26_solver_budget_reconciliation.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r26_solver_budget_reconciliation.json)
- Tài liệu kiểm định solver: [`docs/audit/R26_SOLVER_EQUAL_COMPUTE.md`](file:///D:/Study/Code/Python/Aelous/docs/audit/R26_SOLVER_EQUAL_COMPUTE.md)
- Test suite kiểm định: [`tests/test_r26_solver_equal_compute.py`](file:///D:/Study/Code/Python/Aelous/tests/test_r26_solver_equal_compute.py)

---

### 3. Giai đoạn R27: Certification Test Hardening & Actual Lineage Validation

#### A. Yêu cầu của người dùng
- Nâng cấp toàn bộ các bài kiểm tra chứng nhận từ mức "kiểm tra chuỗi / file tồn tại / đọc sidecar" thành **Evidence Tests** kiểm tra sâu:
  - Băm trực tiếp raw bytes của từng file để đối chiếu SHA-256 (không chỉ đọc sidecar).
  - Bắt buộc kiểm tra chính xác 13 claim IDs (không trùng lặp, không thiếu, không unclassified).
  - Kiểm tra chi tiết R21 execution trace ($124$ runs, $0$ failures, $0$ cache hits), R22 freeze ($79$ files, $24$ categories), R23 post-holdout governance (2024 không tham gia train/tune).
  - Bổ sung validator kiểm tra ranh giới dữ liệu downstream (ngăn chặn triệt để rò rỉ thời tiết METAR/TAF và thông tin khởi hành).

#### B. Những gì đã thực hiện
- Viết test suite `test_r27_certification_hardening.py` gồm 24 bài test độc lập:
  - Tự động băm lại SHA-256 của các manifest chủ chốt (`system_freeze_manifest_v3.json`, `development_evidence_manifest_v3.json`, `academic_model_selection_v3.json`, `post_holdout_evaluation_manifest_v3.json`, v.v.) và so khớp với sidecars.
  - Kiểm tra toàn bộ 79 files trong Freeze Manifest V3 trên ổ đĩa, đảm bảo băm byte khớp 100%.
  - Chuẩn hóa 13 claim IDs vào 5 nhóm trạng thái hợp lệ (`CORRECTED`, `SUPPORTED_WITH_LIMITATION`, `BLOCKED`, `NOT_SUPPORTED`, `HISTORICAL_ONLY`).
  - Tích hợp `validate_downstream_input_boundary` để chặn đứng các cột `WEATHER_*` và `DEP_DELAY*`.

#### C. Kết quả đạt được
- Thiết lập hệ thống chốt chặn cryptographic không thể làm giả.
- Bộ test R27: **24/24 PASS (100%)**.

#### D. Các file chứng minh
- Báo cáo hardening test: [`artifacts/audit/r27_certification_test_hardening.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r27_certification_test_hardening.json)
- Bảng băm thực tế của các artifacts: [`artifacts/audit/r27_lineage_actual_hashes.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r27_lineage_actual_hashes.json)
- Bảng xác nhận 13 claims: [`artifacts/audit/r27_claim_matrix_validation.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r27_claim_matrix_validation.json)
- Báo cáo xác thực provenance: [`artifacts/audit/r27_provenance_validation.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r27_provenance_validation.json)
- Tài liệu hardening: [`docs/audit/R27_CERTIFICATION_TEST_HARDENING.md`](file:///D:/Study/Code/Python/Aelous/docs/audit/R27_CERTIFICATION_TEST_HARDENING.md)
- Test suite kiểm định: [`tests/test_r27_certification_hardening.py`](file:///D:/Study/Code/Python/Aelous/tests/test_r27_certification_hardening.py)

---

### 4. Giai đoạn R28: Probabilistic Metric, Calibration & Dependency Audit

#### A. Yêu cầu của người dùng
- Phân biệt bản chất toán học giữa:
  - **P4**: Parametric continuous density, Exact continuous CRPS, Exact NLL.
  - **P5**: Non-parametric quantile forecasting.
- Tuyệt đối không dùng chung định nghĩa capability cho P4 và P5. Nghiêm cấm tuyên bố P5 cung cấp hàm mật độ liên tục hay continuous NLL/PIT.
- Kiểm tra tuyên bố "P4 calibrated": Chỉ được gọi là calibrated nếu có bằng chứng thực nghiệm trực tiếp.
- Kiểm tra toàn diện closure của các thư viện phụ thuộc (dependencies).

#### B. Những gì đã thực hiện
- Kiểm toán toán học và mã nguồn của mô hình xác suất:
  - **P4 (NGBoost Student-T)**: Cung cấp tham số phân phối liên tục ($\mu, \sigma, \nu \ge 2.1$), CDF, PPF, tích phân CRPS liên tục ($17.6532$ holdout) và NLL liên tục ($4.6307$ holdout).
  - Về calibration của P4: Do chưa có kiểm định empirical calibration riêng biệt $\to$ Phán quyết: `NOT_SEPARATELY_CERTIFIED`. Sửa đổi wording chính thức: *"P4 NGBoost Student-T provides a parametric continuous predictive density; empirical calibration is not separately certified."*
  - **P5 (Quantile Regression)**: Ước lượng 5 phân vị rời rạc ($\tau \in \{0.10, 0.25, 0.50, 0.75, 0.90\}$) với pinball loss ($11.7588$ holdout). Khẳng định hàm mật độ liên tục, continuous NLL và sampling là `NOT_AVAILABLE / NOT_SUPPORTED`.
- Thiết lập taxonomy phân loại CRPS chuẩn xác (`exact_continuous_crps`, `exact_discrete_crps`, `crps_quantile_approximation`, `pinball_loss`).
- Kiểm kê và chứng nhận closure của 10 thư viện phụ thuộc (`scipy 1.17.1`, `ngboost 0.5.11`, `lightgbm 4.7.0`, `xgboost 3.2.0`, `scikit-learn 1.9.0`, v.v.).

#### C. Kết quả đạt được
- Tách bạch vai trò hoạt động giữa Continuous Density và Quantile Forecaster.
- Bộ test R28: **11/11 PASS (100%)**.

#### D. Các file chứng minh
- Ma trận năng lực xác suất: [`artifacts/audit/r28_probabilistic_capability_matrix.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r28_probabilistic_capability_matrix.json)
- Báo cáo nguồn gốc metric: [`artifacts/audit/r28_metric_lineage.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r28_metric_lineage.json)
- Bằng chứng kiểm định calibration: [`artifacts/audit/r28_calibration_evidence.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r28_calibration_evidence.json)
- Đóng gói dependency closure: [`artifacts/audit/r28_dependency_closure.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r28_dependency_closure.json)
- Tài liệu kiểm định xác suất: [`docs/audit/R28_PROBABILISTIC_AUDIT.md`](file:///D:/Study/Code/Python/Aelous/docs/audit/R28_PROBABILISTIC_AUDIT.md)
- Test suite kiểm định: [`tests/test_r28_probabilistic_audit.py`](file:///D:/Study/Code/Python/Aelous/tests/test_r28_probabilistic_audit.py)

---

### 5. Giai đoạn R29: Execution Provenance Reconciliation

#### A. Yêu cầu của người dùng
- Đối soát toàn diện nguồn gốc thực thi (execution provenance) của $124$ runs trong R21:
  - Chứng minh $124$ runs phân rã chính xác vào những họ thí nghiệm (experiment families) nào.
  - Giải trình lý do $4$ họ thí nghiệm còn lại (Point, Probabilistic, Statistics, Stability) được tái sử dụng (`REUSED_VALID_ARTIFACT`) theo đúng tiêu chí tái sử dụng của R21.
- Truy vết toàn vẹn chuỗi: R21 Execution Trace $\to$ R22 Freeze $\to$ R23 Post-Holdout.
- Tạo file Parquet máy đọc được quản lý 224 development runs và bộ 14 test kiểm định theo danh mục bắt buộc.

#### B. Những gì đã thực hiện
- Xây dựng ma trận thực thi toàn diện gồm **224 development runs** (lưu dạng Parquet):
  - **124 Fresh Rebuilt Runs**:
    - Selection Family: **10 runs** (`R21_SEL_01..10`) trên tập 2023 dev slice (5 point baselines + 5 probabilistic candidates).
    - Downstream Simulation Family: **84 runs** (`R21_DOWNSTREAM_01..84`) under `SCALAR_FORECAST_IMPACT` (7 candidates $\times$ 4 scenarios $\times$ 3 solvers).
    - Monte Carlo Family: **30 runs** (`R21_MC_01..30`) under $s/\sqrt{N}$ SE tracking (6 candidates $\times$ 5 sample sizes).
  - **100 Reused Runs (hợp lệ theo tiêu chuẩn R21)**:
    - Point Benchmark Family: **20 runs** (5 models $\times$ 4 rolling folds 2016–2022 từ R13 rebuild).
    - Probabilistic Benchmark Family: **20 runs** (5 candidates $\times$ 4 rolling folds 2016–2022 từ R13 rebuild / R19 decoupling).
    - Statistical Inference Family: **48 families** (Holm-Bonferroni FWER control & cluster bootstrap trên `FL_DATE` từ R18 repair).
    - Stability Family: **12 runs** (3 seeds $\times$ 4 rolling folds từ R13 multi-seed replication).
  - Thống kê: Cache hits = **0**, Failures = **0**, Unclassified runs = **0**.
- Truy vết R22 Freeze: Toàn bộ 79 files thuộc 24 categories đều có nguồn gốc rõ ràng ($0$ orphaned artifacts, $0$ unrecorded executions).
- Truy vết R23 Post-Holdout: Chứng minh tập 2024 chỉ được đánh giá post-freeze trên các mô hình đã đóng băng ($0$ training/tuning trên 2024).

#### C. Kết quả đạt được
- Hoàn thành bảng đối soát 224 runs không còn một điểm mù execution.
- Bộ test R29: **21/21 PASS (100%)** (bao gồm cả 14 mandatory tests).

#### D. Các file chứng minh
- Bảng ma trận 224 runs (Parquet): [`artifacts/audit/r29_execution_matrix.parquet`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r29_execution_matrix.parquet)
- Báo cáo đối soát thực thi: [`artifacts/audit/r29_execution_provenance_reconciliation.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r29_execution_provenance_reconciliation.json)
- Báo cáo đối soát số lượng run: [`artifacts/audit/r29_run_count_reconciliation.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r29_run_count_reconciliation.json)
- Chuỗi nguồn gốc lineage: [`artifacts/audit/r29_lineage_chain.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r29_lineage_chain.json)
- Tài liệu kiểm định provenance: [`docs/audit/R29_EXECUTION_PROVENANCE.md`](file:///D:/Study/Code/Python/Aelous/docs/audit/R29_EXECUTION_PROVENANCE.md)
- Test suite kiểm định: [`tests/test_r29_execution_provenance.py`](file:///D:/Study/Code/Python/Aelous/tests/test_r29_execution_provenance.py)

---

### 6. Giai đoạn R30: Final Evidence Reconciliation

#### A. Yêu cầu của người dùng
- Tổng hợp trạng thái toàn diện trước khi phát hành chứng nhận:
  - Tạo bảng trạng thái chính thức cho **18 research domains** với các trường: `status`, `evidence_path`, `evidence_hash`, `source_run_id`, `limitations`, `allowed_claims`, `forbidden_claims`.
  - Đối soát đầy đủ **13 claims** với lịch sử thay đổi qua các vòng R25–R29, allowed scope, prohibited scope.
  - Khóa chặt các đường biên nhận thức: Point champion co-existence, Probabilistic role separation, Downstream scalar semantics, Oracle non-deployable benchmark, Synthetic airfield simulation, Monte Carlo s/sqrt(N) tracking, Reproducibility under contained specification.
- Final Gate: Chỉ PASS nếu không còn bất kỳ mâu thuẫn P0 nào.

#### B. Những gì đã thực hiện
- Thiết lập bảng trạng thái 18 domains (lưu dạng Parquet và JSON):
  - **15 Domains `PASS`**: Core Arrival point, Core Arrival probabilistic, Flight Chain, Temporal governance, Statistical inference, Point model selection, Probabilistic model selection, Synthetic Turn, Gate Simulation, Greedy, CP-SAT, SA, CP-SAT + SA, Monte Carlo, Certification tests.
  - **3 Domains `LIMITED`**: Auxiliary Departure (benchmark cách ly), Weather (quarantined để chống lookahead bias theo V4 invariant), Reproducibility (`CERTIFIED_WITH_LIMITATIONS` theo spec đóng gói).
  - **0 Domains `BLOCKED`**.
- Hoàn thành ma trận đối soát 13 claims với câu chữ chuẩn xác được cấp phép và các tuyên bố bị cấm.
- Thiết lập bộ 16 bài unit tests kiểm tra toàn diện các quy tắc biên.

#### C. Kết quả đạt được
- Đạt trạng thái nhất quán 100% giữa tất cả các artifacts, không còn bất kỳ mâu thuẫn P0 nào.
- Bộ test R30: **16/16 PASS (100%)**.

#### D. Các file chứng minh
- Báo cáo đối soát bằng chứng cuối cùng: [`artifacts/audit/r30_final_evidence_reconciliation.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r30_final_evidence_reconciliation.json)
- Bảng trạng thái 18 domains (Parquet): [`artifacts/audit/r30_final_status_matrix.parquet`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r30_final_status_matrix.parquet)
- Tài liệu đối soát bằng chứng: [`docs/audit/R30_FINAL_EVIDENCE_RECONCILIATION.md`](file:///D:/Study/Code/Python/Aelous/docs/audit/R30_FINAL_EVIDENCE_RECONCILIATION.md)
- Test suite kiểm định: [`tests/test_r30_final_reconciliation.py`](file:///D:/Study/Code/Python/Aelous/tests/test_r30_final_reconciliation.py)

---

### 7. Giai đoạn R31: Final V4 Forensic Certification

#### A. Yêu cầu của người dùng
- Giai đoạn chốt sổ cuối cùng (Final Certification Gate):
  - Tuyệt đối không thay đổi phương pháp khoa học, không retrain, không tune mô hình.
  - Đóng băng môi trường thực thi (OS, Python, packages, Git commit).
  - Kiểm kê toàn bộ các artifacts cốt lõi và tính lại SHA-256 thực tế từ raw bytes.
  - Chạy toàn bộ các bộ test từ R25 đến R30 cùng với full regression suite.
  - Phán quyết chứng nhận theo quy tắc: Chỉ cấp `CERTIFIED_WITH_LIMITATIONS` khi mọi điều kiện được thỏa mãn. Nếu còn blocker thì bắt buộc phải là `BLOCKED`.
  - Phân tách rõ ràng các mục trong báo cáo cuối: CERTIFIED FACTS, LIMITATIONS, BLOCKED CLAIMS, NON-DEPLOYABLE BENCHMARKS, POST-HOLDOUT RESULTS, SYNTHETIC DOWNSTREAM RESULTS.
  - Xuất bảng tóm tắt Step 16 đúng format quy định.

#### B. Những gì đã thực hiện
- Đóng băng môi trường: Python 3.11.15 trên Windows 10 AMD64, Git commit `c99b3e84b403527bcfb0f9612a1e2737c9f63701`.
- Kiểm kê 31 artifacts cốt lõi trong `final_freeze_manifest_v4.json`: Tất cả 31 files đều tồn tại và khớp SHA-256 byte thực tế với sidecars ($0$ hash mismatches).
- Chạy toàn bộ regression test suite của repository: **194/194 tests PASS** trong 6.98 giây, $0$ failures, $0$ warnings.
- Phát hành gói chứng nhận cuối cùng:
  - `final_evidence_certification_v4.json`
  - `final_claim_boundary_audit_v4.json`
  - `final_reproducibility_audit_v4.json`
  - `final_freeze_manifest_v4.json`
  - `final_execution_summary_v4.json`
  - `FINAL_EVIDENCE_CERTIFICATION_V4.md`
- Viết test suite `test_r31_final_certification.py` gồm 21 bài kiểm định tự động xác nhận toàn bộ quy trình.

#### C. Kết quả đạt được
- Ban hành chính thức phán quyết: **`CERTIFIED_WITH_LIMITATIONS`**.
- Bộ test R31: **21/21 PASS (100%)**.
- Toàn bộ test suite repository: **194/194 PASS (100%)**.

#### D. Các file chứng minh
- Chứng nhận bằng chứng cuối cùng: [`artifacts/audit/final_evidence_certification_v4.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/final_evidence_certification_v4.json)
- Báo cáo ranh giới 13 claims: [`artifacts/audit/final_claim_boundary_audit_v4.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/final_claim_boundary_audit_v4.json)
- Báo cáo chứng nhận tái lập: [`artifacts/audit/final_reproducibility_audit_v4.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/final_reproducibility_audit_v4.json)
- Manifest đóng băng V4 (31 artifacts): [`artifacts/audit/final_freeze_manifest_v4.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/final_freeze_manifest_v4.json)
- Báo cáo tổng hợp thực thi: [`artifacts/audit/final_execution_summary_v4.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/final_execution_summary_v4.json)
- Báo cáo chứng nhận người đọc được: [`docs/audit/FINAL_EVIDENCE_CERTIFICATION_V4.md`](file:///D:/Study/Code/Python/Aelous/docs/audit/FINAL_EVIDENCE_CERTIFICATION_V4.md)
- Test suite kiểm định cuối cùng: [`tests/test_r31_final_certification.py`](file:///D:/Study/Code/Python/Aelous/tests/test_r31_final_certification.py)

---

## III. BẢNG TỔNG HỢP TRẠNG THÁI CUỐI CÙNG (STEP 16 METRICS)

```text
CERTIFICATION_STATUS:
CERTIFIED_WITH_LIMITATIONS

R25:
PASS

R26:
PASS

R27:
PASS

R28:
PASS

R29:
PASS

R30:
PASS

R31:
PASS

P0_BLOCKERS:
0

P1_LIMITATIONS:
12

UNSUPPORTED_CLAIMS_REMAINING:
0

HASH_MISMATCHES:
0

UNCLASSIFIED_CLAIMS:
0

UNVERIFIED_EXECUTIONS:
0

2024_ADAPTATION_DETECTED:
NO

FINAL_ACTION:
CERTIFIED_WITH_LIMITATIONS
```

---

## IV. BẢNG TỔNG HỢP TOÀN BỘ CÁC BỘ TEST ĐÃ CHẠY

| Test Suite File | Phạm vi kiểm tra | Số lượng test | Trạng thái |
| :--- | :--- | :---: | :---: |
| [`test_r17_downstream_semantics.py`](file:///D:/Study/Code/Python/Aelous/tests/test_r17_downstream_semantics.py) | Ranh giới ngữ nghĩa downstream & gate tracking | 7 | **PASS** |
| [`test_r18_statistical_inference.py`](file:///D:/Study/Code/Python/Aelous/tests/test_r18_statistical_inference.py) | Suy luận thống kê FWER Holm-Bonferroni | 7 | **PASS** |
| [`test_r19_ensemble_lineage.py`](file:///D:/Study/Code/Python/Aelous/tests/test_r19_ensemble_lineage.py) | Nguồn gốc trọng số ensemble | 5 | **PASS** |
| [`test_r19_probabilistic_comparability.py`](file:///D:/Study/Code/Python/Aelous/tests/test_r19_probabilistic_comparability.py) | Khả năng so sánh metric xác suất | 7 | **PASS** |
| [`test_r20_artifact_freshness.py`](file:///D:/Study/Code/Python/Aelous/tests/test_r20_artifact_freshness.py) | Độ tươi của artifacts & bảo vệ 2024 | 6 | **PASS** |
| [`test_r20_freeze_gate.py`](file:///D:/Study/Code/Python/Aelous/tests/test_r20_freeze_gate.py) | Cổng đóng băng hệ thống trước rebuild | 5 | **PASS** |
| [`test_r21_targeted_rebuild.py`](file:///D:/Study/Code/Python/Aelous/tests/test_r21_targeted_rebuild.py) | Tái xây dựng có mục tiêu 124 runs | 5 | **PASS** |
| [`test_r22_system_freeze_v3.py`](file:///D:/Study/Code/Python/Aelous/tests/test_r22_system_freeze_v3.py) | Đóng băng 79 files across 24 categories | 14 | **PASS** |
| [`test_r23_post_holdout_evaluation.py`](file:///D:/Study/Code/Python/Aelous/tests/test_r23_post_holdout_evaluation.py) | Đánh giá 2024 post-holdout | 6 | **PASS** |
| [`test_r24_final_certification.py`](file:///D:/Study/Code/Python/Aelous/tests/test_r24_final_certification.py) | Kiểm định chứng nhận gốc | 7 | **PASS** |
| [`test_r25_point_selection_consistency.py`](file:///D:/Study/Code/Python/Aelous/tests/test_r25_point_selection_consistency.py) | Tính nhất quán chọn mô hình điểm (2023 vs 2024) | 7 | **PASS** |
| [`test_r26_solver_equal_compute.py`](file:///D:/Study/Code/Python/Aelous/tests/test_r26_solver_equal_compute.py) | Hợp đồng ngân sách tính toán công bằng (T=2.0s) | 12 | **PASS** |
| [`test_r27_certification_hardening.py`](file:///D:/Study/Code/Python/Aelous/tests/test_r27_certification_hardening.py) | Băm byte SHA256 & xác thực 13 claims | 24 | **PASS** |
| [`test_r28_probabilistic_audit.py`](file:///D:/Study/Code/Python/Aelous/tests/test_r28_probabilistic_audit.py) | Phân định P4 continuous vs P5 quantile & closure | 11 | **PASS** |
| [`test_r29_execution_provenance.py`](file:///D:/Study/Code/Python/Aelous/tests/test_r29_execution_provenance.py) | Đối soát nguồn gốc thực thi 224 development runs | 21 | **PASS** |
| [`test_r30_final_reconciliation.py`](file:///D:/Study/Code/Python/Aelous/tests/test_r30_final_reconciliation.py) | Ma trận 18 domains & đối soát 13 claims | 16 | **PASS** |
| [`test_r31_final_certification.py`](file:///D:/Study/Code/Python/Aelous/tests/test_r31_final_certification.py) | Chứng nhận pháp y V4 cuối cùng | 21 | **PASS** |
| **Các test pipeline phụ trợ khác** | Unit tests cho mô hình RF, pipeline refactor, v.v. | 13 | **PASS** |
| **TỔNG CỘNG TEST SUITE** | **Toàn bộ repository** | **194** | **194/194 PASS (100%)** |
