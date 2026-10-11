# UI-R08 Deliverable 03: Test Execution Log

**Execution Timestamp:** 2026-10-11T03:02:46+07:00  
**Environment:** Windows 11 (AMD64 / x86_64)  
**Python Runtime:** Python 3.11.15 (`D:\Study\Code\Python\Aelous\.venv\Scripts\python.exe`)  
**Core Dependencies:**
- `streamlit`: 1.65.0
- `plotly`: 7.1.0
- `pytest`: 9.1.1
- `ortools`: 9.12.4544
- `xgboost`: 2.1.4
- `pandas`: 2.2.3
- `numpy`: 2.2.3
- `scipy`: 1.15.2
- `shap`: 0.46.0

---

## 1. Suite 1: UI-R08 Acceptance Criteria Suite (`test_ui_r08_final_acceptance.py`)

### Command Executed:
```powershell
.venv\Scripts\python.exe -m pytest tests\dashboard\test_ui_r08_final_acceptance.py -v
```

### Raw Output:
```
============================= test session starts =============================
platform win32 -- Python 3.11.15, pytest-9.1.1, pluggy-1.6.0 -- D:\Study\Code\Python\Aelous\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: D:\Study\Code\Python\Aelous
configfile: pytest.ini
plugins: anyio-4.15.1
collecting ... collected 40 items

tests/dashboard/test_ui_r08_final_acceptance.py::test_r08_t01_app_startup PASSED [  2%]
tests/dashboard/test_ui_r08_final_acceptance.py::test_r08_t02_five_pages PASSED [  5%]
tests/dashboard/test_ui_r08_final_acceptance.py::test_r08_t03_presentation_mode PASSED [  7%]
tests/dashboard/test_ui_r08_final_acceptance.py::test_r08_t04_research_mode PASSED [ 10%]
tests/dashboard/test_ui_r08_final_acceptance.py::test_r08_t05_scenario_switch PASSED [ 12%]
tests/dashboard/test_ui_r08_final_acceptance.py::test_r08_t06_canonical_navigation PASSED [ 15%]
tests/dashboard/test_ui_r08_final_acceptance.py::test_r08_t07_no_solver_on_startup PASSED [ 17%]
tests/dashboard/test_ui_r08_final_acceptance.py::test_r08_t08_explicit_run_only PASSED [ 20%]
tests/dashboard/test_ui_r08_final_acceptance.py::test_r08_t09_no_filter_triggered_solve PASSED [ 22%]
tests/dashboard/test_ui_r08_final_acceptance.py::test_r08_t10_stale_detection PASSED [ 25%]
tests/dashboard/test_ui_r08_final_acceptance.py::test_r08_t11_scenario_identity PASSED [ 27%]
tests/dashboard/test_ui_r08_final_acceptance.py::test_r08_t12_no_fake_kpi PASSED [ 30%]
tests/dashboard/test_ui_r08_final_acceptance.py::test_r08_t13_no_fake_metadata PASSED [ 32%]
tests/dashboard/test_ui_r08_final_acceptance.py::test_r08_t14_no_actual_leakage PASSED [ 35%]
tests/dashboard/test_ui_r08_final_acceptance.py::test_r08_t15_model_provenance PASSED [ 37%]
tests/dashboard/test_ui_r08_final_acceptance.py::test_r08_t16_aircraft_turn_pairing PASSED [ 40%]
tests/dashboard/test_ui_r08_final_acceptance.py::test_r08_t17_buffer_enforcement PASSED [ 42%]
tests/dashboard/test_ui_r08_final_acceptance.py::test_r08_t18_cross_midnight PASSED [ 45%]
tests/dashboard/test_ui_r08_final_acceptance.py::test_r08_t19_apron_classification PASSED [ 47%]
tests/dashboard/test_ui_r08_final_acceptance.py::test_r08_t20_pooled_remote_capacity PASSED [ 50%]
tests/dashboard/test_ui_r08_final_acceptance.py::test_r08_t21_independent_verifier PASSED [ 52%]
tests/dashboard/test_ui_r08_final_acceptance.py::test_r08_t22_solver_status PASSED [ 55%]
tests/dashboard/test_ui_r08_final_acceptance.py::test_r08_t23_fallback_provenance PASSED [ 57%]
tests/dashboard/test_ui_r08_final_acceptance.py::test_r08_t24_fair_benchmark PASSED [ 60%]
tests/dashboard/test_ui_r08_final_acceptance.py::test_r08_t25_p06_unknown PASSED [ 62%]
tests/dashboard/test_ui_r08_final_acceptance.py::test_r08_t26_mc_solver_grouping PASSED [ 65%]
tests/dashboard/test_ui_r08_final_acceptance.py::test_r08_t27_mc_scenario_count PASSED [ 67%]
tests/dashboard/test_ui_r08_final_acceptance.py::test_r08_t28_mode_a_feasibility_conflict PASSED [ 70%]
tests/dashboard/test_ui_r08_final_acceptance.py::test_r08_t29_mode_c_greedy_limitation PASSED [ 72%]
tests/dashboard/test_ui_r08_final_acceptance.py::test_r08_t30_paired_statistics PASSED [ 75%]
tests/dashboard/test_ui_r08_final_acceptance.py::test_r08_t31_cvar_ci PASSED [ 77%]
tests/dashboard/test_ui_r08_final_acceptance.py::test_r08_t32_research_inspector_truthfulness PASSED [ 80%]
tests/dashboard/test_ui_r08_final_acceptance.py::test_r08_t33_missing_artifact_handling PASSED [ 82%]
tests/dashboard/test_ui_r08_final_acceptance.py::test_r08_t34_invalid_configuration PASSED [ 85%]
tests/dashboard/test_ui_r08_final_acceptance.py::test_r08_t35_cache_isolation PASSED [ 87%]
tests/dashboard/test_ui_r08_final_acceptance.py::test_r08_t36_export_provenance PASSED [ 90%]
tests/dashboard/test_ui_r08_final_acceptance.py::test_r08_t37_offline_startup PASSED [ 92%]
tests/dashboard/test_ui_r08_final_acceptance.py::test_r08_t38_browser_visual_acceptance PASSED [ 95%]
tests/dashboard/test_ui_r08_final_acceptance.py::test_r08_t39_responsive_display PASSED [ 97%]
tests/dashboard/test_ui_r08_final_acceptance.py::test_r08_t40_defense_rehearsal PASSED [100%]

======================= 40 passed, 3 warnings in 5.12s ========================
```
**Exit Code:** 0

---

## 2. Suite 2: Comprehensive Dashboard Regression Suite (`tests/dashboard/`)

### Command Executed:
```powershell
.venv\Scripts\python.exe -m pytest tests\dashboard\ -q
```

### Raw Output:
```
........................................................................ [ 20%]
........................................................................ [ 40%]
........................................................................ [ 60%]
........................................................................ [ 80%]
.......................................................................  [100%]
============================== warnings summary ===============================
tests/dashboard/test_foundation.py::test_p10b_16_preflight_handles_missing_optional_artifacts
  D:\Study\Code\Python\Aelous\.venv\Lib\site-packages\shap\plots\colors\_colors.py:47: PendingDeprecationWarning: The set_bad function will be deprecated in a future version. Use cmap.with_extremes(bad=...) or Colormap(bad=...) instead.
    red_blue.set_bad(gray_rgb.tolist(), 1.0)
359 passed, 3 warnings in 9.41s
```
**Exit Code:** 0

---

## 3. Suite 3: Research Pipeline & Remediation Regression Suite

### Command Executed:
```powershell
.venv\Scripts\python.exe -m pytest tests\test_native_dual_core_pipeline_p07.py tests\test_ml_research_validation_p08.py tests\test_monte_carlo_robustness_p09.py -q
```

### Raw Output:
```
........................................................................ [ 80%]
.................                                                        [100%]
89 passed, 3 warnings in 7.28s
```
**Exit Code:** 0

---

## 4. Suite 4: Operations Research & Scalability Regression Suite

### Command Executed:
```powershell
.venv\Scripts\python.exe -m pytest tests\test_r34_p5_mathematical_audit.py tests\test_r35_solver_repro.py tests\test_sa_hybrid_correctness_p03.py tests\test_scalability_benchmark.py -q
```

### Raw Output:
```
.................................................................        [100%]
65 passed in 7.73s
```
**Exit Code:** 0

---

## 5. Summary Execution Metrics

| Test Suite Category | Test Files | Total Tests | Passed | Failed | Duration | Exit Code |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| UI-R08 Acceptance Criteria | 1 | 40 | 40 | 0 | 5.12s | 0 |
| Dashboard Unit & Integration | 14 | 359 | 359 | 0 | 9.41s | 0 |
| Research Pipeline (P07-P09) | 3 | 89 | 89 | 0 | 7.28s | 0 |
| Backend OR & Scalability | 4 | 65 | 65 | 0 | 7.73s | 0 |
| **Consolidated Total** | **21** | **513** | **513** | **0** | **~24.4s** | **0** |
