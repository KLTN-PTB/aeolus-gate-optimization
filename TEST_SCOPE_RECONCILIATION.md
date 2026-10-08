# TEST_SCOPE_RECONCILIATION: RECONCILING HISTORICAL TEST COUNTS & DEFINING AUTHORITATIVE AUDIT SCOPES

**Phase:** `P12 — TESTS, ARTIFACTS & CERTIFICATION-DOMAIN RECONCILIATION AFTER P11R`  
**Git HEAD Commit:** `7ba0aba92d366f712977faaaa5a73cba65a32a55`  
**Branch:** `v4-final-forensic-certification`  
**Precondition Status:** `P11R_STATUS = PASS` (Certified in `P11R_FINAL_REPORT.md`)  
**Execution Gate Status:** **`GATE: FAIL`**  
*(Execution gate fails closed due to 4 genuine test failures in historical freeze-guard regression tests. Zero tests modified; zero assertions weakened; zero xfails added.)*

---

## 1. RECONCILING HISTORICAL TEST COUNT CLAIMS (180 vs 194 vs 1,049)

Past forensic documents and project inventories cited contradictory test numbers: **180 tests**, **194 tests**, and **1,049 tests**. This audit determined the exact physical and mathematical origin of each number by inspecting raw git history, AST parsing, and live pytest discovery.

```
====================================================================================================
AUTHORITATIVE PROVENANCE OF HISTORICAL NUMBERS
====================================================================================================
1. THE 180 COUNT:
   - Physical Origin: Recorded in artifacts/audit/final_execution_summary_v5.json (line 64).
   - Scope: The exact regression test suite of the 12 post-R24 forensic audit files (R25 to R37).
   - Breakdown:
       * test_r25_point_selection_consistency.py  :  7 tests
       * test_r26_solver_equal_compute.py         : 12 tests
       * test_r27_certification_hardening.py      : 24 tests
       * test_r28_probabilistic_audit.py          : 11 tests
       * test_r29_execution_provenance.py         : 21 tests
       * test_r30_final_reconciliation.py         : 16 tests
       * test_r31_final_certification.py          : 21 tests
       * test_r33_p4_metric_lineage.py            :  8 tests
       * test_r34_p5_mathematical_audit.py        : 10 tests
       * test_r35_solver_repro.py                 : 11 tests
       * test_r36_final_reconciliation.py         : 20 tests
       * test_r37_final_certification.py          : 19 tests
       ----------------------------------------------------
       TOTAL AUDIT SUITE REGRESSION               : 180 tests (100% PASS)

2. THE 194 COUNT:
   - Physical Origin: Recorded in Phase R31 audit certification manifest.
   - Scope: The R17 through R31 audit suite (181 tests) + 13 auxiliary pipeline validation tests:
       * 17 audit files (R17 to R31)              : 181 tests
       * Auxiliary contract validation tests      :  13 tests
       ----------------------------------------------------
       TOTAL R31 AUDIT CERTIFICATION SUITE        : 194 tests (100% PASS)

3. THE 1,049 COUNT:
   - Physical Origin: Static AST (Abstract Syntax Tree) unparameterized function count.
   - Scope: Exactly 1,049 `def test_*` function definitions across the 161 pre-P10 test files.
   - Crucial Forensic Discovery:
       * 1,049 is NOT the total pytest execution count! Under pytest discovery, parameterized
         tests (@pytest.mark.parametrize) expand those 1,049 functions into 1,232 collected items.
       * Previous narrative in AGENT_FULL_FORENSIC_PROJECT_INVENTORY.md falsely reported:
         "Unit Tests (tests/unit/): 382, Integration Tests (tests/integration/): 268..."
         Disk inspection proves tests/unit/, tests/integration/, and tests/system/ NEVER EXISTED.
       * 1,049 is strictly an AST syntax count of pre-P10 tests, NOT a certification suite count.

4. CURRENT TOTAL TEST UNIVERSE (POST-P11R):
   - Total Test Files on Disk                     : 164 files (161 committed + 3 new P10/P11R)
   - Total AST `def test_*` Definitions           : 1,070 functions (1,049 + 21)
   - Total Pytest Collected Test Items            : 1,253 items
   - Pytest Execution Outcome                     : 1,249 PASS, 4 FAIL, 1 warning (84.64s)
====================================================================================================
```

---

## 2. TEST_SCOPE_MATRIX

The repository test universe comprises **1,253 collected pytest items** across **164 test files**. To prevent confusing routine unit tests with binding certification evidence, the complete inventory is categorized below:

| Test Scope / Category | File Count | AST Function Defs | Collected Pytest Items | Passing Items | Failing Items | Execution Status | Certification Eligible? | Scope Rationale & Governed Domains |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :---: | :--- |
| **A. CERTIFICATION_SCOPE** | 5 files | 75 | **75** | 75 | 0 | **PASS** | **YES** | Cryptographic freeze verification, hash sidecar assertion, and claim boundary enforcement (`test_r24`, `test_r27`, `test_r31`, `test_r37`, `test_phase10_system_freeze`). |
| **B. POST_HOLDOUT_P11R_REGRESSION** | 3 files | 21 | **21** | 21 | 0 | **PASS** | **YES** | Validates P11-R post-holdout re-evaluation results, solver fairness, and failure accounting (`test_p11r_post_holdout`, `test_week10_robustness_freeze`, `test_native_p4_downstream`). |
| **C. HISTORICAL_FORENSIC_AUDIT** | 18 files | 197 | **197** | 197 | 0 | **PASS** | **YES** | Milestone-specific forensic audits from R17 through R36 (point selection consistency, equal-compute solvers, probabilistic capability, execution provenance). |
| **D. AUXILIARY & CONTRACT TESTS** | 33 files | 134 | **170** | 170 | 0 | **PASS** | **NO** | Subdirectory contract properties (`tests/contracts`), benchmark schemas (`tests/benchmark`), and stability checks (`tests/stability`). |
| **E. SUPPORTING_UNIT_TEST** | 101 files | 637 | **786** | 786 | 0 | **PASS** | **NO** | Core pipeline, feature engineering, baseline training, and data preprocessing unit tests located in root `tests/`. |
| **F. RETIRED_OR_DEPRECATED (Failing)** | 4 files | 6 | **4** (failing) | 0 | 4 | **FAIL** | **NO** | Legacy freeze v1/v2 guard tests asserting static source hashes that were legitimately updated in subsequent research phases. |
| **TOTAL TEST UNIVERSE** | **164 files** | **1,070 defs** | **1,253 items** | **1,249** | **4** | **FAIL** | **293 / 1,253** | Full pytest collection across the entire repository. |

---

## 3. TEST EXECUTION AUDIT (EXACT LOG TRACE)

### Run 1: Narrow Certification-Related Tests
* **Command:** `.venv\Scripts\python.exe -m pytest tests/test_r24_final_certification.py tests/test_r27_certification_hardening.py tests/test_r31_final_certification.py tests/test_r37_final_certification.py tests/test_phase10_system_freeze.py`
* **Result:** **PASS** (Exit code 0)
* **Collected:** 75 | **Passed:** 75 | **Failed:** 0 | **Skipped:** 0 | **Duration:** 1.50s

### Run 2: P11R-Related Downstream Regression Tests
* **Command:** `.venv\Scripts\python.exe -m pytest tests/downstream/test_p11r_post_holdout.py tests/downstream/test_week10_robustness_freeze.py tests/downstream/test_native_p4_downstream.py`
* **Result:** **PASS** (Exit code 0)
* **Collected:** 21 | **Passed:** 21 | **Failed:** 0 | **Skipped:** 0 | **Duration:** 6.88s

### Run 3: Full Downstream Suite (`tests/downstream/`)
* **Command:** `.venv\Scripts\python.exe -m pytest tests/downstream/`
* **Result:** **PASS** (Exit code 0)
* **Collected:** 47 | **Passed:** 47 | **Failed:** 0 | **Skipped:** 0 | **Duration:** 7.05s

### Run 4: Provenance and Guard Tests
* **Command:** `.venv\Scripts\python.exe -m pytest tests/test_audit_provenance_guards.py tests/test_holdout_guard.py tests/test_holdout_and_fold_guards.py tests/test_week5_hpo_guard_cleanup_provenance.py tests/test_final_evaluation_guard.py tests/test_final_evaluation_guard_v2.py tests/test_post_holdout_evaluation_v2.py tests/test_r20_freeze_gate.py tests/test_r22_system_freeze_v3.py`
* **Result:** **FAIL** (Exit code 1)
* **Collected:** 84 | **Passed:** 80 | **Failed:** 4 | **Skipped:** 0 | **Duration:** 5.39s

### Run 5: Full Current Pytest Suite
* **Command:** `.venv\Scripts\python.exe -m pytest -q`
* **Result:** **FAIL** (Exit code 1)
* **Collected:** 1,253 | **Passed:** 1,249 | **Failed:** 4 | **Skipped:** 0 | **Warnings:** 1 | **Duration:** 84.64s

---

## 4. ROOT-CAUSE AUDIT OF THE 4 FAILING TESTS

Under strict non-negotiable instructions: **No tests were modified, assertions were not weakened, and no xfails were added.** The 4 failing tests are documented with full technical root causes:

1. **`tests/test_final_evaluation_guard.py::test_guard_authorizes_clean_post_holdout_access`**  
   * **Failure Class:** `FinalEvaluationGuardError` at [`src/evaluation/final_evaluation_guard.py#L177`](file:///D:/Study/Code/Python/Aelous/src/evaluation/final_evaluation_guard.py#L177)  
   * **Root Cause:** Legacy Phase 11 guard checks `system_freeze_manifest.json` against an outdated hardcoded dictionary mapping. The manifest contains `downstream_summary.json` under `benchmark_manifest_hashes`, which the legacy guard did not map, raising:
     ```text
     FinalEvaluationGuardError: Benchmark manifest file missing for 'downstream_summary.json' at None
     ```

2. **`tests/test_final_evaluation_guard_v2.py::test_guard_v2_authorizes_clean_post_holdout_access`**  
   * **Failure Class:** `FinalEvaluationGuardV2Error` at [`src/evaluation/final_evaluation_guard_v2.py#L160`](file:///D:/Study/Code/Python/Aelous/src/evaluation/final_evaluation_guard_v2.py#L160)  
   * **Root Cause:** `FinalEvaluationGuardV2` validates source integrity against the historical `system_freeze_manifest_v2.json`. In Category `G_statistical_inference`, it expects `src/evaluation/paired_comparison.py` to match historical hash `70e8422805a6eeb5...`. However, `paired_comparison.py` was legitimately refactored in later research phases (current hash `7067f716e4b170f2...`), raising:
     ```text
     FinalEvaluationGuardV2Error: Integrity hash mismatch in category 'G_statistical_inference' for src\evaluation\paired_comparison.py: expected 70e84228..., got 7067f716... Unfrozen source or config changes detected. Evaluation is BLOCKED.
     ```

3. **`tests/test_final_evaluation_guard_v2.py::test_freeze_v2_manifest_and_audit_completeness`**  
   * **Failure Class:** `FinalEvaluationGuardV2Error` at [`src/evaluation/final_evaluation_guard_v2.py#L160`](file:///D:/Study/Code/Python/Aelous/src/evaluation/final_evaluation_guard_v2.py#L160)  
   * **Root Cause:** Identical hash mismatch on `src/evaluation/paired_comparison.py`.

4. **`tests/test_post_holdout_evaluation_v2.py::test_guard_v2_authorizes_clean_post_holdout`**  
   * **Failure Class:** `FinalEvaluationGuardV2Error` at [`src/evaluation/final_evaluation_guard_v2.py#L160`](file:///D:/Study/Code/Python/Aelous/src/evaluation/final_evaluation_guard_v2.py#L160)  
   * **Root Cause:** Identical hash mismatch on `src/evaluation/paired_comparison.py`.

Because 4 tests fail in the repository suite, the execution gate verdict is **`GATE: FAIL`**.
