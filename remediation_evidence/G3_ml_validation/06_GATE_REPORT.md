# AEOLUS-G3 — DELIVERABLE 06: GATE AUDIT REPORT

## 1. Official Gate Decision

**GATE STATUS: PASS (CERTIFIED WITH DOCUMENTED SCIENTIFIC LIMITATIONS)**

The Senior Machine Learning Research Engineer, MLOps Engineer, Statistical Evaluation Specialist, and Data Leakage Auditor hereby certify that **Gate G3: Machine Learning Evidence, Outbound Probability & Scientific Validation** has satisfied all non-negotiable scientific, causal, and reproducibility requirements.

## 2. Gate Verification Criteria Checklist

| Verification Requirement | Status | Evidence / Artifact Reference |
| :--- | :--- | :--- |
| **Prerequisites Verified** | **PASS** | Gates G0, G1, and G2 verified PASS prior to execution. Working tree isolated on `remediation/g3-ml-evidence`. |
| **Source & Checkpoint Preservation** | **PASS** | Original frozen regression models in `artifacts/dual_core/models/` and probabilistic checkpoints in `artifacts/probabilistic/` remain 100% untouched. |
| **Outbound Classification Baselines** | **PASS** | Trained true `LogisticRegression` and `XGBoostClassifier` baselines; replaced legacy heuristic sigmoid risk scores. |
| **Probability Calibration & Reliability** | **PASS** | Fitted Isotonic and Platt calibration on 2022 dev split without test leakage. Achieved $\text{ECE} \approx 0.011 \le 0.05$ and Brier score $0.156 < 0.168$ baseline. |
| **Regression Baseline Explanation** | **PASS** | Explained mathematical reason why Median predictor wins on MAE (L1 optimality on zero-skew bulk) while ML wins on RMSE and tail error ($\ge 15$, $\ge 60$ min). |
| **Probabilistic P1–P5 Lineage** | **PASS** | Audited raw prediction parquets in `artifacts/probabilistic/`. Confirmed P4 has native checkpoint while P5 is predictions-only. |
| **Feature Ablation Governance** | **PASS** | Tabular certified safe. Flight Chain and Weather restricted to exploratory research due to T-2h snapshot availability and METAR lookahead. |
| **Holdout 2024 Preservation** | **PASS** | Year 2024 strictly excluded from all training, tuning, calibration, and selection decisions. |
| **Unit & Integration Test Suite** | **PASS** | 15/15 dedicated G3 tests passed; 72/72 regression tests passed across repository in 2.56 seconds. |

## 3. Quantitative Summary of Findings (2023 Selection Split, N = 332,734)

- **Class Prevalence ($P(\text{DEP\_DELAY} \ge 15 \text{ min})$):** **20.63%**
- **Constant Prevalence Baseline:** Brier Score = **0.16776**, ECE = **0.06361**, PR-AUC = **0.20625**.
- **Outbound Logistic Regression (Calibrated):** ROC-AUC = **0.61336**, PR-AUC = **0.29381**, Brier Score = **0.15892**, ECE = **0.01047**.
- **Outbound XGBoost Classifier (Calibrated):** ROC-AUC = **0.64289**, PR-AUC = **0.32916**, Brier Score = **0.15637**, ECE = **0.01192**.
- **Calibration Target:** $\text{ECE} \le 0.05$ successfully satisfied by both calibrated models ($\text{ECE} \approx 0.011$).
- **Departure Regression ($N = 332,734$):**
  - Median Baseline: $\text{MAE} = 15.60$ min, $\text{RMSE} = 45.76$ min, $\text{Tail MAE}_{\ge 15} = 62.33$ min, $\text{Tail MAE}_{\ge 60} = 132.54$ min.
  - XGBoost Regressor: $\text{MAE} = 17.60$ min, $\text{RMSE} = 43.00$ min, $\text{Tail MAE}_{\ge 15} = 48.91$ min, $\text{Tail MAE}_{\ge 60} = 117.18$ min.

## 4. Sign-off & Transition to Gate G4

Gate G3 is officially certified. The machine learning pipeline now possesses rigorous metric lineage, true calibrated outbound classifiers, and complete baseline transparency. Gate G4 (Optimization Solvers & Hybrid Parity Remediation) may proceed when authorized.
