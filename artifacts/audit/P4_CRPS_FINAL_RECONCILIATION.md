# P4 CRPS Final Forensic Reconciliation Report

**Audit Target**: `P4_ngboost_student_t` (CRPS Semantic & Numerical Lineage Reconciliation)  
**Repository**: `Aeolus Probabilistic Core Arrival & Gate Optimization` (`D:\Study\Code\Python\Aelous`)  
**Branch**: `v4-final-forensic-certification`  
**Commit**: `7ba0aba92d366f712977faaaa5a73cba65a32a55`  
**Auditor**: Independent Forensic Auditor (Google DeepMind Antigravity)  
**Date**: `2026-10-04`  
**Mandate**: READ-ONLY Targeted Forensic Reconciliation Pass (No retrain, no tuning, no new predictions, no adaptation of 2024 holdout)

---

## 1. Executive Summary & Problem Formulation

In earlier audit phases, Family B ($\text{CRPS} = 16.8921, \text{NLL} = 4.2185$) was proven to be a fabricated draft documentation defect and formally rejected.

However, an ambiguity persisted within the legitimate P4 records:
1. **JSON-reported authoritative holdout metric**: `17.6532` (recorded in `artifacts/post_holdout_v3/marginal_forecast_metrics_2024_v3.json`)
2. **Direct recomputation via 9-quantile trapezoidal sum**: `17.645600` (on `artifacts/evaluation/final_holdout_2024/holdout_predictions_2024.parquet`)
3. **Direct recomputation via exact analytical Student-t CRPS**: `18.325040` (on `artifacts/evaluation/final_holdout_2024/holdout_predictions_2024.parquet`)
4. **2023 development selection metric**: `18.4840` (recorded in `artifacts/manifests/academic_model_selection_v3.json`)
5. **Stage 11 export rescaled proxy**: `17.133078` (in `artifacts/evaluation/final_holdout_2024/final_holdout_metrics_summary.json`, where $\text{CRPS} = \text{MAE} \times 0.78$)

Scientific certification cannot rely on saying these values are "approximately equal". This targeted forensic audit investigates the exact mathematical definition, implementation code, physical artifact, sampling population, and numerical derivation of each value.

---

## 2. Lineage Breakdown of All CRPS Candidates

### A. Exact Continuous Student-t CRPS (`18.325040`)
- **Mathematical Definition**: Exact closed-form integral of the Continuous Ranked Probability Score for non-standardized 3-parameter continuous Student-t distributions:
  $$\text{CRPS}(F, y) = \sigma \left[ z \left(2F_\nu(z) - 1\right) + 2 f_\nu(z) \frac{\nu + z^2}{\nu - 1} - \frac{2\sqrt{\nu}}{\nu - 1} \frac{B(1/2, \nu - 1/2)}{B(1/2, \nu/2)^2} \right]$$
  where $z = (y - \mu) / \sigma$, $\nu > 1$, $f_\nu$ is the standard Student-t PDF, and $F_\nu$ is the standard Student-t CDF (Jordan, Krüger, Lerch 2019).
- **Source Code Implementation**: [`src/models/probabilistic/student_t_correctness.py#analytical_student_t_crps`](file:///D:/Study/Code/Python/Aelous/src/models/probabilistic/student_t_correctness.py#L96-L130).
- **Physical Source Artifact**: Recomputed directly on [`artifacts/evaluation/final_holdout_2024/holdout_predictions_2024.parquet`](file:///D:/Study/Code/Python/Aelous/artifacts/evaluation/final_holdout_2024/holdout_predictions_2024.parquet) (SHA256: `67620cc572a367ba...`).
- **Model Checkpoint**: Frozen checkpoint [`artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib`](file:///D:/Study/Code/Python/Aelous/artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib) (`n_estimators = 50`, `learning_rate = 0.005`, `seed = 202601`).
- **Quantile Grid**: None. Integrates analytically over the full continuous support $(-\infty, +\infty)$.
- **Population**: $N = 5,000$ monthly-stratified 2024 BTS ATL arrival holdout flights.
- **Aggregation**: Unweighted sample mean $\frac{1}{N} \sum_{i=1}^N \text{CRPS}(F_i, y_i)$.
- **Scientific Role**: **PRIMARY METRIC FOR P4 IN ACADEMIC THESIS / BENCHMARK**.

### B. 9-Quantile Trapezoidal CRPS Approximation (`17.645600`)
- **Mathematical Definition**: Numerical quadrature of the pinball loss integral across 9 discrete pre-registered quantile levels:
  $$\text{CRPS}_{\text{approx}}(F, y) = \sum_{k=0}^{7} 2 (\alpha_{k+1} - \alpha_k) \frac{\text{Pinball}_{\alpha_k}(y, q_{\alpha_k}) + \text{Pinball}_{\alpha_{k+1}}(y, q_{\alpha_{k+1}})}{2}$$
- **Source Code Implementation**: [`src/evaluation/forecast_metrics.py#L135-L161`](file:///D:/Study/Code/Python/Aelous/src/evaluation/forecast_metrics.py#L135-L161) in `evaluate_predictive_distribution()`.
- **Pre-Registered Quantile Levels**: $\alpha \in \{0.025, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.975\}$.
- **Physical Source Artifact**: Recomputed directly on [`artifacts/evaluation/final_holdout_2024/holdout_predictions_2024.parquet`](file:///D:/Study/Code/Python/Aelous/artifacts/evaluation/final_holdout_2024/holdout_predictions_2024.parquet).
- **Why It Differs from Exact Analytical CRPS**:
  The 9-quantile trapezoidal quadrature truncates probability mass below $\alpha = 0.025$ and above $\alpha = 0.975$ (omitting the outer 5% of the distribution). Because P4 predicts heavy-tailed Student-t densities with low degrees of freedom ($\bar{\nu} \approx 2.52$), significant loss density lies in the extreme tails. Truncating these tails causes the 9-quantile approximation to underestimate the true continuous CRPS by $0.6794$ min ($17.6456$ vs $18.3250$).
- **Scientific Role**: **AUXILIARY METRIC FOR CROSS-MODEL COMPARISON** (Enables equitable comparison with discrete quantile models like P5 LightGBM, which lack continuous density).

### C. JSON-Reported Authoritative Metric (`17.6532`)
- **Mathematical Definition**: 9-quantile trapezoidal CRPS approximation evaluated by `evaluate_predictive_distribution()` on the candidate wrapper `cand_p4 = P4NGBoostStudentTCandidate(seed=202601)`.
- **Source Code Implementation**: [`scripts/run_post_holdout_evaluation_v2.py#L598`](file:///D:/Study/Code/Python/Aelous/scripts/run_post_holdout_evaluation_v2.py#L598) -> `evaluate_marginal_forecasts_2024_v2()` -> [`src/evaluation/forecast_metrics.py#L161`](file:///D:/Study/Code/Python/Aelous/src/evaluation/forecast_metrics.py#L161).
- **Physical Source Artifact**: [`artifacts/post_holdout_v3/marginal_forecast_metrics_2024_v3.json`](file:///D:/Study/Code/Python/Aelous/artifacts/post_holdout_v3/marginal_forecast_metrics_2024_v3.json#L66) (SHA256: `90159f1dd0a0bbbe...`).
- **Exact Reason for $17.645600$ vs $17.6532$**:
  - Both runs evaluated the **exact same 5,000 monthly-stratified 2024 flights** (verified with 5,000/5,000 identical flight keys between `holdout_predictions_2024.parquet` and `load_stratified_2024_marginal_sample`).
  - `17.645600` was produced by `scripts/run_probabilistic_stage11_final_holdout.py` using the Stage 10 frozen checkpoint `model_weights_frozen_v1.joblib` (which was trained with `n_estimators = 50`).
  - `17.6532` was produced by `scripts/run_post_holdout_evaluation_v2.py` using `P4NGBoostStudentTCandidate`, which hardcodes `n_estimators = 40` in [`src/models/probabilistic/candidate_interfaces.py#L267`](file:///D:/Study/Code/Python/Aelous/src/models/probabilistic/candidate_interfaces.py#L267).
  - The $0.0076$ min difference ($0.043\%$) is strictly an estimator-depth variance ($40$ vs $50$ boosting iterations).
  - **Mislabeled Documentation Finding**: In `artifacts/audit/r28_metric_lineage.json` and subsequent narrative reports, `17.6532` was improperly classified as `"exact_continuous_crps"`. Code tracing proves it is mathematically a 9-quantile trapezoidal approximation.

### D. 2023 Development Selection Metric (`18.4840`)
- **Mathematical Definition**: 9-quantile trapezoidal CRPS approximation evaluated on the 2023 development model selection slice.
- **Source Code Implementation**: [`scripts/run_academic_model_selection.py#L270`](file:///D:/Study/Code/Python/Aelous/scripts/run_academic_model_selection.py#L270) -> `evaluate_probabilistic_prediction()` -> `evaluate_predictive_distribution()`.
- **Physical Source Artifact**: [`artifacts/manifests/academic_model_selection_v3.json`](file:///D:/Study/Code/Python/Aelous/artifacts/manifests/academic_model_selection_v3.json#L155) (SHA256: `0ba819f68a960d4b...`).
- **Population**: $N = 1,500$ validation flights sampled from calendar year 2023 (`sample_val_2023: 1500`, `seed: 202601`).
- **Training Window**: Outer development 2016–2022 ($2,000 \text{ flights/year} \times 7 = 14,000$ flights).
- **Why It Differs from 2024 Values**:
  It belongs to a completely different temporal partition and sample size: **2023 Development Selection** ($N=1,500$) versus **2024 Post-Holdout** ($N=5,000$).

---

## 3. Comprehensive Metric Lineage Matrix

| Value | Metric Identity | Exact or Approx | Mathematical Formula | Code Implementation | Source Artifact | Temporal Split | Population N | Aggregation | SHA-256 Digest | Audit Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`18.325040`** | Continuous Student-t CRPS | **EXACT** | Jordan, Krüger, Lerch (2019) analytical closed form | `student_t_correctness.py#L96` | `holdout_predictions_2024.parquet` | 2024 Holdout | 5,000 | Arithmetic Mean | `67620cc572...` | **VALID (PRIMARY)** |
| **`17.645600`** | 9-Quantile CRPS Quadrature | **APPROX** | Trapezoidal pinball sum over 9 quantiles | `forecast_metrics.py#L135` | `holdout_predictions_2024.parquet` | 2024 Holdout | 5,000 | Arithmetic Mean | `67620cc572...` | **VALID (AUXILIARY)** |
| **`17.6532`** | 9-Quantile CRPS Quadrature | **APPROX** | Trapezoidal pinball sum (cand_p4, n=40) | `forecast_metrics.py#L135` | `marginal_forecast_metrics_2024_v3.json` | 2024 Holdout | 5,000 | Arithmetic Mean | `90159f1dd0...` | **VALID (MISLABELED)** |
| **`18.4840`** | 9-Quantile CRPS Quadrature | **APPROX** | Trapezoidal pinball sum on 2023 dev | `forecast_metrics.py#L135` | `academic_model_selection_v3.json` | 2023 Selection | 1,500 | Arithmetic Mean | `0ba819f68a...` | **VALID (DEV ONLY)** |
| **`17.133078`** | Rescaled MAE Proxy | **HEURISTIC** | $\text{MAE} \times 0.78$ ($21.965485 \times 0.78$) | `final_holdout.py#L338` | `final_holdout_metrics_summary.json` | 2024 Holdout | 5,000 | Sample Mean | `49be0f7e4a...` | **SUPERSEDED** |
| **`16.8921`** | Fabricated Value (Family B) | **INVALID** | None (Hallucinated entry in draft inventory) | None | `AGENT_FULL_FORENSIC_PROJECT_INVENTORY.md` | N/A | N/A | None | Untracked | **REJECTED** |

---

## 4. Answers to Mandatory Forensic Questions

### Q1: Is `17.6532` an exact continuous Student-t CRPS?
**NO**. Code tracing in `src/evaluation/forecast_metrics.py` lines 150–162 proves that for model family `"ngboost_student_t"`, the evaluation function sets `metrics["crps"] = metrics["crps_quantile_approx"]`. `17.6532` is a 9-quantile trapezoidal pinball sum.

### Q2: Is `17.6532` a 9-quantile approximation?
**YES**. It was generated by trapezoidal numerical integration over the 9 pre-registered quantiles $\alpha \in \{0.025, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.975\}$.

### Q3: Why does direct recomputation give `17.645600` rather than `17.6532`?
Because `holdout_predictions_2024.parquet` stores the predictions from checkpoint `model_weights_frozen_v1.joblib` (trained with `n_estimators = 50`), whereas `17.6532` was exported during `run_post_holdout_evaluation_v2.py` where `P4NGBoostStudentTCandidate` was configured with `n_estimators = 40`. Both runs evaluated the exact same 5,000 flights (5,000/5,000 identical keys). The discrepancy is strictly the $0.0076$ min difference from 40 vs 50 boosting iterations.

### Q4: Why does exact Student-t CRPS give `18.325040`?
Because the exact closed-form formula integrates the scoring rule across $(-\infty, +\infty)$, incorporating the heavy tail dispersion ($\nu \approx 2.52$). The 9-quantile trapezoidal quadrature cuts off the outer 5% of probability mass, which omits tail loss and underestimates the true continuous CRPS by $\approx 0.68$ min ($17.6456$ vs $18.3250$).

### Q5: Why is 2023 development value `18.4840` different?
Because `18.4840` is from the **2023 development model selection slice** ($N = 1,500$ validation flights from 2023, trained on 2016–2022 with $N = 14,000$), whereas the holdout values are from the **2024 Post-Holdout slice** ($N = 5,000$ flights from 2024). They are distinct temporal partitions.

### Q6: Is `17.6532` generated from the same physical prediction matrix currently hashed?
**NO**. The physical prediction matrix `holdout_predictions_2024.parquet` (SHA256: `67620cc572...`) contains predictions from `model_weights_frozen_v1.joblib` ($n=50$). `17.6532` was generated in-memory during `run_post_holdout_evaluation_v2.py` using `P4NGBoostStudentTCandidate` ($n=40$).

### Q7: If yes, explain the numerical discrepancy exactly.
N/A (see Q8).

### Q8: If no, identify the actual source artifact.
The source artifact recording `17.6532` is [`artifacts/post_holdout_v3/marginal_forecast_metrics_2024_v3.json`](file:///D:/Study/Code/Python/Aelous/artifacts/post_holdout_v3/marginal_forecast_metrics_2024_v3.json) (SHA256: `90159f1dd0a0bbbe...`), generated during Phase R23 post-holdout execution.

### Q9: Which CRPS definition was pre-registered for P4?
Per `docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md` (Section 9.2, lines 651–660, and Section 22):
- Candidates with full parametric density (B5 / P4) are pre-registered for continuous distribution evaluation via CRPS and NLL.
- The exact continuous closed-form Student-t CRPS was formally specified and mathematically implemented in `src/models/probabilistic/student_t_correctness.py#analytical_student_t_crps` (Jordan et al. 2019).
- The 9-quantile trapezoidal formula in `forecast_metrics.py` was implemented as a multi-model comparator to evaluate models like P5 LightGBM Quantile Regression that lack continuous density.

### Q10: Which CRPS should be the PRIMARY metric in the thesis?
**Exact Continuous Analytical Student-t CRPS** (Jordan et al. 2019):
$$\text{PRIMARY\_CRPS\_VALUE\_2024} = \mathbf{18.325040 \text{ min}}$$

### Q11: Which CRPS should be reported only as AUXILIARY/APPROXIMATE?
**9-Quantile Trapezoidal CRPS Approximation**:
$$\text{AUXILIARY\_CRPS\_VALUE\_2024} = \mathbf{17.645600 \text{ min}} \quad (\text{or } 17.6532 \text{ in V3 Post-Holdout re-evaluation})$$
Reported strictly as an auxiliary cross-model comparator to enable fair apples-to-apples comparison against discrete quantile models like P5 (which cannot evaluate continuous density or exact analytical CRPS).

---

## 5. Required Forensic Reconciliation Block

```text
================================================================================
P4 CRPS FINAL RECONCILIATION DETERMINATION
================================================================================
PRIMARY_CRPS_DEFINITION = Exact continuous Student-t closed-form CRPS (Jordan, Krüger, Lerch 2019; src/models/probabilistic/student_t_correctness.py)
PRIMARY_CRPS_VALUE_2024 = 18.325040
AUXILIARY_CRPS_DEFINITION = 9-quantile trapezoidal pinball sum approximation over alphas {0.025, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.975} (src/evaluation/forecast_metrics.py)
AUXILIARY_CRPS_VALUE_2024 = 17.645600 (Recomputed on holdout_predictions_2024.parquet) / 17.6532 (Recorded in marginal_forecast_metrics_2024_v3.json)
17.6456_TO_17.6532_EXACT_CAUSE = Estimator depth variance in NGBoost: 17.6456 uses frozen checkpoint (n_estimators=50); 17.6532 used candidate wrapper (n_estimators=40). Both evaluated identical 5,000 monthly-stratified 2024 flights.
2023_18.4840_IDENTITY = 9-quantile trapezoidal CRPS approximation evaluated on 2023 development selection slice (N=1,500 validation flights, trained on 2016-2022 N=14,000).
CRPS_LINEAGE = CLOSED
GATE_P5R = PASS
================================================================================
```
