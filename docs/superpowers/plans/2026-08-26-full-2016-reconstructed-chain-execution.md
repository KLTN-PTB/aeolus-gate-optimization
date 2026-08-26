# Full 2016 Reconstructed Chain Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run and audit the approved full 2016 Reconstructed Schedule Flight Chain without accessing or executing 2017-2024.

**Architecture:** Use the existing Python 3.11 `.venv`, PyArrow scanner, and per-year SQLite staging pipeline unchanged. Publish only the complete 2016 production partition, then independently validate year-level gates and real inbound-ATL mappings from canonical source and derived Parquet using bounded scans.

**Tech Stack:** Python 3.11.15, pandas 2.3.3, PyArrow 25.0.1, SQLite 3.50.4, pytest 9.1.1, PowerShell.

**Spec:** `docs/superpowers/specs/2026-08-26-reconstructed-schedule-flight-chain-design.md`

## Global Constraints

- Execute only year 2016; never invoke 2017-2023 or inspect 2024 development data.
- Use `.venv\Scripts\python.exe` and the existing `chunk_size=100000`.
- Do not pass `--max-rows`.
- Do not read raw Flight Chain `.pt`, use `torch.load`, change Weather `DROP`, recompute `flight_key_v1`, or modify `data/raw/**`.
- Original Aeolus raw Flight Chain remains `FINAL — NO_GO`.
- Do not set `GO_FOR_ABLATION` or create a final 2016-2023 decision.
- Do not commit or push repository changes.

---

### Task 1: Update current top-level design status only

**Files:**
- Modify: `docs/superpowers/specs/2026-08-26-reconstructed-schedule-flight-chain-design.md`

**Interfaces:**
- Consumes: accepted datetime amendment and corrected bounded-smoke evidence.
- Produces: current status text stating amendment implemented, smoke A/B PASS, full 2016 not yet executed.

- [ ] **Step 1:** Locate the stale top-level status paragraph before any historical audit/amendment section.
- [ ] **Step 2:** Replace only that status text; do not alter historical evidence or the versioned amendment.
- [ ] **Step 3:** Inspect the focused diff and confirm the change is confined to the top-level status text.

### Task 2: Preflight the full-2016 production run

**Files/data:**
- Read: `configs/base.yaml`
- Read: `data/processed/tabular_by_year/year=2016/`
- Verify absent: `data/processed/flight_chain_reconstructed_v1/`

**Interfaces:**
- Consumes: existing CLI and production output configuration.
- Produces: verified interpreter/dependencies, 5,537,987-row input count, free disk, raw inventory fingerprint, and safety-guard baseline.

- [ ] **Step 1:** Verify `.venv` reports Python 3.11.15 and approved dependency versions.
- [ ] **Step 2:** Call `assert_data_access_allowed(2016, "development")` and confirm 2024 development access is denied.
- [ ] **Step 3:** Confirm the production output root does not exist and the canonical 2016 Parquet metadata totals 5,537,987 rows.
- [ ] **Step 4:** Snapshot all raw path/size/`mtime_ns` entries and compute the stable inventory fingerprint.
- [ ] **Step 5:** Confirm Weather is `DROP`, `flight_key_v1` is unchanged, raw Chain decision is `FINAL — NO_GO`, and reconstruction code contains no `torch.load`.

### Task 3: Run the complete 2016 reconstruction

**Files/data:**
- Create: `data/processed/flight_chain_reconstructed_v1/`

**Interfaces:**
- Consumes: `scripts/reconstruct_flight_chain.py --years 2016 --chunk-size 100000` with no `--max-rows`.
- Produces: complete 2016 chain groups, members, inbound target map, and `reconstruction_manifest.json`.

- [ ] **Step 1:** Run exactly:

  ```powershell
  .\.venv\Scripts\python.exe scripts/reconstruct_flight_chain.py --years 2016 --chunk-size 100000
  ```

- [ ] **Step 2:** Poll the single process while it runs and do not launch any other year.
- [ ] **Step 3:** Require status `PASS`, `is_complete=true`, `source_partition_rows=5537987`, and staging removed after PASS.
- [ ] **Step 4:** If it fails, retain staging, publish no success claim, skip later-year execution, and report the exact gate/error.

### Task 4: Validate full-2016 year gates and real ATL mappings

**Files/data:**
- Read: `data/processed/tabular_by_year/year=2016/`
- Read: `data/processed/flight_chain_reconstructed_v1/{chain_groups,chain_members,inbound_target_map}/year=2016/`

**Interfaces:**
- Consumes: completed 2016 manifest and derived Parquet.
- Produces: independent gate results, ATL source/output counts, mapping-integrity checks, and traceable stored-flight-key examples.

- [ ] **Step 1:** Verify manifest gates: mapped equals eligible, duplicate flight key zero, invalid chain ID zero, multi-chain membership zero, and unmapped eligible rows zero.
- [ ] **Step 2:** Inspect all three Arrow schemas and require zero target, actual/outcome, Weather, uncertain, or `FLIGHTS` columns.
- [ ] **Step 3:** If exclusions are zero, independently count canonical `DEST == "ATL"` with a projected PyArrow batch scan; if exclusions exist, apply the production eligibility normalizers during the bounded scan before counting ATL.
- [ ] **Step 4:** Scan emitted inbound targets and require row count equals independently counted eligible ATL rows, unique `target_flight_key`, non-null single `chain_id`, and `0 <= chain_position < chain_length`.
- [ ] **Step 5:** Scan ATL chain members and require every emitted target key has exactly one member with identical `chain_id` and `chain_position`.
- [ ] **Step 6:** Scan referenced chain groups and require target `chain_length` equals group `member_count` for every target.
- [ ] **Step 7:** Record several examples containing stored `flight_key`, chain ID, position/length, source row, service date, carrier/flight number, origin, destination, and departure time.
- [ ] **Step 8:** Recompute raw inventory and require exact path/size/`mtime_ns` equality; reconfirm 2024 denial and Weather `DROP`.

### Task 5: Publish full-2016 evidence

**Files:**
- Create: `artifacts/manifests/flight_chain_reconstructed_full_2016_manifest_v1.json`
- Create: `docs/dataset_audit/flight_chain_reconstructed_full_2016_report.md`

**Interfaces:**
- Consumes: production manifest, independent ATL audit, schemas, resources, raw inventory, and examples.
- Produces: self-contained thesis evidence with status `FULL_2016_PASS` or the exact failure state.

- [ ] **Step 1:** Record complete row/mapping/chain/ambiguity/duplicate-signature statistics and all exclusion reasons.
- [ ] **Step 2:** Record measured runtime, rows/second, peak staging, peak SQLite, output bytes, peak Python allocation, free disk before/after, and staging cleanup status.
- [ ] **Step 3:** Record all critical gate results, ATL counts and integrity checks, raw/holdout/weather evidence, and traceable examples.
- [ ] **Step 4:** State explicitly that only 2016 ran, 2017-2023 remain NOT RUN, and status remains below `GO_FOR_ABLATION`.

### Task 6: Final regression and stop gate

**Files:**
- Verify: repository working tree and all evidence above.

**Interfaces:**
- Consumes: completed full-2016 output and evidence artifacts.
- Produces: final review report; no later-year execution.

- [ ] **Step 1:** Run `\.venv\Scripts\python.exe -m pytest -q` and require zero failures.
- [ ] **Step 2:** Run `\.venv\Scripts\python.exe scripts/smoke_test.py` and require PASS.
- [ ] **Step 3:** Run `git diff --check` and require exit code zero.
- [ ] **Step 4:** Run final raw inventory, Weather, 2024, raw decision, output completeness, and `git status --short -- data/raw` checks.
- [ ] **Step 5:** Run `git status --short` and `git diff --stat`; report changed files without committing.
- [ ] **Step 6:** Stop and return the required full-2016 review status. Do not execute 2017-2023.
