# Week-5 Tuned Development OOF Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Materialize immutable, four-fold 2019--2022 development OOF Parquet for HPO-selected RF, HGB, and XGBoost parameters.

**Architecture:** A provenance loader verifies each authoritative summary, task result manifest, and completed Optuna SQLite study before projecting frozen parameter dictionaries into the existing `run_fold_experiment` estimator-bundle interface. One runner then writes versioned per-fold Parquet, exact Linear-anchor parity evidence, diagnostics, and manifests without modifying baseline files or Optuna studies.

**Tech Stack:** Python, Optuna public API, scikit-learn, XGBoost CPU, PyArrow, pytest.

**Spec:** User PROMPT 07 in this conversation.

## Global Constraints

- Read authoritative manifests and SQLite only; no Optuna optimize, enqueue, parameter edit, calibration, selection, 2023, or 2024 rows.
- Require protocol v1.1 SHA-256 `b987c0489c5d18b02500f34c786c01359f45e50b2b32bdea3de4332a161556e5`.
- Use four locked folds and existing Week-4 OOF schema with train-only preprocessing.
- New output identities are `arrival_{method}_tuned_rolling_run_v1_1`; all collision handling is fail-closed.

---

### Task 1: Authoritative tuned-parameter reader

**Files:**
- Create: `src/models/week5_tuned_oof.py`
- Create: `tests/test_week5_tuned_oof.py`

**Interfaces:**
- Produces: `load_tuned_method_inputs(root, protocol)` and `build_tuned_estimator_bundle_factory(inputs, protocol)`.

- [ ] Write failing tests for exact summary/result/SQLite agreement, rejection of mismatch, frozen no-tuning input, and strict task-specific estimator bundles.
- [ ] Run focused tests and observe missing-module failure.
- [ ] Implement a public-Optuna-API provenance reader plus HPO-context adapters for RF/HGB/XGB factories.
- [ ] Re-run focused tests and confirm pass.

### Task 2: Tuned OOF materializer

**Files:**
- Create: `scripts/materialize_week5_tuned_development_oof.py`
- Create: `tests/test_week5_tuned_oof_runner.py`

**Interfaces:**
- Produces: `build_preflight`, `run_tuned_method`, and `verify_tuned_oof_outputs`.

- [ ] Write failing tests for output collision, HPO linkage, exact key/target parity, finite prediction schema, and forbidden temporal input checks.
- [ ] Run focused tests and observe missing-runner failure.
- [ ] Implement the single ordered runner over RF, HGB, XGB using `run_fold_experiment`, Parquet sinks, Linear OOF anchor, and manifest diagnostics.
- [ ] Re-run focused tests and confirm pass.

### Task 3: Production materialization and verification

**Files:**
- Create only in production: twelve per-fold tuned OOF Parquet files, three preflights, and three rolling-run manifests.

- [ ] Validate all authoritative HPO sources, baseline immutability hashes, fresh output paths, and no active tuned runner.
- [ ] Run targeted compatibility tests.
- [ ] Run the materializer once, in RF → HGB → XGB order.
- [ ] Verify all twelve Parquet files against Linear target parity and each other; verify raw probability/signed-delay output and source hashes.
- [ ] Run fresh targeted tests, full suite, and compile/import checks.
