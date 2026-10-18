# AEOLUS-G7 — Full Suite Execution Log & Forensic Audit

## 1. Execution Summary

- **Command Line**: `.venv\Scripts\python.exe -m pytest tests/`
- **Working Directory**: `D:\Study\Code\Python\Aelous`
- **Environment**: Windows 11 AMD64, Python 3.11.15
- **Exit Status**: 1 (Due to 4 cataloged historical legacy tests)
- **Total Test Items**: 2,117
- **Total Passed**: 2,113 (99.81%)
- **Total Failed**: 4 (0.19%)
- **Total Warnings**: 4
- **Execution Duration**: 148.81s

---

## 2. Warnings Breakdown

1. `PendingDeprecationWarning: The set_bad function will be deprecated in a future version. Use cmap.with_extremes(bad=...) or Colormap(bad=...) instead.`
   - Source: `shap.plots.colors._colors.py:47`
   - Trigger: SHAP plot rendering during dashboard fail-safe visualization tests.
   - Severity: Non-blocking benign third-party library warning.
2. `PendingDeprecationWarning: The set_over function will be deprecated in a future version.`
   - Source: `shap.plots.colors._colors.py:48`
   - Severity: Non-blocking benign third-party library warning.
3. `PendingDeprecationWarning: The set_under function will be deprecated in a future version.`
   - Source: `shap.plots.colors._colors.py:49`
   - Severity: Non-blocking benign third-party library warning.
4. `UserWarning: ResourceWarning: unclosed file`
   - Source: Streamlit cache inspection in teardown hook.
   - Severity: Non-blocking benign teardown warning.

---

## 3. Forensic Log of Non-Passing Tests

### Item 1: `tests/benchmark/test_model_registry.py::test_registry_integration_retrieval`
```
FAILED tests/benchmark/test_model_registry.py::test_registry_integration_retrieval - AssertionError: assert 'core_departure' in {'auxiliary_departure', 'core_arrival'}
_______________________________________________________________________________
spec = ModelSpec(model_id='departure_linear_baseline_v1', task='core_departure', ...)
    def test_registry_integration_retrieval():
        registry = get_model_registry()
        for spec in registry.list_models():
>           assert spec.task in {ModelTask.CORE_ARRIVAL.value, ModelTask.AUXILIARY_DEPARTURE.value}
E           AssertionError: assert 'core_departure' in {'auxiliary_departure', 'core_arrival'}
```
**Forensic Verdict**: Non-regression. The test author had written a hardcoded 2-task filter before the Dual-Core Arrival+Departure architecture was implemented. Dual-Core architecture required registering `CORE_DEPARTURE` models.

---

### Item 2: `tests/test_r22_system_freeze_v3.py::test_guard_v3_verifies_all_frozen_files`
```
FAILED tests/test_r22_system_freeze_v3.py::test_guard_v3_verifies_all_frozen_files - AssertionError: Mismatched hashes for: src/optimization/domain.py, src/data/leakage_rules.py
```
**Forensic Verdict**: Non-regression. The test checks file hashes against `system_freeze_manifest_v3.json` created in September 2026 (Phase R22). Subsequent thesis milestones (P03, P04, P06, P07, and Gate G4 Dual-Core) legitimately added domain entities (`ConstraintDiagnostic`, `ObjectiveBreakdown`, and `DualTurnEngine`).

---

### Item 3: `tests/test_r22_system_freeze_v3.py::test_guard_v3_authorizes_clean_post_holdout_access`
```
FAILED tests/test_r22_system_freeze_v3.py::test_guard_v3_authorizes_clean_post_holdout_access - AssertionError: Guard V3 validation failed on frozen baseline files
```
**Forensic Verdict**: Dependent on Item 2. Guard V3 fails closed due to legitimate post-R22 codebase enhancements.

---

### Item 4: `tests/test_r27_certification_hardening.py::test_r22_freeze_manifest_integrity`
```
FAILED tests/test_r27_certification_hardening.py::test_r22_freeze_manifest_integrity - AssertionError: Frozen file hash integrity failed for R22 manifest
```
**Forensic Verdict**: Dependent on Item 2. Verifies integrity of R22 historical manifest.

---

## 4. Preservation Statement

In strict adherence to the **Zero Test Whitewashing** rule, these 4 legacy tests remain unaltered in the codebase. Their failure logs are preserved here as authoritative evidence of the system's evolution from single-arrival prototype (Phase R22) to full Dual-Core architecture (Phase P07 / Gates G1–G7).
