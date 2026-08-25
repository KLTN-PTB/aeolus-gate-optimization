**ỨNG DỤNG HỌC MÁY VÀ LẬP TRÌNH RÀNG BUỘC TRONG DỰ BÁO ĐỘ TRỄ CHUYẾN BAY VÀ TỐI ƯU TÁI PHÂN BỔ CỔNG ĐỖ TÀU BAY**

**ROADMAP TRIỂN KHAI 12 TUẦN - BẢN ĐỒNG BỘ**

*Bản thiết kế cấp cao theo đề cương và quyết định cuối cùng của nhóm*

| **Phiên bản**          | 3.0 - Đồng bộ theo protocol nghiên cứu đã duyệt                                 |
|------------------------|---------------------------------------------------------------------------------|
| **Ngày**               | 23/08/2026                                                                      |
| **Phạm vi**            | 12 tuần - Aeolus 2016-2024                                                      |
| **Quyết định cốt lõi** | Tabular chính + Flight Chain optional có GO/NO-GO sớm + Synthetic Aircraft Turn |

# 1. Mục tiêu của roadmap

Roadmap này chuyển đề cương đã đồng bộ thành kế hoạch triển khai 12 tuần theo kiến trúc Predict -> Simulate -> Optimize -> Evaluate. Aeolus 2016-2024 được audit schema theo từng năm; dự báo pre-flight dùng prediction cut-off cố định T = CRS_DEP_TIME - 2 giờ. Machine Learning được phát triển bằng rolling temporal validation trong 2016-2022, năm 2023 dùng cho development confirmation và hoàn thiện simulation/optimization, còn 2024 được khóa làm final end-to-end holdout chỉ mở sau khi toàn bộ pipeline đã freeze.

Nguyên tắc khóa phạm vi: không suy diễn 2017-2024 giống 2016 trước khi audit; không truy vết tail number/aircraft registration thật; Flight Chain chỉ đi tiếp nếu GO/NO-GO chứng minh mapping an toàn; không dùng 2024 để điều chỉnh bất kỳ model/simulation/optimization config nào; CP-SAT và hybrid CP-SAT+SA phải so sánh dưới cùng tổng ngân sách tính toán; optimizer chỉ giảm tác động của delay lên gate operations, không làm giảm flight delay thực tế.

# Các quyết định thống nhất dùng xuyên suốt

| **Hạng mục**                | **Quyết định thống nhất**                                                                                                                                                                                                           |
|-----------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Phạm vi dữ liệu             | Aeolus 2016-2024; bắt buộc schema audit từng năm trước canonical schema; xử lý year-by-year/chunk, không rút ngắn phạm vi năm.                                                                                                      |
| Dữ liệu chính               | Aeolus Tabular là nguồn bắt buộc cho ML.                                                                                                                                                                                            |
| Flight Chain                | Optional context. Feasibility audit + GO/NO-GO ở tuần 1-2; chỉ ablation nếu có mapping an toàn, đúng prediction cut-off và không suy luận aircraft identity/rotation thật.                                                          |
| Flight Network              | Không dùng trong pipeline chính; không triển khai GNN trong 12 tuần.                                                                                                                                                                |
| Hub thí nghiệm              | ATL; ML chính dùng inbound DEST=ATL, outbound ORIGIN=ATL dùng cho tầng mô phỏng Aircraft Turn.                                                                                                                                      |
| Temporal protocol           | Rolling temporal validation bên trong 2016-2022 cho tuning/model development; 2023 dùng development confirmation/model selection và phát triển downstream; 2024 là final end-to-end holdout chỉ mở sau khi toàn bộ hệ thống freeze. |
| Classification target       | P(ARR_DELAY >= 15 phút); nhãn = 1 khi ARR_DELAY >= 15, ngược lại 0.                                                                                                                                                               |
| Regression target           | ARR_DELAY theo phút, giữ giá trị âm/0/dương.                                                                                                                                                                                        |
| Tối đa 5 phương pháp ML     | 1) Logistic/Ridge, 2) Random Forest, 3) HistGradientBoosting, 4) XGBoost, 5) Weighted Ensemble.                                                                                                                                    |
| Aircraft Turn               | Mô phỏng bằng TURN_ID + SIM_AIRCRAFT_ID; không tạo/giả lập TAIL_NUM thật.                                                                                                                                                           |
| Đơn vị tối ưu gate          | Aircraft Turn mô phỏng, không phải aircraft identity thật.                                                                                                                                                                          |
| Tài nguyên gate             | 20-50 gate mô phỏng, mặc định 30 contact gates cho core; REMOTE_STAND là resource riêng có availability/capacity, UNASSIGNED là trạng thái không được gán.                                                                          |
| Quy mô kịch bản             | Ba mức benchmark khoảng 100 / 200 / 300 flight movements trong 24 giờ; đây là sampled/synthetic scenario, không đại diện toàn bộ một ngày vận hành ATL.                                                                             |
| Optimization                | Initial Greedy -> CP-SAT standalone -> Hybrid CP-SAT + Simulated Annealing; hybrid chỉ refinement time-limited incumbent và phải dùng cùng tổng compute budget với CP-SAT standalone.                                             |
| Infeasible/fallback         | Tách CONTACT_GATE / REMOTE_STAND / UNASSIGNED; giữ hard constraints, remote có resource constraints và penalty cao, unassigned có penalty rất cao; không phá compatibility để ép feasible.                                          |
| Robustness                  | Hai protocol: plan robustness (giữ assignment cố định dưới perturbation) và recourse (re-optimize sau realization). Chạy pilot 20 -> 50; final target 500 scenarios nếu runtime khả thi, dùng cùng scenario seeds.                 |
| Dashboard                   | Streamlit + Plotly.                                                                                                                                                                                                                 |
| Claim nghiên cứu            | Tối ưu tác động của delay lên gate operations; không tuyên bố solver làm giảm flight delay thực tế.                                                                                                                                 |
| Prediction cut-off          | Cố định T = CRS_DEP_TIME - 2 giờ cho core experiment. Weather/feature chỉ SAFE nếu chứng minh khả dụng tại hoặc trước cut-off; nếu không phải lag/drop.                                                                             |
| ML -> Optimization utility | Core experiment so Schedule-only vs ML prediction vs Oracle actual ARR_DELAY (Oracle chỉ là upper-bound evaluation, không phải operational input) dưới cùng solver/scenario.                                                        |

# 2. Kiến trúc tổng thể

| **Tầng**           | **Nội dung**                                                                                         | **Đầu ra chính**                                             |
|--------------------|------------------------------------------------------------------------------------------------------|--------------------------------------------------------------|
| 1. Data           | Aeolus Tabular 2016-2024 cho ATL; schema audit từng năm; Flight Chain feasibility optional           | Canonical schema + inbound/outbound partitions + manifests   |
| 2. Preprocessing  | Prediction cut-off T-2h, leakage/weather audit, model-specific preprocessing, rolling temporal folds | Development folds 2016-2022 + 2023 development + sealed 2024 |
| 3. ML comparison  | 4 base methods + Weighted Ensemble; rolling validation + fixed HPO budget                            | p_delay_15 + predicted ARR_DELAY + 2023 model selection      |
| 4. Optional Chain | GO/NO-GO sớm; nếu GO thì ablation Tabular-only vs Tabular+Chain trên 2023                            | KEEP/DROP decision trước downstream freeze                   |
| 5. Simulation     | Synthetic Aircraft Turn trên 2023 + 20-50 gates + pairing/turnaround/scenario-size sensitivity       | TURN occupancy windows + initial gate plan                   |
| 6. Baseline       | Conflict verifier + Greedy + Schedule-only/ML/Oracle regimes                                         | Baseline assignments + utility KPI                           |
| 7. Optimization   | CP-SAT standalone vs equal-compute CP-SAT+SA; CONTACT/REMOTE/UNASSIGNED tách biệt                    | Feasible assignments + objective/bound/gap/runtime           |
| 8. Robustness     | Plan robustness + recourse; pilot 20/50 -> final target 500 scenarios                               | Robustness/scalability distributions + freeze report         |
| 9. Final holdout  | Mở 2024 đúng một lần sau khi model + simulation + optimization config freeze                         | Final end-to-end ML/optimization results                     |
| 10. Demo          | Streamlit + Plotly                                                                                   | Dashboard + reproducible artifacts                           |

# 3. Chiến lược dữ liệu và Machine Learning

- Sử dụng toàn bộ Aeolus 2016-2024 trong phạm vi ATL; trước khi hợp nhất phải audit schema từng năm (columns, dtype, row count, date coverage, missingness, target distribution, carrier/airport cardinality, weather fields, index consistency và duplicates). Dữ liệu được xử lý theo từng năm/chunk và lưu Parquet để kiểm soát RAM/disk IO.

- ML chính dự báo inbound DEST=ATL. Outbound ORIGIN=ATL được giữ để xây Aircraft Turn mô phỏng, không dùng để suy luận tail number thật.

- Temporal protocol: rolling validation chỉ trong 2016-2022 cho preprocessing/tuning/calibration/ensemble development; sau đó fit lại trên 2016-2022 và dùng 2023 cho development confirmation/model selection. Năm 2024 giữ kín cho final end-to-end evaluation sau khi toàn bộ ML + simulation + optimization đã freeze.

- Tối đa 5 phương pháp ML: Logistic/Ridge, Random Forest, HistGradientBoosting, XGBoost, Weighted Ensemble. Ensemble có thể không trở thành champion nếu không cải thiện.

- Classification: P(ARR_DELAY >= 15); Regression: ARR_DELAY signed minutes. Actual operation fields chỉ làm label/evaluation.

- Flight Chain được feasibility-audit ngay tuần 1-2. Nếu không có flight-level mapping/semantics an toàn thì DROP sớm; chỉ khi GO mới chạy ablation trên 2023, không dùng split .pt gốc làm temporal split chính.

| **\#** | **Classification**              | **Regression**                 | **Vai trò**                         |
|--------|---------------------------------|--------------------------------|-------------------------------------|
| 1      | Logistic Regression             | Ridge Regression               | Baseline tuyến tính, dễ giải thích  |
| 2      | Random Forest Classifier        | Random Forest Regressor        | Tree ensemble baseline              |
| 3      | HistGradientBoosting Classifier | HistGradientBoosting Regressor | Gradient boosting baseline hiệu quả |
| 4      | XGBoost Classifier              | XGBoost Regressor              | Model mạnh, phân tích SHAP sâu      |
| 5      | Weighted probability ensemble   | Weighted prediction ensemble   | Kết hợp các base model tốt nhất     |

# 4. Quy tắc Synthetic Aircraft Turn và Gate Occupancy

Aircraft Turn là tầng mô phỏng dùng để giải quyết bài toán gate có thời điểm chiếm và giải phóng hữu hạn. Mỗi TURN có thể ghép một inbound với một outbound hợp lệ; nếu không ghép được thì dùng fallback service window. TURN_ID và SIM_AIRCRAFT_ID chỉ có ý nghĩa trong simulation.

| **Quy tắc**                      | **Định nghĩa thống nhất**                                                                                                                                  |
|----------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Nhãn classification              | y_cls = 1 nếu ARR_DELAY >= 15; ngược lại y_cls = 0.                                                                                                       |
| Target regression                | y_reg = ARR_DELAY (phút, signed).                                                                                                                          |
| Predicted arrival                | A_pred = A_sched + DeltaT_pred.                                                                                                                            |
| Risk buffer                      | B_risk = f(p_delay); baseline đề xuất: clip(round(B_max \* p_delay), 0, B_max), với p_delay đã calibration và B_max nằm trong config/sensitivity analysis. |
| Earliest feasible departure      | D_min = A_pred + T_turnaround.                                                                                                                             |
| Predicted/simulated departure    | D_pred = max(D_sched, D_min).                                                                                                                              |
| Gate release - paired turn       | Gate_release = D_pred + B_risk.                                                                                                                            |
| Gate release - unmatched inbound | Gate_release = A_pred + dwell_default + B_risk.                                                                                                            |
| Occupancy                        | Gate occupancy = \[A_pred, Gate_release\].                                                                                                                 |
| Nominal occupancy                | Initial schedule dùng A_sched và nominal release trước khi inject predicted delay; reassignment được đo so với initial gate plan.                          |

- Nominal gate plan được tạo từ schedule trước khi inject prediction. Reassignment được tính so với initial_gate_id, vì vậy thuật ngữ tái phân bổ được dùng đúng nghĩa.

- P(delay) chủ yếu chuyển thành B_risk đã calibration; core objective không cộng thêm generic risk exposure nếu không có định nghĩa độc lập để tránh double-count uncertainty. DeltaT regression dịch chuyển predicted arrival.

- Benchmark simulation ở ba mức khoảng 100/200/300 flight movements trong 24 giờ; số TURN là kết quả pairing/fallback. Pairing/turnaround/gate assumptions phải có sensitivity analysis và không được mô tả như một ngày vận hành thật của ATL.

- Nếu contact gate không khả thi, solver phân biệt REMOTE_STAND (resource có no-overlap/availability/capacity) và UNASSIGNED (không được gán) với penalty riêng; không dùng relaxation phá hard compatibility.

# 5. Roadmap 12 tuần

| **Tuần** | **Trọng tâm**                                                          | **Mục tiêu**                                                                                                                                                      | **Deliverable chính**                                                                                                          |
|----------|------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------|
| Tuần 1   | Chốt phạm vi, prediction cut-off và audit feasibility                  | Khóa T = CRS_DEP_TIME - 2h, decision registry, schema-audit plan và Flight Chain feasibility audit ban đầu.                                                       | project_structure.md; decision_registry.md; schema_audit_plan.md; flight_chain_feasibility_v0.md; ...                          |
| Tuần 2   | Schema audit 2016-2024, ATL filter, leakage/weather và GO/NO-GO Chain  | Tạo canonical schema, temporal manifests; xác nhận weather availability tại T-2h và quyết định Flight Chain có đủ điều kiện đi tiếp hay không.                    | schema_compatibility_matrix.md; atl_inbound.parquet; atl_outbound.parquet; split_manifest.json; decision_include_chain.md; ... |
| Tuần 3   | Preprocessing, feature engineering và outlier protocol                 | Tạo common information set nhưng cho phép model-specific transforms; giữ raw signed ARR_DELAY và định nghĩa sensitivity/simulation guard.                         | src/data/preprocessing.py; src/features/tabular_features.py; feature_manifest.json; tests/test_no_leakage.py; ...              |
| Tuần 4   | 3 baseline + rolling temporal validation                               | Train Logistic/Ridge, RF, HGB và đánh giá trên rolling folds trong 2016-2022; lưu OOF predictions.                                                                | src/models/linear_models.py; random_forest.py; hist_gradient_boosting.py; reports/baseline_ml_rolling.md; ...                  |
| Tuần 5   | XGBoost + Optuna với fixed budget                                      | Hoàn thành model số 4; tuning RF/HGB/XGBoost bằng objective tổng hợp trên rolling folds, budget/seed/pruner khóa trước.                                           | src/models/xgboost_models.py; src/models/optuna_tuning.py; configs/hpo_budget.yaml; optuna_studies/; ...                       |
| Tuần 6   | Weighted Ensemble, 2023 model selection, SHAP và Chain ablation nếu GO | Tối ưu ensemble từ OOF development predictions; dùng 2023 cho model selection/Chain ablation; freeze ML pipeline nhưng chưa mở 2024.                              | weighted_ensemble.py; model_comparison_2023.md; flight_chain_ablation.md; model_registry.json; ...                             |
| Tuần 7   | Synthetic Aircraft Turn và gate simulation trên 2023                   | Tạo sampled scenarios 100/200/300, contact/remote resources, initial plan; chạy pairing/turnaround/gate sensitivity.                                              | turn_generator.py; gate_generator.py; turns_2023.parquet; simulation_assumptions.md; ...                                       |
| Tuần 8   | Conflict engine, Greedy và CP-SAT core + ML utility experiment         | Xây verifier/Greedy/CP-SAT trên 2023; chạy Schedule-only vs ML vs Oracle dưới cùng solver/scenario.                                                               | conflict_engine.py; greedy.py; cp_sat.py; reports/ml_optimization_utility.md; ...                                              |
| Tuần 9   | Equal-compute CP-SAT vs Hybrid CP-SAT+SA + scalability                 | Đánh giá SA như refinement của time-limited incumbent với cùng tổng compute budget; benchmark 100/200/300 movements và solver gap/runtime.                        | simulated_annealing.py; reports/equal_compute_comparison.md; reports/scalability.md; ...                                       |
| Tuần 10  | Robustness trên 2023, Monte Carlo pilot và full-system freeze          | Tách plan robustness/recourse; pilot 20 -> 50, chuẩn bị final target 500 nếu runtime khả thi; freeze toàn bộ config trước 2024.                                  | monte_carlo.py; robustness_pilot.parquet; sensitivity_analysis.md; system_freeze_manifest.json; ...                            |
| Tuần 11  | Final end-to-end holdout 2024                                          | Mở 2024 sau freeze; chạy final ML + simulation + Greedy/CP-SAT/Hybrid + Schedule/ML/Oracle và final Monte Carlo target 500 nếu runtime khả thi, không tuning lại. | reports/final_end_to_end_2024.md; results/final_2024/; monte_carlo_2024.parquet; ...                                           |
| Tuần 12  | Dashboard, đóng gói, báo cáo và bảo vệ                                 | Trực quan hóa development 2023 và final 2024 tách biệt; hoàn thiện reproducibility, luận văn, README, slide và demo.                                              | dashboard/app.py; README.md; requirements.txt; final_thesis_assets/; slides/; ...                                              |

# 6. Các mốc kiểm soát

| **Mốc**           | **Điều kiện đạt**                                                                                                                       |
|-------------------|-----------------------------------------------------------------------------------------------------------------------------------------|
| M1 - cuối tuần 2  | Schema audit 2016-2024 + canonical schema + T-2h cut-off + leakage/weather audit + temporal manifests + Flight Chain GO/NO-GO hoàn tất. |
| M2 - cuối tuần 6  | Đủ 5 phương pháp; rolling-development 2016-2022, model selection/Chain ablation trên 2023; ML pipeline freeze, 2024 chưa mở.            |
| M3 - cuối tuần 7  | Synthetic TURN + contact/remote gates + initial plan trên 2023; pairing/turnaround/scenario-scale sensitivity hoạt động.                |
| M4 - cuối tuần 9  | Greedy/CP-SAT/Hybrid dùng cùng verifier/objective; equal-compute comparison và scalability 100/200/300 hoàn tất.                        |
| M5 - cuối tuần 10 | Plan robustness + recourse pilot hoàn tất; Monte Carlo runtime được ước lượng và toàn bộ system config freeze trước 2024.               |
| M6 - cuối tuần 11 | Final end-to-end holdout 2024 hoàn tất; Schedule-only vs ML vs Oracle và final robustness target 500 nếu runtime khả thi.               |
| M7 - cuối tuần 12 | Dashboard + reproducibility + luận văn/slide/demo đồng bộ; không có tuning sau khi xem 2024.                                            |

# 7. Rủi ro chính và kiểm soát

| **Rủi ro**                                          | **Cách kiểm soát**                                                                                                                                    |
|-----------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------|
| Khối lượng Aeolus 2016-2024 lớn                     | Chunk/year processing, PyArrow/Parquet partition, ATL filter sớm; schema audit bằng streaming, không load toàn bộ raw cùng lúc.                       |
| Weather có nguy cơ look-ahead                       | Core cut-off T = CRS_DEP_TIME - 2h; weather chỉ giữ nếu provenance/timestamp chứng minh availability tại cut-off, nếu không lag/drop.                 |
| Flight Chain không map an toàn/không cải thiện      | Feasibility audit tuần 1-2 và GO/NO-GO sớm; nếu GO mới ablation tuần 6, nếu NO thì DROP không ảnh hưởng core.                                         |
| 2023 bị adaptive overfit                            | HPO/calibration/ensemble development ưu tiên rolling folds 2016-2022; 2023 dùng model selection/downstream development có kiểm soát; 2024 giữ kín.    |
| 2020 distribution shift                             | Báo cáo performance/year và distribution; giữ 2020 trong development data, dùng rolling folds để thấy biến động theo thời gian.                       |
| Synthetic pairing/gate assumptions chi phối kết quả | Chạy sensitivity cho turnaround, max_turn_window, pairing policy, gate mix và scenario scale; không coi synthetic configuration là vận hành ATL thực. |
| Scenario gate infeasible                            | Tách CONTACT_GATE / REMOTE_STAND / UNASSIGNED với constraints và penalty riêng; không phá hard compatibility.                                         |
| Timeline/compute quá tải                            | Khóa Optuna budget; Monte Carlo pilot 20 -> 50 trước final target 500; CP-SAT/Hybrid dùng time limit và equal total compute.                         |

# 8. Phạm vi không triển khai trong 12 tuần

- Không truy vết TAIL_NUM/aircraft registration thật và không tái dựng aircraft rotation thật.

- Không dùng Flight Network/GNN/Deep Learning sequence model làm core.

- Không xây crew scheduling, fleet assignment, ATC optimization, towing/surface optimization hoặc passenger-connection optimization.

- Không tái dựng gate schedule thật của ATL từ Aeolus; gates, compatibility và Aircraft Turn là simulation layer.

- Không thêm LightGBM/CatBoost thành model core thứ 6; chỉ có tối đa 5 phương pháp ML đã khóa.

- Không dùng random split; không mở test 2024 cho tới khi model, simulation, objective weights, solver protocol và robustness protocol đã freeze.

# 9. Tiêu chí hoàn thành đề tài

- Dữ liệu ATL đủ 2016-2024, có schema compatibility matrix theo từng năm, prediction cut-off T-2h và leakage/weather audit có bằng chứng.

- Có tối đa 5 phương pháp ML; tuning bằng rolling temporal folds 2016-2022, model selection trên 2023 và final 2024 chỉ sau full-system freeze.

- Flight Chain có GO/NO-GO sớm; nếu GO mới có ablation/KEEP-DROP trên 2023, nếu không map an toàn thì DROP khỏi pipeline.

- Synthetic Aircraft Turn có start/end hữu hạn; pairing/turnaround/scenario-size sensitivity được báo cáo; contact gate, remote stand và unassigned được phân biệt.

- Greedy, CP-SAT và Hybrid CP-SAT+SA dùng cùng verifier/metric; CP-SAT vs Hybrid dùng cùng tổng compute budget; có Schedule-only vs ML vs Oracle experiment và plan robustness/recourse.

- Final Monte Carlo hướng tới 500 scenarios sau pilot runtime; failed/infeasible cases được giữ trong báo cáo, cùng seeds giữa phương pháp có thể so sánh.

- Dashboard cho thấy Scheduled -> Predicted -> Optimized, phân tách development 2023 với final 2024; luận văn nêu rõ dữ liệu thực Aeolus và simulation layer, không claim giảm flight delay thực tế.
