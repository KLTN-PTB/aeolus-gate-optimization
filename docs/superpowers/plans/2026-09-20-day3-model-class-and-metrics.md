# Day 3 Model Class and Metrics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reconcile Day 2 metrics, diagnose temporal degradation through 2022, and compare LightGBM and schedule-only interaction candidates under the locked rolling protocol.

**Architecture:** Treat the existing Day 2 runner and manifests as immutable evidence. Add independent diagnostic/reporting code and new versioned manifests for Day 3 experiments; preserve V1/V1.1/V1.2, Day 1, and Day 2 artifacts. Keep all model comparisons on the same seeds, 25K/year training sample, 25K validation sample, and allowed years 2016–2022.

**Tech Stack:** Python, pandas, scikit-learn preprocessing, XGBoost, LightGBM if installed, JSON manifests, pytest.

**Spec:** User-provided Day 3 metric reconciliation, fold diagnostics, LightGBM native categorical, interaction, and decision-registry requirements in the conversation on 2026-09-20.

## Global Constraints

- Do not open 2024.
- Do not use 2023 for tuning or row-level benchmark data.
- Do not modify V1/V1.1/V1.2 manifests, Day 1 reports, or Day 2 reports.
- Do not use actual-operation fields, weather, or flight-chain fields.
- Use only schedule-safe fields for V1.3 interactions.
- Every new report or manifest must be versioned and include input/runner hashes and access guards.
- Use seeds `[42, 43, 44, 45, 46]` and sample `25K/year` plus `25K` validation rows for fair model comparison.

## Review Focus

- Fold-4 reports must not be mislabeled as rolling-fold macro metrics; test the source fold metadata and summary aggregation separately.
- The listed per-fold values must be attributed to the correct config (`a2` versus `b2`); test exact config-specific arithmetic.
- Baseline medians must be fit on each fold's train side only; test the fold-local baseline source and sparse-cell counts.
- Temporal diagnostics must not read 2023/2024; test the allowed-year guard in the diagnostic runner.
- Native categorical and cross features must not leak target/outcome values; test feature columns and manifests against the forbidden-field policy.

### Task 1: Metric reconciliation blocker

**Files:**
- Create: `docs/notes/day3_metric_reconciliation.md`
- Test: `tests/test_day3_metric_reconciliation.py`
- Read-only evidence: `scripts/run_phase_a_benchmark_mae.py`, `artifacts/manifests/phase_a_benchmark_mae_b2.json`, `artifacts/manifests/phase_a_benchmark_mae_per_fold.json`

**Interfaces:**
- Consumes: existing Day 2 runner and JSON manifests.
- Produces: a documented canonical metric distinction and exact A2/B2 arithmetic.

- [ ] **Step 1: Write failing tests for fold scope and config attribution.** Assert B2's main report declares Fold 4, its summary skill is `-0.2519280802513224`, and the per-fold values map A2/B2 distinctly.
- [ ] **Step 2: Run the focused tests and confirm they fail if the expected reconciliation helpers are absent.**
- [ ] **Step 3: Add the note with code-line evidence, formulas, exact macro arithmetic, and the conclusion that the displayed `+0.47%` sequence is A2 rather than B2.
- [ ] **Step 4: Run the focused tests and verify the note and source manifests are consistent.

### Task 2: Fold 2022 and 2019→2022 diagnostics

**Files:**
- Create: `scripts/run_day3_fold_diagnostics.py`
- Create: `artifacts/manifests/day3_fold_diagnostics_v1.json`
- Modify: `docs/notes/day3_metric_reconciliation.md`
- Create: `tests/test_day3_fold_diagnostics.py`

**Interfaces:**
- Consumes: guarded 2016–2022 loader, V1.1 feature data, existing per-fold report.
- Produces: PSI by requested feature, carrier-hour sparse-cell stability, fold trend, severe MAE, and shrinkage tables.

- [ ] **Step 1: Write failing tests for PSI output keys, allowed years, fold trend order, and sparse-cell fields.
- [ ] **Step 2: Run focused tests and observe failure because the diagnostic runner does not exist.
- [ ] **Step 3: Implement fold-local diagnostics with train-fit carrier-hour baselines and versioned JSON output.
- [ ] **Step 4: Run focused tests and inspect the generated tables for all four folds.

### Task 3: LightGBM native-categorical benchmark

**Files:**
- Create: `scripts/run_phase_a_benchmark_lightgbm.py`
- Create: `artifacts/manifests/phase_a_benchmark_lightgbm_v1_1_fold4.json`
- Create: `artifacts/manifests/phase_a_benchmark_lightgbm_v1_1_per_fold.json`
- Create: `tests/test_day3_lightgbm_runner.py`

**Interfaces:**
- Consumes: V1.1 loader and feature manifest, frozen Week 5 reference metadata, fold diagnostics.
- Produces: fold-4 and rolling-fold LightGBM L1 reports with native categorical columns, seeds `[42..46]`, and fair sample sizes.

- [ ] **Step 1: Write failing tests for LightGBM availability handling, categorical feature declaration, parameters, and artifact guards.
- [ ] **Step 2: Run focused tests and observe the expected missing-runner failure.
- [ ] **Step 3: Implement the independent benchmark runner and native categorical matrix preparation.
- [ ] **Step 4: Run the tests, then execute fold 4 and four locked folds.
- [ ] **Step 5: Compare LightGBM against B2 on fold 4 and macro skill, without changing any Day 2 artifact.

### Task 4: Conditional V1.3 schedule-only interactions

**Files:**
- Modify: `src/features/refactored_features.py`
- Create: `artifacts/manifests/feature_manifest_arrival_v1_3.json`
- Create: `scripts/run_phase_a_benchmark_v1_3.py`
- Create: `artifacts/manifests/phase_a_benchmark_v1_3_xgboost.json`
- Create: `artifacts/manifests/phase_a_benchmark_v1_3_lightgbm.json`
- Create: `tests/test_day3_v1_3_interactions.py`

**Interfaces:**
- Consumes: V1.1 schedule features and the winning model class only when Task 3 permits the conditional run.
- Produces: three string cross features and versioned comparison manifests.

- [ ] **Step 1: Write failing tests for exact cross-feature values and forbidden-field exclusion.
- [ ] **Step 2: Run focused tests and confirm failure before implementation.
- [ ] **Step 3: Implement `carrier_month`, `route_dow`, and `arrhour_weekend` as schedule-only categorical crosses.
- [ ] **Step 4: Run tests and create the V1.3 manifest.
- [ ] **Step 5: Run XGBoost B2 and LightGBM only when the conditional gate is met, then record the 0.3pp decision.

### Task 5: Final synthesis and registry

**Files:**
- Create: `docs/notes/day3_model_class_and_interactions.md`
- Modify: `docs/decisions/decision_registry.md` only if the tightened supersede conditions are met.

**Interfaces:**
- Consumes: Day 1/Day 2 immutable manifests, Day 3 reconciliation, diagnostics, and model-class artifacts.
- Produces: a three-day comparison table, explicit point-regression conclusion, and a registry entry that separates technical supersession from temporal-stability warning.

- [ ] **Step 1: Write the final table with fold-4 and macro metrics for every available config.
- [ ] **Step 2: Apply the registry gate: macro positive, fold 2022 no worse than `-1pp`, and no strong 2021→2022 degradation.
- [ ] **Step 3: Add the registry entry only if the evidence meets the gate; otherwise document why the old gate remains operationally cautionary.
- [ ] **Step 4: Run the full relevant test suite and artifact compliance checks.

