# UI-R00: 04 — EXISTING TEST BASELINE & VERIFICATION LOGS

**Document ID:** `AEOLUS-UI-R00-04-TEST-BASELINE`  
**Phase:** UI-R00 (Baseline, Technical Audit & Safety Freeze)  
**Audit Timestamp:** 2026-10-10T23:28:00+07:00  
**Auditor:** Senior Scientific QA Lead & Test Automation Specialist  

---

## 1. Executive Summary

A critical requirement of UI-R00 is establishing an immutable test baseline before any UI redesign code is written.

All tests in the repository were executed against the active virtual environment (`.venv`, Python 3.11.15). The audit verified:
1. **123 / 123 tests PASSED** in the dedicated dashboard test suite (`tests/dashboard/`).
2. **89 / 89 tests PASSED** in the core ML and optimization regression test suites (`tests/test_*_p07..p09.py`).
3. **10 / 10 page-mode combinations PASSED** under `streamlit.testing.v1.AppTest` with **0 unhandled exceptions**.
4. **Total Verified Tests:** **212 / 212 tests (100% Pass Rate)**.

Per UI-R00 safety rules, **zero test assertions were altered, commented out, or loosened**.

---

## 2. Test Execution Log 1: Dashboard Suite (`tests/dashboard/`)

- **Command Executed:** `.\.venv\Scripts\python.exe -m pytest tests/dashboard/ -v`
- **Working Directory:** `D:\Study\Code\Python\Aelous`
- **Execution Date:** 2026-10-10 23:16:35
- **Exit Code:** `0`
- **Duration:** `19.13 seconds`
- **Summary:** `123 passed, 3 warnings in 19.13s`

### 2.1. Test Suite Breakdown

| Test Module | Test Count | Status | Scope Tested |
| :--- | :---: | :---: | :--- |
| `test_foundation.py` | 16 | **16 PASS** | Theme tokens, contracts, scenario loading, allowlists, capacity policies |
| `test_gate_operations.py` | 28 | **28 PASS** | Live solving, greedy/cpsat bounds, independent verifier, export integrity |
| `test_lab_and_robustness.py` | 26 | **26 PASS** | Multi-solver benchmarks, Monte Carlo modes, paired analysis, audit drawer |
| `test_services.py` | 6 | **6 PASS** | Scenario quarantine, live solver limit guards, preflight artifact health |
| `test_ui_components.py` | 20 | **20 PASS** | Plotly theme, charts 01/02/03/05/06/08, KPI scorecards, leakage guards |
| `test_final_acceptance.py` | 27 | **27 PASS** | Acceptance criteria P10-F, visual QA invariants, offline operation |
| **Total Dashboard Suite** | **123** | **123 PASS** | **100% Success Rate** |

### 2.2. Pytest Warnings Logged
Three deprecation warnings were captured during execution (non-fatal, origin: third-party SHAP library):
```text
tests/dashboard/test_foundation.py::test_p10b_16_preflight_handles_missing_optional_artifacts
  D:\Study\Code\Python\Aelous\.venv\Lib\site-packages\shap\plots\colors\_colors.py:47: PendingDeprecationWarning: 
  The set_bad function will be deprecated in a future version. Use cmap.with_extremes(bad=...) or Colormap(bad=...) instead.
```

---

## 3. Test Execution Log 2: Core Regression Pipeline Suite (P07–P09)

- **Command Executed:** `.\.venv\Scripts\python.exe -m pytest tests/test_native_dual_core_pipeline_p07.py tests/test_ml_research_validation_p08.py tests/test_monte_carlo_robustness_p09.py -v`
- **Working Directory:** `D:\Study\Code\Python\Aelous`
- **Execution Date:** 2026-10-10 23:17:03
- **Exit Code:** `0`
- **Duration:** `7.88 seconds`
- **Summary:** `89 passed, 3 warnings in 7.88s`

### 3.1. Regression Test Breakdown

| Test Suite | Test Count | Status | Research Area |
| :--- | :---: | :---: | :--- |
| `test_native_dual_core_pipeline_p07.py` | 30 | **30 PASS** | Native dual turn engine, prediction contract, adapter verification |
| `test_ml_research_validation_p08.py` | 26 | **26 PASS** | Temporal train-test non-overlap, cutoff compliance, TreeSHAP additivity |
| `test_monte_carlo_robustness_p09.py` | 33 | **33 PASS** | 500 scenario accounting, paired difference formulas, Oracle labeling |
| **Total Regression Suite** | **89** | **89 PASS** | **100% Success Rate** |

---

## 4. Test Execution Log 3: Headless Streamlit AppTest Smoke

- **Engine:** `streamlit.testing.v1.AppTest`
- **Script:** `dashboard/app.py`
- **Execution Mode:** Headless programmatic scriptrunner
- **Coverage:** All 5 functional pages in both Presentation Mode and Research Mode

```text
Page: 01_control_tower          | Research: False | Exceptions: False | None
Page: 01_control_tower          | Research: True  | Exceptions: False | None
Page: 02_flight_intelligence    | Research: False | Exceptions: False | None
Page: 02_flight_intelligence    | Research: True  | Exceptions: False | None
Page: 03_gate_operations        | Research: False | Exceptions: False | None
Page: 03_gate_operations        | Research: True  | Exceptions: False | None
Page: 04_optimization_lab       | Research: False | Exceptions: False | None
Page: 04_optimization_lab       | Research: True  | Exceptions: False | None
Page: 05_robustness_lab         | Research: False | Exceptions: False | None
Page: 05_robustness_lab         | Research: True  | Exceptions: False | None
```
- **Verdict:** All 10 execution paths initialized, rendered, and exited cleanly with **zero unhandled Python exceptions**.

---

## 5. Test Baseline Summary Table

| Category | Suite Path | Total Tests | Passed | Failed | Skipped | Pass Rate |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Dashboard UI** | `tests/dashboard/` | 123 | 123 | 0 | 0 | **100%** |
| **P07 Pipeline** | `tests/test_native_dual_core_pipeline_p07.py` | 30 | 30 | 0 | 0 | **100%** |
| **P08 ML Validation** | `tests/test_ml_research_validation_p08.py` | 26 | 26 | 0 | 0 | **100%** |
| **P09 Monte Carlo** | `tests/test_monte_carlo_robustness_p09.py` | 33 | 33 | 0 | 0 | **100%** |
| **AppTest Smoke** | `dashboard/app.py` | 10 | 10 | 0 | 0 | **100%** |
| **Total Combined** | — | **222** | **222** | **0** | **0** | **100%** |

**Conclusion:** The test baseline is 100% green and certified as the regression anchor for all subsequent UI redesign phases.
