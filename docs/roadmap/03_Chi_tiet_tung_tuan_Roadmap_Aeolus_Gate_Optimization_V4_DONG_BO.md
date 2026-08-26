**ỨNG DỤNG HỌC MÁY VÀ LẬP TRÌNH RÀNG BUỘC TRONG DỰ BÁO ĐỘ TRỄ CHUYẾN BAY VÀ TỐI ƯU TÁI PHÂN BỔ CỔNG ĐỖ TÀU BAY**

**CHI TIẾT TỪNG TUẦN CỦA ROADMAP — BẢN ĐỒNG BỘ V4**

*Kế hoạch thực thi, deliverable, acceptance gate và guardrail cho Dual Prediction Architecture*

| **Phiên bản** | 4.0 — Dual Prediction Architecture |
|---|---|
| **Ngày** | 26/08/2026 |
| **Phạm vi** | 12 tuần — Aeolus 2016–2024 |
| **Quyết định cốt lõi** | Core Arrival no-Weather + Auxiliary Departure point-in-time Weather study |

# 1. Cách sử dụng tài liệu

Đây là execution-level companion của Roadmap và Tech Stack V4. Decision
Registry là single source of truth. Config, leakage rules, tests, reports,
dashboard và thesis phải dùng cùng task names/targets/cut-off/temporal roles.
Ba V3 documents được giữ nguyên làm historical protocol; V4 là authoritative
cho work sau amendment ngày 26/08/2026.

Week 1–2 đã **COMPLETED** trước amendment. Evidence đã PASS không được viết lại
như thể V4 tồn tại từ đầu, không được regenerate, và không được làm sai kết quả
lịch sử: E002 raw Weather DROP; E003 raw `.pt` FINAL_NO_GO; E005 reconstructed
Schedule Chain FULL_DATA_PASS/GO_FOR_ABLATION. Week 3A đã **COMPLETED**, Week
3B đã **COMPLETED_WITH_BLOCKED_ML_BRANCH**, và Week 3C đã **COMPLETED** ngày
26/08/2026. Week 3 đã đóng; Core Arrival hiện ready cho Week 4.

# Các quyết định thống nhất dùng xuyên suốt

| **Hạng mục** | **Quyết định V4** |
|---|---|
| Core Arrival | `DEST=ATL`; `y_arr_cls = 1[ARR_DELAY >= 15]`; `y_arr_reg = ARR_DELAY` signed; no Weather. |
| Auxiliary Departure | `ORIGIN=ATL`; `y_dep_cls = 1[DEP_DELAY >= 15]`; no regression. |
| Cut-off | `CRS_DEP_TIME - 2 hours` cho cả hai task. |
| Arrival predictors | Schedule/Calendar/Carrier/Route/safe context; optional reconstructed Chain ablation only. |
| Arrival forbidden | Weather, `DEP_DELAY`, predicted departure delay, actual operations/outcomes. |
| Departure experiment | DEP-A Schedule-only vs DEP-B same data/model/protocol + audited point-in-time Weather. |
| Raw Weather | Six Aeolus fields `INSUFFICIENT_EVIDENCE`, DROP for both tasks. |
| External Weather | Separate `weather_point_in_time_v1`, `AUDIT_REQUIRED`, disabled; no provider selected. |
| Raw Chain | `.pt` FINAL_NO_GO; read-only; never core/ablation/reverse-engineered. |
| Reconstructed Chain | `schedule_chain_v1` GO_FOR_ABLATION; schedule context only; disabled/outside core. |
| Chain-derived predictors | D026 + E006: completed audit found no snapshot evidence and `KEEP_SAFE=[]`; 7 local/past `REVIEW_REQUIRED`, 11 future/full-chain `BLOCKED_UNTIL_PROVEN`, identifiers `IDENTIFIER_ONLY`; ARR-B disabled. |
| Core methods | Logistic/Ridge, RF, HGB, XGBoost, Weighted Ensemble; max 5. |
| Auxiliary method | Same XGBoost Classifier for DEP-A/DEP-B; Logistic optional sanity only. |
| Temporal | 2016–2022 rolling; 2023 selection/ablation/downstream; 2024 sealed final. |
| Downstream | Only Core Arrival prediction feeds Synthetic Turn/gates/Greedy/CP-SAT/SA/Monte Carlo. |
| Claim | Synthetic gate impact only; no real aircraft/gate/delay-reduction claim. |

# 2. Quy ước chung cho mọi tuần

- `data/raw/**` immutable. External Weather, nếu được phép sau này, nằm ngoài
  raw Aeolus và có source/version riêng.
- Không rerun canonicalization, temporal manifests, flight-key creation hoặc
  reconstructed Chain vì V4 migration.
- Không truy cập row-level 2024 trong development; existing metadata/docs chỉ
  dùng cho consistency. Access guard không được weaken.
- Cả hai task fail closed theo T-2h; actual operations và unknown fields không
  được vào candidate `X`.
- Arrival không Weather, kể cả indirect path qua auxiliary probability.
- Weather không chứng minh issue/publication/availability time thì DEP-B không
  chạy. DEP-B bị block không phải core failure.
- Encoder/imputer/scaler/frequency map/HPO/calibration/ensemble weights fit
  trong training window; không dùng 2023 cho HPO, không dùng 2024 để quyết định.
- Reconstructed membership không truncate theo `max_context_length=6`.
- Full reconstructed membership không tự động predictor-safe. Week 3B.0 audit
  đã hoàn tất với `KEEP_SAFE=[]`; only a future evidence-backed `KEEP_SAFE`
  feature may proceed to the separate normal Arrival leakage gate.
- `flight_key`, `chain_id`, `source_year`, `source_row_number` là trace/join/
  audit only, không predictor.
- CONTACT_GATE, REMOTE_STAND, UNASSIGNED tách biệt; Greedy/CP-SAT/SA dùng shared
  conflict verifier/objective.
- CP-SAT standalone và CP-SAT+SA dùng equal total compute; failed/infeasible
  cases không bị xóa.
- Mỗi experiment/version/config/seed được log; không tạo fake result.

# 3. Dependency tổng quan

| **Giai đoạn** | **Trọng tâm** | **Phụ thuộc** |
|---|---|---|
| Week 1 | Scope, audit plan, guards | None — completed historical evidence |
| Week 2 | Schema/canonical/leakage/Weather/raw Chain evidence | Week 1 — completed historical evidence |
| V4 amendment | Task-aware baseline migration | Completed Week 1–2 + E005, no model result |
| Week 3A | **COMPLETED** — Core Arrival preprocessing | V4 baseline READY; acceptance PASS 26/08/2026 |
| Week 3B | **COMPLETED_WITH_BLOCKED_ML_BRANCH** | 3B.0/3B.2/3B.4 complete; 3B.1/3B.3 skipped without failure; E006 `KEEP_SAFE=[]`; no artifact |
| Week 3C | **COMPLETED** — provider-agnostic Weather contract preparation | I004/W1–W15 contract; provider TBD, `AUDIT_REQUIRED`, disabled; no data/API/join/model |
| Week 4 | Three Core Arrival baselines | Week 3 closeout complete; `READY_FOR_WEEK_4 = YES`; auxiliary Weather is not a Core dependency |
| Week 5 | Core XGBoost/Optuna | Week 4 |
| Week 6 | Ensemble/2023/SHAP/ARR ablation/conditional DEP ablation | Week 5; ARR-B requires approved D026 `KEEP_SAFE` subset; DEP-B additionally requires provenance PASS |
| Week 7 | Synthetic Turn/gates | Frozen Core Arrival; auxiliary not a dependency |
| Week 8 | Conflict/Greedy/CP-SAT/utility | Week 7 |
| Week 9 | Equal-compute hybrid/scalability | Week 8 |
| Week 10 | Robustness/pilots/freeze | Week 9 |
| Week 11 | Final 2024 | Approved `system_freeze_manifest` |
| Week 12 | Dashboard/thesis/demo | Frozen final artifacts |

# TUẦN 1: CHỐT PHẠM VI, CUT-OFF VÀ AUDIT BASELINE — COMPLETED

Mục tiêu lịch sử: khóa scope, ATL, T-2h, temporal roles, raw policy, registry,
schema/Chain audit plans và 2024 guard trước pipeline chính.

## A. Evidence đã hoàn tất

- Repository/config/logging/access-guard baseline.
- Aeolus 2016–2024 inventory và immutable raw boundary.
- `DEST=ATL` inbound, `ORIGIN=ATL` outbound, Arrival targets V3.
- Schema audit plan, data dictionary V0, Chain feasibility V0.
- Assumptions, limitations, experiment log.

## B. V4 interpretation

Không rewrite lịch sử. V4 giữ ATL/T-2h/temporal/raw/claim decisions và bổ sung
dual-task role sau Week 2. Outbound trở thành auxiliary Departure **và** vẫn
phục vụ future synthetic Turn simulation.

## Deliverable preserved

`configs/base.yaml` lịch sử đã được migrate contract; decision/inventory/audit
docs và access guard evidence được giữ. Không regenerate Week-1 artifacts.

## Acceptance state

**PASS / COMPLETED.** Không có model/preprocessing/simulation result ở Week 1.

## Guardrail

Không mô tả V4 như quyết định ban đầu của Week 1; không sửa evidence để hợp
thức hóa Weather hoặc raw Chain.

# TUẦN 2: SCHEMA, TEMPORAL, LEAKAGE/WEATHER VÀ CHAIN EVIDENCE — COMPLETED

Mục tiêu lịch sử: audit schema 2016–2024, materialize canonical/ATL flows,
finalize temporal manifests, leakage/Weather evidence và raw Chain decision.

## A. Evidence đã hoàn tất

- `canonical_schema_v1`: 34 ordered fields, nine annual audits.
- Canonical/year, inbound `DEST=ATL`, outbound `ORIGIN=ATL` processed partitions.
- `flight_key_v1`, `expanding_window_v1`, split/access manifests.
- E002: six raw Aeolus Weather fields `INSUFFICIENT_EVIDENCE`/DROP.
- E003: original raw Flight Chain `.pt` `FINAL — NO_GO`.
- Subsequent derived evidence E005: reconstructed `schedule_chain_v1` full
  2016–2023 PASS and `GO_FOR_ABLATION`, independent of E003.

## B. V4 interpretation

Week-2 Arrival leakage findings remain evidence. V4 adds a task-aware
Departure contract without promoting stored raw Weather. External Weather is
a new source class and must not be faked as canonical Aeolus Weather.

## Deliverable preserved

All Week-2 manifests, processed datasets, reports, decisions and reconstruction
production artifacts remain unchanged. Reconstruction is not rerun.

## Acceptance state

**PASS / COMPLETED.** 2024 remains sealed; only historical authorized
schema/canonical metadata evidence exists.

## Guardrail

Không thay E002/E003/E005, `flight_key_v1`, `schedule_chain_v1`,
`canonical_datetime_storage_amendment_v1`, fold boundaries hoặc row-level
artifacts.

# ARCHITECTURE AMENDMENT V4: BASELINE MIGRATION — 26/08/2026

Mục tiêu: chuyển single Arrival contract thành dual prediction architecture,
không thực hiện Week 3.

## A. Công việc

- Refactor `configs/base.yaml` thành `arrival_core` và
  `departure_auxiliary`; cập nhật flow roles và tách raw/reconstructed Chain.
- Refactor leakage API theo `task`, default Arrival, unknown task/field fail
  closed, raw Weather forbidden cho cả hai.
- Update tests/smoke và synchronized Markdown V4.
- Preserve V3 files, artifacts/data/access guard; no training/Weather/feature
  work.

## Deliverable

V4 config/rules/tests, three V4 roadmap documents, D021–D025, architecture
decision, Weather plan/addendum, README/project structure/thesis notes/log.

## Acceptance gate

All tests + compile/import + metadata-only smoke PASS; no data/artifact changes;
cross-document target/Weather/Chain/T-2h/ATL/2024/downstream consistency PASS.

# TUẦN 3A: CORE ARRIVAL PREPROCESSING — COMPLETED 26/08/2026

Mục tiêu: tạo fold-safe Core Arrival preprocessing contract tại T-2h, chưa
train model competition.

Phụ thuộc: V4 baseline readiness PASS.

## Dependency activation preflight — bắt buộc trước implementation

1. Kiểm tra scikit-learn đã tồn tại trong verified `.venv` hay chưa.
2. Xác định candidate version tương thích Python 3.11.
3. Candidate-test trong current environment.
4. Chỉ pin dependency khi Week 3A code thực sự import/use nó.
5. Không unnecessarily upgrade NumPy, Pandas hoặc PyArrow.
6. Sau dependency change, chạy full regression suite trước khi viết pipeline.

Preflight này không được dùng để bắt đầu Week 3A trong baseline hardening.

## A. Công việc phải thực hiện

- Tạo `y_arr_cls = 1[ARR_DELAY >= 15]` và
  `y_arr_reg = ARR_DELAY` signed; giữ negative/zero/positive.
- Build Arrival predictor contract từ Schedule, Calendar, Carrier, Route và
  audited safe context; tuyệt đối no Weather/no predicted Departure.
- Define missing-value policy per feature type và missing indicator policy.
- Define categorical treatment; airport integer indices không continuous;
  high-cardinality strategy fit trong training fold.
- Define model-specific transformers: Linear scaling/one-hot; tree/boosting
  appropriate encoding; common raw information set.
- Define outlier protocol: ground truth không abs/clip để đẹp metric; optional
  robust loss/sensitivity và simulation guard tách riêng.
- Validate task-aware leakage, fold isolation, constant-drop, unknown-field and
  2024 guard behavior.
- Version feature manifest, label contract, preprocessing config và transformer
  registry.

## B. Hướng triển khai kỹ thuật

- Every transformer fit inside each expanding training fold.
- 2023 không fit preprocessing/HPO; chỉ transform sau protocol lock cho Week 6.
- 2024 không row-level access/transform/evaluate.
- Do not include target, actual timestamps/durations, raw Weather, IDs or
  flow-specific constants.

## Deliverable cuối tuần

- `src/data/preprocessing.py`
- `src/features/tabular_features.py`
- `feature_manifest_arrival_v1.json`
- `feature_pipeline_registry_arrival_v1.json`
- `configs/outlier_and_simulation_guard.yaml`
- leakage/cutoff/fold/label tests

## Tiêu chí nghiệm thu

- Reproducible fold-specific Arrival matrices without 2023/2024 fit.
- Exact labels and signed target; no Weather/Departure/actual outcomes.
- All transforms traceable and unknown fields fail closed.

## Acceptance state

**PASS / COMPLETED.** `feature_manifest_arrival_v1` khóa common raw
Schedule/Calendar/Carrier/Route information set. Linear và tree/boosting
transformers fit train-fold only; high-cardinality flight number dùng
non-target frequency mapping fit trong train fold. Bounded smoke dùng 1,024
rows 2016 làm train và 512 rows 2019 làm validation, với column projection và
batch size 256. Không model estimator, Weather, Chain, 2023 fit hay row-level
2024 access. Week 3B đã đóng fail-closed; Week 3C contract đã hoàn tất và Core
Arrival hiện ready cho Week 4.

## Guardrail

Không implement/train Week-4 models sớm; không clip ground truth; không dùng
Weather “vì auxiliary đã có”.

## Cập nhật tài liệu khóa luận

Ghi label/preprocessing/outlier/feature contracts và evidence tests, không ghi
model result.

# TUẦN 3B: RECONSTRUCTED CHAIN FEATURE ENGINEERING — COMPLETED_WITH_BLOCKED_ML_BRANCH

Mục tiêu planned ban đầu là build **và audit** optional
`reconstructed_chain_features_v1` từ existing `schedule_chain_v1`, không thay
reconstruction membership/semantics. Execution outcome dừng fail-closed sau
E006 vì dataset-level `GO_FOR_ABLATION` không phải feature-level ML approval.

Phụ thuộc: E005 `GO_FOR_ABLATION`, D026,
`reconstructed_chain_feature_availability_plan_v1.md`, và Week 3A join/leakage
contract.

## Week 3B.0 — CHAIN_FEATURE_POINT_IN_TIME_AVAILABILITY_AUDIT — COMPLETED 26/08/2026

Đây là sub-stage bắt buộc đầu tiên, trước feature materialization:

- Derive `target_cutoff = target CRS_DEP_TIME - 2 hours` từ canonical schedule
  fields, không actual time.
- Với từng feature, ghi rõ source members là `past`, `target`, `future`, hoặc
  `full-chain`, cùng schedule/context required.
- Không coi row/timestamp tồn tại trong final historical dataset là proof nó
  available tại T-2h.
- Target/position-local và past-context bắt đầu `REVIEW_REQUIRED`.
- Future/full-chain bắt đầu `BLOCKED_UNTIL_PROVEN`.
- `flight_key`, `chain_id`, `source_year`, `source_row_number` giữ
  `IDENTIFIER_ONLY`.
- Audit theo C1–C10 trong availability plan. Promotion chỉ registry-first từ
  primary/versioned availability evidence, không từ model/2023/2024 result.

**Kết quả E006:** không có schedule publication timestamp, versioned snapshot,
timetable issue/revision history, hay evidence tương đương. `KEEP_SAFE=[]`; 7
local/past features giữ `REVIEW_REQUIRED`; `is_single_leg_chain` cùng 10
future/full-chain features là `BLOCKED_UNTIL_PROVEN`; 4 identifiers giữ
`IDENTIFIER_ONLY`. Audit không đọc row-level Chain, không dùng external
evidence/model/2023/2024, không tạo feature artifact và không thay reconstruction.

## Week 3B.1 — Derive candidate features — SKIPPED_NOT_REQUIRED_FOR_ML

Không derive feature. E006 có `KEEP_SAFE=[]`, nên không tồn tại approved ML
subset để materialize. Candidate list dưới đây được giữ làm planned historical
scope, không phải file/artifact đã tạo:

Candidate list giữ nguyên full membership, nhưng initial status conservative:

```text
TARGET/POSITION LOCAL — REVIEW_REQUIRED
chain_position
legs_before_target
is_first_chain_leg

PAST-CONTEXT — REVIEW_REQUIRED
minutes_from_chain_first_departure
minutes_since_previous_scheduled_departure
has_previous_chain_leg
previous_leg_destination_matches_target_origin

FUTURE/FULL-CHAIN — BLOCKED_UNTIL_PROVEN
is_single_leg_chain
chain_length
legs_after_target
is_last_chain_leg
chain_length_gt_6
minutes_to_chain_last_departure
minutes_to_next_scheduled_departure
has_next_chain_leg
next_leg_origin_matches_target_destination
chain_schedule_span_minutes
chain_position_fraction
```

E006 reclassifies `is_single_leg_chain` thành `BLOCKED_UNTIL_PROVEN`: feature
này cần chứng minh không có cả previous lẫn future member. `chain_length_gt_6`
vẫn blocked; giữ chain dài hơn sáu trong reconstruction không chứng minh final
length predictor-safe.

## Week 3B.2 — Mark status per feature — COMPLETED_THROUGH_E006

- Ghi status, reason, required inputs/member directions, evidence reference,
  policy/config/source version và normal Arrival leakage result.
- Chỉ `KEEP_SAFE` mới có thể đi tiếp tới Arrival leakage contract; PASS một gate
  không thay PASS gate còn lại.
- Unknown/unclassified feature fail closed. Không auto-promote bằng intuition,
  correlation, SHAP, ROC-AUC, MAE, 2023 hay 2024.

E006 audit manifest và policy YAML là execution evidence cho substage này; không
cần derive feature để khóa status.

## Week 3B.3 — Materialize only a traceable artifact — SKIPPED_OPTIONAL_DIAGNOSTIC

Diagnostic materialization được policy cho phép nhưng không thực thi: không có
approved ML subset và diagnostic output không làm thay đổi admissibility. Do đó
không tạo module, directory, matrix hay manifest feature mới. Các rule planned
dưới đây chỉ áp dụng nếu audit tương lai được mở lại bằng evidence mới:

- Full membership retained; không truncate/pad reconstructed chain về 6.
- `max_context_length=6` chỉ future context-transformer metadata.
- Schedule-only derivation; no Weather, `FLIGHTS`, targets or actual outcomes.
- Endpoint match chỉ structural schedule context, không physical aircraft.
- Output version riêng; join coverage/uniqueness/fingerprint validated.
- Blocked/review features có thể materialize cho audit/research diagnostics chỉ
  khi manifest ghi rõ `ML_ADMISSIBLE=false`; predictor-matrix builder phải reject.

## Week 3B.4 — Keep ARR-B disabled — COMPLETED / PASS

Không auto-enable ARR-B trong Week 3. Week 6 chỉ được chạy ARR-A/ARR-B nếu có
approved `KEEP_SAFE` subset đã pass cả availability và normal Arrival leakage
gates. Nếu không có feature PASS, ghi blocked/limitation thay vì bypass policy.

## Deliverable cuối tuần

- Completed C1–C10 feature availability audit and per-feature status manifest.
- Machine-readable closure disposition; ARR-B vẫn disabled.
- `src/features/reconstructed_chain_features.py`: planned, not created because
  E006 approved no ML-safe features.
- `data/processed/reconstructed_chain_features_v1/`: optional planned path, not
  created; diagnostic materialization was skipped.

## Tiêu chí nghiệm thu

- 1:1 target join, deterministic output, no predictor identifiers/leakage.
- Chain length >6 preserved and test-covered without claiming availability.
- No candidate silently enters `X`; unknown/review/blocked/identifier fail closed.
- Raw `.pt` never opened; production reconstruction artifact unchanged.

## Guardrail

Không claim aircraft rotation, không overwrite reconstruction, không suy diễn
final membership là point-in-time snapshot, không enable ARR-B by default và
không run ablation trong Week 3.

## Cập nhật tài liệu khóa luận

Nêu rõ schedule/service-number context, dataset-vs-feature boundary, candidate
status, availability evidence và claim boundary.

# TUẦN 3C: AUXILIARY WEATHER CONTRACT PREPARATION — COMPLETED 26/08/2026

Mục tiêu: chuẩn bị source specification, provenance requirements, join
contract và audit plan; không bắt buộc có Weather dataset thành công.

Phụ thuộc: `point_in_time_weather_plan_v1.md`.

## A. Công việc phải thực hiện

- Define minimum timestamps: issue/publication/availability and valid time.
- Define timezone/DST and ATL airport/station/grid mapping requirements.
- Separate forecast, observation, reanalysis/model-fill semantics.
- Define immutable source/version/license/signature manifest.
- Define point-in-time join, deterministic tie-break, missing-data and DEP-A/
  DEP-B exact row parity.
- Define audit gates/leakage tests/PASS-FAIL decision and provider evaluation
  criteria without selecting provider by assumption.

## B. Không thuộc Week 3

- No download/API client/source ingestion.
- No Weather join/feature matrix/model run.
- No promotion of six raw Aeolus Weather scalars.
- No use of 2024 metadata beyond existing consistency evidence, and no rows.

## Deliverable cuối tuần

- `weather_point_in_time_contract_v1.md` reviewed source/schema/join contract.
- `weather_point_in_time_contract_v1.json` W1–W15 audit/decision template.
- Pure synthetic validation in `src/data/weather_contract.py`; no provider
  client, data acquisition, production join, or Weather feature artifact.
- Explicit state: provider `TBD`, `AUDIT_REQUIRED`, disabled.

## Tiêu chí nghiệm thu

- Weather ambiguity removed from future workflow.
- Arrival Week 3A/3B can complete independently.
- Failure path documented as `BLOCKED_NOT_CORE_FAILURE`.

## Guardrail

Không chọn Meteostat/provider vì familiarity; không gọi observation forecast;
không dùng valid time thay availability time.

## Acceptance state

**PASS / COMPLETED.** Forecast, observation, reanalysis/model-analysis/
model-fill semantics are distinct. Contract requires issue/publication/
available/valid times, timezone-aware UTC normalization, versioned ATL
location mapping, variable/source provenance, availability-first deterministic
selection, duplicate rejection, and exact DEP-A/DEP-B target row parity. All
W1–W15 gates are critical. No provider was selected, no Weather was downloaded
or joined, no model was trained, and no 2024 row was accessed.

`POINT_IN_TIME_WEATHER_PROVENANCE` remains `AUDIT_REQUIRED`; DEP-B remains
disabled. Failure remains `BLOCKED_NOT_CORE_FAILURE`, so Week 3 closes and
Core Arrival proceeds with `READY_FOR_WEEK_4 = YES`.

# TUẦN 4: CORE ARRIVAL BASELINES VÀ ROLLING VALIDATION

Mục tiêu: train 3/5 Core Arrival methods cho classification và regression trên
rolling development 2016–2022.

Phụ thuộc kỹ thuật: Week 3A PASS; ARR-B features không bắt buộc cho base core
run. Week 3B đã đóng fail-closed và Week 3C contract/project closeout đã PASS;
`READY_FOR_WEEK_4 = YES`. Weather provenance không phải Week-4 Core dependency.

## A. Công việc phải thực hiện

- Logistic Regression / Ridge Regression.
- Random Forest Classifier / Regressor.
- HistGradientBoosting Classifier / Regressor.
- Per-fold/per-year ROC-AUC, PR-AUC, Recall, F1, Brier/calibration; MAE, RMSE,
  R² cho signed regression; runtime/memory.
- Store OOF predictions and preprocessing/model/version manifests.

## B. Hướng triển khai

- Same Arrival information contract; model-specific transformer allowed.
- Training/fitting only inside existing folds; no 2023 model choice, no 2024.
- Class weighting derived from training fold, no temporal-crossing oversample.

## Deliverable

Core baseline model modules, OOF predictions, rolling report, tests/manifests.

## Acceptance gate

Three methods complete for both Arrival tasks, common metrics/rows/folds,
zero Weather/Departure leakage.

## Guardrail

Không coi Accuracy là primary, không đổi target giữa methods, không train
auxiliary 5-model competition.

# TUẦN 5: CORE ARRIVAL XGBOOST + OPTUNA FIXED BUDGET

Mục tiêu: hoàn thành method 4 và fixed-budget tuning trong 2016–2022.

## A. Công việc

- XGBoost Classifier/Regressor cho Arrival targets.
- Optuna studies cho RF/HGB/XGBoost với aggregate rolling-fold objectives.
- Lock trials/timeout/seed/sampler/pruner trước run; calibration trong
  development folds only.
- Save study DB, best params, OOF predictions, HPO/resource manifest.

## Acceptance gate

Four base methods; no 2023/2024 HPO; probability metrics use probability, not
hard labels; reproducible fixed budget.

## Guardrail

Không tune ARR-A/ARR-B khác budget để tạo advantage; auxiliary Weather vẫn
không chạy nếu provenance chưa PASS.

# TUẦN 6: ENSEMBLE, 2023 SELECTION, SHAP VÀ CONTROLLED ABLATIONS

Mục tiêu: hoàn thành method 5, dùng 2023 có kiểm soát, quyết định reconstructed
Chain KEEP/DROP, và chạy auxiliary Weather chỉ khi provenance PASS.

Phụ thuộc: Week 5; ARR-B requires a documented D026 availability audit and a
non-empty `KEEP_SAFE` subset that also passes normal Arrival leakage; DEP-B
additionally requires `POINT_IN_TIME_WEATHER_PROVENANCE = PASS`.

E006 hiện có `KEEP_SAFE=[]`, vì vậy ARR-B/Chain ML đang
`BLOCKED_PENDING_NEW_EVIDENCE`; Week 6 không được bypass gate này.

## A. Core Arrival

- Optimize nonnegative ensemble weights summing to 1 from OOF 2016–2022 only.
- Refit candidates on 2016–2022 and compare exactly 5 methods on 2023.
- SHAP/feature plausibility for XGBoost/champion; calibration report.
- ARR-A: Tabular-only.
- ARR-B: same rows/folds/model/config/budget +
  only the independently approved `KEEP_SAFE` subset from
  `reconstructed_chain_features_v1`.
- Decide reconstructed features KEEP/DROP for later frozen Core Arrival; no
  assumption Ensemble/ARR-B wins.

## B. Auxiliary Departure Weather

If provenance PASS:

- DEP-A Schedule-only versus DEP-B same inputs plus audited Weather.
- Same outbound target rows, labels, folds, preprocessing except Weather,
  XGBoost classifier/config, seed, HPO budget and metrics.
- Report discrimination, calibration, coverage/missingness, per-year/fold
  behavior and effect uncertainty.

If provenance not PASS:

```text
AUXILIARY_WEATHER = BLOCKED_NOT_CORE_FAILURE
CORE_ARRIVAL_FREEZE = CONTINUE
```

No placeholder raw Aeolus Weather is substituted. Auxiliary output never feeds
Arrival or downstream.

## Deliverable

- Core Weighted Ensemble/2023 comparison/SHAP.
- `arrival_reconstructed_chain_ablation.md` and KEEP/DROP decision.
- Either auxiliary Weather report + provenance reference or explicit blocked
  limitation.
- Core model registry and ML freeze manifest; 2024 unopened.

## Acceptance gate

- Five-method cap; weights not tuned on 2023/2024.
- ARR arms differ only by reconstructed features.
- Every ARR-B feature passed both T-2h availability and normal Arrival leakage
  gates; `GO_FOR_ABLATION` alone is not sufficient.
- DEP arms, if run, differ only by audited Weather.
- Core freeze proceeds independently of auxiliary status.

## Guardrail

Không raw Chain/raw Weather; không predicted Departure in Arrival; không dùng
2024 để choose champion/feature/Weather.

# TUẦN 7: SYNTHETIC AIRCRAFT TURN VÀ GATE SIMULATION

Mục tiêu: tạo finite synthetic Turns/gate resources trên 2023 từ **frozen Core
Arrival predictions only**.

## A. Công việc

- Deterministic sampled scenarios ~100/200/300 movements; không full ATL day.
- Synthetic inbound/outbound pairing/fallback; each flight at most once.
- `TURN_ID`/`SIM_AIRCRAFT_ID`; no `TAIL_NUM`/physical rotation.
- Contact gates, constrained REMOTE_STAND, explicit UNASSIGNED.
- Nominal schedule occupancy/initial plan before Arrival prediction injection.
- `A_pred`, calibrated Arrival risk buffer, finite release; sensitivity for
  turnaround/window/pairing/gate mix.

## B. Downstream input check

Prediction schema must reject `p_dep_delay`, auxiliary model version and
Weather columns. Only Arrival probability/signed delay are accepted.

## Deliverable

Turn/gate generators, 2023 scenarios/initial plan, assumptions/sensitivity,
input-boundary tests.

## Acceptance gate

Finite windows, unique pairing, state semantics separated, three scales,
2024 closed, auxiliary not a dependency.

## Guardrail

Không claim real gate/aircraft operation; không use Weather/Departure output to
modify risk buffer or release in V4.

# TUẦN 8: CONFLICT ENGINE, GREEDY, CP-SAT VÀ ARRIVAL UTILITY

Mục tiêu: shared verifier, Greedy baseline, CP-SAT core và direct utility
experiment trên 2023.

## A. Công việc

- Independent conflict verifier for overlap, availability, capacity,
  compatibility, buffer and assignment states.
- Greedy: keep initial contact when feasible, then remote, else unassigned.
- CP-SAT TURN-to-resource with hard constraints.
- Shared soft objective: reassign + remote + unassigned + utilization balance
  (+ documented preference); no double-count risk.
- Same scenario/solver/gates/metrics across Schedule-only, Core Arrival ML and
  Oracle actual signed `ARR_DELAY` upper-bound.
- Log conflicts, reassignments, CONTACT/REMOTE/UNASSIGNED, objective parts,
  runtime, solver status/bound/gap.

## Deliverable

Conflict/Greedy/CP-SAT modules, optimization config, Arrival utility report,
expected-result and boundary tests.

## Acceptance gate

All outputs pass verifier or record explicit failure/unassigned. Auxiliary
Departure never appears as an information regime.

## Guardrail

Oracle không deployable; REMOTE != UNASSIGNED; no objective change between
regimes; 2024 unopened.

# TUẦN 9: EQUAL-COMPUTE CP-SAT VS CP-SAT+SA VÀ SCALABILITY

Mục tiêu: paired fair comparison ở scales ~100/~200/~300.

## A. Công việc

- Pre-register total wall-clock budget T per scale.
- CP-SAT standalone gets T; Hybrid splits T into CP-SAT incumbent + SA without
  exceeding T.
- SA hard-feasible neighbors or reject/repair; shared verifier/objective.
- Paired seeds/scenarios; report objective/status/CONTACT/REMOTE/UNASSIGNED,
  runtime, CP-SAT bound/gap and failures.
- Lock SA params on 2023 development only.

## Deliverable

SA module, compute manifest, equal-compute/scalability reports and results.

## Acceptance gate

Equal total compute demonstrated; no assumption SA improves CP-SAT; no hidden
infeasibility or changed simulation truth.

## Guardrail

Không change budget after results, không relax hard constraints, không use
2024 for SA parameters.

# TUẦN 10: ROBUSTNESS, RECOURSE, MONTE CARLO PILOT VÀ FREEZE

Mục tiêu: separate fixed-plan robustness/recourse, estimate runtime, then
freeze entire system before 2024.

## A. Công việc

- Plan robustness: hold forecast assignment fixed under realized perturbation.
- Recourse: re-optimize after realization; report recovery changes/runtime.
- Perturbations from development OOF residuals and documented assumptions;
  delay/turnaround/gate disruption separated.
- Pilot 20 then 50, same seeds, retain all failures/infeasible cases.
- Final sensitivity on 2023 for pairing/turnaround/Arrival risk buffer/gate
  mix/objective/compute/SA/robustness distribution.
- Freeze model/features, optional reconstructed decision, simulation, solver,
  compute, seeds and robustness. Auxiliary Weather status is documented but
  not an optimizer dependency.

## Deliverable

Monte Carlo module, pilot results, robustness/sensitivity reports,
`system_freeze_manifest.json`.

## Acceptance gate

Both modes reported, pilot runtime supports preregistered final count, freeze
manifest complete, 2024 still sealed.

## Guardrail

Không call recourse plan robustness; không drop failed cases; no 2024-driven
distribution/objective/gate config.

# TUẦN 11: FINAL END-TO-END HOLDOUT 2024

Mục tiêu: one frozen final evaluation only after approved system freeze.

## A. Công việc

- Unlock through final-evaluation guard and transform/evaluate 2024 with frozen
  Core Arrival pipeline.
- Apply frozen scenario/pairing/gate/solver/SA/robustness protocols.
- Schedule-only vs Core Arrival ML vs Oracle; Greedy/CP-SAT/Hybrid under shared
  scenario/verifier/objective/equal-compute.
- Final plan robustness/recourse with preregistered scenario count.
- Retain failures; report ML metrics, calibration, conflicts/reassignments,
  states/utilization/objective/gap/runtime and distribution summaries.
- Record git/config/model/artifact hashes and lock results; technical bug fixes
  versioned/rerun consistently, never tuned from result.

## B. Auxiliary boundary

Auxiliary Departure Weather result, if it exists, remains separately reported
research evidence and is not injected into final optimizer. 2024 auxiliary
evaluation must also obey its own preregistered freeze and may not affect core.

## Deliverable

Final ML/end-to-end/robustness reports, result Parquet, `final_test_manifest`.

## Acceptance gate

2024 access occurs only after freeze; no config changes from final results;
shared fairness protocols and explicit failure accounting.

## Guardrail

Không cherry-pick day/seed; no target-distribution-driven change; không claim
synthetic robustness as real ATL evidence.

# TUẦN 12: DASHBOARD, REPRODUCIBILITY, THESIS VÀ DEMO

Mục tiêu: present the frozen end-to-end story without altering research scope.

## A. Công việc

- Streamlit + Plotly views for Core Arrival risk/signed prediction, synthetic
  Turns, gate states, initial vs optimized timeline, solver/scalability/
  robustness KPIs.
- Distinguish 2023 development and final 2024; Scheduled/Core Arrival ML/
  Oracle/Optimized labels explicit.
- Auxiliary Departure Weather result/blocked limitation in a separate research
  panel; never shown as optimizer input.
- End-to-end regression checks over frozen artifacts/manifests.
- Sync README, thesis, slides/demo with V4; include raw Weather/Chain evidence,
  reconstructed Chain limitation, synthetic claim boundary and 2024 protocol.

## Deliverable

Dashboard, reproducibility guide, final thesis assets, slides/demo checklist.

## Acceptance gate

One reproducible flow; no target/cut-off/Weather/Chain/temporal/downstream
contradictions; final artifacts read-only; no tuning UI/path for 2024.

## Guardrail

Không gọi dashboard là Evaluate, không claim optimizer reduces real flight
delay, không hide blocked auxiliary Weather.

# 4. Bảng milestone cuối roadmap

| **Mốc** | **Điều kiện đạt** |
|---|---|
| M1 — Week 2 | **COMPLETED** evidence: canonical/schema/temporal; E002 DROP; E003 raw Chain NO_GO. |
| V4 baseline | Dual-task config/leakage/tests/docs PASS; E005 preserved; no data/2024/model/feature work. |
| M2 — Week 6 | Core 5 methods + 2023 selection; current E006 blocks ARR reconstructed ablation while `KEEP_SAFE=[]`; auxiliary DEP-A/DEP-B only if Weather provenance PASS; ML freeze. |
| M3 — Week 7 | Synthetic Turn/gates use only Core Arrival; sensitivity complete. |
| M4 — Week 9 | Shared verifier/objective; Greedy/CP-SAT/equal-compute Hybrid; scalability complete. |
| M5 — Week 10 | Plan robustness/recourse pilots + full-system freeze before 2024. |
| M6 — Week 11 | Frozen 2024 end-to-end and final robustness; no tuning. |
| M7 — Week 12 | Dashboard/reproducibility/thesis/slides V4-consistent. |

# 5. Checklist đồng bộ cuối cùng

- `DEST=ATL` Core Arrival, `ARR_DELAY >= 15`, signed `ARR_DELAY`, T-2h, no
  Weather, no predicted Departure input.
- `ORIGIN=ATL` Auxiliary Departure, `DEP_DELAY >= 15`, no regression, T-2h.
- Raw Aeolus Weather DROP for both; external Weather separate,
  AUDIT_REQUIRED/disabled until availability proof.
- Raw `.pt` FINAL_NO_GO; reconstructed `schedule_chain_v1` GO_FOR_ABLATION,
  optional, full membership, not physical rotation.
- Full membership is not blanket feature approval: 3B.0 complete with
  `KEEP_SAFE=[]`; local/past review, future/full-chain blocked, identifiers
  isolated, ARR-B disabled pending new evidence.
- Week 3A/3B/3C separated; Weather cannot block Arrival completion.
- Week 4–5 only Core Arrival methods/HPO; no auxiliary 5-model expansion.
- Week 6 ARR-A/ARR-B uses only reconstructed features approved `KEEP_SAFE` by
  D026 and normal Arrival leakage; DEP-A/DEP-B only after provenance PASS;
  otherwise blocked limitation and proceed.
- Week 7–12 preserve Greedy/CP-SAT/SA/robustness/gate/synthetic semantics.
- Only Core Arrival prediction feeds optimizer; auxiliary remains research-only.
- 2016–2022/2023/2024 roles unchanged; 2024 sealed until full freeze.
- V3 history and Week 1–2/Chain artifacts preserved; no `.docx` changed.
