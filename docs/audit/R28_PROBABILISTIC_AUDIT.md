# AEOLUS V4 Task R28: Probabilistic Metric, Calibration & Dependency Audit Report

## 1. Executive Summary
Task R28 establishes rigorous mathematical boundaries, metric taxonomy, calibration evidence accounting, and exact dependency closure for the Aeolus V4 probabilistic forecasting stack:
1. **P4 NGBoost Student-T**: Confirmed as `PARAMETRIC_CONTINUOUS_DENSITY_ENABLED` with explicit parameters ($\mu, \sigma, 
u \ge 2.1$), continuous CDF, continuous PPF, continuous generative sampling, and exact continuous NLL density. Empirical calibration is formally audited and classified as **`NOT_SEPARATELY_CERTIFIED`**.
2. **P5 Quantile Regression**: Confirmed as `NON_PARAMETRIC_QUANTILE_FORECASTING_ONLY`. Continuous density, continuous CDF, continuous NLL, and analytical sampling are formally classified as **`NOT_AVAILABLE` / `NOT_SUPPORTED`**.
3. **CRPS Terminology Taxonomy**: Strictly distinguishes `exact_continuous_crps`, `exact_discrete_crps`, `crps_quantile_approximation`, and `pinball_loss`. Banned calling pinball loss "CRPS" or calling discrete approximations "exact CRPS".
4. **Dependency Closure**: Verified 10 required packages and exact frozen versions (`scipy 1.17.1`, `ngboost 0.5.11`, `lightgbm 4.7.0`, `xgboost 3.2.0`, `scikit-learn 1.9.0`, etc.).

---

## 2. Metric Comparability & Capability Matrix

| Model | Density | Quantiles | NLL | Exact Continuous CRPS | Quantile CRPS Approximation | Pinball Loss | Continuous Sampling | Calibration Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **P1 Empirical** | No | Yes | No | No | No | Yes | Yes (discrete) | `NOT_CERTIFIED` |
| **P2 Residual Gaussian** | Yes | Yes | Yes | Yes | No | Yes | Yes | `NOT_CERTIFIED` |
| **P3 NGBoost Normal** | Yes | Yes | Yes | Yes | No | Yes | Yes | `NOT_CERTIFIED` |
| **P4 NGBoost Student-T** | **Yes** | **Yes** | **Yes** | **Yes** | No | **Yes** | **Yes** | **`NOT_SEPARATELY_CERTIFIED`** |
| **P5 Quantile Regression** | **No** | **Yes** | **No** | **No** | **Yes** | **Yes** | **No** | **`NOT_APPLICABLE_DENSITY`** |

---

## 3. Forensic Calibration Audit: P4 Student-T

### Audit Findings:
1. **Absence of Empirical Calibration Evidence**: No PIT uniformity hypothesis tests, empirical interval coverage tables, or reliability curves exist for continuous Student-T density.
2. **Disambiguation from Phase B**: `phase_b_calibration_report.json` was an exploratory Platt scaling test for binary delay classification ($ARR\_DELAY \ge 15$), not continuous Student-T density.
3. **Epistemological Guardrail**: Finite NLL ($4.58$ dev, $4.63$ holdout) and competitive CRPS ($18.48$ dev, $17.65$ holdout) establish scoring rule performance, but do NOT prove empirical calibration.

### Mandatory Claim Wording Amendment:
- **Prior Claim**: *"P4 provides calibrated parametric continuous density..."*
- **Certified Amended Claim**: **`"P4 NGBoost Student-T provides a parametric continuous predictive density; empirical calibration is not separately certified."`**
- **Prohibited Phrases**: *"P4 is empirically calibrated", "P4 guarantees calibrated tail bounds"*.

---

## 4. CRPS Terminology Taxonomy

1. **`exact_continuous_crps`**: Evaluates continuous density via integral $\int (F(t) - \mathbb{I}(y \le t))^2 dt$. Applied to P4 Student-T ($17.6532$ holdout), P3 Normal, P2 Gaussian.
2. **`exact_discrete_crps`**: Closed-form computation over empirical step CDF. Applied to P1.
3. **`crps_quantile_approximation`**: Quadrature approximation from discrete quantiles $\alpha$. Applied to P5 ($16.85$ dev).
4. **`pinball_loss`**: Asymmetric piecewise linear loss $\rho_\alpha(u) = u(\alpha - \mathbb{I}(u < 0))$. Applied to P5 individual quantiles.
5. **`unsupported_label`**: Labeling pinball loss as "CRPS" without qualification or calling approximations "exact" is strictly prohibited.

---

## 5. Dependency Closure

| Package | Installed Version | Primary Role in Probabilistic Pipeline |
| :--- | :--- | :--- |
| `scipy` | `1.17.1` | Student-T & Normal CDF (`student_t.cdf`), PPF (`student_t.ppf`), standard normal CDF |
| `ngboost` | `0.5.11` | NGBoost natural gradient boosting regressors for P3 Normal and P4 Student-T |
| `lightgbm` | `4.7.0` | LightGBM quantile regression with pinball loss objective for P5 |
| `xgboost` | `3.2.0` | XGBRegressor point predictions and P2 residual uncertainty baseline |
| `scikit-learn` | `1.9.0` | Linear baseline, preprocessors, KFold cross-validation |
| `numpy` | `2.2.6` | Vectorized array math, random number generation (`standard_t`) |
| `pandas` | `2.3.3` | Inbound flight dataframes, fold slicing |
| `pyarrow` | `25.0.1` | Parquet evaluation datasets, scenario scans |
| `ortools` | `9.15.6755` | Downstream gate assignment solvers |
| `pytest` | `9.1.1` | Test validation framework |

---

## 6. Audit Verdict
- **Verdict**: **`PASS`**
- **Artifacts Created**:
  - `artifacts/audit/r28_probabilistic_capability_matrix.json`
  - `artifacts/audit/r28_metric_lineage.json`
  - `artifacts/audit/r28_calibration_evidence.json`
  - `artifacts/audit/r28_dependency_closure.json`
  - `docs/audit/R28_PROBABILISTIC_AUDIT.md`
- **Unit Test Suite**: `tests/test_r28_probabilistic_audit.py` (11 tests).
