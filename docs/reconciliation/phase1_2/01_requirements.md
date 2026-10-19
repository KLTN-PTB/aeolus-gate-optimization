# Ma trận đối chiếu yêu cầu đề cương

Nguồn là đề CNTT-KLCN168. Mỗi dòng có trích đoạn nguyên văn và vị trí trong bản trích xuất.
35 hạng mục bao gồm kỹ thuật, sản phẩm, quy trình và khuyến khích tùy chọn. Không cộng điểm tổng và điểm con để chấm điểm.

| Mã | Yêu cầu | CLO hoặc rubric | Hiện trạng | Bằng chứng | GVHD |
|---|---|---|---|---|---|
| [R01](#r01) | Dữ liệu Aeolus và tiền xử lý | CLO2.2; CLO3 | PARTIAL | TRACEABLE_ARTIFACTS | NONE |
| [R02](#r02) | Đặc trưng biết trước thời điểm dự báo | CLO3 | PARTIAL | TRACEABLE_ARTIFACTS | NONE |
| [R03](#r03) | Logistic Regression và Random Forest làm baseline | CLO3 | PARTIAL | STORED_PREDICTIONS | NONE |
| [R04](#r04) | XGBoost Classifier và Regressor | CLO3 | PARTIAL | STORED_PREDICTIONS | PENDING |
| [R05](#r05) | Stacking Ensemble làm mô hình so sánh | Mục 6 giới thiệu thuật toán | NOT_EVIDENCED | NOT_REPRODUCIBLE | PENDING |
| [R06](#r06) | Bayesian Optimization bằng Optuna | CLO3 | PARTIAL | SQLITE_AND_MANIFEST | NONE |
| [R07](#r07) | Chia dữ liệu theo thời gian | CLO3 | PARTIAL | TRACEABLE_ARTIFACTS | NONE |
| [R08](#r08) | Đánh giá ROC-AUC Precision Recall F1 | CLO3 | PARTIAL | STORED_PREDICTIONS | NONE |
| [R09](#r09) | Đánh giá MAE RMSE | CLO3 | PARTIAL | STORED_PREDICTIONS | NONE |
| [R10](#r10) | So sánh Tabular với Tabular và Flight Chain | CLO3 | NOT_EVIDENCED | HARDCODED_SUMMARY | PENDING |
| [R11](#r11) | Đặc trưng thời tiết | Mục 5 và kế hoạch tuần | NOT_EVIDENCED | AVAILABILITY_AUDIT_ONLY | PENDING |
| [R12](#r12) | Feature Importance và SHAP | CLO3; tuần 6 | PARTIAL | STORED_ATTRIBUTIONS | NONE |
| [R13](#r13) | CP-SAT và ràng buộc cứng | CLO3 | PARTIAL | STORED_SOLVER_RUNS | NONE |
| [R14](#r14) | SA và Hybrid cải thiện tiêu chí mềm | CLO3 | PARTIAL | STORED_SOLVER_RUNS | PENDING |
| [R15](#r15) | So sánh Greedy CP-SAT Hybrid | CLO3 | PARTIAL | STORED_SOLVER_RUNS | NONE |
| [R16](#r16) | Chi phí trễ tái phân bổ xung đột thời gian | CLO3 | PARTIAL | STORED_SOLVER_RUNS | PENDING |
| [R17](#r17) | Monte Carlo 500 kịch bản | CLO3 | PARTIAL | STORED_LEDGER | NONE |
| [R18](#r18) | Quy mô 20–50 cổng 100–300 chuyến | CLO3; CLO4 | PARTIAL | STORED_SOLVER_RUNS | NONE |
| [R19](#r19) | Pipeline trên tập con Aeolus thực tế | CLO4; 0.75 điểm theo T1R8 | PARTIAL | NATIVE_RUN_MANIFEST | PENDING |
| [R20](#r20) | Dashboard Streamlit hoặc Plotly Dash | CLO3 | PARTIAL | APPLICATION_TESTS | PENDING |
| [R21](#r21) | Gantt và cảnh báo rủi ro trễ | CLO3 | PARTIAL | APPLICATION_TESTS | NONE |
| [R22](#r22) | Mô-đun so sánh và phân phối Monte Carlo | CLO3 | PARTIAL | APPLICATION_TESTS | NONE |
| [R23](#r23) | Lưu model lịch log Optuna và từng kịch bản | CLO3 | PARTIAL | CHECKPOINTS_AND_LEDGER | NONE |
| [R24](#r24) | Mã nguồn tái lập và môi trường | CLO3; tuần cuối | PARTIAL | CLEAN_CHECKOUT_ACCEPTANCE | NONE |
| [R25](#r25) | Nội dung báo cáo tổng quan và phương pháp | CLO1.1; CLO1.2; CLO2.1; CLO5.1 | PARTIAL | DRAFT_ONLY | NONE |
| [R26](#r26) | Hình thức báo cáo | CLO5.1; 0.5 điểm T1R10 | NOT_EVIDENCED | MARKDOWN_ONLY | NONE |
| [R27](#r27) | Slide và phong cách báo cáo | CLO5.2; 0.5 điểm T1R12 | PARTIAL | MARKDOWN_ONLY | NONE |
| [R28](#r28) | Phân công nhóm và tác phong làm việc | CLO6; T1R3; T1R11 | NOT_EVIDENCED | NO_SIGNED_RECORD | PENDING |
| [R29](#r29) | Gặp GVHD hằng tuần và tích hợp nội dung | Mục 12; CLO6 | NOT_EVIDENCED | NO_ADVISOR_RECORD | PENDING |
| [R30](#r30) | Lịch 12 tuần và hạn nộp | Mục 8; mục 10 | PARTIAL | PROPOSAL_SCHEDULE_ONLY | PENDING |
| [R31](#r31) | Khảo sát công trình và tài liệu tham khảo | CLO1.1; T1R2 | PARTIAL | DRAFT_ONLY | NONE |
| [R32](#r32) | Ví dụ trễ dẫn tới xung đột và xử lý | CLO1.2; T1R4 | PARTIAL | DEMO_SCRIPT | NONE |
| [R33](#r33) | Cấu hình hệ thống và xử lý theo tập con | CLO3; mục 7 | PARTIAL | REQUIREMENTS_AND_ACCEPTANCE | NONE |
| [R34](#r34) | Mục tiêu hỗ trợ quyết định trên sân bay mô phỏng | Mục 5; CLO1.1 | PARTIAL | SIMULATION_EVIDENCE | NONE |
| [R35](#r35) | Khuyến khích NCKH và công bố | CLO3; T1R13; tùy chọn | NOT_EVIDENCED | NO_AWARD_OR_PUBLICATION_RECORD | NONE |

PARTIAL: có triển khai/bằng chứng và còn giới hạn. NOT_EVIDENCED: chưa đủ căn cứ cho hạng mục đó.
PENDING: chưa có xác nhận GVHD. NONE: chưa đề nghị điều chỉnh riêng, không có nghĩa đã duyệt.
Nguồn hiện hữu chưa đủ xác minh số học: đọc 05_results.md và validation.json.

## R01

**Dữ liệu Aeolus và tiền xử lý** — PARTIAL; GVHD: NONE.

Mã cũ: REQ-01. Nguồn: P017.

> P017: Thu thập và thực hiện tiền xử lý với bộ dữ liệu Aeolus: A Multi-structural Flight Delay Dataset.

Triển khai: src/data/canonicalize.py.
Bằng chứng: artifacts/remediation/ml_validation/leakage_audit.json.
Kiểm thử: tests/test_temporal_split.py.
Hành động: Chốt phạm vi Aeolus ATL; tách BTS 2026 dùng demo khỏi dữ liệu nghiên cứu.

## R02

**Đặc trưng biết trước thời điểm dự báo** — PARTIAL; GVHD: NONE.

Mã cũ: REQ-01. Nguồn: P018.

> P018: Xây dựng mô hình Machine Learning (Random Forest, Logistic Regression, XGBoost) dự đoán xác suất chuyến bay bị trễ và mức độ trễ ước tính từ các đặc trưng có thể biết trước thời điểm khai thác, bao gồm lịch bay, thông tin chuyến bay, thời tiết và đặc trưng ngữ cảnh khác.

Triển khai: src/features/tabular_features.py.
Bằng chứng: configs/base.yaml.
Kiểm thử: tests/test_g3_ml_validation.py.
Hành động: Mô tả cutoff CRS_DEP_TIME - 2h theo từng task; không khẳng định dữ liệu chưa chứng minh khả dụng.

## R03

**Logistic Regression và Random Forest làm baseline** — PARTIAL; GVHD: NONE.

Mã cũ: REQ-02. Nguồn: P143.

> P143: Đánh giá Logistic Regression và Random Forest làm các mô hình baseline và thiết lập mốc so sánh.

Triển khai: src/models/linear_models.py; src/models/random_forest_models.py.
Bằng chứng: artifacts/remediation/ml_validation/classification_metrics.csv.
Kiểm thử: tests/test_g3_ml_validation.py.
Hành động: Tách baseline arrival/departure; không yêu cầu có checkpoint cho mọi mô hình chỉ dùng nghiên cứu.

## R04

**XGBoost Classifier và Regressor** — PARTIAL; GVHD: PENDING.

Mã cũ: REQ-02. Nguồn: P086.

> P086: + Cài đặt mô hình XGBoost Classifier/Regressor dự báo P(delay ≥ 15 phút) và ΔT trễ; cài đặt bộ giải CP-SAT (Google OR-Tools) cho bài toán Gate Assignment với các ràng buộc cứng

Triển khai: src/models/week5_xgboost.py.
Bằng chứng: artifacts/remediation/outbound_classification/metrics/outbound_classification_metrics_2023.csv.
Kiểm thử: tests/test_g3_ml_validation.py.
Hành động: Giải trình phạm vi XGBoost hiện có và NGBoost arrival mở rộng; không gộp classifier với sigmoid từ hồi quy.

## R05

**Stacking Ensemble làm mô hình so sánh** — NOT_EVIDENCED; GVHD: PENDING.

Mã cũ: NEW. Nguồn: P029.

> P029: Giới thiệu thuật toán: XGBoost: mô hình gradient boosting dùng để dự báo phân loại/hồi quy độ trễ. Logistic Regression, Random Forest và Stacking Ensemble dùng để so sánh hiệu quả dự báo. CP-SAT (Google OR-Tools): bộ giải Constraint Programming cho bài toán GAP với các ràng buộc cứng. Simulated Annealing: metaheuristic cải thiện lời giải khả thi của CP-SAT theo các tiêu chí mềm. Optuna: framework tối ưu hyperparameter bằng Bayesian Optimization.

Triển khai: src/models/registry.py.
Bằng chứng: configs/academic_model_selection.yaml.
Kiểm thử: Chưa có kiểm thử hoặc biên bản riêng.
Hành động: Xin GVHD xác nhận Weighted Ensemble có được chấp nhận thay Stacking; nếu không, lập việc bổ sung riêng.

## R06

**Bayesian Optimization bằng Optuna** — PARTIAL; GVHD: NONE.

Mã cũ: REQ-03. Nguồn: P145.

> P145: Điều chỉnh siêu tham số bằng Optuna.

Triển khai: src/models/week5_xgboost_hpo.py.
Bằng chứng: artifacts/manifests/week5_hpo_protocol_v1_1__xgboost_classification_result_v1.json; artifacts/manifests/week5_hpo_protocol_v1_1__xgboost_regression_result_v1.json.
Kiểm thử: tests/test_week5_hpo_execution.py.
Hành động: Xác minh best trial/params trực tiếp SQLite; không suy ra departure checkpoint đã HPO từ study arrival.

## R07

**Chia dữ liệu theo thời gian** — PARTIAL; GVHD: NONE.

Mã cũ: REQ-03. Nguồn: P019.

> P019: Tối ưu hyperparameter của mô hình ML bằng Bayesian Optimization (Optuna) và đánh giá theo quy trình chia dữ liệu theo thời gian nhằm hạn chế temporal leakage.

Triển khai: src/data/temporal_protocol.py.
Bằng chứng: configs/current_state.yaml.
Kiểm thử: tests/test_temporal_split.py.
Hành động: Tách rolling 2019–2022, selection 2023 và các thế hệ hậu kiểm 2024; không gọi 2023 là untouched test.

## R08

**Đánh giá ROC-AUC Precision Recall F1** — PARTIAL; GVHD: NONE.

Mã cũ: REQ-02. Nguồn: P033.

> P033: Đánh giá mô hình dự báo bằng ROC-AUC, MAE, RMSE, Precision, Recall, F1 trên tập kiểm thử chia theo thời gian (temporal split). So sánh mô hình chỉ sử dụng Tabular với mô hình kết hợp Tabular + Flight Chain Features. Đánh giá bài toán tối ưu bằng cách so sánh Greedy, CP-SAT và CP-SAT kết hợp Simulated Annealing theo tổng chi phí do trễ, số lần tái phân bổ, xung đột cổng và thời gian giải; kiểm tra độ bền của phương án phân cổng bằng Monte Carlo Simulation (500 kịch bản).

Triển khai: src/models/metrics.py.
Bằng chứng: artifacts/remediation/outbound_classification/predictions/outbound_classification_selection_2023.parquet.
Kiểm thử: tests/test_g3_ml_validation.py.
Hành động: Tính lại có threshold, số mẫu, confusion matrix và kiểu tổng hợp; không dùng số AUC bản nháp.

## R09

**Đánh giá MAE RMSE** — PARTIAL; GVHD: NONE.

Mã cũ: REQ-02. Nguồn: P033.

> P033: Đánh giá mô hình dự báo bằng ROC-AUC, MAE, RMSE, Precision, Recall, F1 trên tập kiểm thử chia theo thời gian (temporal split). So sánh mô hình chỉ sử dụng Tabular với mô hình kết hợp Tabular + Flight Chain Features. Đánh giá bài toán tối ưu bằng cách so sánh Greedy, CP-SAT và CP-SAT kết hợp Simulated Annealing theo tổng chi phí do trễ, số lần tái phân bổ, xung đột cổng và thời gian giải; kiểm tra độ bền của phương án phân cổng bằng Monte Carlo Simulation (500 kịch bản).

Triển khai: src/models/metrics.py.
Bằng chứng: artifacts/dual_core/predictions/departure_point_selection_2023_v1.parquet.
Kiểm thử: tests/test_g3_ml_validation.py.
Hành động: Dùng phút có dấu và đúng population; không chứng minh lợi thế ML bằng median fit trên nhãn đánh giá.

## R10

**So sánh Tabular với Tabular và Flight Chain** — NOT_EVIDENCED; GVHD: PENDING.

Mã cũ: REQ-04. Nguồn: P033.

> P033: Đánh giá mô hình dự báo bằng ROC-AUC, MAE, RMSE, Precision, Recall, F1 trên tập kiểm thử chia theo thời gian (temporal split). So sánh mô hình chỉ sử dụng Tabular với mô hình kết hợp Tabular + Flight Chain Features. Đánh giá bài toán tối ưu bằng cách so sánh Greedy, CP-SAT và CP-SAT kết hợp Simulated Annealing theo tổng chi phí do trễ, số lần tái phân bổ, xung đột cổng và thời gian giải; kiểm tra độ bền của phương án phân cổng bằng Monte Carlo Simulation (500 kịch bản).

Triển khai: src/features/chain_feature_policy.py.
Bằng chứng: artifacts/remediation/ml_validation/feature_ablation.csv; remediation_evidence/G3_ml_validation/11_FEATURE_ABLATION_STATUS.md.
Kiểm thử: tests/test_g3_ml_validation.py.
Hành động: Đề nghị chấp nhận kiểm toán tính khả dụng thay thực nghiệm Chain; không công bố độ cải thiện từ hằng số.

## R11

**Đặc trưng thời tiết** — NOT_EVIDENCED; GVHD: PENDING.

Mã cũ: REQ-01. Nguồn: P140.

> P140: Feature Engineering từ lịch bay, thời tiết và Flight Chain.

Triển khai: src/data/weather_contract.py.
Bằng chứng: docs/dataset_audit/weather_point_in_time_contract_v1.md.
Kiểm thử: tests/test_weather_contract.py.
Hành động: Đề nghị loại weather khỏi predictors khi chưa có provenance tại cutoff; không suy diễn toàn bộ nguồn Meteostat là METAR.

## R12

**Feature Importance và SHAP** — PARTIAL; GVHD: NONE.

Mã cũ: NEW. Nguồn: P147.

> P147: Phân tích Feature Importance và SHAP.

Triển khai: dashboard/visualizers/shap_charts.py.
Bằng chứng: artifacts/remediation/ml_validation/shap_outputs/summary_statistics.json.
Kiểm thử: tests/test_g3_ml_validation.py.
Hành động: Tính lại TreeSHAP trên đúng 1.000 dòng, checkpoint/preprocessor; giới hạn explanation ở departure regression.

## R13

**CP-SAT và ràng buộc cứng** — PARTIAL; GVHD: NONE.

Mã cũ: REQ-05. Nguồn: P020.

> P020: Xây dựng bộ giải Constraint Programming (CP-SAT, Google OR-Tools) cho bài toán phân cổng trên môi trường sân bay mô phỏng, bảo đảm các ràng buộc vận hành cứng.

Triển khai: src/optimization/solvers/cp_sat_solver.py; src/optimization/domain.py.
Bằng chứng: artifacts/remediation/cp_sat/parity_results.json.
Kiểm thử: tests/test_g5_solver_correctness.py.
Hành động: Đối chiếu formulation, checker độc lập và parity; không tuyên bố đã kiểm tra ràng buộc vận hành không được mô phỏng.

## R14

**SA và Hybrid cải thiện tiêu chí mềm** — PARTIAL; GVHD: PENDING.

Mã cũ: REQ-06. Nguồn: P021.

> P021: Áp dụng Simulated Annealing để cải thiện lời giải khả thi của CP-SAT theo các tiêu chí mềm và giảm chi phí phát sinh do tái phân bổ cổng.

Triển khai: src/optimization/solvers/hybrid_solver.py; src/optimization/sa/annealer.py.
Bằng chứng: artifacts/remediation/benchmarks/g5_fair_benchmark/g5_fair_benchmark_results.csv.
Kiểm thử: tests/test_g5_solver_correctness.py.
Hành động: Trình bày gain đo được; đề không được diễn giải thành buộc SA luôn thắng CP-SAT hay cho phép so sánh khác mục tiêu.

## R15

**So sánh Greedy CP-SAT Hybrid** — PARTIAL; GVHD: NONE.

Mã cũ: REQ-07. Nguồn: P022, P033, P088.

> P022: Đánh giá hệ thống bằng cách so sánh Greedy, CP-SAT và CP-SAT kết hợp Simulated Annealing; đồng thời kiểm tra độ bền của phương án phân cổng bằng Monte Carlo Simulation.
> P033: Đánh giá mô hình dự báo bằng ROC-AUC, MAE, RMSE, Precision, Recall, F1 trên tập kiểm thử chia theo thời gian (temporal split). So sánh mô hình chỉ sử dụng Tabular với mô hình kết hợp Tabular + Flight Chain Features. Đánh giá bài toán tối ưu bằng cách so sánh Greedy, CP-SAT và CP-SAT kết hợp Simulated Annealing theo tổng chi phí do trễ, số lần tái phân bổ, xung đột cổng và thời gian giải; kiểm tra độ bền của phương án phân cổng bằng Monte Carlo Simulation (500 kịch bản).
> P088: + Đánh giá thực nghiệm bằng ROC-AUC, MAE, RMSE, Precision, Recall, F1 (temporal split); so sánh Greedy, CP-SAT và CP-SAT kết hợp Simulated Annealing; kiểm tra độ bền bằng Monte Carlo Simulation (500 kịch bản)

Triển khai: src/optimization/benchmark_harness.py.
Bằng chứng: artifacts/remediation/benchmarks/g5_fair_benchmark/g5_fair_benchmark_manifest.json.
Kiểm thử: tests/test_g5_solver_correctness.py.
Hành động: Ghi ngân sách, seed, hash và công thức chi phí; không suy ra fairness mới từ tên manifest.

## R16

**Chi phí trễ tái phân bổ xung đột thời gian** — PARTIAL; GVHD: PENDING.

Mã cũ: REQ-07. Nguồn: P033.

> P033: Đánh giá mô hình dự báo bằng ROC-AUC, MAE, RMSE, Precision, Recall, F1 trên tập kiểm thử chia theo thời gian (temporal split). So sánh mô hình chỉ sử dụng Tabular với mô hình kết hợp Tabular + Flight Chain Features. Đánh giá bài toán tối ưu bằng cách so sánh Greedy, CP-SAT và CP-SAT kết hợp Simulated Annealing theo tổng chi phí do trễ, số lần tái phân bổ, xung đột cổng và thời gian giải; kiểm tra độ bền của phương án phân cổng bằng Monte Carlo Simulation (500 kịch bản).

Triển khai: src/optimization/evaluation.py.
Bằng chứng: artifacts/remediation/benchmarks/g5_fair_benchmark/g5_fair_benchmark_results.csv.
Kiểm thử: tests/test_g5_solver_correctness.py.
Hành động: Đối chiếu trọng số thực tế; delay cost có thể bằng 0, không quy đổi điểm thành tiền hoặc tuyên bố optimizer giảm ML delay.

## R17

**Monte Carlo 500 kịch bản** — PARTIAL; GVHD: NONE.

Mã cũ: REQ-08. Nguồn: P033, P088.

> P033: Đánh giá mô hình dự báo bằng ROC-AUC, MAE, RMSE, Precision, Recall, F1 trên tập kiểm thử chia theo thời gian (temporal split). So sánh mô hình chỉ sử dụng Tabular với mô hình kết hợp Tabular + Flight Chain Features. Đánh giá bài toán tối ưu bằng cách so sánh Greedy, CP-SAT và CP-SAT kết hợp Simulated Annealing theo tổng chi phí do trễ, số lần tái phân bổ, xung đột cổng và thời gian giải; kiểm tra độ bền của phương án phân cổng bằng Monte Carlo Simulation (500 kịch bản).
> P088: + Đánh giá thực nghiệm bằng ROC-AUC, MAE, RMSE, Precision, Recall, F1 (temporal split); so sánh Greedy, CP-SAT và CP-SAT kết hợp Simulated Annealing; kiểm tra độ bền bằng Monte Carlo Simulation (500 kịch bản)

Triển khai: src/simulation/monte_carlo_engine_v2.py.
Bằng chứng: artifacts/remediation/monte_carlo_mc500/mc500_20261012_173538_afa5db/simulation_manifest.json.
Kiểm thử: tests/test_g7_scientific_invariants.py.
Hành động: Tính lại ledger 500 realizations/5.500 slots; tách A B1 B2 C1 C2 và trạng thái OPTIMAL/FEASIBLE.

## R18

**Quy mô 20–50 cổng 100–300 chuyến** — PARTIAL; GVHD: NONE.

Mã cũ: REQ-10. Nguồn: P028.

> P028: Mô tả bài toán: Dự báo độ trễ chuyến bay: dự đoán P(delay ≥ 15 phút) và mức độ trễ ước tính ΔT từ các đặc trưng biết trước thời điểm khai thác trên bộ dữ liệu Aeolus: A Multi-structural Flight Delay Dataset. Gate Assignment Problem (GAP): phân/tái phân bổ cổng cho các chuyến bay trên môi trường sân bay mô phỏng (20–50 cổng, 100–300 chuyến bay/ngày), bảo đảm các ràng buộc vận hành cứng.

Triển khai: src/simulation/scalability_scenario.py.
Bằng chứng: artifacts/remediation/cp_sat/scalability_results.csv.
Kiểm thử: tests/test_g5_solver_correctness.py.
Hành động: Đếm contact và remote riêng; tách chuyến, movements, turns; kịch bản 150 cổng là mở rộng.

## R19

**Pipeline trên tập con Aeolus thực tế** — PARTIAL; GVHD: PENDING.

Mã cũ: REQ-10. Nguồn: P106.

> P106: Triển khai trên dữ liệu thực tế: chạy toàn bộ pipeline (tiền xử lý, dự báo XGBoost, tối ưu CP-SAT/SA) trên tập con dữ liệu Aeolus theo sân bay/thời gian đã lựa chọn

Triển khai: src/simulation/native_dual_core_pipeline.py.
Bằng chứng: artifacts/remediation/native_dual_core_g4_pilot/run_manifest.json.
Kiểm thử: tests/test_native_dual_core_pipeline_p07.py.
Hành động: Trình GVHD khác biệt arrival NGBoost; xác nhận đủ luồng dự báo-tối ưu không dùng replay hậu nghiệm thay bằng chứng ML.

## R20

**Dashboard Streamlit hoặc Plotly Dash** — PARTIAL; GVHD: PENDING.

Mã cũ: REQ-09. Nguồn: P034.

> P034: Xây dựng dashboard (Streamlit/Plotly Dash) minh họa tính ứng dụng của hệ thống, gồm: Các biểu đồ hiển thị lịch phân cổng và cảnh báo rủi ro trễ theo từng chuyến bay; mô-đun so sánh Greedy/CP-SAT/CP-SAT kết hợp Simulated Annealing và biểu đồ phân phối kết quả Monte Carlo Simulation.

Triển khai: dashboard/app.py; web_dashboard/app.py.
Bằng chứng: docs/dashboard/EXPERIMENT_ACCEPTANCE.md.
Kiểm thử: tests/dashboard/test_services.py.
Hành động: Giữ Streamlit theo đề; React/FastAPI mở rộng; visual QA còn chưa nghiệm thu trực tiếp.

## R21

**Gantt và cảnh báo rủi ro trễ** — PARTIAL; GVHD: NONE.

Mã cũ: REQ-09. Nguồn: P092.

> P092: + Cài đặt chức năng 1: Gantt chart hiển thị lịch phân cổng và cảnh báo rủi ro trễ theo từng chuyến bay

Triển khai: dashboard/visualizers/gantt_chart.py; web_dashboard/frontend/src/GatePage.tsx.
Bằng chứng: docs/dashboard/WEB_END_TO_END.md.
Kiểm thử: tests/web_dashboard/test_pipeline.py.
Hành động: Đối chiếu timeline, đơn vị, filter và nhãn xác suất đúng model.

## R22

**Mô-đun so sánh và phân phối Monte Carlo** — PARTIAL; GVHD: NONE.

Mã cũ: REQ-09. Nguồn: P093.

> P093: + Cài đặt chức năng 2: mô-đun so sánh Greedy/CP-SAT/CP-SAT+SA và biểu đồ phân phối kết quả Monte Carlo Simulation

Triển khai: web_dashboard/experiments.py; dashboard/pages/page_05_robustness_lab.py.
Bằng chứng: docs/dashboard/EXPERIMENT_ACCEPTANCE.md.
Kiểm thử: tests/web_dashboard/test_experiments.py.
Hành động: Không gán kết quả official MC500 cho upload khác; web recourse là hồi cứu.

## R23

**Lưu model lịch log Optuna và từng kịch bản** — PARTIAL; GVHD: NONE.

Mã cũ: NEW. Nguồn: P091.

> P091: + Tổ chức cấu trúc lưu trữ kết quả: mô hình XGBoost đã huấn luyện, lịch phân cổng CP-SAT/CP-SAT+SA, log Optuna và kết quả Monte Carlo theo từng kịch bản

Triển khai: web_dashboard/storage.py.
Bằng chứng: artifacts/remediation/monte_carlo_mc500/mc500_20261012_173538_afa5db/execution_ledger_summary.json.
Kiểm thử: tests/web_dashboard/test_api.py.
Hành động: Kiểm tra đường dẫn và export; lưu bằng chứng model nào có checkpoint, model nào chỉ có dự báo.

## R24

**Mã nguồn tái lập và môi trường** — PARTIAL; GVHD: NONE.

Mã cũ: NEW. Nguồn: P163.

> P163: Hoàn thiện slide, kịch bản demo và mã nguồn tái lập.

Triển khai: scripts/start_web_dashboard.ps1; scripts/start_web_dashboard.cmd; web_dashboard/solver_execution.py; src/optimization/execution.py; src/optimization/solvers/budgeted_hybrid.py; scripts/validate_dashboard_solver_protocol.py.
Bằng chứng: requirements-app.txt; docs/dashboard/EXPERIMENT_ACCEPTANCE.md; docs/dashboard/SOLVER_PROTOCOL_V2_IMPLEMENTATION.md; docs/dashboard/solver_protocol_v2_measurements.json.
Kiểm thử: tests/web_dashboard/test_api.py; tests/web_dashboard/test_solver_execution.py.
Hành động: Phân biệt chạy demo với tái huấn luyện, bitwise với numerical, dependency app với dependency toàn nghiên cứu.

## R25

**Nội dung báo cáo tổng quan và phương pháp** — PARTIAL; GVHD: NONE.

Mã cũ: NEW. Nguồn: P109.

> P109: Nội dung kiến thức trình bày trong quyển báo cáo

Triển khai: Chưa xác định artifact triển khai riêng.
Bằng chứng: remediation_evidence/G9_thesis/03_THESIS_DRAFT.md.
Kiểm thử: Chưa có kiểm thử hoặc biên bản riêng.
Hành động: Viết lại bản đang dùng theo kết quả đối soát; bản G9 giữ nguyên lịch sử; chưa xác nhận bibliographic sources bên ngoài.

## R26

**Hình thức báo cáo** — NOT_EVIDENCED; GVHD: NONE.

Mã cũ: NEW. Nguồn: P112.

> P112: Hình thức, định dạng quyển báo cáo

Triển khai: Chưa xác định artifact triển khai riêng.
Bằng chứng: remediation_evidence/G9_thesis/10_SUBMISSION_CHECKLIST.md.
Kiểm thử: Chưa có kiểm thử hoặc biên bản riêng.
Hành động: Chuyển Word/PDF theo mẫu trường và kiểm tra layout ở giai đoạn tài liệu cuối.

## R27

**Slide và phong cách báo cáo** — PARTIAL; GVHD: NONE.

Mã cũ: NEW. Nguồn: P118.

> P118: Phong cách báo cáo, Slide.

Triển khai: Chưa xác định artifact triển khai riêng.
Bằng chứng: remediation_evidence/G9_thesis/07_DEFENSE_SLIDE_CONTENT.md.
Kiểm thử: Chưa có kiểm thử hoặc biên bản riêng.
Hành động: Chuẩn hóa nội dung hiện tại; tạo PPTX và diễn tập ở giai đoạn sau.

## R28

**Phân công nhóm và tác phong làm việc** — NOT_EVIDENCED; GVHD: PENDING.

Mã cũ: NEW. Nguồn: P063.

> P063: Lập kế hoạch và phân công thực hiện công việc

Triển khai: Chưa xác định artifact triển khai riêng.
Bằng chứng: remediation_evidence/G9_thesis/10_SUBMISSION_CHECKLIST.md.
Kiểm thử: Chưa có kiểm thử hoặc biên bản riêng.
Hành động: Nhóm cung cấp nhật ký/phân công thực tế; không tự gán tên thành viên hay xác nhận tác phong.

## R29

**Gặp GVHD hằng tuần và tích hợp nội dung** — NOT_EVIDENCED; GVHD: PENDING.

Mã cũ: NEW. Nguồn: P188.

> P188: Gặp giảng viên hướng dẫn ít nhất 1 lần/tuần, thực hiện đề tài theo sự phân công của giảng viên hướng dẫn. Trước mỗi buổi báo cáo, sinh viên phải tích hợp những nội dung được phân công vào chung trong một tài liệu/ phần mềm.

Triển khai: Chưa xác định artifact triển khai riêng.
Bằng chứng: remediation_evidence/G9_thesis/10_SUBMISSION_CHECKLIST.md.
Kiểm thử: Chưa có kiểm thử hoặc biên bản riêng.
Hành động: Chuẩn bị agenda và mẫu biên bản; chờ nhóm xác nhận lịch sử trao đổi.

## R30

**Lịch 12 tuần và hạn nộp** — PARTIAL; GVHD: PENDING.

Mã cũ: NEW. Nguồn: P048.

> P048: Thời gian thực hiện: 12 tuần (từ ngày 10/08/2026 đến ngày 25/10/2026).

Triển khai: Chưa xác định artifact triển khai riêng.
Bằng chứng: remediation_evidence/G9_thesis/10_SUBMISSION_CHECKLIST.md.
Kiểm thử: Chưa có kiểm thử hoặc biên bản riêng.
Hành động: Giữ nguyên lịch đề gốc; tiến độ thật báo cáo riêng; không tự xác nhận gia hạn hoặc đã nộp.

## R31

**Khảo sát công trình và tài liệu tham khảo** — PARTIAL; GVHD: NONE.

Mã cũ: NEW. Nguồn: P057.

> P057: Khảo sát các công trình nghiên cứu liên quan

Triển khai: Chưa xác định artifact triển khai riêng.
Bằng chứng: remediation_evidence/G9_thesis/06_REFERENCES.md.
Kiểm thử: Chưa có kiểm thử hoặc biên bản riêng.
Hành động: Bảo toàn danh mục nguồn đề; chuẩn hóa cách dẫn và ghi rõ nguồn chưa được xác minh trực tuyến trong đợt này.

## R32

**Ví dụ trễ dẫn tới xung đột và xử lý** — PARTIAL; GVHD: NONE.

Mã cũ: NEW. Nguồn: P068.

> P068: Ví dụ minh hoạ: một kịch bản chuyến bay bị trễ làm phát sinh xung đột cổng và cách bài toán tối ưu tái phân bổ cổng xử lý tình huống này

Triển khai: Chưa xác định artifact triển khai riêng.
Bằng chứng: remediation_evidence/G9_thesis/08_DEMO_SCRIPT.md.
Kiểm thử: tests/web_dashboard/test_experiments.py.
Hành động: Dùng ví dụ được ghi nhãn minh họa, không biến thành bằng chứng vận hành thật.

## R33

**Cấu hình hệ thống và xử lý theo tập con** — PARTIAL; GVHD: NONE.

Mã cũ: NEW. Nguồn: P031, P082.

> P031: Mô tả cấu hình hệ thống và ngôn ngữ lập trình: Windows 11, CPU tối thiểu Core i5, RAM ≥ 16GB, ổ SSD. Ngôn ngữ lập trình: Python 3.11 trở lên, sử dụng các thư viện Pandas, NumPy, Scikit-learn, XGBoost, Optuna, Google OR-Tools (CP-SAT) và SHAP.
> P082: Mô tả cấu hình hệ thống: hệ điều hành Windows 11/Ubuntu 22.04, CPU tối thiểu Core i5, RAM ≥ 16GB, Lựa chọn môi trường thử nghiệm: Visual Studio Code, Jupyter Notebook để phát triển mô hình ML và bộ giải CP-SAT

Triển khai: scripts/start_web_dashboard.ps1; scripts/start_web_dashboard.cmd.
Bằng chứng: requirements-app.txt.
Kiểm thử: Chưa có kiểm thử hoặc biên bản riêng.
Hành động: Ghi cấu hình kiểm tra thật; không cam kết performance trên mọi Core i5/Ubuntu khi chưa đo.

## R34

**Mục tiêu hỗ trợ quyết định trên sân bay mô phỏng** — PARTIAL; GVHD: NONE.

Mã cũ: NEW. Nguồn: P015.

> P015: Xây dựng hệ thống hỗ trợ ra quyết định cho bài toán tái phân bổ cổng đỗ tàu bay, kết hợp mô hình học máy dự báo độ trễ chuyến bay với mô hình tối ưu hóa có ràng buộc trên môi trường sân bay mô phỏng, nhằm giảm tác động của độ trễ và hạn chế xung đột tài nguyên cổng.

Triển khai: src/optimization/domain.py.
Bằng chứng: artifacts/remediation/native_dual_core_g4_pilot/run_manifest.json.
Kiểm thử: tests/test_g5_solver_correctness.py.
Hành động: Kết luận trong phạm vi mô phỏng; không tuyên bố giảm độ trễ sân bay thật hoặc deployment certification.

## R35

**Khuyến khích NCKH và công bố** — NOT_EVIDENCED; GVHD: NONE.

Mã cũ: NEW. Nguồn: P121.

> P121: Cộng điểm khuyến khích cho nhóm sinh viên tham gia thực hiện NCKH liên quan nội dung đề tài (tổng điểm chung không vượt quá 10 điểm)

Triển khai: Chưa xác định artifact triển khai riêng.
Bằng chứng: remediation_evidence/G9_thesis/10_SUBMISSION_CHECKLIST.md.
Kiểm thử: Chưa có kiểm thử hoặc biên bản riêng.
Hành động: Yêu cầu tùy chọn; không tính điểm hoặc ghi đạt giải khi chưa có hồ sơ.

## Thang điểm và lịch gốc

Các ô của ba bảng được giữ trong [proposal_extract.json](../../../artifacts/reconciliation/phase1_2/proposal_extract.json).
T1R7 chứa CLO3, điểm tổng 4,0 và điểm con. Không cộng lặp hoặc tự phân điểm khi nguồn chưa chỉ rõ.
T1R13 là khuyến khích NCKH. Lịch tuần thiếu số hiển thị trong ô nguồn được giữ nguyên.
