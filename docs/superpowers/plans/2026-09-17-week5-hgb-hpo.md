# Week-5 HGB HPO v1.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run and prove two fresh, production HistGradientBoosting Week-5 HPO studies with complete execution provenance.

**Architecture:** A small HGB-only estimator factory feeds the existing generic fold objective. A parameterized HGB runner owns study creation, per-study Windows guard/heartbeat journals, immutable result manifests, and post-run SQLite verification while leaving RF history untouched.

**Tech Stack:** Python 3.11, scikit-learn HistGradientBoosting, Optuna SQLite, pytest, Windows `SetThreadExecutionState` and `QueryUnbiasedInterruptTime`.

**Spec:** `docs/superpowers/specs/2026-09-17-week5-hgb-hpo-design.md`

## Global Constraints

- Keep protocol `week5_hpo_protocol_v1_1` and hash `b987c0489c5d18b02500f34c786c01359f45e50b2b32bdea3de4332a161556e5` unchanged.
- Use exactly 10 COMPLETE trials per study, TPE seed 202601, NopPruner, Optuna parallelism 1, and 14,400 seconds per study.
- Access HPO row data only for 2016--2022, use the four locked folds, fit preprocessing on training rows only, and never use forbidden predictors.
- Preserve HGB `early_stopping=False`; do not alter search spaces, targets, objectives, or the 0.5 reporting-only threshold.
- Store explicit `GUARD_CLEANUP_SUCCESS` in each study's own journal and fail closed on every collision, suspend, or provenance mismatch.

---

### Task 1: Strict HGB HPO estimator factory

**Files:**
- Create: `src/models/week5_hist_gradient_boosting_hpo.py`
- Create: `tests/test_week5_hist_gradient_boosting_hpo.py`

**Interfaces:**
- Consumes: `HPOFoldContext` and frozen `Week5StudySpec` values.
- Produces: `build_week5_hist_gradient_boosting_estimator(context)` returning the correct scikit-learn classifier or regressor.

- [ ] **Step 1: Write the failing test**

```python
def test_hgb_factory_rejects_early_stopping_or_unfrozen_parameters() -> None:
    with pytest.raises(Week5ProtocolViolation):
        build_week5_hist_gradient_boosting_estimator(context_with_invalid_fixed_params)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_week5_hist_gradient_boosting_hpo.py -q`
Expected: FAIL because the factory module is absent.

- [ ] **Step 3: Write minimal implementation**

```python
def build_week5_hist_gradient_boosting_estimator(context: HPOFoldContext) -> object:
    # Validate method, exact seven frozen parameter names, seed, and
    # early_stopping=False; construct classifier with fold-only class weights.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_week5_hist_gradient_boosting_hpo.py -q`
Expected: PASS.

### Task 2: HGB production runner and immutable provenance

**Files:**
- Create: `scripts/run_week5_hist_gradient_boosting_hpo_v1_1.py`
- Create: `tests/test_week5_hist_gradient_boosting_hpo_runner_v1_1.py`

**Interfaces:**
- Consumes: protocol/specs, existing generic objective engine and execution guard.
- Produces: `preflight_v1_1`, fresh HGB studies, individual guard/heartbeat journals, result manifests, summary, and `verify_completed_hgb_run`.

- [ ] **Step 1: Write failing tests**

```python
def test_hgb_sequence_does_not_start_regression_after_bad_classification() -> None: ...
def test_result_manifest_requires_explicit_cleanup_success(tmp_path: Path) -> None: ...
def test_preflight_rejects_hgb_storage_or_journal_collision(tmp_path: Path) -> None: ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_week5_hist_gradient_boosting_hpo_runner_v1_1.py -q`
Expected: FAIL because the runner module is absent.

- [ ] **Step 3: Write minimal implementation**

```python
HGB_STUDY_IDS = ('hist_gradient_boosting_classification', 'hist_gradient_boosting_regression')
# Guard begins before fresh SQLite creation; one journal per study; callback
# stops on environment invalidation; materialize only after exactly 10 COMPLETE.
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_week5_hist_gradient_boosting_hpo_runner_v1_1.py -q`
Expected: PASS.

### Task 3: Pre-production and production evidence

**Files:**
- Create at runtime: HGB SQLite stores and `.execution.jsonl` / `.guard.jsonl` journals.
- Create at runtime: two result manifests and `week5_hist_gradient_boosting_hpo_v1_1_summary_v1.json`.

**Interfaces:**
- Consumes: passing code and no conflicting artifacts.
- Produces: 10 COMPLETE valid trials for Classification, then Regression, and verified immutable manifests.

- [ ] **Step 1: Run targeted tests and preflight**

Run: `uv run pytest tests/test_week5_hist_gradient_boosting_hpo*.py tests/test_week5_hpo_execution.py tests/test_week5_hpo_engine.py -q` then `uv run python scripts/run_week5_hist_gradient_boosting_hpo_v1_1.py --preflight`
Expected: all tests pass and preflight reports no collisions.

- [ ] **Step 2: Start one production runner**

Run: `uv run python scripts/run_week5_hist_gradient_boosting_hpo_v1_1.py --production`
Expected: Classification finishes validly before Regression; each gets one independent 14,400-second ceiling.

- [ ] **Step 3: Verify final evidence**

Run: targeted HGB tests, generic Week-5/RF provenance tests, complete pytest suite, and Python compile/import checks.
Expected: SQLite has exactly 10 COMPLETE and zero RUNNING trials per study; manifests prove recomputation and explicit cleanup success.
