# FORENSIC AUDIT REPORT: R38 NATIVE DOWNSTREAM PREFLIGHT
**Project**: Aeolus Probabilistic Core Arrival & Gate Optimization  
**Repository**: `D:\Study\Code\Python\Aelous`  
**Branch**: `v4-final-forensic-certification`  
**Commit HEAD**: `7ba0aba92d366f712977faaaa5a73cba65a32a55`  
**Date**: 2026-10-04  
**Audit Type**: Read-Only Downstream Rebuild Pre-Flight (Category E)  
**Status**: `R38_PREFLIGHT = BLOCKED`

---

## 1. EXECUTIVE SUMMARY & FORENSIC VERDICT

Following the closure of `P10-R2`, which established that historical downstream Monte Carlo simulations suffered from a **`METHODOLOGY_DEVIATION`** (using Ridge + fixed Student-t for P4 and XGBoost + piecewise Gaussian transformation for P5), this pre-flight pass investigated the technical and data lineage feasibility of executing the approved **`CATEGORY_E`** rebuild (connecting native frozen P4 and native P5 median directly into the synthetic turn, gate simulation, solver benchmarks, and robustness evaluation).

### Critical Forensic Findings:
1. **P4 Checkpoint Availability**: Certified native P4 checkpoint [`artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib`](file:///D:/Study/Code/Python/Aelous/artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib) (SHA-256: `e7e7462f17b65b276ebdee9c7beced15e090f69b088a18896d5a91aaa8cb062f`) is fully intact, loads cleanly as `B5NGBoostStudentT`, and natively outputs observation-dependent parameters $\mu(x)$, $\sigma(x)$, and $\nu(x)$.
2. **P5 Serialized Model Checkpoint Missing**: P5 (`B4LightGBMQuantile` / `P5_quantile_regression`) has **NO serialized model weights file** anywhere in the repository. Historically, Stage 1 trained 9 LightGBM pinball models per fold in-memory and exported only the validation predictions to parquet without persisting booster objects to disk.
3. **Scenario Population vs Prediction Mismatch**:
   - The approved downstream scenario population (`SCEN_2023_LOW`, `SCEN_2023_MEDIUM`, etc.) is drawn exclusively from operational year **2023** (e.g., date `2023-11-23` for `SCEN_2023_LOW`).
   - The pre-existing native prediction parquet files for both P4 and P5 ([`predictions_fold_1.parquet`](file:///D:/Study/Code/Python/Aelous/artifacts/probabilistic/lightgbm_quantile/predictions_fold_1.parquet) through `predictions_fold_4.parquet`) cover strictly years **2019 to 2022** (Folds 1–4).
   - Direct deterministic join between `SCEN_2023_LOW` (30 flights) and existing P4/P5 prediction artifacts yields **0 / 30 matching flight keys (100% missing)**.
4. **Retraining & Pre-Flight Block**:
   - While frozen P4 can generate out-of-sample predictions on 2023 scenario features without retraining via its frozen checkpoint, P5 cannot generate predictions on 2023 flights without being refitted/retrained from scratch on 2016–2022 development data.
   - Retraining forecasting models is strictly prohibited by current protocol governance (*"Forecasting models themselves MUST NOT be retrained"*), creating a direct architectural deadlock for P5 on 2023 scenarios.
   - Under the strict acceptance criteria of Task 4, Task 11, and the pre-flight protocol, this pass concludes:
     ```text
     R38_PREFLIGHT = BLOCKED
     ```

---

## 2. TASK 1 — NATIVE P4 ARTIFACT AVAILABILITY

We inspected the metadata, filesystem hashes, and serialization structures of all native P4 artifacts.

### 2.1 Model Checkpoint Inspection
- **Path**: [`artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib`](file:///D:/Study/Code/Python/Aelous/artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib)
- **SHA-256**: `e7e7462f17b65b276ebdee9c7beced15e090f69b088a18896d5a91aaa8cb062f`
- **File Size**: 243,595 bytes
- **Model Object Class**: `src.models.probabilistic.baselines.B5NGBoostStudentT`
- **Underlying Engine**: `ngboost.NGBRegressor` with `Dist=ngboost.distns.t`
- **Base Estimator**: `DecisionTreeRegressor(criterion='friedman_mse', max_depth=3, splitter='best')`
- **Training Period**: 2016–2022 outer development window (7 years stratified subsample)
- **Hyperparameters**: `n_estimators=50`, `learning_rate=0.005`, `seed=202601`
- **Parameter Output Heads**:
  - Location head: $\mu(x)$
  - Scale head: $\sigma(x) \ge 1.0$ (enforces `DEFAULT_SIGMA_FLOOR = 1.0`)
  - Degrees of freedom head: $\nu(x) \ge 2.1$ (enforces finite variance $\nu > 2$)
- **Status**: `VALID_AND_PERMANENTLY_FROZEN`

### 2.2 Native P4 Prediction Artifacts
All fold predictions in [`artifacts/probabilistic/ngboost_student_t/`](file:///D:/Study/Code/Python/Aelous/artifacts/probabilistic/ngboost_student_t/) contain 19 columns:
`['flight_key', 'flight_date', 'y_true', 'mu', 'sigma', 'df', 'nll', 'p_ge_15', 'p_ge_60', 'p_ge_120', 'q_025', 'q_050', 'q_100', 'q_250', 'q_500', 'q_750', 'q_900', 'q_950', 'q_975']`.

### 2.3 `NATIVE_P4_ARTIFACT_MAP`

| Artifact ID | Artifact Type | File Path | SHA-256 Checksum | Prediction Period | Rows | Key Columns |
|---|---|---|---|---|---|---|
| `P4_CKPT_V1` | Frozen Model Weights | `artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib` | `e7e7462f17b65b276ebdee9c7beced15e090f69b088a18896d5a91aaa8cb062f` | N/A (Trained 2016–2022) | N/A | N/A |
| `P4_PRED_FOLD1` | OOF Prediction Parquet | `artifacts/probabilistic/ngboost_student_t/predictions_fold_1.parquet` | `404b90a4cfa5be2095bf859339f29c50074c7c7599976fbf9a65c14f46f041b0` | 2019-01-01 to 2019-12-31 | 5,000 | `flight_key`, `mu`, `sigma`, `df` |
| `P4_PRED_FOLD2` | OOF Prediction Parquet | `artifacts/probabilistic/ngboost_student_t/predictions_fold_2.parquet` | `615f812378500c6499ce376e70e61760c0731e45bb843169e2d3d100d2ce6342` | 2020-01-01 to 2020-12-31 | 5,000 | `flight_key`, `mu`, `sigma`, `df` |
| `P4_PRED_FOLD3` | OOF Prediction Parquet | `artifacts/probabilistic/ngboost_student_t/predictions_fold_3.parquet` | `1c5e0334bfd5f22cc31b18ba51d1414f3bb516e6d3c44cc13cd8ba9b23d49760` | 2021-01-01 to 2021-12-31 | 5,000 | `flight_key`, `mu`, `sigma`, `df` |
| `P4_PRED_FOLD4` | OOF Prediction Parquet | `artifacts/probabilistic/ngboost_student_t/predictions_fold_4.parquet` | `d5126e978469c079eb126be454cd4b7a5609b6418d300928b6fcec0daba4acac` | 2022-01-01 to 2022-12-31 | 5,000 | `flight_key`, `mu`, `sigma`, `df` |
| `P4_HOLDOUT_2024` | Post-Holdout Prediction Parquet | `artifacts/evaluation/final_holdout_2024/holdout_predictions_2024.parquet` | `4c8d328325a774fcf33bb55278d1e3895e634ae9260c7f8a846c4f932822a550` | 2024-01-01 to 2024-12-31 | 5,000 | `flight_key`, `pred_mu`, `pred_sigma`, `pred_df` |

---

## 3. TASK 2 — NATIVE P5 ARTIFACT AVAILABILITY

We inspected the metadata, filesystem hashes, and schema of all native P5 (`B4LightGBMQuantile` / `P5_quantile_regression`) artifacts.

### 3.1 Quantile Schema & Levels
In [`artifacts/probabilistic/lightgbm_quantile/`](file:///D:/Study/Code/Python/Aelous/artifacts/probabilistic/lightgbm_quantile/), all fold prediction parquet files contain 12 columns:
`['flight_key', 'flight_date', 'y_true', 'q_025', 'q_050', 'q_100', 'q_250', 'q_500', 'q_750', 'q_900', 'q_950', 'q_975']`.

- **Quantile Count**: Exactly 9 quantiles.
- **Quantile Levels**: $\alpha \in \{0.025, 0.050, 0.100, 0.250, 0.500, 0.750, 0.900, 0.950, 0.975\}$.
- **Availability of Median $\hat{q}_{0.50}$**: **CONFIRMED**. Column `q_500` contains the native pinball median forecast.
- **Model Checkpoint Availability**: **NONE**. An exhaustive filesystem search confirmed that zero `.joblib`, `.model`, `.txt`, `.booster`, or `.bin` files exist for P5. Stage 1 trained P5 in-memory and discarded the models after exporting parquet predictions.

### 3.2 `NATIVE_P5_ARTIFACT_MAP`

| Artifact ID | Artifact Type | File Path | SHA-256 Checksum | Prediction Period | Rows | Median Column |
|---|---|---|---|---|---|---|
| `P5_CKPT_V1` | Model Checkpoint | **DOES NOT EXIST ON DISK** | N/A | N/A | 0 | N/A |
| `P5_PRED_FOLD1` | OOF Quantiles Parquet | `artifacts/probabilistic/lightgbm_quantile/predictions_fold_1.parquet` | `302aabd051dedf306689a920ba0c29eb03b426520f9ec3282e65118314f8f791` | 2019-01-01 to 2019-12-31 | 5,000 | `q_500` |
| `P5_PRED_FOLD2` | OOF Quantiles Parquet | `artifacts/probabilistic/lightgbm_quantile/predictions_fold_2.parquet` | `4a8f72c6f21d6870e986b9c72ce1c79f937c223ee2f1172f1fbbd1f59f9dd5ae` | 2020-01-01 to 2020-12-31 | 5,000 | `q_500` |
| `P5_PRED_FOLD3` | OOF Quantiles Parquet | `artifacts/probabilistic/lightgbm_quantile/predictions_fold_3.parquet` | `39d0081e31494035613522d5b91ec24e0b325cb1087d122675c9e595d843fff3` | 2021-01-01 to 2021-12-31 | 5,000 | `q_500` |
| `P5_PRED_FOLD4` | OOF Quantiles Parquet | `artifacts/probabilistic/lightgbm_quantile/predictions_fold_4.parquet` | `4192dcc73a3a5cc4a6e7ca3bf96c7e5ee0a2459072f71a04301cd21419d94a62` | 2022-01-01 to 2022-12-31 | 5,000 | `q_500` |
| `P5_HOLDOUT_2024` | Post-Holdout Prediction Parquet | **DOES NOT EXIST** (P5 not evaluated on 2024) | N/A | N/A | 0 | N/A |

---

## 4. TASK 3 — SCENARIO POPULATION IDENTITY

We audited all candidate scenario sets documented in [`artifacts/manifests/downstream_protocol_v2.json`](file:///D:/Study/Code/Python/Aelous/artifacts/manifests/downstream_protocol_v2.json), [`artifacts/manifests/downstream_experiment_matrix_v2.json`](file:///D:/Study/Code/Python/Aelous/artifacts/manifests/downstream_experiment_matrix_v2.json), and [`src/evaluation/downstream_comparison.py`](file:///D:/Study/Code/Python/Aelous/src/evaluation/downstream_comparison.py).

### Candidate Scenario Population Inventory:

| Candidate Scenario ID | Operational Date | Year | Flight Count ($K$) | Contact Gates | Seed | Population Temporal Role | Governing Manifest |
|---|---|---|---|---|---|---|---|
| **`SCEN_2023_LOW`** | 2023-11-23 | 2023 | 30 | 10 | 202601 | `DEVELOPMENT_MODEL_SELECTION` | `downstream_protocol_v2.json`, `scenario_manifest.json` |
| **`SCEN_2023_MEDIUM`** | 2023-07-03 | 2023 | 50 | 15 | 202602 | `DEVELOPMENT_MODEL_SELECTION` | `downstream_protocol_v2.json`, `downstream_experiment_matrix_v2.json` |
| **`SCEN_2023_HIGH`** | 2023-07-13 | 2023 | 70 | 20 | 202603 | `DEVELOPMENT_MODEL_SELECTION` | `downstream_protocol_v2.json`, `downstream_experiment_matrix_v2.json` |
| **`SCEN_2023_DISRUPTED`** | 2023-08-07 | 2023 | 50 | 15 | 202604 | `DEVELOPMENT_MODEL_SELECTION` | `downstream_protocol_v2.json`, `downstream_experiment_matrix_v2.json` |
| **`STAGE_9_OPERATIONAL_DAYS`** | 25 days across 2023 | 2023 | 529 total | 30 | 202601 | `DEVELOPMENT_MODEL_SELECTION` | `probabilistic_stage9_gate_simulation_v1.json` |
| **`SCEN_2024_WINTER`** | 2024-01-15 | 2024 | 40 | 12 | 202601 | `FINAL_HOLDOUT` (Post-Holdout) | `r26_solver_equal_compute_results.parquet` |
| **`SCEN_2024_FALL_DISRUPTED`** | 2024-10-10 | 2024 | 60 | 18 | 202601 | `FINAL_HOLDOUT` (Post-Holdout) | `r26_solver_equal_compute_results.parquet` |

### Primary Rebuild Candidate Selection:
Per protocol precedence, **`SCEN_2023_LOW`** (date: `2023-11-23`, $K=30$, gates$=10$, seed$=202601$) is the canonical primary instance evaluated across historical Phase 8 and Phase 9 Monte Carlo convergence runs.

---

## 5. TASK 4 — KEY / JOIN COMPATIBILITY

We evaluated whether each flight in the candidate scenario population can be joined deterministically to existing prediction artifacts.

### 5.1 Join Analysis for Canonical Scenario `SCEN_2023_LOW`

```text
Scenario Population: SCEN_2023_LOW (Date: 2023-11-23, N = 30 flights)
Extracted flight_key sample:
  1. flight_key_v1_8227ad19b05885e4306f12121fbe009a
  2. flight_key_v1_fc2e62944dcb4dc3599f55714e367ce0
  3. flight_key_v1_a45ea5eca21f49531f072d43895b9724
  4. flight_key_v1_2bd298c71c8970891c00bd4417fbdccd
  5. flight_key_v1_1dd536a20a035bc10271e45db054487d
```

### 5.2 Deterministic Join Verification Table

| Scenario Key Source | Target Prediction Artifact | Prediction Key | 1:1 Join? | Missing Count | Duplicate Count | Temporal Validity | Evidence & Root Cause |
|---|---|---|---|---|---|---|---|
| `SCEN_2023_LOW` (30 flights) | `P4_PRED_FOLD1..4` (2019–2022) | `flight_key` | **NO** | **30 / 30 (100%)** | 0 | Incompatible years | Scenario is from 2023-11-23; fold predictions terminate at 2022-12-31. |
| `SCEN_2023_LOW` (30 flights) | `P5_PRED_FOLD1..4` (2019–2022) | `flight_key` | **NO** | **30 / 30 (100%)** | 0 | Incompatible years | Scenario is from 2023-11-23; fold predictions terminate at 2022-12-31. |
| `SCEN_2023_LOW` (30 flights) | `P4_HOLDOUT_2024` (2024) | `flight_key` | **NO** | **30 / 30 (100%)** | 0 | Incompatible years | Scenario is 2023; holdout is 2024. |
| `SCEN_2023_LOW` (30 flights) | `P4_CKPT_V1` (Frozen NGBoost) | Evaluated on `X_scen` | **YES** | **0 / 30 (0%)** | 0 | **VALID** | Frozen checkpoint can evaluate 2023 feature vector `X_scen` directly. |
| `SCEN_2023_LOW` (30 flights) | `P5_CKPT_V1` (LightGBM) | Evaluated on `X_scen` | **IMPOSSIBLE** | **30 / 30 (100%)** | 0 | **BLOCKED** | P5 checkpoint does not exist on disk; cannot evaluate `X_scen`. |

### Join Finding:
`SCENARIO_JOIN_STATUS = BLOCKED`.  
Because no pre-computed 2023 prediction artifact exists for P5, and no serialized model weights file exists to compute $\hat{q}_{0.50}(X_{\text{scen}})$ out-of-sample, P5 cannot be joined to the 2023 scenario population without violating the "no retraining" constraint.

---

## 6. TASK 5 — TEMPORAL VALIDITY

1. **Training Window Isolation**:
   - Both P4 and P5 models were designed to train strictly on the outer development window `[2016, 2017, 2018, 2019, 2020, 2021, 2022]`.
   - Frozen checkpoint `model_weights_frozen_v1.joblib` was verified to be trained exclusively on 2016–2022 subsamples.
2. **Point-in-Time Prediction Cutoff**:
   - The strict operational cutoff `CRS_DEP_TIME - 2 hours` is preserved. Features ingested by `TreePreprocessor` (`CRS_ELAPSED_TIME`, `calendar_*`, `OP_CARRIER`, `ORIGIN`, `OP_CARRIER_FL_NUM`) are available strictly before pushback.
   - All departure delay, downstream delay, and weather leakage features are blocked by `validate_downstream_input_boundary()`.
3. **2024 Temporal Boundary**:
   - Operational year 2024 remains completely isolated from development.
   - Zero 2024 data was used in model fitting, tuning, or feature preprocessing.

---

## 7. TASK 6 — P4 PARAMETER VALIDITY

We verified the mathematical integrity of P4 parameter representation:
1. **Observation-Dependent Heteroscedasticity**:
   - In [`artifacts/probabilistic/ngboost_student_t/predictions_fold_*.parquet`](file:///D:/Study/Code/Python/Aelous/artifacts/probabilistic/ngboost_student_t/predictions_fold_1.parquet), columns `mu`, `sigma`, and `df` vary per row, confirming true heteroscedastic output from `NGBoost`.
   - Inspection of `model_weights_frozen_v1.joblib` confirms that calling `predict_distribution(X)` invokes:
     $$\text{dist} = \text{model\_}.\text{pred\_dist}(X_{\text{trans}})$$
     $$\mu(x) = \text{dist.loc}, \quad \sigma(x) = \max(\text{dist.scale}, 1.0), \quad \nu(x) = \max(\text{dist.df}, 2.1)$$
2. **Sampling Representation**:
   - When generative scenarios are required for Monte Carlo robustness, the exact downstream mathematical representation must be:
     $$Y_i = \mu(x_i) + \sigma(x_i) \cdot T_{\nu(x_i)}$$
     where $T_{\nu} \sim \text{Student-t}(\nu)$.
   - Historical substitution of homoscedastic Ridge base delay and fixed $\sigma=16.5, \nu=4.0$ is completely eliminated.
3. **Status**: `NATIVE_P4_PARAMETER_STATUS = VERIFIED_HETEROSCEDASTIC`.

---

## 8. TASK 7 — P5 DOWNSTREAM VALIDITY

1. **Permitted Representation**:
   - In accordance with Protocol Decision [D027](file:///D:/Study/Code/Python/Aelous/docs/decisions/decision_registry.md#L41) and the `P10-R2` audit, P5 possesses strictly quantile capabilities.
   - It possesses no continuous CDF, no likelihood, and no native generative sampler.
   - Downstream integration is permitted solely as a **deterministic forecast-only median** ($\hat{q}_{0.50}$).
2. **Forbidden Operations**:
   - Fitting an asymmetric Laplace distribution: **FORBIDDEN**.
   - Inventing piecewise Gaussian scaling ($\sigma_L=19.8, \sigma_R=29.7$): **FORBIDDEN**.
   - Sampling stochastic realizations around P5: **FORBIDDEN**.
3. **Simulator Consumption Feasibility**:
   - In deterministic downstream evaluation ([`src/evaluation/downstream_comparison_v2.py:420`](file:///D:/Study/Code/Python/Aelous/src/evaluation/downstream_comparison_v2.py#L420)), `evaluate_candidate_on_scenario()` directly consumes scalar predicted delays `pred_delay = float(predicted_delays[i])` to construct planned turns. This is fully compatible with P5 median.
   - In Monte Carlo robustness ([`src/evaluation/mc_convergence.py:280-285`](file:///D:/Study/Code/Python/Aelous/src/evaluation/mc_convergence.py#L280-L285)), `DelayTransformationEngine.transform` supports `allow_p5_forecast_only=True`, which replicates the deterministic median across all $N$ scenarios (`np.tile(base, (n_scen, 1))`).
4. **Integration Block Finding**:
   - Despite mathematical compatibility, P5 integration into `SCEN_2023_LOW` is physically blocked because **neither pre-computed predictions nor a frozen model file exist for 2023 flights**.
   - `P5_INTEGRATION_BLOCKED = YES`.

---

## 9. TASK 8 — SYNTHETIC TURN COMPATIBILITY

We inspected [`src/simulation/aircraft_turn.py`](file:///D:/Study/Code/Python/Aelous/src/simulation/aircraft_turn.py) and [`src/evaluation/downstream_comparison_v2.py`](file:///D:/Study/Code/Python/Aelous/src/evaluation/downstream_comparison_v2.py):

### 9.1 Required Inputs for `AircraftTurnModel.synthesize_turn()`
- `flight_id`: Unique flight identifier string.
- `carrier`: Airline designator string.
- `flight_number`: Flight number string.
- `scheduled_arrival_min`: Scheduled gate arrival time in minutes from midnight (int).
- `arrival_delay_min`: Inflow arrival delay in minutes (float).
- `nominal_gate_id`: Published nominal gate assignment string.

### 9.2 Turn Synthesis Mathematical Logic
1. Planned Turn (Input to Solver):
   $$\text{arrival\_min}_{\text{planned}} = \text{scheduled\_arrival\_min} + \text{predicted\_delay}$$
   $$\text{turnaround\_min} = \max(\text{min\_turnaround\_minutes}, \text{default\_dwell\_minutes})$$
   $$\text{departure\_min}_{\text{planned}} = \text{arrival\_min}_{\text{planned}} + \text{turnaround\_min}$$
   $$\text{planned\_occupancy} = [\text{arrival\_min}_{\text{planned}}, \text{departure\_min}_{\text{planned}} + \text{buffer\_minutes}]$$
2. Realized Turn (Input to Evaluator):
   $$\text{arrival\_min}_{\text{realized}} = \text{scheduled\_arrival\_min} + \text{actual\_arrival\_delay}$$
   $$\text{departure\_min}_{\text{realized}} = \text{arrival\_min}_{\text{realized}} + \text{turnaround\_min}$$
   $$\text{realized\_occupancy} = [\text{arrival\_min}_{\text{realized}}, \text{departure\_min}_{\text{realized}} + \text{buffer\_minutes}]$$

### 9.3 Information Isolation Confirmation:
- Realized delay (`row["ARR_DELAY"]`) is strictly isolated to evaluation and is **NEVER** injected into planned turn synthesis.
- Native P4 ($\mu(x)$) and P5 ($\hat{q}_{0.50}$) provide scalar `predicted_delays`, which drop directly into `synthesize_turn()`.
- Status: `SYNTHETIC_TURN_COMPATIBILITY = FULLY_COMPATIBLE`.

---

## 10. TASK 9 — SOLVER COMPATIBILITY

We audited the interfaces of all 4 solvers:
1. **`DeterministicGreedyGateSolver`** ([`src/optimization/greedy.py`](file:///D:/Study/Code/Python/Aelous/src/optimization/greedy.py))
2. **`CPSatGateSolver`** ([`src/optimization/cpsat.py`](file:///D:/Study/Code/Python/Aelous/src/optimization/cpsat.py))
3. **`SimulatedAnnealingGateSolver`** ([`src/optimization/sa.py`](file:///D:/Study/Code/Python/Aelous/src/optimization/sa.py))
4. **`HybridCPSatSASolver`** ([`src/optimization/hybrid.py`](file:///D:/Study/Code/Python/Aelous/src/optimization/hybrid.py))

### Verification:
- All solvers consume standardized objects: `(turns: list[AircraftTurn], gates: list[Gate], config: GateOptimizationConfig)`.
- Solvers are completely agnostic to whether turns originated from Ridge proxies, native NGBoost, or P5 quantiles.
- All 4 solvers enforce identical hard constraints (no simultaneous gate occupancy, minimum buffer separation, aircraft gate compatibility).
- Objective function weights (reassignment $= 10$, remote $= 200$, unassigned $= 1000$) evaluate identically.
- Status: `SOLVER_REUSE_STATUS = FULLY_COMPATIBLE` (zero solver modifications required).

---

## 11. TASK 10 — 2024 HOLDOUT BOUNDARY

1. **Governance Classification**:
   - The 2024 holdout was unsealed during Phase 11 historical evaluations.
   - Under scientific integrity rules, 2024 is classified as **`POST_HOLDOUT`**.
2. **Labeling Requirement**:
   - Any future evaluation using 2024 data MUST NOT be labeled "unseen" or "untouched holdout".
   - The mandatory designation for future holdout benchmarks is:
     ```text
     POST_HOLDOUT RE-EVALUATION AFTER METHODOLOGY REPAIR
     ```
3. **Execution Guard**:
   - In strict compliance with pre-flight instructions, zero 2024 row-level evaluations were initiated.

---

## 12. TASK 11 — RETRAINING REQUIREMENT ANALYSIS

We evaluated whether existing frozen artifacts are sufficient to run Category E rebuild:

1. **Native P4 (NGBoost Student-T)**:
   - Checkpoint exists (`model_weights_frozen_v1.joblib`).
   - Retraining P4: **`NO`**. The frozen checkpoint can predict out-of-sample on any operational bank feature matrix.
2. **Native P5 (LightGBM Quantile)**:
   - Checkpoint: **DOES NOT EXIST ON DISK**.
   - Parquet predictions: Exist only for 2019–2022 development folds.
   - Retraining P5: **`YES`** (if 2023 scenarios are retained). Because P5 models were not serialized historically, predicting $\hat{q}_{0.50}$ on `SCEN_2023_LOW` requires fitting `B4LightGBMQuantile` on the 2016–2022 development window.
3. **Architectural Deadlock**:
   - Since the user directive explicitly specifies *"Forecasting models themselves MUST NOT be retrained"*, P5 cannot obtain predictions for `SCEN_2023_LOW`.
   - Therefore:
     ```text
     RETRAIN_REQUIRED = YES (for P5 under current 2023 scenario selection)
     ```

---

## 13. TASK 12 — REBUILD SPECIFICATION: `R38_NATIVE_DOWNSTREAM_REBUILD_SPEC`

When protocol governance authorizes either (a) a one-time outer-window fit of P5 LightGBM Quantile on 2016–2022 to materialize 2023 scenario predictions, or (b) an alternative scenario selection, the rebuild must execute according to this exact machine-readable specification:

```yaml
specification_id: R38_NATIVE_DOWNSTREAM_REBUILD_SPEC
version: 1.0.0
rebuild_scope: CATEGORY_E
target_directory: artifacts/native_downstream_v1/

scenario_population:
  scenario_id: SCEN_2023_LOW
  operational_date: "2023-11-23"
  n_flights: 30
  n_contact_gates: 10
  bank_start_hour: 12
  seed: 202601
  source_dataset: data/processed/inbound_atl/year=2023

model_regimes:
  P4_native:
    model_id: P4_ngboost_student_t
    checkpoint_file: artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib
    checkpoint_sha256: e7e7462f17b65b276ebdee9c7beced15e090f69b088a18896d5a91aaa8cb062f
    output_representation: heteroscedastic_student_t
    parameters_consumed: [mu, sigma, df]
    sampling_formula: "mu(x) + sigma(x) * StudentT(df=df(x))"
  
  P5_native:
    model_id: P5_quantile_regression
    evaluation_mode: FORECAST_ONLY_MEDIAN
    median_quantile_level: 0.50
    stochastic_sampling: PROHIBITED
    asymmetric_transformation: PROHIBITED
    mc_representation: "tile(q_0.50(x), N)"

simulation_configuration:
  turn_model:
    min_turnaround_minutes: 45.0
    default_dwell_minutes: 60.0
    separation_buffer_minutes: 15.0
  objective_function:
    reassignment_penalty: 10.0
    remote_penalty: 200.0
    unassigned_penalty: 1000.0
    delay_risk_penalty: 0.0

solver_benchmarks:
  solvers:
    - DeterministicGreedy
    - CPSat
    - SimulatedAnnealing
    - HybridCPSatSA
  wall_clock_budget_seconds: 2.0
  solver_seed: 202601

monte_carlo_robustness:
  counts_grid: [100, 250, 500, 1000, 2500]
  canonical_n: 500
  common_random_numbers: TRUE
  crn_source: "numpy.random.default_rng(202601).uniform(0.001, 0.999)"

artifact_boundaries:
  immutable_historical_artifacts:
    - artifacts/audit/r21_execution_trace.json
    - artifacts/audit/r26_solver_equal_compute_results.parquet
    - artifacts/downstream_model_comparison/
    - artifacts/monte_carlo_model_comparison_v2/
  new_output_namespace: artifacts/native_downstream_v1/
```

---

## 14. FINAL SUMMARY FIELDS (ACCEPTANCE CRITERIA)

```text
NATIVE_P4_ARTIFACT_STATUS = AVAILABLE_AND_VERIFIED
NATIVE_P4_PARAMETER_STATUS = VERIFIED_HETEROSCEDASTIC
NATIVE_P5_ARTIFACT_STATUS = PARTIALLY_AVAILABLE (folds 1-4 present, NO serialized model checkpoint)
NATIVE_P5_Q50_STATUS = VERIFIED_IN_FOLDS (q_500 present in folds 1-4, missing for 2023 scenarios)
SCENARIO_JOIN_STATUS = BLOCKED
P4_DOWNSTREAM_INPUT_STATUS = READY (frozen checkpoint can generate native mu, sigma, nu for 2023 scenario without retraining)
P5_DOWNSTREAM_INPUT_STATUS = BLOCKED (no 2023 predictions exist on disk; no serialized model checkpoint exists to predict on 2023)
SYNTHETIC_TURN_COMPATIBILITY = FULLY_COMPATIBLE
SOLVER_REUSE_STATUS = FULLY_COMPATIBLE
HOLDOUT_BOUNDARY = POST_HOLDOUT_SEALED
RETRAIN_REQUIRED = YES (P5 LightGBM Quantile requires outer-window fit on 2016-2022 to produce 2023 scenario predictions because no model weights were serialized historically)
REBUILD_SCOPE = CATEGORY_E
R38_PREFLIGHT = BLOCKED
```

---

## 15. HALT BOUNDARY

- In strict adherence to the Acceptance Criteria, because Condition 4 (deterministic and complete join) and Condition 8 (zero retraining required) cannot be satisfied simultaneously for P5 on 2023 scenarios, the pre-flight gate returns **`R38_PREFLIGHT = BLOCKED`**.
- Zero code modifications were made.
- Zero retraining was performed.
- Zero experiments were rerun.
- Execution halts immediately. Awaiting user review and governance determination.
