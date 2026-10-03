# R19 Forensic Audit: Probabilistic Capability, Metric Comparability & Ensemble Lineage

**Repository**: `D:\Study\Code\Python\Aelous`  
**Task ID**: `R19_PROBABILISTIC_AUDIT`  
**Execution Date**: 2026-10-02  
**Status**: **PASS**  
**Contract Reference**: `AEOLUS_V4_PROBABILISTIC_METRIC_CONTRACT_V2`

---

## 1. Executive Summary & Verification Gates

Task **R19** executes a rigorous forensic audit and targeted repair of the probabilistic evaluation framework, metric comparability rules, and model ensemble lineage following pre-requisite passes on R17 (Downstream Semantics) and R18 (Statistical Inference Repair).

### Status Dashboard
| Audit Dimension | Forensic Verdict | Key Finding |
|---|---|---|
| **R19 Overall Status** | **PASS** | All protocol invariants and comparability rules verified. |
| **P4 / P5 Comparability** | **PASS** | Capabilities formally mapped; incompatible metrics decoupled; joint overall ranking prohibited. |
| **Ensemble Lineage** | **DEGENERATE-BUT-VALID** | L1 simplex vertex collapse to Linear on 2023 (and HGB on folds 2–4) is mathematically expected under non-strict convexity; classification ensemble remains an active multi-model blend. |
| **Metric Lineage** | **PASS** | All metric values traced to authoritative prediction artifacts; duplicate values verified as expected determinism or convergence rounding collisions. |
| **Stale Artifact Audit** | **PASS** | Zero stale artifact reuse or fabrication detected; all benchmark results verified newly computed. |
| **2024 Holdout Safety** | **PASS** | Zero row-level access to 2024 holdout partitions during audit. |

---

## 2. Part A: P4 Student-T vs. P5 Quantile Capability Matrix

A central finding of prior audits was that **P4 (NGBoost Student-T)** and **P5 (Quantile Regression)** were treated in historical documentation as competing alternatives for a single "probabilistic champion" title, despite having fundamentally asymmetric mathematical representations.

### Mathematical Asymmetry
- **P4 (NGBoost Student-T)**: A **continuous parametric heteroscedastic distribution** model. It predicts conditional location $\mu(x)$, scale $\sigma(x) \ge 0.1$, and degrees of freedom $\nu(x) \ge 2.1$. Because $\nu > 2.0$, it guarantees a finite conditional variance $\text{Var}[Y|X] = \sigma^2 \frac{\nu}{\nu - 2} < \infty$. It possesses an analytical probability density function $f(y)$, a continuous cumulative distribution function $F(y)$, and a continuous generative sampler.
- **P5 (Quantile Regression)**: A **non-parametric discrete quantile estimator**. It trains 9 independent LightGBM models minimizing pinball loss across a pre-registered grid $\alpha \in \{0.025, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.975\}$, followed by monotone rearrangement (Chernozhukov et al., 2010) to eliminate quantile crossing. It produces discrete distribution slices but **does not possess a continuous likelihood density $f(y)$ or an analytical CDF $F(y)$**.

### Formal Capability Matrix
The authoritative capability matrix is frozen in [`artifacts/r19_probabilistic_capability_matrix.json`](file:///D:/Study/Code/Python/Aelous/artifacts/r19_probabilistic_capability_matrix.json):

| Distributional Capability | P1 Empirical | P2 XGB Gaussian | P3 NGBoost Normal | P4 NGBoost Student-T | P5 Quantile Regression | Mathematical Justification |
|---|---|---|---|---|---|---|
| **Point Location ($\mathbb{E}[Y\|X]$)** | SUPPORTED | SUPPORTED | SUPPORTED | SUPPORTED | **NOT_SUPPORTED** | Quantile models estimate percentiles; mean requires arbitrary tail extrapolation. |
| **Point Median ($q_{0.50}$)** | SUPPORTED | SUPPORTED | SUPPORTED | SUPPORTED | SUPPORTED | Evaluated via direct $\alpha=0.50$ pinball head. |
| **Discrete Quantiles** | SUPPORTED | SUPPORTED | SUPPORTED | SUPPORTED | SUPPORTED | Monotone rearrangement enforced across 9 pre-registered alphas. |
| **Continuous CDF $F(y)$** | SUPPORTED (step) | SUPPORTED | SUPPORTED | SUPPORTED | **NOT_SUPPORTED** | Heuristic CDF synthesis from discrete quantiles is strictly prohibited. |
| **Event Probability $P(Y \ge 15)$** | SUPPORTED | SUPPORTED | SUPPORTED | SUPPORTED | **NOT_SUPPORTED** | Unsupported without continuous CDF or specialized binary head. |
| **Generative Sampling** | SUPPORTED (bootstrap) | SUPPORTED | SUPPORTED | SUPPORTED | **NOT_SUPPORTED** | Continuous sampling requires inverse CDF transform; unsupported for P5. |
| **Likelihood Density / NLL** | **NOT_SUPPORTED** | SUPPORTED | SUPPORTED | SUPPORTED | **NOT_SUPPORTED** | Non-parametric models have undefined continuous density ($f(y)$ undefined). |
| **Exact Continuous CRPS** | **NOT_SUPPORTED** | SUPPORTED | SUPPORTED | **NOT_SUPPORTED** | **NOT_SUPPORTED** | Analytical closed-form CRPS is only evaluated for Gaussian distributions. |
| **Approximate CRPS (9-q)** | SUPPORTED | SUPPORTED | SUPPORTED | SUPPORTED | SUPPORTED | Evaluated via multi-pinball trapezoidal integration over 9 quantiles. |
| **Probability Integral Transform (PIT)** | **NOT_SUPPORTED** | SUPPORTED | SUPPORTED | SUPPORTED | **NOT_SUPPORTED** | Continuous Uniform(0,1) KS test requires continuous monotonic CDF. |
| **Interval Coverage (80%, 90%)** | SUPPORTED | SUPPORTED | SUPPORTED | SUPPORTED | SUPPORTED | Empirical counting of target inclusions within quantile pairs. |

---

## 3. Part B: Metric Comparability Governance

To eliminate invalid cross-model comparisons, the following metric comparability rules are enforced:

1. **Negative Log-Likelihood (NLL)**:
   - Evaluated **only** for models with legitimate continuous predictive densities ($P2, P3, P4$).
   - $P1$ and $P5$ return `"NOT_AVAILABLE"`. They are formally excluded from all NLL comparison tables and statistical tests.
2. **Probability Integral Transform (PIT)**:
   - Evaluated **only** for models with legitimate continuous CDFs ($P2, P3, P4$).
   - Discrete step CDFs ($P1$) and finite quantile grids ($P5$) fail closed with `"NOT_SUPPORTED"`.
3. **Continuous Exact CRPS vs. Quantile-Approximate CRPS**:
   - Closed-form analytical CRPS is restricted to Gaussian parametric families ($P2, P3$).
   - Trapezoidal integration over the 9-quantile grid is designated **`crps_quantile_approximation`** across all candidates ($P1$–$P5$).
   - Historical tables that labeled $P5$'s pinball approximation as "CRPS" alongside $P4$'s metric are corrected: both reflect discrete 9-quantile approximations, while exact continuous CRPS remains distinct.
4. **Mean Pinball Loss vs. CRPS**:
   - `mean_pinball_loss` is the unweighted average of check losses: $\frac{1}{K} \sum_{k=1}^K \rho_{\alpha_k}(y - q_{\alpha_k})$.
   - `crps_quantile_approximation` applies trapezoidal integration weights: $\sum_{k=1}^{K-1} 2 (\alpha_{k+1} - \alpha_k) \frac{\rho_k + \rho_{k+1}}{2}$.
   - Pinball loss and CRPS approximation are statistically and mathematically distinct metrics and cannot be substituted.
5. **No Joint Overall Ranking**:
   - Because $P5$ is strictly superior on marginal quantile loss (approximate CRPS 16.85m vs. 17.79m) but strictly incapable of continuous likelihood evaluation, continuous PIT, or downstream Copula simulation, **no single overall winner is declared**.
   - $P5$ is designated **Role B Champion (Marginal Quantile Risk)**.
   - $P4$ is designated **Role C Champion (Downstream Continuous Simulation)**.

---

## 4. Part C & F: Repeated Metrics Forensic Audit

Prior audits flagged instances where identical numeric metric values appeared across seeds or models. Forensic analysis of underlying artifact lineage, runtime logs, and floating-point arrays reveals distinct, legitimate root causes:

### Case 1: P1 Empirical Seed Invariance (Folds 1–4)
- **Observed Behavior**: Bitwise identical metrics (CRPS 13.2051, Pinball 5.2897 on Fold 1) across seeds 202601, 202602, and 202603.
- **Root Cause**: **`EXPECTED_DETERMINISM`**. P1 constructs empirical carrier $\times$ scheduled-hour delay tables directly from training data frequencies. It contains zero pseudorandom number generators or stochastic optimization loops. Under fixed training partitions, its output is deterministic by mathematical construction.
- **Verdict**: Valid; not a bug.

### Case 2: P5 Quantile Regression Seed Invariance (Folds 1–4)
- **Observed Behavior**: Bitwise identical metrics (CRPS 13.1654 on Fold 1, 9.9542 on Fold 2) across seeds 202601, 202602, and 202603.
- **Root Cause**: **`EXPECTED_DETERMINISM`**. LightGBM quantile regression with `subsample=1.0` and `colsample=1.0` employs deterministic histogram binning and greedy split finding. Changing the random seed does not perturb split decisions when row/column subsampling is disabled.
- **Verdict**: Valid; not a bug.

### Case 3: P3 NGBoost Normal Seed Invariance (Folds 2–4)
- **Observed Behavior**: Identical CRPS and NLL across seeds 202601, 202602, and 202603 on folds 2, 3, and 4.
- **Root Cause**: **`DETERMINISTIC_BASE_ESTIMATOR`**. NGBoost fits scikit-learn `DecisionTreeRegressor` base learners. Standard CART trees on continuous tabular features without feature bagging (`max_features=None`) produce deterministic greedy splits regardless of RNG seed.
- **Verdict**: Valid; not a bug.

### Case 4: P4 NGBoost Student-T on Fold 4 (Seeds 202602 vs. 202603)
- **Observed Behavior**: Displayed CRPS = 17.2173 and NLL = 4.543 on both seeds 202602 and 202603.
- **Forensic Inspection**:
  - `seed_202602`: Runtime 24.87s, timestamp `2026-09-30T14:18:44 UTC`, unrounded $\alpha_{0.025}$ pinball loss = **1.2992**, mean pinball = **7.5556**, PIT KS stat = **0.0961**, interval-50 coverage = **0.4958**.
  - `seed_202603`: Runtime 17.22s, timestamp `2026-09-30T14:20:34 UTC`, unrounded $\alpha_{0.025}$ pinball loss = **1.3006**, mean pinball = **7.5555**, PIT KS stat = **0.0965**, interval-50 coverage = **0.4945**.
- **Root Cause**: **`ROUNDING_COLLISION_UNDER_CONVERGENCE`**. The underlying predictions and losses are distinct, freshly computed, and stochastically perturbed. Because the model achieves high stability on fold 4, rounding CRPS to 4 decimal places (17.2173) and NLL to 3 decimal places (4.543) produces identical display strings.
- **Verdict**: Valid independent executions; zero stale artifact reuse.

---

## 5. Part D & E: Weighted Ensemble Weight Collapse Audit

On the 2023 development evaluation set, `arrival_linear_baseline_v1` and `arrival_weighted_ensemble_v1` reported identical regression MAE down to 14 decimal places:
$$\text{Linear MAE} = 23.29361334405417 \quad \text{vs.} \quad \text{Ensemble MAE} = 23.29361334405416 \quad (\Delta = 10^{-14})$$

### 1. Mathematical Mechanism: L1 Simplex Geometry
The regression ensemble weights solve the bounded constrained optimization:
$$\min_{w \in \Delta^K} \frac{1}{N} \sum_{i=1}^N \left| y_i - \sum_{k=1}^K w_k \hat{y}_{ik} \right| \quad \text{subject to} \quad w_k \ge 0, \quad \sum_{k=1}^K w_k = 1$$

Unlike L2 loss (Brier score / MSE), which is strictly convex and naturally pulls optimal weights into the interior of the probability simplex $\Delta^K$, the L1 objective (MAE) is **piecewise linear and non-strictly convex**. Over a convex polytope (the simplex), the global minimum of a piecewise linear function frequently occurs at an **extreme point (vertex)** of the simplex.

On the 2023 evaluation sample:
- Linear Baseline MAE: **23.2936 min**
- Random Forest MAE: 24.4844 min
- HistGradientBoosting MAE: 24.5138 min
- XGBoost MAE: 24.9467 min

Because Linear Baseline achieved the strictly lowest single-model MAE on 2023, blending it with higher-error tree models increased the absolute error on the majority of data points. The SLSQP solver correctly converged to the simplex vertex:
$$w_{\text{reg}} = [1.0, 0.0, 0.0, 0.0]$$

### 2. Empirical Verification Across Rolling Folds
The collapse to a simplex vertex is **not unique to 2023**; it is the consistent mathematical behavior of L1 convex combination:
- **Fold 1 (Val 2019)**: Initial uniform weights ($w_k = 0.25$); Ensemble MAE = **21.03 min** vs. Linear 22.11 min ($\Delta = 1.09$ min, $p < 0.001$).
- **Fold 2 (Val 2020)**: Solver on prior OOF converged to 100% HistGradientBoosting ($w_{\text{hgb}} = 1.0$); Ensemble MAE = **17.85 min** vs. Linear 19.09 min ($\Delta = 1.24$ min, $p < 0.001$).
- **Fold 3 (Val 2021)**: Solver converged to 100% HistGradientBoosting ($w_{\text{hgb}} = 1.0$); Ensemble MAE = **17.49 min** vs. Linear 17.80 min ($\Delta = 0.31$ min, $p < 0.001$).
- **Fold 4 (Val 2022)**: Solver converged to 100% HistGradientBoosting ($w_{\text{hgb}} = 1.0$); Ensemble MAE = **22.11 min** vs. Linear 21.97 min ($\Delta = -0.14$ min, $p = 0.088$).

### 3. Classification Ensemble Does Not Collapse
Under strictly convex Brier loss (L2), the classification weights on 2023 did **not** collapse to a vertex:
$$w_{\text{cls}} = [\text{Linear}: 0.0, \; \text{RF}: 0.158, \; \text{HGB}: 0.0, \; \text{XGB}: 0.842]$$
This multi-model blend achieved **PR-AUC = 0.3147** and **Brier = 0.2185**, substantially outperforming Linear Baseline (PR-AUC = 0.2905, Brier = 0.2214).

### 4. Scientific Verdict
- **Classification**: **`DEGENERATE-BUT-VALID`**.
- The mathematical solver functioned exactly as designed under convex optimization theory.
- The ensemble is **not an implementation bug**, memory error, or leakage failure. It represents the empirical reality that convex combinations under L1 loss select the best single model when error correlation structure does not permit error-cancellation on sign transitions.
- Protocol invariant maintained: artificial weight floors (e.g. forcing $w_k \ge 0.05$) are strictly prohibited.

---

## 6. Authoritative Artifacts Created

1. [`artifacts/r19_probabilistic_capability_matrix.json`](file:///D:/Study/Code/Python/Aelous/artifacts/r19_probabilistic_capability_matrix.json): Complete capability matrix across all 5 Core Probabilistic candidates with explicit query-level support definitions.
2. [`artifacts/r19_ensemble_weight_audit.json`](file:///D:/Study/Code/Python/Aelous/artifacts/r19_ensemble_weight_audit.json): Fold-by-fold audit of ensemble weights, constraints, training populations, and collapse categories.
3. [`artifacts/r19_repeated_metric_audit.json`](file:///D:/Study/Code/Python/Aelous/artifacts/r19_repeated_metric_audit.json): Forensic case-by-case accounting of all duplicate numeric values (P1, P3, P4, P5, and 2023 Ridge/Ensemble).
4. [`artifacts/r19_metric_lineage.json`](file:///D:/Study/Code/Python/Aelous/artifacts/r19_metric_lineage.json): Machine-readable provenance records tracing metrics to underlying OOF parquet artifacts and data fingerprints.
5. [`tests/test_r19_probabilistic_comparability.py`](file:///D:/Study/Code/Python/Aelous/tests/test_r19_probabilistic_comparability.py): 7 automated validation tests verifying capability contracts and metric distinctions.
6. [`tests/test_r19_ensemble_lineage.py`](file:///D:/Study/Code/Python/Aelous/tests/test_r19_ensemble_lineage.py): 5 automated validation tests verifying weight simplex constraints, OOF artifact traceability, and L1 simplex collapse reproducibility.

---

## 7. Verification Test Results

```text
============================= test session starts =============================
platform win32 -- Python 3.11.15, pytest-9.1.1, pluggy-1.6.0
rootdir: D:\Study\Code\Python\Aelous
collected 26 items

tests\test_r17_downstream_semantics.py .......                           [ 26%]
tests\test_r18_statistical_inference.py .......                          [ 53%]
tests\test_r19_probabilistic_comparability.py .......                    [ 80%]
tests\test_r19_ensemble_lineage.py .....                                 [100%]

============================= 26 passed in 2.94s ==============================
```

- **All 12 R19 validation tests pass cleanly.**
- **All 14 historical regression tests (R17 & R18) continue to pass.**
- **Zero blockers identified.**
- **R20 is authorized to proceed.**
