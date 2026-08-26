# Reconstructed Schedule Flight Chain Design

**Date:** 2026-08-26  
**Status:** Datetime amendment implemented; bounded smoke A/B PASS; full 2016–2023 reconstruction PASS; reconstructed chain `GO_FOR_ABLATION`; original raw Aeolus Flight Chain remains `FINAL — NO_GO`  
**Scope:** Deterministic, schedule-only chain reconstruction from canonical Tabular for development years 2016–2023

## 1. Purpose and evidence boundary

The original Aeolus Flight Chain `.pt` archives remain `FINAL — NO_GO`. They do not provide an exact sample-to-Tabular mapping, encoder mappings, point-in-time weather evidence, or a physical-aircraft identifier. This design does not load, reverse engineer, correlate, rewrite, rename, or otherwise reinterpret those archives.

The new artifact is a **Reconstructed Schedule Flight Chain**, also describable as **Derived Flight Chain Context**. It represents a same-carrier, same-operating-flight-number, same-service-date schedule context reconstructed from canonical Tabular. It is not a physical aircraft rotation, same-aircraft chain, tail number, registration, or airframe identity.

The source universe is the complete canonical yearly partition:

`data/processed/tabular_by_year/year=<YYYY>/`

The ML target universe is derived only after full-chain reconstruction by selecting members whose normalized `DEST == "ATL"`.

## 2. Locked baseline contracts

- Reuse `FLIGHT_KEY_VERSION = "flight_key_v1"` from `src/data/canonicalize.py` without changing its formula.
- Treat `flight_key`, `source_row_number`, and `source_year` as traceability identifiers, never ML predictors.
- Preserve `CORE_WEATHER_POLICY = "DROP"`.
- Preserve the original raw Flight Chain decision as `FINAL — NO_GO`.
- Preserve development access for 2016–2023 and block 2024 development access through `assert_data_access_allowed(year, "development")`.
- Read no raw `.pt` tensor or label.
- Write nothing under `data/raw/tabular/` or `data/raw/chain/`.

## 3. Runtime and dependency contract

The production CLI must run from the repository `.venv`. It fails closed when `sys.prefix` does not resolve to `<project-root>/.venv`. Tests import pure functions without triggering that CLI-only runtime check.

The project dependency file records exact installed versions of at least Python-facing runtime packages used by this pipeline, including `pandas`, `pyarrow`, `PyYAML`, and `pytest`. The reconstruction manifest additionally records the runtime Python, pandas, PyArrow, and SQLite versions. All documented execution commands use:

`.\.venv\Scripts\python.exe`

PyArrow is the canonical Parquet reader/writer. SQLite from the Python standard library is an intermediate, per-year staging mechanism only.

## 4. Identifier contracts

### 4.1 Chain ID

Constants:

```python
CHAIN_ID_VERSION = "schedule_chain_v1"
CHAIN_GROUP_COMPONENTS = (
    "source_year",
    "FL_DATE",
    "OP_CARRIER",
    "OP_CARRIER_FL_NUM",
)
PHYSICAL_AIRCRAFT_IDENTITY = False
```

Normalized components are joined with ASCII unit separator `\x1f`, encoded as UTF-8, and hashed with BLAKE2b using a 16-byte digest. The identifier is:

`schedule_chain_v1_<32-lowercase-hex-digest>`

Python's process-dependent `hash()` is prohibited.

### 4.2 Natural schedule signature

`schedule_signature_v1` is an audit-only BLAKE2b-128 identifier over:

- `source_year`
- `FL_DATE`
- `OP_CARRIER`
- `OP_CARRIER_FL_NUM`
- `ORIGIN`
- `DEST`
- normalized `CRS_DEP_TIME`

It detects duplicated natural schedule rows. It never replaces `flight_key`, and duplicate signatures are retained as separate memberships.

## 5. Normalization and eligibility

### 5.1 Group components

- `source_year`: exact integer equal to the requested partition year.
- `FL_DATE`: trimmed and parsed as a strict calendar date, then emitted as ISO `YYYY-MM-DD`.
- `OP_CARRIER`: trimmed and uppercased; empty values are missing.
- `OP_CARRIER_FL_NUM`: verified before normalization as the documented operating carrier flight number from the canonical data dictionary and official preprocessing evidence. At runtime it must be numeric, finite, and mathematically integral. It is emitted as a base-10 integer string without `.0`, exponent notation, whitespace, or padding. Encoded `.pt` values are never used.

The smoke/full audit reports missing, non-numeric, non-finite, and non-integral flight-number values separately. No value is guessed or imputed.

### 5.2 Scheduled departure time

`CRS_DEP_TIME` accepts string or numeric representations that describe an integral HHMM value. Leading zeros are optional. Valid behavior includes:

- `5` -> `0005` -> service date at `00:05`
- `45` -> `0045` -> service date at `00:45`
- `800` -> `0800` -> service date at `08:00`
- `1530` -> `1530` -> service date at `15:30`
- `2400` -> `2400` -> next calendar date at `00:00`

Hours `00..23` require minutes `00..59`. `2400` is the only valid `24xx` value. Negative, fractional, non-numeric, non-finite, or out-of-range values are invalid. The derived timestamp is timezone-naive because the canonical source does not provide a timezone contract; it is an ordering representation, not a UTC instant.

### 5.3 Eligibility and fail-closed invariants

A source row is eligible when group fields and `CRS_DEP_TIME` normalize successfully and canonical traceability fields are valid. Missing/invalid group or departure fields are excluded with exact per-reason counts; nothing is imputed.

The following indicate a broken canonical contract and abort the year rather than silently excluding rows:

- missing or empty `flight_key`;
- duplicate `flight_key`;
- missing/non-integral `source_row_number`;
- `source_year` inconsistent with the requested partition;
- one `flight_key` mapping to more than one reconstructed chain.

Missing `ORIGIN` or `DEST` is retained as an empty normalized audit value because neither field defines group eligibility. It remains visible in ambiguity reporting and never receives an invented airport.

## 6. Ordering and ambiguity

Members are ordered within a chain by:

1. `scheduled_departure_timestamp`;
2. normalized `ORIGIN`;
3. normalized `DEST`;
4. `flight_key`.

The last three fields are reproducibility tie-breakers only. They do not establish the undocumented original Aeolus order.

`chain_position` is zero-based. Members sharing a scheduled departure timestamp within the same chain receive `order_ambiguous = true`; other members receive `false`. The parent group receives `has_order_tie = true` when any timestamp is duplicated.

Full membership is always retained. Reconstruction never truncates to six and never pads fake records. `max_context_length: 6` is metadata for a later, separately approved feature transformer.

## 7. Output schemas

The versioned root is:

`data/processed/flight_chain_reconstructed_v1/`

Each table is partitioned as `<table>/year=<YYYY>/part-00000.parquet`, with multiple Parquet row groups allowed inside a part.

### 7.1 `chain_groups`

- `chain_id: string`
- `chain_version: string`
- `source_year: int64`
- `FL_DATE: string`
- `OP_CARRIER: string`
- `OP_CARRIER_FL_NUM: string`
- `member_count: int64`
- `first_scheduled_departure: timestamp[us]`, timezone-naive
- `last_scheduled_departure: timestamp[us]`, timezone-naive
- `has_order_tie: bool`

### 7.2 `chain_members`

- `chain_id: string`
- `chain_version: string`
- `chain_position: int64`
- `flight_key: string`
- `schedule_signature: string`
- `source_year: int64`
- `source_row_number: int64`
- `FL_DATE: string`
- `OP_CARRIER: string`
- `OP_CARRIER_FL_NUM: string`
- `ORIGIN: string`
- `DEST: string`
- `CRS_DEP_TIME: string`
- `CRS_ARR_TIME: string`
- `CRS_ELAPSED_TIME: float64`, nullable
- `scheduled_departure_timestamp: timestamp[us]`, timezone-naive
- `is_inbound_atl: bool`
- `order_ambiguous: bool`

### 7.3 `inbound_target_map`

- `target_flight_key: string`
- `chain_id: string`
- `chain_position: int64`
- `chain_length: int64`
- `source_year: int64`

No table contains actual operations, targets, weather, `FLIGHTS`, raw `.pt` labels, or aircraft identity.

## 8. Bounded-memory staging architecture

One year is processed at a time:

1. Enforce `development` access before opening the processed partition.
2. Verify the input Parquet schema and project only the required schedule/provenance columns.
3. Read batches with PyArrow using `--chunk-size`.
4. Normalize each batch and insert eligible rows into a SQLite staging database outside `data/raw`.
5. Maintain only two indexes: the `flight_key` primary key and one composite ordering index over group fields, scheduled timestamp, tie-break fields, and `flight_key`.
6. Stream the ordered cursor one chain at a time, derive positions/ties/signature duplicates, and write bounded PyArrow buffers.
7. Validate output counts, schema, mappings, fingerprints, and raw metadata.
8. Publish the year's staged Parquet outputs only after all year gates pass.
9. Delete that year's SQLite staging directory only after the year passes. A failed year's staging path is retained and reported for diagnosis; it is never placed under `data/raw`.
10. Release Arrow/SQLite objects before beginning the next year.

SQLite uses no WAL and no durability-oriented journal because it is disposable derived staging. Indexes exist during insertion so reported database growth captures their persistent footprint without a separate external index-build spike.

Resource metrics include input bytes, output bytes, runtime, row throughput, peak observed staging bytes, and peak Python allocation measured by `tracemalloc`. The report states that `tracemalloc` excludes some native PyArrow allocations.

## 9. Output and raw-path safety

Every configurable output/staging/manifest path is resolved before use. A path equal to or nested under either raw root is rejected, including paths reached through symlinks/junctions after resolution.

Production year directories are append-only by version and refuse overwrite. Temporary output is published only after validation. Partial production directories are never treated as passing artifacts.

Raw integrity uses metadata-only snapshots of all files under both raw roots:

- normalized relative path;
- size;
- `mtime_ns`.

The before/after snapshots must match exactly. The pipeline never opens raw `.pt` data and never uses `torch.load()`.

## 10. Validation gates and fingerprints

Each year records:

- input/source rows and eligible rows;
- mapped members and excluded rows/reasons;
- chain and inbound-target counts;
- duplicate/multi-chain/null identifier counts;
- ambiguous chains, ambiguous timestamps, and ambiguous members;
- duplicate natural signatures and excess duplicate rows;
- chain length distribution and chains longer than six;
- logical content fingerprints for all three tables and a combined fingerprint;
- dependency and resource metrics.

Critical gates are:

- A: `mapped_rows == eligible_source_rows`;
- B: duplicate `flight_key == 0`;
- C: invalid `chain_id == 0`;
- D: repeated fixture/smoke input has identical logical IDs, memberships, positions, and fingerprints;
- E: output schemas are disjoint from `LEAKAGE_COLUMNS`, `TARGET_COLUMNS`, `WEATHER_COLUMNS`, `UNCERTAIN_COLUMNS`, and explicit actual/outcome fields;
- F: `PHYSICAL_AIRCRAFT_IDENTITY is False` and documentation preserves the semantic boundary;
- G: raw path/size/mtime snapshots are identical;
- H: 2024 development access remains blocked.

Fingerprints hash explicitly ordered logical fields with canonical null/boolean/numeric/timestamp serialization. Creation timestamps and Parquet writer metadata are excluded.

## 11. CLI and execution stages

`scripts/reconstruct_flight_chain.py` supports:

- `--years`, including ranges such as `2016-2023`;
- `--output-root`;
- `--dry-run`;
- `--chunk-size`;
- `--max-rows` for explicitly incomplete smoke runs.

Default years are 2016–2023. Year 2024 is rejected by the development guard.

Execution order:

1. TDD for pure normalization, ID, ordering, mapping, leakage, raw-path, and holdout behavior.
2. Full synthetic test suite.
3. Incomplete 2016 smoke using a bounded `--max-rows` and a non-production smoke root.
4. Inspect runtime, peak staging, estimated full-year staging, free disk, and Python allocation. Do not change architecture automatically.
5. Continue only if the smoke indicates safe disk/RAM/runtime margins.
6. Run full production reconstruction for 2016–2023, one year at a time.
7. Run all critical gates, full regression tests, raw comparison, and a second deterministic logical comparison where feasible.
8. Generate final manifest, reconstruction report, and decision.

If the smoke is unsuitable, execution stops and reports evidence before any architectural change.

## 12. Status and decision policy

Three execution statuses remain distinct:

- `IMPLEMENTATION PASS`: code and synthetic tests pass.
- `SMOKE DATA PASS`: the bounded 2016 smoke passes its explicitly incomplete gates and resource audit.
- `FULL DATA PASS`: every full 2016–2023 year and every critical gate pass.

`GO_FOR_ABLATION` is permitted only after `FULL DATA PASS`. Synthetic tests, a partial smoke, or a single full year can produce at most `CANDIDATE_REQUIRES_REVIEW`.

The new decision document must always state:

- Original Aeolus raw Flight Chain: `FINAL — NO_GO`.
- Reconstructed Schedule Flight Chain: independently evaluated status.
- `physical_aircraft_identity = false`.
- No claim that reconstructed context improves any model.

No model training, Chain feature transformer, SHAP, HPO, simulation, or optimization is part of this task.

## 13. Planned repository changes

Create:

- `src/data/flight_chain_reconstruction.py`
- `scripts/reconstruct_flight_chain.py`
- `tests/test_flight_chain_reconstruction.py`
- `requirements.txt`
- `artifacts/manifests/flight_chain_reconstructed_manifest_v1.json` after full execution
- `docs/dataset_audit/flight_chain_reconstruction_report.md` after audit
- `docs/decisions/decision_reconstructed_chain.md` only after final validation

Modify as needed:

- `configs/base.yaml`
- `scripts/smoke_test.py`
- `README.md`
- `docs/decisions/decision_registry.md`
- `docs/thesis_notes/assumptions.md`
- `docs/thesis_notes/limitations.md`

The original `docs/decisions/decision_include_chain.md`, raw data, canonical artifacts, leakage rules, weather policy, and access guard are not weakened or rewritten.

---

## Versioned Amendment: canonical datetime storage representation v1

**Amendment version:** `canonical_datetime_storage_amendment_v1`  
**Approved:** 2026-08-26  
**Design-owner decision:** `AMENDMENT_SUPPORTED_WITH_AMBIGUOUS_MIDNIGHT_FAIL_CLOSED`

This section appends a versioned storage-representation amendment. It does not
rewrite the original design expectation that `FL_DATE` would be an ISO date and
`CRS_DEP_TIME` would be an integral HHMM value. The earlier full development
audit correctly returned `AMENDMENT_REQUIRES_REVIEW` because original `0000`
versus `2400` provenance was not proven. The design-owner decision above
subsequently approves the narrower rules below without claiming that provenance.

### Evidence retained from the full 2016-2023 canonical audit

- 48,389,162 development rows were scanned with the 2024 holdout unopened.
- `FL_DATE` was 100% timestamp-like canonical strings, 100% at `00:00:00`,
  with zero non-midnight and zero invalid values.
- `CRS_DEP_TIME` was 100% timestamp-like, 100% on the same calendar date as
  `FL_DATE`, with zero previous-date, next-date, greater-than-one-day, invalid,
  or exact-midnight values.
- Original `0000` versus `2400` provenance remains **NOT PROVEN**.
- The `CRS_ARR_TIME` date component is not evidence of overnight-arrival
  rollover and must not be interpreted that way.

### Scope and identifier compatibility

The semantic schedule-chain contract is unchanged. Only accepted canonical
storage representations expand. `CHAIN_ID_VERSION` remains
`schedule_chain_v1`; `FLIGHT_KEY_VERSION` remains `flight_key_v1`; stored
canonical `flight_key` values are reused without recomputation. Datetime
normalization affects grouping, schedule signature, ordering, and derived output
representation only.

### `FL_DATE` accepted storage representations

- An ISO date such as `2016-01-01` normalizes to `2016-01-01`.
- An exact timestamp-like value such as `2016-01-01 00:00:00` normalizes to
  `2016-01-01`.
- A timestamp-like `FL_DATE` with a non-midnight clock is a contract violation
  and fails closed. Its time component must never be silently stripped.
- Existing safe Python `date`/`datetime` inputs remain accepted only under the
  same midnight rule for `datetime` values.

### `CRS_DEP_TIME` accepted storage representations

The explicit integral HHMM contract remains in force: `5`, `45`, `800`, and
`1530` normalize to `0005`, `0045`, `0800`, and `1530`. Explicit HHMM `2400`
continues to map to `00:00` on the next calendar day because that input itself
contains the explicit `2400` representation.

An exact timestamp-like canonical `CRS_DEP_TIME` is accepted only when:

1. `FL_DATE` first normalizes successfully;
2. its calendar date equals the normalized service date; and
3. its clock is not exactly `00:00:00`.

For an accepted timestamp, HHMM is derived from its hour/minute and the parsed
timestamp itself is the schedule-ordering timestamp. For example,
`2016-01-01 09:00:00` becomes `0900` and
`2016-01-01 00:05:00` becomes `0005` for service date `2016-01-01`.

A canonical timestamp exactly at midnight fails with
`AMBIGUOUS_CANONICAL_MIDNIGHT`; it is not mapped to either `0000` or `2400`.
Any previous- or next-date canonical departure timestamp, including next-day
midnight, fails with `UNEXPECTED_CANONICAL_DATE_RELATION`; rollover is never
inferred from timestamp storage.

These representation-contract violations are fatal for a production year. The
year aborts, staging is retained for diagnosis, and no production artifact is
published. They are not ordinary missing-value exclusions.

### `CRS_ARR_TIME` remains outside this amendment

No arrival-rollover inference, duration derivation, or ordering use is added.
`CRS_ARR_TIME` remains schedule-only and its canonical value may be preserved in
`chain_members` without giving its date component rollover semantics. Arrival
normalization requires a separate future contract.

All prior raw-data protections, the original raw Flight Chain
`FINAL — NO_GO`, `CORE_WEATHER_POLICY = "DROP"`, leakage exclusions, and the
2024 development access guard remain unchanged. This amendment can produce at
most `CANDIDATE_REQUIRES_REVIEW` until a later full 2016-2023 reconstruction and
all critical gates pass.
