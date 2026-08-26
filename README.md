# Aeolus Gate Optimization

Baseline hiện hành: **Research Protocol V4.0 — Dual Prediction Architecture**
(26/08/2026).

Trạng thái thực thi: **Week 3 = COMPLETED**. Week 3A Core Arrival preprocessing
đã hoàn tất; Week 3B là `COMPLETED_WITH_BLOCKED_ML_BRANCH`; Week 3C Weather
contract preparation đã hoàn tất. E006 không approve Chain predictor nào,
nhưng Core Arrival hiện `READY_FOR_WEEK_4 = YES`.

```text
Predict -> Simulate -> Optimize -> Evaluate
                                      |
                                      v
                                  Dashboard
```

Dashboard là presentation layer; không thay thế bước Evaluate.

## Kiến trúc V4

### Core — Arrival Delay, no Weather

- Flow: inbound `DEST=ATL`.
- Cut-off: `T_prediction = CRS_DEP_TIME - 2 hours`.
- Classification: `y_arr_cls = 1[ARR_DELAY >= 15]`.
- Regression: `y_arr_reg = ARR_DELAY` theo signed minutes; không `abs`, không
  clip ground truth để cải thiện metric.
- Candidate input: Schedule, Calendar, Carrier, Route và contextual feature đã
  chứng minh point-in-time safe.
- Weather: **không được dùng**. Core Arrival cũng không nhận `DEP_DELAY`,
  `P(departure_delay)`, actual timestamps/durations hoặc outcome thực tế.

Chỉ prediction của Core Arrival đi vào downstream:

```text
Arrival Prediction -> Synthetic Aircraft Turn -> Gate Simulation
  -> Greedy -> CP-SAT -> CP-SAT + SA -> Monte Carlo
```

### Auxiliary — Departure Delay Weather study

- Flow: outbound `ORIGIN=ATL`.
- Cùng cut-off T-2h.
- Classification: `y_dep_cls = 1[DEP_DELAY >= 15]`.
- Không có Departure regression trong baseline V4.
- Planned controlled experiment: DEP-A Schedule-only so với DEP-B Schedule +
  audited point-in-time Weather, ưu tiên cùng XGBoost Classifier/config/seed/
  budget/metrics.
- Auxiliary Departure là research-only và **không feed optimizer**.

External Weather hiện có provider `TBD`, status `AUDIT_REQUIRED`,
`enabled=false`. Week 3C đã khóa contract W1–W15, availability-first join và
DEP-A/DEP-B row parity; không có Weather dataset/API/join nào được tạo.

## Weather evidence boundary

Sáu raw Aeolus fields `O_TEMP`, `O_PRCP`, `O_WSPD`, `D_TEMP`, `D_PRCP`,
`D_WSPD` giữ nguyên E002:

```text
INSUFFICIENT_EVIDENCE
DROP_FROM_PREDICTORS
```

Chúng không phải documented forecasts và không được tạo heuristic lag. Một
source mới như `weather_point_in_time_v1` phải được version riêng dưới
conceptual `data/external/weather/` và chỉ được enable khi chứng minh
`information_available_time <= prediction_cutoff`. Nếu audit không PASS,
auxiliary Weather experiment bị block nhưng Core Arrival tiếp tục.

Contract reviewed hiện hành là `weather_point_in_time_contract_v1`. Nó phân
biệt forecast, observation, reanalysis/model-analysis/model-fill; yêu cầu
`issue_time`, `publication_time`, `available_time`, `valid_time`, UTC/location/
variable provenance và không coi valid time là availability proof. Đây là
template cho future provider audit, không phải Weather provenance PASS.

## Flight Chain boundary

Hai artifact độc lập tuyệt đối:

- Original Aeolus raw Flight Chain `.pt`: **`FINAL_NO_GO`**, read-only, không
  dùng core/ablation, không reverse-engineer, không infer aircraft identity.
- Reconstructed Schedule Flight Chain `schedule_chain_v1`:
  **`FULL_DATA_PASS` / `GO_FOR_ABLATION`**, derived từ canonical Tabular,
  disabled by default và outside core. Nó chỉ là schedule/service-number
  context, không phải `TAIL_NUM` hay physical aircraft rotation.

Production reconstruction 2016–2023 đã PASS với 48,389,162 mapped rows, 100%
coverage và independent inbound-ATL validation. Artifact nằm tại
`data/processed/flight_chain_reconstructed_v1/` và không được regenerate trong
baseline migration. Full membership, kể cả chain dài hơn 6, đã được giữ;
`max_context_length=6` chỉ là future transformer metadata.

**`GO_FOR_ABLATION` là quyết định ở dataset level. Feature-level point-in-time
admissibility vẫn có gate riêng.** Audit E006 đã hoàn tất và không tìm thấy
schedule publication/version/snapshot evidence tại T-2h: `KEEP_SAFE = []`, 7
local/past candidates giữ `REVIEW_REQUIRED`, `is_single_leg_chain` cùng 10
future/full-chain candidates là `BLOCKED_UNTIL_PROVEN`, và identifiers giữ
`IDENTIFIER_ONLY`. ARR-B vẫn disabled.

Week 3B đã đóng fail-closed: 3B.0 PASS; 3B.1
`SKIPPED_NOT_REQUIRED_FOR_ML`; 3B.2 completed through E006; 3B.3
`SKIPPED_OPTIONAL_DIAGNOSTIC`; 3B.4 PASS. Không có
`reconstructed_chain_features_v1` hay feature code được tạo. Diagnostic vẫn là
một capability được phép với `ML_ADMISSIBLE=false`, nhưng không được thực thi
vì không thay đổi admissibility. Identifiers `flight_key`, `chain_id`,
`source_year`, `source_row_number` chỉ dùng cho join/trace/audit. ARR-B và Chain
ML bị block pending new evidence; Core Arrival Tabular-only không bị ảnh hưởng.

## Temporal safety

- 2016–2022: expanding-window rolling development.
- 2023: model selection, controlled ablation và downstream development.
- 2024: **SEALED FINAL HOLDOUT**, chỉ mở sau full-system freeze; không dùng cho
  feature/model/HPO/config decisions.

Access guard hiện tại tiếp tục chặn development access tới 2024.

## Week 3A Core Arrival preprocessing

Week 3A cung cấp exact `y_arr_cls`/signed `y_arr_reg`, common raw information
set Schedule/Calendar/Carrier/Route, fold-train-only linear và tree/boosting
transformers, bounded year/column/batch reads, cùng versioned feature/pipeline
manifests. `FLIGHTS`, airport indices, Weather, Departure/actual outcomes,
identifiers và ATL destination constants không vào `X`; unknown fields fail
closed. `CRS_ARR_TIME` cũng không được dùng để đoán overnight rollover hay
derive duration; pipeline dùng audited scheduled `CRS_ELAPSED_TIME`.

Không model estimator nào được train. Week 3A không fit 2023, không truy cập
row-level 2024 và không đọc reconstructed Chain để feature-engineer. ARR-B vẫn
disabled.

## Data and environment

- Python runtime: `>=3.11`; verified repository `.venv`: Python 3.11.15.
- Week 3A ML preprocessing dependency: scikit-learn 1.9.0.
- Raw Aeolus: `data/raw/tabular/<year>/` và `data/raw/chain/<year>/`, immutable
  và không commit.
- External point-in-time Weather trong tương lai phải tách khỏi raw Aeolus;
  baseline hiện tại không tạo/download dữ liệu này.
- Direct baseline dependencies được pin tối thiểu trong `requirements.txt`.
  Future ML/optimization/dashboard packages chỉ được thêm khi code tương ứng
  thực sự được triển khai.

## Tài liệu authoritative

Đọc theo thứ tự:

1. `docs/decisions/decision_registry.md`
2. `docs/decisions/decision_dual_prediction_architecture_v4.md`
3. ba file `docs/roadmap/*_V4_DONG_BO.md`
4. `docs/dataset_audit/leakage_audit.md`
5. `docs/dataset_audit/weather_timing_audit.md`
6. `docs/dataset_audit/point_in_time_weather_plan_v1.md`
7. `docs/dataset_audit/weather_point_in_time_contract_v1.md`
8. `docs/dataset_audit/reconstructed_chain_feature_availability_plan_v1.md`
9. `docs/dataset_audit/reconstructed_chain_feature_availability_audit_v1.md`
10. `project_structure.md`

Ba roadmap V3 được giữ nguyên làm historical protocol. Week 1–2 evidence và
production artifacts vẫn giữ nguyên; amendment V4 được chốt sau Week 2 và
không dựa trên model result hay 2024.
