# AEOLUS-G3 — DELIVERABLE 01: SCOPE AND BASELINE

## 1. Executive Summary & Remediation Mandate

This document establishes the official forensic scope, baseline integrity, and engineering boundaries for Gate G3: **Machine Learning Evidence, Outbound Probability & Scientific Validation**.

In legacy Phase P08 (`scripts/generate_p08_validation_artifacts.py` and `artifacts/remediation/ml_validation/`), several severe scientific and MLOps discrepancies were uncovered:
1. **Absence of a True Outbound Classifier:** P08 departure classification metrics were derived via a heuristic logistic sigmoid applied to predicted delay continuous regression outputs:
   $$\text{score} = \frac{1}{1 + \exp(-(\hat{y} - 15.0) / 10.0)}$$
   This was an ad-hoc heuristic risk score, not a trained, calibrated classification probability $P(\text{DEP\_DELAY} \ge 15 \mid X)$.
2. **Hardcoded Summary Metrics:** Multiple metric entries (including tuned arrival XGBoost in classification metrics, the entire probabilistic P1–P5 table, and the feature ablation A/B/C table) were stored as hardcoded dictionary entries rather than dynamically evaluated from raw model predictions.
3. **Median Predictor Dominance in MAE:** The constant median baseline achieved a lower MAE than all machine learning models on both arrival ($16.76$ min vs $19.43$–$20.24$ min) and departure ($15.60$ min vs $17.60$–$17.94$ min). Legacy documents failed to provide the mathematical justification for deploying ML under this phenomenon.
4. **Information Leakage in Feature Branches:** Weather observation features (METAR/ASOS) and flight chain linkages represented critical post-hoc information lookaheads relative to the T-2h prediction cutoff.

## 2. Baseline Configuration & Environmental Provenance

- **Repository Root:** `D:\Study\Code\Python\Aelous`
- **Active Remediation Branch:** `remediation/g3-ml-evidence`
- **Base Commit SHA:** `c95caef53808a561b1a7d3a5a09399cc52f754f5`
- **Prerequisite Gates:**
  - Gate G0 (Baseline & Rollback Gate): **PASS** (`remediation_evidence/G0_baseline/`)
  - Gate G1 (Data Provenance & Temporal Contracts): **PASS** (`remediation_evidence/G1_data_contracts/`)
  - Gate G2 (Monte Carlo Scientific Correctness): **PASS** (`remediation_evidence/G2_monte_carlo/`)
- **Execution Runtime:** Python 3.11.15 (Windows 11 AMD64, scikit-learn v1.9.0, XGBoost v3.2.0, NGBoost v0.5.3, PyTorch/OR-Tools)
- **Source Preservation Invariant:** All existing regression checkpoints in `artifacts/dual_core/models/` and probabilistic weights in `artifacts/probabilistic/` remain **STRICTLY FROZEN (READ-ONLY)**. All new classification artifacts are isolated in `artifacts/remediation/outbound_classification/`.

## 3. Scope Decomposition

| Domain Area | Legacy State (P08) | Remediated State (G3) |
| :--- | :--- | :--- |
| **Outbound Classification** | Heuristic sigmoid on regression predictions | True trained classifiers: **Logistic Regression** and **XGBoost Classifier** with probability calibration |
| **Probability Calibration** | Uncalibrated heuristic scores | Formal calibration via **Isotonic** and **Platt (Sigmoid)** scaling on 2022 development set; verified ECE $\le 0.05$ |
| **Metric Lineage** | Hardcoded tuples and dictionary entries in script | Comprehensive metric lineage matrix categorizing metrics into `RECOMPUTED_VERIFIED`, `HISTORICAL_REPORTED`, and `HEURISTIC_DERIVED` |
| **Regression Baselines** | Median outperforming ML in MAE left unexplained | Rigorous tail risk and RMSE analysis proving ML dramatically reduces severe delay errors ($\ge 15$, $\ge 60$ min) critical for gate assignment |
| **Probabilistic P1–P5** | Hardcoded table without lineage documentation | Audited prediction parquets in `artifacts/probabilistic/`; documented that P4 possesses native checkpoint while P5 is predictions-only |
| **Feature Ablation** | Hardcoded constants | Classified branches: Tabular (Certified Safe), Flight Chain (Blocked/Exploratory), Weather (Contaminated/Exploratory) |

## 4. Architectural Boundaries

Gate G3 introduces `scripts/train_outbound_classifiers_g3.py` and stores outputs in:
- `artifacts/remediation/outbound_classification/models/`
- `artifacts/remediation/outbound_classification/predictions/`
- `artifacts/remediation/outbound_classification/metrics/`

The original artifacts in `artifacts/dual_core/` and `artifacts/remediation/ml_validation/` are preserved for auditability and regression verification.
