# Aeolus V4 R25: Point Model Selection Numerical & Claim Consistency Audit

> **Audit Task**: `R25_POINT_SELECTION_CONSISTENCY`  
> **Status**: `PASS`  
> **Timestamp (UTC)**: `2026-10-02T11:51:15.663034+00:00`  
> **Protocol**: `AEOLUS_V4_FORENSIC_OVERHAUL_STAGE_R25`  

---

## 1. Executive Summary

This forensic audit resolves the apparent numerical contradiction in the final evidence package:
- On the **2023 model selection slice**: Ridge MAE is `24.6181` min, Weighted Ensemble MAE is `24.6177` min, difference is `0.00045` min.
- On the **2024 post-holdout set**: Ridge MAE is `22.9125` min, Weighted Ensemble MAE is `23.3175` min, difference is `0.4050` min.
- Configured indifference band: `0.10` min (6 seconds).

### The Inconsistency
Prior summary text assigned a single blanket status `TIED_WITHIN_0.10_MIN_INDIFFERENCE_BAND` covering both years, which was numerically inaccurate for 2024 where the difference (`0.4050` min) clearly exceeds `0.10` min.

### The Resolution
1. **2023 Selection Slice**: `abs(24.6181 - 24.6177) = 0.00045 <= 0.10` min $\to$ **TIED** within the pre-registered indifference band. Both models are legitimately co-selected as point prediction champions for the development phase.
2. **2024 Post-Holdout Evaluation**: `abs(22.9125 - 23.3175) = 0.4050 > 0.10` min $\to$ **NOT TIED** within the indifference band.
3. **No Overall Champion**: Because 2024 is strictly a `POST_HOLDOUT` evaluation dataset and cannot be used to select or adapt models, no single overall point champion is asserted across all datasets.

---

## 2. Numerical Evidence Matrix

| Dataset Slice | Role | Ridge MAE (min) | Ensemble MAE (min) | Absolute Difference (min) | Indifference Band (min) | Tie Rule: $|\Delta| \le 0.10$ | Certified Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **2023 Development** | Model Selection Slice | 24.618133 | 24.617684 | **0.000449** | 0.10 | **True** (0.00045 $\le$ 0.10) | `TIED_WITHIN_0.10_MIN_INDIFFERENCE_BAND` |
| **2024 Post-Holdout** | Post-Holdout Evaluation | 22.912500 | 23.317500 | **0.405000** | 0.10 | **False** (0.4050 > 0.10) | `NOT_TIED_DIFFERENCE_EXCEEDS_0.10_MIN` |

---

## 3. Provenance & Lineage Verification

1. **Source Manifests**:
   - `artifacts/manifests/academic_model_selection_v3.json` (SHA: `0ba819f68a960d4bea9b0ec0e99d059a5acc424255a6f3a230e6301e775879d5`)
   - `configs/model_selection_protocol_v2.yaml` (SHA: `425cdc64ea2a20e016ec619dd677198cb68e8282640e3923bd52ad0d91c9bd61`)
   - `artifacts/post_holdout_v3/marginal_forecast_metrics_2024_v3.json` (SHA: `90159f1dd0a0bbbe5eb25b9646aa8bbdaa179edce8a56924165bab971d0f594c`)
   - `artifacts/post_holdout_v3/post_holdout_evaluation_manifest_v3.json` (SHA: `b9d7a7cf51b8f5691d7b37e6ce73ceb92113358247469f1cb750ff2a407c4f23`)
2. **Zero 2024 Adaptation**:
   - Training window: `[2016, 2017, 2018, 2019, 2020, 2021, 2022]`
   - Selection year: `2023`
   - Evaluation year: `2024` under strictly fail-closed `POST_HOLDOUT` pre-access guard governance.
   - Zero parameter, hyperparameter, threshold, ensemble weight, calibration, or feature engineering adaptation on 2024.

---

## 4. Reconciled Claim Boundaries

### `CLAIM_02_POINT_CHAMPION_SELECTION`
- **Allowed Wording**: *"Ridge regression and the 50/50 Weighted Ensemble tie within the 0.10 min indifference band on the 2023 model selection slice. On 2024 post-holdout, the difference is 0.405 min (> 0.10 min) and models are not tied; no single overall point champion is asserted."*
- **Prohibited Wording**: `Ridge dominates all models unconditionally, Ridge is statistically significantly superior to Weighted Ensemble, Both models tied overall across all years, Single overall point champion`

### `CLAIM_05_SINGLE_OVERALL_CHAMPION`
- **Allowed Wording**: *"Model selection is decoupled into distinct operational roles based on verified mathematical capabilities; single overall champion selection is blocked."*
- **Prohibited Wording**: `Overall best model, Universal champion, Single winner of the benchmark`

---

## 5. Audit Verdict

- **Audit Status**: **`PASS`**
- **Remaining P0 Blockers**: `0`
- **Next Permitted Phase**: `R26 — SOLVER EQUAL-TOTAL-COMPUTE RE-CERTIFICATION`
