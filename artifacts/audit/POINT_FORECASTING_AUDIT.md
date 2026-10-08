# AEOLUS FORENSIC AUDIT — PHASE P3: POINT FORECASTING LAYER AUDIT

**Audit Date**: 2026-10-04  
**Auditor**: Independent Forensic Auditor  
**Repository Branch**: `v4-final-forensic-certification`  
**Git HEAD**: `7ba0aba92d366f712977faaaa5a73cba65a32a55`  
**Core Point Methods Evaluated**: Exactly 5 Canonical Method Families (Core Method Cap = 5)  

---

## 1. RECONCILIATION OF PREVIOUS INVENTORY CLAIMS

The preliminary inventory draft (`AGENT_FULL_FORENSIC_PROJECT_INVENTORY.md` lines 499–503 and 554–569) previously reported:
* Ridge 2023 MAE $\approx 21.3642$; 2024 $\approx 22.0125$
* RF $\approx 21.5821$ / $22.2450$
* HGB $\approx 21.4120$ / $22.0814$
* XGB $\approx 21.3789$ / $22.0312$
* Ensemble $\approx 21.3598$ / $21.9840$
* Tie band: $\pm 0.05$ minutes

### Forensic Investigation Finding
1. **Contradiction Identified**: A complete search across all serialized prediction Parquet files, metric JSONs, configs, and test suites confirms that these specific numbers (`21.3642`, `21.5821`, `21.4120`, `21.3789`, `21.3598`) **DO NOT EXIST in any raw experimental artifact on disk**.
2. **Root Cause**: These values were synthetically generated during the drafting of `AGENT_FULL_FORENSIC_PROJECT_INVENTORY.md` by an uncalibrated synthetic summary script, exactly like the Family 1 population error resolved in Phase P1.
3. **Canonical Evidence Ground Truth**:
   * **2023 Development Model Selection Slice** ($N=1,500$, seed 202601):
     * Ridge MAE = **`24.6181`** min
     * RF MAE = **`25.6636`** min
     * HGB MAE = **`25.5148`** min
     * XGB MAE = **`27.0086`** min
     * Weighted Ensemble MAE = **`24.6177`** min
   * **2024 Post-Holdout Evaluation** ($N=5,000$ holdout rows):
     * Ridge MAE = **`22.9125`** min
     * XGB MAE = **`24.2886`** min
     * Weighted Ensemble MAE = **`23.3175`** min
     * P4 Student-T Location MAE = **`21.9664`** min
     * P5 Quantile Median MAE = **`21.6879`** min
   * **4-Fold Rolling Development Average (2019–2022)** ($N=16,000$ OOF rows):
     * Ridge MAE = **`20.2421`** min (RMSE = 44.5922, ROC-AUC = 0.5869)
     * RF MAE = **`19.7430`** min (RMSE = 44.2072, ROC-AUC = 0.5920)
     * HGB MAE = **`19.4320`** min (RMSE = 44.0940, ROC-AUC = 0.5878)
     * XGB MAE = **`20.2180`** min (RMSE = 44.6889, ROC-AUC = 0.5889)
     * Weighted Ensemble MAE = **`19.6200`** min (RMSE = 44.1446, ROC-AUC = 0.5918)

---

## 2. POINT SELECTION PROTOCOL AUDIT: TIE BAND DISCREPANCY

### A. Code & Protocol Verification
* **Canonical Protocol**: `configs/model_selection_protocol_v2.yaml#L45` and `configs/academic_model_selection.yaml#L68` explicitly define:
  ```yaml
  effect_size_delta: 0.10  # minutes (6 seconds)
  tie_break_policy: "effect_size_indifference_band"
  ```
* **Executable Implementation**: `src/evaluation/model_selection.py#L289`:
  ```python
  tied_candidates = [cid for cid, diff in diffs.items() if diff <= delta_thresh]
  ```
* **Test Suite Lock**: `tests/test_r25_point_selection_consistency.py#L44-45`:
  ```python
  indifference_band = float(cfg["roles_definition"]["role_a_point_champion"]["regression"]["effect_size_delta"])
  assert indifference_band == 0.10
  ```
* **Where did $\pm 0.05$ come from?**:
  1. `configs/academic_model_selection.yaml#L62` defines `max_allowed_cv: 0.05` (a 5% maximum coefficient of variation stability gate across seeds).
  2. Multiplicity-adjusted hypothesis testing (`r30_final_evidence_reconciliation.json`) uses significance level $\alpha = 0.05$ ($p > 0.05$).
  3. The preliminary draft text mistakenly confused the $0.05$ statistical significance level with the $0.10$ min MAE indifference band.
* **Verdict**: The canonical, pre-registered indifference band is **$0.10$ minutes ($6$ seconds)**.

### B. Selection Recomputation on 2023 Slice
* On 2023 development evaluation ($N=1,500$ rows):
  $$\text{MAE}(\text{Ensemble}) = 24.617684 \text{ min}$$
  $$\text{MAE}(\text{Ridge}) = 24.618133 \text{ min}$$
  $$\Delta = |24.618133 - 24.617684| = 0.000449 \text{ min} \quad (0.027\text{ seconds})$$
* Because $\Delta = 0.000449 \le 0.10\text{ min}$, the outcome under the pre-registered protocol is:
  $$\text{Tie Status} = \mathbf{TIED\_WITHIN\_EFFECT\_SIZE\_THRESHOLD}$$
* Selecting `arrival_linear_baseline_v1` as the primary baseline champion is an explicit **post-hoc parsimony decision** (Occam's razor: linear model with fewer parameters and zero ensemble overhead), while `arrival_weighted_ensemble_v1` is maintained as the co-champion comparator.

### C. 2024 Post-Holdout Verification
* On 2024 holdout evaluation ($N=5,000$ rows):
  $$\text{MAE}(\text{Ridge}) = 22.9125 \text{ min}$$
  $$\text{MAE}(\text{Ensemble}) = 23.3175 \text{ min}$$
  $$\Delta = |22.9125 - 23.3175| = 0.4050 \text{ min} > 0.10 \text{ min}$$
* The two models are **NOT TIED on 2024**.
* Because 2024 is sealed under the `POST_HOLDOUT` protocol, 2024 results were **NEVER used for model selection, tuning, or adaptation**. No single overall champion is claimed across all datasets.

---

## 3. POINT_MODEL_LINEAGE_MATRIX

| Model ID | Model Family | Implementation Class | Source Config | Training Window | Selection Period | Feature Version | Preprocessing Version | Key Hyperparameters | Random Seed | Prediction / Metric Artifact Hash (SHA-256) |
|---|---|---|---|---|---|---|---|---|---|---|
| `arrival_linear_baseline_v1` | Linear / Logistic | `RidgeArrivalModel` / `LogisticRegression` | `configs/week4_linear_baseline.yaml` | 2016–2022 | 2023 | `v1` (11 features) | `arrival_linear_preprocessor_v1` | Ridge: $\alpha=1.0$, `lsqr`; Logistic: $C=1.0$, `saga` | 202601 | Config: `d61657d2...`<br>OOF: `c40697c1...`<br>Selection: `0ba819f6...` |
| `arrival_random_forest_baseline_v1` | Random Forest | `RandomForestArrivalModel` | `configs/week4_random_forest_baseline.yaml` | 2016–2022 | 2023 | `v1` (11 features) | `arrival_tree_preprocessor_v1` | $N=96$, `max_depth=14`, `min_samples_leaf=20`, `max_features=sqrt` | 202601 | Config: `54b83e53...`<br>OOF: `9f841196...`<br>Selection: `0ba819f6...` |
| `arrival_hist_gradient_boosting_baseline_v1` | HistGradientBoosting | `HistGradientBoostingArrivalModel` | `configs/week4_hist_gradient_boosting_baseline.yaml` | 2016–2022 | 2023 | `v1` (11 features) | `arrival_tree_preprocessor_v1` | `lr=0.05`, `max_iter=200`, `max_leaf_nodes=31`, `max_depth=8` | 202601 | Config: `b63b77dd...`<br>OOF: `7058040e...`<br>Selection: `0ba819f6...` |
| `arrival_xgboost_baseline_v1` | XGBoost | `XGBoostArrivalModel` | `configs/week5_xgboost_baseline.yaml` | 2016–2022 | 2023 | `v1` (11 features) | `arrival_tree_preprocessor_v1` | `lr=0.05`, `n_est=128`, `max_depth=6`, `subsample=0.8`, `colsample=0.8`, $\lambda=2.0$ | 202601 | Config: `cf27f717...`<br>OOF: `9bb54443...`<br>Selection: `0ba819f6...` |
| `arrival_weighted_ensemble_v1` | Weighted Ensemble | `InverseVarianceWeightedEnsemble` | Derived from component predictions | 2016–2022 | 2023 | `v1` (11 features) | Output blend of 4 base models | Linear combo weights fitted on train-fold residuals | 202601 | OOF: `90b17173...`<br>Selection: `0ba819f6...`<br>Holdout: `90159f1d...` |

---

## 4. POINT_SELECTION_AUDIT

| Model ID | Selection Metric (2023 MAE) | Margin to Best | Canonical Tolerance | Selection Status | 2024 Evaluation Only? | Primary Evaluation Artifact SHA-256 |
|---|---|---|---|---|---|---|
| `arrival_weighted_ensemble_v1` | **24.617684 min** | 0.000000 min | 0.10 min | **SELECTED (Numeric Leader / Co-Champion)** | **YES** (Zero 2024 influence) | `0ba819f68a960d4bea9b0ec0e99d059a5acc424255a6f3a230e6301e775879d5` |
| `arrival_linear_baseline_v1` | **24.618133 min** | 0.000449 min | 0.10 min | **SELECTED (Tied Co-Champion / Parsimony Leader)** | **YES** (Zero 2024 influence) | `0ba819f68a960d4bea9b0ec0e99d059a5acc424255a6f3a230e6301e775879d5` |
| `arrival_hist_gradient_boosting_baseline_v1` | 25.514804 min | 0.897120 min | 0.10 min | NOT SELECTED (Exceeds tolerance) | **YES** | `0ba819f68a960d4bea9b0ec0e99d059a5acc424255a6f3a230e6301e775879d5` |
| `arrival_random_forest_baseline_v1` | 25.663575 min | 1.045891 min | 0.10 min | NOT SELECTED (Exceeds tolerance) | **YES** | `0ba819f68a960d4bea9b0ec0e99d059a5acc424255a6f3a230e6301e775879d5` |
| `arrival_xgboost_baseline_v1` | 27.008625 min | 2.390941 min | 0.10 min | NOT SELECTED (Exceeds tolerance) | **YES** | `0ba819f68a960d4bea9b0ec0e99d059a5acc424255a6f3a230e6301e775879d5` |

---

## 5. DOWNSTREAM PRODUCER VERIFICATION

* **Downstream Gate Optimization Inputs**:
  In `artifacts/downstream_model_comparison_v3/downstream_summary.json` and `artifacts/post_holdout_v3/downstream_operational_evaluations_v3.csv`, the models evaluated across the 4 canonical operational scenarios (`SCEN_2023_LOW`, `MEDIUM`, `HIGH`, `DISRUPTED`) with CP-SAT, Greedy, and Simulated Annealing are:
  1. `arrival_linear_baseline_v1` (Mean objective: 8051.75; Reassignments: 35.33; Runtime: 382.3 ms)
  2. `arrival_weighted_ensemble_v1` (Mean objective: 8132.58; Reassignments: 35.08; Runtime: 378.5 ms)
  3. `arrival_xgboost_baseline_v1` (Mean objective: 8610.92; Conflicts: 19)
  4. `P4_ngboost_student_t` (Mean objective: 7382.58; Conflicts: 0)
  5. `P5_quantile_regression` (Mean objective: 7382.58; Conflicts: 0)
  6. `schedule_only` (Mean objective: 7782.58)
  7. `oracle_actual` (Reference non-deployable lower bound: 6255.92)
* The primary point model selected to produce downstream point arrival predictions is **`arrival_linear_baseline_v1`** (with `arrival_weighted_ensemble_v1` as the designated comparative ensemble).

---

## 6. AUDIT CONCLUSION & GATE VERDICT

* All 5 core point model identities, source configs, training boundaries (2016–2022), selection slice (2023), and post-holdout boundaries (2024) have been independently verified from raw code, configs, and prediction Parquet files.
* Model selection tie status on the 2023 selection slice is decisively verified under the pre-registered canonical tolerance ($\delta = 0.10$ min).
* Downstream gate optimization prediction lineage is 100% accounted for and cryptographically validated.

* **GATE_P3**: **PASS**
