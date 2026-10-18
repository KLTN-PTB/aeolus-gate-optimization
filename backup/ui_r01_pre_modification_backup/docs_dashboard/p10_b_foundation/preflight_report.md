# Aeolus Dashboard Preflight Inspection Report

**Document ID:** `AEOLUS-P10-B-PREFLIGHT-REPORT`  
**Phase:** P10-B (Dashboard Foundation, Data Contracts & Safe Integration)  
**Inspection Date:** 2026-10-09  
**Execution Environment:** Python 3.11.15 Virtualenv (`.venv`) on Windows AMD64  
**Inspection Engine:** `PreflightService.run_preflight_checks()`  

---

## 1. Executive Summary

Prior to launching the interactive demonstration application, the **Preflight Service** executed an automated diagnostic scan verifying Python package versions, model check validity, artifact persistence, and scientific anti-leakage isolation.

### Readiness Scores:
- **System Overall Health:** **HEALTHY (100% Passed)**
- **Presentation Mode Readiness:** **READY**
- **Research Mode Readiness:** **READY**
- **Live Solving Engine (CP-SAT):** **OPERATIONAL**

---

## 2. Diagnostic Inspection Checklist

| Category | Diagnostic Check Name | Expected Condition | Observed State | Severity | Verdict |
| :--- | :--- | :--- | :--- | :---: | :---: |
| **Dependencies** | Python Interpreter | Python 3.11+ | Python 3.11.15 AMD64 | Critical | **PASS** |
| **Dependencies** | `streamlit` | $\ge 1.30.0$ | `streamlit==1.65.0` | Critical | **PASS** |
| **Dependencies** | `plotly` | $\ge 5.18.0$ | `plotly==7.1.0` | Critical | **PASS** |
| **Dependencies** | `ortools` | $\ge 9.0.0$ | `ortools==9.15.6755` | Critical | **PASS** |
| **Dependencies** | `xgboost` | $\ge 2.0.0$ | `xgboost==3.2.0` | Critical | **PASS** |
| **Dependencies** | `pandas` | $\ge 2.0.0$ | `pandas==2.3.3` | Critical | **PASS** |
| **Dependencies** | `numpy` | $\ge 1.24.0$ | `numpy==2.2.6` | Critical | **PASS** |
| **Dependencies** | `scipy` | $\ge 1.10.0$ | `scipy==1.17.1` | Critical | **PASS** |
| **Dependencies** | `shap` | $\ge 0.40.0$ | `shap==0.51.0` | Advisory | **PASS** |
| **Artifacts** | `statistical_summary.json` | File exists | `artifacts/remediation/monte_carlo/statistical_summary.json` (8.4 KB) | Critical | **PASS** |
| **Artifacts** | `fixed_plan_results.csv` | File exists | `artifacts/remediation/monte_carlo/fixed_plan_results.csv` (215.9 KB) | Critical | **PASS** |
| **Artifacts** | `recourse_results.csv` | File exists | `artifacts/remediation/monte_carlo/recourse_results.csv` (207.5 KB) | Critical | **PASS** |
| **Artifacts** | `solver_runs.csv` | File exists | `artifacts/remediation/benchmarks/solver_runs.csv` (20.4 KB) | Critical | **PASS** |
| **Artifacts** | `regression_metrics.csv` | File exists | `artifacts/remediation/ml_validation/regression_metrics.csv` (1.6 KB) | Advisory | **PASS** |
| **Artifacts** | `solver_results.parquet` | File exists | `artifacts/stress_1500x50/solver_results.parquet` (15.0 KB) | Advisory | **PASS** |
| **Governance** | 2024 Holdout Seal | Quarantined | Year 2024 completely excluded from scenario registry | Critical | **PASS** |
| **Engine** | CP-SAT Live Solver | Callable | Google OR-Tools CP-SAT sparse interval model solver verified | Critical | **PASS** |

---

## 3. Graceful Degradation & Fault Tolerance Rules

The `PreflightService` enforces the following fault tolerance rules:
1. **Critical Failure:** If any critical package (`streamlit`, `plotly`, `ortools`) or core artifact (`statistical_summary.json`) is missing, the application renders an explicit diagnostic error card and halts startup cleanly without unhandled Python stack traces.
2. **Advisory Failure:** If an advisory artifact is missing (e.g., `solver_results.parquet` for 1,500 flights or `shap`), the application launches successfully into Presentation Mode, and automatically disables the specific research tab/expander with an informative explanation:
   > *"Mô-đun Khảo sát Khả năng Mở rộng 1,500 chuyến bay tạm thời vô hiệu hóa do thiếu tệp artifact. Các chức năng khác của hệ thống vẫn hoạt động bình thường."*

---

## 4. Verification Command
To reproduce this preflight inspection report at any time:
```bash
.\.venv\Scripts\python.exe -m pytest tests/dashboard/test_services.py -k test_preflight_service_full_report -v
```
