# Week-5 HGB Post-Study Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adopt the immutable completed HGB Classification study, repair schema-safe provenance materialization, then run only a fresh HGB Regression study.

**Architecture:** Replace the physical-SQL study reader with an Optuna-public-API reader that projects direction, states, best-trial data, timestamps, and user attributes. A recovery-only entrypoint validates immutable Classification evidence, writes the amendment and Classification result, verifies a fresh Regression namespace, and invokes only the Regression study path.

**Tech Stack:** Python 3.11, Optuna 5.0.0, SQLite, pytest, scikit-learn HGB, Windows execution reliability journals.

**Spec:** User-provided `PROMPT 05A — RECOVER HGB POST-STUDY ARTIFACT CRASH + CONTINUE REGRESSION`.

## Global Constraints

- Keep protocol `week5_hpo_protocol_v1_1` and hash `b987c0489c5d18b02500f34c786c01359f45e50b2b32bdea3de4332a161556e5` unchanged.
- Never optimize, resume, delete, write, or add trials to Classification.
- Preserve Classification SQLite, heartbeat, and guard journal byte-for-byte.
- Start Regression only after adopted Classification evidence and result manifest pass.
- Regression uses 10 trials, TPE seed 202601, NopPruner, `n_jobs=1`, timeout 14400, and `early_stopping=False`.
- Never access row-level 2023 or 2024 data.

---

### Task 1: Schema-safe completed-study reader

**Files:**
- Modify: `scripts/run_week5_hist_gradient_boosting_hpo_v1_1.py`
- Modify: `tests/test_week5_hist_gradient_boosting_hpo_runner_v1_1.py`

**Interfaces:**
- Consumes: `study_name` and SQLite storage path.
- Produces: direction, state counts, best trial/value/params, timestamps, and trial user attributes via `optuna.load_study`.

- [ ] Add temporary classification/maximize and regression/minimize Optuna SQLite tests with completed trials and user attributes.
- [ ] Run the tests and capture failure from the current `studies.direction` query.
- [ ] Replace `_sqlite_state_evidence` with a public-API evidence reader.
- [ ] Run the tests and verify both directions and state projections pass.

### Task 2: Adopt immutable Classification evidence

**Files:**
- Create: `scripts/recover_week5_hgb_hpo_v1_1.py`
- Create: `tests/test_week5_hgb_poststudy_recovery_v1_1.py`
- Create at runtime: `artifacts/manifests/week5_hgb_poststudy_recovery_amendment_v1.json`
- Create at runtime: `artifacts/manifests/week5_hpo_protocol_v1_1__hist_gradient_boosting_classification_result_v1.json`

**Interfaces:**
- Consumes: pre-recovery hashes and completed Classification evidence.
- Produces: immutable recovery amendment and Classification result manifest without calling optimize.

- [ ] Add tests for the real Classification evidence projection, objective recomputation, zero new trials, and pre/post hash equality.
- [ ] Add a recovery control-flow test proving Classification optimize is unreachable.
- [ ] Implement Classification adoption and immutable manifest materialization.
- [ ] Run recovery preflight and write the two versioned manifests.

### Task 3: Regression-only continuation

**Files:**
- Modify: `scripts/recover_week5_hgb_hpo_v1_1.py`
- Modify: `tests/test_week5_hgb_poststudy_recovery_v1_1.py`

**Interfaces:**
- Consumes: validated Classification result and absent Regression paths.
- Produces: one fresh Regression study with independent guard and heartbeat evidence.

- [ ] Add a test proving continuation invokes only `hist_gradient_boosting_regression`.
- [ ] Add collision tests for every Regression production path.
- [ ] Implement `--continue-regression` with adoption gate before `run_one_hgb_study` for Regression only.
- [ ] Run targeted tests and recovery preflight.
- [ ] Start exactly one Regression continuation process.

### Task 4: Final verification after Regression completion

**Files:**
- Create at runtime: Regression result manifest and authoritative HGB summary.

**Interfaces:**
- Consumes: completed Regression SQLite and explicit cleanup journal.
- Produces: Prompt 05A acceptance evidence and final status.

- [ ] Verify both SQLite studies, recompute both objectives, validate parameter spaces, protocol hash, TPE/NopPruner provenance, and explicit cleanup.
- [ ] Verify Classification evidence hashes equal the pre-recovery snapshot.
- [ ] Run targeted, full-suite, compile, and import checks.
- [ ] Return PASS or IN_PROGRESS using the required Prompt 05A form.
