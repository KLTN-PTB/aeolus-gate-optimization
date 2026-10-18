# AEOLUS-G6: Security Validation & Vulnerability Audit Report

**Gate Identifier:** `AEOLUS-G6`  
**Gate Title:** Dashboard Scientific Integrity, Runtime Validation & Visual QA  
**Audit Date:** 2026-10-11  
**Target Branch:** `remediation/g6-dashboard`  

---

## 1. Threat Modeling for Scientific Web Applications

Web dashboards that interface with file systems, ML model weights, and optimization solvers present distinct security and integrity attack vectors:
1. **Arbitrary File Access & Path Traversal:** Attackers injecting relative path sequences (`../`) through scenario selectors or file upload parameters.
2. **Directory Prefix Spoofing:** Sibling directories mimicking allowlist names (e.g. `artifacts/models_untrusted/` matching prefix `artifacts/models`).
3. **Execution of Untrusted Model Checkpoints:** Loading malicious pickled model weights from unauthorized directories.
4. **Target Data Leakage:** Accidental leakage of ground-truth future target variables through CSV export mechanisms.
5. **Denial-of-Service via Computational Exhaustion:** Triggering combinatorial solvers in unconstrained loops on page load.

---

## 2. Security Controls & Technical Implementations

### 2.1. Canonical Path Containment vs Substring Prefix Matching
In `dashboard/core/config.py`, naive prefix checking was replaced by **canonical path containment**:

```python
# Before remediation (VULNERABLE):
rel_posix = path.resolve().relative_to(self.project_root).as_posix()
return any(rel_posix.startswith(allowed) for allowed in self.ALLOWED_ARTIFACT_DIRS)

# After remediation (HARDENED):
def is_path_allowlisted(self, path: Path) -> bool:
    try:
        resolved = path.resolve()
        for allowed in self.ALLOWED_ARTIFACT_DIRS:
            allowed_path = (self.project_root / allowed).resolve()
            if resolved == allowed_path or allowed_path in resolved.parents:
                return True
        return False
    except (ValueError, RuntimeError):
        return False
```

**Verification Results:**
- `Path("../../etc/passwd")` -> **REJECTED (False)**
- `Path("artifacts/models_evil/trojan.pkl")` -> **REJECTED (False)**
- `Path("artifacts/models/p4_arrival_ngboost/model.pkl")` -> **ACCEPTED (True)**
- Verified by unit tests `test_ui_sec_01_path_traversal_rejection` and `test_ui_sec_02_invalid_model_path_rejection`.

### 2.2. Model Directory Whitelisting
The configuration enforces a strict allowlist of authorized model directories:
- `artifacts/models/`
- `artifacts/remediation/`
- `artifacts/p08_validation/`
- `data/processed/`

Any attempt to point the dashboard's model loader to an arbitrary directory (e.g., `C:/Windows/System32` or `/tmp/malicious_models`) raises an authorization fault and triggers graceful preflight failure.

### 2.3. Zero-Target-Leakage in Export Adapters
In `dashboard/adapters/export_adapter.py`:
- Before serializing any gate allocation table or benchmark result to CSV, `ScientificValidator.check_prediction_data_leakage(list(df.columns))` inspects all column headers against forbidden ground-truth tokens:
  * `ARR_DELAY`, `DEP_DELAY`, `ARR_DELAY_NEW`, `DEP_DELAY_NEW`, `ACTUAL_ELAPSED_TIME`
- Attempting to export a dataframe containing any of these columns throws a `DataLeakageError`, preventing accidental empirical contamination.

### 2.4. Computational Denial-of-Service Protection
- Solvers are never executed automatically upon page entry, scenario switching, or filter modification.
- Optimization requires an explicit user action (`st.button("Chạy Phân Cổng CP-SAT")`).
- Solvers enforce a strict 30-second time budget (`time_limit_sec = 30.0`), preventing unconstrained CPU utilization or server hang.

---

## 3. Summary of Security Verification Tests

| Security Test Case | Target Invariant | Implementation Test | Outcome |
|:---|:---|:---|:---:|
| `SEC-01` | Path traversal rejection | `test_ui_sec_01_path_traversal_rejection` | **PASSED** |
| `SEC-02` | Prefix spoofing & untrusted model rejection | `test_ui_sec_02_invalid_model_path_rejection` | **PASSED** |
| `SEC-03` | Target delay leakage barrier | `ScientificValidator.check_prediction_data_leakage` | **PASSED** |
| `SEC-04` | Unsolicited solve prevention | `test_ui_solver_01_manual_trigger_only` | **PASSED** |

All security controls are verified and operational.
