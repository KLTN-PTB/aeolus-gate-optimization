# Week-5 XGBoost HPO v1.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run fresh, provenance-complete XGBoost Classification and Regression Optuna studies under the frozen Week-5 v1.1 protocol.

**Architecture:** Add a small XGBoost HPO estimator factory that consumes the existing generic fold objective context, then add a narrowly scoped production runner using the established HGB execution guard, heartbeat, public Optuna evidence reader, result materializer, and immutable summary conventions. The runner refuses existing XGB artifacts and runs Classification fully before Regression.

**Tech Stack:** Python, Optuna, XGBoost CPU, scikit-learn preprocessing, SQLite, pytest.

**Spec:** User PROMPT 06 in this conversation.

## Global Constraints

- Protocol is `week5_hpo_protocol_v1_1`, SHA-256 `b987c0489c5d18b02500f34c786c01359f45e50b2b32bdea3de4332a161556e5`.
- Use exactly 10 complete trials, 14,400 seconds per study, TPESampler seed 202601, NopPruner, and Optuna/XGBoost `n_jobs=1`.
- Use CPU `tree_method=hist`; no GPU and no validation-driven early stopping.
- HPO accesses only 2016--2022 and preserves baseline/Week-4 evidence.
- Never overwrite, resume, delete, or rename around a colliding production study.

---

### Task 1: Frozen XGBoost HPO estimator factory

**Files:**
- Create: `src/models/week5_xgboost_hpo.py`
- Create: `tests/test_week5_xgboost_hpo.py`

**Interfaces:**
- Produces: `build_week5_xgboost_hpo_estimator(context: HPOFoldContext) -> XGBClassifier | XGBRegressor`

- [ ] **Step 1: Write failing tests** for exact frozen parameters, CPU-only tree method, train-fold derived `scale_pos_weight`, signed regression, and rejection of parameter/fixed-parameter drift.
- [ ] **Step 2: Run the focused test** and confirm import failure before implementation.
- [ ] **Step 3: Implement the minimal strict factory** that uses only validated context parameters and existing generic HPO preprocessing.
- [ ] **Step 4: Re-run focused tests** and confirm they pass.

### Task 2: Fresh-only XGBoost HPO runner and materializer

**Files:**
- Create: `scripts/run_week5_xgboost_hpo_v1_1.py`
- Create: `tests/test_week5_xgboost_hpo_runner_v1_1.py`

**Interfaces:**
- Produces: `preflight_v1_1`, `run_xgboost_sequence`, `run_and_materialize_xgboost_sequence`, and `main()`.

- [ ] **Step 1: Write failing tests** for order enforcement, artifact collisions, public-API SQLite study reading, and explicit cleanup evidence.
- [ ] **Step 2: Run the focused test** and confirm it fails because the runner is absent.
- [ ] **Step 3: Implement the runner** by adapting the proven HGB execution/provenance flow with only the XGB study IDs, factory, artifact paths, and XGB dependency provenance changed.
- [ ] **Step 4: Re-run focused tests** and confirm they pass.

### Task 3: Pre-production verification and production

**Files:**
- Create at production only: two XGB SQLite studies, journals, result manifests, and authoritative XGB summary.

- [ ] **Step 1: Verify RF/HGB authoritative PASS, protocol hash, no active XGB runner, and no XGB artifact collision.**
- [ ] **Step 2: Run targeted tests, generic HPO tests, execution-cleanup tests, and baseline XGBoost compatibility tests.**
- [ ] **Step 3: Launch the single runner in the background; it must materialize Classification before creating Regression.**
- [ ] **Step 4: After it exits, directly verify study states/directions/objective recomputation, frozen parameter bounds, explicit cleanup events, and temporal evidence.**
- [ ] **Step 5: Run fresh targeted, full-suite, and compile/import checks.**
