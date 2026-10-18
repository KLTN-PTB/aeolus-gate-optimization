# AEOLUS-G7 — Test Scope Inventory and Reconciliation Report

## 1. Inventory Reconciliation Overview

To resolve discrepancies between historical audit logs (e.g. 1,990 collected items in historical G0 audit, 359 dashboard tests, 89 research tests) and current execution numbers, this document provides an item-level inventory reconciliation across all test scopes in `tests/`.

---

## 2. Test File & Directory Inventory

| Category / Subdirectory | Number of Files | Total Collected Items | Active Status | Pass Count | Fail Count |
|:---|:---:|:---:|:---|:---:|:---:|
| **Root Unit & Integration Tests** (`tests/test_*.py`) | 39 | 1,228 | Active | 1,225 | 3 |
| **Dashboard Test Suite** (`tests/dashboard/`) | 14 | 359 | Active | 359 | 0 |
| **Optimization & Benchmark Tests** (`tests/benchmark/`, `tests/optimization/`) | 8 | 172 | Active | 171 | 1 |
| **Simulation & Turn Tests** (`tests/simulation/`, `tests/pairing/`) | 6 | 134 | Active | 134 | 0 |
| **Data & Feature Pipeline Tests** (`tests/data/`, `tests/features/`) | 7 | 97 | Active | 97 | 0 |
| **Remediation Test Suites** (`tests/test_g*.py`) | 7 | 127 | Active | 127 | 0 |
| **Total Repository Active Test Base** | **81** | **2,117** | **Active** | **2,113** | **4** |

---

## 3. Reconciliation with Historical Audits

1. **Baseline Inception (Gate G0)**:
   - Historical count: 1,990 collected tests.
   - At the start of remediation, the suite contained 1,990 active tests without the dedicated G1–G7 remediation verification suites.
2. **Remediation Phase Additions (G1 through G7)**:
   - G1 Data Provenance: +22 tests (`test_g1_provenance_and_temporal_contracts.py`)
   - G2 Monte Carlo: +24 tests (`test_g2_monte_carlo_causality.py`)
   - G3 ML Validation: +14 tests (`test_g3_ml_validation.py`)
   - G4 Native Dual-Core E2E: +19 tests (`test_g4_native_e2e.py`)
   - G5 Solver Correctness: +21 tests (`test_g5_solver_correctness.py`)
   - G6 Dashboard Integrity: +12 tests (`test_g6_dashboard_integrity.py`)
   - G7 Scientific Invariants: +15 tests (`test_g7_scientific_invariants.py`)
   - **Net Remediation Additions**: **+127 tests**.
3. **Reconciled Equation**:
   $$1,990 \text{ (historical baseline)} + 127 \text{ (remediation G1--G7)} = 2,117 \text{ (current active collection)}$$
   The arithmetic matches with exact item-level precision.

---

## 4. Test Category Mapping & Execution Times

| Scope Code | Scope Description | Pytest Target | Items | Wall-Clock Time |
|:---|:---|:---|:---:|:---:|
| `SCOPE_REM` | Remediation Gates G1–G7 | `tests/test_g*.py` | 127 | 24.16s |
| `SCOPE_INV` | Scientific Invariants & Flows | `tests/test_g7_scientific_invariants.py` | 15 | 1.30s |
| `SCOPE_DASH`| Dashboard Acceptance | `tests/dashboard/` | 359 | 8.91s |
| `SCOPE_RES` | Research Protocols P07–P09 | `tests/test_*_p0[789]*.py` | 89 | 6.21s |
| `SCOPE_ALL` | Full Pytest Suite | `tests/` | 2,117 | 148.81s |
