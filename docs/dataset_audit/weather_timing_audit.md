# Weather Timing Audit — Week 2

## Scope and decision rule

Audit date: 2026-08-23. The prediction-time contract is:

`T_cutoff = CRS_DEP_TIME - 2 hours`

This is a provenance and information-availability audit. It does not use correlations, model scores, target distributions, or 2024 performance. A raw weather field can be `KEEP_SAFE` only when its value time and publication/issue time prove that the value was available at or before `T_cutoff`.

The weather-field list was derived from `artifacts/manifests/canonical_schema_v1.json`, not from an assumed fixed list. The canonical schema contains exactly:

- origin: `O_TEMP`, `O_PRCP`, `O_WSPD`;
- destination: `D_TEMP`, `D_PRCP`, `D_WSPD`.

All six fields are present in 2016–2024. Presence and dtype compatibility are schema facts only; they do not prove point-in-time availability.

## Sources inspected

Evidence was inspected in the required order.

### A. Local project evidence

- Three synchronized V3 roadmaps, especially the T-2h feature-availability rule and the instruction to lag or drop weather without provenance.
- `artifacts/manifests/canonical_schema_v1.json`, `docs/dataset_audit/schema_compatibility_matrix.md`, `docs/dataset_audit/data_dictionary_v1.md`, and `docs/dataset_audit/leakage_audit.md`.
- Local source/config/document search for Meteostat extraction, weather timestamp, station/source metadata, forecast issue time, and weather join logic.

Result: the local project contains the six scalar weather columns but no weather observation timestamp, forecast issue/run timestamp, station/source flag, model-fill flag, or upstream join implementation.

### B. Official Aeolus code and dataset metadata

- [Official Aeolus repository](https://github.com/Flnny/Delay-data), branch `main`, inspected at commit [`6d10cab7a5d542733ff6a8b88d1ab4d4f98b1c6f`](https://github.com/Flnny/Delay-data/tree/6d10cab7a5d542733ff6a8b88d1ab4d4f98b1c6f), commit date 2025-07-29, retrieved 2026-08-23.
- Repository tree plus `README.md`, `Datasets/Flight_tab.py`, `Datasets/data_extract.py`, `Datasets/data_pro.py`, `Datasets/columns_and_data_info.yaml`, and `Datasets/arr_delay_data_info.yaml` at that commit.
- [Official Kaggle Aeolus dataset page](https://www.kaggle.com/datasets/flnny123/mfddmulti-modal-flight-delay-dataset/data), dataset version 4, last updated 2025-10-17, metadata retrieved 2026-08-23.

Result: the repository documents the field names and consumes already-created `flight_with_weather_<year>.csv` files. Its complete published tree does not contain the code that originally retrieves weather or joins it to flights. The Kaggle metadata supplies files and high-level dataset provenance, but no per-row weather valid time, issue time, join key, source station, or model-fill indicator.

### C. Primary external documentation

- [Aeolus NeurIPS 2025 paper](https://papers.neurips.cc/paper_files/paper/2025/file/586fbdff064d506f5af3e3db82681f84-Paper-Datasets_and_Benchmarks_Track.pdf), Section 3.1 and Appendix A. The paper identifies Meteostat as the source and describes the weather inputs as hourly measurements, but it does not publish the flight-to-weather timestamp alignment or point-in-time publication rule.
- [Meteostat hourly station API documentation](https://dev.meteostat.net/api/stations/hourly.html), retrieved 2026-08-23. It describes historical hourly observations, optional statistically model-filled gaps, a `time` of observation, and an observation availability offset of approximately two to three hours.
- [Meteostat hourly point API documentation](https://dev.meteostat.net/api/point/hourly), retrieved 2026-08-23. It likewise describes historical observations and optional model-filled gaps.

These sources are primary project/provider sources. No blog, tutorial, correlation, or model result was used as evidence.

## Provenance findings

1. The Aeolus paper supports that the underlying source is Meteostat hourly weather. It does not establish whether each released value is a direct station observation, an interpolated point value, or a model-filled gap.
2. The released Aeolus table has no weather timestamp. Therefore the represented hour cannot be reconstructed without assuming undocumented join logic.
3. The released code does not show whether weather was aligned to scheduled departure, actual departure, scheduled arrival, actual arrival, flight date only, or another timestamp.
4. There is no forecast issuance/run timestamp or archived forecast identifier. The six columns must not be called forecasts.
5. Meteostat's documented historical hourly observations are not instantaneously available: normal publication is delayed by roughly two to three hours, and some records arrive later. A weather valid time alone would therefore still be insufficient; point-in-time use also needs an availability/issue rule.
6. The published paper and repository disagree on example temperature units (paper Appendix A labels Fahrenheit while the repository README shows Celsius). This does not change the timing decision, but it is additional unresolved provenance metadata.

## Required questions and answers

| Question | Evidence-based answer |
|---|---|
| What timestamp does each value represent? | Not documented in the released CSV, repository, Kaggle metadata, or paper. |
| Observation or forecast? | Aeolus calls the source hourly measurements; Meteostat hourly data is historical observation-oriented and may contain model-filled gaps. Aeolus provides neither source flags nor forecast issue metadata, so the exact per-value class is not recoverable. It is not a documented point-in-time forecast. |
| Joined to scheduled or actual time? | Unknown; the construction/join code is absent from the published repository. |
| Could future observed weather have been used? | Cannot be ruled out. The absent join timestamp and availability metadata prevent a no-look-ahead proof. |
| Available at `CRS_DEP_TIME - 2h`? | Not evidenced for any of the six fields. |
| Can a safe lag be created from the existing Aeolus columns? | No defensible deterministic lag can be constructed from the current scalar columns because they omit observation valid time, publication time, station/source identity, and model-fill flags. A future separately versioned weather source could be audited and joined point-in-time, but that would be a new data pipeline, not a safe lag of the existing fields. |

## Per-field decision table

| Field | Side / measure | Represented timestamp | Observation vs forecast | Join anchor | Future-weather risk | T-2h availability | Safe lag from existing data | Status |
|---|---|---|---|---|---|---|---|---|
| `O_TEMP` | Origin temperature | Undocumented | Historical hourly measurement lineage; exact observation/model-fill status unavailable | Undocumented | Cannot be excluded | Not proven | No | `INSUFFICIENT_EVIDENCE` |
| `O_PRCP` | Origin precipitation | Undocumented | Historical hourly measurement lineage; exact observation/model-fill status unavailable | Undocumented | Cannot be excluded | Not proven | No | `INSUFFICIENT_EVIDENCE` |
| `O_WSPD` | Origin wind speed | Undocumented | Historical hourly measurement lineage; exact observation/model-fill status unavailable | Undocumented | Cannot be excluded | Not proven | No | `INSUFFICIENT_EVIDENCE` |
| `D_TEMP` | Destination temperature | Undocumented | Historical hourly measurement lineage; exact observation/model-fill status unavailable | Undocumented | Cannot be excluded | Not proven | No | `INSUFFICIENT_EVIDENCE` |
| `D_PRCP` | Destination precipitation | Undocumented | Historical hourly measurement lineage; exact observation/model-fill status unavailable | Undocumented | Cannot be excluded | Not proven | No | `INSUFFICIENT_EVIDENCE` |
| `D_WSPD` | Destination wind speed | Undocumented | Historical hourly measurement lineage; exact observation/model-fill status unavailable | Undocumented | Cannot be excluded | Not proven | No | `INSUFFICIENT_EVIDENCE` |

`INSUFFICIENT_EVIDENCE` is not promoted to `KEEP_SAFE`, `LAG_REQUIRED`, or a claim that a particular future timestamp was used. It records the evidence boundary exactly.

## T-2h conclusion

No canonical Aeolus weather field passes the T-2h availability contract. There is no evidence strong enough to use a raw weather value in the core candidate feature matrix, and no safe lag can be derived from the released scalar fields without guessing the upstream join.

This conclusion does not say that weather is unimportant. It says the released weather representation is not point-in-time auditable for this project's prediction contract.

## Core weather policy

Core policy: **DROP** all six raw weather columns from candidate `X`.

- Keep the columns unchanged in canonical/processed storage for traceability.
- Exclude them from Week-3 core predictors through `src/data/leakage_rules.py`.
- Do not relabel them as forecasts.
- Do not create heuristic lags from other flight rows.
- Reconsider only if versioned upstream construction evidence supplies the weather valid time, availability/issue time, source/model-fill provenance, timezone, and exact join key. Any reconsideration must update this audit, the decision registry, data dictionary, leakage rules, and tests before feature use.

The absence of usable core weather is not a project failure; schedule-only remains a valid locked comparison regime.

## Remaining uncertainty

- Exact weather valid timestamp and timezone.
- Scheduled-time versus actual-time join anchor at origin and destination.
- Station observation versus interpolated point data and per-field source station.
- Whether Meteostat model filling was enabled and which rows/fields were filled.
- Publication/availability timestamp for every value.
- Temperature, precipitation, and wind-speed unit convention in the delivered files.
- Original weather extraction/join code and its version.

None of these unknowns may be resolved from value distributions or model performance.

## V4 architecture addendum — 2026-08-26

E002 remains unchanged: the six raw Aeolus Weather columns retain
`INSUFFICIENT_EVIDENCE` and policy `DROP` for both Core Arrival and Auxiliary
Departure predictors. This addendum does not promote those fields, call them
forecasts, or authorize heuristic lags.

V4 introduces a separate, auxiliary outbound Departure research branch:
Schedule-only versus Schedule plus audited point-in-time Weather. That branch
requires a separately sourced and versioned artifact such as
`weather_point_in_time_v1`, governed by
`point_in_time_weather_plan_v1.md`. Its current status is `AUDIT_REQUIRED` and
disabled. It is not canonical Aeolus Weather and does not feed Core Arrival or
the downstream gate optimizer.

If the future source cannot prove
`information_available_time <= CRS_DEP_TIME - 2 hours`, the auxiliary Weather
experiment is blocked and recorded as a limitation; the core Arrival thesis
continues.
