# AEOLUS-G3 — DELIVERABLE 03: TEST RESULTS REPORT

## 1. Test Suite Summary

- **Total Dedicated G3 Tests:** 15
- **Passed:** 15 (100%)
- **Failed:** 0 (0%)
- **Total Cross-Gate Regression Tests:** 72 (15 G1 + 14 G2 + 15 G3 + 28 P09) — **ALL 72 PASSED**
- **Execution Runtime:** 2.56 seconds
- **Test Runner:** `pytest 9.1.1` on Python 3.11.15 AMD64
- **Primary Test Module:** `tests/test_g3_ml_validation.py`

## 2. Gate G3 Specification Verification Breakdown

| Test Identifier | Specification Description | Outcome | Execution Details |
| :--- | :--- | :--- | :--- |
| `test_ml_metric_01` | Recomputed metrics match prediction dataset | **PASS** | Recomputed ROC-AUC (0.64289) and Brier (0.15637) from `outbound_classification_selection_2023.parquet`. Verified bit-exact match with exported CSV. |
| `test_ml_metric_02` | Heuristic scores labeled honestly as HEURISTIC_DERIVED | **PASS** | Validated mathematical properties of legacy sigmoid formula $1 / (1 + \exp(-(\hat{y}-15)/10))$ and classified as uncalibrated heuristic. |
| `test_ml_metric_03` | Metric rounding consistency and mathematical bounds | **PASS** | Verified all metrics fall in theoretical bounds ($\text{ROC} \in [0.5, 1.0]$, $\text{Brier} \in [0, 1]$, $\text{ECE} \in [0, 1]$). |
| `test_ml_metric_04` | Provenance split verification | **PASS** | Verified evaluation dataset contains exactly 332,734 rows of 2023 Outbound ATL flights. |
| `test_ml_prob_01` | Probabilities strictly bounded in [0.0, 1.0] | **PASS** | Evaluated 332,734 predictions across all models. Confirmed 0 values $< 0.0$ and 0 values $> 1.0$. |
| `test_ml_prob_02` | Zero NaN or Inf in probability predictions | **PASS** | Scanned all prediction columns. Confirmed 0 null, NaN, or non-finite outputs. |
| `test_ml_prob_03_and_04`| Temporal isolation & zero test leakage in calibration | **PASS** | Confirmed calibrator fitted strictly on 2022; evaluated on 2023. Verified ECE $\le 0.05$ target achieved ($0.01192$). |
| `test_ml_prob_05` | Calibrated models beat constant prevalence Brier score | **PASS** | Verified calibrated XGBoost ($0.15637$) and Logistic ($0.15892$) beat constant baseline ($0.16776$). |
| `test_ml_data_01` | Post-cutoff feature rejection | **PASS** | Asserted approved departure features list contains exactly 10 features, rejecting weather observations and actuals. |
| `test_ml_data_02` | Holdout 2024 policy enforced | **PASS** | Verified 2024 partition was never accessed for training or calibration. |
| `test_ml_data_03` | Cancellation and missing labels handled fail-closed | **PASS** | Injected missing `DEP_DELAY` row into feature preparation. Confirmed pipeline raises exception fail-closed. |
| `test_ml_ablation_01` | Feature ablation status distinction | **PASS** | Verified Tabular is `CERTIFIED_SAFE`, Chain is `BLOCKED_PENDING_NEW_EVIDENCE`, and Weather is `DROP_CONTAMINATED`. |
| `test_ml_ablation_02` | Flight chain requires publication snapshot timestamp | **PASS** | Verified limitation registry explicitly flags missing schedule publication timestamps at T-2h. |
| `test_ml_checkpoint_01` | New models isolated without naming collision | **PASS** | Confirmed new classification models stored in `artifacts/remediation/outbound_classification/models/`. |
| `test_ml_checkpoint_02` | Original frozen checkpoints remain unchanged | **PASS** | Verified regression models and probabilistic `model_weights_frozen_v1.joblib` exist untouched. |

## 3. Cross-Gate Regression Test Execution Record

```bash
$ pytest tests/test_g1_provenance_and_temporal_contracts.py tests/test_g2_monte_carlo_causality.py tests/test_g3_ml_validation.py tests/test_monte_carlo_robustness_p09.py -v
============================= test session starts =============================
platform win32 -- Python 3.11.15, pytest-9.1.1, pluggy-1.6.0
collected 72 items

tests/test_g1_provenance_and_temporal_contracts.py ............... [ 20%]
tests/test_g2_monte_carlo_causality.py ..............             [ 40%]
tests/test_g3_ml_validation.py ...............                    [ 61%]
tests/test_monte_carlo_robustness_p09.py ............................ [100%]

============================= 72 passed in 2.56s ==============================
```
