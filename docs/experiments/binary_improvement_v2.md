# Binary classification improvement V2

This experiment improves both `P(ARR_DELAY >= 15)` for inbound ATL and
`P(DEP_DELAY >= 15)` for outbound ATL at scheduled departure minus two hours.
It does not replace the delay-distribution models used by the optimizer.

## Run

From the repository root with the existing Python 3.11 environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-binary.txt
.\.venv\Scripts\python.exe scripts\run_binary_improvement_v2.py --smoke
.\.venv\Scripts\python.exe scripts\run_binary_improvement_v2.py
.\.venv\Scripts\python.exe scripts\audit_binary_improvement_baselines.py artifacts\binary_improvement_v2\<run>
.\.venv\Scripts\python.exe scripts\package_binary_improvement_v2.py artifacts\binary_improvement_v2\<run> artifacts\binary_improvement_v2\release_<run>
```

After installing the pinned environment, `--smoke` uses small, explicitly labelled datasets. Its models cannot
be recommended for promotion. The next command runs the full protocol with a 12-hour
wall-clock budget. No command starts a dashboard, browser or notebook. Training
requires the local 2016–2022 processed partitions; only the runnable dashboard
sample partitions are bundled in Git. Loading a saved bundle does not require
the training partitions or a separate download of its encoder/calibrator.
The packaging command verifies completed-run source/model hashes, creates CPU
inference copies in a new release directory, checks each in a fresh Python
process, and adds paired bootstrap diagnostics for all research candidates.
It never changes the frozen model decision or activates a dashboard model.
The baseline audit command adds the matching full-row rolling XGBoost and constant
baseline controls, with candidate AP deltas by year, using only cached
2016–2021 data. It does not change selected models or thresholds. The fixed
baseline procedure is descriptive and is excluded from model selection.

The output directory must be new. Completed output is never silently overwritten
or resumed with changed source/configuration. Read `progress.json` for current
activity, `summary.json` and `REPORT.md` for results, and each task's files for
detailed evidence. Working caches, row predictions and Optuna databases are
ignored by Git; models, hashes, metrics and reports remain reviewable artifacts.

## Temporal protocol

| Partition | Purpose |
|---|---|
| 2016–2021 | Feature development, screening, rolling validation, final classifier fit |
| Rolling 2019, 2020, 2021 | Train only on earlier years; full validation populations |
| Q1 2022 | Fit candidate calibrators |
| Q2 2022 | Choose calibration method; refit selected method on Q1–Q2 |
| Q3 2022 | Select F1 threshold with precision >= 1.5 times Q3 prevalence |
| Q4 2022 | Frozen-rule candidate selection |
| 2023 | One historical confirmation after saving model hashes and threshold decisions |
| 2024 | Blocked before cache or filesystem access |

These historical periods have already participated in project development.
Neither the new split nor bootstrap creates an untouched test. Historical 2024
evaluation also means it cannot honestly be called an unseen holdout again.
The frozen V1/Week 4/Week 5 protocols are preserved; this is a separate version.

## Features and training

- F0 reproduces each task's original raw feature set and tree preprocessing.
- F1 adds scheduled arrival clock, cyclic clock/calendar representations and
  carrier–route, carrier–hour and carrier–flight interactions. All are schedule
  sources. No actual operations, weather or unapproved chain features are used.
- F2 adds frequency and smoothed historical event rates, smoothing strength 50.
  Train encodings for a year use strictly earlier years. The first year uses
  prior 0.5 without reading its own labels. Inference maps use only training
  data, stay frozen, and give unknown groups the training prior and zero
  frequency. These are learned offline statistics, not live delay observations.
- Screening uses up to 300,000 proportionally sampled training rows. November–
  December 2020 is reserved for early stopping; full 2021 is scored for HPO.
- Each task requests at most 12 XGBoost and 6 HGB trials. Two family winners
  must finish three full-data rolling folds to remain eligible.
- Execution revision `fixed_iteration_challengers_v1` compares early stopping
  against fixed iteration counts (XGBoost 100/300/600/1200; HGB 100/200/300).
  The first development-only run selected 5 trees on late-2020 early stopping
  and was stopped before reading 2023. Its interrupted evidence is retained;
  adding these challengers does not increase the trial budget. Fixed-count
  models do not consult early-stopping labels; the separate 2021 screening
  population still supplies the Optuna objective.
- XGBoost tries CUDA first; CPU fallback is recorded. HGB uses CPU with bounded
  OpenMP/BLAS threads. Optuna and model seeds are 202601.
- Deadline-stopped fits are discarded. An unfinished full-validation candidate
  cannot be promoted. Screening stops at hour 5 and verification at hour 9 to
  reserve final calibration/evaluation time. Per-fit cap is 15 minutes.

`controlled_ablation.json` uses identical parameters, rows, seed and validation
year for F0/F1/F2. Optuna trial comparisons are labelled diagnostic, because
different parameters would confound an attribution to features alone.

## Calibration, thresholds and recommendation

Compare identity, sigmoid on log-odds, and isotonic. Choose by Q2 Brier; within
0.001 of the best use the frozen simplicity order sigmoid, identity, isotonic.
Refit that method on Q1–Q2 only. Choose the threshold on Q3; ties prefer higher
precision then a higher threshold. If the precision floor is infeasible, keep
0.5 and report it rather than weakening the floor. Every evaluation reports
both the fixed 0.5 threshold and the selected threshold.

All baselines and candidates train on the same eligible 2016–2021 rows and use
the same calibration/threshold procedure. Promotion gates compare with the
new full-data F0 XGBoost baseline, not a historical baseline scored on different
rows: AP gain >= 0.005; ROC drop <= 0.005; Brier increase <= 2%; selected-threshold
F1 gain >= 0.02; and the preselected precision floor must hold. Select on Q4;
within AP difference 0.005 prefer lower Brier, then shorter fit time.

The selection and model hashes are saved **before reading 2023**. Confirmation
does not choose new parameters or thresholds. A recommended research upgrade
also needs the same gates on 2023 and a positive lower 95% paired 7-day block
bootstrap bound for AP gain (1,000 resamples). If it fails, keep existing models.
No automatic changes to the dashboard registry or optimizer are made by this
research runner. Published results include sample counts, prevalence, monthly,
carrier and route diagnostics, AP/ROC/Brier/log-loss/ECE, confusion matrices,
alert rates, inference times, curves and portable model reload checks.

## Use a saved model

```python
import joblib
import pandas as pd

model = joblib.load("artifacts/binary_improvement_v2/<run>/arrival/xgboost_candidate.joblib")
schedule = pd.read_parquet("my_canonical_schedule.parquet")
result = model.predict_schedule(schedule)
# flight_key, p_delay, predicted_delayed, decision_threshold
```

Schedules use the repository's canonical timestamp representation and require
flight keys. No delay target is required at inference. Any supplied actual
delay is discarded before feature preparation. `predict_proba` accepts the
prepared schedule feature frame and preserves the standard two-column class
order `[0, 1]`. Empty prepared batches return shape `(0, 2)`.

The saved bundle includes the fitted encoder, preprocessor, classifier,
calibrator, threshold and task metadata. Their classes are importable modules,
avoiding the legacy `__main__.CalibratedPredictor` pickle problem. Keep the
repository code and pinned dependencies alongside the model.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_binary_improvement_v2.py -q
```

The suite covers time-safe history encodings, unknown categories, invalid
probabilities, threshold tradeoffs, paired bootstrap ties, promotion rejection
for threshold-only gains, fresh-process persistence, empty prediction batches,
inference without outcomes, and the unconditional 2024 access block.

Primary references: [threshold tuning](https://scikit-learn.org/stable/modules/classification_threshold.html),
[probability calibration](https://scikit-learn.org/stable/modules/calibration.html),
[XGBoost GPU support](https://xgboost.readthedocs.io/en/stable/gpu/index.html).
