# Schema Audit Plan — Week 2

## Purpose and scope

This document defined the Week-2 plan. The plan has now been executed for each Aeolus Tabular year, 2016–2024; evidence is recorded in the versioned per-year manifests, compatibility matrix, and canonical schema. It implements decisions D002, D003, D007, D008, D011, D013, and D020 in `docs/decisions/decision_registry.md`.

The audit is year-by-year and chunk-based. It must not rewrite raw data, load all nine CSV files into RAM, train models, generate processed data, or use Flight Chain source splits as the thesis temporal protocol.

## Schema audit is not model/result access

Schema audit examines structure and metadata needed for safe canonicalization: columns, types, coverage, quality, and compatibility. It is distinct from model fitting, HPO, feature selection, calibration, model selection, simulation tuning, optimization tuning, or performance reporting.

Structural audit of **2024** is permitted in Week 2 to establish schema compatibility and canonicalization. It must not produce or use 2024 performance results for any development decision. The sealed final-holdout rule remains unchanged.

## Execution approach

1. Process one year at a time from `data/raw/tabular/<year>/`.
2. Read CSV data in bounded chunks using Pandas `read_csv(..., chunksize=...)`; use PyArrow streaming/dataset facilities where beneficial for schema and scan tasks.
3. Collect only aggregations, metadata, samples justified by the audit protocol, and manifests. Do not concatenate all years or retain full raw records in memory.
4. Record code version, audit configuration, chunk size, year, source path, file byte size, start/end time, and errors in an audit manifest.
5. Keep all raw inputs read-only. Write audit outputs only to approved documentation/manifests and later processed locations, never back to `data/raw/`.
6. Complete cross-year comparison only after each year has an individual audit record.

## Per-year audit checklist

For every year 2016–2024, record the following before any canonical schema decision.

| # | Audit item | Week 2 evidence to record |
|---:|---|---|
| 1 | Columns | Exact names, count, presence/absence, and unexpected fields. |
| 2 | Column order | Ordered list and positional differences from other years. |
| 3 | Dtype | Parsed dtype per column, inferred type changes, mixed-type warnings, and parse failures. |
| 4 | Row count | Streaming total row count and malformed-row policy/result. |
| 5 | Date coverage | `FL_DATE` parsing result, min/max date, years/months observed, invalid-date count. |
| 6 | Missingness | Per-column missing count and percentage, calculated by chunks. |
| 7 | Target availability/distribution | Presence and missingness of `ARR_DELAY`; distribution summaries and `ARR_DELAY >= 15` counts, without model fitting. |
| 8 | Carrier cardinality | Cardinality and top-count summary for documented carrier field(s), including `OP_CARRIER` if present. |
| 9 | Airport cardinality | Cardinality and top-count summary for `ORIGIN`/`DEST` if present; no ATL filtering output in this stage. |
| 10 | Weather fields | Candidate weather columns, source naming/provenance metadata if available, and timing status `SAFE`/`UNCERTAIN` pending T-2h evidence. |
| 11 | `ORIGIN_INDEX`/`DEST_INDEX` consistency | Presence, dtype, cardinality, and cross-year mapping-stability evidence; do not assume stable semantics. |
| 12 | Duplicate rows/keys | Whole-row duplicate count plus documented candidate flight-key duplicate count using streaming/fingerprints or external bounded storage. |
| 13 | Timestamp parsing | Parsing diagnostics for `FL_DATE`, scheduled-time fields, nulls, invalid values, and timezone/format assumptions. |
| 14 | Actual-operation fields | Presence and audit classification of `DEP_TIME`, `ARR_TIME`, `WHEELS_OFF`, `WHEELS_ON`, `TAXI_IN`, `TAXI_OUT`, `AIR_TIME`, and `ACTUAL_ELAPSED_TIME`; these are excluded from pre-flight predictors. |
| 15 | Schema drift | Per-field differences in presence, order, dtype, missingness, value domains, and date coverage against the developing canonical comparison matrix. |

## Cross-year outputs

After all nine year records are complete, produce:

1. A **schema compatibility matrix** with one row per field and one column/group per year, showing presence, order, dtype, semantic status, and drift classification.
2. A versioned **canonical schema** that defines required, optional, deprecated, unavailable, and uncertain fields.
3. A field-status register: `TARGET`, `LEAKAGE`, `SAFE`, or `UNCERTAIN`; weather remains `UNCERTAIN` until availability at T-2h is evidenced.
4. A temporal manifest that separates rolling development 2016–2022, development 2023, and sealed final holdout 2024.
5. An audit manifest tying every output to source paths, file metadata, configuration, and code version.

Canonicalization must be based on documented cross-year compatibility, not an assumption that later years match 2016. Any unresolved field remains `UNCERTAIN` or is excluded from the first canonical feature contract until evidence exists.

## Flight Chain boundary

Flight Chain remains optional. Its source train/val/test filenames are not temporal splits for this thesis. Any Chain feasibility work must answer the separately tracked mapping/semantics and temporal-safety questions before GO; it must not be treated as a substitute for the Tabular schema audit.

## Week 2 acceptance checklist

- [x] Individual chunked audit record exists for every Tabular year 2016–2024.
- [x] No raw file was modified; source paths and byte sizes are recorded.
- [x] Columns, order, dtypes, row counts, dates, missingness, targets, carrier/airport cardinality, weather candidates, indices, duplicates, timestamps, actual-operation fields, and drift are covered for every year.
- [x] Schema compatibility matrix is complete and reviewable.
- [x] Canonical schema is versioned and clearly distinguishes required/optional/uncertain fields.
- [x] Weather availability at T-2h is evidenced or fields remain lagged/dropped/uncertain.
- [x] `ORIGIN_INDEX`/`DEST_INDEX` are accepted only with cross-year stability evidence.
- [x] Actual-operation fields are excluded from the pre-flight predictor contract.
- [x] Temporal manifest locks 2016–2022, 2023, and 2024 to their approved roles.
- [x] No 2024 performance result is used for HPO, model selection, simulation, optimization, or robustness configuration.
- [x] Flight Chain has a documented final `NO_GO` decision in `flight_chain_feasibility_report.md` and `decision_include_chain.md`, without unsupported identity claims.

## Out of scope for this plan

The planning prompt did not execute the audit. Its Week-2 execution subsequently created only schema/canonicalization artifacts; it did not train models, fit ML preprocessing, or evaluate 2024 performance.
