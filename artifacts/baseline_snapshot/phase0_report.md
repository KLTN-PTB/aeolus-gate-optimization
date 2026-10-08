# PHASE 0 BASELINE SNAPSHOT & RECONCILIATION REPORT
## AEOLUS GATE OPTIMIZATION RESEARCH PLATFORM

**Target Phase:** Phase 0 — Baseline Freeze, Repository Inspection & Environment Reconciliation  
**Target Next Phase:** 1500-flight × 50-gate Scalability & Stress Benchmark  
**Generated At (UTC):** `2026-10-05T03:12:00Z`  
**Governing Architecture Protocol:** `AEOLUS_V4_PHASE14_FINAL_CERTIFICATION`  
**System Lifecycle State:** `CERTIFIED_WITH_LIMITATIONS`  
**Rebuild Decision:** `REBUILD_REQUIRED = NO`  
**Active Development Branch:** `development/scalability-1500x50`  
**Certified Baseline Commit:** `7ba0aba92d366f712977faaaa5a73cba65a32a55`  
**Baseline Test Verdict:** **`PASS (1,216/1,216 tests, 100%)`**  

---

## 1. EXECUTIVE SUMMARY & VERIFICATION VERDICT

In accordance with the mandatory **Scientific Safety Contract**, Phase 0 established an immutable, bit-for-bit verified research baseline prior to embarking on the upcoming 1500-flight × 50-gate scalability experiment.

```
====================================================================================================
PHASE 0 GATE DECLARATION & SAFETY VERDICT
====================================================================================================
PHASE_0_STATUS                                          = PASS
CERTIFIED_BASELINE_IDENTIFIED                           = YES (Commit 7ba0aba on branch v4-final-forensic-certification)
DEVELOPMENT_BRANCH_CREATED                              = YES (development/scalability-1500x50)
BASELINE_REGRESSION_TEST_STATUS                         = PASS (1,216/1,216 active tests, 0 failures, 86.44s)
P4_FROZEN_CHECKPOINT_HASH_VERIFIED                     = YES (SHA-256: e7e7462f17b65b276ebdee9c7beced15e090f69b088a18896d5a91aaa8cb062f)
P5_FORECAST_ONLY_ROLE_PRESERVED                         = YES (Role B: Quantile Forecast Champion; no continuous sampling)
2024_HOLDOUT_TUNING_OR_RETRAINING                      = ZERO (Strictly POST_HOLDOUT_REEVALUATION_AFTER_METHODOLOGY_REPAIR)
ML_MODELS_RETRAINED                                     = ZERO (0 models touched or refitted)
WEATHER_IN_CORE_ARRIVAL                                 = ZERO (100% prohibited and absent)
FLIGHT_CHAIN_IN_CORE_ARRIVAL                            = ZERO (100% prohibited and absent)
STRESS_TEST_IMPLEMENTATION                              = NOT_STARTED (Phase 0 scope strictly enforced)
API_OR_DASHBOARD_IMPLEMENTATION                         = NOT_STARTED (Phase 0 scope strictly enforced)
REMAINING_BLOCKERS                                      = ZERO (0)
====================================================================================================
```

---

## 2. STEP 1: REPOSITORY STATE & BASELINE INSPECTION

A comprehensive forensic inspection of the repository was conducted:

1. **Git State:**
   - **Base Branch:** `v4-final-forensic-certification`
   - **HEAD Commit:** `7ba0aba92d366f712977faaaa5a73cba65a32a55`
   - **Commit Message:** `docs(sync): synchronize project documentation, master index map, and README with V5 certification state`
   - **Status:** Unstaged modifications and untracked files are 100% accounted for as the documentation synchronization and downstream audit artifacts delivered during Phases P10 through P15 (documented in [`THESIS_EVIDENCE_NORMALIZATION_REPORT.md`](file:///D:/Study/Code/Python/Aelous/THESIS_EVIDENCE_NORMALIZATION_REPORT.md)).
2. **Authoritative Checkpoint & Manifest Verification:**
   - **P4 Model Checkpoint:** Located at [`artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib`](file:///D:/Study/Code/Python/Aelous/artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib).
     - Physical SHA-256: `e7e7462f17b65b276ebdee9c7beced15e090f69b088a18896d5a91aaa8cb062f`
     - Matches `system_freeze_manifest.json` lines 169 & 315 bit-for-bit.
   - **System Freeze Manifest:** Located at [`system_freeze_manifest.json`](file:///D:/Study/Code/Python/Aelous/system_freeze_manifest.json) (and mirrored in `artifacts/manifests/system_freeze_manifest.json`).
     - Physical SHA-256: `9e6693dafae3ba439c0b6b9a5f3038ec87f0dd63f75dbcad5752ff8da0f98214`
     - Matches [`FINAL_TEST_SCOPE_RECONCILIATION.md`](file:///D:/Study/Code/Python/Aelous/FINAL_TEST_SCOPE_RECONCILIATION.md) line 54 bit-for-bit.
   - **Predictor Contract Code:** Located at [`src/features/tabular_features.py`](file:///D:/Study/Code/Python/Aelous/src/features/tabular_features.py).
     - Physical SHA-256: `33d2e08b37058032764cd6968021542aeca3aa68268bf9525bf878e217234418`
     - Matches `system_freeze_manifest.json` line 57 bit-for-bit.

---

## 3. STEP 2: BASELINE REGRESSION TEST EXECUTION

The full active regression test suite was executed against the local virtual environment:

- **Command:** `& "D:\Study\Code\Python\Aelous\.venv\Scripts\python.exe" -m pytest`
- **Execution Timestamp:** `2026-10-05T03:07:56Z`
- **Python Version:** `Python 3.11.15 (main, Mar 10 2026, 18:12:25) [MSC v.1944 64 bit (AMD64)]`
- **Pytest Version:** `pytest-9.1.1 (pluggy-1.6.0)`
- **Platform:** `win32 (Windows-10-10.0.19045-SP0)`
- **Duration:** `86.44 seconds (0:01:26)`
- **Exit Code:** `0`
- **Result:** **`1,216 passed, 0 failed, 1 warning`** (100% PASS across 161 test files).

### Test Scope Governance (`pytest.ini`):
The test harness operates under the governance policy established in Phase P12.1 / P12-R1:
- **Active Tests:** 1,216 tests verifying all 13 certified scientific domains (`CLAIM_01` through `CLAIM_13`).
- **Retired Historical Guards (Safely Quarantined):** Exactly 3 files ignored via `pytest.ini` (`tests/test_final_evaluation_guard.py`, `tests/test_final_evaluation_guard_v2.py`, `tests/test_post_holdout_evaluation_v2.py`, accounting for 37 obsolete test items). These targeted obsolete v1/v2 freeze hashes prior to downstream refactoring and have 0 production callers (cataloged in [`artifacts/audit/retired_guard_scope_manifest.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/retired_guard_scope_manifest.json)).

---

## 4. STEP 3: DEVELOPMENT BRANCH CREATION

To ensure isolation from the certification baseline:
- **Active Development Branch:** `development/scalability-1500x50`
- **Command Executed:** `git checkout -b development/scalability-1500x50`
- **Base Branch:** `v4-final-forensic-certification` at commit `7ba0aba92d366f712977faaaa5a73cba65a32a55`.
- **Integrity Rule:** History was strictly preserved; zero branches, tags, or historical commits were rewritten or deleted.

---

## 5. STEP 4: BASELINE SNAPSHOT INVENTORY

A dedicated, non-destructive baseline snapshot directory was established at [`artifacts/baseline_snapshot/`](file:///D:/Study/Code/Python/Aelous/artifacts/baseline_snapshot):

| Snapshot File | Description | Checksum / Identifier |
| :--- | :--- | :--- |
| [`git_commit.txt`](file:///D:/Study/Code/Python/Aelous/artifacts/baseline_snapshot/git_commit.txt) | Exact commit hash, author, and message of baseline | Commit `7ba0aba92d366f712977faaaa5a73cba65a32a55` |
| [`git_status.txt`](file:///D:/Study/Code/Python/Aelous/artifacts/baseline_snapshot/git_status.txt) | Complete git working tree status on `development/scalability-1500x50` | Tracked modifications & untracked audit artifacts |
| [`environment.txt`](file:///D:/Study/Code/Python/Aelous/artifacts/baseline_snapshot/environment.txt) | Complete platform details and pip list (all 89 packages) | Python 3.11.15, NumPy 2.2.6, SciPy 1.17.1, OR-Tools 9.15.6755 |
| [`test_summary.txt`](file:///D:/Study/Code/Python/Aelous/artifacts/baseline_snapshot/test_summary.txt) | Detailed test execution log, exit code, and runtime duration | 1,216 passed / 1,216 run, exit code 0 |
| [`baseline_manifest.json`](file:///D:/Study/Code/Python/Aelous/artifacts/baseline_snapshot/baseline_manifest.json) | Machine-readable manifest linking code hashes, model hashes, and invariants | SHA-256 sidecars across all critical system files |

---

## 6. STEP 5: DOCUMENTATION RECONCILIATION & DRIFT ANALYSIS

Forensic investigation resolved all known documentation discrepancies by referencing physical source code and authoritative audit manifests:

### 6.1. Feature Count Reconciliation (10 vs 11 Features)
- **Investigation:**
  - `src/features/tabular_features.py`: Defines `APPROVED_PREDICTOR_COLUMNS` consisting of 8 numeric features (`CRS_ELAPSED_TIME`, `calendar_year`, `calendar_month`, `calendar_day_of_month`, `calendar_day_of_week`, `is_weekend`, `scheduled_departure_hour`, `scheduled_departure_minute`), 2 low-cardinality categorical features (`OP_CARRIER`, `ORIGIN`), and 1 high-cardinality frequency feature (`OP_CARRIER_FL_NUM`). Total: **11 features**.
  - `src/audit/protocol_guards.py#L19` & `#L669`: Explicitly mandates and tests the **11-feature contract**.
  - `system_freeze_manifest.json#L126`: Explicitly specifies `"feature_count": 11`.
  - `artifacts/audit/FEATURE_LINEAGE_AUDIT.md#L17-19`: Clarifies the lineage:
    * **V1 (11 features):** Authoritative active core predictor set (includes `calendar_year`).
    * **V1.1 (13 features):** Adds `scheduled_arrival_hour` and `scheduled_arrival_minute`.
    * **V2 (10 features):** Experimental ablation that removed `calendar_year` to eliminate cross-year covariate shift.
- **Reconciliation Verdict:** The canonical, production, and certified feature contract is **11 features (V1)**. Statements in older text mentioning "10 features" were informal references or conflations with the V2 ablation. `docs/CURRENT_STATE.md` was reconciled to clarify this distinction.

### 6.2. Test Count Discrepancy Reconciliation (180 vs 1,216 Tests)
- **Investigation:**
  - `artifacts/audit/AGENT_FULL_FORENSIC_PROJECT_INVENTORY.md#L947` & `TEST_SCOPE_RECONCILIATION.md#L14-38`: Cites **180 tests** as the sum of the 12 audit test suites (`tests/audit/test_r25_*.py` through `tests/audit/test_r37_*.py`) created during the Phase R37 / V5 certification pass.
  - Live AST and PyTest discovery: The repository contains 164 total test files. PyTest collects **1,216 active tests** across 161 files (with 3 historical guard files quarantined in `pytest.ini`).
- **Reconciliation Verdict:** **1,216 active tests** is the authoritative, repository-wide regression test count. **180 tests** represents solely the audit-suite subset. Both numbers are mathematically correct within their respective scopes.

### 6.3. P4 Checkpoint Hash Reconciliation
- **Investigation:**
  - Physical file on disk: `artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib`
  - Computed SHA-256: `e7e7462f17b65b276ebdee9c7beced15e090f69b088a18896d5a91aaa8cb062f`
  - `system_freeze_manifest.json` lines 169 & 315: `e7e7462f17b65b276ebdee9c7beced15e090f69b088a18896d5a91aaa8cb062f`
  - `FINAL_SCIENTIFIC_CERTIFICATION_REPORT.md` line 112: `e7e7462f17b65b276ebdee9c7beced15e090f69b088a18896d5a91aaa8cb062f`
  - `src/evaluation/native_downstream_p4.py` line 6: `e7e7462f17b65b276ebdee9c7beced15e090f69b088a18896d5a91aaa8cb062f`
  - `docs/CURRENT_STATE.md` line 39 previously contained an outdated hash string (`e7e7462fa1a11516...`).
- **Reconciliation Verdict:** The correct and bit-for-bit verified SHA-256 hash is `e7e7462f17b65b276ebdee9c7beced15e090f69b088a18896d5a91aaa8cb062f`. `docs/CURRENT_STATE.md` was reconciled accordingly.

### 6.4. Holdout 2024 Semantics & Model Role Hardening
- **Calendar Year 2024:** Authoritatively classified as `POST_HOLDOUT_REEVALUATION_AFTER_METHODOLOGY_REPAIR`. It was unsealed post-repair in Phase P11-R under cryptographic audit. It must NEVER be described as an untouched, unseen, or first-access holdout.
- **Model Role Decoupling:**
  - `P5_quantile_regression`: Role B (Marginal Quantile Forecast Champion). Strictly `FORECAST_ONLY`, 9 quantiles. Prohibited from continuous sampling or Monte Carlo generation.
  - `P4_ngboost_student_t`: Role C (Continuous Downstream Simulation Champion). Closed-form analytical Student-T CRPS ($18.33$ min) and continuous NLL ($4.62$). Sole authorized probabilistic generator for downstream Monte Carlo flight delay draws.
  - `arrival_linear_baseline_v1`: Point baseline (Ridge).
- **Synthetic Simulation Boundary:** All gate assignments and operational metrics are bounded to the synthetic research airfield simulation (`AircraftTurnModel`, 10 contact gates + 1 overflow stand). Zero real-world ATL operational delay reduction is claimed.

---

## 7. UNRESOLVED INCONSISTENCIES

**NONE.** All physical artifacts, configuration files, git history, and test suites are 100% reconciled and mutually consistent.

---

## 8. DEFINITION OF DONE VERIFICATION

- [x] Certified baseline identified: Commit `7ba0aba92d366f712977faaaa5a73cba65a32a55` on `v4-final-forensic-certification`.
- [x] Development branch created: `development/scalability-1500x50`.
- [x] Baseline tests pass: 1,216 / 1,216 active tests pass 100% (exit code 0, 86.44s).
- [x] Baseline snapshot exists: Complete inventory in `artifacts/baseline_snapshot/`.
- [x] Documentation drift documented and reconciled: 10 vs 11 features, 180 vs 1,216 tests, P4 hash.
- [x] No scientific methodology changed: Preserved all 13 claims and mathematical formulations.
- [x] No ML model retrained: Frozen weights remain bit-for-bit untouched.
- [x] No 2024 tuning occurred: Preserved `POST_HOLDOUT_REEVALUATION_AFTER_METHODOLOGY_REPAIR` status.
- [x] Working tree state explicitly reported.
- [x] Stress-test, API, and Dashboard implementations deferred to subsequent phases.

Phase 0 is formally **COMPLETE**. Execution stops here in accordance with instructions.
