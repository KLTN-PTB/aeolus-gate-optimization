**ỨNG DỤNG HỌC MÁY VÀ LẬP TRÌNH RÀNG BUỘC TRONG DỰ BÁO ĐỘ TRỄ CHUYẾN BAY VÀ TỐI ƯU TÁI PHÂN BỔ CỔNG ĐỖ TÀU BAY**

**ROADMAP TRIỂN KHAI 12 TUẦN — BẢN ĐỒNG BỘ V4**

*Bản thiết kế cấp cao theo V4 Dual Prediction Architecture*

| **Phiên bản** | 4.0 — Dual Prediction Architecture |
|---|---|
| **Ngày** | 26/08/2026 |
| **Phạm vi** | 12 tuần — Aeolus 2016–2024 |
| **Quyết định cốt lõi** | Core Arrival không Weather + Auxiliary Departure Weather study + Synthetic Aircraft Turn |

# 1. Mục tiêu của roadmap

Roadmap V4 triển khai kiến trúc **Predict -> Simulate -> Optimize -> Evaluate**;
Dashboard là presentation layer. Core research task dự báo Arrival Delay cho
inbound `DEST=ATL`; auxiliary research task đánh giá Weather point-in-time cho
Departure Delay trên outbound `ORIGIN=ATL`. Hai task dùng chung cut-off
`T = CRS_DEP_TIME - 2 giờ`, nhưng chỉ Core Arrival prediction đi vào gate
simulation/optimization.

Week 1–2 đã **COMPLETED** theo protocol trước đó. Toàn bộ evidence schema,
canonical data, temporal manifests, leakage/Weather audit, raw Flight Chain
`FINAL — NO_GO`, và reconstructed `schedule_chain_v1`
`FULL_DATA_PASS / GO_FOR_ABLATION` được giữ nguyên. Architecture Amendment V4
được chốt sau Week 2, không dựa trên model result và không dùng 2024 để ra
quyết định. Week 3A đã **COMPLETED**, Week 3B đã
**COMPLETED_WITH_BLOCKED_ML_BRANCH**, và Week 3C đã **COMPLETED** ngày
26/08/2026. Week 3 đã đóng; chưa có model nào được train và Core Arrival hiện
`READY_FOR_WEEK_4 = YES`.

Nguyên tắc khóa phạm vi: raw Aeolus read-only; không regenerate artifact đã
PASS; không suy luận aircraft identity; không dùng 2024 cho development;
Weather chỉ được nghiên cứu trong auxiliary Departure nếu provenance
point-in-time PASS; CP-SAT và CP-SAT+SA so sánh equal total compute; optimizer
không được diễn giải là làm giảm flight delay thực tế.

# Các quyết định thống nhất dùng xuyên suốt

| **Hạng mục** | **Quyết định V4** |
|---|---|
| Phạm vi dữ liệu | Aeolus 2016–2024; canonical/schema evidence Week 1–2 giữ nguyên; xử lý year/chunk, raw immutable. |
| Core ML | Arrival Delay trên inbound `DEST=ATL`: classification `y_arr_cls = 1[ARR_DELAY >= 15]` và regression `y_arr_reg = ARR_DELAY` signed. |
| Auxiliary ML | Departure Delay trên outbound `ORIGIN=ATL`: classification `y_dep_cls = 1[DEP_DELAY >= 15]`; không Departure regression. |
| Prediction cut-off | Cả hai task: `T_prediction = CRS_DEP_TIME - 2 hours`; feature phải available tại hoặc trước cut-off. |
| Arrival Weather | **NO Weather**; không dùng raw Aeolus Weather, external Weather hoặc predicted Departure delay. |
| Departure Weather | DEP-A Schedule-only so với DEP-B Schedule + audited point-in-time Weather; chỉ Weather family khác nhau. |
| Raw Aeolus Weather | Sáu `O_*`/`D_*` fields giữ E002 `INSUFFICIENT_EVIDENCE`, `DROP_FROM_PREDICTORS` cho cả hai task; không gọi forecast, không heuristic lag. |
| External Weather | `weather_point_in_time_v1`, riêng version/provenance; hiện `AUDIT_REQUIRED`, disabled; không block Core Arrival. |
| Raw Flight Chain `.pt` | E003 **`FINAL — NO_GO`**; read-only; không core, không ablation, không reverse-engineer. |
| Reconstructed Schedule Chain | E005 **`FULL_DATA_PASS / GO_FOR_ABLATION`**; schedule/service-number context, optional, disabled by default, outside core. |
| Reconstructed feature availability | D026 + E006: audit đã `COMPLETED`, không có schedule snapshot/publication evidence, `KEEP_SAFE=[]`; 7 local/past `REVIEW_REQUIRED`, 11 future/full-chain `BLOCKED_UNTIL_PROVEN`, identifiers `IDENTIFIER_ONLY`; ARR-B disabled. |
| Temporal protocol | Rolling development 2016–2022; 2023 model selection/controlled ablation/downstream development; 2024 SEALED FINAL HOLDOUT. |
| Core methods | Tối đa 5: Logistic/Ridge, Random Forest, HistGradientBoosting, XGBoost, Weighted Ensemble. |
| Auxiliary method | Controlled XGBoost Classifier cho DEP-A/DEP-B; Logistic optional sanity baseline, không full 5-model competition. |
| Downstream source | Chỉ Core Arrival prediction feed Synthetic Turn -> Gate Simulation -> Greedy -> CP-SAT -> CP-SAT+SA -> Monte Carlo. |
| Aircraft Turn | `TURN_ID` + `SIM_AIRCRAFT_ID` synthetic; không tạo/giả lập `TAIL_NUM`. |
| Gate states | CONTACT_GATE, REMOTE_STAND, UNASSIGNED tách biệt. |
| Optimization | Greedy -> CP-SAT standalone -> equal-compute CP-SAT+SA; SA chỉ refinement incumbent. |
| Robustness | Plan robustness và recourse tách biệt; pilot 20 -> 50; final target 500 nếu runtime khả thi. |
| Claim | Tối ưu tác động delay lên gate operations mô phỏng; không claim giảm delay thật hoặc vận hành gate thật ATL. |

# 2. Kiến trúc tổng thể

```text
                         AEOLUS TABULAR
                              |
              +---------------+---------------+
              |                               |
              v                               v
     CORE ARRIVAL MODEL             AUXILIARY DEPARTURE MODEL
       inbound DEST=ATL               outbound ORIGIN=ATL
 Schedule/Calendar/Carrier/Route    Schedule/Calendar/Carrier/Route
 Optional Reconstructed Chain      Point-in-time Weather (audit-gated)
              |                               |
     ARR classification+regression       DEP classification
              |
              v
 Synthetic Turn -> Gate Simulation -> Greedy -> CP-SAT -> CP-SAT+SA
              -> Monte Carlo -> Evaluate -> Dashboard
```

| **Tầng** | **Nội dung** | **Đầu ra chính** |
|---|---|---|
| 1. Data | Canonical Aeolus 2016–2024, ATL flows, preserved manifests; external Weather separate | Versioned source/flow contracts |
| 2. Core preprocessing | Arrival labels, task-aware leakage, model-specific transformers | Arrival feature manifest/folds |
| 3. Optional Chain features | Week 3B closed without derivation/materialization: audit/status gates complete, optional execution skipped | `KEEP_SAFE=[]`; no feature artifact; ARR-B/Chain ML blocked pending new evidence |
| 4. Auxiliary preparation | Completed provider-agnostic point-in-time Weather source/join/audit contract | I004 + W1–W15 template; provider TBD, `AUDIT_REQUIRED`, disabled; no dataset |
| 5. Core ML | Four base methods + Weighted Ensemble | Arrival probability and signed delay |
| 6. Controlled ablations | ARR-A/ARR-B; DEP-A/DEP-B only if Weather provenance PASS | KEEP/DROP or blocked limitation |
| 7. Simulation | Synthetic Aircraft Turn, contact/remote resources, nominal/predicted occupancy | Scenarios and initial plan |
| 8. Optimization | Greedy, CP-SAT, equal-compute CP-SAT+SA | Feasible assignments and KPIs |
| 9. Robustness/final | Plan robustness, recourse, Monte Carlo, sealed 2024 | Final end-to-end evidence |
| 10. Presentation | Streamlit/Plotly | Dashboard over evaluated artifacts |

# 3. Chiến lược dữ liệu và Machine Learning

## 3.1 Core Arrival

- Target rows: inbound `DEST=ATL`.
- Labels: `y_arr_cls` và `y_arr_reg`; regression giữ signed minutes.
- Feature families: Schedule, Calendar, Carrier, Route, safe scheduled/context.
- Cấm: Weather, `DEP_DELAY`, predicted Departure delay, actual `DEP_TIME`/
  `ARR_TIME`, taxi/wheels/air-time/actual elapsed và mọi realized outcome.
- Optional ARR-B chỉ dùng features derived từ `schedule_chain_v1` đã được
  approve `KEEP_SAFE` qua D026 và normal Arrival leakage review; identifiers
  chỉ join/trace/audit, không predictor.

Core Arrival giữ tối đa 5 phương pháp:

| **#** | **Classification** | **Regression** | **Vai trò** |
|---|---|---|---|
| 1 | Logistic Regression | Ridge Regression | Linear sanity/interpretable baseline |
| 2 | Random Forest Classifier | Random Forest Regressor | Bagged tree baseline |
| 3 | HistGradientBoosting Classifier | HistGradientBoosting Regressor | Efficient boosting baseline |
| 4 | XGBoost Classifier | XGBoost Regressor | Strong boosting + SHAP |
| 5 | Weighted probability ensemble | Weighted signed-delay ensemble | OOF-weighted comparison |

## 3.2 Auxiliary Departure Weather experiment

Target rows là outbound `ORIGIN=ATL`; target duy nhất `DEP_DELAY >= 15`.
DEP-A và DEP-B phải có cùng target rows, temporal folds, non-Weather
preprocessing, model/config, random seed, HPO budget và metrics. Chỉ Weather
feature family thay đổi. XGBoost Classifier là controlled architecture mặc
định; Logistic Regression chỉ optional sanity baseline.

DEP-B chỉ được chạy khi `POINT_IN_TIME_WEATHER_PROVENANCE = PASS`. Nếu chưa
PASS, ghi `AUXILIARY_WEATHER = BLOCKED_NOT_CORE_FAILURE` và tiếp tục Week 7.
Auxiliary predictions không được join vào Arrival features hoặc optimizer.

## 3.3 Flight Chain

Raw `.pt` không được dùng. Reconstructed `schedule_chain_v1` đã PASS full
2016–2023 và chỉ được dùng cho controlled Arrival ablation. Không truncate
membership về 6; `max_context_length=6` không thay reconstruction. Candidate
structural features được định nghĩa ở Detailed Roadmap Week 3B.

`GO_FOR_ABLATION` là dataset-level decision, không phải blanket predictor
approval. Week 3B.0 `CHAIN_FEATURE_POINT_IN_TIME_AVAILABILITY_AUDIT` đã hoàn
tất: không có schedule publication/version/snapshot evidence, nên
`KEEP_SAFE=[]`; 7 target/local hoặc past-context features giữ
`REVIEW_REQUIRED`, `is_single_leg_chain` cùng 10 future/full-chain features giữ
`BLOCKED_UNTIL_PROVEN`, identifiers là `IDENTIFIER_ONLY`. Week 3B closure ghi:
3B.0 `COMPLETED_PASS`; 3B.1 `SKIPPED_NOT_REQUIRED_FOR_ML`; 3B.2
`COMPLETED_THROUGH_E006`; 3B.3 `SKIPPED_OPTIONAL_DIAGNOSTIC`; 3B.4
`COMPLETED_PASS`. Diagnostic materialization được phép về policy nhưng không
thực thi vì không làm thay đổi admissibility. Chỉ feature được promote
registry-first sau evidence mới mới có thể qua normal Arrival leakage contract.
Full reconstructed membership vẫn được giữ nguyên.

# 4. Quy tắc Synthetic Aircraft Turn và Gate Occupancy

Downstream V3 được giữ nguyên, nhưng nguồn prediction được khóa rõ là Core
Arrival.

| **Quy tắc** | **Định nghĩa V4** |
|---|---|
| Arrival class | `y_arr_cls = 1[ARR_DELAY >= 15]` |
| Arrival regression | `y_arr_reg = ARR_DELAY` signed |
| Predicted arrival | `A_pred = A_sched + DeltaT_arr_pred` |
| Risk buffer | `B_risk = f(p_arr_delay)` từ Core Arrival probability đã calibration |
| Earliest departure | `D_min = A_pred + T_turnaround` |
| Simulated departure | `D_pred = max(D_sched, D_min)` |
| Paired release | `Gate_release = D_pred + B_risk` |
| Unmatched inbound | `Gate_release = A_pred + dwell_default + B_risk` |
| Occupancy | `[A_pred, Gate_release]` |
| Auxiliary boundary | `p_dep_delay` và Weather không xuất hiện trong các công thức downstream V4 |

Nominal gate plan dùng schedule trước khi inject Arrival prediction.
Reassignment đo so với `initial_gate_id`. CONTACT/REMOTE/UNASSIGNED có
constraints, penalty, và KPI riêng; không phá hard compatibility để ép feasible.

# 5. Roadmap 12 tuần

| **Tuần** | **Trạng thái / trọng tâm V4** | **Mục tiêu** | **Deliverable chính** |
|---|---|---|---|
| 1 | **COMPLETED** — scope/audit baseline | Preserve T-2h, registry, inventory, guards | Existing Week-1 evidence unchanged |
| 2 | **COMPLETED** — schema/leakage/Weather/raw Chain gate | Preserve canonical/temporal evidence, E002 DROP, E003 NO_GO | Existing Week-2 artifacts unchanged |
| Amendment | **COMPLETED 26/08/2026** — V4 baseline migration | Separate Core Arrival and Auxiliary Departure; retain E005 reconstructed Chain | V4 config/rules/tests/docs; no ML/FE |
| 3A | **COMPLETED 26/08/2026** — Core Arrival preprocessing | Activated scikit-learn 1.9.0; exact labels, missing/categorical/outlier rules, fold-safe transformers, bounded validation | `feature_manifest_arrival_v1`, transformer registry, tests; no model |
| 3B | **COMPLETED_WITH_BLOCKED_ML_BRANCH 26/08/2026** | Close fail-closed after E006; no derivation/materialization needed | 3B.0/3B.2/3B.4 complete; 3B.1/3B.3 skipped; `KEEP_SAFE=[]`; no feature artifact |
| 3C | **COMPLETED** — auxiliary Weather contract preparation | Provider-agnostic source/timezone/location/variable specification, availability-first join, W1–W15 gates and exact DEP row parity | `weather_point_in_time_contract_v1`; provider TBD, `AUDIT_REQUIRED`, disabled; no data/API/join/model |
| 4 | Pending — three Core Arrival baselines | Logistic/Ridge, RF, HGB on rolling 2016–2022 | OOF Arrival predictions/report |
| 5 | Pending — Core XGBoost + fixed Optuna | XGBoost; HPO only inside 2016–2022 | Studies/manifest/OOF predictions |
| 6 | Pending — ensemble, 2023 selection, SHAP, ablations | ARR Chain ablation; DEP Weather only if provenance PASS | ML freeze; KEEP/DROP/blocked decisions |
| 7 | Pending — Synthetic Turn/gate simulation | Use only frozen Core Arrival predictions | 2023 scenarios and initial plan |
| 8 | Pending — conflicts, Greedy, CP-SAT | Schedule vs Arrival ML vs Oracle utility | Solver/utility report |
| 9 | Pending — CP-SAT vs CP-SAT+SA | Equal total compute, scalability 100/200/300 | Comparison/scalability report |
| 10 | Pending — robustness and freeze | Plan robustness, recourse, pilots 20/50, freeze | `system_freeze_manifest` |
| 11 | Pending — sealed 2024 final | One frozen end-to-end evaluation, no tuning | Final results/manifests |
| 12 | Pending — dashboard/thesis/demo | Present evaluated artifacts and reproducibility | Streamlit/Plotly, thesis/slides/demo |

# 6. Các mốc kiểm soát

| **Mốc** | **Điều kiện đạt** |
|---|---|
| M1 — Week 2 | **PASS/COMPLETED**: canonical/schema/temporal/leakage evidence; raw Weather DROP; raw Chain NO_GO. |
| V4 baseline | Task-aware config/rules/tests/docs pass; reconstructed Chain remains optional; 2024 sealed; no artifact regeneration. |
| M2 — Week 6 | Core 5-method comparison; 2023 selection; current E006 outcome blocks ARR-B because `KEEP_SAFE=[]` unless new registry-first evidence changes the policy; DEP Weather either audited experiment or explicit blocked limitation; 2024 closed. |
| M3 — Week 7 | Synthetic turns/gates driven only by Core Arrival; sensitivity complete. |
| M4 — Week 9 | Greedy/CP-SAT/Hybrid share verifier/objective; equal-compute and scalability complete. |
| M5 — Week 10 | Robustness pilots and full-system freeze before 2024. |
| M6 — Week 11 | Frozen final 2024 end-to-end evaluation, no retuning. |
| M7 — Week 12 | Dashboard/reproducibility/thesis/slide consistent with V4 claim boundaries. |

# 7. Rủi ro chính và kiểm soát

| **Rủi ro** | **Kiểm soát** |
|---|---|
| Arrival bị Weather ảnh hưởng gián tiếp | Không Weather và không `P(departure_delay)` trong Arrival; task-aware leakage tests. |
| Raw Weather bị gọi nhầm forecast | E002 giữ `INSUFFICIENT_EVIDENCE/DROP`; external source version riêng. |
| External Weather look-ahead | Audit issue/publication/valid/availability time, timezone, location, join; fail closed. |
| Weather block core | Weather failure chỉ block DEP-B; Arrival/Week 7 tiếp tục. |
| Raw/reconstructed Chain nhập nhằng | Raw `.pt` FINAL_NO_GO; reconstructed schedule context GO_FOR_ABLATION; tên/status/config riêng. |
| Full membership bị hiểu nhầm là feature-safe | D026 + versioned availability policy; future/full-chain features fail closed; `GO_FOR_ABLATION` không enable ARR-B. |
| Chain bị diễn giải physical rotation | Cấm identity predictor/claim; endpoint continuity chỉ structural context. |
| 2023 adaptive overfit | HPO/weights trong rolling 2016–2022; 2023 chỉ controlled selection; 2024 sealed. |
| Downstream dùng sai prediction | D025 + artifact schema chỉ nhận Core Arrival output. |
| Equal-compute không công bằng | Pre-register total wall-clock budget và shared verifier/objective/seeds. |
| Synthetic claim vượt evidence | Gate/Turn synthetic; limitations/dashboard wording bắt buộc. |

# 8. Phạm vi không triển khai trong baseline migration

- Không implement Week 3 preprocessing/features hoặc
  `reconstructed_chain_features_v1`.
- Không train ML, chạy Optuna/SHAP, model selection hay ablation.
- Không download/join Weather hoặc chọn provider khi chưa có evidence.
- Không reconstruct Chain/canonical/flight key/temporal artifacts.
- Không mở row-level 2024.
- Không implement CP-SAT, SA, Monte Carlo hoặc dashboard.
- Không sửa `.docx`; thesis proposal cần sync riêng sau migration.

# 9. Tiêu chí hoàn thành đề tài

- Core Arrival đạt target/cut-off/no-Weather contract và downstream utility
  được đánh giá qua Schedule-only/ML/Oracle dưới cùng scenario/solver.
- Auxiliary Departure Weather comparison, nếu chạy, chứng minh arm parity và
  point-in-time provenance; nếu không đủ evidence phải báo limitation minh bạch.
- Raw Weather và raw Chain không được promote; reconstructed Chain chỉ optional
  ablation và không physical identity. Mỗi Chain-derived predictor phải PASS
  availability tại T-2h rồi mới qua normal Arrival leakage gate.
- Temporal roles 2016–2022/2023/2024 giữ nguyên; 2024 chỉ sau freeze.
- Greedy, CP-SAT, CP-SAT+SA dùng cùng verifier/metrics; robustness tách plan và
  recourse, không bỏ failed/infeasible scenarios.
- Dashboard thể hiện **Scheduled -> Core Arrival Predicted -> Optimized ->
  Evaluated**, phân biệt 2023 development và 2024 final, không trình bày
  Auxiliary Departure như optimizer input.
