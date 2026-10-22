# Binary Improvement V3

V3 targets at least one Arrival and one Departure classifier passing every
unchanged V2 Q4/2022 target. Both remain T-2h classifiers for delays >=15 minutes.
All results are historical development evidence. No untouched test is available;
2024 is blocked. No dashboard or optimizer activation occurs in this runner.
The pre-run data diagnosis and its limits are documented in
[`binary_improvement_v3_diagnosis.vi.md`](binary_improvement_v3_diagnosis.vi.md).

## Reproduce

Use Python 3.11 and the repository's existing local processed training data:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-binary-v3.txt
.\.venv\Scripts\python.exe -m pytest tests\test_binary_improvement_v3.py -q
.\.venv\Scripts\python.exe scripts\run_binary_improvement_v3.py --smoke
.\.venv\Scripts\python.exe scripts\run_binary_improvement_v3.py
.\.venv\Scripts\python.exe scripts\plot_binary_improvement_v3.py artifacts\binary_improvement_v3\<run>
.\.venv\Scripts\python.exe scripts\validate_binary_improvement_v3.py artifacts\binary_improvement_v3\<run>
.\.venv\Scripts\python.exe scripts\diagnose_binary_v3_results.py artifacts\binary_improvement_v3\<run>
```

`--output <new-directory>` is supported. Runs never overwrite an existing
directory. A smoke run uses labelled small samples and cannot produce Q4_PASS.
Progress is in `progress.json`; detailed metrics in `model_results.json`;
the Vietnamese human-readable report is `RESULTS.vi.md`.
For a read-only progress/trial count snapshot, use
`python scripts/status_binary_improvement_v3.py <run-directory>`.
The independent validator writes `validation.json`: it verifies source/data/model
hashes, recomputes stored Q4 and 2023 metrics, checks the full Q4 population against
V2 and loads every CPU bundle for raw schedule inference without outcome columns.
Validation success confirms artifact integrity; `goal_both_tasks_pass` separately
states whether both tasks actually met all unchanged Q4 targets.
For a completed run where both tasks have `NO_Q4_PASS`, the posthoc diagnostic
script writes `posthoc_diagnosis.json` and appends the observed month shift and
oracle threshold analysis to the report. Oracle thresholds use Q4 labels and
are never installed, selected or treated as qualified models.

## Executed run, 2026-10-21/22

`artifacts/binary_improvement_v3/full_qualified_20261021` completed all 192 HPO
trials and exported 36 CPU bundles in 7,933.5 seconds. Independent artifact and
raw-schedule inference validation passed; regression checks passed 135 tests.
Both tasks retained `NO_Q4_PASS`; all 36 seed variants failed at least one gate.
Arrival's highest primary-seed F1 was .342415 (required .350305). Departure's
highest primary-seed F1 was .371656 (required .379557), from the matched
retraining control, which also missed the AP gate. No model was activated.
See the run's `RESULTS.vi.md`, `validation.json` and `posthoc_diagnosis.json`.

## Frozen target and temporal roles

The exact AP/ROC/Brier/F1/Precision values are derived from the existing V2
baseline metrics and saved with their SHA256. Candidate data never change these
absolute targets. The approximate targets are:

| Task | AP >= | ROC >= | Brier <= | F1 >= | Precision >= |
|---|---:|---:|---:|---:|---:|
| Arrival | .266209 | .658022 | .126303 | .350305 | .252018 |
| Departure | .320704 | .662131 | .140428 | .379557 | .309651 |

| Role | A | B |
|---|---|---|
| Maximum classifier training date | 2021-12-31 | 2022-06-30 |
| Calibrator fit | 2022 Q1 | July 2022 |
| Calibrator method selection | 2022 Q2 | August 2022 |
| Calibrator refit | 2022 H1 | July-August 2022 |
| Threshold selection | 2022 Q3 | September 2022 |
| Final historical target | 2022 Q4 | 2022 Q4 |

All ranges are calendar-date-inclusive. Native/historical models try the
full history, a two-year window or a three-year window before the training
cutoff, with no time decay or a 365-day half-life. The first 90 calendar days
in each training window are history warmup and excluded from classifier fit
for every representation, including matched controls.

HPO uses matching A/B simulations on Q4/2019 and Q4/2021. Full-row verification
adds Q2/2022 using the same nine-month (A) or three-month (B) separation from
training cutoff to the scored quarter. Q4/2020 is reported as a stress case
outside the HPO objective. Scored periods, calibration periods and classifier
training periods never overlap within a fold.

Q4/2022 labels are inaccessible to the bounded reader until every concrete
final model, threshold and hash is written to `selection_freeze.json`.
2023 is inaccessible until the Q4 decision is frozen separately. Reads are
projected through Arrow filters; entire 2022 label frames are never loaded and
then filtered in Python. 2024 is rejected before any IO/cache access.

## Representations, classifiers and selection

- `original` reproduces V2 feature information and tree preprocessing.
- `native` represents carrier and airport as unordered categorical columns,
  adds cyclic calendar/clock features and distances to rule-derived US federal
  holidays, and keeps a train-fitted carrier-flight frequency.
- `history` also adds smoothed rates/frequencies for carrier, route,
  carrier-route, carrier-hour and carrier-flight. Group-month counts use
  cumulative counts **minus the current month**. The historical prior likewise
  excludes the current month. At inference all mappings are frozen at train
  cutoff; unknown categories become missing and unknown history groups use
  the training prior/zero frequency. Absolute calendar year is absent from
  native/history predictors and remains present in the original Arrival control.

Each task/branch requests up to 24 XGBoost, 12 HGB and 12 LightGBM trials (192
total). Fixed boosting iteration counts are searched explicitly; random
internal early-stopping splits are not used. XGBoost tries CUDA, while HGB and
LightGBM use CPU. Positive-class weights are training-only. Native categorical
cardinality is checked against the HGB 255-category bound.

Optuna maximizes AP improvement and F1 improvement together on historical
folds with explicit ROC/Brier/Precision/threshold-feasibility constraints. The
deterministic shortlist order is: more folds passing all relative gates, then
more satisfied guard constraints, then the minimum of normalized AP/F1 gains,
then AP gain, then F1 gain.
One family winner per algorithm enters full verification when available.
Relative gates use the same fold's matched control and the same validation
rows. At most two final candidates survive per task/branch.

The best full-verification global configuration is also tested with a DL
expert using the same parameters. Mixing alphas are .25/.5/.75/1.0, fitted and
chosen only on historical development folds. Non-DL flights always use the
global classifier; unsupported experts cannot become a selected DL mixture.

Identity, sigmoid, isotonic and regularized carrier-aware calibration are
compared by selection-period Brier. Within .001, prefer simpler calibration.
Carrier calibration uses a log-odds slope and one-hot carrier intercepts, with
C in .1/1/10. Carriers with <1000 calibration rows or <100 positives use the
global calibrator. The chosen method is refit on its fit+selection periods.
One global decision threshold maximizes F1 subject to the **fixed original V2
precision floor** on final models. Internal fold floors use their own threshold
period prevalence, never future 2022 statistics.

## Results and integrity

All final models, including matched retraining controls, use deployment seed
202601 and diagnostic seeds 202602/202603; seeds never select a better-looking
deployment result. Controls are eligible for the same absolute Q4 gates; their
role is retained so a data-update gain is not attributed to HPO. This policy
was clarified before opening any new Q4 model scores. Every model is exported for CPU inference and
checked in a fresh Python interpreter before its pre-Q4 freeze.

Q4_PASS is the conjunction of all five absolute metric targets and a feasible
threshold. Passing primary-seed candidates are ranked by AP, then Brier within
an AP .005 indifference band, then inference time. Seed stability is a separate
reported result. Each primary candidate receives 1,000 paired 7-day bootstrap
resamples for AP, ROC-AUC, Brier and F1 differences against the frozen V2 model.
Historical 2023 confirmation cannot change models or thresholds.

The run directory contains exact configuration, source snapshots and hashes,
source data hashes, full fold records, feature ablations, stress results,
per-flight predictions (locally ignored in Git), model bundles, freeze manifests
and the final report. Working caches/databases and smoke outputs are ignored.
Existing V2 artifacts are not rewritten.

The 12-hour budget reserves hours 0-6 for screening, 6-9 for verification and
hours 9-10.5 for final fitting. Remaining time is reserved for Q4/2023 scoring,
uncertainty and reports. Fits stopped by the deadline are incomplete and cannot
pass. All numerical backends use at most 8 threads and one model fit at a time.

## Portable inference

```python
import joblib
model = joblib.load("<run>/models/<model_id>.joblib")
predictions = model.predict_schedule(canonical_schedule_dataframe)
```

No target or training files are needed for inference. The bundle contains all
encoding, classifiers/experts, calibration and threshold state. Preserve this
repository code and the pinned dependencies alongside the model. Standard
`predict_proba(prepared_frame)` returns columns `[P(0), P(1)]`.
