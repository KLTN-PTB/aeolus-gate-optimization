# Aeolus Tabular Data Dictionary V0

## Status and scope

This is an initial, evidence-limited dictionary derived only from the header of `data/raw/tabular/2016/flight_with_weather_2016.csv`. It is **not** the canonical schema. The canonical schema may be frozen only after the year-by-year 2016–2024 schema audit planned for Week 2.

Inspection method: the first CSV record was read with Python's standard CSV parser. No data row was read, no full-file scan was performed, and no 2017–2024 file content was opened. Semantic descriptions below are therefore provisional guesses from column names plus the locked V3 roadmap decisions.

`SAFE_CANDIDATE` means only “logically plausible at prediction time and eligible for audit.” It does not mean the field is finally approved for the model.

## Prediction-time contract

The core prediction cut-off is locked as:

`T_cutoff = CRS_DEP_TIME - 2 hours`

A feature may enter `X` only when every piece of information used to create it is demonstrably available at or before `T_cutoff`. Future realized information, including actual movement times and post-operation durations or delays, must not enter predictors. Availability must be established from provenance and timestamp evidence; a clear-looking column name is insufficient.

This contract implements D008 in the decision registry and applies before feature engineering, encoding, aggregation, imputation, or joining optional data.

## Observed 2016 columns

Availability-status values in this table are audit states, not claims about the final schema.

| # | Column | Observed name | Semantic guess | Role | Availability status | Reason | Verification needed |
|---:|---|---|---|---|---|---|---|
| 1 | `FL_DATE` | `FL_DATE` | Scheduled/operating flight date | SAFE_CANDIDATE | Provisional: likely known by T-2h | Calendar date is logically pre-flight information. | Confirm parsing, timezone/date semantics, nulls, and cross-year consistency. |
| 2 | `OP_CARRIER` | `OP_CARRIER` | Operating carrier code | SAFE_CANDIDATE | Provisional: likely known by T-2h | Carrier is normally part of the published schedule. | Confirm code semantics, effective-date changes, cardinality, and availability provenance. |
| 3 | `OP_CARRIER_FL_NUM` | `OP_CARRIER_FL_NUM` | Operating carrier flight number | IDENTIFIER_OR_HIGH_CARDINALITY | Likely scheduled, but restricted pending review | It may aid traceability but can be high-cardinality and may encode route/schedule patterns unsafely. | Audit cardinality, reuse, temporal-safe encoding, stability, and whether it should be excluded from `X`. |
| 4 | `ORIGIN` | `ORIGIN` | Origin airport code | SAFE_CANDIDATE | Provisional: likely known by T-2h | Origin is scheduled route information; core inbound filtering uses destination ATL. | Confirm code system, missingness, cardinality, and cross-year stability. |
| 5 | `DEST` | `DEST` | Destination airport code | SAFE_CANDIDATE | Provisional: likely known by T-2h | Destination is scheduled route information; `DEST=ATL` defines core inbound ML scope. | Confirm code system, missingness, cardinality, and cross-year stability. |
| 6 | `CRS_DEP_TIME` | `CRS_DEP_TIME` | Computer Reservation System scheduled departure time | SAFE_CANDIDATE | Provisional: cut-off anchor | This scheduled field defines `T_cutoff` and is expected before prediction. | Confirm HHMM semantics, timezone, date rollover, revisions, nulls, and parsing rules. |
| 7 | `DEP_TIME` | `DEP_TIME` | Actual departure time | LEAKAGE | Post-cutoff realized operation; prohibited in `X` | Actual departure is future realized information relative to the pre-flight cut-off. | Confirm exact operational definition only for label/evaluation handling; never approve as predictor at T-2h. |
| 8 | `DEP_DELAY` | `DEP_DELAY` | Realized departure delay in minutes | LEAKAGE | Post-cutoff realized operation; prohibited in `X` | It depends on actual departure and is not available at T-2h. | Confirm units/sign and missingness for audit/evaluation only. |
| 9 | `TAXI_OUT` | `TAXI_OUT` | Realized taxi-out duration | LEAKAGE | Post-cutoff realized operation; prohibited in `X` | Taxi-out is observed after departure operations begin. | Confirm units and missingness for audit/evaluation only. |
| 10 | `WHEELS_OFF` | `WHEELS_OFF` | Actual wheels-off time | LEAKAGE | Post-cutoff realized operation; prohibited in `X` | This is a realized movement timestamp. | Confirm parsing/timezone/rollover for audit/evaluation only. |
| 11 | `WHEELS_ON` | `WHEELS_ON` | Actual wheels-on time | LEAKAGE | Post-cutoff realized operation; prohibited in `X` | This is a realized arrival timestamp. | Confirm parsing/timezone/rollover for audit/evaluation only. |
| 12 | `TAXI_IN` | `TAXI_IN` | Realized taxi-in duration | LEAKAGE | Post-cutoff realized operation; prohibited in `X` | Taxi-in is observed after landing. | Confirm units and missingness for audit/evaluation only. |
| 13 | `CRS_ARR_TIME` | `CRS_ARR_TIME` | Scheduled arrival time | SAFE_CANDIDATE | Provisional: likely known by T-2h | Scheduled arrival is logically part of the pre-flight schedule. | Confirm HHMM semantics, timezone, date rollover, revisions, and nulls. |
| 14 | `ARR_TIME` | `ARR_TIME` | Actual arrival time | LEAKAGE | Post-cutoff realized operation; prohibited in `X` | Actual arrival is future realized information. | Confirm exact operational definition only for target/evaluation handling. |
| 15 | `ARR_DELAY` | `ARR_DELAY` | Realized signed arrival delay in minutes | TARGET | Post-outcome target only; prohibited in `X` | D010 locks this field as the signed regression target; D009 derives classification from it. | Confirm dtype, units, sign, missingness, cancellation/diversion handling, and cross-year availability. |
| 16 | `CRS_ELAPSED_TIME` | `CRS_ELAPSED_TIME` | Scheduled elapsed time | SAFE_CANDIDATE | Provisional: likely known by T-2h | Scheduled duration is logically available from the itinerary. | Confirm units, derivation, revision timing, nulls, and consistency with scheduled timestamps. |
| 17 | `ACTUAL_ELAPSED_TIME` | `ACTUAL_ELAPSED_TIME` | Realized elapsed time | LEAKAGE | Post-cutoff realized operation; prohibited in `X` | It is computed from completed operation times. | Confirm units and missingness for audit/evaluation only. |
| 18 | `AIR_TIME` | `AIR_TIME` | Realized airborne duration | LEAKAGE | Post-cutoff realized operation; prohibited in `X` | It is known only after flight operation. | Confirm units and missingness for audit/evaluation only. |
| 19 | `FLIGHTS` | `FLIGHTS` | Unknown flight-related measure | UNCERTAIN | Semantics unknown | The name does not establish meaning, grain, or prediction-time admissibility; T002 remains open. | Obtain source documentation and audit values/distribution without inferring semantics from the name. |
| 20 | `MONTH` | `MONTH` | Calendar month | SAFE_CANDIDATE | Provisional: known by T-2h | It is derivable from a known scheduled date. | Confirm consistency with `FL_DATE`, dtype, range, and cross-year representation. |
| 21 | `DAY_OF_MONTH` | `DAY_OF_MONTH` | Calendar day of month | SAFE_CANDIDATE | Provisional: known by T-2h | It is derivable from a known scheduled date. | Confirm consistency with `FL_DATE`, dtype, and valid range. |
| 22 | `DAY_OF_WEEK` | `DAY_OF_WEEK` | Encoded calendar weekday | SAFE_CANDIDATE | Provisional: known by T-2h | It is derivable from a known scheduled date. | Confirm coding convention, consistency with `FL_DATE`, dtype, and valid range. |
| 23 | `ORIGIN_INDEX` | `ORIGIN_INDEX` | Numeric encoding/index for origin airport | UNCERTAIN | Conditional on cross-year mapping audit | Numeric index meaning may drift across years and cannot be inferred from the 2016 header. | Prove mapping to `ORIGIN`, uniqueness, stability for 2016–2024, and temporal-safe use (T003). |
| 24 | `DEST_INDEX` | `DEST_INDEX` | Numeric encoding/index for destination airport | UNCERTAIN | Conditional on cross-year mapping audit | Numeric index meaning may drift across years and cannot be inferred from the 2016 header. | Prove mapping to `DEST`, uniqueness, stability for 2016–2024, and temporal-safe use (T003). |
| 25 | `O_TEMP` | `O_TEMP` | Origin-side temperature | UNCERTAIN | T-2h provenance/timestamp unverified | The header does not show whether this is an observation, forecast, aggregation, or future value. | Establish source, station/join logic, units, observation/forecast issue time, valid time, and availability by T-2h (T001). |
| 26 | `O_PRCP` | `O_PRCP` | Origin-side precipitation | UNCERTAIN | T-2h provenance/timestamp unverified | The header does not show whether this is an observation, forecast, aggregation, or future value. | Establish source, station/join logic, units/window, issue/valid time, and availability by T-2h (T001). |
| 27 | `O_WSPD` | `O_WSPD` | Origin-side wind speed | UNCERTAIN | T-2h provenance/timestamp unverified | The header does not show whether this is an observation, forecast, aggregation, or future value. | Establish source, station/join logic, units, issue/valid time, and availability by T-2h (T001). |
| 28 | `D_TEMP` | `D_TEMP` | Destination-side temperature | UNCERTAIN | T-2h provenance/timestamp unverified | The header does not show whether this is an observation, forecast, aggregation, or future value. | Establish source, station/join logic, units, observation/forecast issue time, valid time, and availability by T-2h (T001). |
| 29 | `D_PRCP` | `D_PRCP` | Destination-side precipitation | UNCERTAIN | T-2h provenance/timestamp unverified | The header does not show whether this is an observation, forecast, aggregation, or future value. | Establish source, station/join logic, units/window, issue/valid time, and availability by T-2h (T001). |
| 30 | `D_WSPD` | `D_WSPD` | Destination-side wind speed | UNCERTAIN | T-2h provenance/timestamp unverified | The header does not show whether this is an observation, forecast, aggregation, or future value. | Establish source, station/join logic, units, issue/valid time, and availability by T-2h (T001). |
| 31 | `O_LATITUDE` | `O_LATITUDE` | Origin airport/station latitude | SAFE_CANDIDATE | Provisional: static lookup likely available by T-2h | Static geography is logically available before flight, but the referenced entity is not proven by the header. | Confirm whether coordinate belongs to airport or weather station, source, units/CRS, join logic, nulls, and cross-year stability. |
| 32 | `O_LONGITUDE` | `O_LONGITUDE` | Origin airport/station longitude | SAFE_CANDIDATE | Provisional: static lookup likely available by T-2h | Static geography is logically available before flight, but the referenced entity is not proven by the header. | Confirm whether coordinate belongs to airport or weather station, source, units/CRS, join logic, nulls, and cross-year stability. |
| 33 | `D_LATITUDE` | `D_LATITUDE` | Destination airport/station latitude | SAFE_CANDIDATE | Provisional: static lookup likely available by T-2h | Static geography is logically available before flight, but the referenced entity is not proven by the header. | Confirm whether coordinate belongs to airport or weather station, source, units/CRS, join logic, nulls, and cross-year stability. |
| 34 | `D_LONGITUDE` | `D_LONGITUDE` | Destination airport/station longitude | SAFE_CANDIDATE | Provisional: static lookup likely available by T-2h | Static geography is logically available before flight, but the referenced entity is not proven by the header. | Confirm whether coordinate belongs to airport or weather station, source, units/CRS, join logic, nulls, and cross-year stability. |

## Target derivation

- Regression: `y_reg = ARR_DELAY`, preserving signed minutes (negative, zero, and positive) under D010.
- Classification: `y_cls = 1` when `ARR_DELAY >= 15`, otherwise `0`, under D009.
- `y_cls` is a derived target and is **not** one of the 34 observed header columns.
- Neither target may be included in `X`. Actual-operation fields remain label/evaluation-only where appropriate.

## Role summary

| Role | Count |
|---|---:|
| SAFE_CANDIDATE | 14 |
| TARGET | 1 |
| LEAKAGE | 9 |
| UNCERTAIN | 9 |
| IDENTIFIER_OR_HIGH_CARDINALITY | 1 |
| CONSTANT_OR_REVIEW_NEEDED | 0 |
| **Total observed columns** | **34** |

These counts classify only the observed 2016 header. They do not assert that later years have the same columns or that any candidate has passed Week 2 audit.

## Unknown register

| ID | Unknown | Current state | Evidence needed / next action |
|---|---|---|---|
| U001 | Weather observation/forecast timing | OPEN; all six weather fields remain `UNCERTAIN`. | Establish provenance, issue/observation timestamp, valid time, join logic, and proof of availability at or before T-2h; otherwise lag or drop. |
| U002 | `FLIGHTS` semantics | OPEN; `FLIGHTS` remains `UNCERTAIN`. | Obtain source documentation and audit grain/values; do not infer meaning from its name. |
| U003 | Cross-year airport-index stability | OPEN; `ORIGIN_INDEX` and `DEST_INDEX` remain `UNCERTAIN`. | Build and compare per-year mappings against airport codes for 2016–2024 before candidate use. |
| U004 | Cross-year schema drift | OPEN; only the 2016 header was inspected here. | Run the planned year-by-year Week 2 schema audit and compatibility matrix before defining canonical schema. |
| U005 | Cancelled/diverted representation | OPEN; no explicit cancellation/diversion column appears in the observed 2016 header. | Determine whether such cases are omitted, encoded through target/time missingness, or represented differently; do not infer from absence of header fields. |
| U006 | Flight Chain mapping semantics | OPEN and deliberately out of scope for this dictionary. | Resolve through the separate Flight Chain feasibility audit and GO/NO-GO; do not load `.pt` files or treat their train/val/test names as thesis temporal splits here. |

## Cross-check with locked decisions

- **D003:** This dictionary covers Tabular as the core data source; Flight Chain is not incorporated.
- **D004 / T004:** Flight Chain stays optional and unresolved pending its separate feasibility audit; no aircraft identity or rotation is inferred.
- **D006 / D007:** `ORIGIN` and `DEST` are retained as candidates needed to express inbound `DEST=ATL` for ML and outbound `ORIGIN=ATL` for simulation. This file does not perform either filter.
- **D008:** The T-2h prediction contract is explicit, and actual-operation fields are barred from predictors.
- **D009 / D010:** Classification and signed regression targets are documented exactly as locked.
- **D011 / D020:** This V0 uses only the 2016 header; it does not inspect or use 2024 content or results.
- **D013:** Raw Aeolus data was read only at the header boundary and was not modified.
- **D014:** No actual or synthetic aircraft identity is introduced. `OP_CARRIER_FL_NUM` is treated as a high-cardinality identifier candidate, not aircraft identity.
- **T001 / T002 / T003:** Weather timing, `FLIGHTS` semantics, and airport-index stability remain open rather than being promoted to locked facts.

No mismatch with the three synchronized V3 roadmap documents or `docs/decisions/decision_registry.md` was identified at V0 scope.
