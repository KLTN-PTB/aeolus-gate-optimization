# Day 1 Feature Gap Closure Implementation Plan

## Goal

Close the Phase A regression comparison gap without changing the frozen V1
manifest, reading blocked years, weather, raw Flight Chain artifacts, or
actual-operation fields. Produce exact scheduled-arrival features, per-fold
carrier/hour target encoding, two benchmark reports, new manifests, and the
Day 1 note.

## Design decision

The live Phase A script currently consumes Protocol V2 features, which omit
`calendar_year`; the frozen Week 5 HPO result references Protocol V1, whose
predictor list contains 11 columns including `calendar_year`. To keep the
V1.1 manifest truthful and the tuned-parameter comparison aligned with HPO,
the new benchmark path will use the existing V1 feature preparation plus the
two exact scheduled-arrival clock columns. Existing V2 behavior remains
unchanged except that the projected raw source will retain `CRS_ARR_TIME`.

The target encoder will consume only `OP_CARRIER`,
`scheduled_arrival_hour`, and the training label (`y_arr_reg` or
`ARR_DELAY`). It will return the encoded value and cell count aligned to the
requested application frame. Validation target values are ignored. A single
mapping is fit independently for each benchmark seed/fold and is never reused
across folds or variants.

## Files

- Modify `src/features/tabular_features.py`: retain `CRS_ARR_TIME` in the
  safe source projection, parse its schedule clock without rollover/duration
  derivation, and expose the two V1.1 predictors.
- Modify `src/data/preprocessing.py`: allow optional target-encoding numeric
  columns while preserving existing callers.
- Modify `src/models/baselines.py`: prefer exact
  `scheduled_arrival_hour` over the approximation and preserve fallbacks.
- Modify `src/features/refactored_features.py`: add the stateless
  `compute_carrier_arrhour_median` helper and its logging/fallback contract.
- Modify `src/data/stratified_loader.py`: add an explicit V1.1 feature-set
  selection used only by the new benchmark path.
- Modify `scripts/run_phase_a_benchmark.py`: support V1.1/V1.2a/V1.2b,
  load frozen XGBoost HPO parameters, preserve `reg:squarederror`, compute
  target encoding per seed/fold, and write a caller-selected report path with
  timestamps and input hashes.
- Create `artifacts/manifests/feature_manifest_arrival_v1_1.json`.
- Create `artifacts/manifests/feature_manifest_arrival_v1_2.json`.
- Create `artifacts/manifests/phase_a_benchmark_report_v1_1.json`.
- Create `artifacts/manifests/phase_a_benchmark_report_v1_2a.json`.
- Create `artifacts/manifests/phase_a_benchmark_report_v1_2b.json`.
- Modify/add tests for exact schedule parsing, baseline priority, target
  encoding fallback/smoothing, and validation-label independence.
- Create `docs/notes/day1_feature_gap_closure.md` with the verification note,
  comparison table, gates, anomalies, and selected Day 2 feature set.

## Verification sequence

1. Add failing unit tests for exact scheduled time and target encoding.
2. Run those tests and confirm expected failures.
3. Implement the smallest production changes.
4. Run focused tests, then the full test suite.
5. Run the V1.1, V1.2a, and V1.2b five-seed Phase A benchmarks. These use
   only 2016--2022 and never access 2023/2024.
6. Validate report schemas, hashes, manifest immutability, no-NaN/range
   assertions, and the final Day 1 note.
