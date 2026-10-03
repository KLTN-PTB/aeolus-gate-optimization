# Aeolus Probabilistic Core Arrival & Gate Optimization
## Definitive Final Evidence Certification & Claim Boundary Audit V3 (Task R24)

> **Certification Status**: `CERTIFIED_WITH_LIMITATIONS`  
> **Certifying Authority**: `AEOLUS_V4_FORENSIC_CERTIFICATION_COUNCIL`  
> **Timestamp (UTC)**: `2026-10-02T11:52:19.537233+00:00`  
> **Protocol**: `AEOLUS_V4_FORENSIC_OVERHAUL_STAGE_R24`  

---

### 1. Executive Summary & Epistemological Stance

Following the sequential forensic overhaul protocol (Tasks R13 through R23), this document certifies the empirical evidence, cryptographic provenance, and methodological boundaries of the Aeolus research system under status **`CERTIFIED_WITH_LIMITATIONS`**.

In strict adherence to academic integrity and empirical standards:
- **NO claims of perfection, infallibility, or '100% reproducibility' are permitted.**
- **NO claims of real-world airport operations or airline cost savings at Atlanta (ATL) are permitted.** The BTS TranStats dataset lacks physical gate numbers; all gate assignments are evaluated in a synthetic simulated research environment.
- **NO claims of equivalence to the Oracle are permitted.** The Oracle reference utilizes post-hoc actual delays and represents an unachievable theoretical upper bound.
- **NO single overall champion is recognized.** Model selection is decoupled across distinct mathematical roles: point accuracy, quantile forecasting, and downstream simulation.

---

### 2. Cryptographic Provenance & Freeze Lineage

All underlying code, data contracts, and evidence manifests are cryptographically sealed and verified with SHA-256 hashes:

| Artifact | SHA-256 Checksum | Governance Role |
| :--- | :--- | :--- |
| `system_freeze_manifest_v3.json` | `0144ea3ffb73039c070dac4c7f0a410995e755d973f300289651ffa4be30020c` | Seals all 79 result-affecting files across 24 categories |
| `post_holdout_evaluation_manifest_v3.json` | `b9d7a7cf51b8f5691d7b37e6ce73ceb92113358247469f1cb750ff2a407c4f23` | 2024 Locked Post-Holdout Evaluation (84 runs, 0 failures) |
| `academic_model_selection_v3.json` | `0ba819f68a960d4bea9b0ec0e99d059a5acc424255a6f3a230e6301e775879d5` | Decoupled 3-role selection on 2016-2023 development set |
| `development_evidence_manifest_v3.json` | `506cf808dbf044b4404a844ac7f525b1877e51e9a52567398ea2cd4afeae876d` | Verified development evidence manifest |

---

### 3. Decoupled Model Selection & Capabilities

Because point error minimization, probabilistic sharpness, and scenario generation require distinct mathematical properties, joint single-champion selection is fail-closed blocked:

| Operational Role | Certified Model(s) | 2023 Development | 2024 Post-Holdout | Capabilities & Limitations |
| :--- | :--- | :--- | :--- | :--- |
| **Role A: Point Prediction** | `arrival_linear_baseline_v1` (Ridge) & `arrival_weighted_ensemble_v1` | MAE: 24.618 vs 24.618 min (diff = 0.0004 min <= 0.10 min: TIED) | MAE: 22.913 vs 23.318 min (diff = 0.405 min > 0.10 min: NOT TIED) | 2023 selection slice co-champions; not tied on 2024 post-holdout. No single overall champion asserted. |
| **Role B: Probabilistic Forecasting** | `P5_quantile_regression` | CRPS: 16.85 min | MAE: 21.688 min | Champion discrete CRPS & pinball loss. Analytical density and continuous NLL NOT_AVAILABLE. |
| **Role C: Downstream Simulation** | `P4_ngboost_student_t` | CRPS: 18.48 min, NLL: 4.58 | CRPS: 17.653, NLL: 4.631 | Parametric continuous Student-T density. Enables continuous Monte Carlo sampling. |

---

### 4. Downstream Operational Optimization Summary

Evaluated on 4 seasonal 2024 operational scenarios (30-70 flights, 10-20 contact gates) across 7 candidates and 3 solvers (Deterministic Greedy, CP-SAT, Simulated Annealing):

- **Total Operational Runs**: 84
- **Hard Constraint Violations Observed**: 0 (100% hard feasible across all runs)
- **Realized Flight Conflicts Observed**: 0
- **Solver Failures / Timeouts**: 0 unaccounted failures
- **Governing Semantics**: `SCALAR_FORECAST_IMPACT` (models pass point/median/mean scalar forecasts to gate allocation solver)

---

### 5. Definitive Claim Boundary Matrix

Each historical claim has been forensically audited and assigned strict allowed and prohibited wording boundaries:

#### [CORRECTED] CLAIM_01_TEMPORAL_POST_HOLDOUT: TEMPORAL_EVALUATION
- **Original Claim**: "2024 is an untouched, pristine, unseen final holdout dataset."
- **Forensic Finding**: Repository lineage audit proved 2024 data was accessed during initial pipeline exploration. It cannot be claimed as pristine or unseen.
- **Methodological Boundary**: Evaluated strictly post-freeze under POST_HOLDOUT protocol governance with zero parameter or threshold adaptation.
- **Allowed Wording**: "2024 is evaluated strictly post-freeze under POST_HOLDOUT protocol governance with zero parameter, hyperparameter, or threshold adaptation."
- **Prohibited Wording**: `untouched holdout, never-before-seen dataset, blind test, pristine holdout`
- **Supporting Evidence**: `artifacts/post_holdout_v3/post_holdout_evaluation_manifest_v3.json`

#### [SUPPORTED_WITH_LIMITATION] CLAIM_02_POINT_CHAMPION_SELECTION: POINT_PREDICTION
- **Original Claim**: "Ridge Regression is the absolute best point prediction model across all evaluation metrics."
- **Forensic Finding**: On 2023 development selection, Ridge and the 50/50 Weighted Ensemble tie within the 0.10 min indifference band (|diff| = 0.00045 min <= 0.10 min). On 2024 post-holdout, they do NOT tie (|diff| = 0.4050 min > 0.10 min). Therefore, no single overall point champion is asserted across all datasets.
- **Methodological Boundary**: Ridge and Weighted Ensemble tie as co-champions solely on the 2023 selection slice under the pre-registered 0.10 min indifference band. On 2024 post-holdout, difference exceeds the 0.10 min band; no universal point champion is claimed.
- **Allowed Wording**: "Ridge regression and the 50/50 Weighted Ensemble tie within the 0.10 min indifference band on the 2023 model selection slice. On 2024 post-holdout, the difference is 0.405 min (> 0.10 min) and models are not tied; no single overall point champion is asserted."
- **Prohibited Wording**: `Ridge dominates all models unconditionally, Ridge is statistically significantly superior to Weighted Ensemble, Both models tied overall across all years, Single overall point champion`
- **Supporting Evidence**: `artifacts/manifests/academic_model_selection_v3.json`

#### [CORRECTED] CLAIM_03_PROBABILISTIC_P5_CRPS: PROBABILISTIC_FORECASTING
- **Original Claim**: "P5 Quantile Regression achieves champion CRPS and provides a full analytical continuous probability distribution."
- **Forensic Finding**: Quantile regression estimates discrete conditional quantiles; it does not estimate analytical continuous density, continuous CDF, or exact continuous NLL. Invented Laplace/asymmetric transforms were ad-hoc.
- **Methodological Boundary**: P5 is certified strictly for quantile-based sharpness, discrete CRPS (16.85 min dev), and median point forecast. Analytical density and exact continuous NLL are NOT_AVAILABLE.
- **Allowed Wording**: "P5 Quantile Regression achieves champion discrete CRPS (16.85 min) and pinball loss under quantile interval evaluation; continuous density is not available."
- **Prohibited Wording**: `P5 provides a full continuous predictive density, P5 continuous PIT calibration, P5 exact NLL`
- **Supporting Evidence**: `artifacts/manifests/academic_model_selection_v3.json`

#### [SUPPORTED_WITH_LIMITATION] CLAIM_04_PROBABILISTIC_P4_STUDENT_T: PROBABILISTIC_FORECASTING
- **Original Claim**: "P4 NGBoost Student-T is strictly dominated by P5 across all criteria."
- **Forensic Finding**: P4 provides calibrated parametric continuous density, exact continuous CRPS (18.48 min dev, 17.65 min holdout), and continuous NLL (4.58 dev, 4.63 holdout), uniquely enabling continuous Monte Carlo sampling.
- **Methodological Boundary**: P4 is certified as the Downstream Simulation Candidate due to its analytical continuous parametric distribution.
- **Allowed Wording**: "P4 NGBoost Student-T provides calibrated continuous parametric density and is the primary candidate for downstream continuous sampling."
- **Prohibited Wording**: `P4 is strictly dominated by P5 across all criteria, P4 has uncalibrated tail intervals`
- **Supporting Evidence**: `artifacts/manifests/academic_model_selection_v3.json`

#### [BLOCKED] CLAIM_05_SINGLE_OVERALL_CHAMPION: MODEL_SELECTION
- **Original Claim**: "A single overall best champion model exists across all prediction, probabilistic, and operational tasks."
- **Forensic Finding**: Point error, probabilistic sharpness, and downstream scenario generation require fundamentally distinct mathematical capabilities. Joint single-champion selection is scientifically invalid.
- **Methodological Boundary**: Selection is decoupled into 3 distinct operational roles: Point Champion (Ridge/Ensemble tie), Forecast Champion (P5 Quantile), Downstream Candidate (P4 Student-T). Joint overall selection is fail-closed BLOCKED.
- **Allowed Wording**: "Model selection is decoupled into distinct operational roles based on verified mathematical capabilities; single overall champion selection is blocked."
- **Prohibited Wording**: `Overall best model, Universal champion, Single winner of the benchmark`
- **Supporting Evidence**: `artifacts/manifests/academic_model_selection_v3.json`

#### [NOT_SUPPORTED] CLAIM_06_CRN_VARIANCE_REDUCTION: MONTE_CARLO_SIMULATION
- **Original Claim**: "Common Random Numbers (CRN) reduces Monte Carlo variance by 82.4%."
- **Forensic Finding**: No empirical outer replications (R >= 2) comparing Var_CRN(Delta) to Var_indep(Delta) were conducted to substantiate 82.4%. The figure was an unverified claim.
- **Methodological Boundary**: Variance reduction is formally classified as NOT_ESTABLISHED across all code and manifests.
- **Allowed Wording**: "CRN variance reduction status is NOT_ESTABLISHED pending empirical outer replication studies."
- **Prohibited Wording**: `CRN reduces variance by 82.4%, 82.4% variance reduction proven`
- **Supporting Evidence**: `artifacts/monte_carlo_model_comparison_v2/crn_variance_reduction_report.json`

#### [NOT_SUPPORTED] CLAIM_07_MC_N500_OPTIMALITY: MONTE_CARLO_SIMULATION
- **Original Claim**: "Sample size N=500 is mathematically optimal for Monte Carlo simulation because SE < 0.3 min."
- **Forensic Finding**: No pre-registered precision tolerance epsilon* was established prior to data observation; SE < 0.3 min was a post-hoc threshold. Full registered grid N in {100, 250, 500, 1000, 2500} was evaluated with empirical SE tracking.
- **Methodological Boundary**: Precision target status is NOT_PREREGISTERED; full grid was evaluated without truncation under O(1/sqrt(N)) asymptotic empirical tracking.
- **Allowed Wording**: "Monte Carlo precision target was NOT_PREREGISTERED; full grid N in {100, 250, 500, 1000, 2500} was evaluated with empirical SE tracking."
- **Prohibited Wording**: `N=500 is mathematically optimal, SE < 0.3 min error bound guaranteed`
- **Supporting Evidence**: `artifacts/monte_carlo_model_comparison_v2/monte_carlo_convergence_report.json`

#### [CORRECTED] CLAIM_08_REAL_WORLD_GATE_OPERATIONS: DEPLOYMENT_BOUNDARIES
- **Original Claim**: "Aeolus achieves 100% gate conflict reduction and massive operational cost savings at Hartsfield-Jackson Atlanta International Airport (ATL)."
- **Forensic Finding**: No ground truth gate assignments exist in the BTS TranStats dataset. Gates, turn times, and bank scenarios are synthetically synthesized.
- **Methodological Boundary**: Strictly simulated synthetic research environment. Real airfield operations and monetary claims are strictly prohibited.
- **Allowed Wording**: "Aeolus achieves 0 hard constraint violations and eliminates gate assignment overlaps in a simulated synthetic research environment constructed from BTS flight schedules."
- **Prohibited Wording**: `Real airfield deployment at ATL, Operational savings for Delta Air Lines, Field-proven gate management system`
- **Supporting Evidence**: `artifacts/post_holdout_v3/post_holdout_evaluation_manifest_v3.json`

#### [CORRECTED] CLAIM_09_ORACLE_EQUIVALENCE: DEPLOYMENT_BOUNDARIES
- **Original Claim**: "Downstream models achieve performance equivalent to the Oracle."
- **Forensic Finding**: Oracle uses actual realized delays after the fact to solve gate assignment. It is an unachievable non-deployable theoretical reference upper bound.
- **Methodological Boundary**: Oracle is strictly a non-deployable reference bound. Any claim of equivalence is prohibited.
- **Allowed Wording**: "Downstream models matched the Oracle reference on realized conflict count (0 conflicts) and objective values under specific scenarios, but Oracle remains a non-deployable theoretical reference."
- **Prohibited Wording**: `Equivalent to Oracle, Replaces the Oracle, Deployable oracle performance`
- **Supporting Evidence**: `artifacts/post_holdout_v3/paired_downstream_deltas_v3.parquet`

#### [SUPPORTED_WITH_LIMITATION] CLAIM_10_DOWNSTREAM_SEMANTICS: DOWNSTREAM_OPTIMIZATION
- **Original Claim**: "Downstream gate optimization is fully uncertainty-aware across all 7 candidates."
- **Forensic Finding**: Downstream gate optimization uses SCALAR_FORECAST_IMPACT semantics where candidates provide point/median/mean scalars to the solver. Full predictive distributions are not ingested into the objective function.
- **Methodological Boundary**: Formally governed under SCALAR_FORECAST_IMPACT semantics with separate accounting for contact, remote, and unassigned flights.
- **Allowed Wording**: "Downstream pipeline operates under SCALAR_FORECAST_IMPACT semantics where candidates provide point/median/mean scalars to the gate assignment solver."
- **Prohibited Wording**: `Fully integrated stochastic dynamic programming gate optimizer, Distribution-tail aware gate optimizer`
- **Supporting Evidence**: `artifacts/audit/r17_downstream_semantics_decision.json`

#### [CORRECTED] CLAIM_11_STATISTICAL_SIGNIFICANCE: STATISTICAL_INFERENCE
- **Original Claim**: "Differences between models achieve p < 0.001 standalone significance."
- **Forensic Finding**: Standalone p-values computed without multiplicity corrections or clustered dependence were statistically invalid. Repaired using day-cluster/aggregate bootstrap and Holm-Bonferroni / Benjamini-Hochberg.
- **Methodological Boundary**: Multiplicity-adjusted inference confirms no statistically significant difference between Ridge and Weighted Ensemble (adjusted p > 0.05), while both significantly outperform baselines.
- **Allowed Wording**: "Multiplicity-adjusted inference using Holm-Bonferroni and Benjamini-Hochberg across 10 model pairs confirms that Ridge and Weighted Ensemble show no statistically significant difference in point accuracy (adjusted p > 0.05), while both significantly outperform XGBoost and baselines."
- **Prohibited Wording**: `Standalone p < 0.001 significance, All models statistically distinguishably ranked`
- **Supporting Evidence**: `artifacts/audit/r18_paired_statistics_v2.json`

#### [NOT_SUPPORTED] CLAIM_12_AUXILIARY_DEPARTURE_DELAY: PREDICTION_PIPELINE
- **Original Claim**: "Auxiliary departure delay predictions improve core arrival gate optimization."
- **Forensic Finding**: Routing departure delay predictions into arrival gate optimization violates V4 Core Arrival cutoff (CRS_DEP_TIME - 2h) and target semantics.
- **Methodological Boundary**: Auxiliary departure models are research-only and strictly isolated from the Core Arrival pipeline.
- **Allowed Wording**: "Auxiliary departure delay models are strictly isolated research-only benchmarks and do not feed arrival gate optimization."
- **Prohibited Wording**: `Integrated departure-arrival joint optimization, Departure delay feeds arrival gate solver`
- **Supporting Evidence**: `artifacts/manifests/academic_model_selection_v3.json`

#### [HISTORICAL_ONLY] CLAIM_13_REPRODUCIBILITY_STANDARDS: SCIENTIFIC_RIGOR
- **Original Claim**: "The system is 100% reproducible, meets top-tier ML/OR perfection standards, and provides error-free research."
- **Forensic Finding**: Claims of perfection, 100% reproducibility, or flawless research are epistemologically unsupportable. Real systems have boundary conditions, assumptions, and synthetic environments.
- **Methodological Boundary**: The system is Certified With Limitations under cryptographic freeze manifests, deterministic seeds, and explicit failure accounting.
- **Allowed Wording**: "The system is Certified With Limitations under cryptographic freeze manifests, deterministic seeds, and explicit failure accounting."
- **Prohibited Wording**: `100% reproducible, Meets top-tier ML/OR standards, Error-free research, Scientifically proven`
- **Supporting Evidence**: `artifacts/manifests/final_evidence_certification_v3.json`

---

### 6. Verification and Compliance

The certification is accompanied by automated test suite `tests/test_r24_final_certification.py`, verifying:
1. Cryptographic sidecar integrity (`.sha256`).
2. Certification status `CERTIFIED_WITH_LIMITATIONS`.
3. Complete claim boundary matrix mapping with 0 unclassified claims.
4. Strict prohibition of banned phrases across reports and manifests.
5. Complete execution trace reconciliation across R21, R22, and R23.

**Signed by**: Aeolus Forensic Certification Council  
**Status**: `CERTIFIED_WITH_LIMITATIONS`
