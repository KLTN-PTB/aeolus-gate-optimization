# UI-R00: 01 — REPOSITORY BASELINE & SYSTEM ENVIRONMENT

**Document ID:** `AEOLUS-UI-R00-01-BASELINE`  
**Phase:** UI-R00 (Baseline, Technical Audit & Safety Freeze)  
**Audit Timestamp:** 2026-10-10T23:25:00+07:00  
**Auditor:** Principal Software Auditor & Senior System QA Lead  
**Audit Mode:** Read-Only Technical Audit (Strictly Zero Mutations to Source)

---

## 1. Executive Summary

This document establishes the official repository baseline, dependency topology, git working tree state, and environment configuration for the Aeolus Gate Optimization project prior to the UI redesign sequence (UI-R01 through UI-R08).

All observations recorded herein represent empirical measurements executed directly against the local runtime environment on `2026-10-10`.

---

## 2. Repository & Version Control Status

| Parameter | Observed State | Notes / Context |
| :--- | :--- | :--- |
| **Repository Root** | `D:\Study\Code\Python\Aelous` | Absolute project path |
| **Current Branch** | `development/scalability-1500x50` | Active working branch |
| **HEAD Commit** | `223f0dd` | `feat(p06): CP-SAT formulation optimization, oracle parity, and independent verification` |
| **Previous Commits** | `8cf96b9`, `bd70ca8`, `aa4c19d`, `0783ba2` | P00–P06 commits |
| **Working Tree Dirty** | **YES** | Pre-existing modifications present |
| **Tracked Modified Files** | `src/optimization/adapter.py` | Import type-checking cleanup only |
| **Untracked Directories** | `dashboard/`, `docs/dashboard/`, `docs/dashboard_discovery/`, `tests/dashboard/`, `artifacts/remediation/` | Implemented during Phase P10 |
| **Untracked Files** | `README_DASHBOARD.md`, `requirements-dashboard.txt`, P07-P09 test scripts | Preserved intact |

### 2.1. Git Working Tree Separation
Per UI-R00 safety rules, no destructive operations (`git reset --hard`, `git clean -fd`) were executed.
- **Pre-existing changes:** The uncommitted dashboard implementation and P07–P09 scripts remain completely isolated and intact.
- **Phase UI-R00 additions:** Restricted strictly to `docs/dashboard/redesign/UI-R00/`.

---

## 3. Python Runtime & Environment Baseline

| Component | Detected Version | Target Specification | Status |
| :--- | :--- | :--- | :---: |
| **Python** | `3.11.15` (AMD64, MSC v.1944) | Python 3.11+ | **PASS** |
| **Operating System** | `Windows-10-10.0.19045-SP0` | Windows 10/11 | **PASS** |
| **Streamlit** | `1.65.0` | Streamlit 1.30+ | **PASS** (Deprecation notes logged) |
| **Plotly** | `7.1.0` | Plotly 5.18+ | **PASS** |
| **Google OR-Tools** | `9.15.6755` | OR-Tools 9.8+ | **PASS** |
| **Pandas** | `2.3.3` | Pandas 2.0+ | **PASS** |
| **NumPy** | `2.4.4` | NumPy 1.24+ | **PASS** |
| **SciPy** | `1.17.1` | SciPy 1.10+ | **PASS** |
| **Pydantic** | `2.12.5` | Pydantic 2.0+ | **PASS** |
| **XGBoost** | `3.2.0` | XGBoost 1.7+ | **PASS** |
| **SHAP** | `0.51.0` | SHAP 0.44+ | **PASS** |
| **Pytest** | `9.1.1` | Pytest 8.0+ | **PASS** |
| **Psutil** | `7.2.2` | Process monitoring | **PASS** |

### 3.1. Browser Automation Tools
- `playwright`: **NOT INSTALLED**
- `selenium`: **NOT INSTALLED**
- `puppeteer`: **NOT INSTALLED**
- **Impact:** Direct automated browser screenshot capture is blocked; visual audit operates under `VISUAL_QA_BLOCKED` protocol.

---

## 4. Current Dashboard Architecture & Entrypoint

- **Main Entrypoint:** [`dashboard/app.py`](file:///D:/Study/Code/Python/Aelous/dashboard/app.py)
- **Execution Command:** `.\.venv\Scripts\streamlit.exe run dashboard/app.py`
- **Application Structure:**
  - [`dashboard/core/`](file:///D:/Study/Code/Python/Aelous/dashboard/core): Configuration, dataclass contracts, state registry, validation rules.
  - [`dashboard/services/`](file:///D:/Study/Code/Python/Aelous/dashboard/services): Scenario management, live optimization, preflight check, experiment caching.
  - [`dashboard/adapters/`](file:///D:/Study/Code/Python/Aelous/dashboard/adapters): Data mapping from disk artifacts and domain objects to UI views.
  - [`dashboard/components/`](file:///D:/Study/Code/Python/Aelous/dashboard/components): Reusable UI widgets (Styles, KPI Cards, Context Bar, Flight Inspector, Research Inspector).
  - [`dashboard/visualizers/`](file:///D:/Study/Code/Python/Aelous/dashboard/visualizers): Plotly figure builders (Gantt, Timelines, Concourse, SHAP, Pareto, Monte Carlo).
  - [`dashboard/pages/`](file:///D:/Study/Code/Python/Aelous/dashboard/pages): 5 functional pages (`page_01` to `page_05`).

---

## 5. Artifact Directories Catalog

| Directory Path | Primary Contents | Health Status |
| :--- | :--- | :---: |
| `artifacts/remediation/benchmarks/` | `solver_runs.csv` (95 runs across 4 algorithms) | VERIFIED |
| `artifacts/remediation/cp_sat/` | `formulation_comparison.json`, `scalability_results.csv` | VERIFIED |
| `artifacts/remediation/ml_validation/` | OOF regression metrics, feature importance, TreeSHAP cases | VERIFIED |
| `artifacts/remediation/monte_carlo/` | `statistical_summary.json`, `fixed_plan_results.csv`, `recourse_results.csv` | VERIFIED |
| `artifacts/remediation/native_dual_core/` | `predictions_sample.csv` (60 inbound/outbound predictions) | VERIFIED |
| `artifacts/stress_1500x50/` | Parquet datasets & solver benchmarks for 1,500-flight stress testing | VERIFIED |
| `artifacts/models/` | Model checkpoint allowlist directories | VERIFIED |
| `data/processed/` | Atlanta BTS 2023 curated training/evaluation tables | VERIFIED |

---

## 6. Existing Automated Test Baseline

- **Dashboard Specific Tests (`tests/dashboard/`):** **123 passed**, 0 failed, 3 warnings in 19.13s.
- **Regression Pipeline Tests (`tests/`):** **89 passed**, 0 failed, 3 warnings in 7.88s.
- **Combined Test Health:** **212 / 212 tests PASSED (100% pass rate)**.
- **Test Integrity Guard:** All test assertions remain untouched. No assertions were softened or modified during UI-R00.
