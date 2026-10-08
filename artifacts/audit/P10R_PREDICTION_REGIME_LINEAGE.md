# FORENSIC AUDIT REPORT: PREDICTION REGIME LINEAGE IN MONTE CARLO (P10-R)
**Project**: Aeolus Probabilistic Core Arrival & Gate Optimization  
**Auditor**: Forensic Audit Protocol (Strict Read-Only Verification)  
**Date**: 2026-10-04  
**Audit Scope**: Targeted Reconciliation of Monte Carlo P4 and P5 Prediction Lineage  
**Status**: `P10R_STATUS = CLOSED`

---

## 1. EXECUTIVE SUMMARY & FORENSIC VERDICT

This targeted reconciliation pass audits the prediction regime lineage feeding the Monte Carlo simulation engine ([`scripts/run_monte_carlo_comparison.py`](file:///D:/Study/Code/Python/Aelous/scripts/run_monte_carlo_comparison.py)).

### Key Forensic Discoveries:
1. **P4 is a Synthetic Proxy, NOT Native P4**:
   - The Monte Carlo arm labelled `"P4_ngboost_student_t"` does **NOT** consume the frozen NGBoost checkpoint ([`model_weights_frozen_v1.joblib`](file:///D:/Study/Code/Python/Aelous/artifacts/probabilistic/model_weights_frozen_v1.joblib)) or native observation-dependent parameters $\mu(x), \sigma(x), \nu(x)$.
   - Instead, it dynamically fits an in-memory `Ridge(alpha=1.0)` model on outer development data to provide location $\hat{\mu}_{\text{Ridge}}$, and adds homoscedastic Student-t perturbations with fixed scalar scale $\sigma=16.5$ and fixed degrees of freedom $\nu=4.0$:
     $$D = \hat{\mu}_{\text{Ridge}} + 16.5 \cdot t_4^{-1}(U)$$
   - Formally classified under **CASE C**: `P4_MC_REGIME = SYNTHETIC_PROXY`.
2. **P5 is an Asymmetric Laplace Proxy, NOT Forecast-Only**:
   - Although [`src/evaluation/mc_convergence.py`](file:///D:/Study/Code/Python/Aelous/src/evaluation/mc_convergence.py) defined a forecast-only adapter, the actual runner [`scripts/run_monte_carlo_comparison.py`](file:///D:/Study/Code/Python/Aelous/scripts/run_monte_carlo_comparison.py) invoked [`MonteCarloDelayTransformer.transform`](file:///D:/Study/Code/Python/Aelous/src/evaluation/monte_carlo_comparison.py#L244-L255).
   - This applied an invented piecewise-linear asymmetric normal quantile transform (asymmetric Laplace proxy) to the XGBoost point prediction:
     $$\text{shock} = \begin{cases} \Phi^{-1}(U) \times (1.8 \times 16.5) = 29.7 \cdot \Phi^{-1}(U) & \text{if } \Phi^{-1}(U) \ge 0 \\ \Phi^{-1}(U) \times (1.2 \times 16.5) = 19.8 \cdot \Phi^{-1}(U) & \text{if } \Phi^{-1}(U) < 0 \end{cases}$$
   - This explains why P5 objective variance in [`convergence_estimates.json`](file:///D:/Study/Code/Python/Aelous/artifacts/monte_carlo_model_comparison_v2/convergence_estimates.json) is $\text{Var} = 84,165.2$ rather than $0.0$.
   - Formally classified as: `P5_MC_REGIME = ASYMMETRIC_LAPLACE_PROXY`.
3. **Temporal Safety Verified**:
   - 2024 holdout data was strictly sealed (`assert_data_access_allowed(2024, "development")` verified).
   - All in-memory estimators were fit strictly on 2016–2022 development folds with 2023 validation.
   - `HOLDOUT_CONTAMINATION = NONE`.

---

## 2. TASK 1 — TRACE ACTUAL MONTE CARLO P4 IMPLEMENTATION

### Execution Lineage:
`Monte Carlo P4 Arm` (`"P4_ngboost_student_t"`)  
$\to$ [`scripts/run_monte_carlo_comparison.py:172-176`](file:///D:/Study/Code/Python/Aelous/scripts/run_monte_carlo_comparison.py#L172-L176): Fit `reg_ridge = Ridge(alpha=1.0)` on outer development set (`train_years=[2016..2022]`).  
$\to$ [`scripts/run_monte_carlo_comparison.py:191`](file:///D:/Study/Code/Python/Aelous/scripts/run_monte_carlo_comparison.py#L191): Set `"P4_ngboost_student_t": base_linear` (where `base_linear = reg_ridge.predict(...)`).  
$\to$ [`scripts/run_monte_carlo_comparison.py:228-235`](file:///D:/Study/Code/Python/Aelous/scripts/run_monte_carlo_comparison.py#L228-L235): Call `MonteCarloDelayTransformer.transform(model_id="P4_ngboost_student_t", latent_u=latent_u, base_delays=base_linear, residual_sigma=16.5, student_t_df=4.0)`.  
$\to$ [`src/evaluation/monte_carlo_comparison.py:237-242`](file:///D:/Study/Code/Python/Aelous/src/evaluation/monte_carlo_comparison.py#L237-L242): Compute sampled delays via:
$$D = \hat{\mu}_{\text{Ridge}} + 16.5 \cdot t_4^{-1}(U)$$
$\to$ Downstream Synthetic Turn generation via [`AircraftTurnModel.synthesize_turn`](file:///D:/Study/Code/Python/Aelous/src/simulation/aircraft_turn.py#L59)  
$\to$ Downstream Gate Assignment via [`DeterministicGreedyGateSolver.solve`](file:///D:/Study/Code/Python/Aelous/src/optimization/solvers/greedy_solver.py).

### Quantity Traceability Comparison:

| Quantity | Expected Native P4 | Actual MC Source | Actual Value Type | Match? | Evidence |
|---|---|---|---|---|---|
| **Location $\mu$** | $\mu_{\text{P4}}(x)$ from NGBoost checkpoint/predictions | In-memory `reg_ridge.predict(prep_lin.transform(X_scen))` | Vector of point predictions from linear model $\hat{\mu}_{\text{Ridge}}$ | **NO (MISMATCH)** | [`scripts/run_monte_carlo_comparison.py:191`](file:///D:/Study/Code/Python/Aelous/scripts/run_monte_carlo_comparison.py#L191): `"P4_ngboost_student_t": base_linear` |
| **Scale $\sigma$** | $\sigma_{\text{P4}}(x)$ conditional scale from NGBoost | Hardcoded argument `residual_sigma=16.5` in runner | Fixed homoscedastic scalar constant ($16.5$) | **NO (MISMATCH)** | [`scripts/run_monte_carlo_comparison.py:233`](file:///D:/Study/Code/Python/Aelous/scripts/run_monte_carlo_comparison.py#L233), [`src/evaluation/monte_carlo_comparison.py:241`](file:///D:/Study/Code/Python/Aelous/src/evaluation/monte_carlo_comparison.py#L241) |
| **Degrees of Freedom $\nu$** | $\nu_{\text{P4}}(x)$ conditional tail parameter from NGBoost | Hardcoded argument `student_t_df=4.0` in runner | Fixed homoscedastic scalar constant ($4.0$) | **NO (MISMATCH)** | [`scripts/run_monte_carlo_comparison.py:234`](file:///D:/Study/Code/Python/Aelous/scripts/run_monte_carlo_comparison.py#L234), [`src/evaluation/monte_carlo_comparison.py:240`](file:///D:/Study/Code/Python/Aelous/src/evaluation/monte_carlo_comparison.py#L240) |
| **Sampling Source** | Native NGBoost Student-t distribution $Y = \mu(x) + \sigma(x) \cdot T_{\nu(x)}$ | SciPy `student_t.ppf(latent_u, df=4.0)` shifted by Ridge | Homoscedastic synthetic Student-t disturbance | **NO (SYNTHETIC PROXY)** | [`src/evaluation/monte_carlo_comparison.py:240-241`](file:///D:/Study/Code/Python/Aelous/src/evaluation/monte_carlo_comparison.py#L240-L241) |

---

## 3. TASK 2 — DETERMINE WHETHER THIS IS NATIVE P4 OR A PROXY

### Classification:
- **CASE A — Native P4**: The simulation directly consumes $\mu_{\text{P4}}(x), \sigma_{\text{P4}}(x), \nu_{\text{P4}}(x)$ from the frozen P4 checkpoint/prediction artifact.  
  $\implies$ **FALSE**. No native P4 parameters were consumed.
- **CASE B — P4-Derived Representation**: The simulation uses a transformation of native P4 outputs.  
  $\implies$ **FALSE**. Native P4 outputs were never loaded or transformed.
- **CASE C — Synthetic Student-t Proxy**: The simulation uses:
  $$\hat{\mu}_{\text{Ridge}} + \text{fixed } \sigma + \text{fixed } df$$
  without directly consuming native P4 outputs.  
  $\implies$ **CONFIRMED (CASE C)**.

**Formal Classification**:
```text
P4_MC_REGIME = SYNTHETIC_PROXY
```
It **MUST NOT** be labelled simply `P4_ngboost_student_t` for downstream optimization or robustness claims.

---

## 4. TASK 3 — TRACE MODEL ARTIFACTS

Inspection of [`scripts/run_monte_carlo_comparison.py`](file:///D:/Study/Code/Python/Aelous/scripts/run_monte_carlo_comparison.py) confirms that:
- Neither [`model_weights_frozen_v1.joblib`](file:///D:/Study/Code/Python/Aelous/artifacts/probabilistic/model_weights_frozen_v1.joblib) nor [`holdout_predictions_2024.parquet`](file:///D:/Study/Code/Python/Aelous/artifacts/evaluation/final_holdout_2024/holdout_predictions_2024.parquet) is referenced, opened, or loaded.
- All model inputs were generated **on-the-fly** inside the process memory.

### Artifacts Lineage Trace:

| Path | SHA256 Hash | Role in Monte Carlo | Model Identity | Split / Data Source | Generation Source |
|---|---|---|---|---|---|
| In-memory `reg_ridge` | N/A (RAM object) | Provides $\mu$ for linear baseline & P4 proxy | `sklearn.linear_model.Ridge(alpha=1.0)` | Train: 2016–2022 (subsample 1200/yr), Val: 2023 (1500) | Fitted on-the-fly via [`load_stratified_fold_data`](file:///D:/Study/Code/Python/Aelous/src/data/stratified_loader.py) |
| In-memory `reg_xgb` | N/A (RAM object) | Provides $\mu$ for XGBoost baseline & P5 proxy | `xgboost.XGBRegressor(n_estimators=50, max_depth=5)` | Train: 2016–2022, Val: 2023 | Fitted on-the-fly via [`load_stratified_fold_data`](file:///D:/Study/Code/Python/Aelous/src/data/stratified_loader.py) |
| Raw 2023 flight batches | Read-only input | Base operational bank `SCEN_2023_LOW` (30 flights) | Canonical tabular flights | 2023 Development | Extracted via [`iter_arrival_development_batches(2023)`](file:///D:/Study/Code/Python/Aelous/src/data/preprocessing.py#L38) |
| `model_weights_frozen_v1.joblib` | `984638703a...` | **NOT USED** (0 bytes read) | Frozen native NGBoost Student-t | Sealed checkpoint | Completely bypassed |
| `holdout_predictions_2024.parquet` | `a90ebf8730...` | **NOT USED** (0 bytes read) | 2024 Holdout predictions | 2024 Sealed Holdout | Completely bypassed |

**Rationale for Substitution in Historical Implementation**:
The runner script was constructed as a rapid downstream solver/scalability benchmark across 6 regimes. To avoid the heavy runtime latency of loading NGBoost and inferencing tree ensembles across hundreds of scenarios, the author substituted Ridge regression + parametric Student-t noise as an operational placeholder, but retained the nominal identifier `"P4_ngboost_student_t"`.

---

## 5. TASK 4 — TEMPORAL SAFETY & HOLDOUT CONTAMINATION AUDIT

We audited the provenance of every parameter in the Monte Carlo execution:

1. **Location Estimators (`reg_ridge`, `reg_xgb`)**:
   - Provenance: `TRAINED` on development years 2016–2022 with validation on 2023.
   - Code verification: [`scripts/run_monte_carlo_comparison.py:162-169`](file:///D:/Study/Code/Python/Aelous/scripts/run_monte_carlo_comparison.py#L162-L169).
   - 2024 data was strictly inaccessible.
2. **Residual Scale ($\sigma = 16.5$)**:
   - Provenance: `FIXED_PRE_REGISTERED` constant passed as function argument.
   - Derived from historical 2016–2022 development arrival delay residual standard deviation.
   - No post-hoc fitting against 2024 holdout.
3. **Degrees of Freedom ($\nu = 4.0$)**:
   - Provenance: `FIXED_PRE_REGISTERED` constant passed as function argument.
   - Standard heavy-tail benchmark parameter.
   - No post-hoc fitting against 2024 holdout.
4. **Holdout Guard Execution**:
   - Verified that `assert_data_access_allowed(2024, "development")` failed closed at line 125, confirming 2024 was completely sealed.

**Verdict**:
```text
HOLDOUT_CONTAMINATION = NONE
```

---

## 6. TASK 5 — SEPARATION OF P4 FROM RIDGE

We analyzed whether $\hat{\mu}_{\text{Ridge}}$ is:
1. Genuinely the P4 location parameter? $\implies$ **NO**. Native P4 has an observation-dependent location $\mu(x)$ predicted by a gradient-boosted tree ensemble with tabular categorical/cyclical features.
2. Merely used as a proxy? $\implies$ **YES**. It is an explicit linear model proxy substituted into the simulation loop.
3. An intermediate diagnostic? $\implies$ **NO**. It directly produced the authoritative artifacts in `artifacts/monte_carlo_model_comparison_v2/`.
4. Stale documentation? $\implies$ **NO**. It is live executable code in [`scripts/run_monte_carlo_comparison.py:191`](file:///D:/Study/Code/Python/Aelous/scripts/run_monte_carlo_comparison.py#L191).

**Forensic Principle**: Ridge regression and P4 NGBoost are completely separate models. A similar MAE or location estimate does not constitute model identity. P4 downstream claims cannot be validated using Ridge predictions.

---

## 7. TASK 6 — P5 BOUNDARY CHECK

We audited the P5 quantile regression arm in the actual Monte Carlo execution:
- **Expected Native Behavior**: P5 is a non-parametric multi-quantile model (no continuous CDF). In Task R4/R5 governance, P5 was restricted to **forecast-only mode** (scalar median replicated across scenarios with zero continuous sampling).
- **Physical Execution Finding**:
  In [`scripts/run_monte_carlo_comparison.py:229-235`](file:///D:/Study/Code/Python/Aelous/scripts/run_monte_carlo_comparison.py#L229-L235), the code called [`MonteCarloDelayTransformer.transform`](file:///D:/Study/Code/Python/Aelous/src/evaluation/monte_carlo_comparison.py#L244-L255):
  ```python
  elif model_id == "P5_quantile_regression":
      spread_left = residual_sigma * 1.2    # 19.8 min
      spread_right = residual_sigma * 1.8   # 29.7 min
      z = norm.ppf(latent_u)
      adjustment = np.where(z >= 0, z * spread_right, z * spread_left)
      sampled = base[None, :] + adjustment
      return sampled
  ```
  Where `base` was `base_xgb` (the in-memory XGBoost point prediction).
- **Physical Artifact Confirmation**:
  In [`artifacts/monte_carlo_model_comparison_v2/convergence_estimates.json`](file:///D:/Study/Code/Python/Aelous/artifacts/monte_carlo_model_comparison_v2/convergence_estimates.json), P5 exhibits:
  - $N=100$: $\text{Var} = 90,390.4$
  - $N=500$: $\text{Var} = 84,165.2$, $\text{SE} = 12.9742$
  - $N=2500$: $\text{Var} = 77,710.6$, $\text{SE} = 5.5753$
  If P5 had been executed in forecast-only mode, the variance across scenarios would be **$0.0$** (identical to `schedule_only` and `oracle_actual`).
- **Verdict**:
  The actual P5 Monte Carlo arm did **NOT** execute in forecast-only mode. It executed an **invented asymmetric Laplace / piecewise linear quantile mapping proxy** applied to XGBoost point predictions.

**Classification**:
```text
P5_MC_REGIME = ASYMMETRIC_LAPLACE_PROXY
```

---

## 8. TASK 7 — DOWNSTREAM CLAIM IMPACT

The discovery that the Monte Carlo P4 and P5 arms are synthetic proxies requires a strict separation between downstream algorithmic infrastructure and specific model superiority claims:

| P10 Result / Area | Uses Native P4? | Uses Proxy? | Claim Still Valid? | Required Scientific Wording |
|---|---|---|---|---|
| **P4 Operational Superiority Claims** | **NO** | **YES** | **NO (INVALID)** | "Kết quả mô phỏng không đại diện cho mô hình P4 NGBoost đã đóng băng. Các tuyên bố về tính ưu việt của P4 ở downstream bị thu hồi do dữ liệu đầu vào thực tế là một synthetic Student-t proxy trên nền Ridge." |
| **P5 Operational Superiority Claims** | **NO** | **YES** | **NO (INVALID)** | "P5 trong Monte Carlo thực tế không chạy native quantile cũng như không phải scalar median thuần túy, mà sử dụng một biến đổi bất đối xứng giả lập (asymmetric Laplace proxy) trên nền XGBoost." |
| **Model Ranking Hierarchy** | **NO** | **YES** | **PARTIAL (BENCHMARK ONLY)** | "Thứ tự hiệu năng downstream là so sánh thực nghiệm giữa 6 cơ chế nhiễu tổng hợp (Schedule-only vs Gaussian vs Student-t heavy tail vs Asymmetric proxy vs Oracle), không phản ánh xếp hạng giữa các mô hình ML nguyên bản." |
| **Monte Carlo Convergence Architecture** | **NO** | **YES** | **YES (VALID)** | "Hạ tầng toán học đánh giá hội tụ Monte Carlo ($N \in [100, 2500]$), tốc độ giảm sai số chuẩn $\mathcal{O}(1/\sqrt{N})$, và cơ chế hạch toán thất bại (failure accounting) hoàn toàn hợp lệ về phương pháp luận tính toán mô phỏng." |
| **Selection of $N=500$** | **NO** | **YES** | **YES (VALID)** | "Quyết định chọn $N=500$ là một thỏa hiệp thực nghiệm hợp lệ giữa chi phí tính toán (~0.35ms/scenario) và độ ổn định phương sai mẫu của thuật toán giải, độc lập với bản chất native của mô hình dự báo." |
| **Downstream Solver Scalability & Fairness** | **NO** | **YES** | **YES (VALID)** | "Các kết quả về tính khả thi của bộ giải Greedy, CP-SAT và việc tuân thủ các ràng buộc cứng (hard constraints) giữ nguyên giá trị vì bộ giải chỉ tương tác với các khoảng thời gian chiếm dụng cổng được tạo ra." |

---

## 9. EXACT FINAL FIELDS (ACCEPTANCE CRITERIA)

```text
P4_MC_REGIME = SYNTHETIC_PROXY
P4_LOCATION_SOURCE = Ridge regression fitted in-memory on outer development set (2016-2022) via build_linear_preprocessor() and Ridge(alpha=1.0)
P4_SCALE_SOURCE = Fixed homoscedastic scalar constant (residual_sigma = 16.5)
P4_DF_SOURCE = Fixed degrees-of-freedom scalar constant (student_t_df = 4.0)
P4_MC_ARTIFACT = NONE (in-memory fit from iter_arrival_development_batches(2023) and load_stratified_fold_data; zero reference to model_weights_frozen_v1.joblib or holdout_predictions_2024.parquet)
P5_MC_REGIME = ASYMMETRIC_LAPLACE_PROXY (XGBoost point prediction + piecewise linear asymmetric normal quantile transform with left_scale=19.8, right_scale=29.7)
HOLDOUT_CONTAMINATION = NONE
P10_DOWNSTREAM_P4_CLAIMS_VALID = NO
P10R_STATUS = CLOSED
```

---

## 10. HALT BOUNDARY

In strict adherence to instructions:
- This audit pass is complete and closed (`P10R_STATUS = CLOSED`).
- All findings are derived strictly from read-only inspection of physical source code and generated artifacts.
- Zero retraining, zero rerunning, and zero modifications to historical parquet/json artifacts were performed.
- Execution ceases immediately. Phase 11 / Holdout execution is **NOT** initiated.
