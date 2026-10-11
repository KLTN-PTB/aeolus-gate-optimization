# AEOLUS DASHBOARD — RESEARCH INSPECTOR SCIENTIFIC SPECIFICATION
**Phase**: UI-R07 v2.0  
**Implementation**: `dashboard/components/research_inspector.py`  

---

## 1. Role & Elimination of Unverified Claims

The **Research Inspector** serves as the cross-page scientific audit drawer. In prior prototypes, several fields defaulted to unsubstantiated positive assertions (e.g. `"status": "VERIFIED"`, `"target_leakage_status": "PASSED"`, `"diagnostics": "ALL_CHECKS_CLEAN"`).

Phase UI-R07 enforces **scientific skepticism by design**:
- Unless explicit, machine-validated verification evidence is supplied in `metadata`, the default status of every audit check is **`NOT_CHECKED`** (or **`CHƯA KIỂM ĐỊNH`**).
- No self-certification of perfection without active verifier execution.

---

## 2. Five Structured Auditing Tabs

1. **Tab 1: Experiment Provenance**:
   - `experiment_id`, `scenario_id`, `scenario_hash` (truncated SHA-256).
   - Data source (`BTS_AIRLINE_ONTIME_ATL_2023`), cutoff rule (`T-2H_SCHEDULED_GATE_IN`).
   - Registered solver configuration payload.
2. **Tab 2: Validation & Diagnostics**:
   - Independent Verifier status (Defaults to `NOT_CHECKED`).
   - Target Leakage Audit status (Defaults to `NOT_CHECKED`).
   - 2024 Holdout Quarantine status (Defaults to `NOT_CHECKED`).
3. **Tab 3: Artifact Inspector**:
   - Relative paths to all linked artifacts.
   - Status defaults to `NOT_CHECKED`.
   - Sanitized JSON payload inspection with download button.
4. **Tab 4: Scientific Protocol**:
   - Explicit definitions of the 3 Monte Carlo modes.
   - Highlighting Finding D1 (Mode A feasibility vs conflict) and Finding D2 (Mode B vs C shared Greedy implementation).
5. **Tab 5: Reproducibility**:
   - Exact CLI commands to reproduce P07, P09, and dashboard test suites.
   - Runtime dependencies and git branch pointer.

---

## 3. Privacy & Sanitization Protocols

The function `sanitize_provenance_data` guarantees:
- All Windows drive letters (`D:\...`, `C:\...`) and local home directory paths (`/home/...`, `/Users/...`) are stripped or redacted.
- Sensitive environment tokens (`token`, `secret`, `password`, `api_key`, `credentials`) are redacted with `[REDACTED_SECRET]`.
