# AEOLUS-G7 — Scope and Baseline Report

## 1. Executive Summary

- **Gate ID**: `AEOLUS-G7`
- **Gate Name**: Full Regression, Scientific Invariants & Reproducibility Validation
- **Branch**: `remediation/g7-regression`
- **Target Platform**: Windows 11 AMD64, Python 3.11.15 (`.venv\Scripts\python.exe`)
- **Execution Date**: 2026-10-11
- **Role**: Principal QA Architect, Scientific Software Verification Engineer, MLOps Reliability Engineer, Release Test Lead

Gate AEOLUS-G7 serves as the comprehensive synthesis, regression validation, and reproducibility audit gate across the entire remediation lifecycle (G0 through G6). Its mandate is to verify that remediation enhancements across data provenance (G1), causal Monte Carlo simulation (G2), machine learning empirical evidence (G3), native real-data flight pairing (G4), solver correctness and fair benchmarking (G5), and scientific dashboard presentation (G6) have not introduced silent regressions, corrupted historical checkpoints, violated metamorphic invariants, or degraded system determinism.

---

## 2. Test Scope Taxonomy

The test landscape of Aeolus Gate Optimization is divided into six distinct, mutually auditable evaluation scopes:

| Scope ID | Scope Name | Path / Filter | Collected Items | Objective & Description |
|:---|:---|:---|:---:|:---|
| **SCOPE-1** | Full Repository Test Suite | `tests/` | 2,117 | Complete regression across legacy and remediated test bases. |
| **SCOPE-2** | Remediation Test Suite (G1–G7) | `tests/test_g*.py` | 127 | Targeted verification of remediation contracts, causal algorithms, and scientific invariants. |
| **SCOPE-3** | Dashboard Acceptance Suite | `tests/dashboard/` | 359 | Visual QA, view models, contract mapping, and UI fail-safe behaviors. |
| **SCOPE-4** | Research Validation (P07–P09) | `tests/test_*_p0[789]*.py` | 89 | Academic protocol compliance for native dual-core, ML research, and Monte Carlo. |
| **SCOPE-5** | Core Invariants & Metamorphic | `tests/test_g7_scientific_invariants.py` | 15 | Formal verification of INV-01..10 and end-to-end integration flows FLOW-A..E. |
| **SCOPE-6** | Deterministic Reproducibility | `scripts/verify_reproducibility_g7.py` | 6 workloads | Multi-run bitwise and numeric parity on representative workloads. |

---

## 3. Pre-Remediation Baseline Comparison (G0 vs G7)

At the inception of the remediation lifecycle (Gate G0 baseline):
- **Collected Test Items**: 1,990 test items in historical inventory.
- **Passing Status**: Reported historically, but untested against remediated strict schemas.
- **Dual-Core Architecture**: P07 lacked verified physical pairing (30 synthetic turns, 0 verified turns).
- **Monte Carlo Protocol**: P09 Mode B suffered from hindsight information leakage; Mode C lacked optimality proof verification.
- **Machine Learning**: Outbound delay prediction lacked probabilistic models (`P(delay >= 15m)`) and was limited to heuristic thresholding.
- **Solvers**: Benchmark had mismatched time horizons and unproven heuristic bounds labeled as oracle optimums.
- **Dashboard**: Had synthetic-to-real data leakage risks and unproven "OPTIMAL" labeling on timed-out runs.

At Gate G7 synthesis:
- **Total Collected Tests**: 2,117 tests (+127 remediation and invariant tests added).
- **Remediation Suite**: 127 / 127 tests passing (100% pass rate).
- **Dashboard Suite**: 359 / 359 tests passing (100% pass rate).
- **Research Suite (P07–P09)**: 89 / 89 tests passing (100% pass rate).
- **Scientific Invariants**: 15 / 15 tests passing (100% pass rate).
- **Full Suite**: 2,113 / 2,117 tests passing (99.81% pass rate). Forensic analysis confirms the 4 remaining failures stem exclusively from historical intermediate freeze manifests from September 2026 prior to dual-core expansion.

---

## 4. Environment & Execution Specifications

- **Python Runtime**: Python 3.11.15 (tags/v3.11.15:dd7bc88, Dec 3 2025, AMD64)
- **Virtual Environment**: `D:\Study\Code\Python\Aelous\.venv`
- **Key Dependencies**:
  - `pytest`: 9.1.1
  - `ortools`: 9.11.4210
  - `numpy`: 1.26.4
  - `pandas`: 2.2.3
  - `scipy`: 1.14.1
  - `scikit-learn`: 1.5.2
  - `xgboost`: 2.1.2
  - `streamlit`: 1.39.0
  - `shap`: 0.46.0
- **Execution Constraints Enforced**:
  - `Zero Test Whitewashing`: No tests were edited to hide bugs, no tests were silently skipped or xfailed.
  - `Zero Checkpoint Overwrite`: Historical checkpoints in `artifacts/models/` remain read-only.
  - `Deterministic Seeds`: All stochastic components pinned to explicit seeds (`seed=42`, `seed=202601`).
