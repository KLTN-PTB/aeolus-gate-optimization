# Aeolus Tabular Data Dictionary V1

## Status and contract

V1 is evidence-based on the complete 2016–2024 schema audit, canonical schema
v1, cross-year airport-index mapping audit, processed ATL partitions, and the
historical V3 prediction contract used in Week 2. It supersedes V0 for Week-2
leakage status but does not replace the canonical storage schema. The dated V4
addendum below defines current task-specific interpretation without rewriting
the evidence table.

Core cutoff: `T_cutoff = CRS_DEP_TIME - 2 hours`. Statuses are `SAFE`, `TARGET`, `LEAKAGE`, `UNCERTAIN`, `INSUFFICIENT_EVIDENCE`, `IDENTIFIER_ONLY`, `DROP_CONSTANT`, and `CONDITIONAL`. For weather, `INSUFFICIENT_EVIDENCE` triggers the fail-closed core policy `DROP`; it does not assert that a specific future timestamp was used.

All canonical fields are present in 2016–2024 with compatible dtype/order. “Week-3 action” is a contract for later work, not preprocessing performed here.

| Canonical name | Years | Role | T-2h availability | Evidence | Final Week-2 status | Week-3 action |
|---|---|---|---|---|---|---|
| `FL_DATE` | 2016–2024 | Schedule date | Available | Full-year date coverage; V3 schedule contract | SAFE | Parse date inside fold-safe pipeline; retain as source for calendar features. |
| `OP_CARRIER` | 2016–2024 | Scheduled carrier | Available | Present all years; scheduled carrier metadata | SAFE | Categorical handling fit within each temporal fold. |
| `OP_CARRIER_FL_NUM` | 2016–2024 | Scheduled flight number | Available | Scheduled/natural metadata; no outcome component | SAFE | Review high cardinality; any encoding must be temporal-fold fitted. |
| `ORIGIN` | 2016–2024 | Scheduled origin airport | Available | Route known pre-flight; stable canonical string | SAFE | Use categorical route information with fold-safe handling. |
| `DEST` | 2016–2024 | Scheduled destination/filter | Available but constant for core inbound | Every inbound partition is `DEST=ATL`; one distinct value/year | DROP_CONSTANT | Retain in storage/validation; exclude from inbound candidate `X`. |
| `CRS_DEP_TIME` | 2016–2024 | Scheduled departure/cutoff anchor | Available | Explicit CRS scheduled field; defines locked cutoff | SAFE | Parse HHMM/date rollover; derive `T_cutoff` in Week 3. |
| `DEP_TIME` | 2016–2024 | Actual departure time | After cutoff/realized | V3 explicitly forbids actual departure in pre-flight `X` | LEAKAGE | Exclude from predictors; audit/evaluation only. |
| `DEP_DELAY` | 2016–2024 | Realized departure delay | After cutoff/realized | Depends on actual departure | LEAKAGE | Exclude from predictors. |
| `TAXI_OUT` | 2016–2024 | Realized taxi-out duration | After cutoff/realized | Observed after departure operation begins | LEAKAGE | Exclude from predictors. |
| `WHEELS_OFF` | 2016–2024 | Actual wheels-off time | After cutoff/realized | Actual movement timestamp | LEAKAGE | Exclude from predictors. |
| `WHEELS_ON` | 2016–2024 | Actual wheels-on time | After cutoff/realized | Actual arrival movement timestamp | LEAKAGE | Exclude from predictors. |
| `TAXI_IN` | 2016–2024 | Realized taxi-in duration | After cutoff/realized | Observed after landing | LEAKAGE | Exclude from predictors. |
| `CRS_ARR_TIME` | 2016–2024 | Scheduled arrival time | Available | Scheduled itinerary field in V3 contract | SAFE | Parse with timezone/date-rollover rules. |
| `ARR_TIME` | 2016–2024 | Actual arrival time | After cutoff/realized | Future realized outcome timestamp | LEAKAGE | Exclude from predictors. |
| `ARR_DELAY` | 2016–2024 | Signed regression target | Outcome only | Locked D010; finite and present in all audited rows | TARGET | Produce `y_reg` only; never include in `X`; do not clip target. |
| `CRS_ELAPSED_TIME` | 2016–2024 | Scheduled elapsed minutes | Available | Scheduled itinerary duration, present/compatible all years | SAFE | Validate units; retain as schedule predictor. |
| `ACTUAL_ELAPSED_TIME` | 2016–2024 | Realized elapsed duration | After cutoff/realized | Computed from completed operation | LEAKAGE | Exclude from predictors. |
| `AIR_TIME` | 2016–2024 | Realized airborne duration | After cutoff/realized | Known only after operation | LEAKAGE | Exclude from predictors. |
| `FLIGHTS` | 2016–2024 | Unknown measure | Unknown | Canonical schema confirms presence/dtype but not semantics or timing | UNCERTAIN | Keep blocked; resolve from source documentation or drop. |
| `MONTH` | 2016–2024 | Calendar month | Available | Deterministically available from scheduled date | SAFE | Validate against `FL_DATE`; avoid redundant representation if appropriate. |
| `DAY_OF_MONTH` | 2016–2024 | Calendar day | Available | Deterministically available from scheduled date | SAFE | Validate against `FL_DATE`. |
| `DAY_OF_WEEK` | 2016–2024 | Calendar weekday | Available | Deterministically available from scheduled date | SAFE | Confirm coding convention; transform only in Week 3. |
| `ORIGIN_INDEX` | 2016–2024 | Origin airport index | Available; modelling treatment conditional | Streaming mapping audit proves `ORIGIN -> ORIGIN_INDEX` stable with no conflicts | CONDITIONAL | Prefer airport code or explicitly document non-ordinal encoding; blocked by default. |
| `DEST_INDEX` | 2016–2024 | Destination airport index | Available but constant for core inbound | Mapping stable; one distinct value/year after `DEST=ATL` | DROP_CONSTANT | Retain in storage; exclude from inbound candidate `X`. |
| `O_TEMP` | 2016–2024 | Origin weather temperature | Not proven | Aeolus identifies Meteostat hourly measurements, but released data/code omit valid time, availability/issue time, source/model-fill flag, and join logic | INSUFFICIENT_EVIDENCE | Core DROP: retain in storage, exclude from candidate `X`; no heuristic lag. |
| `O_PRCP` | 2016–2024 | Origin precipitation | Not proven | Same provenance gap as `O_TEMP`; no per-value observation/publication metadata | INSUFFICIENT_EVIDENCE | Core DROP: retain in storage, exclude from candidate `X`; no heuristic lag. |
| `O_WSPD` | 2016–2024 | Origin wind speed | Not proven | Same provenance gap as `O_TEMP`; no per-value observation/publication metadata | INSUFFICIENT_EVIDENCE | Core DROP: retain in storage, exclude from candidate `X`; no heuristic lag. |
| `D_TEMP` | 2016–2024 | Destination weather temperature | Not proven | Destination join anchor and valid/availability time are undocumented | INSUFFICIENT_EVIDENCE | Core DROP: retain in storage, exclude from candidate `X`; no heuristic lag. |
| `D_PRCP` | 2016–2024 | Destination precipitation | Not proven | Destination join anchor and valid/availability time are undocumented | INSUFFICIENT_EVIDENCE | Core DROP: retain in storage, exclude from candidate `X`; no heuristic lag. |
| `D_WSPD` | 2016–2024 | Destination wind speed | Not proven | Destination join anchor and valid/availability time are undocumented | INSUFFICIENT_EVIDENCE | Core DROP: retain in storage, exclude from candidate `X`; no heuristic lag. |
| `O_LATITUDE` | 2016–2024 | Origin-side coordinate | Logically static; entity mapping not fully proven | Compatible numeric field, but airport-vs-station provenance remains open | CONDITIONAL | Verify entity/mapping; use only after explicit review or derive from approved airport lookup. |
| `O_LONGITUDE` | 2016–2024 | Origin-side coordinate | Logically static; entity mapping not fully proven | Compatible numeric field, but airport-vs-station provenance remains open | CONDITIONAL | Verify entity/mapping; use only after explicit review or derive from approved airport lookup. |
| `D_LATITUDE` | 2016–2024 | Destination-side coordinate | Constant for core inbound | One distinct value/year in all inbound ATL partitions | DROP_CONSTANT | Retain in storage; exclude from inbound candidate `X`. |
| `D_LONGITUDE` | 2016–2024 | Destination-side coordinate | Constant for core inbound | One distinct value/year in all inbound ATL partitions | DROP_CONSTANT | Retain in storage; exclude from inbound candidate `X`. |
| `y_cls` (derived) | 2016–2024 | Classification target | Outcome only | Locked formula `1[ARR_DELAY >= 15]` | TARGET | Derive from target only when constructing labels; never include in `X`. |
| `flight_key` (processed) | 2016–2024 | Traceability identifier | Not predictor information | I002; excludes actual/target fields; uniqueness checked during materialization | IDENTIFIER_ONLY | Preserve for joins/tracing; always exclude from `X`. |
| `source_row_number` (processed) | 2016–2024 | Source traceability | Not predictor information | Stable source ordinal recorded during materialization | IDENTIFIER_ONLY | Preserve for audit only; always exclude from `X`. |
| `source_year` (processed) | 2016–2024 | Partition/provenance identifier | Not approved predictor | Manifest role and source partition metadata | IDENTIFIER_ONLY | Use for folds/partitioning, not as candidate `X`. |

## Status summary

- SAFE: 10 canonical fields.
- TARGET: 1 canonical field plus derived `y_cls`.
- LEAKAGE: 9 canonical fields.
- UNCERTAIN: 1 canonical field (`FLIGHTS`).
- INSUFFICIENT_EVIDENCE: 6 canonical weather fields; all are dropped from core candidate `X` by policy.
- CONDITIONAL: 3 canonical fields.
- DROP_CONSTANT: 4 canonical fields for inbound ATL.
- IDENTIFIER_ONLY: 3 processed traceability fields.

No feature was promoted using target distribution, correlation, model importance, or 2024 performance.

## V4 task-specific addendum — 2026-08-26

The storage schema is unchanged. The current predictor/target interpretation is
task-aware:

| Field family | Core Arrival `DEST=ATL` | Auxiliary Departure `ORIGIN=ATL` |
|---|---|---|
| `ARR_DELAY`, `y_arr_cls`, `y_arr_reg` | TARGET | LEAKAGE / FUTURE_OUTCOME |
| `DEP_DELAY`, `y_dep_cls` | LEAKAGE | TARGET |
| Other actual-operation fields | LEAKAGE | LEAKAGE |
| Six raw Aeolus Weather fields | `INSUFFICIENT_EVIDENCE`, DROP | `INSUFFICIENT_EVIDENCE`, DROP |
| `DEST`, `DEST_INDEX`, `D_LATITUDE`, `D_LONGITUDE` | DROP_CONSTANT | `DEST` SAFE; index/coordinates CONDITIONAL |
| `ORIGIN`, `ORIGIN_INDEX`, `O_LATITUDE`, `O_LONGITUDE` | `ORIGIN` SAFE; index/coordinates CONDITIONAL | DROP_CONSTANT |
| Traceability identifiers | IDENTIFIER_ONLY | IDENTIFIER_ONLY |

`y_cls` in the historical Week-2 table is superseded for new code by
`y_arr_cls`; signed Arrival regression uses `y_arr_reg`; Departure uses
`y_dep_cls`. `DEP_DELAY` becomes a target only for the auxiliary task and
remains forbidden for Core Arrival.

Core Arrival uses no Weather. External `weather_point_in_time_v1` is a separate
future source, not a canonical Aeolus column family; it remains
`AUDIT_REQUIRED` and disabled until an explicit audited contract is approved.
Unknown fields and unknown tasks fail closed. No evidence or stored row was
changed by this addendum.

## Week 3A implementation addendum — 2026-08-26

Core Arrival Week 3A implements the SAFE Schedule/Calendar/Carrier/Route
information set with a stricter fail-closed feature contract. `FL_DATE` and
`CRS_DEP_TIME` are source-only inputs for calendar/departure-clock features and
the T-2h cutoff. Existing `MONTH`, `DAY_OF_MONTH`, and `DAY_OF_WEEK` values are
checked against `FL_DATE`. `CRS_ELAPSED_TIME` is retained as the audited
scheduled-duration predictor.

Although `CRS_ARR_TIME` remains scheduled information, the canonical audit
does not prove its overnight/date-rollover semantics. Week 3A therefore marks
it `REVIEW_REQUIRED` for derived use and does not create a naive elapsed-time
or overnight feature. `ORIGIN_INDEX` and origin coordinates also remain under
review and are excluded; `ORIGIN` code supplies categorical route context.
`FLIGHTS`, Weather, actual operations, identifiers, Departure outcomes, and
inbound destination constants remain excluded. No status was promoted from a
model result, 2023, or 2024.
