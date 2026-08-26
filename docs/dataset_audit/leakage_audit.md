# Leakage Audit — Week 2, T-2h Contract

## Scope and evidence

Audit date: 2026-08-23. Evidence sources are the three synchronized V3 roadmaps, `configs/base.yaml`, canonical schema v1, the 2016–2024 schema compatibility matrix, the processed-data manifest, the cross-year airport-index mapping audit, and the Week-1 prediction contract. No target correlation or model performance was used to classify a field.

This audit governs the core inbound ATL prediction dataset (`DEST=ATL`). Stored processed data remains unchanged; these statuses control later candidate model inputs.

## Prediction-time contract

`T_cutoff = CRS_DEP_TIME - 2 hours`

A predictor is eligible only when every item of information used to construct it exists at or before `T_cutoff`. Availability is an information-time property, not a correlation or dtype property. Realized operations and outcomes are prohibited from `X`, even if they improve development metrics.

Regression target: signed `ARR_DELAY` minutes. Classification target: `y_cls = 1[ARR_DELAY >= 15]`. Neither target may enter `X`.

## Findings by status

| Status | Fields | Audit conclusion |
|---|---|---|
| SAFE | `FL_DATE`, `OP_CARRIER`, `OP_CARRIER_FL_NUM`, `ORIGIN`, `CRS_DEP_TIME`, `CRS_ARR_TIME`, `CRS_ELAPSED_TIME`, `MONTH`, `DAY_OF_MONTH`, `DAY_OF_WEEK` | Scheduled/calendar information identified consistently in canonical schema and the V3 schedule-only contract; logically available before T-2h. High-cardinality handling must still be fit inside temporal folds. |
| TARGET | `ARR_DELAY`; derived `y_cls` | Outcome only. `ARR_DELAY` remains signed and unchanged; `y_cls` uses the locked 15-minute threshold. |
| LEAKAGE | `DEP_TIME`, `DEP_DELAY`, `TAXI_OUT`, `WHEELS_OFF`, `WHEELS_ON`, `TAXI_IN`, `ARR_TIME`, `ACTUAL_ELAPSED_TIME`, `AIR_TIME` | Realized operational timestamps/durations/delays that occur after the core pre-flight cutoff. Never candidate predictors. |
| UNCERTAIN | `FLIGHTS` | Semantics, grain, and prediction-time availability remain undocumented. Keep out of `X`. |
| INSUFFICIENT_EVIDENCE / core DROP | `O_TEMP`, `O_PRCP`, `O_WSPD`, `D_TEMP`, `D_PRCP`, `D_WSPD` | The official paper identifies Meteostat hourly measurements, but released Aeolus artifacts omit valid time, availability/issue time, source/model-fill flags, timezone, and join logic. None passes T-2h; no safe lag can be derived from the scalar fields. Retain in storage but exclude from core `X`. |
| IDENTIFIER_ONLY | `flight_key`, `source_row_number`, `source_year` | Traceability/partition metadata only; not model predictors and not aircraft identifiers. |
| CONDITIONAL | `ORIGIN_INDEX`, `O_LATITUDE`, `O_LONGITUDE` | Airport-code→index mapping is stable across 2016–2024, but index numeric treatment and origin-coordinate entity/mapping require explicit Week-3 handling. Blocked by default. |
| DROP_CONSTANT | `DEST`, `DEST_INDEX`, `D_LATITUDE`, `D_LONGITUDE` | Retained in stored data, but constant after the inbound ATL filter and therefore excluded from Week-3 model input candidates. |

## ATL constant evidence

The processed manifest records all core inbound partitions as `DEST=ATL`. A column-only scan of every inbound partition for 2016–2024 found exactly one distinct value per year for each of `DEST`, `DEST_INDEX`, `D_LATITUDE`, and `D_LONGITUDE`. This is direct processed-data evidence, not an assumption from column names.

An ATL→ATL movement may exist in both inbound and outbound partitions; this does not change the inbound constant rule and is not treated as a duplicate error.

## Conditional index finding

`artifacts/manifests/airport_index_mapping_audit.json` reports no within-year or cross-year conflicts for either `ORIGIN -> ORIGIN_INDEX` or `DEST -> DEST_INDEX`; both mappings are `STABLE` for 2016–2024. Stability removes the prior mapping-drift uncertainty, but it does not justify treating an arbitrary integer index as a continuous measurement. Therefore:

- `ORIGIN_INDEX` is `CONDITIONAL`, blocked by default until Week 3 documents its treatment or chooses the airport code instead.
- `DEST_INDEX` is `DROP_CONSTANT` for inbound ATL regardless of mapping stability.

## Automated enforcement

`src/data/leakage_rules.py` is fail-closed:

- targets, realized outcomes, weather excluded by the completed timing audit, unresolved `FLIGHTS`, identifiers, and inbound constants are forbidden;
- conditional fields require an explicit reviewed opt-in;
- unknown/unregistered columns are rejected;
- the module performs no fitting or preprocessing.

## Week-3 handoff

Week 3 may build model-specific transformations only from the SAFE set plus separately approved CONDITIONAL fields. Encoders, imputers, frequency maps, and scalers must be fit within rolling temporal folds. The completed weather audit sets core policy to DROP all six raw weather fields; promotion is prohibited unless new versioned point-in-time provenance is audited first.

## V4 task-aware addendum — 2026-08-26

The Week-2 findings above remain historical evidence for the inbound Arrival
task. Architecture V4 applies the same T-2h information boundary through two
explicit task contracts:

- `arrival_core`, `DEST=ATL`: `ARR_DELAY`, `y_arr_cls`, and `y_arr_reg` are
  targets; `DEP_DELAY`, actual operations, raw Aeolus Weather, identifiers,
  unresolved fields, and inbound ATL constants are forbidden. Arrival uses no
  Weather and does not consume auxiliary Departure predictions.
- `departure_auxiliary`, `ORIGIN=ATL`: `DEP_DELAY` and `y_dep_cls` are targets;
  `ARR_DELAY`/Arrival labels are future outcomes, actual operations remain
  forbidden, the same raw Aeolus Weather fields remain
  `INSUFFICIENT_EVIDENCE`, and outbound ATL origin constants are dropped.
  Destination airport index/coordinates require explicit categorical/entity
  review and are never treated as continuous merely because their dtype is
  integer/float.

`src/data/leakage_rules.py` now fails closed by task and defaults to
`arrival_core` for compatible callers. Unknown tasks, unknown fields, and
unapproved external Weather fields fail closed. A future point-in-time Weather
source remains disabled until a separate audited contract is added; this
addendum itself grants no approval.

## Week 3A enforcement addendum — 2026-08-26

`feature_manifest_arrival_v1` and `src/features/tabular_features.py` implement
the Core Arrival subset. Raw sources entering derivation are first checked by
this normal `arrival_core` leakage contract; prepared `X` then contains only
the versioned Schedule/Calendar/Carrier/Route columns. Unknown raw fields fail
closed. Weather, `DEP_DELAY`/Departure labels, actual-operation fields,
identifiers, `FLIGHTS`, conditional indices/coordinates, ATL destination
constants, and Chain fields are absent from base `X`.

All learned preprocessing state is scoped to the training rows of one locked
expanding fold. Week 3A performed no 2023 fit, row-level 2024 access, feature
selection by performance, or model training. D026 remains an independent gate
for any future Chain extension; ARR-B is still disabled.
