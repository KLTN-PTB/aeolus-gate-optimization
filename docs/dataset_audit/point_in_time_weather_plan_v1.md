# Point-in-time Weather Plan V1

Plan date: 2026-08-26  
Planned artifact: `weather_point_in_time_v1`  
Current status: **AUDIT_REQUIRED**  
Enabled: **false**

## Purpose and scope

This document specifies the evidence and join contract required before an
external Weather source may enter the V4 **auxiliary outbound Departure
classification experiment**. It is a plan, not proof of approval, not a data
inventory, and not evidence that any provider is suitable.

The Core Arrival model uses no Weather. Failure to acquire or approve a
point-in-time source does not block the Arrival pipeline or the core thesis.
No Weather is downloaded or joined under this plan.

## Prediction cut-off

For each outbound `ORIGIN=ATL` target row:

```text
prediction_cutoff = scheduled_departure_timestamp - 2 hours
```

Every Weather datum and every piece of metadata used to select or transform it
must satisfy:

```text
information_available_time <= prediction_cutoff
```

Valid time alone is insufficient. The contract is about what a forecaster
could have known at the cut-off, not when the weather occurred.

## Required source fields

Every accepted record or deterministic source manifest must provide:

- `issue_time` for forecasts, or a defensible `publication_time` /
  `available_time` for observations;
- `valid_time`;
- airport, station, grid point, or location identifier;
- source timezone plus normalized UTC timestamps;
- weather variable names, units, and missing/sentinel conventions;
- forecast model/run/lead metadata when applicable;
- observation quality/model-fill flags when applicable;
- provider, dataset version, retrieval date, license, and immutable source
  signature;
- documented corrections/revisions policy.

If availability is expressed as a provider-wide delay rather than row-level
timestamps, the delay rule must be primary-source documented, conservative,
versioned, and applied before the join. Undocumented assumptions fail closed.

## Forecast versus observation distinction

Forecast and observation sources must not be merged under one ambiguous field
meaning.

- Forecast: select only a run issued by the cut-off; record issue time, valid
  time, lead time, location, model/version, and revision policy.
- Observation: prove publication/availability by the cut-off; observation
  valid time cannot stand in for availability time.
- Reanalysis, backfill, interpolated, or model-filled data: reject unless its
  historical point-in-time availability is explicitly evidenced. A dataset
  produced retrospectively is not automatically deployment-safe.

The six raw Aeolus scalar Weather columns remain a separate E002 artifact and
must not be copied into this source or relabeled as forecasts.

## Timezone contract

1. Preserve original timestamp and timezone fields.
2. Normalize comparison timestamps to UTC with an explicit timezone database
   version.
3. Resolve airport local time from a versioned airport/timezone mapping.
4. Handle DST ambiguous/nonexistent local times explicitly and fail closed on
   unresolved rows.
5. Derive `prediction_cutoff_utc` from canonical schedule semantics without
   consulting actual departure or arrival time.

## Airport/station/location mapping

The source requires a versioned mapping from `ORIGIN=ATL` to the selected
station/grid/location. The mapping manifest must record coordinates, distance,
selection rule, station active interval, fallback hierarchy, and effective
dates. A provider switch or mapping change creates a new artifact version.

Because the V4 auxiliary task is outbound ATL, origin point-in-time Weather is
the default research family. Any destination Weather addition requires a
separate rationale and the same availability audit; it cannot silently expand
DEP-B.

## Join policy

For each target row:

1. Compute `prediction_cutoff_utc` only from `FL_DATE` and scheduled departure
   storage under the canonical datetime contract.
2. Restrict candidate Weather records to the approved ATL location mapping.
3. Filter to `information_available_time <= prediction_cutoff_utc` before any
   nearest-time or forecast-run selection.
4. For forecasts, select the latest eligible issue/run and the documented
   valid-time rule; never select a future issue because it is closer.
5. For observations, apply the approved publication delay/availability rule
   before time alignment.
6. Use deterministic tie-breaking and record the selected source record ID,
   issue/availability time, valid time, lead/lag, and join-rule version.
7. Reject duplicate or many-to-many joins unless an explicit aggregation rule
   is fit only within the training fold and remains point-in-time safe.

The DEP-A and DEP-B arms must retain identical target rows. Rows with missing
Weather are not silently removed from DEP-B.

## Missing-data policy

- Preserve target-row parity between DEP-A and DEP-B.
- Represent Weather availability/missingness explicitly only after its
  point-in-time safety is audited.
- Fit imputation inside each rolling training fold; never use future years,
  2023 selection rows, or 2024.
- Do not backfill from a future observation or future forecast issue.
- Report coverage and missingness per development fold/year and by variable.
- If coverage falls below a preregistered threshold or differs by experiment
  arm because rows were dropped, fail the comparability gate.

## Versioning and storage boundary

The future source belongs under a separate conceptual root such as:

```text
data/external/weather/weather_point_in_time_v1/
```

It must not be written under `data/raw/tabular`, merged into
`canonical_schema_v1`, or presented as original Aeolus Weather. A source
manifest must contain provider/version, source signatures, schema, variables,
units, mapping version, timezone version, join version, retrieval metadata,
coverage, and provenance-audit status.

Raw external downloads, if later authorized, must also be immutable and kept
separate from derived joined features. This baseline migration creates no
Weather data directory or dataset.

## Audit gates

| Gate | Required evidence | PASS condition | FAIL condition |
|---|---|---|---|
| W1 Source provenance | Primary provider documentation, license, version, immutable signatures | Source/version and historical semantics reproducible | Provider or version cannot be pinned |
| W2 Time semantics | Issue/publication, valid time, timezone, revision policy | All comparison timestamps auditable | Valid time is used as assumed availability |
| W3 Location mapping | Versioned ATL station/grid mapping | Deterministic, effective-date-aware mapping | Undocumented nearest location/fallback |
| W4 Availability | Row/rule-level `information_available_time` | Every joined value available by T-2h | Any look-ahead or unverifiable availability |
| W5 Join integrity | Deterministic key/time rule and diagnostics | One auditable selection per target row | Uncontrolled many-to-many/duplicate join |
| W6 Arm parity | DEP-A/DEP-B target-row identities | Exact row parity and only Weather differs | Target rows/preprocessing/model/budget differ |
| W7 Temporal leakage | Automated fold and cut-off tests | No future fit statistics or future issue | Any leakage path remains |
| W8 Reproducibility | Versioned manifest/config/test evidence | Join reruns deterministically | Missing source/config/hash evidence |

All gates are critical. No partial pass enables DEP-B.

## Leakage tests required before enablement

- Reject `issue_time > prediction_cutoff`.
- Reject observation `available_time > prediction_cutoff` even when
  `valid_time <= prediction_cutoff`.
- Reject missing/naive timezone and unresolved DST cases.
- Reject unknown provider/version/location mapping.
- Reject future backfill and nearest-run selection that crosses the cut-off.
- Reject duplicate/many-to-many joins.
- Assert exact DEP-A/DEP-B target-row identity and temporal folds.
- Assert raw Aeolus Weather remains forbidden in both tasks.
- Assert external Weather fields remain unknown/fail-closed until an explicit
  audited predictor contract is added.
- Assert no auxiliary prediction or Weather column enters Core Arrival or the
  downstream optimizer.

## PASS/FAIL criteria

`POINT_IN_TIME_WEATHER_PROVENANCE = PASS` only when W1–W8 pass, the source and
join artifacts are versioned, leakage tests pass, and the decision registry,
config, rules, tests, data dictionary, and experiment protocol are updated
before DEP-B runs.

`POINT_IN_TIME_WEATHER_PROVENANCE = FAIL` or incomplete evidence means:

```text
AUXILIARY_WEATHER = BLOCKED_NOT_CORE_FAILURE
CORE_ARRIVAL = CONTINUE
```

No provider is selected by this plan. Current status remains
`AUDIT_REQUIRED`; `weather_point_in_time_v1` remains conceptual and disabled.
