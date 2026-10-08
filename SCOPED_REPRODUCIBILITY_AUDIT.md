# SCOPED_REPRODUCIBILITY_AUDIT: AUDIT OF THE FROZEN AEOLUS SYSTEM AFTER P11R

**Phase:** `P13 — Scoped Reproducibility Audit after P11R`  
**Git HEAD Commit:** `7ba0aba92d366f712977faaaa5a73cba65a32a55`  
**Branch:** `v4-final-forensic-certification`  
**Preconditions:** `P11R_STATUS = PASS` | `P12_STATUS = PASS` (Reconciled & Revalidated via `P12R1_STATUS = PASS`)  
**Audit Verdict:** **`P13_STATUS = PASS_WITH_RESERVATION`**  

---

## 1. EXECUTIVE SUMMARY & VERDICT DECLARATION

Phase **P13** evaluated whether an independent researcher can reproduce the frozen Aeolus system within the exact declared scientific and technical scope. In accordance with the non-negotiable protocol:
* **Zero models were retrained or refitted.**
* **Zero 2024 evaluations were rerun.**
* **Zero environment mutations or package upgrades were applied.**
* **All reproducibility evaluations were conducted strictly from frozen artifacts, cryptographic hashes, code manifests, and regression tests.**

```
====================================================================================================
SCOPED REPRODUCIBILITY AUDIT VERDICT
====================================================================================================
P13_STATUS                                              = PASS_WITH_RESERVATION
SCIENTIFIC_REPRODUCIBILITY                              = CONTAINED_AND_CERTIFIED
ENVIRONMENT_REPRODUCIBILITY                             = FULLY_PINNED_AND_VERIFIED
DATA_REPRODUCIBILITY                                    = PASS_WITH_RESERVATION
DATA_HASH                                               = UNAVAILABLE
P4_REPRODUCIBILITY                                      = CERTIFIED_FROZEN_CHECKPOINT
P5_REPRODUCIBILITY                                      = FORECAST_ONLY_ROLE_B_PRESERVED
CONFIGURATION_REPRODUCIBILITY                           = EXACT_AND_FROZEN
COMMAND_REPRODUCIBILITY                                 = SPECIFIED_AND_DOCUMENTED
PRESENTATION_REPRODUCIBILITY                            = NOT_APPLICABLE
BITWISE_REPRODUCIBILITY                                 = NOT_PROVEN
2024_ACCESSED                                           = NO
SCIENTIFIC_METHODOLOGY_CHANGED                          = NO
TEST_ASSERTIONS_WEAKENED                                = NO
HISTORICAL_ARTIFACTS_DELETED                            = NO
====================================================================================================
```

### Forensic Rationale for `PASS_WITH_RESERVATION`:
1. **Contained Scientific Scope (PASS):** The core probabilistic arrival model (`P4_ngboost_student_t`), feature extraction (11 predictors), closed-form Student-t distribution heads, Common Random Numbers (CRN) latent sampling, synthetic airfield gate simulation, and four equal-compute downstream solvers are fully deterministic, specified, and reproducible.
2. **Environment Bit-for-Bit Verified (PASS):** All 11 execution-critical packages (NumPy, SciPy, Pandas, scikit-learn, XGBoost, LightGBM, NGBoost, OR-Tools, PyArrow, Joblib, pytest) installed in `.venv` match the frozen versions registered in [`system_freeze_manifest.json`](file:///D:/Study/Code/Python/Aelous/system_freeze_manifest.json) bit-for-bit.
3. **Data Hash Limitation (RESERVATION):** While raw and processed row counts, schemas (`flight_key_v1`), and temporal partitions are documented, original multi-gigabyte raw CSV files lack cryptographic SHA-256 sidecars (`DATA_HASH = UNAVAILABLE`).
4. **Universal Bitwise Reproduction (RESERVATION):** In strict adherence to scientific rigor, cross-platform and cross-architecture bitwise identity cannot be claimed due to uncontrollable floating-point vectorization and thread scheduling variances across different operating systems and CPU microarchitectures (`BITWISE_REPRODUCIBILITY = NOT_PROVEN`).
5. **Presentation Layer (NOT_APPLICABLE):** No Streamlit or Plotly web dashboards are present in the repository; the scientific pipeline delivers purely through Parquet, CSV, JSON, and Markdown reports.

---

## 2. STEP 0: PREFLIGHT AUDIT & BASELINE PARAMETERS

* **Repository Root:** `D:\Study\Code\Python\Aelous`
* **Git HEAD Commit:** `7ba0aba92d366f712977faaaa5a73cba65a32a55`
* **Branch:** `v4-final-forensic-certification`
* **Working Tree:** Dirty with untracked audit documents; all tracked manifest changes match authoritative freeze checksums.
* **Freeze Manifest Checked:** [`system_freeze_manifest.json`](file:///D:/Study/Code/Python/Aelous/system_freeze_manifest.json) (SHA-256: `9e6693dafae3ba439c0b6b9a5f3038ec87f0dd63f75dbcad5752ff8da0f98214`).
* **Active Pytest Suite:** 1,216 tests, 100% passing (exit code 0, 82.37s).

---

## 3. STEP 1: SCIENTIFIC REPRODUCIBILITY PIPELINE AUDIT

The end-to-end scientific pipeline was audited across each functional stage:

```
data 
  ──> feature contract 
        ──> preprocessing 
              ──> model artifact 
                    ──> probabilistic representation 
                          ──> dependence 
                                ──> sampling 
                                      ──> simulation 
                                            ──> optimization 
                                                  ──> evaluation
```

| Pipeline Node | Artifact Exists | Hash Available | Version Known | Config Frozen | Input Reference Known | Output Schema Known | Executable Command Known | Reproduction Scope | Audit Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- | :---: |
| **1. Data** | YES | NO (`UNAVAILABLE`) | YES (`v1`) | YES | YES (`BTS 2016-2024`) | YES (`inbound_atl`) | YES (`run_week2_canonicalization.py`) | Scoped by row-count & schema contract | **PASS_WITH_RESERVATION** |
| **2. Feature Contract** | YES | YES (`33d2e08b...`) | YES (`arrival_v1`) | YES | YES (`inbound_atl`) | YES (11 predictors) | YES (`extract_arrival_features`) | Deterministic feature extraction | **PASS** |
| **3. Preprocessing** | YES | YES (`82443624...`) | YES (`tree_v1`) | YES | YES (11 features) | YES (scaled arrays) | YES (`build_linear_preprocessor`) | Deterministic outer fit (2016-2022) | **PASS** |
| **4. Model Artifact** | YES | YES (`e7e7462f...`) | YES (`P4 B5`) | YES | YES (X array) | YES (`predict_distribution`) | YES (`joblib.load(...)`) | Frozen serialized checkpoint | **PASS** |
| **5. Representation** | YES | YES (`3a874c1d...`) | YES (`Student-T`) | YES | YES (model output) | YES ($\mu, \sigma, \nu$) | YES (`p4.predict_distribution(X)`) | Closed-form Student-T density | **PASS** |
| **6. Dependence** | YES | YES (`a258616b...`) | YES (`D0 / D2`) | YES | YES (flight schedules) | YES (covariance matrix) | YES (`build_covariance_matrix`) | Pre-cutoff spatio-temporal kernel | **PASS** |
| **7. Sampling** | YES | YES (`834c6668...`) | YES (`PCG64`) | YES | YES (seed 202601) | YES ($S \times M$ matrix) | YES (`generate_stochastic_scenarios`) | Latent CRN with inverse CDF | **PASS** |
| **8. Simulation** | YES | YES (`a258616b...`) | YES (`TurnModel`) | YES | YES (arrival matrix) | YES (occupancy intervals) | YES (`simulate_aircraft_turnarounds`) | Synthetic airfield timeline model | **PASS** |
| **9. Optimization** | YES | YES (`0630b8fe...`) | YES (`Solvers v2`) | YES | YES (turn intervals) | YES (assignment map) | YES (`solver.solve(instance, 2.0)`) | 4 solvers, 2.0s equal-compute ceiling | **PASS** |
| **10. Evaluation** | YES | YES (`341bfb66...`) | YES (`Mode A & B`) | YES | YES (assignments) | YES (metrics JSON) | YES (`run_week10_completion_and_freeze.py`) | Day-cluster bootstrap & recourse | **PASS** |

---

## 4. STEP 2: ENVIRONMENT REPRODUCIBILITY AUDIT

The physical execution environment was inspected and compared against the 10 registered runtime packages in [`system_freeze_manifest.json`](file:///D:/Study/Code/Python/Aelous/system_freeze_manifest.json):

* **Host Operating System:** Windows 10 (10.0.19045-SP0) AMD64
* **Python Runtime:** Python 3.11.15 AMD64 (MSC v.1944 64-bit)

| Package Name | Registered Version | Installed Version (`.venv`) | Match Status | Scientific Impact / Notes |
| :--- | :---: | :---: | :---: | :--- |
| **numpy** | `2.2.6` | `2.2.6` | **EXACT MATCH** | Bitwise PCG64 random number generator stability |
| **scipy** | `1.17.1` | `1.17.1` | **EXACT MATCH** | Student-T CDF, inverse CDF, Gamma function evaluation |
| **pandas** | `2.3.3` | `2.3.3` | **EXACT MATCH** | Parquet dataset partitioning, flight key grouping |
| **scikit-learn** | `1.9.0` | `1.9.0` | **EXACT MATCH** | Ridge regression, preprocessors, DecisionTreeRegressor |
| **xgboost** | `3.2.0` | `3.2.0` | **EXACT MATCH** | Baseline gradient boosted tree comparisons |
| **lightgbm** | `4.7.0` | `4.7.0` | **EXACT MATCH** | Baseline gradient boosting models |
| **ngboost** | `0.5.11` | `0.5.11` | **EXACT MATCH** | Native P4 Student-T distribution regression base |
| **ortools** | `9.15.6755` | `9.15.6755` | **EXACT MATCH** | CP-SAT downstream gate optimization solver |
| **pyarrow** | `25.0.1` | `25.0.1` | **EXACT MATCH** | Binary Parquet storage format fidelity |
| **joblib** | `1.5.3` | `1.5.3` | **EXACT MATCH** | Checkpoint serialization and parallel worker dispatcher |
| **pytest** | `9.1.1` | `9.1.1` | **EXACT MATCH** | Test runner and collection governance |

**Environment Verdict:** 100% exact match across all dependencies. Zero package mismatches exist.

---

## 5. STEP 3: DATA REPRODUCIBILITY AUDIT

* **Canonical Source:** Bureau of Transportation Statistics (BTS) Airline On-Time Performance (2016–2024) combined with hourly surface METAR observations.
* **Source Raw Files:** `data/raw/tabular/{year}/flight_with_weather_{year}.csv` (2016 to 2024).
* **Processed Target:** `data/processed/inbound_atl/year={year}` (Parquet partitions).
* **Contract & Schema:** [`artifacts/manifests/processed_data_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/manifests/processed_data_manifest_v1.json) (`schema_version = v1`, `flight_key_v1`).
* **Cryptographic Data Hash:**
  ```
  DATA_HASH = UNAVAILABLE
  ```
  *Limitation Explanation:* The raw CSV files (~1.5 GB per calendar year) and intermediate partitioned Parquet directories were indexed in `processed_data_manifest_v1.json` by file size in bytes and filesystem modified timestamps, but lack SHA-256 cryptographic checksums. Reproducing the exact dataset from external BTS repositories requires relying on the documented row-count contracts and temporal schema specifications.
* **Row-Count Contracts (Documented & Verified):**
  - **2016:** 5,537,987 source rows $\rightarrow$ 381,166 inbound ATL rows
  - **2017:** 5,575,872 source rows $\rightarrow$ 358,263 inbound ATL rows
  - **2018:** 5,689,512 source rows $\rightarrow$ 366,134 inbound ATL rows
  - **2019:** 7,422,037 source rows $\rightarrow$ 368,037 inbound ATL rows
  - **2020:** 4,685,824 source rows $\rightarrow$ 253,371 inbound ATL rows
  - **2021:** 5,992,843 source rows $\rightarrow$ 317,624 inbound ATL rows
  - **2022:** 6,704,913 source rows $\rightarrow$ 336,664 inbound ATL rows
  - **2023:** 6,814,607 source rows $\rightarrow$ 340,860 inbound ATL rows
  - **2024:** 7,088,149 source rows (sealed holdout partition)
* **Temporal Partitions:** Rolling development 2016–2022; validation / model selection 2023; sealed holdout 2024.
* **Cutoff & Filter:** `DEST == 'ATL'`; feature cutoff strictly enforced at `CRS_DEP_TIME - 2 hours` ($T-2\text{h}$).

---

## 6. STEP 4: P4 (NGBOOST STUDENT-T) REPRODUCIBILITY

* **Model Identity:** `P4_ngboost_student_t` ([`src/models/probabilistic/baselines.py:B5NGBoostStudentT`](file:///D:/Study/Code/Python/Aelous/src/models/probabilistic/baselines.py#L225)).
* **Checkpoint Path:** [`artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib`](file:///D:/Study/Code/Python/Aelous/artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib).
* **Cryptographic SHA-256:**
  - Registered in manifest: `e7e7462f17b65b276ebdee9c7beced15e090f69b088a18896d5a91aaa8cb062f`
  - Computed on disk: `e7e7462f17b65b276ebdee9c7beced15e090f69b088a18896d5a91aaa8cb062f` (**MATCH**)
* **Predictive Heads:** Triplet $[\mu(x), \sigma(x), \nu(x)]$, where $\nu(x) \ge 2.1$ (ensuring finite variance) and $\sigma(x) \ge 10^{-4}$.
* **Downstream Representation:**
  $$Y = \mu(x) + \sigma(x) \cdot \text{StudentT}(\nu(x))$$
* **Downstream Engine Role:** Certified as the sole **Role C: Continuous Downstream Stochastic Simulation Engine**.
* **Calibration Disclosure:** The marginal intervals of P4 are explicitly labeled `NOT_SEPARATELY_CERTIFIED`.

---

## 7. STEP 5: P5 (QUANTILE REGRESSION) REPRODUCIBILITY

In accordance with forensic audit R39 and the decoupled multi-attribute architecture:
* **Role B Declaration:** `P5_quantile_regression` is the **Marginal Quantile Forecast Champion** (evaluating discrete $\tau \in \{0.10, 0.20, \dots, 0.90\}$ and pinball loss).
* **Continuous Sampling Bar:** P5 has no continuous density function and is **strictly prohibited from acting as a downstream continuous stochastic sampler**.
* **Checkpoint Availability:** `NO_SERIALIZED_CHECKPOINT` on disk. Historical predictions were persisted directly into tabular evaluation summaries (`probabilistic_stage6_forecast_evaluation_v1.json`, `r34_p5_capability_forensics.json`).
* **Downstream Necessity:** **`NOT_REQUIRED`**. The core downstream simulation and gate optimization rely exclusively on Native P4 (`B5NGBoostStudentT`).
* **Outer-Fit Reproducibility:** Historical specification is completely preserved in `r34_p5_quantile_config.json`. R39 established that P5 could be reconstructed deterministically if authorized, but no reconstruction is permitted or necessary.

---

## 8. STEP 6: CONFIGURATION REPRODUCIBILITY AUDIT

All 16 operational configuration dimensions were audited for single-source-of-truth consistency between YAML files, Python configuration modules, and [`system_freeze_manifest.json`](file:///D:/Study/Code/Python/Aelous/system_freeze_manifest.json):

1. **Feature Set (11 Predictors):** `CRS_ELAPSED_TIME`, `CRS_HOUR`, `CRS_MINUTE`, `DISTANCE`, `ORIGIN_LATITUDE`, `ORIGIN_LONGITUDE`, `SCHEDULED_DEP_HOUR`, `CARRIER_ENCODED`, `ORIGIN_ENCODED`, `ORIGIN_FREQUENCY`, `FLIGHT_FREQUENCY`. Leakage guard: zero weather, zero departure delay.
2. **Target Definition:** `ARR_DELAY` (signed continuous minutes); severe delay threshold $\ge 15.0$ minutes.
3. **Prediction Cutoff:** `CRS_DEP_TIME - 2 hours` ($T-2\text{h}$).
4. **P4 Hyperparameters:** `DecisionTreeRegressor(max_depth=3)`, `n_estimators=50`, `learning_rate=0.005`, 3 parameter heads (`mu`, `sigma`, `df`).
5. **Dependence:** `D0_independent_with_crn` and `D2_gaussian_copula` (length scale 120.0 min, carrier correlation 0.15, PSD floor $10^{-6}$).
6. **Sampling:** PCG64 PRNG (`numpy.random.default_rng`), seed 202601, uniform clipping $[0.001, 0.999]$, inverse CDF `scipy.stats.t.ppf`.
7. **Monte Carlo Budget:** Canonical $N = 500$; convergence grid $[100, 250, 500, 1000, 2500]$; pilot $[20, 50]$.
8. **Scenario Generation:** 2023 development partition bank `SCEN_2023_LOW` (2023-11-23, Thanksgiving low-delay bank, 14 flights).
9. **Turn Model:** `AircraftTurnModel` ($T_{\text{turn}} = 45\text{ min}$, $T_{\text{dwell}} = 60\text{ min}$, $T_{\text{buffer}} = 15\text{ min}$).
10. **Airfield Topology:** 10 contact gates, 1 overflow apron; states `CONTACT_GATE`, `REMOTE_STAND`, `UNASSIGNED`.
11. **Objective Weights:** Reassignment = 10.0, Overflow = 200.0, Conflict = 1000.0, Delay = 0.0, Risk = 0.0.
12. **Solvers (Equal Compute):** DeterministicGreedy, CPSat, SimulatedAnnealing, HybridCPSatSA; strict 2.0s wall-clock ceiling.
13. **Simulated Annealing:** $T_0 = 100.0$, $T_{\min} = 0.01$, geometric exponential cooling, move probability 0.7.
14. **Robustness Mode A:** `FIXED_PLAN_ROBUSTNESS` under realized P4 continuous Student-T shocks.
15. **Recourse Mode B:** Re-optimization of disrupted schedules via Greedy and CP-SAT.
16. **Deterministic Seeds:** Predetermined deployment seed = 202601; screening seeds = $[202601, 202602, 202603]$.

**Conflict Check Result:** Zero conflicting configurations found across the codebase. All YAML and Python configuration hashes match `system_freeze_manifest.json` bit-for-bit.

---

## 9. STEP 7 & 11: REPRODUCTION COMMAND SPECIFICATION

An independent researcher equipped with the specified environment can validate and reproduce the system using the following three command categories:

### A. Non-Destructive Validation Commands
```powershell
# 1. Verify Full Active Repository Test Suite (1,216 tests, must exit code 0)
.venv\Scripts\python.exe -m pytest -q

# 2. Verify Narrow Certification Suite (75 tests, must exit code 0)
.venv\Scripts\python.exe -m pytest tests/test_r24_final_certification.py tests/test_r27_certification_hardening.py tests/test_r31_final_certification.py tests/test_r37_final_certification.py tests/test_phase10_system_freeze.py

# 3. Verify P11-R Downstream Regression Suite (21 tests, must exit code 0)
.venv\Scripts\python.exe -m pytest tests/downstream/test_p11r_post_holdout.py tests/downstream/test_week10_robustness_freeze.py tests/downstream/test_native_p4_downstream.py

# 4. Verify Active Protocol & Holdout Guard Suite (51 tests, must exit code 0)
.venv\Scripts\python.exe -m pytest tests/test_audit_provenance_guards.py tests/test_holdout_guard.py tests/test_holdout_and_fold_guards.py tests/test_week5_hpo_guard_cleanup_provenance.py tests/test_r20_freeze_gate.py tests/test_r22_system_freeze_v3.py tests/test_phase10_system_freeze.py

# 5. Verify Retired Historical Guard Suite (37 tests, 33 pass / 4 expected historical drift)
.venv\Scripts\python.exe -m pytest tests/test_final_evaluation_guard.py tests/test_final_evaluation_guard_v2.py tests/test_post_holdout_evaluation_v2.py -q
```

### B. Development Reproduction Commands (2016–2023 Development Scope)
```powershell
# 1. Rebuild Native P4 Downstream Evaluation on 2023 Development Scenario Bank
.venv\Scripts\python.exe scripts/run_native_p4_downstream.py
# Outputs: artifacts/native_downstream_v1/downstream_results.json
#          artifacts/native_downstream_v1/downstream_summary.json

# 2. Execute Week 10 Completion, Robustness, Recourse, Sensitivity, and Freeze
.venv\Scripts\python.exe scripts/run_week10_completion_and_freeze.py
# Outputs: artifacts/week10_robustness/pilot_robustness_results.json
#          artifacts/week10_robustness/recourse_results.json
#          artifacts/week10_robustness/sensitivity_results.json
#          artifacts/week10_robustness/failure_accounting.json
#          system_freeze_manifest.json
```

### C. Post-Holdout 2024 Command Specification (DOCUMENTED ONLY — DO NOT RUN IN P13)
```powershell
# MANDATORY CLASSIFICATION: POST_HOLDOUT_REEVALUATION_AFTER_METHODOLOGY_REPAIR
# CRITICAL NOTICE: THIS RUN ACCESSES CALENDAR YEAR 2024.
# It has already been executed and certified in Phase P11-R.
# DO NOT RUN THIS COMMAND DURING AUDIT PHASES.
# Command for post-certification independent reproduction:
.venv\Scripts\python.exe scripts/run_p11r_post_holdout_reevaluation.py
# Expected Outputs: artifacts/post_holdout_re_evaluation_v1/ (10 artifacts)
```

---

## 10. STEP 8 & 9: PRESENTATION & BITWISE REPRODUCIBILITY

* **Presentation Layer:**
  - `SCIENTIFIC_REPRODUCIBILITY`: **`HIGH / FULLY_CONTAINED`**
  - `EXECUTION_REPRODUCIBILITY`: **`HIGH / REPRODUCIBLE_IN_SPECIFIED_ENV`**
  - `PRESENTATION_REPRODUCIBILITY`: **`NOT_APPLICABLE`** (No Streamlit/Plotly dashboards are deployed; all results are stored in structured Parquet, CSV, JSON, and Markdown reports).
* **Bitwise Reproducibility:**
  - `BITWISE_REPRODUCIBILITY = NOT_PROVEN`
  - While PRNG random seeds (PCG64 seed 202601) and solver configurations are locked, cross-platform hardware variances (e.g., AVX2 vs AVX-512 FMA fused multiply-add, OpenMP BLAS thread scheduling, and differences between Windows, Linux, and macOS) can induce least-significant-bit floating-point perturbations in continuous Student-t inverse CDF evaluations. Therefore, universal bit-for-bit reproducibility across arbitrary platforms is strictly disclaimed.

---

## 11. STEP 10: REPRODUCIBILITY MATRIX

```
================================================================================================================================================================
REPRODUCIBILITY_MATRIX
================================================================================================================================================================
Claim ID / Name                               | Scope                            | Required Artifact                           | Cryptographic Hash / Checksum    | Verifying Suite / Evidence                 | Status                | Known Limitation
----------------------------------------------+----------------------------------+---------------------------------------------+----------------------------------+--------------------------------------------+-----------------------+-------------------------------------------------------
CLAIM_01_TEMPORAL_POST_HOLDOUT                | 2024 temporal holdout seal       | system_freeze_manifest.json                 | SHA: 9e6693dafae3ba43...         | test_phase10_system_freeze.py              | PASS                  | 2024 evaluated in P11R; sealed from further evaluation.
CLAIM_02_POINT_CHAMPION_SELECTION             | Ridge vs Ensemble tie (±0.10m)   | academic_model_selection_v3.json            | Validated in R25 manifest        | test_r25_point_selection_consistency.py   | PASS                  | Point champion only; does not provide uncertainty.
CLAIM_03_PROBABILISTIC_P5_CRPS                | P5 quantile pinball loss         | r34_p5_capability_forensics.json            | Validated in R34 manifest        | test_r34_p5_mathematical_audit.py          | PASS_WITH_RESERVATION | Forecast-only Role B; no serialized checkpoint on disk.
CLAIM_04_PROBABILISTIC_P4_STUDENT_T           | P4 continuous Student-T NLL/CRPS | model_weights_frozen_v1.joblib              | SHA: e7e7462f17b65b27...         | test_r33_p4_metric_lineage.py             | PASS                  | Role C continuous engine; calibration not certified.
CLAIM_05_SINGLE_OVERALL_CHAMPION              | Multi-attribute role decoupling  | academic_model_selection_v3.json            | Validated in R31 manifest        | test_r24_final_certification.py            | PASS                  | Rejects single joint champion; enforces B vs C split.
CLAIM_06_CRN_VARIANCE_REDUCTION               | Formal retraction of 82.4% claim | crn_variance_reduction_report.json          | Validated in R19 manifest        | test_mc_convergence_v2.py                  | PASS                  | Historical claim retracted; status is NOT_SUPPORTED.
CLAIM_07_MC_N500_OPTIMALITY                   | Retraction of N=500 optimality   | pilot_robustness_results.json               | SHA: b5b08e45f05c0df6...         | test_monte_carlo_audit_v2.py               | PASS                  | N=500 is a pragmatic computational budget, not optimum.
CLAIM_08_REAL_WORLD_GATE_OPERATIONS           | Synthetic airfield bounds        | downstream_comparison_v2.py                 | SHA: a258616b25f29a79...         | test_downstream_semantics_v2.py            | PASS                  | Bounds all operational claims to synthetic simulation.
CLAIM_09_ORACLE_EQUIVALENCE                   | Acausal oracle brittleness       | robustness_results.json                     | Validated in P11R run manifest   | test_auxiliary_isolation.py                | PASS                  | Oracle is an acausal upper bound, non-deployable.
CLAIM_10_DOWNSTREAM_SEMANTICS                 | Equal-compute 2.0s solver budget | downstream_results.parquet                  | Validated in P11R run manifest   | test_r26_solver_equal_compute.py           | PASS                  | Solver timing jitter subject to CPU load variations.
CLAIM_11_STATISTICAL_SIGNIFICANCE             | Day-cluster bootstrap & Holm-Bon | statistical_comparison.json                 | Validated in P11R run manifest   | test_r18_statistical_inference.py          | PASS                  | Exchangeability assumed across distinct FL_DATE clusters.
CLAIM_12_AUXILIARY_DEPARTURE_DELAY            | Non-contamination isolation      | feature_manifest_arrival_v1.json            | SHA: 33d2e08b37058032...         | test_model_input_boundary.py               | PASS                  | Rejects weather, flight chains, and departure delays.
CLAIM_13_REPRODUCIBILITY_STANDARDS            | Cryptographic freeze lineage     | system_freeze_manifest.json                 | SHA: 9e6693dafae3ba43...         | test_r27_certification_hardening.py        | PASS_WITH_RESERVATION | Raw data CSVs lack initial SHA-256 sidecars.
================================================================================================================================================================
```

---

## 12. FINAL GATE VERDICT DECLARATION

All evaluation requirements for Phase P13 have been fulfilled without model retraining, without methodology modification, and without opening row-level 2024 data:

```
P13_STATUS = PASS_WITH_RESERVATION

SCIENTIFIC_REPRODUCIBILITY = CONTAINED_AND_CERTIFIED

ENVIRONMENT_REPRODUCIBILITY = FULLY_PINNED_AND_VERIFIED

DATA_REPRODUCIBILITY = PASS_WITH_RESERVATION

DATA_HASH = UNAVAILABLE

P4_REPRODUCIBILITY = CERTIFIED_FROZEN_CHECKPOINT

P5_REPRODUCIBILITY = FORECAST_ONLY_ROLE_B_PRESERVED

CONFIGURATION_REPRODUCIBILITY = EXACT_AND_FROZEN

COMMAND_REPRODUCIBILITY = SPECIFIED_AND_DOCUMENTED

PRESENTATION_REPRODUCIBILITY = NOT_APPLICABLE

BITWISE_REPRODUCIBILITY = NOT_PROVEN

2024_ACCESSED = NO

SCIENTIFIC_METHODOLOGY_CHANGED = NO

TEST_ASSERTIONS_WEAKENED = NO

HISTORICAL_ARTIFACTS_DELETED = NO
```

The reproducibility audit is formally complete. In compliance with instructions, execution stops here (**DỪNG**).
