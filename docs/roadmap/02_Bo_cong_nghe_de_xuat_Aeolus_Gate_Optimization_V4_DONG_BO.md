**ỨNG DỤNG HỌC MÁY VÀ LẬP TRÌNH RÀNG BUỘC TRONG DỰ BÁO ĐỘ TRỄ CHUYẾN BAY VÀ TỐI ƯU TÁI PHÂN BỔ CỔNG ĐỖ TÀU BAY**

**BỘ CÔNG NGHỆ ĐỀ XUẤT — BẢN ĐỒNG BỘ V4**

*Tech stack cho Predict -> Simulate -> Optimize -> Evaluate; Dashboard là presentation layer*

| **Phiên bản** | 4.0 — Dual Prediction Architecture |
|---|---|
| **Ngày** | 26/08/2026 |
| **Phạm vi** | 12 tuần — Aeolus 2016–2024 |
| **Quyết định cốt lõi** | Core Arrival no-Weather + Auxiliary Departure point-in-time Weather study |

# 1. Nguyên tắc lựa chọn công nghệ

- Python thống nhất, tái lập được, chạy được trên máy 16 GB RAM bằng
  year/chunk processing; không cần Deep Learning/GNN.
- Runtime contract: **Python >= 3.11**. Baseline hiện được verify trong `.venv`
  với Python 3.11.15; không upgrade package đã PASS nếu chưa có nhu cầu code.
- Data pipeline dùng Pandas/NumPy/PyArrow/Parquet, YAML/JSON manifests và
  SQLite staging khi cần bounded-memory processing. PyArrow và SQLite là thành
  phần thực tế đã hỗ trợ reconstructed Chain full-data PASS.
- Raw Aeolus immutable; external Weather tương lai tách source/version/storage.
- Cả Core Arrival và Auxiliary Departure tuân T-2h. HPO nằm trong rolling folds
  2016–2022; 2023 model selection/downstream development; 2024 sealed final.
- Chỉ Core Arrival output đi vào simulation/optimization.
- Core có tối đa 5 methods; auxiliary Weather không nhân thành một competition
  5 methods khác.
- `requirements.txt` baseline chỉ pin dependency đang được code sử dụng. Future
  ML/optimization/dashboard libraries được thêm theo implementation stage, sau
  compatibility test, không cài chỉ để khớp roadmap.

# Các quyết định thống nhất dùng xuyên suốt

| **Hạng mục** | **Quyết định V4** |
|---|---|
| Core task | Arrival classification + signed regression, inbound `DEST=ATL`, no Weather. |
| Auxiliary task | Departure classification, outbound `ORIGIN=ATL`, DEP-A vs DEP-B Weather. |
| Cut-off | `CRS_DEP_TIME - 2h` cho cả hai task. |
| Raw Weather | E002 `INSUFFICIENT_EVIDENCE`, `DROP` cho cả hai task. |
| External Weather | Optional auxiliary point-in-time source; provider `TBD/AUDIT_REQUIRED`; disabled. |
| Raw Chain | Original `.pt` `FINAL — NO_GO`; PyTorch loading/reverse engineering không thuộc current workflow. |
| Reconstructed Chain | `schedule_chain_v1` GO_FOR_ABLATION; Pandas/PyArrow/SQLite artifact, not physical rotation. |
| Reconstructed feature policy | Week 3B `COMPLETED_WITH_BLOCKED_ML_BRANCH`: E006 has `KEEP_SAFE=[]`; diagnostic materialization allowed but not executed; no feature artifact; ARR-B disabled. |
| Temporal | 2016–2022 rolling; 2023 selection/development; 2024 sealed final. |
| Optimization | Google OR-Tools CP-SAT + Python/NumPy Simulated Annealing; equal total compute. |
| Visualization | Streamlit + Plotly; Matplotlib cho static reporting. |
| Reproducibility | pytest, Git/GitHub, versioned configs/manifests/logs; không commit/push trong migration. |

# 2. Tech stack chính thức theo lớp

| **Lớp** | **Công nghệ** | **Vai trò và trạng thái** |
|---|---|---|
| Runtime/language | Python >=3.11 | Main runtime; verified baseline 3.11.15. |
| Data engineering | Pandas, NumPy | Chunk/year transforms, joins, diagnostics, simulation tables. |
| Columnar IO | PyArrow, Parquet | Partitioned canonical/flow/derived artifacts; bounded-memory reads/writes. |
| Staging | SQLite | Disk-backed deterministic staging cho reconstruction lớn khi cần. |
| Contracts | PyYAML, JSON | Config, schema, temporal, experiment và evidence manifests. |
| Core ML | scikit-learn | Logistic/Ridge, RF, HGB, Pipeline/ColumnTransformer, metrics/calibration. |
| Boosting | XGBoost | Core method 4 và controlled auxiliary Departure classifier. |
| HPO | Optuna | Fixed-budget rolling-fold search trên 2016–2022. |
| Explainability | SHAP | XGBoost/champion analysis sau development, không select từ 2024. |
| Weather | Provider TBD | Optional external point-in-time source cho auxiliary only; audit required. |
| Optimization | Google OR-Tools | CP-SAT standalone/hybrid seed, status/objective/bound/gap. |
| Metaheuristic | Python + NumPy | SA refinement với hard-feasible/reject-repair neighbors. |
| Simulation | NumPy + Pandas | Synthetic Turns, gates, perturbations, Monte Carlo summaries. |
| Visualization | Streamlit, Plotly | Interactive dashboard/timeline/KPI. |
| Static reporting | Matplotlib | Figures cho reports/thesis khi cần; Seaborn không bắt buộc. |
| Quality | pytest | Unit/integration/regression/contract tests. |
| Engineering | Git, GitHub | Version control/review; versioned configs/manifests/experiment logs. |

Version floor trong roadmap là định hướng cho future stages. Mỗi dependency
chỉ được pin khi module tương ứng được implement và candidate-tested trên
Python 3.11; package baseline đang verified không được upgrade tùy tiện.

# 3. Bộ mô hình Machine Learning

## 3.1 Core Arrival — tối đa 5 phương pháp

| **#** | **Classification** | **Regression** | **Công nghệ** | **Tuning** |
|---|---|---|---|---|
| 1 | Logistic Regression | Ridge Regression | scikit-learn | Fold-safe scaling/one-hot; tuning nhẹ 2016–2022 |
| 2 | Random Forest Classifier | Random Forest Regressor | scikit-learn | Fixed-budget Optuna rolling folds |
| 3 | HistGradientBoosting Classifier | HistGradientBoosting Regressor | scikit-learn | Fixed-budget Optuna rolling folds |
| 4 | XGBoost Classifier | XGBoost Regressor | XGBoost | Fixed-budget Optuna rolling folds |
| 5 | Weighted probability ensemble | Weighted signed-delay ensemble | NumPy/scikit-learn metrics | Weights từ OOF 2016–2022 |

Targets: `y_arr_cls = 1[ARR_DELAY >= 15]` và
`y_arr_reg = ARR_DELAY` signed. Arrival input không có Weather và không consume
auxiliary output. Weighted Ensemble không mặc định là champion; SHAP ưu tiên
XGBoost/champion, không chạy nặng cho mọi method nếu không cần.

## 3.2 Auxiliary Departure — controlled ablation

| **Arm** | **Predictor family** | **Classifier** |
|---|---|---|
| DEP-A | Schedule/Calendar/Carrier/Route | XGBoost Classifier |
| DEP-B | Same as DEP-A + audited point-in-time Weather | Same XGBoost config |

Target: `y_dep_cls = 1[DEP_DELAY >= 15]`. Không Departure regression. Target
rows, preprocessing ngoài Weather, folds, seed, HPO budget và metrics phải
giống nhau. Logistic Regression có thể dùng như optional sanity baseline,
nhưng không biến auxiliary thành thêm 5 core methods.

Week 6 là execution gate cho cả ARR-A/ARR-B và DEP-A/DEP-B. ARR ablation chỉ
dùng reconstructed features đã được approve `KEEP_SAFE` qua D026 và normal
Arrival leakage gate; DEP Weather ablation chỉ chạy khi provenance PASS, nếu
không ghi `BLOCKED_NOT_CORE_FAILURE` và Core Arrival vẫn freeze.

# 4. Công nghệ theo từng tầng

| **Tầng** | **Công nghệ** | **Quy tắc triển khai V4** |
|---|---|---|
| Canonical Aeolus IO | Pandas + PyArrow + Parquet | Existing Week 1–2 partitions/manifests giữ nguyên; không regenerate. |
| Reconstruction evidence | Pandas + PyArrow + SQLite | Existing `schedule_chain_v1`; no rerun; max context 6 không truncate membership. |
| Core preprocessing | scikit-learn Pipeline/ColumnTransformer | Task `arrival_core`; fit trong training fold; no Weather/actual outcomes. |
| Reconstructed features | Pandas/NumPy + versioned feature availability policy/audit | 3B closed without execution: 3B.1 skipped for ML and optional 3B.3 diagnostic materialization skipped; any future diagnostic output must remain `ML_ADMISSIBLE=false`. |
| Auxiliary Weather contract | JSON + pure Python validation; future provider client remains unimplemented | Week 3C completed I004/W1–W15 contract and synthetic tests; no download/join; provider TBD, `AUDIT_REQUIRED`, disabled. |
| Core ML | scikit-learn + XGBoost | Five-method cap, OOF 2016–2022, 2023 selection, 2024 sealed. |
| Auxiliary ML | XGBoost | DEP-A/DEP-B controlled arms only after provenance PASS. |
| Tuning | Optuna | Fixed budget; never 2023/2024 HPO. |
| Explainability | SHAP | Core XGBoost/champion; no target/test-driven feature selection. |
| Simulation | Pandas + NumPy + PyYAML | 2023 synthetic pairing/gates/sensitivity; only Core Arrival predictions. |
| Optimization | OR-Tools CP-SAT | Shared verifier/objective; CONTACT/REMOTE/UNASSIGNED distinct. |
| Metaheuristic | Python + NumPy | SA time-limited incumbent refinement under equal total compute. |
| Robustness | NumPy + Pandas | Plan robustness + recourse; pilots 20/50; comparable seeds. |
| Dashboard | Streamlit + Plotly | Read evaluated artifacts; distinguish 2023 development/2024 final. |
| Quality | pytest + compile/import checks | Task-aware leakage, holdout, schema, solver, fairness, artifact tests. |

# 5. Data contracts giữa các tầng

| **Artifact** | **Schema/contract tối thiểu** |
|---|---|
| Core Arrival input | `flight_key`, scheduled/calendar/carrier/route fields, optional approved reconstructed features, `ARR_DELAY`, `y_arr_cls`, `y_arr_reg`, versions; no Weather. |
| Reconstructed feature join | Target `flight_key`, feature/policy version, structural fields and per-feature availability status; `chain_id`/source metadata traceability only. Non-approved materialization records `ML_ADMISSIBLE=false`. |
| Auxiliary Departure input | Same target rows for DEP-A/DEP-B, schedule fields, `DEP_DELAY`, `y_dep_cls`; Weather columns only in audited DEP-B. |
| Point-in-time Weather | Provider/product/version; forecast/observation/reanalysis class; issue/publication/available/valid times; UTC/location/variable provenance; deterministic join metadata and DEP row parity. |
| Core prediction | `flight_key`, `A_sched`, `p_arr_delay_15`, `predicted_arr_delay_min`, model/feature version. |
| Auxiliary prediction | `flight_key`, `p_dep_delay_15`, model/Weather versions; research-only, no optimizer consumer. |
| Aircraft Turn | Synthetic IDs, inbound/outbound keys, schedule, Core Arrival `A_pred`, turnaround, risk buffer, release, scenario version. |
| Gate/assignment | CONTACT/REMOTE resources, UNASSIGNED state, initial/optimized gate, objective components, runtime/status/gap. |
| Monte Carlo | Scenario/seed/mode, perturbation version, method metrics, failures/infeasibility retained. |

Mọi artifact có config/version/seed/manifest. `flight_key` và `chain_id` không
phải aircraft ID. External Weather không được viết vào canonical Aeolus schema.

# 6. Prediction, leakage và Weather rules

- API leakage nhận `task="arrival_core"` hoặc
  `task="departure_auxiliary"`; default Arrival cho caller cũ.
- Unknown task/field/external Weather fail closed. Conditional airport
  index/coordinate fields cần explicit review; integer index không phải
  continuous measure.
- Arrival: `ARR_DELAY`/labels TARGET; `DEP_DELAY`/actual outcomes forbidden;
  inbound destination constants drop; Weather forbidden.
- Departure: `DEP_DELAY`/label TARGET; `ARR_DELAY`/Arrival labels future
  outcome; outbound origin constants drop; raw Weather vẫn forbidden.
- `weather_point_in_time_v1` chỉ được enable sau khi chứng minh
  `information_available_time <= prediction_cutoff` và pass all audit gates.
- DEP-A/DEP-B giữ exact row parity; missing Weather không được làm mất target
  rows hay tạo selection bias.

# 7. Cấu trúc repository/công nghệ đề xuất

```text
configs/base.yaml
configs/reconstructed_chain_feature_policy.yaml # V1 fail-closed family/feature statuses
artifacts/manifests/reconstructed_chain_feature_availability_audit_v1.json # E006
artifacts/manifests/weather_point_in_time_contract_v1.json # Week 3C template, not data
data/raw/...                              # immutable Aeolus
data/external/weather/...                 # future separate source, not created now
data/processed/flight_chain_reconstructed_v1/  # existing PASS artifact
src/data/leakage_rules.py                 # task-aware baseline contract
src/features/chain_feature_policy.py      # availability policy validation only
src/data/preprocessing.py                 # Week 3A implemented; transformers/IO only
src/data/weather_contract.py              # Week 3C pure contract validation only
src/features/tabular_features.py          # Week 3A implemented; labels/base features
src/features/reconstructed_chain_features.py # planned only; not created because E006 approved no ML-safe features
data/processed/reconstructed_chain_features_v1/ # planned only; not created
src/data/weather_point_in_time.py         # future, only after audit/authorization
src/models/...                            # Weeks 4–6
src/simulation/...                        # Week 7+
src/optimization/...                      # Week 8+
src/evaluation/...                        # Week 8+
dashboard/app.py                          # Week 12
```

Week 3B đã đóng `COMPLETED_WITH_BLOCKED_ML_BRANCH` ngày 26/08/2026. Feature
code/artifact ở trên chỉ là planned historical extension point và chưa được tạo.
Weather source/client/data, model, simulation và optimization vẫn chỉ là
planned. Week 3C chỉ tạo contract/template và pure synthetic validation; không
tạo Weather feature hay chọn provider.

# 8. Flight Chain technology boundary

Original raw `.pt` là read-only `FINAL — NO_GO`; PyTorch không còn là
dependency của core/ablation và raw tensors không được load lại. Reconstructed
Schedule Chain là canonical-Tabular-derived artifact đã dùng Pandas, PyArrow,
Parquet và SQLite staging để đạt bounded-memory full-data reconstruction.

Full reconstructed membership phục vụ provenance, deterministic structural
analysis và audit; nó không phải point-in-time schedule snapshot. Dataset-level
`GO_FOR_ABLATION` không tự động approve `chain_length`, future membership hay
bất kỳ derived predictor nào. D026 và
`reconstructed_chain_feature_availability_v1` là gate riêng trước normal
Arrival leakage contract.

E006 đã chạy semantic/provenance gate này và không tìm thấy schedule
publication/version/snapshot evidence tại T-2h. Kết quả `KEEP_SAFE=[]`, 7
local/past features `REVIEW_REQUIRED`, 11 future/full-chain features
`BLOCKED_UNTIL_PROVEN`, 4 identifiers `IDENTIFIER_ONLY`. Chain ML branch là
`BLOCKED_PENDING_NEW_EVIDENCE`.

Week 3B không đọc row-level partitions và không tạo feature artifact. 3B.1 được
đóng `SKIPPED_NOT_REQUIRED_FOR_ML`; 3B.3 được đóng
`SKIPPED_OPTIONAL_DIAGNOSTIC`. Candidate chưa approve vẫn có thể được
materialize cho một audit tương lai nếu manifest ghi `ML_ADMISSIBLE=false`,
nhưng closure hiện tại không thực thi việc đó. Không thay
`flight_key_v1`, `schedule_chain_v1`,
`canonical_datetime_storage_amendment_v1`, group/order semantics hoặc
production partitions; ARR-B vẫn disabled và không thể chạy ở Week 6 khi
`KEEP_SAFE` còn rỗng.

## 8.1 Week 3A dependency activation preflight

Ngay khi Week 3A thực sự bắt đầu:

1. Kiểm tra scikit-learn đã được cài trong verified `.venv` hay chưa.
2. Xác định candidate version tương thích Python 3.11.
3. Candidate-test version đó trong current environment.
4. Chỉ pin khi Week 3A code thực sự import/use scikit-learn.
5. Không upgrade NumPy, Pandas hoặc PyArrow nếu không cần.
6. Chạy full regression suite sau mọi dependency change.

Baseline hardening trước đó không cài dependency hay implement Week 3A. Khi
Week 3A được thực thi ngày 26/08/2026, preflight đã PASS: scikit-learn 1.9.0
được pin sau candidate import test trên Python 3.11.15; NumPy 2.2.6, Pandas
2.3.3 và PyArrow 25.0.1 không bị upgrade. Full regression suite vẫn PASS.

## 8.2 Week 3A implementation status

Week 3A hiện **COMPLETED** với một common Schedule/Calendar/Carrier/Route
information set, linear và tree/boosting transformer families, train-fold-only
imputation/scaling/category/frequency state, bounded year/column/batch IO và
hai versioned manifests. `CRS_ARR_TIME` không được dùng để suy scheduled
duration hay overnight rollover; `CRS_ELAPSED_TIME` là scheduled-duration
predictor đã audit. Không có model estimator, Chain feature, Weather feature,
2023 fit hay row-level 2024 access. Week 3B đã đóng fail-closed; Week 3C đã
hoàn tất provider-agnostic contract và Week 3 đã đóng. Core Arrival hiện
`READY_FOR_WEEK_4 = YES`; Weather provenance vẫn `AUDIT_REQUIRED`/disabled.

# 9. Reproducibility, testing và artifact management

| **Hạng mục** | **Yêu cầu** |
|---|---|
| Runtime | Record Python/package/SQLite versions; candidate-test before pin/upgrade. |
| Config | Task/Weather/Chain/temporal roles in YAML; no conflicting duplicate source of truth. |
| Manifests | Version schema, folds, features, source provenance, joins, models, predictions, scenarios, freeze/final runs. |
| Experiment log | Record protocol amendments and experiments; never invent results. |
| Tests | Config V4, task leakage, raw Weather DROP, external Weather disabled, Chain dataset/feature split status, fail-closed feature policy, 2024 guard. |
| ML tests | Fold isolation, labels, row parity, preprocessing fit scope, no 2023/2024 HPO. |
| Downstream tests | Arrival-only input, gate states, verifier, equal-compute, same-seed robustness. |
| Git | Preserve user changes; do not commit raw/generated data; no commit/push in baseline migration. |

# 10. Môi trường phần cứng và dữ liệu lớn

- 16 GB RAM: year/chunk/PyArrow/Parquet/SQLite; không load full 2016–2024.
- Existing reconstruction artifact đã hoàn tất; không rerun để “kiểm tra” V4.
- XGBoost/RF/Optuna có thể CPU với fixed budget; GPU optional, không đổi
  research method.
- Cache versioned OOF/2023 predictions và scenario manifests khi Weeks 4–10
  thực sự chạy.
- 2024 không được transform/evaluate cho development; metadata manifests được
  giữ để consistency only.

# 11. Công nghệ không thuộc core/current baseline

- LightGBM/CatBoost không là method core thứ 6.
- TensorFlow/PyTorch training, LSTM/Transformer/GNN không thuộc 12-week core.
- Provider Weather cụ thể chưa được chọn; Meteostat không được gọi là forecast
  provider hoặc safe source khi chưa chứng minh issue/availability provenance.
- Weather API/download/join không thuộc baseline migration và không bắt buộc
  để hoàn tất Core Arrival Week 3.
- Backend/database web riêng chưa cần; SQLite chỉ staging/audit, Parquet là
  primary artifact format, Streamlit là presentation layer.

# 12. Checklist đồng bộ công nghệ

- Runtime Python >=3.11; baseline verified 3.11.15.
- Data engineering ghi rõ Pandas, NumPy, PyArrow, Parquet, SQLite, YAML, JSON.
- Core Arrival đúng 5-method cap và no Weather.
- Auxiliary Departure dùng controlled XGBoost; Weather audit-gated, regression
  disabled, no optimizer input.
- Raw Weather DROP; external source TBD/AUDIT_REQUIRED, version riêng.
- Raw Chain FINAL_NO_GO; reconstructed Chain GO_FOR_ABLATION, existing artifact
  không thay đổi.
- Reconstructed feature layer dùng Pandas/NumPy **và** availability policy;
  E006 có `KEEP_SAFE=[]`, full membership không tự động safe, ARR-B không
  auto-enable.
- Optimization OR-Tools CP-SAT + Python/NumPy SA; equal total compute.
- Simulation NumPy/Pandas; visualization Streamlit/Plotly/Matplotlib.
- Engineering pytest/Git/GitHub/versioned configs/manifests/logs.
- `requirements.txt` không bị phình bởi future stack trước khi code sử dụng.
- 2024 sealed, access guard giữ nguyên; only Core Arrival feeds downstream.
