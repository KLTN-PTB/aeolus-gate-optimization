# AEOLUS FORENSIC AUDIT — WEIGHTED ENSEMBLE SPECIFIC AUDIT

**Audit Date**: 2026-10-04  
**Auditor**: Independent Forensic Auditor  
**Repository Branch**: `v4-final-forensic-certification`  
**Git HEAD**: `7ba0aba92d366f712977faaaa5a73cba65a32a55`  
**Target Subject**: Weighted Ensemble Lineage, Weight Degeneracy, and Downstream Operational Routing  

---

## 1. RECONCILIATION OF ENSEMBLE SPECIFICATIONS & HISTORICAL CLAIMS

The audit resolves the contradiction between two conflicting ensemble specifications previously described:
1. **The "Ridge + XGB 50/50" Family**: Described in `docs/audit/FINAL_EVIDENCE_RECONCILIATION_V2.md`, `configs/downstream_candidate_registry_v2.yaml`, and downstream execution runners.
2. **The "Ridge 0.4215, XGB 0.3482, HGB 0.2303, RF 0.0" Family**: Described in `AGENT_FULL_FORENSIC_PROJECT_INVENTORY.md#L580-584`.

### Forensic Finding & Discrepancy Attribution
* **Fabricated Claim Disproven**: An exhaustive scan of all disk artifacts confirms that the weights $[w_{\text{Ridge}}=0.4215, w_{\text{XGB}}=0.3482, w_{\text{HGB}}=0.2303, w_{\text{RF}}=0.0]$ and the cited file `artifacts/models/ensemble/ensemble_v1.json` **DO NOT EXIST on disk**. They were synthetically authored in the preliminary inventory draft (`AGENT_FULL_FORENSIC_PROJECT_INVENTORY.md`).
* **Two Genuine Physical Ensembles Identified**:
  * **`Ensemble_A` (Academic Benchmark SLSQP Ensemble)**: A 4-model convex combination optimizing L1/L2 loss via SLSQP over expanding-window folds. Because minimizing continuous L1 loss (MAE) over a simplex with correlated predictors causes mathematical vertex collapse, this ensemble's regression weights **collapsed to single-vertex solutions** ($w_{\text{HGB}}=1.0$ in Folds 2–4; $w_{\text{Ridge}}=1.0$ in the 2023 development selection slice).
  * **`Ensemble_B` (Downstream 50/50 Heuristic Ensemble)**: A 2-model equal-weighted convex blend:
    $$\hat{y}_{\text{ens}} = 0.5 \times \hat{y}_{\text{Ridge}} + 0.5 \times \hat{y}_{\text{XGB}}$$
    governed by `configs/downstream_candidate_registry_v2.yaml` and executed by downstream simulation scripts.

---

## 2. VERIFICATION OF THE 10 CRITICAL INVARIANTS

1. **Number of Constituent Models**:
   * `Ensemble_A`: Exactly **4 base models** (`arrival_linear_baseline_v1`, `arrival_random_forest_baseline_v1`, `arrival_hist_gradient_boosting_baseline_v1`, `arrival_xgboost_baseline_v1`).
   * `Ensemble_B`: Exactly **2 base models** (`arrival_linear_baseline_v1`, `arrival_xgboost_baseline_v1`).
2. **Actual Empirical Weights**:
   * `Ensemble_A` (audited in `artifacts/r19_ensemble_weight_audit.json`):
     * Fold 1 (2019): Uniform prior: $[0.25, 0.25, 0.25, 0.25]$
     * Fold 2 (2020): Regression $[0, 0, 1.0, 0]$ (HGB 100%); Classification $[0, 0.0064, 0, 0.9936]$
     * Fold 3 (2021): Regression $[0, 0, 1.0, 0]$ (HGB 100%); Classification $[0, 0.0465, 0, 0.9535]$
     * Fold 4 (2022): Regression $[0, 0, 1.0, 0]$ (HGB 100%); Classification $[0, 0, 0, 1.0]$
     * 2023 Selection: Regression $[1.0, 0, 0, 0]$ (Ridge 100%); Classification $[0, 0.158, 0, 0.842]$
   * `Ensemble_B`: Fixed hardcoded equal weights:
     $$w_{\text{Ridge}} = 0.50, \quad w_{\text{XGB}} = 0.50$$
3. **Weights Sum to Exactly 1.0**:
   * `Ensemble_A`: Yes, enforced by SLSQP equality constraint $\sum w_i = 1$ (error $< 10^{-6}$).
   * `Ensemble_B`: Yes, $0.5 + 0.5 = 1.0000$.
4. **Fitting Period**:
   * `Ensemble_A`: Fitted iteratively across expanding-window validation OOF sets (Fold 1 residuals for Fold 2; Folds 1–2 for Fold 3; Folds 1–3 for Fold 4; 2023 dev set for 2023 selection).
   * `Ensemble_B`: Pre-registered structural heuristic; zero historical residual fitting.
5. **Zero Utilization of 2024 Holdout**:
   * Neither ensemble fitted weights on 2024 data. Access guards strictly prohibited 2024 writes.
6. **Zero OOF Leakage**:
   * All inputs entering weight optimization were strictly out-of-fold predictions.
7. **Temporal Windowing Discipline**:
   * Training folds strictly preceded validation folds. Expanding window: 2016–2018 (F1) $\rightarrow$ 2016–2019 (F2) $\rightarrow$ 2016–2020 (F3) $\rightarrow$ 2016–2021 (F4).
8. **Primary Artifact Identity**:
   * Statistical & Academic Selection: `artifacts/manifests/academic_model_selection_v3.json` (SHA-256: `0ba819f68a960d4bea9b0ec0e99d059a5acc424255a6f3a230e6301e775879d5`).
   * Downstream Operational Evaluation: `artifacts/post_holdout_v3/downstream_operational_evaluations_v3.parquet` (SHA-256: `2b3f0bb5807eab826241b8d97cfea8b27a859ea503626543972404fa1429f2b8`).
9. **Co-existence of Parallel Versions**:
   * Yes, `Ensemble_A` and `Ensemble_B` co-exist in distinct pipelines.
10. **Downstream Pipeline Execution**:
    * Downstream solvers strictly execute **`Ensemble_B` (50/50 Ridge + XGBoost)**.

---

## 3. ENSEMBLE_LINEAGE_MATRIX

| Ensemble Version | Pipeline Context | Constituent Models | Weight Formulation | Empirical Weights (Regression) | Optimization Loss | Fitting Period | Downstream Usage? | Lineage Artifact (SHA-256) |
|---|---|---|---|---|---|---|---|---|
| **`Ensemble_A`** | Model Benchmark & Academic Selection | 4 models: Ridge, RF, HGB, XGB | SLSQP constrained convex optimization ($\sum w_i = 1, w_i \ge 0$) | F1: $[0.25, 0.25, 0.25, 0.25]$<br>F2: HGB=1.0<br>F3: HGB=1.0<br>F4: HGB=1.0<br>2023: Ridge=1.0 | L1 Norm (MAE) | Expanding-window OOF residuals (2016–2022 / 2023 dev) | **NO** (Evaluated only in tabular benchmark tables) | `artifacts/r19_ensemble_weight_audit.json`<br>(`3bb69b0ccd843250545f590382111ac6e18f48fec0702e1d46a83cf9be3f1fd7`) |
| **`Ensemble_B`** | Downstream Gate Simulation & Holdout Comparison | 2 models: Ridge, XGBoost | Fixed 50/50 equal-weighted convex blend | Ridge: $0.50$<br>XGBoost: $0.50$ | None (Pre-registered structural parsimony) | None (Frozen 50/50 linear combination) | **YES** (Evaluated as `arrival_weighted_ensemble_v1` in downstream solvers) | `configs/downstream_candidate_registry_v2.yaml`<br>(`6d57b644ce92072e85c7dd787dac8d245c6644e604290fd3cf2c92c201b09bb3`) |

---

## 4. DOWNSTREAM_MODEL_IDENTITY_MAP

| Candidate ID Evaluated Downstream | Actual Model Implementation | Prediction Interface | Downstream Objective (Mean) | Conflict Count (Mean) | Role in Downstream System |
|---|---|---|---|---|---|
| `schedule_only` | Zero Delay Constant ($\Delta t = 0$) | Deterministic scalar zero | 7332.37 | 0.00 | Static Timetable Baseline |
| **`arrival_linear_baseline_v1`** | **Ridge Regression Baseline** | `reg_ridge.predict(prep_lin.transform(X))` | **7589.87** | **0.25** | **Primary Selected Point Production Champion** |
| **`arrival_weighted_ensemble_v1`** | **`Ensemble_B` (50/50 Ridge + XGBoost)** | `0.5 * pred_ridge + 0.5 * pred_xgb` | **7588.20** | **0.25** | **Comparative Point Ensemble** |
| `arrival_xgboost_baseline_v1` | XGBoost Regressor | `reg_xgb.predict(prep_tree.transform(X))` | 7736.54 | 0.50 | Tree-Based Point Comparator |
| `P5_quantile_regression` | LightGBM Quantile Median ($\tau=0.50$) | `dist_p5.median()` | 7383.20 | 0.00 | Quantile Risk Point Prediction |
| `P4_ngboost_student_t` | NGBoost Student-T Location ($\mu$) | `dist_p4.mean()` | 7382.37 | 0.00 | Parametric Continuous Density Location |
| `oracle_actual` | Ground Truth Realized Delay | `flights_df["ARR_DELAY"]` | 6309.87 | 0.00 | Non-Deployable Theoretical Lower Bound |

---

## 5. SINGLE AUDIT CONCLUSION

> ### **Prediction nào thực sự đi vào downstream?**
>
> 1. Khi candidate mang tên `arrival_weighted_ensemble_v1` được kích hoạt downstream, prediction thực sự đi vào solver là **`Ensemble_B`**, được tính bằng công thức:
>    $$\mathbf{pred\_downstream} = \mathbf{0.5 \times \widehat{y}_{Ridge} + 0.5 \times \widehat{y}_{XGBoost}}$$
> 2. Tuy nhiên, giữa hai mô hình điểm cạnh tranh cho quyết định triển khai chính thức, mô hình **Point Champion thực sự được chọn triển khai** theo nguyên tắc parsimony (Occam's razor) là **`arrival_linear_baseline_v1` (Ridge Regression)**, dự báo trực tiếp từ mô hình tuyến tính đơn lẻ (`reg_ridge.predict`), hoàn toàn không phụ thuộc vào ensemble.

---

## 6. AUDIT GATE VERDICT

* **Identity & Weights Provenance**: Fully verified from code and JSON manifests.
* **Fabricated Values Rebutted**: Four-weight SLSQP $[0.4215, 0.3482, 0.2303, 0.0]$ confirmed as hallucinated documentation text with zero physical basis.
* **Downstream Routing**: 100% traced to `0.5 * linear + 0.5 * xgboost`.

* **GATE_ENSEMBLE**: **PASS**
