# Reconstructed Chain Datetime Storage Amendment Implementation Plan

> **For Codex:** Execute this plan incrementally with `superpowers:test-driven-development`; verify every claim with fresh commands before reporting completion.

**Goal:** Implement the design-owner-approved, versioned canonical datetime storage amendment while preserving schedule semantics, existing `flight_key_v1`, raw-data immutability, Weather `DROP`, and the sealed 2024 holdout. Stop after two deterministic bounded 2016 smokes and their resource review.

**Architecture:** Keep `schedule_chain_v1` and the existing SQLite-per-year reconstruction architecture. Extend only the accepted storage representations at the normalization boundary: midnight-only timestamp-like `FL_DATE`, same-service-date non-midnight timestamp-like `CRS_DEP_TIME`, and explicit fail-closed reasons for ambiguous midnight or unexpected date displacement. Treat these contract violations as fatal for the year so no production artifact is published.

**Tech stack:** Python 3.11+, pandas 2.3.3, PyArrow 25.0.1, SQLite from the Python standard library, pytest 9.1.1, PowerShell.

---

## Task 1: Preserve the decision and amend the approved design

**Files:**

- Modify: `docs/superpowers/specs/2026-08-26-reconstructed-schedule-flight-chain-design.md`
- Create: `docs/superpowers/plans/2026-08-26-reconstructed-chain-datetime-storage-amendment.md`

1. Append a dated, clearly versioned amendment; do not rewrite the original design history.
2. Preserve the accepted full-audit facts and the earlier `AMENDMENT_REQUIRES_REVIEW` decision.
3. Record the superseding design-owner decision `AMENDMENT_SUPPORTED_WITH_AMBIGUOUS_MIDNIGHT_FAIL_CLOSED`.
4. State that schedule-chain semantics and identifier versions do not change; only accepted canonical storage representations expand.
5. Document exact accepted and rejected `FL_DATE`/`CRS_DEP_TIME` cases, fatal year behavior, unchanged `CRS_ARR_TIME`, and unchanged `flight_key_v1`.

## Task 2: RED tests for the normalization boundary

**Files:**

- Modify: `tests/test_flight_chain_reconstruction.py`
- Test: `tests/test_flight_chain_reconstruction.py`

1. Add tests for ISO `FL_DATE`, midnight timestamp normalization, and non-midnight rejection.
2. Add tests for same-date canonical departure timestamps at `09:00` and `00:05`.
3. Assert the exact `AMBIGUOUS_CANONICAL_MIDNIGHT` reason for a same-date midnight timestamp.
4. Assert exact rejection of previous-date, next-date midnight, and next-date non-midnight timestamps.
5. Retain and rerun the existing explicit `2400` rollover test.
6. Run the focused tests and record the expected failures before production changes.

## Task 3: RED integration tests for fatal contracts and identifier reuse

**Files:**

- Modify: `tests/test_flight_chain_reconstruction.py`
- Test: `tests/test_flight_chain_reconstruction.py`

1. Add a reconstruction fixture using canonical timestamp storage and assert the stored `flight_key_v1` is emitted unchanged.
2. Add a mixed-validity year fixture proving ambiguous canonical midnight aborts the year, retains staging, and publishes no output.
3. Add a fixture proving an unexpected timestamp date relation aborts the year.
4. Update the former timestamp-rejection fixture so it tests the newly approved fail-closed boundary rather than the superseded storage expectation.
5. Run the focused integration tests and record the expected failures.

## Task 4: Implement the minimal amendment

**Files:**

- Modify: `src/data/flight_chain_reconstruction.py`
- Modify: `scripts/reconstruct_flight_chain.py`
- Test: `tests/test_flight_chain_reconstruction.py`

1. Add a versioned storage amendment constant without changing `CHAIN_ID_VERSION` or `FLIGHT_KEY_VERSION`.
2. Extend `normalize_flight_date()` only for exact timestamp-like canonical values whose time is midnight; reject non-midnight timestamps explicitly.
3. Extend `scheduled_departure_timestamp()` to accept exact timestamp-like values only on the normalized service date and only when not exactly midnight.
4. Preserve the explicit numeric/integral HHMM path, including explicit `2400` rollover.
5. Make ambiguous midnight and unexpected date relationships fatal representation-contract violations during per-year ingestion.
6. Include the amendment version and accepted-storage contract in run results/manifests.
7. Keep `CRS_ARR_TIME` unchanged and schedule-only.
8. Run focused tests, then the full suite under the current environment to isolate code correctness from environment migration.

## Task 5: Migrate `.venv` safely to Python 3.11

**Files:**

- Modify: `.gitignore`
- Modify: `requirements.txt`
- Modify: `README.md`
- Create: `artifacts/manifests/reconstruction_python_environment_v1.json`

1. Preserve the current exact dependency pins and verify the installed Python 3.11 executable.
2. Create `.venv311_candidate` without removing the existing `.venv`.
3. Install exactly `requirements.txt` into the candidate and capture resolved versions.
4. Run the complete test suite with the candidate interpreter.
5. Only after candidate success, resolve and validate the intended workspace paths, move the old `.venv` to an ignored backup, and promote the candidate to `.venv` using PowerShell `Move-Item -LiteralPath`.
6. Do not delete the backup in this task.
7. Record Python, pandas, PyArrow, pytest, NumPy, PyYAML, and SQLite versions in dependency documentation and a machine-readable environment manifest.
8. Verify `\.venv\Scripts\python.exe` is Python 3.11 or newer.

## Task 6: Green verification before real-data smoke

**Files:**

- Test: all tests
- Test: `scripts/smoke_test.py`

1. Run `\.venv\Scripts\python.exe -m pytest -q`.
2. Run `\.venv\Scripts\python.exe scripts/smoke_test.py`.
3. Recheck Weather `DROP`, 2024 development denial, raw decision `FINAL — NO_GO`, and absence of `torch.load` in new implementation paths.
4. Stop if any gate fails.

## Task 7: Corrected bounded 2016 smoke A

**Files/data:**

- Create only: `data/processed/flight_chain_reconstructed_v1_smoke_b/`
- Preserve: `data/processed/flight_chain_reconstructed_v1_smoke_a/`

1. Confirm the new output root does not exist and snapshot all raw path/size/mtime values.
2. Run year 2016 with `--max-rows 250000 --chunk-size 100000`.
3. Confirm actual eligible rows entered SQLite, the year passed, staging was removed after PASS, and no raw inventory entry changed.
4. Capture counts, fingerprints, runtime, staging/SQLite/output bytes, Python allocation, and disk free values.

## Task 8: Corrected bounded 2016 smoke B and determinism gate

**Files/data:**

- Create only: `data/processed/flight_chain_reconstructed_v1_smoke_c/`

1. Repeat the identical bounded 2016 command into the independent root.
2. Compare source/eligible/mapped/chain/inbound/exclusion/ambiguity/duplicate-signature counts.
3. Compare all table and combined logical fingerprints.
4. Verify chain IDs and chain positions through the member-content fingerprints and a direct selected-column logical comparison.
5. Fail closed if any comparison differs; do not continue to resource approval.

## Task 9: Resource and safety audit

**Files:**

- Create: `artifacts/manifests/flight_chain_datetime_amendment_smoke_v1.json`
- Create: `docs/dataset_audit/flight_chain_datetime_amendment_smoke_report.md`

1. Calculate rows/sec, staging bytes/eligible row, and output bytes/eligible row from successfully reconstructed eligible rows only.
2. Extrapolate staging, output, and runtime to the known 2016 partition row count; label the estimate and do not run it.
3. Report free disk before/after and a conservative safety margin, including that `tracemalloc` omits some native PyArrow allocations.
4. Revalidate all 36 raw paths, raw Git status, no `.pt` load, Weather `DROP`, sealed 2024, unchanged `flight_key_v1`, and unchanged raw-chain decision.
5. Keep reconstructed status at `CANDIDATE_REQUIRES_REVIEW`; do not create the final full-data decision document.

## Task 10: Final verification and handoff

**Files:**

- Verify all files touched above

1. Run the full test suite one final time with `.venv`.
2. Run focused safety checks and validate both smoke manifests/reports against actual output roots.
3. Run `git status --short` and `git diff --stat`; explicitly confirm no changed path under `data/raw/**`.
4. Return the required amendment report and stop. Do not run full 2016 or 2016–2023.
