# Week-5 HGB HPO v1.1 Design

## Purpose

Execute the two frozen HistGradientBoosting Optuna studies for Core Arrival
without changing any statistical field in `week5_hpo_protocol_v1_1`.

## Architecture

`src/models/week5_hist_gradient_boosting_hpo.py` supplies a narrowly scoped
estimator factory.  A new command-line runner coordinates the existing generic
four-fold HPO engine, protocol loader, fresh SQLite policy, Windows execution
guard, heartbeat monitor, and HGB factory.  Each study owns a guard journal and
a heartbeat journal so cleanup evidence is unambiguously attributable.

The runner writes an immutable result manifest immediately after each completed
study. After regression completes it writes a new summary and independently
queries both SQLite stores to verify trial states, objectives, parameter-space
membership, protocol attributes, and journal evidence.

## Fixed constraints

- Protocol: `week5_hpo_protocol_v1_1`, hash
  `b987c0489c5d18b02500f34c786c01359f45e50b2b32bdea3de4332a161556e5`.
- Classification maximizes equal-fold mean PR-AUC using probabilities;
  regression minimizes equal-fold mean MAE for signed `ARR_DELAY`.
- Exactly the locked 2016--2022 folds; no row-level 2023 or 2024 access.
- Exactly 10 complete trials per study, `TPESampler(seed=202601)`,
  `NopPruner`, Optuna `n_jobs=1`, and one 14,400-second timeout per study.
- HGB uses only the frozen search spaces and `early_stopping=False`.
- Classification must complete validly before regression begins.
- Guard telemetry must explicitly contain activation and cleanup events for
  each individual study; cleanup success is mandatory for acceptance.

## Error handling

Any storage, journal, immutable-manifest, protocol, guard, or suspend anomaly
fails closed. A suspension sets `ENVIRONMENTAL_EXECUTION_INVALID`, stops further
trial scheduling at the next safe boundary, preserves evidence, and prevents
regression from starting. Incomplete classification prevents regression.

## Testing

Tests cover strict HGB parameter construction, frozen early-stopping and class
weight behavior, fresh-study preflight, ordering, independent guard-journal
cleanup evidence, manifest objective recomputation, and verification rejection
of malformed evidence. Production begins only after targeted tests pass.
