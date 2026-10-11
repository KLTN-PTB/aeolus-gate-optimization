# Phase P08: Feature Availability & Information Barrier Matrix

**Document Version:** `1.0.0`  
**Protocol:** Aeolus Predict-then-Optimize V4.0  
**Phase:** P08 ML Research Validation & Explainability  
**Auditor:** Senior ML Research Scientist & Statistical Validation Lead  
**Evaluation Cutoff:** $T - 2\text{h}$ (`CRS_DEP_TIME - 2 hours`, Local Airport Time: `America/New_York`)

---

## 1. Executive Summary & Information Barrier Rules

In predict-then-optimize gate assignment, delays must be predicted strictly before gate reassignment decisions are computed. The Aeolus operational protocol enforces a strict prediction cutoff of **$T - 2\text{h}$ before scheduled departure** (`CRS_DEP_TIME - 2 hours`).

### Core Invariance Principles
1. **Temporal Cutoff Guarantee:** Any candidate feature $X_j$ must have availability timestamp $\tau(X_j) \le \text{CRS\_DEP\_TIME} - 2\text{h}$.
2. **Zero Lookahead on Actual Operations:** No post-cutoff operational event (wheels off, wheels on, taxi times, actual departure/arrival timestamps, actual delay) may enter candidate predictor sets.
3. **Weather Point-in-Time Separation:** Historical METAR/ASOS observations recorded at actual/scheduled departure or arrival times cannot be substituted for Numerical Weather Prediction (NWP) forecasts without cryptographic publication timestamps. All unverified observations are classified as `DROP`.
4. **Reconstructed Chain Integrity:** Without official airline publication schedule snapshot archives, reconstructed flight chains cannot guarantee structural finality at $T - 2\text{h}$ without risk of lookahead contamination. Therefore, all 18 candidate chain features remain `BLOCKED_PENDING_NEW_EVIDENCE`.
5. **Preprocessing Leakage Prohibition:** All encoders, scalers, imputers, and frequency mappers must be fitted strictly inside training folds (`train_years`). Fitting across validation/test folds is strictly forbidden.

---

## 2. Comprehensive Feature Availability Matrix

The matrix classifies all candidate fields into six functional categories:
- **Group A:** Scheduled Tabular Features
- **Group B:** Historical Aggregate Features
- **Group C:** Weather Forecast Features
- **Group D:** Historical Observed Weather
- **Group E:** Reconstructed Flight Chain Features
- **Group F:** Operational Actual / Future Features

| Group | Feature Name | Source | Available At | Prediction Cutoff | Transformation / Encoding | Leakage Risk | Approval Status | Rationale & Policy Reference |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **A** | `CRS_DEP_TIME` | Official Schedule (OAG/BTS) | Published $\ge 24\text{h}$ before | $T - 2\text{h}$ | Extracted scheduled hour & minute | ZERO | `APPROVED` | Scheduled clock timestamp known months in advance. |
| **A** | `CRS_ARR_TIME` | Official Schedule (OAG/BTS) | Published $\ge 24\text{h}$ before | $T - 2\text{h}$ | Extracted scheduled arrival hour & minute | ZERO | `APPROVED` | Scheduled arrival clock known in advance. |
| **A** | `CRS_ELAPSED_TIME` | Official Schedule (OAG/BTS) | Published $\ge 24\text{h}$ before | $T - 2\text{h}$ | Standard scaled / numeric pass-through | ZERO | `APPROVED` | Scheduled block time represents flight planned duration. |
| **A** | `FL_DATE` | Official Schedule | Published $\ge 24\text{h}$ before | $T - 2\text{h}$ | Calendar parsing | ZERO | `APPROVED` | Service calendar date. |
| **A** | `calendar_month` | Derived from `FL_DATE` | Published $\ge 24\text{h}$ before | $T - 2\text{h}$ | Integer / Sin-Cos cyclical | ZERO | `APPROVED` | Captures seasonal baseline trends. |
| **A** | `calendar_day_of_month`| Derived from `FL_DATE` | Published $\ge 24\text{h}$ before | $T - 2\text{h}$ | Integer numeric | ZERO | `APPROVED` | Calendar cycle index. |
| **A** | `calendar_day_of_week` | Derived from `FL_DATE` | Published $\ge 24\text{h}$ before | $T - 2\text{h}$ | Integer numeric (1=Mon ... 7=Sun) | ZERO | `APPROVED` | Captures weekly traffic cycles (weekend vs weekday). |
| **A** | `is_weekend` | Derived from `DAY_OF_WEEK` | Published $\ge 24\text{h}$ before | $T - 2\text{h}$ | Binary indicator $\mathbb{I}[\text{day} \in \{6, 7\}]$ | ZERO | `APPROVED` | Binary weekend traffic indicator. |
| **A** | `scheduled_departure_hour`| Derived from `CRS_DEP_TIME` | Published $\ge 24\text{h}$ before | $T - 2\text{h}$ | Integer numeric (0–23) | ZERO | `APPROVED` | Primary diurnal congestion driver. |
| **A** | `scheduled_departure_minute`| Derived from `CRS_DEP_TIME` | Published $\ge 24\text{h}$ before | $T - 2\text{h}$ | Integer numeric (0–59) | ZERO | `APPROVED` | Sub-hour bank departure scheduling. |
| **A** | `OP_CARRIER` | Official Schedule | Published $\ge 24\text{h}$ before | $T - 2\text{h}$ | One-hot / Ordinal encoded | ZERO | `APPROVED` | Operating carrier code (DL, AA, WN, etc.). |
| **A** | `ORIGIN` | Official Schedule | Published $\ge 24\text{h}$ before | $T - 2\text{h}$ | One-hot / Ordinal encoded | ZERO | `APPROVED` | Origin airport IATA code (fixed to ATL for Outbound). |
| **A** | `DEST` | Official Schedule | Published $\ge 24\text{h}$ before | $T - 2\text{h}$ | One-hot / Ordinal encoded | ZERO | `APPROVED` | Destination airport IATA code (fixed to ATL for Inbound). |
| **A** | `OP_CARRIER_FL_NUM` | Official Schedule | Published $\ge 24\text{h}$ before | $T - 2\text{h}$ | Training-fold frequency encoding | ZERO | `APPROVED` | High-cardinality flight identifier. |
| **B** | `carrier_historical_mean_delay` | BTS Training History | In-fold train window | $T - 2\text{h}$ | Aggregated exclusively on train fold | LOW | `REVIEW_REQUIRED` | Permitted only if strictly lagged and fit within train fold. |
| **B** | `carrier_hour_congestion_rate`| BTS Training History | In-fold train window | $T - 2\text{h}$ | Historical carrier delay by time-of-day | LOW | `REVIEW_REQUIRED` | Must not compute across validation/test folds. |
| **C** | `nwp_terminal_forecast_wind` | NOAA HRRR / TAF | Issued $T - 3\text{h}$ to $T - 2\text{h}$ | $T - 2\text{h}$ | Weather feature pipeline | MEDIUM | `BLOCKED_NO_DATA` | Desirable, but external HRRR point-in-time archive not provided in dataset. |
| **C** | `nwp_terminal_forecast_precip`| NOAA HRRR / TAF | Issued $T - 3\text{h}$ to $T - 2\text{h}$ | $T - 2\text{h}$ | Weather feature pipeline | MEDIUM | `BLOCKED_NO_DATA` | Desirable, but not materialized in dataset. |
| **D** | `O_TEMP` | METAR Surface Obs | Scheduled origin departure time | $T - 2\text{h}$ (FAILS) | None (Raw temperature) | CRITICAL | `DROP` | Ground station METAR observation measured at flight time, NOT forecast at $T-2\text{h}$. |
| **D** | `O_PRCP` | METAR Surface Obs | Scheduled origin departure time | $T - 2\text{h}$ (FAILS) | None (Raw precipitation) | CRITICAL | `DROP` | Future observation lookahead leak. |
| **D** | `O_WSPD` | METAR Surface Obs | Scheduled origin departure time | $T - 2\text{h}$ (FAILS) | None (Raw wind speed) | CRITICAL | `DROP` | Future observation lookahead leak. |
| **D** | `D_TEMP` | METAR Surface Obs | Scheduled destination arrival time | $T - 2\text{h}$ (FAILS) | None (Raw temperature) | CRITICAL | `DROP` | Recorded at arrival time (hours after departure). |
| **D** | `D_PRCP` | METAR Surface Obs | Scheduled destination arrival time | $T - 2\text{h}$ (FAILS) | None (Raw precipitation) | CRITICAL | `DROP` | Recorded at arrival time. |
| **D** | `D_WSPD` | METAR Surface Obs | Scheduled destination arrival time | $T - 2\text{h}$ (FAILS) | None (Raw wind speed) | CRITICAL | `DROP` | Recorded at arrival time. |
| **E** | `chain_position` | Reconstructed Chain | Post-hoc schedule grouping | $T - 2\text{h}$ (UNVERIFIED) | Integer leg index | HIGH | `BLOCKED_PENDING_NEW_EVIDENCE` | Without schedule publication snapshot, chain topology at $T-2\text{h}$ is unverified. |
| **E** | `legs_before_target` | Reconstructed Chain | Post-hoc schedule grouping | $T - 2\text{h}$ (UNVERIFIED) | Count of prior legs | HIGH | `BLOCKED_PENDING_NEW_EVIDENCE` | Risk of lookahead into full daily schedule revisions. |
| **E** | `is_first_chain_leg` | Reconstructed Chain | Post-hoc schedule grouping | $T - 2\text{h}$ (UNVERIFIED) | Binary indicator | HIGH | `BLOCKED_PENDING_NEW_EVIDENCE` | Unverified availability at $T-2\text{h}$. |
| **E** | `minutes_from_first_dep`| Reconstructed Chain | Post-hoc schedule grouping | $T - 2\text{h}$ (UNVERIFIED) | Elapsed minutes | HIGH | `BLOCKED_PENDING_NEW_EVIDENCE` | Unverified availability at $T-2\text{h}$. |
| **E** | `has_previous_chain_leg`| Reconstructed Chain | Post-hoc schedule grouping | $T - 2\text{h}$ (UNVERIFIED) | Binary indicator | HIGH | `BLOCKED_PENDING_NEW_EVIDENCE` | Unverified availability at $T-2\text{h}$. |
| **E** | `chain_length` | Reconstructed Chain | Full daily schedule grouping | End-of-day (FAILS) | Integer total legs in chain | CRITICAL | `BLOCKED_UNTIL_PROVEN` | Full chain length knows total future legs flown in day. |
| **E** | `legs_after_target` | Reconstructed Chain | Full daily schedule grouping | End-of-day (FAILS) | Count of subsequent legs | CRITICAL | `BLOCKED_UNTIL_PROVEN` | Direct future information leakage. |
| **E** | `is_last_chain_leg` | Reconstructed Chain | Full daily schedule grouping | End-of-day (FAILS) | Binary indicator | CRITICAL | `BLOCKED_UNTIL_PROVEN` | Direct future information leakage. |
| **F** | `DEP_TIME` | Actual Airport Sensor | Actual pushback time | $T$ (FAILS) | Actual departure clock | FATAL | `REJECTED_LEAKAGE` | Realized outcome; strictly forbidden. |
| **F** | `DEP_DELAY` | Derived from `DEP_TIME` | Actual pushback time | $T$ (FAILS) | Signed delay minutes | FATAL | `TARGET_ONLY` | Primary Departure prediction target; forbidden as predictor. |
| **F** | `TAXI_OUT` | Actual Surface Sensor | Takeoff time - Pushback | After takeoff (FAILS) | Elapsed surface taxi | FATAL | `REJECTED_LEAKAGE` | Occurs post-cutoff; forbidden. |
| **F** | `WHEELS_OFF` | ADS-B / Surface Sensor | Takeoff time | After takeoff (FAILS) | Takeoff timestamp | FATAL | `REJECTED_LEAKAGE` | Occurs post-cutoff; forbidden. |
| **F** | `AIR_TIME` | ADS-B Radar | Landing time - Takeoff | After landing (FAILS) | Flight airborne duration | FATAL | `REJECTED_LEAKAGE` | Occurs post-cutoff; forbidden. |
| **F** | `WHEELS_ON` | ADS-B / Runway Sensor | Touchdown time | After landing (FAILS) | Touchdown timestamp | FATAL | `REJECTED_LEAKAGE` | Occurs post-cutoff; forbidden. |
| **F** | `TAXI_IN` | Actual Surface Sensor | Gate arrival - Touchdown | At gate arrival (FAILS) | Elapsed inbound taxi | FATAL | `REJECTED_LEAKAGE` | Occurs post-cutoff; forbidden. |
| **F** | `ARR_TIME` | Gate Sensor / ADS-B | Actual gate arrival | At destination gate (FAILS)| Gate arrival clock | FATAL | `REJECTED_LEAKAGE` | Occurs post-cutoff; forbidden. |
| **F** | `ARR_DELAY` | Derived from `ARR_TIME` | Actual gate arrival | At destination gate (FAILS)| Signed delay minutes | FATAL | `TARGET_ONLY` | Primary Arrival prediction target; forbidden as predictor. |
| **F** | `ACTUAL_ELAPSED_TIME` | Actual Flight Outcome | At destination gate | At destination gate (FAILS)| Total actual duration | FATAL | `REJECTED_LEAKAGE` | Occurs post-cutoff; forbidden. |

---

## 3. Approved Production Feature Sets

### 3.1 Core Arrival Feature Schema (11 Features)
Defined in [`src/features/tabular_features.py`](file:///D:/Study/Code/Python/Aelous/src/features/tabular_features.py#L98-L107):
1. `CRS_ELAPSED_TIME` (Numeric)
2. `calendar_year` (Numeric)
3. `calendar_month` (Numeric)
4. `calendar_day_of_month` (Numeric)
5. `calendar_day_of_week` (Numeric)
6. `is_weekend` (Numeric binary)
7. `scheduled_departure_hour` (Numeric)
8. `scheduled_departure_minute` (Numeric)
9. `OP_CARRIER` (Categorical)
10. `ORIGIN` (Categorical)
11. `OP_CARRIER_FL_NUM` (High cardinality, frequency-encoded)

### 3.2 Core Departure Feature Schema (10 Features)
Defined in [`src/features/departure_features.py`](file:///D:/Study/Code/Python/Aelous/src/features/departure_features.py#L69-L80):
1. `CRS_ELAPSED_TIME` (Numeric)
2. `calendar_month` (Numeric)
3. `calendar_day_of_month` (Numeric)
4. `calendar_day_of_week` (Numeric)
5. `is_weekend` (Numeric binary)
6. `scheduled_departure_hour` (Numeric)
7. `scheduled_departure_minute` (Numeric)
8. `OP_CARRIER` (Categorical)
9. `DEST` (Categorical)
10. `OP_CARRIER_FL_NUM` (High cardinality, frequency-encoded)

---

## 4. Scientific Verification Sign-off

- **Audit Result:** Exactly 11 Core Arrival and 10 Core Departure features are approved for production ML inference.
- **Leakage Integrity:** All 10 tested actual operational features and 6 weather observation features are rejected fail-closed.
- **Verification Tests:** Verified by automated tests [`test_ml02_feature_available_at_lte_cutoff`](file:///D:/Study/Code/Python/Aelous/tests/test_ml_research_validation_p08.py#L82), [`test_ml03_future_actual_feature_rejected`](file:///D:/Study/Code/Python/Aelous/tests/test_ml_research_validation_p08.py#L98), and [`test_ml04_future_weather_observation_rejected`](file:///D:/Study/Code/Python/Aelous/tests/test_ml_research_validation_p08.py#L110).
