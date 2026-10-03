# AEOLUS V4 — R34 P5 QUANTILE CONFIGURATION & CRPS MATHEMATICAL AUDIT REPORT
**Phase**: `R34 — P5 QUANTILE CONFIGURATION & CRPS MATHEMATICAL AUDIT`  
**Auditor**: Independent Forensic Auditor (Google DeepMind Antigravity)  
**Date**: `2026-10-03`  
**Mandate**: Audit Only — No Retrain / No Tuning / No Result Rewriting  
**Target Repository**: `D:/Study/Code/Python/Aelous`  
**Head Commit**: `c99b3e84b403527bcfb0f9612a1e2737c9f63701`  
**Active Branch**: `week5-model-parameters-export`  
**Audit Determination**: **`DISCREPANCY_RESOLVED`**  
**Final Status**: **`PASS`**  

---

## 1. EXECUTIVE SUMMARY & AUDIT MANDATE

Phase **R34** was conducted to resolve critical ambiguities in the documentation and certification package regarding candidate **`P5_quantile_regression`**:
1. **5 vs 9 Quantile Ambiguity**: Prior audit notes in Phase R28 described P5 as estimating 5 quantiles (`{0.10, 0.25, 0.50, 0.75, 0.90}`), whereas R32 referenced a "9-quantile estimator".
2. **Metric Conflation (16.85 min)**: Prior claims and summaries referred to `16.85 min` interchangeably as "discrete CRPS", "pinball loss", and "pinball loss / discrete CRPS".

Under a strict **AUDIT ONLY** protocol, direct code inspection, configuration auditing, raw prediction file analysis, and mathematical metric tracing were conducted across the repository.

### Key Forensic Audit Conclusions:
1. **P5 is Strictly a 9-Quantile Estimator**:
   - In all production source code, configuration files, trained models, and raw prediction parquets, P5 is configured with **9 pre-registered quantiles**:
     $$\alpha \in \{0.025, 0.050, 0.100, 0.250, 0.500, 0.750, 0.900, 0.950, 0.975\}$$
   - Raw out-of-fold prediction parquets possess exactly 9 quantile columns (`q_0.025` through `q_0.975`).
   - The "5-quantile" reference in R28 was an informal, underspecified textual note in audit scripts (`generate_r28_audit_artifacts_v2.py`), not a distinct model implementation.
2. **The 16.85 Metric is Mathematically `CRPS_QUANTILE_APPROXIMATION`**:
   - The value $16.85$ originates from $16.8477$ min in [`artifacts/manifests/academic_model_selection_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/manifests/academic_model_selection_v1.json) on 2023 development data.
   - It was computed via [`compute_quantile_crps_approximation()`](file:///D:/Study/Code/Python/Aelous/src/models/probabilistic/unified_evaluation.py#L85-L125) using trapezoidal integration of pinball losses across the quantile grid:
     $$\text{CRPS}_{\text{approx}} = \frac{2}{\alpha_{\max} - \alpha_{\min}} \int_{\alpha_{\min}}^{\alpha_{\max}} \rho_{\alpha}(y - q_{\alpha}) \, d\alpha$$
   - It is **NOT** Pinball Loss (mean pinball loss was $6.8781$ min on dev, and $6.8204$ min on holdout).
   - It is **NOT** Exact Discrete CRPS (no discrete CDF or PMF support is constructed).
   - Calling it "pinball loss / discrete CRPS" is mathematically erroneous and conflates two distinct loss magnitudes ($6.88$ vs $16.85$).
3. **Disclaimed Capabilities**:
   - `CONTINUOUS_DENSITY`: **`NOT_AVAILABLE`** (Calling `dist.cdf()` raises `CapabilityNotSupportedError`).
   - `CONTINUOUS_NLL`: **`NOT_SUPPORTED`** (`capabilities.nll = False`).
   - `CONTINUOUS_PIT`: **`NOT_SUPPORTED`** (`capabilities.pit = False`).
   - `CONTINUOUS_SAMPLING`: **`NOT_SUPPORTED`** (Calling `dist.sample()` raises `CapabilityNotSupportedError`).
4. **Claim Semantics Action**:
   - `P5_CLAIM_SEMANTICS`: **`NEEDS_REPAIR`** (Terminology in `CLAIM_03_PROBABILISTIC_P5_CRPS` must replace "discrete CRPS and pinball loss (16.85 min)" with "CRPS quantile approximation (16.85 min)").

---

## 2. STEP 1 & STEP 2 — P5 IMPLEMENTATION & 5 VS 9 QUANTILE RESOLUTION

### Source Code Lineage:
- **Candidate Class**: [`P5QuantileRegressionCandidate`](file:///D:/Study/Code/Python/Aelous/src/models/probabilistic/candidate_interfaces.py#L110-L165) in `src/models/probabilistic/candidate_interfaces.py`.
- **Underlying Regressor**: [`B4LightGBMQuantile`](file:///D:/Study/Code/Python/Aelous/src/models/probabilistic/baselines.py#L155-L210) in `src/models/probabilistic/baselines.py`.
- **Distribution Adapter**: [`QuantilePredictiveDistribution`](file:///D:/Study/Code/Python/Aelous/src/contracts/distribution.py#L320-L415) in `src/contracts/distribution.py`.
- **Quantile Definition**: [`PRE_REGISTERED_QUANTILES`](file:///D:/Study/Code/Python/Aelous/src/models/probabilistic/metrics.py#L25-L35) in `src/models/probabilistic/metrics.py`.

### Definitive Quantile Levels:
Inspection of `PRE_REGISTERED_QUANTILES` confirms:
```python
PRE_REGISTERED_QUANTILES: Final[tuple[float, ...]] = (
    0.025, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.975
)
```
- Total Quantile Count: **9**
- Monotone Rearrangement: Enforced via Chernozhukov et al. (2010) sorting across columns (`np.sort(q_matrix, axis=1)`) to guarantee non-crossing:
  $$q_{0.025}(x) \le q_{0.050}(x) \le q_{0.100}(x) \le q_{0.250}(x) \le q_{0.500}(x) \le q_{0.750}(x) \le q_{0.900}(x) \le q_{0.950}(x) \le q_{0.975}(x)$$

### Prediction Shape Verification:
Direct inspection of out-of-fold parquet predictions in `artifacts/probabilistic_benchmark/core_probabilistic_benchmark_v2/core_probabilistic_benchmark_v2/oof/P5_quantile_regression_fold_1.parquet`:
- File Shape: $(4000, 15)$
- Quantile Columns: `['q_0.025', 'q_0.050', 'q_0.100', 'q_0.250', 'q_0.500', 'q_0.750', 'q_0.900', 'q_0.950', 'q_0.975']` (Exactly 9 columns).

### Origin of the "5 Quantiles" Discrepancy:
In Phase R28, script `scripts/generate_r28_audit_artifacts_v2.py` line 227 contained hardcoded summary text:
`"distribution_type": "Discrete Quantiles on {0.10, 0.25, 0.50, 0.75, 0.90}"`.
The author transcribed a subset corresponding to common central intervals ($80\%$ and $50\%$) without referencing the immutable 9-quantile constant in `src.models.probabilistic.metrics`. No 5-quantile model was ever trained or certified.

---

## 3. STEP 3, STEP 4 & STEP 5 — TRACING THE 16.85 METRIC & MATHEMATICAL TAXONOMY

### Provenance of 16.85:
The value $16.85$ originates from Phase 8 / academic model selection V1 on the 2023 development set:
- File: [`artifacts/manifests/academic_model_selection_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/manifests/academic_model_selection_v1.json#L85)
- Raw Value: `"crps": 16.8477` (rounded to $16.85$)
- Accompanying Pinball Loss: `"mean_pinball_loss": 6.8781`
- Accompanying Coverages: `"cov_80": 0.7590`, `"cov_90": 0.8725`

On the 2024 post-holdout set ([`artifacts/post_holdout_v3/marginal_forecast_metrics_2024_v3.json`](file:///D:/Study/Code/Python/Aelous/artifacts/post_holdout_v3/marginal_forecast_metrics_2024_v3.json#L55)):
- Raw Value: `"crps": 16.7675`
- Accompanying Pinball Loss: `"mean_pinball_loss": 6.8204`
- Accompanying Coverages: `"coverage_80": 0.7424`, `"coverage_90": 0.8514`

### Mathematical Classification:

```text
CRPS_QUANTILE_APPROXIMATION
```

### Forensic Proof Against Misclassifications:
1. **Why it is NOT `PINBALL_LOSS`**:
   The asymmetric piecewise-linear pinball loss for a single quantile $\alpha$ is:
   $$\rho_{\alpha}(u) = u \left(\alpha - \mathbb{I}(u < 0)\right)$$
   The mean pinball loss across all 9 quantiles is $6.8781$ min (dev) and $6.8204$ min (holdout). Conflating $16.85$ with pinball loss is a factor-of-2.5 error.
2. **Why it is NOT `EXACT_DISCRETE_CRPS`**:
   Exact discrete CRPS requires evaluating $\text{CRPS}(F, y) = \sum_k \dots$ over a true finite discrete probability distribution with a well-defined CDF step function (as in `P1_empirical`). `QuantilePredictiveDistribution` contains no PMF, no CDF, and disclaims `crps_exact = False`.
3. **Why it IS `CRPS_QUANTILE_APPROXIMATION`**:
   The metric function [`compute_quantile_crps_approximation()`](file:///D:/Study/Code/Python/Aelous/src/models/probabilistic/unified_evaluation.py#L85-L125) implements the standard scoringRules quadrature:
   $$\text{CRPS}(F, y) \approx 2 \int_{0}^{1} \rho_{\alpha}(y - q_{\alpha}) \, d\alpha$$
   approximated using `np.trapezoid(pinball_mat, x=alphas_arr)` normalized by $(\alpha_{\max} - \alpha_{\min})$. Because the integrand is scaled by $2$, the resulting value ($pprox 16.85$) is approximately $2 \times 6.88$ (adjusted for boundary weights).

---

## 4. STEP 6, STEP 7 & STEP 8 — CONTINUOUS CAPABILITY AUDIT

Direct code inspection of [`QuantilePredictiveDistribution`](file:///D:/Study/Code/Python/Aelous/src/contracts/distribution.py#L320-L415) establishes the following architectural boundaries:

```python
@hybrid_contract_property
def capabilities(self) -> DistributionCapabilities:
    return DistributionCapabilities(
        mean=False,
        median=True,
        quantile=True,
        cdf=False,
        probability_ge=False,
        sample=False,
        nll=False,
        crps_exact=False,
        crps_approx=True,
        pit=False,
    )
```

1. **Continuous Density & CDF**: **`NOT_AVAILABLE`**  
   Calling `dist.cdf(x)` raises `CapabilityNotSupportedError("Quantile regression candidates do not provide a continuous CDF. Heuristic CDF synthesis is prohibited by protocol.")`.
2. **Continuous Likelihood / NLL**: **`NOT_SUPPORTED`**  
   `capabilities.nll = False`. Without a continuous probability density function $f(y)$, negative log-likelihood is mathematically undefined.
3. **Continuous Sampling**: **`NOT_SUPPORTED`**  
   Calling `dist.sample(n)` raises `CapabilityNotSupportedError("Generative sampling is unsupported for pure quantile regression models without full continuous CDF.")`.
4. **Probability Integral Transform (PIT)**: **`NOT_SUPPORTED`**  
   `capabilities.pit = False`. Evaluating $u = F(y)$ requires a valid continuous CDF. PIT evaluation on P5 is mathematically invalid and disallowed.

---

## 5. STEP 9 — P5 QUANTILE & METRIC SPECIFICATION MATRIX

| Attribute | Certified P5 Value / Status | Source Code / Evidence Location |
| :--- | :--- | :--- |
| **Quantile Count** | **9** | `src.models.probabilistic.metrics.PRE_REGISTERED_QUANTILES` |
| **Quantile Levels** | `[0.025, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.975]` | `src/models/probabilistic/metrics.py:30` |
| **Base Estimator** | Multi-head LightGBM (`B4LightGBMQuantile`) | `src/models/probabilistic/baselines.py:155` |
| **Monotone Rearrangement** | Yes (Chernozhukov et al., 2010) | `src/models/probabilistic/candidate_interfaces.py:155` |
| **Continuous Density** | **NO** (`NOT_AVAILABLE`) | `src/contracts/distribution.py:350` |
| **Continuous CDF** | **NO** (`NOT_AVAILABLE`) | `src/contracts/distribution.py:350` |
| **Continuous NLL** | **NO** (`NOT_SUPPORTED`) | `src/contracts/distribution.py:405` |
| **Continuous PIT** | **NO** (`NOT_SUPPORTED`) | `src/contracts/distribution.py:405` |
| **Continuous Sampler** | **NO** (`NOT_SUPPORTED`) | `src/contracts/distribution.py:365` |
| **CRPS Classification** | **`CRPS_QUANTILE_APPROXIMATION`** | `src/models/probabilistic/unified_evaluation.py:85` |
| **Dev 2023 Metric** | Approx CRPS: $16.85$ min (16.8477) \| Pinball: $6.88$ min | `artifacts/manifests/academic_model_selection_v1.json` |
| **Holdout 2024 Metric** | Approx CRPS: $16.77$ min (16.7675) \| Pinball: $6.82$ min | `artifacts/post_holdout_v3/marginal_forecast_metrics_2024_v3.json` |

---

## 6. STEP 10 — CLAIM BOUNDARY RECONCILIATION

### Current Wording in `CLAIM_03_PROBABILISTIC_P5_CRPS`:
> *"P5 Quantile Regression achieves champion discrete CRPS (16.85 min) and pinball loss under quantile interval evaluation; continuous density is not available."*

### Mathematical Assessment:
- The phrase *"discrete CRPS (16.85 min) and pinball loss"* is **misleading** because it implies $16.85$ is both discrete CRPS and pinball loss.
- In reality, pinball loss is $6.88$ min, while $16.85$ min is the trapezoidal pinball integral approximation of CRPS.

### Reconciled Scientific Wording:
> *"P5 Quantile Regression achieves champion CRPS quantile approximation (16.85 min dev, 16.77 min holdout) and mean pinball loss (6.88 min dev, 6.82 min holdout) across the pre-registered 9-quantile grid; continuous density, exact continuous NLL, continuous PIT calibration, and generative sampling are NOT AVAILABLE."*

---

## 7. STEP 11 & STEP 12 — ARTIFACTS & TEST SUITE VERIFICATION

### Deliverables Created:
1. [`artifacts/audit/r34_p5_quantile_config.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r34_p5_quantile_config.json) ([`.sha256`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r34_p5_quantile_config.json.sha256))
2. [`artifacts/audit/r34_p5_capability_forensics.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r34_p5_capability_forensics.json) ([`.sha256`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r34_p5_capability_forensics.json.sha256))
3. [`artifacts/audit/r34_p5_metric_reconciliation.parquet`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r34_p5_metric_reconciliation.parquet) ([`.sha256`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r34_p5_metric_reconciliation.parquet.sha256))
4. [`docs/audit/R34_P5_MATHEMATICAL_AUDIT.md`](file:///D:/Study/Code/Python/Aelous/docs/audit/R34_P5_MATHEMATICAL_AUDIT.md) ([`.sha256`](file:///D:/Study/Code/Python/Aelous/docs/audit/R34_P5_MATHEMATICAL_AUDIT.md.sha256))
5. [`tests/test_r34_p5_mathematical_audit.py`](file:///D:/Study/Code/Python/Aelous/tests/test_r34_p5_mathematical_audit.py)

### Pytest Verification (10/10 Passed):
```text
tests/test_r34_p5_mathematical_audit.py::test_final_quantile_count PASSED            [ 10%]
tests/test_r34_p5_mathematical_audit.py::test_final_quantile_levels PASSED           [ 20%]
tests/test_r34_p5_mathematical_audit.py::test_prediction_shape_matches_quantile_count PASSED [ 30%]
tests/test_r34_p5_mathematical_audit.py::test_metric_source_traceable PASSED         [ 40%]
tests/test_r34_p5_mathematical_audit.py::test_metric_classification PASSED           [ 50%]
tests/test_r34_p5_mathematical_audit.py::test_no_pinball_as_crps PASSED              [ 60%]
tests/test_r34_p5_mathematical_audit.py::test_no_approximation_as_exact_crps PASSED  [ 70%]
tests/test_r34_p5_mathematical_audit.py::test_no_unsupported_continuous_density PASSED [ 80%]
tests/test_r34_p5_mathematical_audit.py::test_no_unsupported_continuous_nll PASSED   [ 90%]
tests/test_r34_p5_mathematical_audit.py::test_no_unsupported_pit PASSED              [100%]

============================= 10 passed in 2.86s ==============================
```

---

## 8. ANSWERS TO MANDATORY FORENSIC QUESTIONS (Q1–Q12)

### Q1. Is final P5 a 5-quantile or 9-quantile estimator?
- **VERDICT**: **`9_QUANTILE_ESTIMATOR`**
- **SOURCE**: Model specification constant & OOF parquets
- **FILE**: [`src/models/probabilistic/metrics.py`](file:///D:/Study/Code/Python/Aelous/src/models/probabilistic/metrics.py#L30) & [`artifacts/probabilistic_benchmark/core_probabilistic_benchmark_v2/core_probabilistic_benchmark_v2/oof/P5_quantile_regression_fold_1.parquet`](file:///D:/Study/Code/Python/Aelous/artifacts/probabilistic_benchmark/core_probabilistic_benchmark_v2/core_probabilistic_benchmark_v2/oof/P5_quantile_regression_fold_1.parquet)
- **FIELD/CODE LOCATION**: `PRE_REGISTERED_QUANTILES`, `df.columns`
- **RAW EVIDENCE**: `len(PRE_REGISTERED_QUANTILES) == 9`, 9 quantile columns in parquet.
- **INTERPRETATION**: P5 models the distribution at 9 distinct quantile thresholds.
- **BOUNDARY**: The 5-quantile text in R28 was an incomplete documentation note.

### Q2. What are the exact final quantile levels?
- **VERDICT**: **`PROVEN`**
- **SOURCE**: Source code tuple constant
- **FILE**: [`src/models/probabilistic/metrics.py`](file:///D:/Study/Code/Python/Aelous/src/models/probabilistic/metrics.py#L30)
- **FIELD/CODE LOCATION**: `PRE_REGISTERED_QUANTILES`
- **RAW EVIDENCE**: `(0.025, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.975)`
- **INTERPRETATION**: Covers the 50%, 80%, 90%, and 95% central forecast intervals.
- **BOUNDARY**: Does not provide arbitrary user-specified continuous quantiles.

### Q3. Which configuration generated the certified P5 result?
- **VERDICT**: **`PROVEN`**
- **SOURCE**: Model selection pipeline & candidate factory
- **FILE**: [`src/models/probabilistic/candidate_interfaces.py`](file:///D:/Study/Code/Python/Aelous/src/models/probabilistic/candidate_interfaces.py#L110)
- **FIELD/CODE LOCATION**: `P5QuantileRegressionCandidate.__init__`
- **RAW EVIDENCE**: `B4LightGBMQuantile(alphas=PRE_REGISTERED_QUANTILES, n_estimators=80, learning_rate=0.05, seed=202601)` with monotone rearrangement sorting.
- **INTERPRETATION**: Multi-head LightGBM trees with post-hoc monotone sorting.
- **BOUNDARY**: No neural or spline quantile representations were evaluated.

### Q4. What exactly is the 16.85 metric?
- **VERDICT**: **`CRPS_QUANTILE_APPROXIMATION`**
- **SOURCE**: Academic selection V1 manifest
- **FILE**: [`artifacts/manifests/academic_model_selection_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/manifests/academic_model_selection_v1.json)
- **FIELD/CODE LOCATION**: `ranking_free_comparison_table.probabilistic_models.P5_quantile_regression.crps`
- **RAW EVIDENCE**: `16.8477` (rounded to $16.85$)
- **INTERPRETATION**: The trapezoidal quadrature integral of pinball losses across the 9 quantiles on the 2023 development set.
- **BOUNDARY**: Evaluated on 2023 dev data; 2024 holdout value is $16.7675$.

### Q5. Is it pinball loss?
- **VERDICT**: **`NO`**
- **SOURCE**: Evaluation metric definition
- **FILE**: [`src/models/probabilistic/unified_evaluation.py`](file:///D:/Study/Code/Python/Aelous/src/models/probabilistic/unified_evaluation.py#L110)
- **FIELD/CODE LOCATION**: `compute_quantile_crps_approximation`
- **RAW EVIDENCE**: Pinball loss on the same data was $6.8781$ min. The metric $16.85$ scales integrated pinball loss by a factor of $2$.
- **INTERPRETATION**: Conflating the two creates a 2.5x magnitude distortion.
- **BOUNDARY**: Pinball loss is a single-quantile loss; CRPS integrates over all quantiles.

### Q6. Is it exact discrete CRPS?
- **VERDICT**: **`NO`**
- **SOURCE**: Distribution contract capabilities
- **FILE**: [`src/contracts/distribution.py`](file:///D:/Study/Code/Python/Aelous/src/contracts/distribution.py#L405)
- **FIELD/CODE LOCATION**: `QuantilePredictiveDistribution.capabilities.crps_exact`
- **RAW EVIDENCE**: `crps_exact = False`
- **INTERPRETATION**: No discrete probability mass function or discrete CDF support exists.
- **BOUNDARY**: Exact discrete CRPS is supported only by `P1_empirical`.

### Q7. Is it CRPS quantile approximation?
- **VERDICT**: **`YES`**
- **SOURCE**: Evaluation function implementation
- **FILE**: [`src/models/probabilistic/unified_evaluation.py`](file:///D:/Study/Code/Python/Aelous/src/models/probabilistic/unified_evaluation.py#L85)
- **FIELD/CODE LOCATION**: `compute_quantile_crps_approximation`
- **RAW EVIDENCE**: Uses `np.trapezoid(pinball_mat, x=alphas_arr)` normalized by $(lpha_{\max} - lpha_{\min})$.
- **INTERPRETATION**: Conforms mathematically to Gneiting & Raftery (2007) quantile CRPS approximation.
- **BOUNDARY**: Accuracy is bounded by the discretization grid of 9 quantiles.

### Q8. Does P5 provide a continuous density?
- **VERDICT**: **`NO`**
- **SOURCE**: Distribution contract implementation
- **FILE**: [`src/contracts/distribution.py`](file:///D:/Study/Code/Python/Aelous/src/contracts/distribution.py#L350)
- **FIELD/CODE LOCATION**: `QuantilePredictiveDistribution.cdf`
- **RAW EVIDENCE**: `raise CapabilityNotSupportedError("do not provide a continuous CDF")`
- **INTERPRETATION**: P5 is strictly a non-parametric quantile regressor.
- **BOUNDARY**: Ad-hoc smoothing or heuristic interpolation is explicitly forbidden.

### Q9. Does P5 support continuous NLL?
- **VERDICT**: **`NO`**
- **SOURCE**: Distribution capabilities flag
- **FILE**: [`src/contracts/distribution.py`](file:///D:/Study/Code/Python/Aelous/src/contracts/distribution.py#L405)
- **FIELD/CODE LOCATION**: `DistributionCapabilities.nll`
- **RAW EVIDENCE**: `nll = False`
- **INTERPRETATION**: Likelihood cannot be computed without a probability density function.
- **BOUNDARY**: Any claim of NLL for P5 is invalid.

### Q10. Does P5 support PIT calibration?
- **VERDICT**: **`NO`**
- **SOURCE**: Distribution capabilities flag
- **FILE**: [`src/contracts/distribution.py`](file:///D:/Study/Code/Python/Aelous/src/contracts/distribution.py#L405)
- **FIELD/CODE LOCATION**: `DistributionCapabilities.pit`
- **RAW EVIDENCE**: `pit = False`
- **INTERPRETATION**: PIT transform requires $F(y)$, which does not exist for P5.
- **BOUNDARY**: Coverage can be assessed on individual quantiles, but continuous PIT uniformity cannot.

### Q11. Does P5 support continuous sampling?
- **VERDICT**: **`NO`**
- **SOURCE**: Distribution contract implementation
- **FILE**: [`src/contracts/distribution.py`](file:///D:/Study/Code/Python/Aelous/src/contracts/distribution.py#L365)
- **FIELD/CODE LOCATION**: `QuantilePredictiveDistribution.sample`
- **RAW EVIDENCE**: `raise CapabilityNotSupportedError("Generative sampling is unsupported")`
- **INTERPRETATION**: Cannot generate synthetic flight arrival delay draws for Monte Carlo gate simulation.
- **BOUNDARY**: P5 is restricted downstream to its median (q50) scalar estimate.

### Q12. Is the final terminology mathematically correct?
- **VERDICT**: **`NEEDS_REPAIR`**
- **SOURCE**: Final claim boundary audit
- **FILE**: [`artifacts/audit/final_claim_boundary_audit_v4.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/final_claim_boundary_audit_v4.json#L42)
- **FIELD/CODE LOCATION**: `CLAIM_03_PROBABILISTIC_P5_CRPS`
- **RAW EVIDENCE**: Text currently states *"champion discrete CRPS (16.85 min) and pinball loss"*.
- **INTERPRETATION**: Conflates pinball loss ($6.88$) with approximate CRPS ($16.85$).
- **BOUNDARY**: Must be amended to explicitly state "CRPS quantile approximation (16.85 min)".

---

## 9. FINAL STATUS SUMMARY BLOCK

```text
R34_STATUS:
PASS

FINAL_P5_QUANTILE_COUNT:
9

FINAL_P5_QUANTILE_LEVELS:
[0.025, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.975]

P5_16_85_METRIC:
CRPS_QUANTILE_APPROXIMATION

P5_CONTINUOUS_DENSITY:
NO

P5_NLL:
NOT_SUPPORTED

P5_PIT:
NOT_SUPPORTED

P5_CONTINUOUS_SAMPLING:
NOT_SUPPORTED

P5_CLAIM_SEMANTICS:
NEEDS_REPAIR
```
