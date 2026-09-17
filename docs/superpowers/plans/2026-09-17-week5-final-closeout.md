# Week 5 Final Closeout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verify every Prompt-08 Week-5 acceptance gate, publish an immutable authoritative closeout manifest and experiment report, and leave all Week-6 activities untouched.

**Architecture:** A read-only closeout auditor consumes the frozen protocol, six Optuna result manifests and databases, their method summaries, execution journals, and four-method OOF evidence. It fails closed on any disagreement, emits one deterministic evidence object, and writes the versioned manifest/report only after all checks pass. Production artifacts remain inputs; only the new closeout deliverables and factual experiment-log append are written.

**Tech Stack:** Python 3.11, Optuna public storage API, PyArrow, pytest, JSON, Markdown.

**Spec:** PROMPT 08 in the active conversation.

## Global Constraints

- Protocol is `week5_hpo_protocol_v1_1` with hash `b987c0489c5d18b02500f34c786c01359f45e50b2b32bdea3de4332a161556e5`.
- Do not run Optuna, retrain a model, open row-level 2023/2024, or start any Week-6 work.
- Preserve all Week-4/Week-5 statistical artifacts byte-for-byte.
- Accept RF cleanup through its versioned non-statistical amendment; require direct explicit cleanup success for HGB and XGB.
- Fail closed on study/result/summary/OOF disagreement or output collision.
- No commit or push is authorized by this prompt.

---

### Task 1: Closeout auditor contract

**Files:**
- Create: `scripts/materialize_week5_final_closeout.py`
- Create: `tests/test_week5_final_closeout.py`

**Interfaces:**
- Consumes: repository root `Path`, frozen result/summary/SQLite/OOF evidence.
- Produces: `build_week5_closeout(root: Path) -> dict[str, Any]`, `render_week5_report(summary: Mapping[str, Any]) -> str`, and a fail-closed CLI materializer.

- [ ] **Step 1: Write failing contract tests**

```python
def test_closeout_requires_exactly_six_complete_studies(closeout_fixture):
    evidence = closeout_fixture()
    evidence["studies"][0]["complete_trials"] = 9
    with pytest.raises(RuntimeError, match="10 COMPLETE"):
        validate_study_contract(evidence["studies"])

def test_closeout_requires_direct_hgb_xgb_cleanup(closeout_fixture):
    evidence = closeout_fixture()
    evidence["studies"][2]["cleanup"] = "INFERRED_ONLY"
    with pytest.raises(RuntimeError, match="GUARD_CLEANUP_SUCCESS"):
        validate_study_contract(evidence["studies"])

def test_closeout_rejects_week6_started(closeout_fixture):
    evidence = closeout_fixture()
    evidence["week6_boundary"]["weighted_ensemble_started"] = True
    with pytest.raises(RuntimeError, match="Week 6"):
        validate_week6_boundary(evidence["week6_boundary"])
```

- [ ] **Step 2: Run RED**

Run: `uv run python -m pytest tests/test_week5_final_closeout.py -q`

Expected: import failure because the closeout module does not exist.

- [ ] **Step 3: Implement the minimum fail-closed auditor**

Load studies through `optuna.load_study`, compare database state to result manifests, verify protocol/search-space/runtime fields, validate cleanup provenance, check exact OOF key/target parity through PyArrow, hash every referenced artifact, and return a JSON-serializable summary. Do not load source row data.

- [ ] **Step 4: Run GREEN**

Run: `uv run python -m pytest tests/test_week5_final_closeout.py -q`

Expected: all closeout contract tests pass.

### Task 2: Production closeout materialization

**Files:**
- Create: `artifacts/manifests/week5_core_arrival_xgboost_optuna_summary_v1.json`
- Create: `docs/experiments/week5_core_arrival_xgboost_optuna.md`
- Modify: `docs/experiments/experiment_log.md`

**Interfaces:**
- Consumes: `build_week5_closeout` validated evidence.
- Produces: immutable JSON summary, human-readable report, and append-only closure record.

- [ ] **Step 1: Snapshot immutable inputs**

Hash the protocol, six databases/results, three method summaries, RF amendments, HGB recovery amendment, tuned RF/HGB/XGB manifests and twelve Parquet files, and Week-4 Linear evidence.

- [ ] **Step 2: Run production materializer**

Run: `uv run python scripts/materialize_week5_final_closeout.py --materialize`

Expected: output reports `WEEK5_FINAL_STATUS=PASS`; it refuses to overwrite either deliverable.

- [ ] **Step 3: Append factual experiment-log closure**

Record v1.1 protocol, RF incident/amendments, six completed studies, tuned OOF completion, no 2023 selection, no 2024 rows, no Weather/Departure/Chain predictor, and Week-6 readiness without rewriting prior history.

- [ ] **Step 4: Compare immutable-input hashes**

Expected: every pre-existing statistical artifact remains byte-identical.

### Task 3: Fresh final verification

**Files:**
- Verify: all files created or modified by Tasks 1-2.

**Interfaces:**
- Consumes: completed Week-5 closeout evidence.
- Produces: final Prompt-08 status.

- [ ] **Step 1: Run targeted acceptance tests**

Run all Week-5 protocol, execution/provenance, result-materializer, tuned OOF, temporal/leakage, and closeout tests.

- [ ] **Step 2: Recompute exact OOF parity**

Read only `flight_key`, `y_arr_cls`, and `y_arr_reg` from all four method folds; require four fold identities and 1,254,518 pooled rows.

- [ ] **Step 3: Run full regression suite**

Run: `uv run python -m pytest -q --basetemp=.pytest_tmp_prompt08_full`

Expected: zero failures.

- [ ] **Step 4: Run compile/import verification**

Run: `uv run python -m compileall -q src scripts` followed by imports of the closeout and Week-5 contract modules.

- [ ] **Step 5: Perform final immutable hash comparison**

Expected: no pre-existing protocol, HPO, OOF, baseline, or provenance artifact changed.

- [ ] **Step 6: Return the Prompt-08 form**

Report PASS only when every command above exits zero and every acceptance field in the final manifest is true. Do not start Week 6.
