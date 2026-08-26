# Full 2017-2023 Reconstructed Chain Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Append, independently validate, and finalize complete Reconstructed Schedule Flight Chain production partitions for 2017-2023 while preserving the accepted 2016 partition and all locked safety contracts.

**Architecture:** Execute the existing production CLI once per year, sequentially, with no row limit. After each successful reconstruction, run an independent bounded PyArrow ATL/source/output audit and resource/disk gate before invoking the next year; stop immediately on any critical failure. Preserve results in a run journal, then build the exact 2016-2023 production manifest, aggregate evidence, audit report, and independent decision only after every year passes.

**Tech Stack:** Python 3.11.15, pandas 2.3.3, PyArrow 25.0.1, SQLite 3.50.4, pytest 9.1.1, PowerShell.

**Spec:** `docs/superpowers/specs/2026-08-26-reconstructed-schedule-flight-chain-design.md`

## Global Constraints

- Authorized execution years are exactly 2017, 2018, 2019, 2020, 2021, 2022, and 2023; never invoke 2016 or 2024.
- Run one year at a time through `.venv\Scripts\python.exe`, `--chunk-size 100000`, with no `--max-rows`.
- Do not continue after a critical year, ATL, raw, holdout, environment, overwrite, contract, or disk-safety failure.
- Preserve `schedule_chain_v1`, `canonical_datetime_storage_amendment_v1`, stored `flight_key_v1`, `physical_aircraft_identity=false`, Weather `DROP`, and raw Chain `FINAL — NO_GO`.
- Never load raw `.pt`, use `torch.load`, train a model, construct Chain ML features, or run optimization/simulation.
- Keep full membership; do not truncate or pad chains to six.
- Do not commit, merge, push, or delete failed staging.

---

### Task 1: Fresh preflight and immutable 2016 baseline

**Files/data:**
- Read: `data/processed/flight_chain_reconstructed_v1/`
- Read: `artifacts/manifests/flight_chain_reconstructed_full_2016_manifest_v1.json`
- Create: `artifacts/manifests/flight_chain_reconstructed_2017_2023_run_journal_v1.json`

**Interfaces:**
- Consumes: accepted full-2016 production/evidence and current repository environment.
- Produces: tests/smoke/diff results, environment, raw inventory, free disk, exact present partitions, and immutable 2016 path/size/mtime/fingerprint baseline.

- [ ] Run `.\.venv\Scripts\python.exe -m pytest -q`, `.\.venv\Scripts\python.exe scripts/smoke_test.py`, and `git diff --check`; stop on failure.
- [ ] Verify Python/pandas/PyArrow/SQLite versions, Weather `DROP`, raw Chain `FINAL — NO_GO`, 2024 denial, no `torch.load`, and raw inventory hash across 36 files.
- [ ] Require production years exactly `[2016]`; require all 2017-2023 output partitions absent.
- [ ] Record 2016 logical fingerprints, row counts, and each 2016 Parquet path/size/`mtime_ns` before running 2017.
- [ ] Record canonical source row counts for 2017-2023 from Parquet metadata and verify their aggregate with 2016 equals the established 48,389,162 rows.
- [ ] Require free disk above a conservative next-year staging/output margin.

### Task 2: Sequential per-year reconstruction and fail-closed gate

**Files/data:**
- Create append-only: `data/processed/flight_chain_reconstructed_v1/{chain_groups,chain_members,inbound_target_map}/year=<YEAR>/`
- Update after each CLI invocation: `data/processed/flight_chain_reconstructed_v1/reconstruction_manifest.json`

**Interfaces:**
- Consumes: one `YEAR` in 2017-2023 and current disk/raw/partition state.
- Produces: validated production outputs, a one-year generated manifest record, removed successful staging, and measured resources.

- [ ] Before each year, require its three production partitions absent, prior completed partitions present, `.venv` versions unchanged, raw inventory unchanged, 2024 denied, and disk conservatively safe.
- [ ] Run `.\.venv\Scripts\python.exe scripts/reconstruct_flight_chain.py --years <YEAR> --chunk-size 100000` with no `--max-rows`.
- [ ] Require `PASS`, `is_complete=true`, no max rows, source count equals canonical metadata, mapped equals eligible, unmapped/duplicate-key/invalid-chain/multi-chain counts zero, safe leakage contract, raw unchanged, and successful staging cleanup.
- [ ] On any exception or critical metric, preserve failed staging and stop before the next year.

### Task 3: Independent ATL and schema validation after every year

**Files/data:**
- Read: `data/processed/tabular_by_year/year=<YEAR>/`
- Read: the three derived `year=<YEAR>` partitions.
- Modify: `artifacts/manifests/flight_chain_reconstructed_2017_2023_run_journal_v1.json`

**Interfaces:**
- Consumes: the completed year result from Task 2.
- Produces: canonical ATL count, output ATL counts, join anomalies, traceable examples, schema leakage results, and a year journal entry authorizing the next year.

- [ ] Independently batch-scan canonical normalized `DEST == "ATL"`; if exclusions exist, apply production eligibility before counting.
- [ ] Require canonical eligible ATL count equals inbound-map rows equals ATL chain-member rows.
- [ ] Require zero duplicate target/member keys, null chain IDs, invalid positions, missing/extra members, target/member mismatches, missing/duplicate groups, and group-length mismatches.
- [ ] Require every output schema has empty intersections with target, leakage, actual/outcome, Weather, uncertain, and `FLIGHTS` fields; require raw labels unused and aircraft identity false.
- [ ] Record at least three stored-flight-key trace examples plus year statistics, fingerprints, flight-number observations, actual resources, cleanup state, raw hash, holdout state, and disk-after-cleanup.
- [ ] Only after this entry passes may Task 2 execute the next numerical year.

### Task 4: Aggregate and cross-year validation

**Files/data:**
- Read: all eight production year partitions and journal/evidence manifests.

**Interfaces:**
- Consumes: PASS entries for 2016-2023.
- Produces: exact all-year totals, compatibility results, and immutable-2016 proof.

- [ ] Require production years exactly `[2016,2017,2018,2019,2020,2021,2022,2023]`, with no 2024 or extra partition.
- [ ] Sum actual source/eligible/mapped/chains/ATL/exclusions/ambiguities/duplicates/chains-over-six/output/runtime and require source total exactly equals calculated canonical total and established 48,389,162.
- [ ] Require all eight years share reconstruction, datetime-amendment, flight-key, aircraft, Weather, raw-mapping, and schema contracts.
- [ ] Recompute 2016 row counts/fingerprints and compare 2016 Parquet path/size/mtime against the preflight snapshot.
- [ ] Recompute raw inventory and require exact count/path/size/mtime/fingerprint equality; require 2024 denied.

### Task 5: Final manifests, report, decision, and documentation

**Files:**
- Create: `artifacts/manifests/flight_chain_reconstructed_manifest_v1.json`
- Finalize: `data/processed/flight_chain_reconstructed_v1/reconstruction_manifest.json`
- Modify: `docs/dataset_audit/flight_chain_reconstruction_report.md`
- Create: `docs/decisions/decision_reconstructed_chain.md`
- Modify: `docs/decisions/decision_registry.md`
- Modify: `docs/thesis_notes/assumptions.md`
- Modify: `docs/thesis_notes/limitations.md`
- Modify: `README.md`
- Modify: `project_structure.md`
- Modify: `configs/base.yaml`
- Modify top-level status only: `docs/superpowers/specs/2026-08-26-reconstructed-schedule-flight-chain-design.md`

**Interfaces:**
- Consumes: only an all-years aggregate/cross-year PASS.
- Produces: `FULL_DATA_PASS`, independent `GO_FOR_ABLATION`, and synchronized documentation without changing raw Chain status or enabling core ML use.

- [ ] Write the self-contained full-development evidence manifest with all contracts, per-year results/fingerprints/ATL/resources, aggregate, raw/holdout, and critical gates.
- [ ] Replace the generated production manifest with an exact eight-year manifest and set `overall_status=FULL_DATA_PASS` only after all gates pass.
- [ ] Finalize the audit report while preserving the original raw `.pt` evidence boundary and historical smoke/full-2016 evidence.
- [ ] Create the independent decision stating raw Chain `FINAL — NO_GO`, reconstructed schedule context `GO_FOR_ABLATION`, no aircraft identity, and no predictive-improvement claim.
- [ ] Update the registry/notes/README/structure/config reconstructed status only; keep raw block disabled and `no_go`.
- [ ] Update only the design spec top-level status; preserve historical sections/amendment.

### Task 6: Final verification and stop

**Files:**
- Verify: all production partitions, manifests, documentation, tests, raw data, and Git status.

**Interfaces:**
- Consumes: finalized full-development artifact.
- Produces: required Vietnamese final report and no further execution.

- [ ] Run `.\.venv\Scripts\python.exe -m pytest -q`, `.\.venv\Scripts\python.exe scripts/smoke_test.py`, `git diff --check`, `git status --short`, and `git diff --stat`.
- [ ] Parse and cross-check final manifests, production row counts, all ATL/gate results, 2016 immutability, raw inventory, Weather, 2024 denial, and raw decision.
- [ ] Keep the normal `main` workspace as-is; do not commit, merge, push, or clean user work.
- [ ] Return the required report and stop.
