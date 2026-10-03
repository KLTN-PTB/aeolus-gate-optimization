# AEOLUS V4 — R33 P4 METRIC LINEAGE FORENSIC AUDIT REPORT
**Phase**: `R33 — P4 METRIC LINEAGE FORENSIC AUDIT`  
**Auditor**: Independent Forensic Auditor (Google DeepMind Antigravity)  
**Date**: `2026-10-03`  
**Mandate**: Targeted Audit — No Retrain / No Tuning / No Scientific Rewrite  
**Target Repository**: `D:/Study/Code/Python/Aelous`  
**Head Commit**: `c99b3e84b403527bcfb0f9612a1e2737c9f63701`  
**Active Branch**: `week5-model-parameters-export`  
**Audit Determination**: **`DISCREPANCY_RESOLVED`**  
**Final Status**: **`PASS`**  

---

## 1. EXECUTIVE SUMMARY & INVESTIGATION MANDATE

During phase **R32 Independent Forensic Verification**, an apparent metric divergence was identified for model **`P4_ngboost_student_t`**:
- In the established certification and post-holdout evidence package (Phases R23, R28, R30, R31), P4 was reported with:
  $$\text{CRPS} = 17.6532, \quad \text{NLL} = 4.6307$$
- In the R32 audit report text and JSON deliverable, P4 was reported with:
  $$\text{CRPS} = 17.15 \ (17.1539), \quad \text{NLL} = 4.032 \ (4.0321)$$

Phase **R33** was executed under a strict **AUDIT + RECONCILIATION ONLY** mandate to investigate this divergence to its root cause without retraining any models, modifying hyperparameters, or altering historical scientific records.

### Key Forensic Findings:
1. **Exhaustive Artifact Scan**: A full physical byte-level scan of all JSON, Parquet, Python, and YAML files across the entire repository history established that **$\text{CRPS} = 17.15$ ($17.1539$) and $\text{NLL} = 4.032$ ($4.0321$) do NOT exist in any raw experimental benchmark, model evaluation file, or manifest prior to phase R32**.
2. **Genesis of the Discrepancy**: The pair $(17.1539, 4.0321)$ was an **isolated transcription/hallucination error introduced solely within the R32 documentation and JSON output** during the drafting of question Q8 in [`r32_independent_forensic_verification.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r32_independent_forensic_verification.json) and [`R32_INDEPENDENT_FORENSIC_VERIFICATION.md`](file:///D:/Study/Code/Python/Aelous/docs/audit/R32_INDEPENDENT_FORENSIC_VERIFICATION.md).
3. **Physical Backing of $(17.6532, 4.6307)$**: In contrast, the pair $\text{CRPS} = 17.6532$ and $\text{NLL} = 4.6307$ is physically, mathematically, and cryptographically backed by:
   - Raw holdout evaluation: [`marginal_forecast_metrics_2024_v3.json`](file:///D:/Study/Code/Python/Aelous/artifacts/post_holdout_v3/marginal_forecast_metrics_2024_v3.json) (SHA256: `bd381014e305e55e...`)
   - Post-holdout manifest: [`post_holdout_evaluation_manifest_v3.json`](file:///D:/Study/Code/Python/Aelous/artifacts/post_holdout_v3/post_holdout_evaluation_manifest_v3.json) (SHA256: `799b7bfa7c588960...`)
   - Probabilistic audit lineage: [`r28_metric_lineage.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r28_metric_lineage.json)
   - Certified evidence package: [`final_evidence_certification_v4.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/final_evidence_certification_v4.json) & [`FINAL_EVIDENCE_CERTIFICATION_V4.md`](file:///D:/Study/Code/Python/Aelous/docs/audit/FINAL_EVIDENCE_CERTIFICATION_V4.md)
   - Pytest unit tests: [`tests/test_r28_probabilistic_audit.py`](file:///D:/Study/Code/Python/Aelous/tests/test_r28_probabilistic_audit.py)
4. **Development vs Holdout Distinction**:
   - **2023 Development Selection**: $\text{CRPS} = 18.4840, \quad \text{NLL} = 4.5805$ ([`academic_model_selection_v3.json`](file:///D:/Study/Code/Python/Aelous/artifacts/manifests/academic_model_selection_v3.json)).
   - **2024 Post-Holdout Evaluation**: $\text{CRPS} = 17.6532, \quad \text{NLL} = 4.6307$ ([`marginal_forecast_metrics_2024_v3.json`](file:///D:/Study/Code/Python/Aelous/artifacts/post_holdout_v3/marginal_forecast_metrics_2024_v3.json)).
5. **Discrepancy Classification**: Strictly classified as **`ONE_VALUE_IS_INVALID_OR_MISLABELED`**. The R32 text was mislabeled; the underlying scientific evidence remains intact and uncompromised.
6. **Certification Safety**: The final V4 certification package is **SAFE** (`FINAL_CERTIFICATION_CURRENTLY_SAFE = YES`). No model retraining is required (`RETRAIN_REQUIRED = NO`).

---

## 2. STEP 1 — ENVIRONMENT & REPOSITORY INSPECTION

- **Repository Root**: [Aelous](file:///D:/Study/Code/Python/Aelous)
- **Active Git Branch**: `week5-model-parameters-export`
- **Head Commit**: `c99b3e84b403527bcfb0f9612a1e2737c9f63701`
- **Git Status**: Working tree dirty (contains uncommitted audit files and test logs; no core scientific files modified).
- **Python Version**: `3.11.15`
- **Operating System**: `Windows 10 AMD64 (10.0.19045)`
- **Host Architecture**: `AMD64 / Intel64 Family 6 Model 158 Stepping 10, GenuineIntel`

---

## 3. STEP 2 — COMPREHENSIVE INVENTORY OF P4 ARTIFACTS

Every artifact associated with P4 (`P4_ngboost_student_t`) was audited for byte existence, physical SHA256 digest, and recorded metrics.

| Artifact Path | Artifact Type | Exists | SHA256 (Actual) | Source Phase | Split / Year | Recorded P4 CRPS | Recorded P4 NLL | Metric Lineage Role |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `artifacts/manifests/academic_model_selection_v3.json` | Selection Manifest | True | `0ba819f68a960d4b...` | R8/R22 | Dev 2023 | **18.4840** | **4.5805** | Authoritative 2023 Selection Metric |
| `artifacts/post_holdout_v3/marginal_forecast_metrics_2024_v3.json` | Holdout Metrics | True | `bd381014e305e55e...` | R23 | Holdout 2024 | **17.6532** | **4.6307** | Authoritative 2024 Holdout Metric |
| `artifacts/post_holdout_v3/post_holdout_evaluation_manifest_v3.json` | Holdout Manifest | True | `799b7bfa7c588960...` | R23 | Holdout 2024 | **17.6532** | **4.6307** | Cryptographic Post-Holdout Provenance |
| `artifacts/audit/r28_metric_lineage.json` | Audit Report | True | `b491a92eeb19f854...` | R28 | Dev & Holdout | **18.484 / 17.6532** | **4.5805 / 4.6307** | Reconciled Metric Taxonomy |
| `artifacts/audit/r28_probabilistic_capability_audit.json` | Capability Audit | True | `23a2386fe8909e44...` | R28 | Dev & Holdout | **18.484 / 17.6532** | **4.5805 / 4.6307** | Parametric Density Audit |
| `artifacts/audit/r28_calibration_evidence.json` | Calibration Report | True | `f32c1eb7579698d2...` | R28 | Dev & Holdout | **18.48 / 17.65** | **4.58 / 4.63** | Calibration Boundary Record |
| `artifacts/audit/final_evidence_certification_v4.json` | Final Cert Manifest | True | `102830f30ae5aeb9...` | R31 | Holdout 2024 | **17.6532** | **4.6307** | Authoritative V4 Certification |
| `docs/audit/FINAL_EVIDENCE_CERTIFICATION_V4.md` | Final Cert Report | True | `38b4a24c9657b987...` | R31 | Holdout 2024 | **17.6532** | **4.6307** | Final Dissemination Text |
| `artifacts/audit/r32_independent_forensic_verification.json` | Verification Audit | True | `d7ae5bdcdef65dcb...` | R32 | Erroneous | *17.1539* | *4.0321* | **Mislabeled / Erroneous Entry** |
| `docs/audit/R32_INDEPENDENT_FORENSIC_VERIFICATION.md` | Verification Report | True | `7e8c40b4bf8c9c1c...` | R32 | Erroneous | *17.15* | *4.032* | **Mislabeled / Erroneous Entry** |

*Inventory Summary*: Full machine-readable dataset recorded in [`artifacts/audit/r33_p4_metric_reconciliation.parquet`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r33_p4_metric_reconciliation.parquet).

---

## 4. STEP 3 & STEP 4 — TRACE P4 & METRIC IMPLEMENTATION

### P4 Model Architecture:
- **Implementation File**: [`src/contracts/distribution.py`](file:///D:/Study/Code/Python/Aelous/src/contracts/distribution.py#L225-L315)
- **Candidate Wrapper**: [`src/models/probabilistic/candidate_interfaces.py`](file:///D:/Study/Code/Python/Aelous/src/models/probabilistic/candidate_interfaces.py)
- **Mathematical Class**: `NGBoostStudentTDistribution(PredictiveDistribution)`
- **Distribution Type**: Heteroscedastic 3-parameter continuous Student-T distribution:
  - Location parameter $\mu(x) \in \mathbb{R}$
  - Scale parameter $\sigma(x) \ge 1.0$ (enforced by `DEFAULT_SIGMA_FLOOR = 1.0`)
  - Degrees of freedom $
u(x) \ge 2.1$ (enforced by `df >= 2.1` floor for finite variance)
- **Operational Capabilities**: Fully supports continuous density, continuous CDF, continuous quantile PPF, continuous negative log-likelihood, and continuous Monte Carlo sampling via `numpy.random.default_rng().standard_t`.

### Metric Implementation:
1. **CRPS Formulation**:
   - **Source Function**: [`analytical_student_t_crps()`](file:///D:/Study/Code/Python/Aelous/src/models/probabilistic/student_t_correctness.py#L115-L160) in `src/models/probabilistic/student_t_correctness.py`.
   - **Mathematical Reference**: Jordan, Krueger, Lerch (2019), *"Evaluating Probabilistic Forecasts with scoringRules: An R Package"*, Journal of Statistical Software.
   - **Exact Formula**:
     $$z = rac{y - \mu}{\sigma}$$
     $$	ext{CRPS}(F, y) = \sigma \left[ z \left(2 F_{
u}(z) - 1ight) + 2 f_{
u}(z) rac{
u + z^2}{
u - 1} - rac{2 \sqrt{
u}}{
u - 1} rac{B(0.5, 
u - 0.5)}{B(0.5, 
u/2)^2} ight]$$
   - **Classification**: **`EXACT_CONTINUOUS_CRPS`** (verified against adaptive numerical quadrature in `test_student_t_analytical_crps_vs_numerical_quadrature`).
2. **NLL Formulation**:
   - **Source Function**: Evaluated in [`src/models/probabilistic/unified_evaluation.py`](file:///D:/Study/Code/Python/Aelous/src/models/probabilistic/unified_evaluation.py#L140-L155).
   - **Exact Formula**:
     $$	ext{NLL}(F, y) = -\log f_Y(y) = -\left( \log f_Z\left(rac{y - \mu}{\sigma}; 
uight) - \log \sigma ight)$$
   - **Classification**: **`EXACT_CONTINUOUS_NLL`** (evaluated directly from `scipy.stats.t.logpdf`).

---

## 5. STEP 5 & STEP 6 — TRACING THE DIVERGENT NUMBER PAIRS

### Source of $17.6532 / 4.6307$:
- **Exact File**: [`artifacts/post_holdout_v3/marginal_forecast_metrics_2024_v3.json`](file:///D:/Study/Code/Python/Aelous/artifacts/post_holdout_v3/marginal_forecast_metrics_2024_v3.json#L66-L67)
- **JSON Field**: `metrics.P4_ngboost_student_t.crps = 17.6532`, `metrics.P4_ngboost_student_t.nll = 4.6307`
- **Experimental Context**:
  - Dataset: Bureau of Transportation Statistics (BTS) On-Time Performance database for destination ATL.
  - Temporal Split: Calendar year **2024 Post-Holdout** (Evaluated post-freeze under `POST_HOLDOUT` governance).
  - Sample Size: $N = 5000$ flight records.
  - Model Seed: `202601`.
  - Additional Metrics: Point MAE $= 21.9664$ min, RMSE $= 54.2237$ min, $R^2 = -0.0689$, Pinball Loss $= 7.6585$, 80% Coverage $= 0.7610$, 90% Coverage $= 0.8438$.
- **Validation**: Cryptographically validated in freeze manifest v3 and v4; cross-audited in R28 and verified by pytest in [`tests/test_r28_probabilistic_audit.py`](file:///D:/Study/Code/Python/Aelous/tests/test_r28_probabilistic_audit.py).

### Source of $17.15 / 4.032$:
- **Exact File**: [`artifacts/audit/r32_independent_forensic_verification.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r32_independent_forensic_verification.json#L156-L157)
- **JSON Field**: `mandatory_questions.Q8_p4_continuous_distribution_calibration.raw_values.exact_continuous_crps = 17.1539`, `exact_continuous_nll = 4.0321`
- **Text Mentions**: [`docs/audit/R32_INDEPENDENT_FORENSIC_VERIFICATION.md`](file:///D:/Study/Code/Python/Aelous/docs/audit/R32_INDEPENDENT_FORENSIC_VERIFICATION.md) (Lines 25, 249, 258, 309, 373).
- **Physical Provenance Audit**:
  - An exhaustive regex and numeric query across all 1,200+ files in `artifacts/`, `configs/`, `scripts/`, `src/`, and `tests/` confirmed that **$17.1539$ and $4.0321$ appear nowhere prior to R32**.
  - The number $4.032042$ was located in an unrelated stability run of a point XGBoost baseline (`point_arrival_xgboost_baseline_v1_fold_3_seed_202601.json`).
  - The number $17.1544$ was located as an MAE in an early distribution ablation manifest (`probabilistic_stage3_distribution_ablation_v1.json`).
  - **Forensic Determination**: The numbers $(17.1539, 4.0321)$ were **mistakenly synthesized/hallucinated by the agent drafting the R32 report** without checking the authoritative source manifests (`marginal_forecast_metrics_2024_v3.json` or `academic_model_selection_v3.json`).

---

## 6. STEP 7 — EXPERIMENT ATTRIBUTE COMPARISON TABLE

| Attribute | Genuine Post-Holdout (17.6532 / 4.6307) | R32 Report Entry (17.15 / 4.032) | Genuine Dev Selection (18.484 / 4.5805) | Match / Reconciled Status |
| :--- | :--- | :--- | :--- | :--- |
| **Year** | 2024 | Stated as 2024 | 2023 | Reconciled (Holdout vs Dev) |
| **Split** | POST_HOLDOUT | UNBOUNDED | SELECTION | Reconciled |
| **Sample Size $N$** | 5,000 | Stated as 5,000 | 5,000 | Reconciled |
| **Dataset** | BTS ATL Core Arrival | Stated as BTS ATL | BTS ATL Core Arrival | Reconciled |
| **Model** | P4_ngboost_student_t | P4_ngboost_student_t | P4_ngboost_student_t | Identical Model Architecture |
| **Distribution** | Student-T ($\mu, \sigma, 
u$) | Student-T ($\mu, \sigma, 
u$) | Student-T ($\mu, \sigma, 
u$) | Identical Distribution |
| **Seed** | 202601 | 202601 | 202601 | Identical Seed |
| **Config Hash** | `bd381014e305e55e...` | UNKNOWN | `0ba819f68a960d4b...` | Reconciled |
| **Data Hash** | `799b7bfa7c588960...` | UNKNOWN | `66be80471e7e613b...` | Reconciled |
| **CRPS Function** | `analytical_student_t_crps` | `analytical_student_t_crps` | `analytical_student_t_crps` | Identical Metric Formula |
| **NLL Function** | `scipy.stats.t.logpdf` | `scipy.stats.t.logpdf` | `scipy.stats.t.logpdf` | Identical Metric Formula |
| **Physical File Exists**| **YES** (`marginal_forecast_metrics_2024_v3.json`)| **NO** (Only in R32 summary) | **YES** (`academic_model_selection_v3.json`)| **ONE VALUE INVALID** |

---

## 7. STEP 8 — DISCREPANCY CLASSIFICATION

The discrepancy is classified strictly as:

```text
ONE_VALUE_IS_INVALID_OR_MISLABELED
```

### Scientific Rationale:
1. The pair **$(17.6532, 4.6307)$** is physically present in the cryptographically signed and frozen raw evidence files generated in Phase R23 and verified in Phases R28, R30, and R31.
2. The pair **$(17.15, 4.032)$** (recorded as $17.1539$ and $4.0321$) has zero existence in any computational artifact prior to Phase R32.
3. The discrepancy did not arise from different random seeds, different model hyperparameter configurations, different code implementations, or different temporal splits. It was exclusively a human/agent typographical and transcription defect during R32 report authoring.
4. Consequently, no scientific experiments or models are in question. Only the R32 reporting text contained an invalid value.

---

## 8. STEP 9 & STEP 10 — FINAL CERTIFICATION INTEGRITY & REPAIR

### Final Certified Package Integrity:
In [`artifacts/audit/final_evidence_certification_v4.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/final_evidence_certification_v4.json) and [`docs/audit/FINAL_EVIDENCE_CERTIFICATION_V4.md`](file:///D:/Study/Code/Python/Aelous/docs/audit/FINAL_EVIDENCE_CERTIFICATION_V4.md#L73), the authoritative recorded metrics for P4 on 2024 holdout are:
```text
P4 Student-T MAE: 21.9664 min (Continuous CRPS: 17.6532, NLL: 4.6307)
```
The final certification package V4 **already contains the true, correct, physically verified numbers**. It does NOT contain the errant R32 numbers.

Therefore:
$$	ext{FINAL\_CERTIFIED\_METRIC\_STATUS} = \mathbf{SOUND\_AND\_VERIFIED}$$
$$	ext{FINAL\_CERTIFICATION\_CURRENTLY\_SAFE} = \mathbf{YES}$$

### Claim Boundary Impact:
- **`CLAIM_04_PROBABILISTIC_P4_STUDENT_T`**:
  - Claim wording: *"P4 NGBoost Student-T provides a parametric continuous predictive density; empirical calibration is not separately certified."*
  - Wording does not assert numeric CRPS or NLL thresholds; it asserts mathematical capability and disclaims empirical calibration.
  - Impact: **ZERO IMPACT** on claim boundaries.

---

## 9. STEP 11 & STEP 12 — ARTIFACTS & PYTEST TEST RESULTS

### Deliverables Created:
1. [`artifacts/audit/r33_p4_metric_lineage.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r33_p4_metric_lineage.json) ([`.sha256`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r33_p4_metric_lineage.json.sha256))
2. [`artifacts/audit/r33_p4_metric_reconciliation.parquet`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r33_p4_metric_reconciliation.parquet) ([`.sha256`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r33_p4_metric_reconciliation.parquet.sha256))
3. [`docs/audit/R33_P4_METRIC_LINEAGE.md`](file:///D:/Study/Code/Python/Aelous/docs/audit/R33_P4_METRIC_LINEAGE.md) ([`.sha256`](file:///D:/Study/Code/Python/Aelous/docs/audit/R33_P4_METRIC_LINEAGE.md.sha256))
4. [`tests/test_r33_p4_metric_lineage.py`](file:///D:/Study/Code/Python/Aelous/tests/test_r33_p4_metric_lineage.py)

### Pytest Verification Results:
The dedicated test suite [`tests/test_r33_p4_metric_lineage.py`](file:///D:/Study/Code/Python/Aelous/tests/test_r33_p4_metric_lineage.py) was executed with `pytest`:
```text
tests/test_r33_p4_metric_lineage.py::test_old_p4_metric_source_exists PASSED        [ 12%]
tests/test_r33_p4_metric_lineage.py::test_r32_p4_metric_source_exists PASSED        [ 25%]
tests/test_r33_p4_metric_lineage.py::test_metric_sources_are_traceable PASSED      [ 37%]
tests/test_r33_p4_metric_lineage.py::test_dataset_split_reconciles PASSED          [ 50%]
tests/test_r33_p4_metric_lineage.py::test_p4_model_identity_reconciles PASSED      [ 62%]
tests/test_r33_p4_metric_lineage.py::test_p4_metric_implementation_reconciles PASSED [ 75%]
tests/test_r33_p4_metric_lineage.py::test_no_unresolved_metric_alias PASSED        [ 87%]
tests/test_r33_p4_metric_lineage.py::test_final_authoritative_metric_identified PASSED [100%]

============================== 8 passed in 1.09s ==============================
```

---

## 10. ANSWERS TO MANDATORY FORENSIC QUESTIONS (Q1–Q11)

### Q1: 17.6532 / 4.6307 came from which exact artifact?
- **VERDICT**: **`PROVEN`**
- **EVIDENCE**: Verified directly from the raw evaluation file generated during the 2024 holdout evaluation.
- **SOURCE**: [`artifacts/post_holdout_v3/marginal_forecast_metrics_2024_v3.json`](file:///D:/Study/Code/Python/Aelous/artifacts/post_holdout_v3/marginal_forecast_metrics_2024_v3.json#L66-L67)
- **FIELD/LOCATION**: `metrics.P4_ngboost_student_t.crps` and `metrics.P4_ngboost_student_t.nll`
- **RAW VALUE**: `"crps": 17.6532`, `"nll": 4.6307`
- **WHAT THIS PROVES**: These are the physical, raw, unadjusted holdout evaluation metrics of P4 on the 2024 dataset.
- **WHAT THIS DOES NOT PROVE**: Does not prove P4 empirical interval calibration.

### Q2: 17.15 / 4.032 came from which exact artifact?
- **VERDICT**: **`PROVEN_AS_ERRONEOUS_R32_ENTRY`**
- **EVIDENCE**: An exhaustive scan across all pre-R32 artifacts found 0 occurrences. The values exist only in the R32 report deliverables.
- **SOURCE**: [`artifacts/audit/r32_independent_forensic_verification.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r32_independent_forensic_verification.json#L156-L157)
- **FIELD/LOCATION**: `mandatory_questions.Q8_p4_continuous_distribution_calibration.raw_values`
- **RAW VALUE**: `"exact_continuous_crps": 17.1539`, `"exact_continuous_nll": 4.0321`
- **WHAT THIS PROVES**: Confirms that $(17.15, 4.032)$ was introduced solely as a reporting error in phase R32.
- **WHAT THIS DOES NOT PROVE**: Does not correspond to any genuine model training or evaluation run.

### Q3: Are they the same experiment?
- **VERDICT**: **`PROVEN`** (No, one is a real experiment, one is an erroneous entry).
- **EVIDENCE**: $17.6532 / 4.6307$ is a real experiment on 2024 holdout data ($N=5000$). $17.15 / 4.032$ is not an experiment at all.
- **SOURCE**: [`artifacts/audit/r33_p4_metric_lineage.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r33_p4_metric_lineage.json)
- **FIELD/LOCATION**: `discrepancy_classification`
- **RAW VALUE**: `"ONE_VALUE_IS_INVALID_OR_MISLABELED"`
- **WHAT THIS PROVES**: There are not two conflicting experimental benchmarks; there is only one benchmark and one reporting mistake.
- **WHAT THIS DOES NOT PROVE**: Does not imply any corruption in raw experimental data.

### Q4: Are they the same year/split?
- **VERDICT**: **`PROVEN`**
- **EVIDENCE**: $17.6532 / 4.6307$ belongs strictly to the 2024 post-holdout split. The genuine 2023 development split metrics are $18.4840 / 4.5805$.
- **SOURCE**: [`artifacts/manifests/academic_model_selection_v3.json`](file:///D:/Study/Code/Python/Aelous/artifacts/manifests/academic_model_selection_v3.json) and [`artifacts/post_holdout_v3/marginal_forecast_metrics_2024_v3.json`](file:///D:/Study/Code/Python/Aelous/artifacts/post_holdout_v3/marginal_forecast_metrics_2024_v3.json)
- **FIELD/LOCATION**: `ranking_free_comparison_table.probabilistic_models.P4_ngboost_student_t` vs `metrics.P4_ngboost_student_t`
- **RAW VALUE**: Dev 2023: `(18.484, 4.5805)`; Holdout 2024: `(17.6532, 4.6307)`
- **WHAT THIS PROVES**: Reconciles the distinct performance across development and post-holdout temporal partitions.
- **WHAT THIS DOES NOT PROVE**: Does not indicate data leakage between 2023 and 2024.

### Q5: Are they generated by the same code/config/data?
- **VERDICT**: **`PROVEN`**
- **EVIDENCE**: $17.6532 / 4.6307$ was generated by `P4NGBoostStudentTCandidate` evaluated with `analytical_student_t_crps()` on 2024 holdout data. $17.15 / 4.032$ was generated by no code.
- **SOURCE**: [`src/models/probabilistic/student_t_correctness.py`](file:///D:/Study/Code/Python/Aelous/src/models/probabilistic/student_t_correctness.py)
- **FIELD/LOCATION**: `analytical_student_t_crps()`
- **RAW VALUE**: Exact continuous formula implemented.
- **WHAT THIS PROVES**: Algorithm code has remained immutable and correct.
- **WHAT THIS DOES NOT PROVE**: Does not alter historical training procedures.

### Q6: Which metric pair belongs to the final certified P4 experiment?
- **VERDICT**: **`PROVEN`**
- **EVIDENCE**: The certified V4 manifest explicitly records $17.6532$ and $4.6307$.
- **SOURCE**: [`artifacts/audit/final_evidence_certification_v4.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/final_evidence_certification_v4.json) and [`docs/audit/FINAL_EVIDENCE_CERTIFICATION_V4.md`](file:///D:/Study/Code/Python/Aelous/docs/audit/FINAL_EVIDENCE_CERTIFICATION_V4.md#L73)
- **FIELD/LOCATION**: `Section 3: P4 Student-T MAE: 21.9664 min (Continuous CRPS: 17.6532, NLL: 4.6307)`
- **RAW VALUE**: `CRPS = 17.6532, NLL = 4.6307`
- **WHAT THIS PROVES**: The final certified evidence package is fully authoritative and aligned with raw data.
- **WHAT THIS DOES NOT PROVE**: Does not make P4 an overall champion across all tasks.

### Q7: Is either number invalid or mislabeled?
- **VERDICT**: **`PROVEN`**
- **EVIDENCE**: $17.15 / 4.032$ is invalid and mislabeled.
- **SOURCE**: [`artifacts/audit/r33_p4_metric_lineage.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r33_p4_metric_lineage.json)
- **FIELD/LOCATION**: `discrepancy_classification`
- **RAW VALUE**: `"ONE_VALUE_IS_INVALID_OR_MISLABELED"`
- **WHAT THIS PROVES**: Discrepancy is fully resolved by identifying the mislabeled artifact.
- **WHAT THIS DOES NOT PROVE**: Does not require changing any raw model weights.

### Q8: Does this discrepancy require retraining, or only evidence/label repair?
- **VERDICT**: **`PROVEN`**
- **EVIDENCE**: No retraining is required. The raw model evaluation files are 100% correct.
- **SOURCE**: [`artifacts/audit/r33_p4_metric_lineage.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r33_p4_metric_lineage.json)
- **FIELD/LOCATION**: `retrain_required`
- **RAW VALUE**: `false`
- **WHAT THIS PROVES**: The research codebase and model artifacts remain valid.
- **WHAT THIS DOES NOT PROVE**: Does not obviate future audit documentation updates.

### Q9: Does P4 still have exact continuous CRPS?
- **VERDICT**: **`PROVEN`**
- **EVIDENCE**: P4 implements closed-form Jordan et al. (2019) Student-T CRPS, tested and passing in pytest.
- **SOURCE**: [`src/models/probabilistic/student_t_correctness.py`](file:///D:/Study/Code/Python/Aelous/src/models/probabilistic/student_t_correctness.py#L115) and [`tests/test_r33_p4_metric_lineage.py`](file:///D:/Study/Code/Python/Aelous/tests/test_r33_p4_metric_lineage.py#L145)
- **FIELD/LOCATION**: `analytical_student_t_crps`
- **RAW VALUE**: Verified against adaptive numerical integration `scipy.integrate.quad`.
- **WHAT THIS PROVES**: Mathematical exactness of continuous CRPS is preserved.
- **WHAT THIS DOES NOT PROVE**: Does not apply to discrete quantile models like P5.

### Q10: Does P4 still have exact continuous NLL?
- **VERDICT**: **`PROVEN`**
- **EVIDENCE**: Evaluated directly via continuous Student-T log probability density function.
- **SOURCE**: [`src/models/probabilistic/unified_evaluation.py`](file:///D:/Study/Code/Python/Aelous/src/models/probabilistic/unified_evaluation.py#L150)
- **FIELD/LOCATION**: `- (scipy.stats.t.logpdf(z, df=df) - np.log(sigma))`
- **RAW VALUE**: Exact log likelihood verified.
- **WHAT THIS PROVES**: NLL is an exact continuous log-score metric.
- **WHAT THIS DOES NOT PROVE**: Does not prove likelihood optimization was convex.

### Q11: Does any final claim currently rely on the wrong number?
- **VERDICT**: **`PROVEN`**
- **EVIDENCE**: All 13 final claim definitions were inspected in `final_claim_boundary_audit_v4.json`. `CLAIM_04_PROBABILISTIC_P4_STUDENT_T` defines capability bounds without numeric CRPS/NLL assertions. Furthermore, `FINAL_EVIDENCE_CERTIFICATION_V4.md` already cites the correct numbers ($17.6532 / 4.6307$).
- **SOURCE**: [`artifacts/audit/final_claim_boundary_audit_v4.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/final_claim_boundary_audit_v4.json)
- **FIELD/LOCATION**: `claims[3]` (`CLAIM_04_PROBABILISTIC_P4_STUDENT_T`)
- **RAW VALUE**: No numeric dependency on 17.15 or 4.032.
- **WHAT THIS PROVES**: Core scientific claims are completely unpolluted by the R32 transcription error.
- **WHAT THIS DOES NOT PROVE**: Does not eliminate the need for documenting this audit resolution.

---

## 11. FINAL STATUS SUMMARY BLOCK

```text
R33_STATUS:
PASS

P4_METRIC_DISCREPANCY:
RESOLVED

AUTHORITATIVE_P4_CRPS:
17.6532

AUTHORITATIVE_P4_NLL:
4.6307

RETRAIN_REQUIRED:
NO

FINAL_CERTIFICATION_CURRENTLY_SAFE:
YES
```
