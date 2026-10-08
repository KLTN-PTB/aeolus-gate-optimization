# AEOLUS FORENSIC AUDIT — PHASE P2: PREDICTOR VALIDITY AUDIT AT T-2H

**Audit Date**: 2026-10-04  
**Auditor**: Independent Forensic Auditor  
**Repository Branch**: `v4-final-forensic-certification`  
**Git HEAD**: `7ba0aba92d366f712977faaaa5a73cba65a32a55`  
**Prediction Cutoff Protocol**: $T-2\text{h} = \text{CRS\_DEP\_TIME} - 2\text{ hours}$  
**Target Scope**: Core Arrival Inbound ATL (`DEST == 'ATL'`)  

---

## 1. CUTOFF_LEAKAGE_MATRIX

### A. Approved Core Predictors (Active Feature Set)

The authoritative V4 Core Arrival predictor set is defined across:
* **V1 (11 features)**: `artifacts/manifests/feature_manifest_arrival_v1.json` (Used by all core models in `configs/model_catalog_v2.yaml`)
* **V1.1 (13 features)**: `artifacts/manifests/feature_manifest_arrival_v1_1.json` (Adds exact scheduled arrival clock components `scheduled_arrival_hour`, `scheduled_arrival_minute`)
* **V2 (10 features)**: `artifacts/manifests/feature_manifest_arrival_v2.json` (Removes `calendar_year` to eliminate temporal covariate shift)

| # | Feature Name | Source Column | Transformation & Extraction | Availability Time | Cutoff-Compatible? ($T-2\text{h}$) | Future Dependency? | Leakage Risk | Status |
|---|---|---|---|---|---|---|---|---|
| 1 | `CRS_ELAPSED_TIME` | `CRS_ELAPSED_TIME` | Numeric validation (`_numeric_without_silent_coercion`), scheduled flight duration in minutes | Published schedule (months in advance) | **YES** | **NONE** | **NONE** | **SAFE** |
| 2 | `calendar_year` | `FL_DATE` | Timestamp parsing (`%Y-%m-%d %H:%M:%S`) $\rightarrow$ `flight_date.dt.year` | Published schedule (months in advance) | **YES** | **NONE** | **NONE** | **SAFE** |
| 3 | `calendar_month` | `FL_DATE` | Cross-validated against `MONTH` $\rightarrow$ `flight_date.dt.month` | Published schedule (months in advance) | **YES** | **NONE** | **NONE** | **SAFE** |
| 4 | `calendar_day_of_month`| `FL_DATE` | Cross-validated against `DAY_OF_MONTH` $\rightarrow$ `flight_date.dt.day` | Published schedule (months in advance) | **YES** | **NONE** | **NONE** | **SAFE** |
| 5 | `calendar_day_of_week` | `FL_DATE` | Cross-validated against `DAY_OF_WEEK` $\rightarrow$ `(flight_date.dt.dayofweek + 1)` (1=Mon..7=Sun) | Published schedule (months in advance) | **YES** | **NONE** | **NONE** | **SAFE** |
| 6 | `is_weekend` | `FL_DATE` | Binary indicator: `calendar_day_of_week.isin([6, 7]).astype(int8)` | Published schedule (months in advance) | **YES** | **NONE** | **NONE** | **SAFE** |
| 7 | `scheduled_departure_hour` | `CRS_DEP_TIME` | Wall-clock timestamp parsing $\rightarrow$ `departure.dt.hour` ($0\dots23$) | Published schedule (months in advance) | **YES** | **NONE** | **NONE** | **SAFE** |
| 8 | `scheduled_departure_minute` | `CRS_DEP_TIME` | Wall-clock timestamp parsing $\rightarrow$ `departure.dt.minute` ($0\dots59$) | Published schedule (months in advance) | **YES** | **NONE** | **NONE** | **SAFE** |
| 9 | `scheduled_arrival_hour` (v1.1) | `CRS_ARR_TIME` | Wall-clock timestamp parsing $\rightarrow$ `_parse_scheduled_arrival_clock` ($0\dots23$) | Published schedule (months in advance) | **YES** | **NONE** | **NONE** | **SAFE** |
| 10 | `scheduled_arrival_minute` (v1.1) | `CRS_ARR_TIME` | Wall-clock timestamp parsing $\rightarrow$ `_parse_scheduled_arrival_clock` ($0\dots59$) | Published schedule (months in advance) | **YES** | **NONE** | **NONE** | **SAFE** |
| 11 | `OP_CARRIER` | `OP_CARRIER` | Whitespace stripping, categorical encoding (OHE / Ordinal) | Published schedule (months in advance) | **YES** | **NONE** | **NONE** | **SAFE** |
| 12 | `ORIGIN` | `ORIGIN` | Whitespace stripping, categorical encoding (OHE / Ordinal) | Published schedule (months in advance) | **YES** | **NONE** | **NONE** | **SAFE** |
| 13 | `OP_CARRIER_FL_NUM` | `OP_CARRIER_FL_NUM` | Non-target `FrequencyEncoder` fitted strictly on train fold | Published schedule (months in advance) | **YES** | **NONE** | **NONE** | **SAFE** |

---

### B. Prohibited, Dropped, and Guarded Columns

Every column present in the raw data or candidate schemas that is NOT in the approved predictor list has been explicitly audited, classified, and verified as purged from the feature matrix $X$:

| Column Name | Schema Role | Disposition | Leakage / Contract Justification | Enforcement Location |
|---|---|---|---|---|
| `ARR_DELAY` | Ground truth outcome | `TARGET_ONLY` | Primary regression target; strictly decoupled from $X$ | `src/features/tabular_features.py#L188-201` |
| `y_arr_cls` | Derived label | `TARGET_ONLY` | Primary classification label $1[\text{ARR\_DELAY} \ge 15.0]$ | `src/features/tabular_features.py#L194` |
| `y_arr_reg` | Derived label | `TARGET_ONLY` | Continuous signed delay label | `src/features/tabular_features.py#L195` |
| `DEP_DELAY` | Operational outcome | `DROP_LEAKAGE` | Realized departure delay occurs at $T+0\text{h}$, post cutoff $T-2\text{h}$ | `src/data/leakage_rules.py#L66-68` |
| `y_dep_cls` | Auxiliary label | `DROP_LEAKAGE` | Auxiliary departure outcome; forbidden as predictor | `src/data/leakage_rules.py#L67-68` |
| `DEP_TIME` | Operational timestamp | `DROP_LEAKAGE` | Actual gate-out time; known only after cutoff | `src/data/leakage_rules.py#L54-68` |
| `TAXI_OUT` | Operational duration | `DROP_LEAKAGE` | Realized departure taxi; known only after cutoff | `src/data/leakage_rules.py#L54-68` |
| `WHEELS_OFF` | Operational timestamp | `DROP_LEAKAGE` | Takeoff timestamp; occurs after cutoff | `src/data/leakage_rules.py#L54-68` |
| `WHEELS_ON` | Operational timestamp | `DROP_LEAKAGE` | Touchdown timestamp at ATL; future arrival event | `src/data/leakage_rules.py#L54-68` |
| `TAXI_IN` | Operational duration | `DROP_LEAKAGE` | Realized arrival taxi at ATL; future arrival event | `src/data/leakage_rules.py#L54-68` |
| `ARR_TIME` | Operational timestamp | `DROP_LEAKAGE` | Gate-in timestamp at ATL; future arrival event | `src/data/leakage_rules.py#L54-68` |
| `ACTUAL_ELAPSED_TIME` | Operational duration | `DROP_LEAKAGE` | Total flight duration; known only post-arrival | `src/data/leakage_rules.py#L54-68` |
| `AIR_TIME` | Operational duration | `DROP_LEAKAGE` | Airborne duration; known only post-arrival | `src/data/leakage_rules.py#L54-68` |
| `O_TEMP`, `O_PRCP`, `O_WSPD` | Weather | `DROP_WEATHER` | Origin weather lacks point-in-time provenance at $T-2\text{h}$ | `src/data/leakage_rules.py#L73-80` |
| `D_TEMP`, `D_PRCP`, `D_WSPD` | Weather | `DROP_WEATHER` | Destination weather lacks point-in-time provenance at $T-2\text{h}$ | `src/data/leakage_rules.py#L73-80` |
| `DEST` | Population constant | `DROP_CONSTANT` | Constant for all inbound ATL flights (`DEST == 'ATL'`) | `src/features/tabular_features.py#L405-406` |
| `DEST_INDEX`, `D_LATITUDE`, `D_LONGITUDE` | Spatial constant | `DROP_CONSTANT` | Fixed spatial coordinates for ATL hub | `src/data/leakage_rules.py#L86-88` |
| `ORIGIN_INDEX`, `O_LATITUDE`, `O_LONGITUDE` | Spatial candidate | `REVIEW_REQUIRED` | Blocked by default; redundant with categorical `ORIGIN` | `src/data/leakage_rules.py#L92-94` |
| `FLIGHTS` | Operational counter | `REVIEW_REQUIRED_BLOCKED` | Unverified record counter; permanently blocked | `src/data/leakage_rules.py#L81` |
| `flight_key`, `chain_id`, `source_year`, `source_row_number` | Trace identifiers | `DROP_IDENTIFIER` | Row-level tracking metadata; segregated to `identifiers` | `src/features/tabular_features.py#L38-43` |

---

## 2. FEATURE_LINEAGE_AUDIT: 13 SPECIAL INVESTIGATIVE CHECKS

### Check 1: Cutoff Formulation ($\text{CRS\_DEP\_TIME} - 2\text{ hours}$)
* **Source Location**: `src/features/tabular_features.py#L453`, `src/data/leakage_rules.py#L18`.
* **Code Implementation**:
  ```python
  cutoff = (departure - pd.Timedelta(hours=2)).rename("prediction_cutoff")
  ```
* **Audit Finding**: Cutoff is computed relative to the scheduled departure time (`CRS_DEP_TIME`), exactly 2 hours prior. All input features used to predict arrival delay are static schedule attributes published by airlines months in advance. No live or realized operational data after $T-2\text{h}$ enters the feature pipeline.

### Check 2: Date Rollover Across Midnight
* **Source Location**: `src/features/tabular_features.py#L251-281`, `tests/test_tabular_features.py#L173-179`.
* **Audit Finding**:
  1. For flights departing between `00:01` and `01:59`, `departure - pd.Timedelta(hours=2)` correctly decrements both date and time into day $D-1$ (e.g., `2016-01-02 01:15:00` $\rightarrow$ `2016-01-01 23:15:00`).
  2. The pipeline enforces strict calendar integrity: `flight_date.dt.normalize() == departure.dt.normalize()`, ensuring that `CRS_DEP_TIME` never drifts from `FL_DATE`.
  3. Crucially, flights with ambiguous exact midnight departure (`00:00:00`) are explicitly trapped and fail closed:
     ```python
     ambiguous_midnight = (departure.dt.hour == 0) & (departure.dt.minute == 0) & (departure.dt.second == 0)
     if bool(ambiguous_midnight.any()):
         raise ArrivalFeatureContractViolation("exact-midnight CRS_DEP_TIME is blocked because original 0000/2400 semantics are not proven")
     ```

### Check 3: Timezone and Date Semantics
* **Source Location**: `src/features/tabular_features.py#L284-325`, `tests/test_tabular_features.py#L66-80`.
* **Audit Finding**:
  1. BTS On-Time Performance publishes `CRS_DEP_TIME` in local departure airport time and `CRS_ARR_TIME` in local arrival airport time (Eastern Time for ATL).
  2. Features extract scheduled local clock components: departure hour/minute (local origin) and arrival hour/minute (local ATL).
  3. `CRS_ELAPSED_TIME` is the scheduled elapsed flight duration in minutes, which is timezone-invariant.
  4. The codebase **explicitly forbids naive duration calculation** via `CRS_ARR_TIME - CRS_DEP_TIME` (`feature_manifest_arrival_v1_1.json#L94`: `rollover_or_duration_derivation: false`), preventing errors caused by trans-meridian flights or day boundary crossings.

### Check 4: Historical Aggregations and Window Features
* **Source Location**: `configs/model_catalog_v2.yaml`, `src/features/refactored_features.py#L67-179`.
* **Audit Finding**:
  1. In the authoritative core feature set (`schedule_calendar_carrier_route_v1`), **zero historical rolling delay aggregations exist**.
  2. In experimental feature set v1.2, a candidate target-encoding feature `carrier_arrhour_train_median` was explored. Forensic code audit of `compute_carrier_arrhour_median` confirms it was fitted strictly on `train_df` fold rows only (`fit_scope: recomputed independently per fold using train rows only`), with validation targets strictly excluded (`validation_targets_used_for_feature: false`).
  3. More importantly, **this experimental feature was rejected and excluded from `model_catalog_v2.yaml`**. All active core models use the pure static schedule feature set.

### Check 5: Pre-Split Dataset Computations
* **Source Location**: `src/features/tabular_features.py#L372-469`.
* **Audit Finding**: Feature preparation is strictly row-wise and deterministic. Operations consist of datetime parsing and string stripping on isolated chunks/partitions. There is **zero dataset-wide cross-row calculation** performed prior to temporal splitting.

### Check 6: Statistics Fitting (Development vs Full Dataset)
* **Source Location**: `src/data/preprocessing.py#L47-100`, `src/data/access_guard.py`.
* **Audit Finding**:
  1. All transformers (`SimpleImputer`, `StandardScaler`, `OneHotEncoder`, `OrdinalEncoder`, `FrequencyEncoder`) are fitted strictly within cross-validation folds via `fit_boundary: EACH_FOLD_TRAIN_ROWS_ONLY`.
  2. Training rows never see validation rows during transformer fitting.
  3. Row-level reads during development are strictly locked to 2016–2022 via `_assert_week3a_year` and `Week3ATemporalBoundaryError`.

### Check 7: Imputation Strategy and Scope
* **Source Location**: `src/data/preprocessing.py#L109-166`, `src/features/tabular_features.py#L178-201`.
* **Audit Finding**:
  1. Numeric features: Imputed using `SimpleImputer(strategy="median", add_indicator=True)` fitted strictly on fold `X_train`.
  2. Categorical features: Missing values imputed with constant sentinel `__MISSING__` (no learned statistics).
  3. Target imputation: **Strictly forbidden (`target_imputation: false`)**. In the inbound ATL dataset, missing `ARR_DELAY` rows are filtered out prior to training. In Phase P1 forensic inspection, missing target rows in inbound ATL were confirmed to be exactly 0.

### Check 8: Scaling and Encoding Scope
* **Source Location**: `src/data/preprocessing.py#L47-100, 169-237`.
* **Audit Finding**:
  1. `StandardScaler` (linear pipeline): Fitted exclusively on fold `X_train`.
  2. `OneHotEncoder(handle_unknown="ignore")`: Fitted exclusively on fold `X_train`. Unseen categories in validation/test are zero-hot encoded.
  3. `OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)`: Fitted exclusively on fold `X_train`. Unseen categories map to `-1`.
  4. `FrequencyEncoder`: Computes non-target category frequency counts on fold `X_train`. Unseen categories map to `0.0`.

### Check 9: Target-Derived Features
* **Source Location**: `src/data/leakage_rules.py#L43-49`, `src/features/tabular_features.py#L409-413`.
* **Audit Finding**: **Zero target-derived features exist in the Core Arrival feature set**. The target `ARR_DELAY` and its derived labels `y_arr_cls` and `y_arr_reg` are segregated into separate output vectors immediately after row selection and are blocked from `X`.

### Check 10: Disguised Operational Features
* **Source Location**: `src/data/leakage_rules.py#L54-68`.
* **Audit Finding**: Complete schema audit confirms that no realized operational fields (`DEP_TIME`, `WHEELS_OFF`, `WHEELS_ON`, `ARR_TIME`, `TAXI_OUT`, `TAXI_IN`, `AIR_TIME`, `ACTUAL_ELAPSED_TIME`, delay cause flags) are included or renamed as predictors.

### Check 11: Weather Feature Exclusion
* **Source Location**: `src/data/leakage_rules.py#L73-80`, `src/features/tabular_features.py#L476`, `tests/test_weather_contract.py`.
* **Audit Finding**:
  1. All 6 candidate weather features (`O_TEMP`, `O_PRCP`, `O_WSPD`, `D_TEMP`, `D_PRCP`, `D_WSPD`) have status `INSUFFICIENT_EVIDENCE` / `DROP_WEATHER`.
  2. `POINT_IN_TIME_WEATHER_ENABLED = False`.
  3. Any injection of weather columns triggers an immediate `LeakageRuleViolation`.
  4. `configs/model_catalog_v2.yaml` specifies `weather_included: false` across all models.

### Check 12: Flight Chain Policy
* **Source Location**: `src/features/chain_feature_policy.py`, `configs/model_catalog_v2.yaml`.
* **Audit Finding**:
  1. Raw Flight Chain `.pt` tensor modality is permanently retired as `FINAL_NO_GO`.
  2. Reconstructed schedule-chain features are locked out of base models (`included_in_base_matrix: false`).
  3. All Core Arrival models in `configs/model_catalog_v2.yaml` use `schedule_calendar_carrier_route_v1`, with zero flight chain dependencies.

### Check 13: Airport and Gate Outcomes
* **Source Location**: `src/data/leakage_rules.py#L86-97`.
* **Audit Finding**:
  1. `DEST` is dropped as constant (`DEST=ATL`).
  2. `DEST_INDEX`, `D_LATITUDE`, `D_LONGITUDE` are dropped.
  3. Actual gate assignments, remote stands, ramp tracking, and apron turnaround times are completely absent from the feature set. Downstream gate allocation uses synthetic turns and simulated gates without operational feedback into the ML arrival predictor.

---

## 3. AUDIT SUMMARY & CONCLUSION

All 13 approved features in the Core Arrival predictor set originate strictly from static schedule, calendar, carrier, and route metadata available at or before $T-2\text{h}$. Preprocessing transformers (imputers, scalers, encoders) are fitted strictly on fold training rows without cross-validation or holdout leakage. All prohibited operational fields, realized delays, weather parameters, and raw flight chains are strictly excluded.

* **Core feature set valid?**: **YES**
* **GATE_P2**: **PASS**
