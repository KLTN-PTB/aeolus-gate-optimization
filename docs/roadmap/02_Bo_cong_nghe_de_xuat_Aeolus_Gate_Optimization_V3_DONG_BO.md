**ỨNG DỤNG HỌC MÁY VÀ LẬP TRÌNH RÀNG BUỘC TRONG DỰ BÁO ĐỘ TRỄ CHUYẾN BAY VÀ TỐI ƯU TÁI PHÂN BỔ CỔNG ĐỖ TÀU BAY**

**BỘ CÔNG NGHỆ ĐỀ XUẤT - BẢN ĐỒNG BỘ**

*Tech stack chính thức cho Predict -> Simulate -> Optimize -> Dashboard*

| **Phiên bản**          | 3.0 - Đồng bộ theo protocol nghiên cứu đã duyệt                                 |
|------------------------|---------------------------------------------------------------------------------|
| **Ngày**               | 23/08/2026                                                                      |
| **Phạm vi**            | 12 tuần - Aeolus 2016-2024                                                      |
| **Quyết định cốt lõi** | Tabular chính + Flight Chain optional có GO/NO-GO sớm + Synthetic Aircraft Turn |

# 1. Nguyên tắc lựa chọn công nghệ

- Ưu tiên stack Python thống nhất, tái lập được và đủ xử lý dữ liệu Aeolus 2016-2024 mà không cần Deep Learning/GNN.

- Data pipeline phải hỗ trợ chunk/year processing, Parquet partition và ATL filtering sớm để kiểm soát RAM/disk IO.

- Tất cả preprocessing/model/tuning tuân prediction cut-off T = CRS_DEP_TIME - 2 giờ; HPO/calibration/ensemble development dùng rolling temporal folds trong 2016-2022, 2023 dùng model selection/downstream development và 2024 chỉ dùng final end-to-end sau full-system freeze.

- ML core có đúng tối đa 5 phương pháp đã khóa; không thêm model core ngoài danh sách nếu chưa sửa decision registry.

- PyTorch chỉ phục vụ đọc/audit Flight Chain .pt; không trở thành framework ML chính.

- Optimization sử dụng OR-Tools CP-SAT; Simulated Annealing tự cài bằng Python/NumPy và chỉ refinement time-limited CP-SAT incumbent. CP-SAT standalone và Hybrid phải so sánh dưới cùng tổng compute budget.

- Raw Aeolus bất biến; processed/simulation artifacts version hóa bằng config, seed và manifest.

# Các quyết định thống nhất dùng xuyên suốt

| **Hạng mục**            | **Quyết định thống nhất**                                                                                                                                                      |
|-------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Phạm vi dữ liệu         | Aeolus 2016-2024; schema audit từng năm trước canonical schema; xử lý year-by-year/chunk.                                                                                      |
| Dữ liệu chính           | Aeolus Tabular là nguồn bắt buộc cho ML.                                                                                                                                       |
| Flight Chain            | Optional context; feasibility audit + GO/NO-GO ở tuần 1-2; chỉ ablation nếu mapping an toàn tại T-2h; không coi là aircraft identity/rotation.                                 |
| Flight Network          | Không dùng trong pipeline chính; không triển khai GNN trong 12 tuần.                                                                                                           |
| Hub thí nghiệm          | ATL; ML chính dùng inbound DEST=ATL, outbound ORIGIN=ATL dùng cho tầng mô phỏng Aircraft Turn.                                                                                 |
| Temporal protocol       | Rolling folds trong 2016-2022 cho development/tuning; 2023 cho model selection + simulation/optimization development; 2024 là final end-to-end holdout sau full-system freeze. |
| Classification target   | P(ARR_DELAY >= 15 phút); nhãn = 1 khi ARR_DELAY >= 15, ngược lại 0.                                                                                                          |
| Regression target       | ARR_DELAY theo phút, giữ giá trị âm/0/dương.                                                                                                                                   |
| Tối đa 5 phương pháp ML | 1) Logistic/Ridge, 2) Random Forest, 3) HistGradientBoosting, 4) XGBoost, 5) Weighted Ensemble.                                                                               |
| Aircraft Turn           | Mô phỏng bằng TURN_ID + SIM_AIRCRAFT_ID; không tạo/giả lập TAIL_NUM thật.                                                                                                      |
| Đơn vị tối ưu gate      | Aircraft Turn mô phỏng, không phải aircraft identity thật.                                                                                                                     |
| Tài nguyên gate         | 20-50 gate mô phỏng; mặc định 30 contact gates. REMOTE_STAND là resource riêng; UNASSIGNED là trạng thái không gán.                                                            |
| Quy mô kịch bản         | Benchmark sampled scenarios ~100/~200/~300 flight movements/24h; pairing/fallback tạo số TURN tương ứng.                                                                       |
| Optimization            | Greedy -> CP-SAT standalone -> equal-compute Hybrid CP-SAT+SA; SA không được mặc định là tốt hơn.                                                                            |
| Infeasible/fallback     | CONTACT_GATE / REMOTE_STAND / UNASSIGNED tách biệt; hard constraints giữ nguyên, penalties riêng.                                                                              |
| Robustness              | Plan robustness + recourse; pilot 20 -> 50; final target 500 scenarios nếu runtime khả thi, cùng seeds cho paired comparison.                                                 |
| Dashboard               | Streamlit + Plotly.                                                                                                                                                            |
| Claim nghiên cứu        | Tối ưu tác động của delay lên gate operations; không tuyên bố solver làm giảm flight delay thực tế.                                                                            |
| Prediction cut-off      | T = CRS_DEP_TIME - 2 giờ. Feature/weather không chứng minh availability tại cut-off phải lag/drop.                                                                             |
| ML utility experiment   | Schedule-only vs ML prediction vs Oracle actual ARR_DELAY (upper-bound evaluation only) dưới cùng solver/scenario.                                                             |

# 2. Tech stack chính thức

| **Công nghệ**     | **Phiên bản định hướng**   | **Vai trò**                                                                 | **Tầng**        |
|-------------------|----------------------------|-----------------------------------------------------------------------------|-----------------|
| Python            | 3.11+                      | Ngôn ngữ chính                                                              | Toàn pipeline   |
| Pandas            | 2.x                        | EDA, transform, joins                                                       | Data processing |
| NumPy             | 1.26+/2.x tương thích      | Vectorization, simulation, metrics hỗ trợ                                   | Data/Simulation |
| PyArrow + Parquet | bản tương thích            | Lưu dữ liệu lớn theo partition, IO nhanh                                    | Data storage    |
| scikit-learn      | 1.4+ hoặc bản khóa ổn định | Logistic/Ridge, RF, HistGradientBoosting, Pipeline, metrics, calibration    | ML              |
| XGBoost           | 2.x+                       | Model boosting chính                                                        | ML              |
| Optuna            | 3.x/4.x                    | Fixed-budget Bayesian HPO trên rolling temporal folds; seed/pruner/study DB | ML tuning       |
| SHAP              | bản tương thích XGBoost    | Explainability                                                              | ML analysis     |
| PyTorch           | CPU đủ dùng                | Chỉ đọc/khảo sát Flight Chain .pt khi cần                                   | Optional Chain  |
| Google OR-Tools   | 9.x+                       | CP-SAT; log status/objective/bound/gap; time-limit/equal-compute protocol   | Optimization    |
| Matplotlib        | 3.x                        | Biểu đồ phân tích/static                                                    | Reporting       |
| Plotly            | 5.x/6.x                    | Gantt/timeline tương tác                                                    | Visualization   |
| Streamlit         | 1.x                        | Dashboard                                                                   | Application     |
| PyYAML            | 6.x                        | Config experiment/simulation/objective                                      | Reproducibility |
| joblib            | 1.x                        | Lưu sklearn model/artifact khi phù hợp                                      | ML artifacts    |
| pytest            | 8.x                        | Unit/integration tests                                                      | Quality         |
| Git + GitHub      | current                    | Version control, README, reproducibility                                    | Engineering     |
| VS Code + Jupyter | current                    | IDE + EDA notebook                                                          | Development     |

Ghi chú phiên bản: trước khi chạy experiment chính thức cần khóa requirements/lockfile bằng một môi trường đã smoke-test. Không nâng package giữa các vòng kết quả nếu chưa rerun regression tests.

# 3. Bộ mô hình Machine Learning

| **\#** | **Classification**              | **Regression**                 | **Mục đích**                        | **Tuning**                                                                        |
|--------|---------------------------------|--------------------------------|-------------------------------------|-----------------------------------------------------------------------------------|
| 1      | Logistic Regression             | Ridge Regression               | Baseline tuyến tính, dễ giải thích  | Tuning nhẹ trong rolling folds 2016-2022; model-specific scaling/encoding         |
| 2      | Random Forest Classifier        | Random Forest Regressor        | Tree ensemble baseline              | Optuna fixed budget trên rolling folds 2016-2022                                  |
| 3      | HistGradientBoosting Classifier | HistGradientBoosting Regressor | Gradient boosting baseline hiệu quả | Optuna fixed budget trên rolling folds 2016-2022                                  |
| 4      | XGBoost Classifier              | XGBoost Regressor              | Model mạnh, phân tích SHAP sâu      | Optuna fixed budget trên rolling folds 2016-2022                                  |
| 5      | Weighted probability ensemble   | Weighted prediction ensemble   | Kết hợp các base model tốt nhất     | Tối ưu weights từ OOF development predictions 2016-2022; 2023 chỉ model selection |

- Weighted Ensemble classification = weighted average của probability; regression = weighted average của predicted ARR_DELAY.

- Ensemble weights được tối ưu từ out-of-fold predictions của rolling development folds 2016-2022 với w_i >= 0 và sum(w_i)=1. Năm 2023 dùng để so sánh/model selection; 2024 tuyệt đối không dùng để chỉnh weights.

- Optuna tập trung cho Random Forest, HistGradientBoosting và XGBoost. HPO budget, timeout, seed, sampler và pruner phải khóa trong config trước khi chạy; mặc định khởi đầu 30 trials/study và chỉ thay đổi sau pilot có ghi decision registry, không thay dựa trên 2023/2024 performance.

- SHAP/Feature Importance ưu tiên XGBoost và champion model; không cần chạy SHAP nặng cho tất cả 5 phương pháp.

# 4. Công nghệ theo từng tầng

| **Tầng**              | **Công nghệ**                           | **Quy tắc triển khai**                                                                                                      |
|-----------------------|-----------------------------------------|-----------------------------------------------------------------------------------------------------------------------------|
| Raw/IO                | Pandas + PyArrow                        | Đọc từng năm/chunk; schema audit 2016-2024; Parquet partition year/flow; raw read-only.                                     |
| Preprocessing         | scikit-learn Pipeline/ColumnTransformer | Common information set tại T-2h; model-specific transformer; fit trong từng rolling fold, sau đó refit 2016-2022.           |
| ML                    | scikit-learn + XGBoost                  | 5 phương pháp khóa; OOF predictions + 2023 predictions version hóa; 2024 sealed tới final.                                  |
| Tuning                | Optuna                                  | Fixed budget trên rolling folds 2016-2022; aggregate objective; seed/study DB/pruner; không 2023/2024 tuning.               |
| Explainability        | SHAP + built-in feature importance      | Giải thích XGBoost/champion, không dùng để chọn feature trên test.                                                          |
| Flight Chain optional | PyTorch + Pandas                        | Feasibility audit tuần 1-2; GO/NO-GO sớm; nếu GO thì ablation trên 2023, nếu NO thì DROP.                                   |
| Simulation            | Pandas + NumPy + PyYAML                 | Development trên 2023; deterministic synthetic pairing + sensitivity; sampled scales 100/200/300; contact/remote resources. |
| Optimization          | OR-Tools CP-SAT                         | TURN-to-gate; hard constraints; core soft objective = reassign + remote + unassigned + utilization; log bound/gap/runtime.  |
| Metaheuristic         | Python + NumPy                          | SA refinement của time-limited CP-SAT incumbent; cùng total compute budget; hard-feasible neighbors/reject-repair.          |
| Robustness            | NumPy/Pandas                            | Plan robustness + recourse; pilot 20/50 -> final target 500 if feasible; same scenario seeds.                              |
| Dashboard             | Streamlit + Plotly                      | Scheduled/Predicted/Optimized timeline + KPI.                                                                               |
| Quality               | pytest + Git/GitHub                     | Unit/integration/regression tests + reproducible README.                                                                    |

# 5. Data contracts giữa các tầng

| **Artifact**                  | **Schema tối thiểu**                                                                                                                                           |
|-------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Processed inbound ML          | flight_key, year, FL_DATE, T_cutoff, schedule features, proven-safe/lagged weather, ARR_DELAY, y_cls, schema_version                                           |
| Processed outbound simulation | flight_key, FL_DATE, OP_CARRIER, ORIGIN=ATL, DEST, CRS_DEP_TIME và schedule metadata                                                                           |
| Prediction                    | flight_key, A_sched, p_delay_15, predicted_arr_delay_min, model_version                                                                                        |
| Aircraft Turn                 | turn_id, sim_aircraft_id, inbound_flight_key?, outbound_flight_key?, A_sched, A_pred, D_sched?, T_turnaround, B_risk, gate_release, turn_class, scenario_scale |
| Gate                          | gate_id, resource_type=CONTACT/REMOTE, gate_class, availability windows, capacity/config metadata                                                              |
| Assignment                    | turn_id, initial_gate_id, optimized_gate_id, assignment_status=CONTACT/REMOTE/UNASSIGNED, method, objective components, runtime, solver_status, bound_gap      |
| Monte Carlo                   | scenario_id, seed, experiment_mode=PLAN_ROBUSTNESS/RECOURSE, perturbation params, method metrics, assignment summary                                           |

Mọi artifact phải có version/config/seed hoặc manifest liên quan. flight_key dùng để trace một flight record; TURN_ID/SIM_AIRCRAFT_ID chỉ tồn tại trong simulation và không được diễn giải như aircraft registration thật.

# 6. Công thức và quy tắc kỹ thuật cốt lõi

| **Thành phần**                   | **Quy tắc**                                                                                                                                                                                        |
|----------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Nhãn classification              | y_cls = 1 nếu ARR_DELAY >= 15; ngược lại y_cls = 0.                                                                                                                                               |
| Target regression                | y_reg = ARR_DELAY (phút, signed).                                                                                                                                                                  |
| Predicted arrival                | A_pred = A_sched + DeltaT_pred.                                                                                                                                                                    |
| Risk buffer                      | B_risk = f(p_delay); baseline đề xuất: clip(round(B_max \* p_delay), 0, B_max), với p_delay đã calibration. B_max được khóa trước final test và chạy sensitivity trên development data.            |
| Earliest feasible departure      | D_min = A_pred + T_turnaround.                                                                                                                                                                     |
| Predicted/simulated departure    | D_pred = max(D_sched, D_min).                                                                                                                                                                      |
| Gate release - paired turn       | Gate_release = D_pred + B_risk.                                                                                                                                                                    |
| Gate release - unmatched inbound | Gate_release = A_pred + dwell_default + B_risk.                                                                                                                                                    |
| Occupancy                        | Gate occupancy = \[A_pred, Gate_release\].                                                                                                                                                         |
| Nominal occupancy                | Initial schedule dùng A_sched và nominal release trước khi inject predicted delay; reassignment được đo so với initial gate plan.                                                                  |
| Prediction cut-off               | T_cutoff = CRS_DEP_TIME - 2 giờ. Chỉ feature có thông tin khả dụng tại hoặc trước T_cutoff mới được vào X.                                                                                         |
| Simulation guard                 | Regression target gốc vẫn ARR_DELAY signed; nếu predicted DeltaT cực trị gây cửa sổ phi thực tế, simulation dùng clip range đã preregister và báo riêng sensitivity, không sửa ground-truth label. |

- Prediction cut-off cố định cho core experiment: T = CRS_DEP_TIME - 2 giờ. Weather chỉ dùng khi metadata/provenance chứng minh quan sát hoặc forecast tương ứng đã khả dụng tại cut-off; nếu không phải lag hoặc loại.

- Initial gate plan dùng nominal scheduled occupancy. Predicted occupancy được inject sau đó để phát sinh conflict và đo reassignment.

- CONTACT_GATE, REMOTE_STAND và UNASSIGNED là ba trạng thái khác nhau. Remote stand phải có availability/capacity/no-overlap như resource thật trong simulation; UNASSIGNED là failure/slack state với penalty rất cao.

- Core optimization KPI đo gate changes, contact/remote/unassigned, conflicts, utilization và runtime. Generic risk-exposure term không thuộc core objective nếu nó chỉ lặp lại cùng uncertainty đã đưa vào B_risk.

# 7. Cấu trúc repository đề xuất

> project/  
> configs/  
> base.yaml  
> data.yaml  
> models.yaml  
> hpo_budget.yaml  
> simulation.yaml  
> optimization.yaml  
> robustness.yaml  
> data/  
> raw/tabular/2016...2024/  
> raw/chain/2016...2024/ \# optional  
> processed/inbound_atl/  
> processed/outbound_atl/  
> simulation/  
> notebooks/  
> src/  
> data/load_aeolus.py  
> data/schema_audit.py  
> data/preprocessing.py  
> data/leakage_rules.py  
> data/temporal_split.py  
> features/tabular_features.py  
> features/chain_context.py \# optional  
> models/linear_models.py  
> models/random_forest.py  
> models/hist_gradient_boosting.py  
> models/xgboost_models.py  
> models/weighted_ensemble.py  
> models/optuna_tuning.py  
> simulation/turn_generator.py  
> simulation/gate_generator.py  
> optimization/conflict_engine.py  
> optimization/greedy.py  
> optimization/cp_sat.py  
> optimization/simulated_annealing.py  
> evaluation/ml_optimization_utility.py  
> evaluation/monte_carlo.py  
> dashboard/app.py  
> tests/  
> reports/  
> requirements.txt  
> README.md

# 8. Quy tắc preprocessing và chống leakage

- Không đưa DEP_TIME, ARR_TIME, WHEELS_OFF, WHEELS_ON, TAXI_IN, TAXI_OUT, AIR_TIME, ACTUAL_ELAPSED_TIME vào X của dự báo pre-flight.

- Encoder/imputer/scaler/frequency map phải fit riêng trong từng rolling development fold 2016-2022. Sau khi model protocol khóa, refit trên 2016-2022 rồi dùng 2023 cho model selection/downstream development; 2024 chỉ transform/evaluate sau full-system freeze.

- Sau ATL filter, phát hiện constant columns; ORIGIN_INDEX/DEST_INDEX chỉ dùng nếu schema audit chứng minh mapping ổn định xuyên năm. Common information set phải giống nhau, nhưng từng model được phép dùng transformer/encoding phù hợp.

- Không dùng target encoding trực tiếp nếu không có temporal out-of-fold protocol; không để encoding hoặc feature statistics nhìn sang tương lai.

- Flight Chain .pt có label \>15 trong source gốc nhưng core target vẫn >=15 từ Tabular; không tái sử dụng label .pt làm ground truth chính.

# 9. Reproducibility, testing và artifact management

| **Hạng mục**        | **Yêu cầu**                                                                                                                                                                                                            |
|---------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Seed                | Ghi seed cho schema sampling, simulation, Optuna sampler, model random_state, SA và Monte Carlo.                                                                                                                       |
| Config              | YAML cho cut-off, data/model/HPO/simulation/optimization/robustness; không hard-code weight/time window/compute budget quan trọng.                                                                                     |
| Model registry      | model_name, params, feature_version, train years, validation metrics, artifact path.                                                                                                                                   |
| Prediction registry | model_version + flight_key + p_delay_15 + predicted_arr_delay_min.                                                                                                                                                     |
| Tests               | Schema drift, T-2h leakage, split integrity, 2024 access guard, turn pairing uniqueness, CONTACT/REMOTE/UNASSIGNED semantics, conflict verifier, solver hard constraints, equal-compute budget, same-seed Monte Carlo. |
| Reports             | Rolling development reports trước; 2023 model selection/downstream reports; final 2024 chỉ sau system_freeze_manifest và không overwrite.                                                                              |

# 10. Môi trường phần cứng và chiến lược dữ liệu lớn

- Máy cá nhân 16 GB RAM có thể làm việc nếu schema audit/ATL filter theo chunk và lưu Parquet; không load toàn bộ Aeolus 2016-2024 vào một DataFrame. 2024 chỉ được materialize vào final pipeline sau freeze.

- XGBoost/Random Forest/Optuna có thể chạy CPU; HPO phải có fixed trial/time budget và có thể dùng temporal-stratified development subsample cho pilot rồi refit full 2016-2022. GPU là tùy chọn tăng tốc.

- Flight Chain optional .pt chỉ load từng năm/split khi audit; không cần giữ toàn bộ tensor 2016-2024 trong RAM.

- Cache processed features/OOF predictions/2023 predictions theo version. Monte Carlo chạy 20 -> 50 để ước lượng runtime trước khi cam kết final target 500; cache scenario manifest để đảm bảo paired comparison.

# 11. Công nghệ không thuộc core stack

- LightGBM/CatBoost: không đưa vào core vì đã khóa tối đa 5 phương pháp ML; chỉ xem là future work nếu cần.

- TensorFlow/PyTorch training, LSTM/Transformer/GNN: không thuộc core 12 tuần.

- Weather API ngoài Aeolus: không thuộc pipeline chính; weather availability phải được xử lý bằng audit/lag/drop thay vì tự động gọi API.

- Cơ sở dữ liệu/Backend web riêng: chưa cần; Parquet + Streamlit đủ cho prototype khóa luận.

# 12. Checklist đồng bộ công nghệ

- Dữ liệu = Aeolus 2016-2024 tại ATL; schema audit từng năm, không suy diễn từ riêng 2016.

- ML = đúng tối đa 5 phương pháp; T-2h cut-off; rolling development 2016-2022 -> 2023 model selection -> 2024 final end-to-end sau freeze.

- Flight Chain = optional; GO/NO-GO tuần 1-2, ablation chỉ nếu mapping an toàn; PyTorch chỉ đọc/audit.

- Simulation = TURN_ID/SIM_AIRCRAFT_ID synthetic; scenario 100/200/300; pairing/turnaround sensitivity; CONTACT/REMOTE/UNASSIGNED tách biệt.

- Optimization = Greedy -> CP-SAT standalone -> equal-compute Hybrid CP-SAT+SA; không mặc định SA cải thiện CP-SAT.

- Robustness = plan robustness + recourse; pilot 20/50, final target 500 nếu runtime khả thi; cùng scenario seeds; có Schedule-only vs ML vs Oracle experiment.

- Dashboard = Streamlit + Plotly; development 2023 và final holdout 2024 phải hiển thị/phân biệt rõ.

- Claim = giảm tác động delay lên gate operations trên môi trường mô phỏng; không giảm delay thực tế và không đại diện lịch gate/aircraft identity thật của ATL.
