**ỨNG DỤNG HỌC MÁY VÀ LẬP TRÌNH RÀNG BUỘC TRONG DỰ BÁO ĐỘ TRỄ CHUYẾN BAY VÀ TỐI ƯU TÁI PHÂN BỔ CỔNG ĐỖ TÀU BAY**

**CHI TIẾT TỪNG TUẦN CỦA ROADMAP - BẢN ĐỒNG BỘ**

*Kế hoạch thực thi, deliverable, tiêu chí nghiệm thu và guardrail chống mâu thuẫn*

| **Phiên bản**          | 3.0 - Đồng bộ theo protocol nghiên cứu đã duyệt                                 |
|------------------------|---------------------------------------------------------------------------------|
| **Ngày**               | 23/08/2026                                                                      |
| **Phạm vi**            | 12 tuần - Aeolus 2016-2024                                                      |
| **Quyết định cốt lõi** | Tabular chính + Flight Chain optional có GO/NO-GO sớm + Synthetic Aircraft Turn |

# 1. Cách sử dụng tài liệu

Tài liệu này là bản triển khai chi tiết của file Roadmap 12 tuần. Các tên tuần, target, temporal split, danh sách model, công thức Aircraft Turn, phạm vi gate, Monte Carlo và công nghệ đều lấy từ cùng một decision registry. Nếu có thay đổi cốt lõi, phải sửa đồng thời Roadmap, Tech Stack, Detailed Roadmap và đề cương trước khi tiếp tục experiment.

# Các quyết định thống nhất dùng xuyên suốt

| **Hạng mục**            | **Quyết định thống nhất**                                                                                                                                      |
|-------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Phạm vi dữ liệu         | Aeolus 2016-2024; schema audit từng năm trước canonical schema; year-by-year/chunk.                                                                            |
| Dữ liệu chính           | Aeolus Tabular là nguồn bắt buộc cho ML.                                                                                                                       |
| Flight Chain            | Optional; feasibility audit + GO/NO-GO tuần 1-2; ablation chỉ nếu mapping an toàn tại T-2h; không coi là aircraft identity/rotation.                           |
| Flight Network          | Không dùng trong pipeline chính; không triển khai GNN trong 12 tuần.                                                                                           |
| Hub thí nghiệm          | ATL; ML chính dùng inbound DEST=ATL, outbound ORIGIN=ATL dùng cho tầng mô phỏng Aircraft Turn.                                                                 |
| Temporal protocol       | Rolling folds trong 2016-2022 cho tuning/development; 2023 cho model selection + downstream development; 2024 final end-to-end holdout sau full-system freeze. |
| Classification target   | P(ARR_DELAY >= 15 phút); nhãn = 1 khi ARR_DELAY >= 15, ngược lại 0.                                                                                          |
| Regression target       | ARR_DELAY theo phút, giữ giá trị âm/0/dương.                                                                                                                   |
| Tối đa 5 phương pháp ML | 1) Logistic/Ridge, 2) Random Forest, 3) HistGradientBoosting, 4) XGBoost, 5) Weighted Ensemble.                                                               |
| Aircraft Turn           | Mô phỏng bằng TURN_ID + SIM_AIRCRAFT_ID; không tạo/giả lập TAIL_NUM thật.                                                                                      |
| Đơn vị tối ưu gate      | Aircraft Turn mô phỏng, không phải aircraft identity thật.                                                                                                     |
| Tài nguyên gate         | 20-50 gate mô phỏng; mặc định 30 contact; REMOTE_STAND là resource riêng, UNASSIGNED là failure/slack state.                                                   |
| Quy mô kịch bản         | Benchmark khoảng 100/200/300 flight movements/24h; sampled/synthetic scenario, không đại diện đầy đủ ATL.                                                      |
| Optimization            | Greedy -> CP-SAT standalone -> equal-compute Hybrid CP-SAT+SA; SA refinement time-limited incumbent.                                                         |
| Infeasible/fallback     | CONTACT_GATE / REMOTE_STAND / UNASSIGNED tách biệt; hard constraints giữ nguyên, penalties riêng.                                                              |
| Robustness              | Plan robustness + recourse; pilot 20 -> 50; final target 500 nếu runtime khả thi, same seeds.                                                                 |
| Dashboard               | Streamlit + Plotly.                                                                                                                                            |
| Claim nghiên cứu        | Tối ưu tác động của delay lên gate operations; không tuyên bố solver làm giảm flight delay thực tế.                                                            |
| Prediction cut-off      | Core T = CRS_DEP_TIME - 2 giờ; weather/feature không chứng minh availability tại cut-off phải lag/drop.                                                        |
| ML utility experiment   | Schedule-only vs ML prediction vs Oracle actual ARR_DELAY (upper-bound evaluation only) dưới cùng solver/scenario.                                             |

# 2. Quy ước chung cho mọi tuần

- Raw Aeolus read-only; mọi transform/prediction/simulation ghi artifact mới có version/config/manifest.

- Prediction cut-off core cố định T = CRS_DEP_TIME - 2 giờ; feature/weather chỉ được xem là SAFE nếu chứng minh khả dụng tại hoặc trước cut-off.

- Schema 2016-2024 phải audit theo từng năm trước canonical schema; không suy diễn các năm sau giống 2016.

- Temporal protocol: rolling development folds trong 2016-2022; 2023 dùng model selection và phát triển simulation/optimization; 2024 giữ kín cho final end-to-end sau full-system freeze.

- Có tối đa 5 phương pháp ML trong core comparison; common information set nhưng cho phép model-specific preprocessing/encoding.

- Flight Chain optional; feasibility audit + GO/NO-GO ở tuần 1-2; nếu không map an toàn thì DROP sớm, không suy luận aircraft identity thật.

- TURN_ID/SIM_AIRCRAFT_ID và gate là simulated/synthetic; CONTACT_GATE, REMOTE_STAND, UNASSIGNED được định nghĩa tách biệt.

- Greedy, CP-SAT và Hybrid CP-SAT+SA dùng cùng verifier/metric; CP-SAT standalone và Hybrid dùng cùng tổng compute budget.

- Robustness tách plan robustness và recourse; chạy pilot 20 -> 50 trước final target 500 nếu runtime khả thi; same-seed paired comparison.

- Mỗi tuần cập nhật methodology/experiment notes; 2024 không được dùng để điều chỉnh feature/model/pairing/gate/objective/solver/robustness config.

# 3. Dependency tổng quan

| **Tuần** | **Trọng tâm**                                                                                 | **Phụ thuộc chính**                    |
|----------|-----------------------------------------------------------------------------------------------|----------------------------------------|
| Tuần 1   | Chốt phạm vi, T-2h cut-off, schema-audit plan và Flight Chain feasibility                     | Không                                  |
| Tuần 2   | Schema audit 2016-2024, ATL filter, leakage/weather audit, temporal manifests, Chain GO/NO-GO | Tuần trước                             |
| Tuần 3   | Preprocessing, feature engineering, outlier protocol và model-specific transformers           | Tuần trước                             |
| Tuần 4   | 3 baseline + rolling temporal validation 2016-2022                                            | Tuần trước                             |
| Tuần 5   | XGBoost + Optuna fixed budget trên rolling folds                                              | Tuần trước                             |
| Tuần 6   | Weighted Ensemble, SHAP, 2023 model selection và optional Chain ablation                      | Tuần trước; Chain ablation chỉ nếu GO  |
| Tuần 7   | Synthetic Aircraft Turn + gate simulation trên 2023 + sensitivity                             | Frozen ML predictions/config từ tuần 6 |
| Tuần 8   | Conflict engine, Greedy, CP-SAT core + Schedule/ML/Oracle utility experiment                  | Tuần trước                             |
| Tuần 9   | Equal-compute CP-SAT vs Hybrid CP-SAT+SA + scalability                                        | Tuần trước                             |
| Tuần 10  | Plan robustness/recourse + Monte Carlo pilot + full-system freeze                             | Tuần trước                             |
| Tuần 11  | Final end-to-end holdout 2024                                                                 | system_freeze_manifest cuối tuần 10    |
| Tuần 12  | Dashboard, đóng gói, báo cáo và bảo vệ                                                        | Final 2024 artifacts tuần 11           |

# TUẦN 1: CHỐT PHẠM VI, PREDICTION CUT-OFF, AUDIT AEOLUS VÀ CHUẨN HÓA PROJECT

Mục tiêu tuần: Khóa single source of truth, prediction timestamp và protocol đánh giá trước khi viết pipeline chính; lập kế hoạch schema audit 2016-2024 và kiểm tra khả năng sử dụng Flight Chain.

Phụ thuộc: Không; đây là tuần khóa phạm vi và single source of truth.

## A. Công việc phải thực hiện

- Đọc/đối chiếu đề cương đã đồng bộ; tạo decision registry dùng chung cho code, báo cáo và slide.

- Lập inventory Aeolus 2016-2024 và schema-audit plan: Tabular bắt buộc; Flight Chain optional; Flight Network không thuộc core.

- Chuẩn hóa repository, configs, data/raw, data/processed, reports, tests; thiết lập seed, logging và access guard cho test 2024.

- Chốt ATL là hub thí nghiệm; định nghĩa inbound DEST=ATL, outbound ORIGIN=ATL và targets ARR_DELAY.

- Khóa prediction cut-off core T = CRS_DEP_TIME - 2 giờ; khóa temporal roles: rolling development 2016-2022, development 2023, final holdout 2024.

- Bắt đầu Flight Chain feasibility audit từ bằng chứng 2016: kiểm tra metadata/mapping/semantics; đồng thời mở assumptions, limitations và experiment log.

## B. Hướng triển khai kỹ thuật

- Không sửa raw Aeolus; mọi transform ghi file mới.

- Tạo config/base.yaml chứa year range, hub, T_cutoff, seeds, paths, model names, HPO budget placeholder và simulation defaults.

- Tạo data dictionary ban đầu; danh sách SAFE/TARGET/LEAKAGE/UNCERTAIN; ghi rõ các unknown của 2016 như weather timing, FLIGHTS và index stability.

## Deliverable cuối tuần

- project_structure.md

- decision_registry.md

- data_inventory.md + schema_audit_plan.md

- flight_chain_feasibility_v0.md + data_dictionary_v0.md

- configs/base.yaml

## Tiêu chí nghiệm thu trước khi sang tuần tiếp theo

- Tất cả thành viên dùng cùng target, hub, T-2h cut-off, temporal roles và model list.

- Có kết luận feasibility ban đầu cho Flight Chain; không có giả định Flight Chain = aircraft rotation thật.

- Project smoke test pass, test-2024 access guard hoạt động và config/logging có version.

## Guardrail - các mâu thuẫn phải tránh

- Không gọi weather là SAFE trước khi audit availability tại T = CRS_DEP_TIME - 2 giờ.

- Không dùng TAIL_NUM giả.

- Không dùng random split và không mở 2024 trong development.

## Cập nhật tài liệu khóa luận trong tuần

Ghi lại assumptions, thay đổi config, metric/result chính và hình/bảng liên quan của Tuần 1; mọi quyết định mới phải đối chiếu decision registry trước khi đưa vào luận văn hoặc slide.

# TUẦN 2: SCHEMA AUDIT 2016-2024, ATL FILTER, LEAKAGE/WEATHER AUDIT VÀ FLIGHT CHAIN GO/NO-GO

Mục tiêu tuần: Chứng minh tính tương thích dữ liệu trước khi hợp nhất; tạo canonical schema, temporal manifests và quyết định Flight Chain có đủ điều kiện đi tiếp hay không.

Phụ thuộc: Hoàn tất tiêu chí nghiệm thu của Tuần 1.

## A. Công việc phải thực hiện

- Audit Tabular từng năm 2016-2024 theo chunk: columns/dtype/row count/date coverage/missingness/target distribution/carrier-airport cardinality/weather/index consistency/duplicates.

- Tạo schema compatibility matrix và canonical schema; lọc/lưu inbound DEST=ATL cho ML và outbound ORIGIN=ATL cho simulation.

- Audit actual operational fields: DEP_TIME, ARR_TIME, WHEELS_OFF/ON, TAXI_IN/OUT, AIR_TIME, ACTUAL_ELAPSED_TIME không vào predictor pre-flight.

- Audit weather theo T-2h cut-off. Chỉ giữ biến nếu provenance/timestamp chứng minh available tại hoặc trước cut-off; nếu không phải lag/drop.

- Tạo rolling temporal fold manifest trong 2016-2022; tách 2023 development và 2024 final holdout; không shuffle giữa các năm.

- Hoàn tất Flight Chain feasibility audit: chỉ GO nếu có mapping/semantics đủ tin cậy và temporal-safe; nếu không thì NO-GO/DROP ngay, không chờ tuần 6.

## B. Hướng triển khai kỹ thuật

- Ưu tiên PyArrow/Parquet, partition theo year và flow=inbound/outbound; schema audit dùng streaming để không vượt RAM.

- Không fit encoder/imputer/scaler trên 2023/2024 ở giai đoạn này; ORIGIN_INDEX/DEST_INDEX chỉ đưa vào candidate nếu mapping ổn định xuyên năm.

- Tạo flight_key phục vụ traceability; không gọi key này là aircraft ID; khóa access log cho mọi thao tác với 2024.

## C. Contract temporal split

| **Split**                     | **Năm**   | **Được phép dùng cho**                                                                                                                                  |
|-------------------------------|-----------|---------------------------------------------------------------------------------------------------------------------------------------------------------|
| Rolling development           | 2016-2022 | Fit preprocessing/model trong temporal folds; Optuna/calibration/OOF predictions/ensemble development; không dùng 2023/2024 để HPO.                     |
| Development / model selection | 2023      | Model comparison/champion selection, optional Flight Chain ablation, simulation/optimization/robustness development; được phép điều chỉnh trước freeze. |
| Final holdout                 | 2024      | Chỉ mở sau system freeze; final ML + end-to-end optimization/robustness evaluation; không tuning lại dựa trên kết quả.                                  |

## Deliverable cuối tuần

- data/processed/tabular_by_year/ + schema_compatibility_matrix.md

- atl_inbound.parquet + atl_outbound.parquet

- temporal_folds_manifest.json + split_manifest.json

- leakage_audit.md

- weather_timing_audit.md

- decision_include_chain.md + flight_chain_feasibility_report.md

## Tiêu chí nghiệm thu trước khi sang tuần tiếp theo

- Có schema audit đầy đủ 2016-2024 và canonical schema có version.

- Rolling folds 2016-2022, development 2023 và final holdout 2024 được khóa đúng vai trò.

- SAFE/TARGET/LEAKAGE/UNCERTAIN được review; Flight Chain có GO/NO-GO rõ ràng.

## Guardrail - các mâu thuẫn phải tránh

- Không dùng 2023 cho HPO và không dùng 2024 cho bất kỳ development decision nào.

- Không coi observed weather tương lai là forecast; không suy diễn schema năm sau từ năm 2016.

- Không trộn các temporal folds khi fit preprocessing và không dùng unstable index encoding xuyên năm.

## Cập nhật tài liệu khóa luận trong tuần

Ghi lại assumptions, thay đổi config, metric/result chính và hình/bảng liên quan của Tuần 2; mọi quyết định mới phải đối chiếu decision registry trước khi đưa vào luận văn hoặc slide.

# TUẦN 3: PREPROCESSING, FEATURE ENGINEERING VÀ OUTLIER PROTOCOL CHO ML

Mục tiêu tuần: Tạo common information set tại T-2h cho classification/regression, với model-specific transformers và outlier/simulation-guard protocol được preregister.

Phụ thuộc: Hoàn tất tiêu chí nghiệm thu của Tuần 2.

## A. Công việc phải thực hiện

- Xử lý missing/outlier theo config; main target giữ ARR_DELAY signed nguyên gốc, không tự động xóa extreme delay. Chuẩn bị sensitivity bằng capped/winsorized target hoặc robust loss nếu cần.

- Tạo time/calendar features từ schedule: month, day-of-week, scheduled hour, cyclic features; mọi feature phải khả dụng tại T-2h.

- Duy trì common raw information set nhưng cho phép model-specific preprocessing: Linear có scaling/one-hot; tree/boosting dùng encoding phù hợp, tất cả không leakage.

- Sau ATL filter, loại constant feature; chỉ dùng ORIGIN_INDEX/DEST_INDEX nếu audit chứng minh mapping ổn định; high-cardinality feature phải có temporal-safe strategy.

- Tạo y_cls = ARR_DELAY >= 15 và y_reg = ARR_DELAY signed; simulation guard chỉ clip prediction cực trị theo range preregister, không thay ground truth.

- Lưu feature manifest/version; unit test actual-time field, T-2h availability, fold isolation và 2024 access guard.

## B. Hướng triển khai kỹ thuật

- Linear models dùng StandardScaler/OneHot khi phù hợp; tree models không bắt buộc scaling; preprocessing khác nhau được phép nếu information set giống nhau.

- Mỗi transformer fit riêng trong từng rolling fold; sau model selection protocol mới refit full 2016-2022. 2023 chỉ transform khi sang tuần 6, 2024 chưa transform/evaluate.

- Class imbalance xử lý bằng class weighting/scale_pos_weight từ training fold; không random oversampling xuyên thời gian.

## Deliverable cuối tuần

- src/data/preprocessing.py

- src/features/tabular_features.py

- feature_manifest.json

- dev_features_2016_2022.parquet

- feature_pipeline_registry.json

- configs/outlier_and_simulation_guard.yaml

- tests/test_no_leakage.py + tests/test_cutoff_and_folds.py

## Tiêu chí nghiệm thu trước khi sang tuần tiếp theo

- Pipeline chạy raw partitions -> fold-specific feature matrix bằng một config và không cần mở 2024.

- Classification dùng >=15 đúng tuyệt đối.

- Không có actual operational field/future weather trong predictors; model-specific transformers dùng cùng information set.

## Guardrail - các mâu thuẫn phải tránh

- Không dùng abs(ARR_DELAY).

- Không fit preprocessing trên 2023/2024 trong development folds.

- Không clip ground-truth ARR_DELAY chỉ để làm metric đẹp; simulation guard phải báo riêng.

## Cập nhật tài liệu khóa luận trong tuần

Ghi lại assumptions, thay đổi config, metric/result chính và hình/bảng liên quan của Tuần 3; mọi quyết định mới phải đối chiếu decision registry trước khi đưa vào luận văn hoặc slide.

# TUẦN 4: XÂY 3 PHƯƠNG PHÁP BASELINE VÀ ROLLING TEMPORAL VALIDATION

Mục tiêu tuần: Có 3/5 baseline cho cả hai nhiệm vụ và OOF predictions trên rolling folds 2016-2022 trước XGBoost/Optuna.

Phụ thuộc: Hoàn tất tiêu chí nghiệm thu của Tuần 3.

## A. Công việc phải thực hiện

- Train Logistic Regression cho classification và Ridge Regression cho regression.

- Train Random Forest Classifier/Regressor.

- Train HistGradientBoosting Classifier/Regressor.

- Đánh giá trên rolling temporal folds trong 2016-2022; ghi ROC-AUC, PR-AUC, Recall, F1, Brier cho classification và MAE, RMSE, R2 cho regression, kèm per-fold/per-year distribution.

- Ghi runtime, memory và calibration diagnostics theo fold; không nhìn 2023 để chọn hyperparameter và không mở 2024.

## B. Hướng triển khai kỹ thuật

- Dùng cùng raw information set, target, folds và metrics; cho phép transformer phù hợp từng model nhưng phải fit trong training fold.

- Lưu OOF predictions để tuần 5-6 dùng tuning/ensemble mà không overfit một validation year duy nhất.

- Linear baseline dùng regularization; RF/HGB chưa cần search quá lớn ở tuần này.

## C. Ba phương pháp baseline trong tuần

| **Phương pháp**                 | **Classification**              | **Regression**                 |
|---------------------------------|---------------------------------|--------------------------------|
| Logistic Regression             | Logistic Regression             | Ridge Regression               |
| Random Forest Classifier        | Random Forest Classifier        | Random Forest Regressor        |
| HistGradientBoosting Classifier | HistGradientBoosting Classifier | HistGradientBoosting Regressor |

## Deliverable cuối tuần

- src/models/linear_models.py

- src/models/random_forest.py

- src/models/hist_gradient_boosting.py

- reports/baseline_ml_rolling.md

- predictions/oof_baselines_2016_2022.parquet

## Tiêu chí nghiệm thu trước khi sang tuần tiếp theo

- Có đủ 3/5 phương pháp cho cả hai nhiệm vụ và OOF predictions theo fold.

- Metric tính cùng định nghĩa.

- Không có 2023/2024 leakage.

## Guardrail - các mâu thuẫn phải tránh

- Không coi Accuracy là metric chính.

- Không thay target giữa các model.

- Không báo 2023 champion hoặc test 2024 sớm.

## Cập nhật tài liệu khóa luận trong tuần

Ghi lại assumptions, thay đổi config, metric/result chính và hình/bảng liên quan của Tuần 4; mọi quyết định mới phải đối chiếu decision registry trước khi đưa vào luận văn hoặc slide.

# TUẦN 5: XGBOOST VÀ OPTUNA FIXED-BUDGET TRÊN ROLLING TEMPORAL FOLDS

Mục tiêu tuần: Hoàn thành phương pháp ML số 4 và tuning RF/HGB/XGBoost bằng budget đã khóa, objective tổng hợp trên rolling folds 2016-2022.

Phụ thuộc: Hoàn tất tiêu chí nghiệm thu của Tuần 4.

## A. Công việc phải thực hiện

- Train XGBoost Classifier cho P(ARR_DELAY >= 15) và XGBoost Regressor cho ARR_DELAY phút.

- Tạo Optuna studies cho RF/HGB/XGBoost; objective là aggregate metric qua rolling temporal folds 2016-2022, không dùng 2023.

- Classification tuning ưu tiên ROC-AUC/PR-AUC theo thiết kế; regression ưu tiên MAE và theo dõi RMSE.

- Đánh giá calibration trong development folds; calibration model phải học từ training/OOF development data, không dùng 2023/2024 để tinh chỉnh.

- Lưu best params, study DB, OOF predictions và HPO manifest của toàn bộ 4 base methods.

## B. Hướng triển khai kỹ thuật

- Khóa trials/timeout/seed/sampler/pruner trong configs/hpo_budget.yaml trước khi search; default khởi đầu 30 trials/study, chỉ điều chỉnh theo pilot runtime có ghi decision registry.

- XGBoost scale_pos_weight tính từ train 2016-2022 nếu dùng.

- Không chuẩn hóa numeric riêng cho XGBoost nếu không cần.

## Deliverable cuối tuần

- src/models/xgboost_models.py

- src/models/optuna_tuning.py

- optuna_studies/

- reports/xgboost_tuning_rolling.md

- predictions/oof_all_base_models_2016_2022.parquet

## Tiêu chí nghiệm thu trước khi sang tuần tiếp theo

- Có 4 base methods hoàn chỉnh.

- Best params chỉ dựa rolling development 2016-2022.

- Probability output có calibration report.

## Guardrail - các mâu thuẫn phải tránh

- Không dùng random cross-validation; temporal folds là bắt buộc.

- Không tối ưu trên 2023/2024.

- Không dùng hard class prediction để tính ROC-AUC.

## Cập nhật tài liệu khóa luận trong tuần

Ghi lại assumptions, thay đổi config, metric/result chính và hình/bảng liên quan của Tuần 5; mọi quyết định mới phải đối chiếu decision registry trước khi đưa vào luận văn hoặc slide.

# TUẦN 6: WEIGHTED ENSEMBLE, 2023 MODEL SELECTION, SHAP VÀ OPTIONAL FLIGHT CHAIN ABLATION

Mục tiêu tuần: Hoàn thành phương pháp ML số 5, dùng 2023 cho model selection/optional Chain ablation, sau đó freeze ML pipeline mà chưa mở 2024.

Phụ thuộc: Hoàn tất tiêu chí nghiệm thu của Tuần 5.

## A. Công việc phải thực hiện

- Tạo Weighted Ensemble: classification weighted average probability, regression weighted average prediction.

- Tối ưu ensemble weights từ OOF development predictions 2016-2022 với w_i >= 0 và sum(w_i)=1; không tối ưu weights trực tiếp trên 2023.

- Refit candidate models trên 2016-2022 và so sánh đúng 5 phương pháp trên development year 2023.

- Phân tích SHAP/Feature Importance cho XGBoost/champion; kiểm tra feature plausibility và calibration trên 2023.

- Nếu Flight Chain đã GO ở tuần 2, chạy ablation Tabular-only vs Tabular+Chain trên 2023; nếu NO-GO thì bỏ hoàn toàn khỏi downstream và không cố dùng.

- Chốt champion/KEEP-DROP Chain, freeze ML feature/model/calibration/ensemble artifacts; chưa đánh giá 2024.

## B. Hướng triển khai kỹ thuật

- Ensemble classifier chỉ dùng calibrated probabilities nếu calibration protocol đã được khóa bằng development data.

- Ensemble weights và model registry lưu YAML/JSON, kèm OOF metrics, 2023 metrics và data/feature version.

- Nếu Ensemble không cải thiện, vẫn giữ kết quả như phương pháp so sánh; champion có thể là XGBoost/RF/HGB.

## C. Quy tắc Ensemble và model selection

- Classifier Ensemble lấy weighted average probability; Regressor Ensemble lấy weighted average predicted ARR_DELAY.

- Weights chỉ tối ưu từ OOF 2016-2022; 2023 dùng model selection, không chỉnh weights sau khi xem kết quả.

- Champion có thể là bất kỳ phương pháp nào trong 5; Ensemble không được mặc định là tốt nhất.

- Final Test 2024 bị khóa tới sau full-system freeze ở cuối tuần 10.

## Deliverable cuối tuần

- src/models/weighted_ensemble.py + configs/ensemble_weights.yaml

- reports/model_comparison_2023.md

- reports/shap_analysis.md

- reports/flight_chain_ablation.md + decision_include_chain.md

- model_registry.json + ml_freeze_manifest.json

## Tiêu chí nghiệm thu trước khi sang tuần tiếp theo

- Có đúng tối đa 5 phương pháp trong core comparison.

- Weights không dùng 2023/2024 để tối ưu; 2024 chưa mở.

- Champion/Chain decision được chọn theo rule đã ghi trước và ML freeze manifest tồn tại.

## Guardrail - các mâu thuẫn phải tránh

- Không thêm LightGBM/CatBoost thành model core thứ 6.

- Không ép Ensemble phải thắng.

- Không dùng test 2024 để xác nhận lại champion hoặc điều chỉnh feature.

## Cập nhật tài liệu khóa luận trong tuần

Ghi lại assumptions, thay đổi config, metric/result chính và hình/bảng liên quan của Tuần 6; mọi quyết định mới phải đối chiếu decision registry trước khi đưa vào luận văn hoặc slide.

# TUẦN 7: SYNTHETIC AIRCRAFT TURN, GATE SIMULATION VÀ SENSITIVITY TRÊN 2023

Mục tiêu tuần: Biến development scenarios 2023 thành TURN có start/end hữu hạn, contact/remote gate resources và initial plan trước khi xây solver; chưa mở 2024.

Phụ thuộc: ML freeze manifest cuối tuần 6; Flight Chain không phải dependency nếu quyết định DROP.

## A. Công việc phải thực hiện

- Chọn các ngày 2023 theo protocol deterministic để tạo ba mức sampled scenario khoảng 100/200/300 flight movements; ghi rõ không đại diện toàn bộ vận hành ATL.

- Ghép inbound/outbound synthetic theo temporal feasibility; ưu tiên cùng carrier như một heuristic, mỗi flight dùng tối đa một lần; tạo TURN_ID/SIM_AIRCRAFT_ID.

- Tạo fallback: unmatched inbound dùng dwell_default; outbound-only dùng pre_service_time; không có occupancy vô hạn.

- Sinh 20-50 gate mô phỏng (mặc định 30 contact) và REMOTE_STAND resources với availability/capacity/class; UNASSIGNED không phải gate resource.

- Tạo nominal occupancy từ schedule và initial Greedy gate plan; lưu initial_gate_id làm mốc reassignment.

- Từ frozen ML predictions 2023, tính A_pred, B_risk, D_pred, Gate_release; core objective chưa thêm generic risk exposure ngoài B_risk.

## B. Hướng triển khai kỹ thuật

- Pairing deterministic theo seed/config; không claim same physical aircraft; mọi synthetic assumption được version hóa.

- Chạy sensitivity cho T_turnaround, max_turn_window, same-carrier preference/fallback dwell và gate mix; có conservative/default/relaxed configurations.

- Scenario-scale protocol và selection seed phải cố định trước optimization; 2024 vẫn bị access guard.

## Deliverable cuối tuần

- src/simulation/turn_generator.py

- src/simulation/gate_generator.py

- data/simulation/turns_2023.parquet + gates_2023.yaml

- data/simulation/initial_gate_plan_2023.parquet

- reports/simulation_assumptions_and_sensitivity.md

## Tiêu chí nghiệm thu trước khi sang tuần tiếp theo

- Mỗi TURN có start \< end; không flight nào thuộc hai paired TURN.

- CONTACT/REMOTE resources và UNASSIGNED semantics tách biệt; initial/predicted occupancy tách rõ.

- Có kết quả sensitivity và ba scenario scales; 2024 chưa được sử dụng.

## Guardrail - các mâu thuẫn phải tránh

- Không suy luận TAIL_NUM/rotation thật.

- Không gọi sampled 100/200/300 movements là một ngày ATL đầy đủ.

- Không dùng parameter chỉ vì làm solver dễ hơn; mọi assumption phải có config/sensitivity.

## Cập nhật tài liệu khóa luận trong tuần

Ghi lại assumptions, thay đổi config, metric/result chính và hình/bảng liên quan của Tuần 7; mọi quyết định mới phải đối chiếu decision registry trước khi đưa vào luận văn hoặc slide.

# TUẦN 8: CONFLICT ENGINE, GREEDY, CP-SAT CORE VÀ ML -> OPTIMIZATION UTILITY EXPERIMENT

Mục tiêu tuần: Có verifier độc lập, Greedy baseline và CP-SAT core trên 2023; đo trực tiếp giá trị của dự báo ML đối với quyết định gate.

Phụ thuộc: Synthetic scenarios 2023 và frozen ML outputs từ tuần 7.

## A. Công việc phải thực hiện

- Inject predicted occupancy vào initial gate plan; conflict engine kiểm tra no-overlap, availability, compatibility, buffer và CONTACT/REMOTE resource semantics.

- Xây Greedy reassignment baseline: ưu tiên giữ initial contact gate, sau đó remote feasible; nếu không có resource thì UNASSIGNED.

- Xây CP-SAT TURN-to-gate với CONTACT/REMOTE/UNASSIGNED tách biệt; hard constraints giữ nguyên.

- Core soft objective: reassignments + remote penalty + unassigned penalty + utilization imbalance (+ optional documented preference). Không thêm generic risk exposure nếu chỉ lặp B_risk.

- Thiết kế ML utility experiment trên cùng solver/scenario: Schedule-only, ML prediction và Oracle actual ARR_DELAY. Oracle chỉ dùng upper-bound evaluation.

- Log conflicts, reassignments, contact/remote/unassigned, utilization, objective components, runtime, solver status/bound/gap.

- Tạo small expected-result tests cho verifier và assignment statuses trước khi so solver.

## B. Hướng triển khai kỹ thuật

- Conflict engine là source of truth cho Greedy/CP-SAT/SA; metric definitions khóa trước comparison.

- Objective weights nằm trong YAML và chỉ điều chỉnh trên 2023 development scenarios; mọi thay đổi ghi experiment log.

- Prediction output: DeltaT -> A_pred; p_delay -> B_risk. Core objective không double-count cùng uncertainty.

## C. Công thức Aircraft Turn và gate occupancy bắt buộc

| **Thành phần**                   | **Quy tắc**                                                                                                                                                |
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

## D. Information regimes và assignment status

- Schedule-only: dùng nominal/scheduled occupancy, không dùng ML prediction.

- ML: dùng frozen p_delay_15 và DeltaT prediction để tạo B_risk/A_pred.

- Oracle: dùng actual ARR_DELAY chỉ để ước lượng upper bound của perfect information; không dùng để tạo operational feature/model.

- Assignment status phải là CONTACT, REMOTE hoặc UNASSIGNED; REMOTE vẫn chịu no-overlap/availability/capacity.

- Ba information regimes chạy trên cùng sampled scenario, solver, gate set và metrics.

## Deliverable cuối tuần

- src/optimization/conflict_engine.py

- src/optimization/greedy.py

- src/optimization/cp_sat.py

- src/evaluation/ml_optimization_utility.py

- configs/optimization.yaml

- reports/greedy_cp_sat_and_ml_utility_2023.md

## Tiêu chí nghiệm thu trước khi sang tuần tiếp theo

- Verifier bắt đúng conflict/status cố ý tạo và mọi solver output đều qua verifier.

- Schedule-only/ML/Oracle dùng đúng cùng scenario/solver config.

- CP-SAT hard-feasible hoặc ghi explicit REMOTE/UNASSIGNED, không phá compatibility.

- 2024 chưa mở.

## Guardrail - các mâu thuẫn phải tránh

- Không gọi Oracle là mô hình deployable.

- Không gộp REMOTE và UNASSIGNED thành một KPI.

- Không thay objective/metrics giữa information regimes.

## Cập nhật tài liệu khóa luận trong tuần

Ghi lại assumptions, thay đổi config, metric/result chính và hình/bảng liên quan của Tuần 8; mọi quyết định mới phải đối chiếu decision registry trước khi đưa vào luận văn hoặc slide.

# TUẦN 9: EQUAL-COMPUTE CP-SAT VS HYBRID CP-SAT+SA VÀ SCALABILITY

Mục tiêu tuần: Đánh giá công bằng CP-SAT standalone và Hybrid dưới cùng tổng compute budget; đo scalability theo 100/200/300 movements.

Phụ thuộc: Hoàn tất tiêu chí nghiệm thu của Tuần 8.

## A. Công việc phải thực hiện

- Định nghĩa total compute budget T theo scenario scale. CP-SAT standalone chạy tối đa T; Hybrid chia budget thành CP-SAT seed phase + SA refinement nhưng tổng không vượt T.

- Dùng CP-SAT incumbent time-limited làm seed cho SA; neighbor phải hard-feasible hoặc reject/repair trước accept.

- Không giả định SA cải thiện CP-SAT; so objective, bound/gap (CP-SAT), feasibility, contact/remote/unassigned và total wall-clock runtime.

- Chạy benchmark small/medium/large (~100/~200/~300 movements) trên cùng scenario generator và verifier.

- Khóa SA temperature/cooling/iterations bằng 2023 development; không dùng 2024 để chọn tham số.

- Tạo paired experiment seeds và lưu compute-budget manifest để tránh so sánh không công bằng.

## B. Hướng triển khai kỹ thuật

- Conflict engine vẫn là source of truth; runtime tính end-to-end cho từng phương pháp.

- Reassignment = optimized_gate_id khác initial_gate_id; không đồng nhất với towing operation.

- CONTACT/REMOTE/UNASSIGNED có penalties và KPI riêng; không che infeasibility.

## Deliverable cuối tuần

- src/optimization/simulated_annealing.py

- reports/equal_compute_cp_sat_vs_hybrid.md

- reports/scalability_100_200_300.md

- results/equal_compute_2023.parquet

- configs/compute_budget.yaml

## Tiêu chí nghiệm thu trước khi sang tuần tiếp theo

- CP-SAT/Hybrid dùng cùng total compute budget và cùng verifier/objective.

- SA final output luôn hard-feasible hoặc bị reject; không sửa occupancy truth để giảm objective.

- Có runtime/objective/status/bound-gap theo scenario scale.

## Guardrail - các mâu thuẫn phải tránh

- Không tuyên bố SA tốt hơn trước khi có kết quả.

- Không cho soft objective hoặc SA phá hard constraints.

- Không thay compute budget có lợi cho một phương pháp sau khi xem kết quả.

## Cập nhật tài liệu khóa luận trong tuần

Ghi lại assumptions, thay đổi config, metric/result chính và hình/bảng liên quan của Tuần 9; mọi quyết định mới phải đối chiếu decision registry trước khi đưa vào luận văn hoặc slide.

# TUẦN 10: PLAN ROBUSTNESS, RECOURSE, MONTE CARLO PILOT VÀ FULL-SYSTEM FREEZE

Mục tiêu tuần: Tách đúng hai khái niệm robustness; đo runtime bằng pilot 20 -> 50 scenarios và freeze toàn bộ pipeline trước khi mở 2024.

Phụ thuộc: Hoàn tất tiêu chí nghiệm thu của Tuần 9.

## A. Công việc phải thực hiện

- Plan robustness: tạo assignment từ forecast rồi GIỮ CỐ ĐỊNH assignment trong các realized perturbation scenarios; đo conflict/violation/remote need/recovery need.

- Recourse: sau khi scenario realization xảy ra, cho phép re-optimize bằng Greedy/CP-SAT/Hybrid; đo gate changes, unassigned, objective và runtime phục hồi.

- Tạo perturbation từ OOF residuals 2016-2022 và development assumptions; 2023 dùng để kiểm tra/sensitivity. Tách delay, turnaround, gate disruption thay vì trộn không kiểm soát.

- Chạy pilot 20 scenarios, sau đó 50; ước lượng total runtime và quyết định khả năng chạy final target 500 ở tuần 11. Dùng same seeds cho paired comparison.

- Lưu scenario_manifest, failed/infeasible cases và không cherry-pick seed.

- Chạy sensitivity cuối trên 2023 cho pairing/turnaround/B_max/gate mix/objective weights; sau đó khóa mọi config.

## B. Hướng triển khai kỹ thuật

- system_freeze_manifest phải chứa model/feature/calibration/ensemble, simulation assumptions, gate config, objective weights, compute budgets, SA params và robustness protocol.

- Không tối ưu total flight delay minutes; chỉ đánh giá gate-related impact trên simulation.

- Sau khi freeze, mọi access/tuning path tới 2024 bị khóa; bug fix nếu có phải version hóa và rerun toàn bộ final test, không dùng kết quả để tune.

## C. Robustness protocol bắt buộc

| **Loại**     | **Nội dung**                                                                                                                                                                                                      |
|--------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Hard         | TURN chọn tối đa một resource assignment: CONTACT hoặc REMOTE, hoặc explicit UNASSIGNED state; no-overlap; gate availability/capacity; synthetic compatibility; buffer.                                           |
| Soft         | Reassignments vs initial plan; REMOTE penalty; UNASSIGNED penalty (cao hơn remote); utilization imbalance; optional documented preference. Generic risk exposure chỉ được thêm nếu định nghĩa độc lập với B_risk. |
| Không tối ưu | Không tối ưu/claim giảm total flight delay minutes, crew, fleet, ATC, passenger connection; không dùng objective làm thay đổi simulation truth.                                                                   |

## Deliverable cuối tuần

- src/evaluation/monte_carlo.py

- results/robustness_pilot_20_50_2023.parquet

- reports/plan_robustness_vs_recourse.md

- reports/sensitivity_analysis_2023.md + system_freeze_manifest.json

## Tiêu chí nghiệm thu trước khi sang tuần tiếp theo

- Có cả plan robustness và recourse results.

- Pilot 20/50 hoàn tất; final 500 feasibility được quyết định bằng runtime estimate, không bằng mong muốn.

- Full-system freeze manifest hoàn chỉnh trước mọi thao tác final với 2024.

## Guardrail - các mâu thuẫn phải tránh

- Không dùng 2024 để thay B_max, pairing, gate mix, objective weights, SA params hoặc Monte Carlo distribution.

- Không gọi re-optimization per scenario là plan robustness.

- Không loại failed/infeasible scenarios khỏi báo cáo.

## Cập nhật tài liệu khóa luận trong tuần

Ghi lại assumptions, thay đổi config, metric/result chính và hình/bảng liên quan của Tuần 10; mọi quyết định mới phải đối chiếu decision registry trước khi đưa vào luận văn hoặc slide.

# TUẦN 11: FINAL END-TO-END HOLDOUT 2024 VÀ FINAL ROBUSTNESS

Mục tiêu tuần: Mở 2024 sau full-system freeze và chạy final evaluation một lần theo protocol đã khóa; không tuning lại dựa trên kết quả.

Phụ thuộc: system_freeze_manifest cuối tuần 10 và final-test access guard được phê duyệt.

## A. Công việc phải thực hiện

- Materialize/process 2024 bằng canonical schema và frozen preprocessing; chạy final classification/regression metrics, calibration và prediction artifacts.

- Áp frozen 2023-developed scenario selection/pairing/gate configuration sang 2024; không thay tham số để fit kết quả 2024.

- Chạy Schedule-only vs ML vs Oracle, Greedy/CP-SAT/Hybrid theo same scenario/verifier/objective/compute budget; báo contact/remote/unassigned riêng.

- Chạy final plan robustness và recourse. Nếu pilot tuần 10 xác nhận runtime khả thi, chạy target 500 scenarios; nếu không, dùng số scenario preregister theo runtime decision và nêu limitation.

- Dùng cùng final scenario IDs/seeds giữa các phương pháp có paired comparison; failed/infeasible cases giữ lại.

- Tổng hợp mean, median, std, p95, conflict rate, reassignments, contact/remote/unassigned, utilization, objective, solver gap và runtime.

- Khóa final results; mọi bug fix kỹ thuật sau khi xem 2024 phải version hóa, giải thích và rerun toàn bộ affected final pipeline, không dùng để tune.

## B. Hướng triển khai kỹ thuật

- Không fit uncertainty distribution hoặc optimizer parameters từ 2024.

- Hybrid không được sửa simulation truth/occupancy; CP-SAT/Hybrid giữ equal total compute.

- Lưu final_test_manifest gồm git commit, configs, seeds, model hashes và artifact versions.

## C. Final-holdout fairness protocol

- 2024 chỉ được đánh giá sau system freeze; không cherry-pick ngày/scenario dựa trên kết quả.

- Schedule-only, ML và Oracle dùng cùng scenario/gate resources; solver comparisons dùng cùng compute budget.

- Không bỏ failed/infeasible cases; Oracle chỉ upper-bound evaluation.

- Thống kê tối thiểu: ML metrics + conflicts, reassignments, contact/remote/unassigned, utilization, objective, bound/gap, runtime và robustness quantiles.

## Deliverable cuối tuần

- reports/final_ml_test_2024.md

- reports/final_end_to_end_2024.md

- results/final_2024_assignments_and_kpi.parquet

- results/monte_carlo_2024.parquet + final_test_manifest.json

- reports/final_robustness_and_ml_utility.md

## Tiêu chí nghiệm thu trước khi sang tuần tiếp theo

- 2024 chỉ xuất hiện sau freeze manifest.

- Các phương pháp/ regimes dùng đúng shared scenario and fairness protocol.

- Không có config change dựa trên final results; mọi final output vượt verifier hoặc ghi infeasible/unassigned minh bạch.

- Có thống kê final ML, scalability/optimization và robustness.

## Guardrail - các mâu thuẫn phải tránh

- Không cherry-pick seed/day sau khi xem kết quả.

- Không đổi objective/compute budget giữa methods trên final holdout.

- Không gọi robustness simulation là bằng chứng vận hành thực tế ATL.

## Cập nhật tài liệu khóa luận trong tuần

Ghi lại assumptions, thay đổi config, metric/result chính và hình/bảng liên quan của Tuần 11; mọi quyết định mới phải đối chiếu decision registry trước khi đưa vào luận văn hoặc slide.

# TUẦN 12: DASHBOARD, ĐÓNG GÓI END-TO-END, BÁO CÁO VÀ BẢO VỆ

Mục tiêu tuần: Hoàn thành sản phẩm tái lập từ Aeolus -> rolling ML development -> 2023 simulation/optimization development -> frozen final 2024 -> Dashboard.

Phụ thuộc: Hoàn tất tiêu chí nghiệm thu của Tuần 11.

## A. Công việc phải thực hiện

- Xây Streamlit + Plotly dashboard: ML risk/predicted arrival, Aircraft Turn, CONTACT/REMOTE/UNASSIGNED, initial vs optimized plan, Gantt, conflict, scalability và robustness KPI.

- Cho phép chọn development 2023 hoặc final 2024, scenario scale và method; phân biệt Scheduled / ML Predicted / Oracle / Optimized và không trộn dev với final.

- Chạy end-to-end regression test trên frozen artifacts; verify hashes/configs/final_test_manifest, không phát sinh tuning path mới.

- Rà soát terminology: Tabular main, Flight Chain GO/NO-GO, synthetic TURN/gate, no tail-number claim, remote != unassigned, plan robustness != recourse.

- Hoàn thiện luận văn, bảng/biểu, tài liệu tham khảo, limitations, README, slide và demo script.

- Kiểm tra consistency giữa đề cương, roadmap, tech stack, code, dashboard và slide trước nộp.

## B. Hướng triển khai kỹ thuật

- Dashboard timeline: gate/resource trục y, time trục x; tooltip có TURN, information regime, assignment status, initial vs optimized và solver metadata.

- README có lệnh tái chạy pipeline và mô tả rõ data/simulation boundary.

- Không expose development/tuning action từ dashboard đối với 2024; final artifacts read-only.

## Deliverable cuối tuần

- dashboard/app.py

- README.md

- requirements.txt

- final_results/

- final_thesis_assets/

- slides/

- demo_checklist.md

## Tiêu chí nghiệm thu trước khi sang tuần tiếp theo

- Có một luồng end-to-end tái chạy được với access guard và freeze/final manifests.

- Không có mâu thuẫn target/cut-off/temporal roles/objective/compute budget/status terminology giữa tài liệu.

- Dashboard phân biệt 2023 development với 2024 final và CONTACT/REMOTE/UNASSIGNED đúng semantics.

- Báo cáo nêu rõ giới hạn mô phỏng.

## Guardrail - các mâu thuẫn phải tránh

- Không thêm model/core scope hoặc chỉnh config dựa trên 2024 vào tuần cuối.

- Không gọi ATL gate schedule là dữ liệu gate thật.

- Không bỏ qua limitations/assumptions.

## Cập nhật tài liệu khóa luận trong tuần

Ghi lại assumptions, thay đổi config, metric/result chính và hình/bảng liên quan của Tuần 12; mọi quyết định mới phải đối chiếu decision registry trước khi đưa vào luận văn hoặc slide.

# 4. Bảng milestone cuối roadmap

| **Mốc**           | **Điều kiện đạt**                                                                                                                       |
|-------------------|-----------------------------------------------------------------------------------------------------------------------------------------|
| M1 - cuối tuần 2  | Schema audit 2016-2024 + canonical schema + T-2h cut-off + leakage/weather audit + temporal manifests + Flight Chain GO/NO-GO hoàn tất. |
| M2 - cuối tuần 6  | Đủ 5 phương pháp; rolling development 2016-2022, 2023 model selection/optional Chain ablation; ML freeze, 2024 chưa mở.                 |
| M3 - cuối tuần 7  | Synthetic TURN + CONTACT/REMOTE resources + initial plan trên 2023; pairing/turnaround/scenario-scale sensitivity hoàn tất.             |
| M4 - cuối tuần 9  | Conflict verifier + Greedy + CP-SAT + equal-compute Hybrid; ML utility and scalability experiments hoạt động trên 2023.                 |
| M5 - cuối tuần 10 | Plan robustness/recourse pilot 20/50 + sensitivity hoàn tất; full-system freeze manifest trước 2024.                                    |
| M6 - cuối tuần 11 | Final end-to-end holdout 2024 + final robustness theo preregistered scenario count hoàn tất.                                            |
| M7 - cuối tuần 12 | Dashboard + end-to-end reproducibility + báo cáo/slide/demo đồng bộ, final 2024 read-only.                                              |

# 5. Checklist đồng bộ cuối cùng

- Aeolus sử dụng đủ 2016-2024 trong phạm vi ATL; có schema audit từng năm và không xuất hiện assumption rằng 2017-2024 giống 2016.

- Prediction cut-off core = CRS_DEP_TIME - 2 giờ; weather/feature chỉ dùng khi chứng minh availability hoặc đã lag/drop đúng protocol.

- Tabular là core; Flight Chain có GO/NO-GO sớm và optional ablation, không bị mô tả là aircraft identity thật.

- Có đúng tối đa 5 phương pháp ML; rolling development 2016-2022 -> 2023 model selection/downstream development -> 2024 final holdout.

- 2024 chỉ được mở sau system_freeze_manifest và không dùng để chỉnh model, pairing, gate config, objective, solver, SA hay robustness distribution.

- TURN_ID/SIM_AIRCRAFT_ID và gate resources đều synthetic; scenario 100/200/300 được ghi là sampled, không phải full ATL operation.

- DeltaT -> A_pred; p_delay -> calibrated B_risk; generic risk objective không double-count uncertainty; simulation guard không thay ground-truth target.

- CONTACT_GATE, REMOTE_STAND và UNASSIGNED tách biệt về constraints, penalty và KPI.

- Greedy/CP-SAT/Hybrid cùng verifier/objective; CP-SAT vs Hybrid dùng equal total compute; không mặc định SA cải thiện CP-SAT.

- Có Schedule-only vs ML vs Oracle experiment, plan robustness vs recourse và Monte Carlo pilot 20/50 trước final target 500 nếu runtime khả thi.

- Dashboard/slide/luận văn phân biệt development 2023 với final 2024 và không tuyên bố giảm flight delay thực tế hoặc dùng gate/tail number thật.
