# CERTIFICATION_DOMAIN_MAP: EVIDENCE-BASED DOMAIN RECONCILIATION & P4/P5 ARCHITECTURE GUARD

**Phase:** `P12 — TESTS, ARTIFACTS & CERTIFICATION-DOMAIN RECONCILIATION AFTER P11R`  
**Git HEAD Commit:** `7ba0aba92d366f712977faaaa5a73cba65a32a55`  
**Branch:** `v4-final-forensic-certification`  
**Precondition Status:** `P11R_STATUS = PASS` (Certified in `P11R_FINAL_REPORT.md`)  
**Architecture Guard Status:** **`LOCKED & COMPLIANT`**

---

## 1. EVIDENCE-BASED DOMAIN RECONCILIATION (18 Granular → 13 Certified Domains)

In Phase R30 ([`artifacts/audit/r30_final_evidence_reconciliation.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r30_final_evidence_reconciliation.json)), research boundaries were cataloged into **18 granular operational domains**. In Phase R36 and System Freeze Manifest V5, these were consolidated into **13 certified scientific domains** to establish a strict 1:1 structural correspondence with the 13 core scientific claims (`CLAIM_01` through `CLAIM_13`).

### Consolidation Lineage & Rationales
1. **Domains 13–15 (Solvers: Greedy, CP-SAT, SA, Hybrid):**  
   Consolidated into a single unified domain (**Domain 10: Downstream Gate Optimization & Equal-Compute Solvers**) because all four solvers are benchmarked on the identical scenario instances under an identical 2.0-second wall-clock ceiling (`E014`).
2. **Domains 10–11 (Synthetic Turn & Gate Simulation):**  
   Merged into **Domain 08: Simulation Domain Boundary** because both define the operational mechanics and mathematical bounds of the synthetic airfield model.
3. **Domains 3–5 (Auxiliary Tasks: Departure, Weather, Flight Chains):**  
   Consolidated into **Domain 12: Auxiliary Non-Contamination & Input Isolation** because their singular scientific role is verifying complete non-contamination and zero leakage into the Core Arrival pipeline.
4. **Domain 16 (Monte Carlo):**  
   Split into two distinct scientific domains: **Domain 06** (Variance Reduction via CRN, where the unverified 82.4% reduction claim was formally retracted) and **Domain 07** (Convergence across $N \in [100, 2500]$, establishing empirical $s/\sqrt{N}$ properties).
5. **Domains 17–18 (Reproducibility & Certification Tests):**  
   Merged into **Domain 13: Cryptographic Lineage & Reproducibility Standards** to combine cryptographic hash sidecars, deterministic random seeds, and software environment locking.

---

## 2. THE 18 GRANULAR → 13 CERTIFIED SCIENTIFIC DOMAINS MAPPING MATRIX

| Old Granular Domain (R30) | Certified Scientific Domain | Verifying Test Suites | Supporting Physical Artifacts | Governed Core Claim | Decision ID | Scientific Consolidation Rationale | Evolution Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `Temporal governance` | **Domain 01: Temporal Post-Holdout Governance** | `test_r20_freeze_gate.py`, `test_r22_system_freeze_v3.py`, `test_temporal_split.py` | `system_freeze_manifest.json`, `r22_freeze_audit.json` | `CLAIM_01_TEMPORAL_POST_HOLDOUT` | `E001` | Isolates 2024 access rules; enforces post-freeze semantics with zero parameter tuning. | **CONSOLIDATED** |
| `Point model selection` | **Domain 02: Point Champion Selection** | `test_r25_point_selection_consistency.py`, `test_academic_model_selection_v2.py` | `academic_model_selection_v3.json`, `r25_point_selection_consistency.json` | `CLAIM_02_POINT_CHAMPION_SELECTION` | `E005` | Confirms Ridge and Ensemble tie on 2023 development slice within $\pm 0.10$ min MAE band. | **CONSOLIDATED** |
| `Core Arrival probabilistic prediction` | **Domain 03: P5 Quantile Forecasting** | `test_r34_p5_mathematical_audit.py`, `test_probabilistic/test_quantile.py` | `r34_p5_capability_forensics.json`, `r34_p5_quantile_config.json` | `CLAIM_03_PROBABILISTIC_P5_CRPS` | `E007` | Evaluates discrete quantiles and pinball loss; strictly establishes `FORECAST_ONLY` Role B status. | **SUPERSEDED / SEPARATED** |
| `Probabilistic model selection` (P4 Continuous) | **Domain 04: P4 Continuous Student-t Distribution** | `test_r33_p4_metric_lineage.py`, `test_contracts/test_distribution_properties.py` | `model_weights_frozen_v1.joblib`, `r33_p4_metric_reconciliation.parquet` | `CLAIM_04_PROBABILISTIC_P4_STUDENT_T` | `E008` | Evaluates closed-form Student-t CRPS/NLL density; certifies Role C continuous stochastic engine. | **CONSOLIDATED** |
| `Core Arrival point prediction` | **Domain 05: Decoupled Multi-Attribute Role Assignment** | `test_r24_final_certification.py`, `test_r31_final_certification.py` | `academic_model_selection_v3.json` | `CLAIM_05_SINGLE_OVERALL_CHAMPION` | `E009` | Strictly blocks the unscientific claim of a single joint winner; enforces Role B vs Role C separation. | **SUPERSEDED / CONSOLIDATED** |
| `Monte Carlo` (Variance Reduction) | **Domain 06: Common Random Numbers Variance Reduction** | `test_evaluation/test_mc_convergence_v2.py` | `crn_variance_reduction_report.json` | `CLAIM_06_CRN_VARIANCE_REDUCTION` | `E010` | Retracts the historical unverified 82.4% CRN reduction claim; marks status as `NOT_SUPPORTED`. | **SPLIT / RETRACTED** |
| `Monte Carlo` (Grid Convergence) | **Domain 07: Monte Carlo Sample Size & Convergence** | `test_evaluation/test_monte_carlo_audit_v2.py` | `monte_carlo_convergence_report.json` | `CLAIM_07_MC_N500_OPTIMALITY` | `E011` | Retracts claim that $N=500$ is mathematically optimal; establishes empirical $s/\sqrt{N}$ convergence. | **SPLIT / CONSOLIDATED** |
| `Synthetic Turn` & `Gate Simulation` | **Domain 08: Simulation Domain Boundary** | `test_downstream/test_downstream_semantics_v2.py` | `system_freeze_manifest.json` | `CLAIM_08_REAL_WORLD_GATE_OPERATIONS` | `E012` | Bounds all operational results to synthetic airfield simulation; strictly bans real-world ATL claims. | **MERGED** |
| `Greedy` (Baseline Comparison) | **Domain 09: Acausal Oracle Boundary & Robustness** | `test_downstream/test_auxiliary_isolation.py` | `post_holdout_re_evaluation_v1/robustness_results.json` | `CLAIM_09_ORACLE_EQUIVALENCE` | `E013` | Demonstrates that acausal oracle point schedules are brittle under stochastic perturbations. | **CONSOLIDATED** |
| `CP-SAT`, `SA`, `CP-SAT + SA` | **Domain 10: Downstream Gate Optimization & Equal-Compute Solvers** | `test_r26_solver_equal_compute.py`, `test_r35_solver_repro.py`, `test_same_solver_budget.py` | `r26_solver_equal_compute_results.parquet`, `post_holdout_re_evaluation_v1/downstream_results.parquet` | `CLAIM_10_DOWNSTREAM_SEMANTICS` | `E014` | Consolidates Greedy, CP-SAT, SA, and Hybrid under strict 2.0s equal-compute wall-clock budgets. | **MERGED** |
| `Statistical inference` | **Domain 11: Statistical Significance & Multiplicity Control** | `test_r18_statistical_inference.py`, `test_paired_comparison_v2.py` | `r18_paired_statistics_v2.json` | `CLAIM_11_STATISTICAL_SIGNIFICANCE` | `E015` | Day-cluster bootstrap on `FL_DATE`; enforces Holm-Bonferroni FWER control for paired tests. | **CONSOLIDATED** |
| `Auxiliary Departure`, `Weather`, `Flight Chain` | **Domain 12: Auxiliary Non-Contamination & Input Isolation** | `test_model_input_boundary.py`, `test_auxiliary_isolation.py` | `feature_manifest_arrival_v1.json` | `CLAIM_12_AUXILIARY_DEPARTURE_DELAY` | `E003, E006` | Verifies complete rejection of raw `.pt` flight chain files, METAR weather, and departure delays. | **MERGED / ISOLATED** |
| `Reproducibility` & `Certification tests` | **Domain 13: Cryptographic Lineage & Reproducibility Standards** | `test_r27_certification_hardening.py`, `test_r37_final_certification.py` | `final_freeze_manifest_v5.json`, `final_execution_summary_v5.json` | `CLAIM_13_REPRODUCIBILITY_STANDARDS` | `E016` | Mandates cryptographic SHA-256 sidecars, deterministic seeds, and flags missing dashboard layer. | **MERGED** |

---

## 3. MANDATORY P4 / P5 ARCHITECTURE GUARD

The certification domain mapping enforces the frozen model role decoupling certified in Forensic Audit R39 and System Freeze Manifest:

```
====================================================================================================
P4 / P5 ARCHITECTURAL ROLE ENFORCEMENT
====================================================================================================
[ROLE C: P4_ngboost_student_t]
- Status                        : CERTIFIED CONTINUOUS STOCHASTIC DOWNSTREAM ENGINE
- Checkpoint Path               : artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib
- Checkpoint SHA-256            : e7e7462f17b65b276ebdee9c7beced15e090f69b088a18896d5a91aaa8cb062f
- Predictive Output             : Continuous parameter triplet (mu(x), sigma(x), nu(x))
- Density Evaluation            : Continuous PDF / NLL available in closed form
- Continuous Sampling           : AUTHORIZED AND CERTIFIED (Inverse CDF via PCG64 CRN matrix)
- Calibration Status            : NOT_SEPARATELY_CERTIFIED

[ROLE B: P5_quantile_regression]
- Status                        : MARGINAL QUANTILE FORECAST CHAMPION (FORECAST_ONLY)
- Predictive Output             : 9 discrete marginal quantiles (tau in {0.10, 0.20, ..., 0.90})
- Density Evaluation            : NOT_AVAILABLE (No continuous density function exists)
- Continuous Sampling           : STRICTLY PROHIBITED & INELIGIBLE
- Downstream Role               : FORECAST-ONLY MEDIAN (q_0.5) OR MARGINAL INTERVALS
- Reconstruction Status         : NOT RECONSTRUCTED & NOT RETRAINED
====================================================================================================
```

### Protocol Invariant Assertions
1. **Zero Joint Champion:** No document, test, or claim may declare P4 or P5 as an overall joint champion across both marginal forecasting and stochastic simulation.
2. **P5 Downstream Sampler Prohibition:** P5 quantile regression is mathematically barred from acting as a continuous downstream stochastic generator.
3. **P4 Calibration Disclosure:** Native P4 predictive distributions are mathematically certified with exact Student-t integration, but its marginal intervals remain explicitly labeled `NOT_SEPARATELY_CERTIFIED`.

---

## 4. NO SCIENTIFIC REPAIR VERIFICATION

This reconciliation was conducted under strict audit-only constraints:
* **Zero Model Retraining:** No models were fitted, tuned, or retrained.
* **Zero Feature Modifications:** Feature manifests and extraction scripts were not altered.
* **Zero Hyperparameter Tuning:** No HPO trials or parameter searches were executed.
* **Zero Simulation Changes:** Downstream gate simulators, objective weights, and solver budgets remain identical to the frozen pre-holdout state.
* **Zero 2024 Row-Level Access:** Calendar year 2024 was not opened or re-evaluated.
