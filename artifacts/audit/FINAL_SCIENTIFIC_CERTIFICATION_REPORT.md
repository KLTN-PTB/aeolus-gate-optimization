# FINAL_SCIENTIFIC_CERTIFICATION_REPORT: FINAL SCIENTIFIC CERTIFICATION & CONDITIONAL REBUILD DECISION AFTER P11R

**Phase:** `P14 — Final Scientific Certification & Conditional Rebuild Decision after P11R`  
**Git HEAD Commit:** `7ba0aba92d366f712977faaaa5a73cba65a32a55`  
**Branch:** `v4-final-forensic-certification`  
**Precondition Status:** `P11R_STATUS = PASS` | `P12_STATUS = PASS` (revalidated in `P12R1_STATUS = PASS`) | `P13_STATUS = PASS_WITH_RESERVATION`  
**Certification Status:** **`CERTIFICATION_STATUS = CERTIFIED_WITH_LIMITATIONS`**  
**Rebuild Decision:** **`REBUILD_REQUIRED = NO`**  
**Final Phase Status:** **`P14_STATUS = PASS`**  

---

## 1. EXECUTIVE SUMMARY & SOURCE OF TRUTH HIERARCHY

Phase **P14** synthesizes the complete forensic, scientific, empirical, and governance evidence across the entire history of the Aeolus Core Arrival and Gate Optimization project. In strict adherence to forensic protocol:
* **Zero models were retrained or refitted.**
* **Zero evaluations were rerun on calendar year 2024.**
* **Zero methodology or feature mutations were applied.**
* **No conflicting values were averaged; no historical evidence was erased or overwritten.**

```
====================================================================================================
FINAL SCIENTIFIC CERTIFICATION VERDICT
====================================================================================================
P14_STATUS                                              = PASS
CERTIFICATION_STATUS                                    = CERTIFIED_WITH_LIMITATIONS
REBUILD_REQUIRED                                        = NO
SCIENTIFIC_PIPELINE_STATUS                              = CERTIFIED_ACROSS_13_DOMAINS
P4_DOWNSTREAM_ROLE                                      = ROLE_C_CONTINUOUS_STOCHASTIC_ENGINE
P5_FORECAST_ROLE                                        = ROLE_B_MARGINAL_QUANTILE_CHAMPION
2024_EVIDENCE_STATUS                                    = POST_HOLDOUT_REEVALUATION (P11R)
REMAINING_BLOCKERS                                      = 0 (NONE)
====================================================================================================
```

### Authoritative Hierarchy of Evidence
When evaluating past records, documents, and logs, evidence is prioritized strictly by physical authority:
$$\text{Actual Scientific Artifact} \succ \text{Execution Provenance} \succ \text{Manifest / Configuration} \succ \text{Source Code Lineage} \succ \text{Audit Report} \succ \text{Narrative Documentation}$$

---

## 2. STEP 1: FINAL_SCIENTIFIC_CERTIFICATION_MATRIX

The complete scientific scope comprises **13 certified domains** mapped directly to the core project claims (`CLAIM_01` through `CLAIM_13`):

```
================================================================================================================================================================
FINAL_SCIENTIFIC_CERTIFICATION_MATRIX
================================================================================================================================================================
Claim ID / Name                               | Scientific Domain                | Evidence Artifact                           | Source Code / Lineage                      | Temporal Role          | Status                | Governed Limitation
----------------------------------------------+----------------------------------+---------------------------------------------+--------------------------------------------+------------------------+-----------------------+-------------------------------------------------------------
CLAIM_01_TEMPORAL_POST_HOLDOUT                | Domain 01: Temporal Governance   | system_freeze_manifest.json                 | src.data.access_guard:assert_data_access   | POST_HOLDOUT_P11R      | PASS                  | 2024 evaluated post-repair; sealed from further evaluation.
CLAIM_02_POINT_CHAMPION_SELECTION             | Domain 02: Point Champion        | academic_model_selection_v1.json            | src.models.linear_baseline:RidgeBaseline   | DEVELOPMENT (2016-2023)| PASS                  | Ridge ties Ensemble within ±0.10m MAE; point-only forecast.
CLAIM_03_PROBABILISTIC_P5_CRPS                | Domain 03: P5 Quantile Forecast  | r34_p5_capability_forensics.json            | src.models.probabilistic.quantile          | HISTORICAL (Role B)    | PASS_WITH_RESERVATION | Role B Champion (FORECAST_ONLY); no checkpoint on disk.
CLAIM_04_PROBABILISTIC_P4_STUDENT_T           | Domain 04: P4 Continuous Dist    | model_weights_frozen_v1.joblib              | src.models.probabilistic.baselines:B5      | ROLE_C_ENGINE (2024)   | PASS                  | Role C Stochastic Engine; marginal calibration not certified.
CLAIM_05_SINGLE_OVERALL_CHAMPION              | Domain 05: Multi-Attribute Role  | system_freeze_manifest.json                 | Decoupled Utility Architecture             | SYSTEM_ARCHITECTURE   | PASS                  | Single joint champion rejected; decoupled Role B vs Role C.
CLAIM_06_CRN_VARIANCE_REDUCTION               | Domain 06: CRN Variance Reduct   | crn_variance_reduction_report.json          | PCG64 Latent Generator                    | SIMULATION_METHODOLOGY | PASS                  | Unverified 82.4% reduction claim retracted (NOT_SUPPORTED).
CLAIM_07_MC_N500_OPTIMALITY                   | Domain 07: MC Sample Convergence | pilot_robustness_results.json               | Convergence Grid N in [100, 2500]          | SIMULATION_METHODOLOGY | PASS                  | N=500 optimality retracted; certified as pragmatic budget.
CLAIM_08_REAL_WORLD_GATE_OPERATIONS           | Domain 08: Simulation Boundary   | system_freeze_manifest.json                 | AircraftTurnModel & 10-Gate Airfield       | SIMULATION_BOUNDARY    | PASS                  | Claims strictly bounded to synthetic simulation; no real ATL.
CLAIM_09_ORACLE_EQUIVALENCE                   | Domain 09: Oracle Brittleness    | robustness_results.json (P11R)              | Mode A Fixed-Plan Robustness Realization   | POST_HOLDOUT_P11R      | PASS                  | Oracle is theoretical non-deployable bound; fragile (0% feas).
CLAIM_10_DOWNSTREAM_SEMANTICS                 | Domain 10: Downstream Solvers    | downstream_results.parquet (P11R)           | DeterministicGreedy, CPSat, SA, Hybrid     | POST_HOLDOUT_P11R      | PASS                  | Equal wall-clock budget (2.0s); does not prove equal FLOPs.
CLAIM_11_STATISTICAL_SIGNIFICANCE             | Domain 11: Statistical Inference | downstream_results.csv (P11R)               | Day-cluster bootstrap on FL_DATE + Holm-Bon| STATISTICAL_PROTOCOL   | PASS                  | Exchangeability assumed across distinct calendar dates.
CLAIM_12_AUXILIARY_DEPARTURE_DELAY            | Domain 12: Input Isolation       | feature_manifest_arrival_v1.json            | Arrival Input Boundary Validator           | INPUT_CONTRACT         | PASS                  | Auxiliary models isolated; raw .pt flight chains rejected.
CLAIM_13_REPRODUCIBILITY_STANDARDS            | Domain 13: Reproducibility Stds  | system_freeze_manifest.json                 | SHA-256 sidecars & deterministic seeds     | GOVERNANCE_LINEAGE     | PASS_WITH_RESERVATION | Raw CSVs lack initial SHA-256; universal bitwise NOT_PROVEN.
================================================================================================================================================================
```

---

## 3. STEP 2: DATA INTEGRITY CERTIFICATION

1. **Source Dataset Identity:** Bureau of Transportation Statistics (BTS) Airline On-Time Performance (2016–2024) combined with hourly surface METAR weather observations.
2. **Schema & Traceability:** Governed by `schema_version = v1` and `flight_key_contract` (`flight_key_v1`). Flight keys ensure record traceability without serving as predictive features.
3. **ATL Inbound Isolation:** Physical Parquet partition store at `data/processed/inbound_atl/year={year}` strictly filters `DEST == 'ATL'`.
4. **Temporal Partitioning:**
   - Rolling Development: Calendar years 2016 through 2022 (38.8M source flights, 2.37M ATL inbound flights).
   - Validation & Model Selection: Calendar year 2023 (6.81M source flights, 340,860 ATL inbound flights).
   - Sealed Holdout: Calendar year 2024 (7.09M source flights).
5. **Raw Data Immutability:** Historical partitions in `data/processed/` and `data/raw/` remain bit-for-bit immutable on disk.

---

## 4. STEP 3 & 4: TARGET, CUTOFF & FEATURE LEAKAGE AUDIT

### Target & Cutoff Contract:
* **Target Airport:** `DEST = ATL` (Hartsfield-Jackson Atlanta International Airport).
* **Classification Target:** Binary event $\text{SevereDelay} = (\text{ARR\_DELAY} \ge 15.0\text{ min})$.
* **Regression Target:** Continuous signed arrival delay $\text{ARR\_DELAY} \in (-\infty, +\infty)$ in minutes.
* **Prediction Cutoff:** Strictly enforced at $\text{CRS\_DEP\_TIME} - 120\text{ minutes}$ ($T-2\text{h}$).

### Feature Leakage Verification:
The 11 frozen predictors in [`feature_manifest_arrival_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/manifests/feature_manifest_arrival_v1.json) and [`src/features/tabular_features.py`](file:///D:/Study/Code/Python/Aelous/src/features/tabular_features.py) were audited against all prohibited information channels:
* **Zero Weather Features:** METAR, TAF, visibility, wind speed, and convective precipitation indices are 100% excluded from Core Arrival prediction inputs.
* **Zero Departure Delay Features:** Actual departure delays ($\text{DEP\_DELAY}$) and downstream departure timestamps ($\text{DEP\_TIME}$) are 100% excluded.
* **Zero Future Outcomes:** No post-cutoff actual outcomes, wheels-off, wheels-on, or taxi durations are accessible to the models.
* **Zero Flight Chain Leakage:** Raw PyTorch geometric (`.pt`) graph neural network embeddings and acausal tail-number chain files are strictly barred by the input validator.

---

## 5. STEP 5: POINT FORECASTING CERTIFICATION

* **Historical Point Development (2016–2023):** As certified in `academic_model_selection_v3.json` and `test_r25_point_selection_consistency.py`, the `Ridge` baseline (`arrival_linear_baseline_v1`) and the `Weighted Ensemble` (`arrival_weighted_ensemble_v1`) tied on the 2023 validation set within the pre-registered tolerance band of $\pm 0.10$ minutes MAE.
* **Historical Post-Holdout 2024:** `arrival_linear_baseline_v1` achieved Point MAE of **22.91 min**; `arrival_weighted_ensemble_v1` achieved **23.32 min**.
* **P11-R Repaired Post-Holdout 2024:** Evaluated with preprocessors fitted strictly on the 2016–2022 development set, `arrival_linear_baseline_v1` achieved Point MAE of **23.39 min** (RMSE: 52.94 min).
* **Governance Invariant:** No joint overall champion is declared. Point models are certified as point-only comparators and are ineligible for continuous downstream stochastic simulation.

---

## 6. STEP 6: P4 CERTIFICATION (ROLE C: CONTINUOUS STOCHASTIC DOWNSTREAM ENGINE)

* **Model Checkpoint:** Serialized at [`artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib`](file:///D:/Study/Code/Python/Aelous/artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib).
* **Cryptographic Hash:** SHA-256 confirmed bit-for-bit at `e7e7462f17b65b276ebdee9c7beced15e090f69b088a18896d5a91aaa8cb062f`.
* **Distribution Family:** Heteroscedastic 3-Parameter Student-$t$ distribution yielding $[\mu(x), \sigma(x), \nu(x)]$, with heavy-tail constraint $\nu(x) \ge 2.10$ and scale floor $\sigma(x) \ge 10^{-4}$.
* **Empirical Degrees of Freedom on 2024:** Mean $\nu = 2.52$ (range $[2.10, 2.78]$), rigorously confirming fat-tailed arrival dynamics.
* **Proper Scoring Rules:**
  - Exact Closed-Form Continuous CRPS: **18.33 minutes** (Student-$t$ integration).
  - Exact Continuous NLL: **4.62**.
  - Tail Event Brier Score ($Y \ge 15$ min): **0.1544**.
* **Sampling Capability:** Full inverse CDF continuous sampling via PCG64 PRNG ($U \sim \text{Uniform}(0.001, 0.999)$).
* **Calibration State:** Certified as `NOT_SEPARATELY_CERTIFIED` (80% interval coverage is 76.12%; 90% interval coverage is 84.54%).

---

## 7. STEP 7: P5 CERTIFICATION (ROLE B: MARGINAL QUANTILE FORECAST CHAMPION)

* **Decoupled Role B Declaration:** `P5_quantile_regression` is the permanent **Marginal Quantile Forecast Champion** (`FORECAST_ONLY`).
* **Predictive Structure:** 9 registered quantiles ($\tau \in \{0.10, 0.20, \dots, 0.90\}$) with monotone rearrangement.
* **Continuous Sampling Bar:** P5 has no continuous density function, no joint multivariate covariance mechanism, and is **strictly prohibited from acting as a downstream continuous stochastic sampler**.
* **Checkpoint Status:** `NO_SERIALIZED_CHECKPOINT` on disk. Historical predictions are certified from immutable evaluation logs. In accordance with Forensic Audit R39, **P5 reconstruction is NOT REQUIRED for the core downstream thesis**.

---

## 8. STEP 8 & 9: DOWNSTREAM GATE SIMULATION & SOLVER FAIRNESS

* **Simulation Boundary:** All gate assignments and operational metrics are bounded to the **Synthetic Airfield Simulation Model** ([`AircraftTurnModel`](file:///D:/Study/Code/Python/Aelous/src/evaluation/downstream_comparison_v2.py)) with 10 contact gates and 1 overflow apron. Real-world ATL airport operational optimality claims are strictly prohibited.
* **Solver Equal Compute:** All four solvers operated under an identical wall-clock ceiling:
  ```
  EQUAL_WALL_CLOCK_BUDGET (2.0s ceiling)
  ```
  *(Certified as equal wall-clock time; does not imply equal floating-point operation counts).*
* **Downstream Benchmark Results (64 Solver Runs on 2024):**
  - **`DeterministicGreedy`:** Solves in $0.51 - 2.31\text{ ms}$; produces feasible schedules with zero constraint violations.
  - **`CPSat`:** Solves in $65.7 - 1,016.5\text{ ms}$; proves **100% global optimality** with 0.0% gap across all scenarios.
  - **`SimulatedAnnealing`:** Exhausts full 2,000 ms ceiling; achieves within $0.1\%$ of optimal objective.
  - **`HybridCPSatSA`:** Solves in $1,064 - 2,010\text{ ms}$; matches the global CP-SAT optimum in 100% of runs.

---

## 9. STEP 10: MONTE CARLO ROBUSTNESS & RECOURSE

* **Monte Carlo Protocol:** Canonical $N = 500$ realizations; PRNG generator `numpy.random.default_rng(202601)`.
* **Common Random Numbers (CRN):** Empirical CRN matrix active. Historical claim of 82.4% variance reduction remains retracted (`NOT_SUPPORTED`).
* **Mode A (Fixed-Plan Robustness Under P4 Shocks):**
  - In peak summer congestion (`SCEN_2024_SUMMER`, 60 flights, 15 gates), the fixed plan generated by `P4_ngboost_student_t` achieved **100.0% feasibility** (zero gate conflicts across all 500 realizations).
  - In contrast, `schedule_only` degraded to **27.6% feasibility** (0.72 average conflicts).
  - The linear baseline (`arrival_linear_baseline_v1`) collapsed to **2.4% feasibility** (1.67 average conflicts).
  - The acausal point oracle (`oracle_actual`) collapsed to **0.0% feasibility** (9.58 average conflicts), proving that point-optimized schedules without stochastic margin collapse catastrophically under arrival jitter.
* **Mode B (Recourse Re-Optimization):** Dynamic real-time gate reassignments resolved **100% of realized conflicts** in $<1.0\text{ ms}$ per realization across all seasons.

---

## 10. STEP 11: HISTORICAL 2024 EVIDENCE VS P11R POST-HOLDOUT RE-EVALUATION

```
========================================================================================================================
HISTORICAL 2024 EVIDENCE VS P11R POST-HOLDOUT RE-EVALUATION DUAL REPORTING
========================================================================================================================
Metric / Dimension                           | Historical Generation 2 (Sept 2026)             | Repaired P11-R Generation (Oct 2026)            | Root Cause of Divergence
---------------------------------------------+-------------------------------------------------+-------------------------------------------------+---------------------------------------------------
Evaluation Role Label                        | POST_HOLDOUT                                    | POST_HOLDOUT_REEVALUATION_AFTER_METHODOLOGY_REP | Mandatory labeling following methodology repair.
P4 Model Checkpoint                          | artifacts/probabilistic/ngboost_student_t/      | artifacts/probabilistic/ngboost_student_t/      | Identical frozen model weights (SHA: e7e7462f...).
P4 Point MAE on 2024                         | 21.96 min                                       | 21.97 min                                       | Consistent within 0.01 min.
P4 Continuous CRPS                           | 17.65 min (Discrete quantile approximation)    | 18.33 min (Exact closed-form Student-T formula) | Repaired mathematically exact Student-T integral.
P4 Heavy-Tail Degrees of Freedom             | Reported as unverified distribution parameter   | Empirically verified mean nu = 2.52 in [2.1, 2.8] | Strict validation of Student-T tail thickness.
P5 Quantile Regression Role                  | Unclear downstream candidate                    | Strictly locked as Role B (FORECAST_ONLY)       | Barred from continuous downstream simulation (R39).
Downstream Simulation Engine                 | Heuristic P5 quantile sampling / discrete proxy | Native P4 Student-T continuous CRN inverse CDF  | Architectural repair certified in P10-A.
Summer Fixed-Plan Feasibility (P4)           | 100.0%                                          | 100.0% (Zero conflicts across 500 shocks)       | Robustness certified under native Student-T shocks.
Downstream Failure Accounting                | 0 dropped flights                               | 0 dropped flights (Zero-dropping contract)      | Exact audit trail verified across all 64 runs.
========================================================================================================================
```

---

## 11. STEP 12: FINAL CLAIM STATUS & OVERALL CERTIFICATION

Each of the 13 certified scientific domains has been evaluated independently:
* 11 domains achieved **`PASS`**.
* 2 domains achieved **`PASS_WITH_RESERVATION`** (Domain 03: P5 forecast-only status; Domain 13: unhashed raw CSV files and unproven universal bitwise reproduction).
* 0 domains failed (`FAIL = 0`); 0 domains unverified (`UNVERIFIED = 0`).

Because the core scientific chain is complete, verifiable, and free of contradictions, but bounded limitations exist:
```
CERTIFICATION_STATUS = CERTIFIED_WITH_LIMITATIONS
```

---

## 12. STEP 13: CONDITIONAL REBUILD DECISION

A comprehensive review of the eight legitimate rebuild triggers was conducted:
1. **Predictor Leakage:** `CLEAN` — Verified 11 predictors; zero weather, zero departure delay.
2. **Cutoff Violation:** `CLEAN` — Strictly enforced at $T-2\text{h}$.
3. **Invalid Training Protocol:** `CLEAN` — 2016–2022 development only; 2023 validation; 2024 holdout.
4. **Invalid Model Artifact:** `CLEAN` — Certified P4 checkpoint verified with cryptographic SHA-256.
5. **Invalid Prediction Artifact:** `CLEAN` — Post-holdout Parquet and JSON files valid and complete.
6. **Holdout Contamination:** `CLEAN` — 2024 accessed only under frozen guard; zero training or tuning.
7. **Forbidden Information in Ensemble:** `CLEAN` — Standard point features only.
8. **Scientifically Invalid Metric:** `CLEAN` — Proper scoring rules (Student-t CRPS, continuous NLL, Brier score).

```
REBUILD_REQUIRED = NO
```
Zero scientific justifications for a repository rebuild exist. All historical contradictions and legacy guard drift were resolved through explicit versioned governance without altering scientific code.

---

## 13. STEP 14: KNOWN LIMITATIONS

1. **2024 Post-Holdout Status:** Calendar year 2024 evidence is classified as `POST_HOLDOUT_REEVALUATION_AFTER_METHODOLOGY_REPAIR` and must never be represented as an untouched, first-access holdout.
2. **P5 Forecast-Only Status:** `P5_quantile_regression` has no serialized model checkpoint on disk and is strictly barred from continuous downstream sampling.
3. **P4 Calibration Disclosure:** Native P4 predictive intervals are mathematically proper but remain `NOT_SEPARATELY_CERTIFIED` for empirical coverage calibration.
4. **Bitwise Platform Reproducibility:** Universal cross-platform bit-for-bit reproducibility across unpinned operating systems and CPU microarchitectures is `NOT_PROVEN`.
5. **Synthetic Simulation Boundary:** Gate optimization results are bounded strictly to a simulated 10-contact-gate airfield and cannot be extrapolated to real-world ATL operations.
6. **Equal Wall-Clock Limitation:** The 2.0-second solver ceiling proves equal wall-clock time termination, not equal computational FLOPs.
7. **Raw Data Hash Absence:** Multi-gigabyte raw CSV files lack initial cryptographic SHA-256 checksum sidecars (`DATA_HASH = UNAVAILABLE`).

---

## 14. FINAL GATE DECLARATION

```
P14_STATUS = PASS

CERTIFICATION_STATUS = CERTIFIED_WITH_LIMITATIONS

REBUILD_REQUIRED = NO
```

The final scientific certification and rebuild decision is complete and formally closed. In accordance with instructions, execution stops here (**DỪNG**).
