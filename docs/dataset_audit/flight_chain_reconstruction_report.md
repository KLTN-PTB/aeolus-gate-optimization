# Reconstructed Schedule Flight Chain — Implementation and Bounded Smoke Report

**Audit date:** 2026-08-26  
**Recommendation:** `GO_FOR_ABLATION` for the reconstructed schedule context only  
**Full 2016–2023 reconstruction:** `PASS`

## Why reconstruction was needed

The original Aeolus Flight Chain `.pt` archives do not preserve an exact
sample-to-canonical-row mapping, source row ordinal, original group key, or
encoder mappings. They also include tensors whose temporal safety cannot be
established. Their existing decision remains `FINAL — NO_GO`; this work does
not load or reverse engineer them.

## What reconstruction means

The implementation creates a deterministic schedule/service-number context
from full canonical yearly Tabular partitions. Its grouping identity is
`source_year`, normalized `FL_DATE`, normalized `OP_CARRIER`, and normalized
`OP_CARRIER_FL_NUM`. Full chain membership is reconstructed before an
inbound-target mapping selects `DEST == ATL`.

It does **not** mean physical aircraft rotation, same-aircraft chain, tail
number, registration, or airframe identity. The explicit code/config/manifest
contract is `physical_aircraft_identity = false`.

## Identifier and ordering contract

- Existing `flight_key_v1` is reused as an identifier-only canonical-row key.
- `schedule_chain_v1_<digest>` uses BLAKE2b-128 over normalized group fields.
- `chain_position` is zero-based.
- Primary order is the scheduled departure timestamp derived from `FL_DATE`
  and HHMM `CRS_DEP_TIME`.
- `CRS_DEP_TIME=2400` maps to 00:00 on the next calendar day and has a direct
  unit test.
- Ties use `ORIGIN`, `DEST`, and `flight_key` only for reproducibility and are
  marked ambiguous.
- Reconstruction retains full membership; it does not truncate or pad to six.

## Temporal and leakage safety

The derived schemas contain schedule/provenance fields only. Tests reject all
target, actual-operation, unsafe weather, `FLIGHTS`, and raw `.pt` label fields.
`CORE_WEATHER_POLICY` remains `DROP`. The unchanged access guard permits
development years 2016–2023 and blocks 2024 development access.

## Implementation validation

The implementation uses PyArrow batch reads and a per-year SQLite staging
database outside `data/raw`. SQLite has only the primary-key index and one
composite ordering index. A passed year removes staging; a failed year retains
it for diagnosis. Production output refuses overwrite. Logical content hashes
exclude file-writer metadata.

Synthetic and regression validation after the fail-closed corrections passed
90 tests. This includes proof that flight-number value semantics are checked
before other field normalization. It proves implementation behavior on fixtures, not full-data
fitness.

## Bounded 2016 smoke evidence

The CLI ran through the repository `.venv` with PyArrow 25.0.1, pandas 2.3.3,
Python 3.10.11, SQLite 3.40.1, `--max-rows 250000`, and
`--chunk-size 100000`. The full canonical partition contains 5,537,987 rows.

The smoke exposed a canonical representation contradiction:

| Field | Locked reconstruction assumption | Observed canonical example | Result |
|---|---|---|---|
| `FL_DATE` | ISO `YYYY-MM-DD` | `2016-01-01 00:00:00` | mismatch |
| `CRS_DEP_TIME` | integral HHMM | `2016-01-01 09:00:00` | mismatch |

All 250,000 rows were excluded as `FL_DATE:invalid_date`, leaving zero eligible
members, zero chains, and zero inbound targets. Therefore coverage,
membership, ambiguity, natural-signature duplication, and data-level
determinism are not evaluable. The initially emitted empty artifact and its
`PASS` label are explicitly invalidated by this audit.

After root-cause analysis, a TDD fail-closed control was added: a non-empty
source batch with zero eligible members now aborts, publishes no year output,
and retains staging. The locked date/HHMM normalization was not silently
changed. A second smoke was not run because the user-approved stop condition
had been reached.

## `OP_CARRIER_FL_NUM` semantic check

Repository documentation identifies the field as the scheduled operating
carrier flight number, and canonical Arrow storage is `double`. An independent
bounded scan of the same 250,000 rows found 0 missing, 0 non-finite, and 0
non-integral values, with observed range 1–6884. This supports the intended
integral-string normalization for the bounded sample only; it is not a full
2016–2023 proof.

## Resource audit

The rejected-row run took 7.356 seconds (33,985.75 input rows/second), observed
16,214 bytes peak staging, 12,288 bytes peak SQLite, 129,429,372 bytes peak
Python allocation, and 3,926 output bytes. Free disk changed from
65,988,186,112 to 65,988,161,536 bytes. `tracemalloc` excludes some native
PyArrow allocations.

These measurements are **not representative** of reconstruction: no row was
inserted, sorted, grouped, or materially written. A full-2016 disk/RAM/runtime
extrapolation is therefore `BLOCKED`, and no safe-margin conclusion is made.

## Raw integrity

The post-smoke inventory contains the same 36 raw paths as baseline manifests
(9 Tabular CSV files and 27 Chain `.pt` files). Every size and `mtime_ns`
matches; mismatch count is zero. No raw file was written, renamed, loaded as a
tensor, or used for mapping.

## Difference from original `.pt`

This implementation is a new deterministic transform of canonical Tabular. It
does not claim to reproduce the original encoded tensor sequences, split
membership, padding/truncation, or hidden encoder mappings.

## Coverage and ambiguity results

| Year | Source rows read | Eligible | Mapped | Chains | Inbound targets | Ambiguous order | Duplicate signatures |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2016 bounded smoke | 250,000 | 0 | 0 | 0 | 0 | NOT EVALUABLE | NOT EVALUABLE |
| 2016 full | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| 2017–2023 | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |

## Recommendation

`CANDIDATE_REQUIRES_REVIEW`. Do not run full 2016–2023 reconstruction and do
not start chain feature engineering. The design owner must explicitly decide
whether canonical timestamp-like strings are an allowed representation of the
same schedule semantics and approve a versioned contract amendment. Any
approved change must begin with new failing tests and another bounded 2016
smoke/resource audit. `GO_FOR_ABLATION` is not permitted at this stage.

---

## Superseding datetime-storage amendment smoke (2026-08-26)

The preceding section remains the historical record of the rejected Python
3.10 smoke under the original ISO-date/integral-HHMM storage expectation. The
full canonical datetime audit and subsequent design-owner decision approved
`canonical_datetime_storage_amendment_v1`, with ambiguous canonical midnight
and unexpected departure-date relations failing closed. Schedule semantics,
`schedule_chain_v1`, and stored `flight_key_v1` identifiers did not change.

The corrected pipeline ran under Python 3.11.15, pandas 2.3.3, PyArrow 25.0.1,
and SQLite 3.50.4. Two independent bounded 2016 roots each processed 250,000
source rows as 250,000 eligible/mapped members, 249,755 chains, zero exclusions,
zero ambiguity flags, and zero duplicate schedule signatures. All table and
combined logical fingerprints matched, and a direct PyArrow comparison of
`flight_key`, `chain_id`, and `chain_position` matched for every member.

The bounded prefix contained only `DEST=LAX` (210,706 rows) and `DEST=DCA`
(39,294 rows), so an inbound-ATL target did not occur in these real-data smoke
runs. The zero inbound count is reproducible, but the real-data smoke therefore
does not independently exercise the inbound target-map path; synthetic tests
continue to cover that mapping.

The peak measured staging footprint was 128,246,136 bytes, including a peak
SQLite size of 105,017,344 bytes; final Parquet output was 23,228,792 bytes.
The slower run took 168.784 seconds. Conservative linear extrapolation to the
5,537,987-row 2016 partition estimates 2,840,901,736 bytes peak staging,
514,562,992 bytes output, and 3,738.9 seconds (62.3 minutes). Current free disk
was 65,661,325,312 bytes. `tracemalloc` observed 185,874,263 bytes peak Python
allocation but does not measure all native PyArrow allocations.

The corrected bounded status is `CANDIDATE_REQUIRES_REVIEW`, not
`GO_FOR_ABLATION`. No full 2016 or full 2016-2023 reconstruction was run.
Detailed evidence is recorded in
`flight_chain_datetime_amendment_smoke_report.md` and
`artifacts/manifests/flight_chain_datetime_amendment_smoke_v1.json`.

---

## Full development reconstruction — final evidence (2026-08-26)

This section supersedes the earlier operational recommendation while retaining
all historical audit and amendment sections above. Full production
reconstruction completed sequentially for 2016–2023 under Python 3.11.15,
pandas 2.3.3, PyArrow 25.0.1, and SQLite 3.50.4. The transformation used the
unchanged `schedule_chain_v1`, `canonical_datetime_storage_amendment_v1`, and
stored `flight_key_v1` contracts. It did not access 2024 or load any raw `.pt`.

### Coverage and mapping

| Year | Source | Eligible | Mapped | Coverage | Chains | ATL targets | Excluded |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 2016 | 5,537,987 | 5,537,987 | 5,537,987 | 100% | 4,153,379 | 381,166 | 0 |
| 2017 | 5,575,872 | 5,575,872 | 5,575,872 | 100% | 4,213,097 | 358,263 | 0 |
| 2018 | 6,986,842 | 6,986,842 | 6,986,842 | 100% | 5,370,758 | 386,580 | 0 |
| 2019 | 7,161,827 | 7,161,827 | 7,161,827 | 100% | 5,522,884 | 391,075 | 0 |
| 2020 | 4,312,091 | 4,312,091 | 4,312,091 | 100% | 3,476,881 | 242,121 | 0 |
| 2021 | 5,755,666 | 5,755,666 | 5,755,666 | 100% | 4,734,600 | 309,621 | 0 |
| 2022 | 6,413,416 | 6,413,416 | 6,413,416 | 100% | 5,192,960 | 311,701 | 0 |
| 2023 | 6,645,461 | 6,645,461 | 6,645,461 | 100% | 5,339,817 | 332,741 | 0 |
| **Total** | **48,389,162** | **48,389,162** | **48,389,162** | **100%** | **38,004,376** | **2,713,268** | **0** |

Every year passed `mapped_rows == eligible_source_rows`, with zero duplicate
`flight_key`, invalid/null `chain_id`, multi-chain membership, or unmapped
eligible rows. Independent PyArrow audits found the same ATL count in the
canonical source, `inbound_target_map`, and ATL `chain_members` for every year.
All target/member/group mapping-error counters were zero.

### Chain size and ambiguity

| Year | Min | Median | P95 | Max | Chains > 6 | Ambiguous chains/timestamps/members | Duplicate signatures |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 2016 | 1 | 1 | 2 | 8 | 3,104 | 0 / 0 / 0 | 0 |
| 2017 | 1 | 1 | 2 | 8 | 3,709 | 1 / 1 / 2 | 0 |
| 2018 | 1 | 1 | 2 | 8 | 5,611 | 2 / 2 / 4 | 1 |
| 2019 | 1 | 1 | 2 | 8 | 4,344 | 0 / 0 / 0 | 0 |
| 2020 | 1 | 1 | 2 | 8 | 593 | 0 / 0 / 0 | 0 |
| 2021 | 1 | 1 | 2 | 8 | 777 | 0 / 0 / 0 | 0 |
| 2022 | 1 | 1 | 2 | 8 | 885 | 0 / 0 / 0 | 0 |
| 2023 | 1 | 1 | 2 | 8 | 241 | 0 / 0 / 0 | 0 |

The 19,264 chains longer than six were retained in full. The three ambiguous
chains and one duplicate natural schedule signature are disclosed descriptive
evidence, not mapping failures; deterministic tie-breaking preserved all
members without merging. `max_context_length=6` remains a future feature-layer
contract only.

### Flight-number, leakage, and temporal gates

All 48,389,162 `OP_CARRIER_FL_NUM` values were present, numeric, finite, and
mathematically integral. Per-year observed ranges were 1–8402 (2016), 1–8402
(2017), 1–7909 (2018), 1–7933 (2019), 1–9888 (2020), 1–8808 (2021),
1–9562 (2022), and 1–9887 (2023). No accepted row violated the canonical
datetime storage contract.

Derived schemas contain zero target, actual/outcome, weather, uncertain,
`FLIGHTS`, or raw `.pt` label fields. `CORE_WEATHER_POLICY` remains `DROP`.
Development access to 2024 remains blocked and no `year=2024` production
partition exists.

### Resources and reproducibility

| Year | Runtime (s) | Rows/s | Peak staging (bytes) | Peak SQLite (bytes) | Output (bytes) |
|---:|---:|---:|---:|---:|---:|
| 2016 | 3,731.168 | 1,484.25 | 2,780,627,978 | 2,321,006,592 | 459,621,386 |
| 2017 | 3,785.772 | 1,472.85 | 2,799,261,830 | 2,336,264,192 | 462,997,638 |
| 2018 | 4,749.680 | 1,471.01 | 3,508,682,974 | 2,928,291,840 | 580,391,134 |
| 2019 | 4,865.234 | 1,472.04 | 3,597,797,460 | 3,002,527,744 | 595,269,716 |
| 2020 | 2,932.878 | 1,470.26 | 2,174,907,184 | 1,809,125,376 | 365,781,808 |
| 2021 | 3,927.005 | 1,465.66 | 2,903,814,051 | 2,413,416,448 | 490,397,603 |
| 2022 | 4,377.261 | 1,465.17 | 3,230,814,093 | 2,688,622,592 | 542,191,501 |
| 2023 | 4,543.123 | 1,462.75 | 3,346,357,604 | 2,786,086,912 | 560,270,692 |

Total measured runtime was 32,912.120 seconds and final Parquet content was
4,056,921,478 bytes. Each passed year removed its staging directory; no stale
SQLite/WAL/SHM file remains. Peak Python allocation was 216,448,591 bytes, but
`tracemalloc` does not measure all native PyArrow allocations.

Logical fingerprints are persisted per table and year in
`artifacts/manifests/flight_chain_reconstructed_manifest_v1.json`. The 2016
fingerprints were independently recomputed after the 2017–2023 run and matched
their immutable baseline exactly.

### Integrity and evidence boundary

The raw inventory remained exactly 36 files with identical relative paths,
sizes, and `mtime_ns`; its BLAKE2b fingerprint remained
`c4071bfaad09e21d2d51cee64d01acf5a9b0fef5011f1122615ed379567a05c4`.
No raw `.pt` was loaded or used for mapping.

This artifact remains a schedule/service-number context. It does not recover
physical aircraft identity, tail number, registration, raw tensor membership,
or a same-aircraft rotation. `physical_aircraft_identity = false`.

## Final recommendation

**Reconstructed Schedule Flight Chain: `GO_FOR_ABLATION`.** The derived
schedule context is approved only for later controlled comparison of
Tabular-only versus Tabular plus reconstructed-chain features. It is not
enabled by default, is not included in the core pipeline, and does not imply
predictive improvement.

**Original Aeolus raw Flight Chain `.pt`: `FINAL — NO_GO`.** That independent
decision is unchanged.
