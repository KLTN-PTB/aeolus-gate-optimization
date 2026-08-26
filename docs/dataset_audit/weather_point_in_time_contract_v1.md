# Weather Point-in-Time Contract V1

Contract review date: 2026-08-26  
Protocol: Research Protocol V4.0  
Task: `departure_auxiliary`  
Planned source artifact: `weather_point_in_time_v1`  
Provider: `TBD`  
Current provenance status: `AUDIT_REQUIRED`  
Enabled: `false`

## 1. Purpose and authority

This Week 3C reviewed contract operationalizes
`point_in_time_weather_plan_v1.md`; it does not replace or rewrite that plan.
The plan remains the research intent and this document plus
`weather_point_in_time_contract_v1.json` is its executable audit template.
No provider, product, source data, or Weather variable has been approved.

The contract applies only to the auxiliary outbound experiment:

```text
DEP-A = Schedule-only
DEP-B = identical target rows and protocol + audited point-in-time Weather
ORIGIN = ATL
y_dep_cls = 1[DEP_DELAY >= 15]
target_prediction_cutoff = CRS_DEP_TIME - 2 hours
```

There is no Departure regression. Weather may not enter Core Arrival,
simulation, or optimization. Failure of this contract is
`DEP_B = BLOCKED_NOT_CORE_FAILURE`; Core Arrival continues.

## 2. Boundaries retained from V4

The six Aeolus fields `O_TEMP`, `O_PRCP`, `O_WSPD`, `D_TEMP`, `D_PRCP`, and
`D_WSPD` remain E002 `INSUFFICIENT_EVIDENCE` and `DROP_FROM_PREDICTORS` for
both tasks. They are not forecasts, cannot substitute for an external source,
and cannot be made admissible by a row/day shift or heuristic lag.

Any future external source belongs under the conceptual
`data/external/weather/` boundary and is versioned independently. It must not
be written to `data/raw/tabular/` or described as canonical Aeolus Weather.
Week 3C creates no data directory or source artifact.

## 3. Weather semantic classes

| Class | Required interpretation | Predictor default |
|---|---|---|
| `FORECAST` | A versioned product issued for a future or contemporaneous valid time. Issue, publication, availability, and valid-time provenance are distinct. | Audit required. |
| `OBSERVATION` | A measurement with separate observation and publication/availability times. `observation_time` is not information availability. | Audit required. |
| `REANALYSIS` | A retrospective reconstruction generally produced after the event. | `BLOCKED_FOR_PREDICTOR_USE` unless the exact version proves pre-cutoff availability. |
| `MODEL_ANALYSIS` | A model analysis that may assimilate information unavailable at operational cutoff. | `BLOCKED_FOR_PREDICTOR_USE` unless the exact version proves pre-cutoff availability. |
| `MODEL_FILL` | Interpolated/backfilled/model-filled values whose creation time may be retrospective. | `BLOCKED_FOR_PREDICTOR_USE` unless the exact version proves pre-cutoff availability. |

Unknown classes fail closed. Retrospective products may be retained only for
explicit diagnostic/research use and must not enter DEP-B predictors.

## 4. Source identity and immutable provenance

A future source manifest must record:

- provider, dataset/product name, and product version;
- retrieval date, source URLs or identifiers, and license/usage reference;
- file names, byte sizes, and hash/signature where feasible;
- time coverage, location coverage, variables, units, and timezone semantics;
- exact retrieval parameters and response metadata when an API lacks an
  immutable version, with that limitation stated explicitly.

`provider = TBD` remains locked until a separate evidence audit. Familiarity,
convenience, or model performance cannot select or approve a provider.

## 5. Time and timezone contract

The minimum logical fields are:

```text
issue_time
publication_time
available_time
valid_time
```

For observations, `observation_time` is also required. Provider field names
may differ only when a documented mapping identifies which source field and
primary evidence establishes each logical meaning. Missing availability
semantics fail closed. In particular, the contract never silently sets
`available_time = issue_time`.

Canonical storage is timezone-aware UTC, consistent with the existing
canonical datetime amendment. Every record retains the source timezone,
normalized UTC timestamp, and conversion rule. When local timestamps occur,
DST behavior, ambiguous local times, and nonexistent local times must be
documented and deterministically handled. Naive timestamps fail closed.

## 6. ATL location mapping

DEP-B covers outbound `ORIGIN=ATL`. A source location may be an airport,
station, grid point, or forecast grid cell, but its mapping must record:

- `location_type`, `location_id`, latitude, and longitude;
- the source mapping rule and mapping version;
- distance to ATL where applicable;
- effective dates or versions when station/grid mappings change.

"Nearest station" is not automatically correct. Location fitness must pass a
documented audit for the selected product and variable semantics.

## 7. Variable metadata

No exact variable set is selected in Week 3C. Temperature, precipitation, and
wind speed are candidate families only. Each future variable must record its
source and canonical names, units, measurement/forecast meaning, aggregation
window, height/level where applicable, and missing-value semantics. No Aeolus
`O_`/`D_` scalar is automatically mapped to an external variable.

## 8. Point-in-time join and deterministic selection

For every outbound target row:

1. derive `target_prediction_cutoff` from canonical scheduled
   `CRS_DEP_TIME - 2 hours`, never actual time;
2. restrict records to the approved ATL location mapping and compatible
   product/variable semantics;
3. filter by `publication_time <= cutoff` and
   `available_time <= cutoff` before considering valid time;
4. for forecasts also require `issue_time <= cutoff`;
5. among eligible records, prefer the latest eligible issue (or documented
   observation publication), then nearest compatible `valid_time`;
6. break remaining ties deterministically by provider, product, version,
   location ID, and record ID, and record the selected source metadata.

`valid_time <= cutoff` is neither required in all forecast applications nor
sufficient for availability. A record published after cutoff is rejected even
if its valid time precedes cutoff. For a 07:00 cutoff, a forecast available at
05:10 is eligible while one issued at 08:00 and available at 08:05 is not.

Duplicate provider/product/version/location/issue-or-observation/valid keys
must be detected and reported. Arbitrary `drop_duplicates(keep="first")` is
forbidden. Duplicates fail unless a future versioned contract explicitly
defines and tests a semantically valid deterministic resolution.

## 9. DEP-A/DEP-B row parity and missing Weather

`row_parity_required = true`: DEP-A and DEP-B use the exact same ordered target
rows. Missing Weather never changes target eligibility and may not drop rows
only from DEP-B. A future artifact must carry a `weather_available` flag,
missing reason, and coverage statistics. Detailed imputation is deferred until
a source passes audit and the policy is locked; it may not be chosen from model
performance.

## 10. W1-W15 critical audit gates

| Gate | Requirement | PASS evidence |
|---|---|---|
| W1 | Source identity/version | Provider, product, and version uniquely identified. |
| W2 | License/retrieval provenance | Retrieval, source identifiers, license, files, sizes, and hashes/signatures recorded. |
| W3 | Weather semantic class | Forecast/observation/retrospective meaning explicitly classified. |
| W4 | Time fields present | Required logical times and mappings are complete. |
| W5 | Availability-time semantics proven | Primary evidence proves the field representing information availability. |
| W6 | Timezone/DST proven | Source timezone, UTC normalization, conversion, and DST rules are deterministic. |
| W7 | ATL location mapping proven | Versioned airport/station/grid mapping is defensible. |
| W8 | Units/variable semantics proven | Units, aggregation, level, and missing meaning are documented. |
| W9 | Point-in-time join deterministic | Availability-first join and tie-break are versioned and reproducible. |
| W10 | No future availability leakage | Synthetic and later source tests reject post-cutoff information. |
| W11 | DEP-A/DEP-B row parity | Exact target row identity/order is preserved. |
| W12 | Missing-data policy | Missing Weather retains rows and records flags/reasons/coverage. |
| W13 | Duplicate/tie-break determinism | Duplicates are rejected or resolved only by an approved deterministic rule. |
| W14 | No raw Aeolus substitution | All six E002 fields remain excluded. |
| W15 | No Core Arrival/optimizer path | Weather is confined to auxiliary DEP-B. |

All gates are critical. There is no average score or majority vote. A provider
can receive `POINT_IN_TIME_WEATHER_PROVENANCE = PASS` only when W1-W15 all
PASS. Any failed or unproven critical gate yields:

```text
POINT_IN_TIME_WEATHER_PROVENANCE = FAIL / INSUFFICIENT_EVIDENCE
DEP_B = BLOCKED_NOT_CORE_FAILURE
CORE_ARRIVAL = CONTINUE
```

No partial enablement, raw-Weather substitution, weakened cutoff, or heuristic
lag is permitted.

## 11. Provider evaluation template

No provider rows are populated in Week 3C.

| provider | product | semantic class | versioning | issue time | publication/availability time | valid time | timezone | historical archive | ATL location resolution | variables | license | immutable/version evidence | point-in-time eligibility | result | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|

## 12. Future decision template

```text
Provider:
Product/version:

W1: PASS / FAIL / UNPROVEN
W2: PASS / FAIL / UNPROVEN
W3: PASS / FAIL / UNPROVEN
W4: PASS / FAIL / UNPROVEN
W5: PASS / FAIL / UNPROVEN
W6: PASS / FAIL / UNPROVEN
W7: PASS / FAIL / UNPROVEN
W8: PASS / FAIL / UNPROVEN
W9: PASS / FAIL / UNPROVEN
W10: PASS / FAIL / UNPROVEN
W11: PASS / FAIL / UNPROVEN
W12: PASS / FAIL / UNPROVEN
W13: PASS / FAIL / UNPROVEN
W14: PASS / FAIL / UNPROVEN
W15: PASS / FAIL / UNPROVEN

POINT_IN_TIME_WEATHER_PROVENANCE =
PASS / FAIL / INSUFFICIENT_EVIDENCE

DEP_B =
ENABLED_FOR_CONTROLLED_EXPERIMENT / BLOCKED_NOT_CORE_FAILURE
```

## 13. Week 3C decision and non-results

Week 3C completes contract preparation only. Provider selection, download/API
access, source ingestion, Weather joining, feature-matrix construction,
outbound label/preprocessing execution, DEP-A/DEP-B, and model training were
not performed. No row-level 2024 data was accessed. The current state remains:

```text
POINT_IN_TIME_WEATHER_PROVENANCE = AUDIT_REQUIRED
EXTERNAL_WEATHER_ENABLED = false
PROVIDER_SELECTED = NO
```

This unresolved auxiliary state does not block Week 4/5 Core Arrival work.
Week 6 DEP-B may run only after a later provider-specific W1-W15 PASS.

