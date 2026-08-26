# Canonical Schedule Datetime Representation Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scan every canonical development row for 2016–2023 with bounded PyArrow batches, establish the actual schedule date/time representations and rollover evidence, then make the required amendment decision without touching production normalization unless the evidence supports it.

**Architecture:** A new audit-only module projects exactly six approved canonical columns, enforces the existing development access guard before opening each yearly dataset, and accumulates vectorized representation/relation metrics one batch at a time. A small CLI writes a self-contained JSON manifest; the Markdown audit report and any conditional versioned amendment are derived only after all eight years complete.

**Tech Stack:** Python 3.10, PyArrow 25, standard-library counters/JSON, pytest

**Spec:** User task `AUDIT CANONICAL DATE/TIME REPRESENTATION BEFORE AMENDING RECONSTRUCTED FLIGHT CHAIN CONTRACT` dated 2026-08-26

## Global Constraints

- Inspect only development years 2016–2023 and call `assert_data_access_allowed(year, "development")` before opening each partition.
- Project only `FL_DATE`, `CRS_DEP_TIME`, `CRS_ARR_TIME`, `source_year`, `source_row_number`, and `flight_key`.
- Do not read raw Flight Chain `.pt`, modify `data/raw/**`, train a model, construct chains, or inspect 2024 development data.
- Do not modify `normalize_flight_date` or `scheduled_departure_timestamp` during the audit phase.
- Preserve raw Chain `FINAL — NO_GO`, `CORE_WEATHER_POLICY = "DROP"`, leakage rules, access guard, and `flight_key_v1`.
- Scan one year and one Arrow batch at a time; do not materialize or concatenate full years.
- `GO_FOR_ABLATION` is forbidden. Even a corrected smoke remains `CANDIDATE_REQUIRES_REVIEW`.
- Do not commit or push; use test/diff checkpoints.

---

### Task 1: Audit-only batch semantics and tests

**Files:**
- Create: `tests/test_canonical_schedule_datetime_audit.py`
- Create after RED: `src/data/canonical_schedule_datetime_audit.py`

**Interfaces:**
- Produces: `AUDIT_COLUMNS: tuple[str, ...]`
- Produces: `ScheduleDatetimeAuditAccumulator(year: int, example_limit: int = 3)`
- Produces: `consume(batch: pyarrow.RecordBatch) -> None`
- Produces: `finish(*, arrow_types: Mapping[str, str]) -> dict[str, object]`

- [ ] **Step 1: Write a failing controlled-batch test**

Create literal rows covering timestamp midnight/non-midnight `FL_DATE`, ISO date-only, missing and invalid values; timestamp-like and HHMM-like departure; same-day midnight, next-day midnight, previous-day, greater-than-one-day, and invalid relations; and scheduled-arrival same/next/other relations. Assert exact counts, min/max dates, hour/minute distributions, and traceable examples containing the stored `flight_key` unchanged.

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_canonical_schedule_datetime_audit.py -q
```

Expected: import/collection failure because the audit-only module does not exist.

- [ ] **Step 3: Implement exact audit-only categories**

Use PyArrow compute kernels with exact formats `%Y-%m-%d %H:%M:%S`, `%Y-%m-%dT%H:%M:%S`, and `%Y-%m-%d`; identify syntactically and semantically valid integral HHMM separately. Normalize timestamp values only inside the audit accumulator. Do not import or call production reconstruction normalization.

- [ ] **Step 4: Implement calendar relations and bounded examples**

Cast parsed timestamps to `date32`, count day differences `0`, `1`, `-1`, and absolute difference greater than one. Split same-day and next-day midnight from other clock values. Store no more than `example_limit` rows per category with only the six projected fields.

- [ ] **Step 5: Run focused tests and verify GREEN**

Require the synthetic metrics to pass twice with identical results.

---

### Task 2: Per-year dataset scanner and access isolation

**Files:**
- Modify: `tests/test_canonical_schedule_datetime_audit.py`
- Modify after RED: `src/data/canonical_schedule_datetime_audit.py`

**Interfaces:**
- Produces: `audit_canonical_year(project_root: Path, year: int, batch_size: int = 100_000) -> dict[str, object]`
- Produces: `audit_development_years(project_root: Path, years: Iterable[int], batch_size: int = 100_000) -> dict[str, object]`

- [ ] **Step 1: Write failing temporary-Parquet integration tests**

Build a synthetic `year=2016` partition containing the six audit columns plus an unrelated sentinel column. Assert exact projection metadata, Arrow storage types, row totals, source-year consistency counts, bounded batch count, and results equal the pure accumulator expectations.

- [ ] **Step 2: Write failing holdout and schema tests**

Assert 2024 raises the unchanged `DataAccessDenied` before dataset scanning. Missing any approved audit column must fail closed. A requested year outside 2016–2023 must fail.

- [ ] **Step 3: Run integration tests and verify RED**

Expected: scanner functions are absent.

- [ ] **Step 4: Implement bounded PyArrow scanning**

Call the existing access guard first, open only the requested yearly partition, project `AUDIT_COLUMNS`, set bounded batch/readahead values, feed batches to the accumulator, and verify scanner row count equals Parquet metadata row count.

- [ ] **Step 5: Implement aggregate manifest payload**

Run requested years sequentially, reject duplicates/2024, record dependencies and runtime, and emit a decision-evidence section without deciding amendment support in code.

- [ ] **Step 6: Run focused and holdout tests GREEN**

Run the new module plus `tests/test_holdout_guard.py`.

---

### Task 3: Audit CLI and baseline compatibility

**Files:**
- Modify: `tests/test_canonical_schedule_datetime_audit.py`
- Create after RED: `scripts/audit_canonical_schedule_datetime.py`
- Modify after creation: `scripts/smoke_test.py`

**Interfaces:**
- Produces CLI flags `--years`, `--batch-size`, and `--output`
- Default output: `artifacts/manifests/canonical_schedule_datetime_representation_audit_v1.json`

- [ ] **Step 1: Write failing CLI parsing tests**

Assert defaults are 2016–2023 and 100,000 rows, ranges parse deterministically, non-positive batch sizes fail, and 2024 is rejected before audit execution.

- [ ] **Step 2: Run CLI tests and verify RED**

Expected: audit CLI import failure.

- [ ] **Step 3: Implement minimal `.venv` CLI**

Reuse the existing project `.venv` guard and year parser behavior, call `audit_development_years`, and atomically write sorted/indented JSON outside `data/raw`.

- [ ] **Step 4: Update baseline smoke required paths after artifacts exist**

Require the audit module, CLI, report, and manifest without weakening existing config/raw/holdout checks.

- [ ] **Step 5: Run new tests, full pytest, and baseline smoke GREEN**

No canonical production rows are inspected in this task step.

---

### Task 4: Full development representation audit

**Files:**
- Generate: `artifacts/manifests/canonical_schedule_datetime_representation_audit_v1.json`

**Interfaces:**
- Consumes the audit CLI for years 2016–2023.
- Produces complete per-year metrics and bounded examples.

- [ ] **Step 1: Capture raw metadata inventory**

Compare current raw path/size/`mtime_ns` against existing baseline manifests without opening payloads.

- [ ] **Step 2: Execute the full bounded-memory scan**

Run:

```powershell
.\.venv\Scripts\python.exe scripts/audit_canonical_schedule_datetime.py --years 2016-2023 --batch-size 100000
```

The CLI must log an allowed development access decision before opening each year. Stop on any schema, row-count, or parse-accounting mismatch.

- [ ] **Step 3: Validate accounting identities**

For each field/year require category counts plus nulls to equal total rows; relation counts must equal timestamp-like rows having parseable `FL_DATE`; exact anomaly counts must remain unrounded.

- [ ] **Step 4: Search only existing repository evidence for 2400 provenance**

Review canonicalizer code, schema manifests, data dictionaries, and feasibility reports. Do not inspect `.pt` or introduce a raw-data read. Distinguish observed next-day midnight timestamps from proven original HHMM `2400` provenance.

- [ ] **Step 5: Revalidate raw inventory**

Require path/size/`mtime_ns` equality before proceeding to the decision.

---

### Task 5: Evidence report and conditional amendment decision

**Files:**
- Create: `docs/dataset_audit/canonical_schedule_datetime_representation_audit.md`
- Conditionally modify only for `AMENDMENT_SUPPORTED`: `docs/superpowers/specs/2026-08-26-reconstructed-schedule-flight-chain-design.md`

**Interfaces:**
- Produces exactly one decision: `AMENDMENT_SUPPORTED`, `AMENDMENT_REQUIRES_REVIEW`, or `AMENDMENT_REJECTED`.

- [ ] **Step 1: Evaluate the critical 2400 gate**

Choose `AMENDMENT_SUPPORTED` only if existing evidence proves a deterministic interpretation for every accepted timestamp relation, including the distinction between same-day `00:00` and next-day `00:00`. If provenance is absent, record `2400_SEMANTICS_NOT_PROVEN` and do not modify production normalization.

- [ ] **Step 2: Write the complete Markdown audit**

Include required year tables, exact counts, representation examples, date relations, hour/minute distributions, storage types, evidence boundary, and the chosen decision. State that `CRS_ARR_TIME` is scheduled only.

- [ ] **Step 3: Apply the conditional branch**

If decision is review/rejected, leave production parser/spec behavior untouched and skip Tasks 6–7. If supported, add a clearly versioned amendment section to the design spec and begin a new TDD cycle before touching production code.

---

### Task 6: Conditional production amendment via TDD

**Files:**
- Modify only if supported: `tests/test_flight_chain_reconstruction.py`
- Modify only after verified RED: `src/data/flight_chain_reconstruction.py`
- Modify only after verified GREEN: reconstruction design/report/manifest metadata

- [ ] **Step 1: Write failing literal conversion tests**

Cover ISO date, midnight timestamp date, rejected non-midnight date, same-day timestamp departure, proven next-day-midnight `2400`, same-day-midnight `0000`, unexpected relations, and exact stored `flight_key` reuse.

- [ ] **Step 2: Verify RED against unchanged production normalization**

The timestamp acceptance tests must fail for the intended missing behavior while all locked rejection tests remain meaningful.

- [ ] **Step 3: Implement the smallest versioned storage-representation expansion**

Keep semantic outputs unchanged: ISO service date, canonical HHMM string, deterministic schedule timestamp, original stored `flight_key` untouched. Fail closed outside evidence-supported relations.

- [ ] **Step 4: Verify focused and full suite GREEN**

Do not proceed to smoke if any regression remains.

---

### Task 7: Conditional corrected smoke and resource review

**Files:**
- Generate only if supported: two new non-production 2016 smoke roots
- Update: audit report and manifest with smoke evidence

- [ ] **Step 1: Run corrected bounded 2016 smoke A and B**

Use independent roots, `--max-rows 250000`, and `--chunk-size 100000`; never overwrite the prior invalidated smoke root.

- [ ] **Step 2: Compare logical results**

Require identical counts, exclusions, ambiguity metrics, duplicate signatures, and all logical fingerprints. Revalidate raw metadata after each run.

- [ ] **Step 3: Calculate resource estimates only from eligible rows**

Report bytes/time per eligible row, estimated full-2016 staging/output/runtime, current free disk, explicit safety margin, and the native-PyArrow caveat.

- [ ] **Step 4: Stop before full 2016**

No full-year or full-period reconstruction is authorized by this task.

---

### Task 8: Fresh verification and handoff

**Files:**
- Verify all changed and generated artifacts

- [ ] **Step 1: Run proof commands fresh**

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/smoke_test.py
git diff --check
git status --short
git diff --stat
```

- [ ] **Step 2: Verify locked contracts explicitly**

Check raw metadata, raw decision, weather DROP, unchanged leakage/access files, no `.pt` loader, no `data/raw/**` diff, and unchanged `flight_key_v1` formula.

- [ ] **Step 3: Return the required audit report format**

Use `NOT PROVEN` for unsupported claims and `NOT_RUN` for every skipped conditional task. Keep `SAFE_TO_RUN_FULL_2016_2023 = NO` unconditionally.
