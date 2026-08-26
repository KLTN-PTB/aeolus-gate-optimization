# Canonical Schedule Date/Time Representation Audit

**Audit date:** 2026-08-26  
**Scope:** Full canonical development partitions, 2016–2023  
**Rows scanned:** 48,389,162  
**Decision:** `AMENDMENT_REQUIRES_REVIEW`  
**Critical rollover result:** `2400_SEMANTICS_NOT_PROVEN`

## Purpose and safety boundary

This audit was triggered by the failed bounded 2016 Reconstructed Schedule
Flight Chain smoke. The approved production contract expected an ISO service
date and integral HHMM schedule time, while canonical storage contained
timestamp-like strings.

The audit projected only `FL_DATE`, `CRS_DEP_TIME`, `CRS_ARR_TIME`,
`source_year`, `source_row_number`, and `flight_key`. Every year was opened
only after `assert_data_access_allowed(year, "development")` succeeded. It
used PyArrow batches of at most 100,000 rows, one year at a time. It did not
construct chains, inspect 2024, load `.pt`, or modify production normalization.

## Required yearly summary

All percentages below are exact because the numerator equals the yearly row
count. No anomaly count is rounded.

| Year | Rows | FL_DATE timestamp-like % | FL_DATE non-midnight | CRS_DEP timestamp-like % | CRS_DEP same-date | CRS_DEP next-day-midnight | CRS_DEP other-date | CRS_DEP invalid | CRS_ARR representation status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 2016 | 5,537,987 | 100% | 0 | 100% | 5,537,987 | 0 | 0 | 0 | 100% timestamp; all same-date |
| 2017 | 5,575,872 | 100% | 0 | 100% | 5,575,872 | 0 | 0 | 0 | 100% timestamp; all same-date |
| 2018 | 6,986,842 | 100% | 0 | 100% | 6,986,842 | 0 | 0 | 0 | 100% timestamp; all same-date |
| 2019 | 7,161,827 | 100% | 0 | 100% | 7,161,827 | 0 | 0 | 0 | 100% timestamp; all same-date |
| 2020 | 4,312,091 | 100% | 0 | 100% | 4,312,091 | 0 | 0 | 0 | 100% timestamp; all same-date |
| 2021 | 5,755,666 | 100% | 0 | 100% | 5,755,666 | 0 | 0 | 0 | 100% timestamp; all same-date |
| 2022 | 6,413,416 | 100% | 0 | 100% | 6,413,416 | 0 | 0 | 0 | 100% timestamp; all same-date |
| 2023 | 6,645,461 | 100% | 0 | 100% | 6,645,461 | 0 | 0 | 0 | 100% timestamp; all same-date |

## FL_DATE representation

All three audited fields have Arrow storage type `large_string` in every year.
Every one of the 48,389,162 `FL_DATE` values parses with the exact format
`%Y-%m-%d %H:%M:%S`; none is null, ISO-date-only, non-parseable, or
non-midnight. Each year's min/max date covers its labelled calendar year.

| Year | Timestamp-like | Midnight | Non-midnight | Invalid | Min | Max |
|---|---:|---:|---:|---:|---|---|
| 2016 | 5,537,987 | 5,537,987 | 0 | 0 | 2016-01-01 | 2016-12-31 |
| 2017 | 5,575,872 | 5,575,872 | 0 | 0 | 2017-01-01 | 2017-12-31 |
| 2018 | 6,986,842 | 6,986,842 | 0 | 0 | 2018-01-01 | 2018-12-31 |
| 2019 | 7,161,827 | 7,161,827 | 0 | 0 | 2019-01-01 | 2019-12-31 |
| 2020 | 4,312,091 | 4,312,091 | 0 | 0 | 2020-01-01 | 2020-12-31 |
| 2021 | 5,755,666 | 5,755,666 | 0 | 0 | 2021-01-01 | 2021-12-31 |
| 2022 | 6,413,416 | 6,413,416 | 0 | 0 | 2022-01-01 | 2022-12-31 |
| 2023 | 6,645,461 | 6,645,461 | 0 | 0 | 2023-01-01 | 2023-12-31 |

Within the audited development data, the timestamp-like `FL_DATE` is
deterministically equivalent to its service calendar date because its time
component is always exactly midnight and its year coverage matches
`source_year`. This conclusion concerns `FL_DATE` only; it does not prove the
rollover semantics of either schedule-time field.

Representative category example:

```text
source_year=2016, source_row_number=1
FL_DATE="2016-01-01 00:00:00"
flight_key="flight_key_v1_363199169546780c9b36a1eb330a504c"
category=timestamp_space_seconds_at_midnight
```

## CRS_DEP_TIME representation and relations

Every departure value is a non-null, parseable timestamp string in the exact
space-separated seconds format. There are no HHMM-like or unrecognized values.
All 48,389,162 timestamp date components equal normalized `FL_DATE`; previous,
next, and greater-than-one-day counts are all zero.

| Year | Same date | Next-day midnight | Previous date | >1 day | Invalid |
|---|---:|---:|---:|---:|---:|
| 2016 | 5,537,987 | 0 | 0 | 0 | 0 |
| 2017 | 5,575,872 | 0 | 0 | 0 | 0 |
| 2018 | 6,986,842 | 0 | 0 | 0 | 0 |
| 2019 | 7,161,827 | 0 | 0 | 0 | 0 |
| 2020 | 4,312,091 | 0 | 0 | 0 | 0 |
| 2021 | 5,755,666 | 0 | 0 | 0 | 0 |
| 2022 | 6,413,416 | 0 | 0 | 0 | 0 |
| 2023 | 6,645,461 | 0 | 0 | 0 | 0 |

Representative category example:

```text
FL_DATE="2016-01-01 00:00:00"
CRS_DEP_TIME="2016-01-01 09:00:00"
category=timestamp_space_seconds_same_service_date_non_midnight
```

### Midnight and rollover evidence

The complete hour/minute distributions are stored per year in the JSON
manifest. The following exact counts isolate the midnight question:

| Year | Departure hour=00 | Departure minute=00 | Exact same-day 00:00 | Exact next-day 00:00 |
|---|---:|---:|---:|---:|
| 2016 | 16,089 | 612,484 | 0 | 0 |
| 2017 | 15,821 | 614,007 | 0 | 0 |
| 2018 | 17,569 | 743,981 | 0 | 0 |
| 2019 | 16,028 | 787,072 | 0 | 0 |
| 2020 | 7,386 | 551,626 | 0 | 0 |
| 2021 | 11,191 | 729,106 | 0 | 0 |
| 2022 | 11,558 | 729,813 | 0 | 0 |
| 2023 | 10,764 | 727,081 | 0 | 0 |
| **Total** | **106,406** | **5,495,170** | **0** | **0** |

Hour `00` departures exist, but none is exactly `00:00`; their minutes are
non-zero. Therefore neither an original `0000` nor an original `2400` case is
observable in canonical development data.

The canonicalizer writes string columns without a date/time conversion, while
the canonical schema marks these fields as requiring later normalization. The
data dictionaries require HHMM/date-rollover review but do not document an
original-value-to-timestamp transform. No repository evidence proves:

```text
next-day midnight = original HHMM 2400
same-day midnight = original HHMM 0000
```

Result: `2400_SEMANTICS_NOT_PROVEN`.

## CRS_ARR_TIME representation

`CRS_ARR_TIME` is scheduled information only; this audit makes no claim about
actual or operational arrival. Every value is a non-null timestamp in the same
space-separated format, and every stored date equals `FL_DATE`:

| Year | Timestamp-like | Same date | Next date | Other | Invalid | Same-date exact 00:00 |
|---|---:|---:|---:|---:|---:|---:|
| 2016 | 5,537,987 | 5,537,987 | 0 | 0 | 0 | 15 |
| 2017 | 5,575,872 | 5,575,872 | 0 | 0 | 0 | 0 |
| 2018 | 6,986,842 | 6,986,842 | 0 | 0 | 0 | 89 |
| 2019 | 7,161,827 | 7,161,827 | 0 | 0 | 0 | 93 |
| 2020 | 4,312,091 | 4,312,091 | 0 | 0 | 0 | 21 |
| 2021 | 5,755,666 | 5,755,666 | 0 | 0 | 0 | 7 |
| 2022 | 6,413,416 | 6,413,416 | 0 | 0 | 0 | 4 |
| 2023 | 6,645,461 | 6,645,461 | 0 | 0 | 0 | 1 |

An example scheduled arrival at exact midnight is:

```text
FL_DATE="2016-06-01 00:00:00"
CRS_DEP_TIME="2016-06-01 22:25:00"
CRS_ARR_TIME="2016-06-01 00:00:00"
flight_key="flight_key_v1_4d986809472d41250e374154e9c090e1"
```

The date remains the service date even when the clock-time sequence suggests a
possible overnight arrival. Consequently the date component must not be
interpreted as proven scheduled-arrival rollover. A future output contract
needs explicit review before normalizing this field.

## Traceability and accounting

- `source_year` mismatches: 0.
- Null `source_row_number`: 0.
- Null `flight_key`: 0.
- Stored `flight_key_v1` values were copied only into bounded examples and were
  never recomputed or changed.
- Representation categories account for every row; timestamp relation
  categories account for every timestamp-like value.
- Runtime: 264.1573775 seconds for 48,389,162 rows.

## Amendment decision

**`AMENDMENT_REQUIRES_REVIEW`**

The storage representation itself is uniform and deterministic. `FL_DATE`
timestamp-midnight values can be shown equivalent to service dates, and the
clock component of same-date departure timestamps is observable. However, the
task declares original HHMM `2400` semantics a critical gate. No same-day or
next-day departure at exact midnight exists in 2016–2023, and repository
provenance does not establish how `0000` or `2400` would be represented.

Production `normalize_flight_date` and `scheduled_departure_timestamp` therefore
remain unchanged. No amendment tests, corrected reconstruction smoke, or
resource extrapolation were run. A design-owner decision is required before a
versioned representation amendment can be proposed.

## Evidence sources

- Full manifest:
  `artifacts/manifests/canonical_schedule_datetime_representation_audit_v1.json`
- Canonical implementation: `src/data/canonicalize.py`
- Canonical schema: `artifacts/manifests/canonical_schema_v1.json`
- `docs/dataset_audit/canonical_schema_v1.md`
- `docs/dataset_audit/data_dictionary_v1.md`
- `docs/dataset_audit/flight_chain_feasibility_report.md`

The original raw Flight Chain remains `FINAL — NO_GO`; this audit neither uses
nor changes that decision.
