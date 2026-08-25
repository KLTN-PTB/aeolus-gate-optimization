# Schema compatibility matrix — v1 (2026-08-23)

Source evidence: `artifacts/manifests/schema_audit/schema_2016.json` through `schema_2024.json`. This is a structural/data-quality audit, not model-result access.

| Year | Rows | FL_DATE coverage | Columns | Dtype/order | ARR_DELAY finite | Carrier | Origin / destination | Weather fields | Index characteristics | Duplicate rows |
|---|---:|---|---:|---|---:|---:|---|---|---|---:|
| 2016 | 5,537,987 | 2016-01-01–2016-12-31 | 34 | compatible | 5,537,987 | 12 | 308 / 308 | 6 | 308 / 308 | 0 |
| 2017 | 5,575,872 | 2017-01-01–2017-12-31 | 34 | compatible | 5,575,872 | 12 | 312 / 312 | 6 | 312 / 312 | 0 |
| 2018 | 6,986,842 | 2018-01-01–2018-12-31 | 34 | compatible | 6,986,842 | 18 | 316 / 316 | 6 | 316 / 316 | 0 |
| 2019 | 7,161,827 | 2019-01-01–2019-12-31 | 34 | compatible | 7,161,827 | 17 | 316 / 316 | 6 | 316 / 316 | 0 |
| 2020 | 4,312,091 | 2020-01-01–2020-12-31 | 34 | compatible | 4,312,091 | 17 | 316 / 316 | 6 | 316 / 316 | 0 |
| 2021 | 5,755,666 | 2021-01-01–2021-12-31 | 34 | compatible | 5,755,666 | 17 | 316 / 317 | 6 | 316 / 317 | 0 |
| 2022 | 6,413,416 | 2022-01-01–2022-12-31 | 34 | compatible | 6,413,416 | 17 | 316 / 316 | 6 | 316 / 316 | 0 |
| 2023 | 6,645,461 | 2023-01-01–2023-12-31 | 34 | compatible | 6,645,461 | 15 | 309 / 309 | 6 | 309 / 309 | 0 |
| 2024 | 6,284,841 | 2024-01-01–2024-12-31 | 34 | compatible | 6,284,841 | 15 | 305 / 306 | 6 | 305 / 306 | 0 |

## Findings

- All 34 columns are present in the same order in all nine years. Observed storage dtypes are compatible across years; no column-level dtype drift was found.
- `FL_DATE` covers exactly its labelled calendar year. `ARR_DELAY` is present and finite for every audited row; all year summaries contain its signed distribution and `>=15` count/rate.
- The six weather columns (`O_TEMP`, `O_PRCP`, `O_WSPD`, `D_TEMP`, `D_PRCP`, `D_WSPD`) are present in every year. Their provenance and availability at T-2h remain unresolved; presence is not a SAFE-feature decision.
- Cardinalities change across years (notably carrier and airport participation), which is expected population drift rather than schema incompatibility.
- Exact streaming duplicate detection found zero duplicate rows per file using a temporary disk-backed dual-hash index. The negligible hash-collision caveat remains recorded in each machine summary.
- The separate streaming mapping evidence in `artifacts/manifests/airport_index_mapping_audit.json` found `ORIGIN -> ORIGIN_INDEX` **STABLE** and `DEST -> DEST_INDEX` **STABLE** across 2016–2024, with no within-year or cross-year conflicts. This establishes mapping stability, not feature availability or modelling safety.

## Schema drift conclusion

No unreconcilable structural drift was found. The canonical schema is therefore ready as `canonical_schema_v1`; it is a storage/schema contract and does not finalize feature inclusion.
