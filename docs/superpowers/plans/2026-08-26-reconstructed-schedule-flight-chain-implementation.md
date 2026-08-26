# Reconstructed Schedule Flight Chain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and validate a deterministic, schedule-only Reconstructed Flight Chain from canonical Tabular, then stop after a bounded 2016 smoke and resource review.

**Architecture:** Pure normalization/ID/reconstruction functions establish the tested logical contract. A production orchestrator projects safe canonical columns with PyArrow, stages one year in SQLite with only a primary key and one ordering index, streams deterministic Parquet outputs, validates them, and deletes staging only after the year passes.

**Tech Stack:** Python standard library, SQLite, pandas, PyArrow/Parquet, PyYAML, pytest

**Spec:** `docs/superpowers/specs/2026-08-26-reconstructed-schedule-flight-chain-design.md`

## Global Constraints

- Original raw `.pt` Flight Chain remains `FINAL — NO_GO` and is never loaded or reverse engineered.
- `data/raw/tabular/` and `data/raw/chain/` are read-only; no write target may resolve under either root.
- Reuse `flight_key_v1`; it remains identifier-only and never enters ML predictors.
- `CORE_WEATHER_POLICY = "DROP"`; leakage/weather/`FLIGHTS`/target/actual fields never enter derived output.
- Development access is 2016–2023 only; 2024 remains sealed by the unchanged access guard.
- Production CLI must run through the repository `.venv`.
- SQLite is per-year intermediate staging outside raw, with exactly a primary-key index and one composite ordering index, and is deleted only after year validation passes.
- `GO_FOR_ABLATION` is forbidden until full 2016–2023 reconstruction and every critical gate pass.
- No model training, feature transformer, HPO, simulation, or optimization is in scope.
- Do not commit or push; use diff/test checkpoints instead.
- Stop after bounded 2016 smoke and resource audit for user review; do not start the full 2016–2023 run.

---

### Task 1: Dependency and runtime contract

**Files:**
- Create: `requirements.txt`
- Test: `tests/test_flight_chain_reconstruction.py`
- Later modify: `src/data/flight_chain_reconstruction.py`

**Interfaces:**
- Produces: `assert_project_venv(project_root: Path) -> None`
- Produces: `dependency_versions() -> dict[str, str]`

- [ ] **Step 1: Install approved dependencies into `.venv`**

Run:

```powershell
.\.venv\Scripts\python.exe -m pip install pandas pyarrow
```

Record the resolved versions together with existing PyYAML and pytest versions in `requirements.txt` using exact `==` pins.

- [ ] **Step 2: Write failing runtime/dependency tests**

```python
def test_project_venv_guard_rejects_non_project_prefix(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "prefix", str(tmp_path / "different-env"))
    with pytest.raises(RuntimeError, match="repository .venv"):
        assert_project_venv(ROOT)

def test_dependency_versions_are_self_contained():
    observed = dependency_versions()
    assert {"python", "pandas", "pyarrow", "sqlite"} <= observed.keys()
    assert all(observed.values())
```

- [ ] **Step 3: Run tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_flight_chain_reconstruction.py -q
```

Expected: collection/import failure because the reconstruction module does not exist.

- [ ] **Step 4: Defer production implementation until Task 2 establishes the module**

Keep the failing tests in place. Do not create a runtime-only module fragment that bypasses the core TDD sequence.

---

### Task 2: Pure normalization and deterministic identifiers

**Files:**
- Create: `src/data/flight_chain_reconstruction.py`
- Modify: `tests/test_flight_chain_reconstruction.py`

**Interfaces:**
- Produces: `CHAIN_ID_VERSION`, `CHAIN_GROUP_COMPONENTS`, `SCHEDULE_SIGNATURE_VERSION`, `PHYSICAL_AIRCRAFT_IDENTITY`
- Produces: `normalize_flight_date(value: object) -> str`
- Produces: `normalize_carrier(value: object) -> str`
- Produces: `normalize_flight_number(value: object) -> str`
- Produces: `scheduled_departure_timestamp(flight_date: object, crs_dep_time: object) -> tuple[str, datetime]`
- Produces: `make_chain_id(record: Mapping[str, object]) -> str`
- Produces: `make_schedule_signature(record: Mapping[str, object]) -> str`

- [ ] **Step 1: Add failing ID and normalization tests**

Tests cover:

```python
assert make_chain_id(base) == make_chain_id(dict(base))
assert make_chain_id(base) != make_chain_id({**base, "OP_CARRIER": "DL"})
assert make_chain_id(base) != make_chain_id({**base, "FL_DATE": "2016-01-02"})
assert make_chain_id(base) != make_chain_id({**base, "OP_CARRIER_FL_NUM": 124})
assert normalize_flight_number(123.0) == "123"
assert normalize_flight_number(" 123.0 ") == "123"
with pytest.raises(ValueError, match="non-integral"):
    normalize_flight_number("123.5")
```

Also assert the explicit semantic constant:

```python
assert PHYSICAL_AIRCRAFT_IDENTITY is False
```

- [ ] **Step 2: Add failing scheduled-time tests**

```python
@pytest.mark.parametrize(
    ("raw", "hhmm", "expected"),
    [
        (5, "0005", datetime(2016, 1, 1, 0, 5)),
        (45, "0045", datetime(2016, 1, 1, 0, 45)),
        (800, "0800", datetime(2016, 1, 1, 8, 0)),
        (1530, "1530", datetime(2016, 1, 1, 15, 30)),
        (2400, "2400", datetime(2016, 1, 2, 0, 0)),
    ],
)
def test_scheduled_departure_hhmm_and_rollover(raw, hhmm, expected):
    assert scheduled_departure_timestamp("2016-01-01", raw) == (hhmm, expected)
```

Invalid minutes, `2401`, negative, fractional, missing, and non-finite values must raise `ValueError`.

- [ ] **Step 3: Run focused tests and verify RED**

Run the new normalization/ID tests and confirm failure is caused by missing functions.

- [ ] **Step 4: Implement minimal pure contracts**

Use strict `Decimal` parsing for flight numbers/times, `date.fromisoformat`, BLAKE2b-128, `\x1f` payload separators, and explicit prefixes. Import `FLIGHT_KEY_VERSION` only for validation; do not duplicate or change its formula.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run all Task-2 cases with `.venv` and require zero failures.

- [ ] **Step 6: Add runtime/dependency functions and turn Task-1 tests GREEN**

`assert_project_venv` compares resolved `sys.prefix` with `<root>/.venv`. `dependency_versions` imports package versions and reports `sqlite3.sqlite_version` and `platform.python_version()`.

- [ ] **Step 7: Run the whole new test module**

Expected: normalization, ID, rollover, semantics, runtime, and dependency tests pass.

---

### Task 3: Synthetic reconstruction, ordering, mapping, leakage, and fingerprints

**Files:**
- Modify: `src/data/flight_chain_reconstruction.py`
- Modify: `tests/test_flight_chain_reconstruction.py`

**Interfaces:**
- Produces: `ReconstructionResult` dataclass with `chain_groups`, `chain_members`, `inbound_target_map`, `metrics`, and `fingerprints`
- Produces: `reconstruct_records(records: Iterable[Mapping[str, object]], *, expected_year: int) -> ReconstructionResult`
- Produces: `assert_derived_schema_safe(table_columns: Mapping[str, Iterable[str]]) -> None`

- [ ] **Step 1: Write failing grouping and ordering tests**

Synthetic rows demonstrate:

- same carrier + number + date share one chain;
- different date/carrier/number produce different chains;
- `0800` precedes `1200`;
- ties are ordered by normalized `ORIGIN`, `DEST`, `flight_key` independent of input order;
- tied members are ambiguous and parent group has `has_order_tie`;
- `chain_position` is zero-based and stable.

- [ ] **Step 2: Write failing mapping and duplicate tests**

Assert:

```python
assert len({row["flight_key"] for row in result.chain_members}) == len(result.chain_members)
assert {row["target_flight_key"] for row in result.inbound_target_map} == {"inbound-key"}
assert all(row["chain_length"] == 3 for row in result.inbound_target_map)
```

A repeated `flight_key` must raise rather than pick a chain. Two rows with the same natural signature but distinct `flight_key` values remain present and increment duplicate-signature metrics.

- [ ] **Step 3: Write failing exclusion and fingerprint tests**

Missing group/time fields are excluded with exact reason counters. Two shuffled executions over the same logical records must yield identical IDs, positions, table fingerprints, and combined fingerprint.

- [ ] **Step 4: Write failing leakage test**

Build the union of output columns and assert it is disjoint from:

```python
LEAKAGE_COLUMNS | TARGET_COLUMNS | WEATHER_COLUMNS | UNCERTAIN_COLUMNS | {"FLIGHTS"}
```

Passing a forbidden field in a declared output schema must raise a fail-closed validation error.

- [ ] **Step 5: Run focused tests and verify RED**

Confirm failures arise because reconstruction/result/validation functions are absent.

- [ ] **Step 6: Implement minimal in-memory logical reconstruction**

Normalize eligible rows, fail on canonical traceability corruption, sort by the documented contract, group one chain at a time, mark ties, generate inbound mapping, compute exclusion/ambiguity/length/duplicate metrics, and hash canonical logical rows.

- [ ] **Step 7: Run focused tests and verify GREEN**

Require all synthetic behavior to pass, then refactor shared chain emission into a helper reusable by SQLite streaming.

---

### Task 4: Raw/output guards and 2024 isolation

**Files:**
- Modify: `src/data/flight_chain_reconstruction.py`
- Modify: `tests/test_flight_chain_reconstruction.py`

**Interfaces:**
- Produces: `assert_output_path_safe(path: Path, *, project_root: Path) -> Path`
- Produces: `snapshot_raw_inventory(project_root: Path) -> dict[str, dict[str, int | str]]`
- Produces: `assert_raw_inventory_unchanged(before, after) -> None`
- Production orchestrator consumes unchanged `assert_data_access_allowed(year, "development")`

- [ ] **Step 1: Write failing raw-path tests**

Reject raw root, raw child, `..`-normalized raw child, and a symlink/junction resolving into raw. Accept a temporary processed path.

- [ ] **Step 2: Write failing inventory tests**

Create fixture raw files under a temporary project and assert snapshots use relative path, size, and `mtime_ns`; mutation causes `assert_raw_inventory_unchanged` to fail.

- [ ] **Step 3: Write failing holdout test**

Call the production access helper/orchestrator for 2024 and expect `DataAccessDenied` with the existing sealed-development message. Also reassert the existing `access_guard.py` source is not modified by this task.

- [ ] **Step 4: Run tests and verify RED**

Confirm guard functions are missing.

- [ ] **Step 5: Implement resolved-path guards and metadata snapshots**

Use `Path.resolve()` plus `is_relative_to`, recursive file metadata only, and no content reads. Preserve `mtime_ns` exactly.

- [ ] **Step 6: Run tests and verify GREEN**

Run new tests plus `tests/test_holdout_guard.py`.

---

### Task 5: Per-year PyArrow + SQLite production engine

**Files:**
- Modify: `src/data/flight_chain_reconstruction.py`
- Modify: `tests/test_flight_chain_reconstruction.py`

**Interfaces:**
- Produces: `FlightChainReconstructor(project_root: Path, output_root: Path, chunk_size: int, max_rows: int | None, dry_run: bool)`
- Produces: `FlightChainReconstructor.reconstruct_year(year: int) -> dict[str, object]`
- Produces: `FlightChainReconstructor.reconstruct_years(years: Sequence[int]) -> dict[str, object]`

- [ ] **Step 1: Write a failing temporary-Parquet integration test**

Create a canonical fixture partition with PyArrow, run `reconstruct_year(2016)`, and assert:

- all three output paths and schemas;
- Parquet metadata row counts;
- SQLite staging removed after pass;
- manifest metrics equal synthetic expectations;
- only safe source columns were projected;
- output rerun refuses overwrite.

- [ ] **Step 2: Write failing SQLite contract/resource tests**

During a test hook before cleanup, query `PRAGMA index_list(staged_rows)` and assert only the primary-key index plus `idx_staged_order` exist. Assert year metrics contain positive `peak_staging_bytes`, runtime, input/output bytes, and `peak_python_allocation_bytes`.

- [ ] **Step 3: Write failing failed-year staging test**

Inject a duplicate `flight_key`, expect failure, assert no production year output is published, and assert the reported staging directory remains outside raw for diagnosis.

- [ ] **Step 4: Run integration tests and verify RED**

Expected: engine class absent.

- [ ] **Step 5: Implement batch ingestion**

Validate canonical input schema, call the 2016–2023 development guard, use `pyarrow.dataset` batches with only approved columns, normalize rows, insert into a `WITHOUT ROWID` table keyed by `flight_key`, and maintain one composite order index.

- [ ] **Step 6: Implement streamed output**

Read the single deterministic order, buffer at most `chunk_size` logical rows, write exact explicit Arrow schemas with Zstandard compression, calculate fingerprints during emission, validate counts/schema/forbidden fields, and atomically publish the year directories.

- [ ] **Step 7: Implement staging lifecycle and resource metrics**

Track database/staging bytes after committed batches, `tracemalloc` peak, monotonic runtime, row throughput, source/output bytes, and free-disk context. Delete staging only after all year gates pass; preserve/report it on failure.

- [ ] **Step 8: Run integration tests and verify GREEN**

Run the full new test module twice. Logical fingerprints and positions must match between independent temporary roots.

---

### Task 6: CLI, config, dependency validation, and baseline smoke compatibility

**Files:**
- Create: `scripts/reconstruct_flight_chain.py`
- Modify: `configs/base.yaml`
- Modify: `tests/test_base_config.py`
- Modify: `tests/test_flight_chain_reconstruction.py`
- Modify: `scripts/smoke_test.py`
- Modify: `README.md`
- Modify: `project_structure.md`

**Interfaces:**
- Produces: `parse_years(value: str) -> list[int]`
- CLI flags: `--years`, `--output-root`, `--dry-run`, `--chunk-size`, `--max-rows`

- [ ] **Step 1: Write failing CLI/config tests**

Assert range/list parsing, invalid years, non-positive chunk/max rows, default 2016–2023 behavior, output-under-raw rejection, and 2024 development rejection.

Update the config test to require the original raw state unchanged while checking the separate reconstructed block:

```python
raw = {key: config["flight_chain"][key] for key in (
    "enabled_by_default", "status", "include_in_core", "week6_ablation"
)}
assert raw == {
    "enabled_by_default": False,
    "status": "no_go",
    "include_in_core": False,
    "week6_ablation": False,
}
assert config["flight_chain"]["reconstructed"]["physical_aircraft_identity"] is False
```

- [ ] **Step 2: Run CLI/config tests and verify RED**

Confirm failures come from absent CLI/config contract.

- [ ] **Step 3: Implement CLI and config**

The CLI inserts project root on `sys.path`, enforces `.venv`, resolves config-relative paths, prints a JSON-compatible summary, and returns nonzero on gate failure. Config retains raw `status: no_go` and adds `reconstructed.version/status/source/group_fields/order/tie/max_context_length/physical_aircraft_identity`.

- [ ] **Step 4: Update baseline smoke validation**

Replace exact equality of the whole `flight_chain` mapping with exact validation of the four raw keys plus the separate reconstructed contract. Add required module/script/report paths only when those artifacts are actually created.

- [ ] **Step 5: Document commands and semantic boundary**

README/project structure identify the derived artifact, `.venv` commands, full-source vs inbound-target universes, raw `NO_GO`, and no physical-aircraft interpretation.

- [ ] **Step 6: Run tests and verify GREEN**

Run new tests, `tests/test_base_config.py`, holdout/leakage tests, and `scripts/smoke_test.py` through `.venv`.

---

### Task 7: Synthetic suite and bounded 2016 smoke

**Files:**
- Generated only: a non-production smoke output root outside raw
- Create after evidence: `docs/dataset_audit/flight_chain_reconstruction_report.md`
- Create after evidence: `artifacts/manifests/flight_chain_reconstructed_smoke_manifest_v1.json`

**Interfaces:**
- Consumes the CLI and engine from Tasks 5–6.
- Produces an explicitly incomplete smoke manifest and report; does not produce the final full-data manifest or decision.

- [ ] **Step 1: Run the full synthetic/regression suite**

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/smoke_test.py
```

Stop if either command fails.

- [ ] **Step 2: Capture pre-smoke raw inventory**

Use `snapshot_raw_inventory` and compare it with the existing processed/chain audit manifests. Do not hash or open `.pt` payloads.

- [ ] **Step 3: Run bounded 2016 smoke twice**

Use a non-production smoke root and a conservative initial `--max-rows` value such as 250,000 with the approved chunk size. Run a second independent output root with identical arguments. Do not access 2024.

- [ ] **Step 4: Validate smoke determinism and semantics**

Compare logical fingerprints, IDs, positions, counts, schemas, exclusion reasons, flight-number audit findings, raw snapshots, and holdout behavior. If `OP_CARRIER_FL_NUM` contains non-integral or contradictory values, stop and report without changing normalization.

- [ ] **Step 5: Audit resource margins**

Record runtime, rows/second, peak staging bytes, staging bytes/eligible row, peak Python allocation, Arrow caveat, output bytes, disk free before/after, and a conservative extrapolation to the full 2016 row count. Treat extrapolation as planning evidence, not a measured full-year result.

- [ ] **Step 6: Apply the safety decision**

Mark bounded smoke `PASS` only if all partial-data gates pass and projected disk usage leaves a documented safety margin. If disk/RAM/runtime is unsuitable, stop without changing architecture.

- [ ] **Step 7: Write smoke manifest and audit report**

The report clearly labels implementation, synthetic, and smoke status; lists exact `NOT RUN` full-year/full-period items; preserves raw `FINAL — NO_GO`; and sets reconstructed status no higher than `CANDIDATE_REQUIRES_REVIEW`.

---

### Task 8: Fresh verification and handoff before full execution

**Files:**
- Verify all changed files
- Do not create: `docs/decisions/decision_reconstructed_chain.md`
- Do not create: `artifacts/manifests/flight_chain_reconstructed_manifest_v1.json`

**Interfaces:**
- Produces the user-facing implementation/smoke report and a full-run recommendation.

- [ ] **Step 1: Re-run all proof commands fresh**

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/smoke_test.py
git diff --check
git status --short
git diff --stat
```

- [ ] **Step 2: Verify immutable contracts explicitly**

Confirm raw metadata unchanged, `decision_include_chain.md` still contains `FINAL — NO_GO`, `CORE_WEATHER_POLICY == "DROP"`, access guard still blocks 2024 development, no `torch.load` exists in the new implementation, and no changed path is under `data/raw/**`.

- [ ] **Step 3: Review requirements against spec**

Check each design section and acceptance gate. Report every unrun full-data gate as `NOT RUN`, not pass.

- [ ] **Step 4: Return the required Vietnamese report format**

Set:

- `IMPLEMENTATION_SUCCESS` from fresh tests;
- `SMOKE_DATA_SUCCESS` from bounded smoke evidence;
- `FULL_2016_2023_RECONSTRUCTION_SUCCESS = NO / NOT RUN`;
- `SAFE_TO_PROCEED_TO_CHAIN_FEATURE_ENGINEERING = NO` before full validation;
- `SAFE_TO_PROCEED_TO_NEXT_PROMPT` according to implementation/smoke evidence.

Stop and await explicit approval before any full 2016–2023 execution.
