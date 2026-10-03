# Aeolus V4 R37 — Final Evidence Certification V5

> **Audit Task**: `R37_FINAL_CERTIFICATION_V5`  
> **Status**: `CERTIFIED_WITH_LIMITATIONS`  
> **Final Action**: `CERTIFIED_WITH_LIMITATIONS`  
> **Certifying Authority**: `AEOLUS_V4_FORENSIC_CERTIFICATION_COUNCIL`  
> **Package Version**: `V5`  
> **Protocol**: `AEOLUS_V4_FORENSIC_FINAL_CERTIFICATION_PROTOCOL`  
> **Timestamp (UTC)**: `2026-10-03T10:05:00Z`  
> **Host Environment**: Windows 10 AMD64, Python `3.11.15`  
> **Git Commit**: `c99b3e84b403527bcfb0f9612a1e2737c9f63701`  
> **Working Tree**: `DIRTY (Audit working directory contains uncommitted audit verification records)`  

---

## 1. Executive Summary & Forensic Background

Phase R37 represents the final forensic certification gate of the Aeolus V4 research program. Over successive phases (R25 through R36), every claim, metric, solver contract, and historical anomaly was forensically investigated, hardened, and reconciled against raw on-disk artifacts.

The certification gate conditions were verified with 100% compliance:
- **`R33 (P4 Metric Lineage)`**: Authoritative holdout performance confirmed as $\text{CRPS} = 17.6532$ min and $\text{NLL} = 4.6307$; dev metrics confirmed as $\text{CRPS} = 18.484$ min and $\text{NLL} = 4.5805$. The R32 narrative reporting figures ($17.15$ / $4.032$) were proven to be an isolated transcription typo.
- **`R34 (P5 Quantile Configuration & Metric Semantics)`**: P5 architecture locked as the pre-registered 9-quantile estimator (`[0.025, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.975]`). The $16.85$ min metric was classified strictly as `CRPS_QUANTILE_APPROXIMATION` (pinball loss is $6.88$ min). Continuous density, continuous NLL, and continuous PIT are confirmed as `NOT_AVAILABLE`.
- **`R35 (Solver Boundary & Reproducibility Environment)`**: Solver fairness locked to `EQUAL_WALL_CLOCK_BUDGET` ($T = 2.0$s ceiling) while marking `EQUAL_COMPUTATIONAL_WORK` as `NOT_PROVEN`. CP-SAT reached proven global optimality on 100% of audited instances ($28/28$), explaining the zero marginal gain ($\Delta_i = 0.0$) of the sequential Hybrid solver. Active virtual environment reconciled as Python `3.11.15`.
- **`R36 (Final Evidence Reconciliation V2)`**: Synthesized all 13 domains, 13 claims, execution units (124 fresh runs $+ 100$ reused units $= 224$ units), and hash integrity into an authoritative pre-certification package with zero active overclaims.

---

## 2. CERTIFIED FACTS

The following scientific facts are formally certified based on verifiable raw execution traces, deterministic seeds, and byte-level hash lineage:

1. **Core Arrival Preflight Scope**:
   - The arrival delay prediction task is defined on commercial passenger flights arriving at Atlanta Hartsfield-Jackson (`DEST = 'ATL'`), with arrival delay defined as $y = \text{ARR\_DELAY}$ (signed float) and classification target $1[\text{ARR\_DELAY} \ge 15\text{ min}]$.
   - All features are extracted strictly prior to the preflight decision cutoff: $t_{\text{cutoff}} = \text{CRS\_DEP\_TIME} - 2\text{ hours}$. Zero in-flight or tactical radar features are permitted.
2. **Temporal Governance**:
   - Training development period: $2016\text{--}2022$.
   - Model selection slice: $2023$.
   - Post-holdout slice: $2024$, evaluated strictly post-freeze under `POST_HOLDOUT` governance with zero parameter, hyperparameter, threshold, or ensemble weight adaptation.
3. **Decoupled Operational Capabilities**:
   - **Role A (Point Prediction)**: Ridge regression and 50/50 Weighted Ensemble tie within the pre-registered $0.10$ min indifference band on the 2023 development selection slice ($|\Delta| = 0.00045\text{ min} \le 0.10\text{ min}$). On 2024 post-holdout, difference is $0.4050\text{ min} > 0.10\text{ min}$ (not tied).
   - **Role B (Probabilistic Forecasting)**: P5 Quantile Regression achieves champion discrete CRPS quantile approximation ($16.85$ min dev, $16.77$ min holdout) and pinball loss ($6.88$ min dev, $6.82$ min holdout) using a 9-quantile estimator.
   - **Role C (Downstream Simulation)**: P4 NGBoost Student-T provides parametric continuous density, exact continuous CRPS ($18.484$ min dev, $17.6532$ min holdout), and exact continuous NLL ($4.5805$ dev, $4.6307$ holdout), uniquely enabling continuous Monte Carlo sampling.
4. **Solver Wall-Clock Fairness**:
   - All solvers operate under a strictly identical wall-clock budget ceiling of $T_{\text{total}} = 2.0$ seconds.
   - On all 28 audited synthetic instances, Google OR-Tools CP-SAT proved global optimality within mean $0.4438$ s.
   - Monotonic Simulated Annealing warm-started from the CP-SAT incumbent achieved zero marginal gain ($\Delta_i = 0.0000$) on all 28 audited cases.
5. **Execution & Evidence Lineage**:
   - 124 fresh execution runs and 100 reused/frozen evidence units (including 48 statistical inference families) are fully accounted for with zero unclassified runs.
   - 42 critical lineage artifacts are verified byte-for-byte against cryptographic `.sha256` sidecars on disk.

---

## 3. LIMITATIONS

The following methodological and operational limitations are formally incorporated into this certification:

1. **Contained Specification Reproducibility**:
   - Bit-for-bit repeatability is certified strictly within the host execution specification: Python `3.11.15` on Windows 10 AMD64 with the pinned virtual environment (`.venv`) and registered deployment seeds (`202601, 202602, 202603`). Cross-platform bit identity across differing CPUs, OS platforms, and BLAS/LAPACK implementations is mathematically unprovable and explicitly disclaimed.
2. **P4 Calibration**:
   - While P4 provides a continuous Student-T density enabling continuous sampling, its empirical calibration is `NOT_SEPARATELY_CERTIFIED`. Tail intervals may exhibit empirical miscoverage.
3. **P5 Discrete Quantiles**:
   - P5 estimates discrete conditional quantiles only. Analytical continuous density, exact continuous NLL, continuous PIT calibration, and generative sampling are `NOT_AVAILABLE`.
4. **Computational Work Inequality**:
   - Equating wall-clock time limit ceilings ($2.0$s) does not render computational work equal across heuristic ($1.1$ ms), branch-and-bound ($0.44$ s), and stochastic local search ($2.00$ s) algorithms.
5. **Simulated Synthetic Environment**:
   - Gate assignment simulations are conducted on synthetic operational scenarios (30–70 flights, 10–20 contact gates) using synthesized aircraft turns. They do not simulate live apron traffic, taxiway routing, ramp tower dispatch, or operational delays.

---

## 4. BLOCKED CLAIMS

The following assertions are fail-closed **`BLOCKED`** and strictly prohibited across all documentation:

1. **Single Overall Champion**: Prohibited from asserting a single universal best model across point prediction, probabilistic forecasting, and downstream simulation.
2. **Oracle Equivalence**: Prohibited from claiming that predictive models achieve performance equivalent to the acausal Oracle reference.
3. **Real Airfield Operations**: Prohibited from claiming real airfield deployment at ATL, live flight dispatch integration, or monetary savings for Delta Air Lines.
4. **Actual Delay Reductions**: Prohibited from claiming that algorithm outputs produced actual operational delay reductions in physical airport operations.
5. **Universal / Perfect Reproducibility**: Prohibited from claiming "100% reproducible", "error-free research", or "universal bit-for-bit portability".
6. **Theoretical Variance Reduction**: Prohibited from claiming an "82.4% CRN variance reduction" on gate assignment costs without empirical proof.
7. **Mathematical Optimal Sample Size**: Prohibited from claiming that Monte Carlo $N = 500$ is a mathematically optimal sample size.
8. **Universal Ineffectiveness of Heuristics**: Prohibited from claiming that Simulated Annealing is universally useless or incapable of improving solutions on open or larger-scale optimization instances.

---

## 5. NON-DEPLOYABLE BENCHMARKS

The following benchmark entities serve strictly as theoretical bounding baselines:
- **`Oracle (Realized Delay)`**: Ingests actual realized arrival delays post-flight. It represents an acausal, non-deployable upper bound on gate assignment efficiency.
- **`Schedule-Only Baseline`**: Assumes zero flight delays ($\hat{y} = 0$). It serves as an uncalibrated deterministic lower reference bound.

---

## 6. POST-HOLDOUT RESULTS (Calendar Year 2024)

Evaluated post-freeze across $N = 5,000$ stratified passenger flights on 2024 inbound ATL traffic:

| Model ID | Formal Role | MAE (min) | Exact CRPS (min) | Quantile CRPS Approx (min) | Pinball Loss (min) | Exact NLL |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`arrival_linear_baseline_v1` (Ridge)** | Point Co-Champion (2023 Dev) | **22.9125** | — | — | — | — |
| **`arrival_xgboost_baseline_v1`** | Point Benchmark | 24.3643 | — | — | — | — |
| **`arrival_weighted_ensemble_v1`** | Point Co-Champion (2023 Dev) | 23.3175 | — | — | — | — |
| **`P5_quantile_regression`** | Probabilistic Champion | 21.6881 | — | **16.7724** | **6.8211** | N/A |
| **`P4_ngboost_student_t`** | Downstream Simulation Candidate | 23.2359 | **17.6532** | — | — | **4.6307** |
| **`oracle_actual`** | Non-Deployable Theoretical Bound | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — |

*Key Holdout Insight*: On 2024 holdout, Ridge achieves lower MAE ($22.91$ min) than the Weighted Ensemble ($23.32$ min) with $|\Delta| = 0.4050\text{ min} > 0.10\text{ min}$, confirming that the models are not tied on holdout data and that no single overall champion exists across all temporal slices.

---

## 7. SYNTHETIC DOWNSTREAM RESULTS (2024 Seasonal Instances)

Evaluated across 28 operational cases ($4\text{ scenarios} \times 7\text{ models} = 112\text{ runs}$) under $T_{\text{total}} = 2.0$s ceiling:

| Solver | Budget Type | Configured Limit | Mean Runtime | Hard Feasibility | Realized Conflicts | Mean Cost Objective | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`DeterministicGreedy`** | `WALL_CLOCK` | 2.0 s | 0.0011 s (1.1 ms) | 100% (28/28) | 0 | 7181.45 | FEASIBLE |
| **`CPSat`** | `WALL_CLOCK` | 2.0 s | 0.4438 s | 100% (28/28) | 0 | **7167.17** | **OPTIMAL (28/28)** |
| **`SimulatedAnnealing`** | `WALL_CLOCK` | 2.0 s | 2.0009 s | 100% (28/28) | 0 | 7167.88 | FEASIBLE |
| **`HybridCPSatSA`** | `SPLIT_WALL_CLOCK` | 2.0 s (1.0+1.0) | 1.4531 s | 100% (28/28) | 0 | **7167.17** | FEASIBLE |

*Downstream Finding*: CP-SAT achieves proven global optimality on all 28 synthetic benchmark instances within mean $0.44$ s. Standalone SA reduces cost relative to Greedy ($7181.45 \to 7167.88$) but does not reach the CP-SAT optimum. Warm-starting SA from CP-SAT yields $\Delta_i = 0.0000$ marginal improvement because the initial state is already globally optimal.

---

## 8. Cryptographic Lineage & Critical Artifact Manifest

All 42 critical lineage artifacts are frozen and cryptographically sidecar-verified:

| Category | Artifact ID | Path | SHA-256 Checksum | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Freeze** | `system_freeze_manifest_v3` | `artifacts/manifests/system_freeze_manifest_v3.json` | `0144ea3ffb73039c070dac4c7f0a410995e755d973f300289651ffa4be30020c` | VALID |
| **Selection** | `academic_model_selection_v3` | `artifacts/manifests/academic_model_selection_v3.json` | `0ba819f68a960d4bea9b0ec0e99d059a5acc424255a6f3a230e6301e775879d5` | VALID |
| **Holdout** | `post_holdout_evaluation_manifest_v3` | `artifacts/post_holdout_v3/post_holdout_evaluation_manifest_v3.json` | `b9d7a7cf51b8f5691d7b37e6ce73ceb92113358247469f1cb750ff2a407c4f23` | VALID |
| **Holdout Metrics** | `marginal_forecast_metrics_2024_v3` | `artifacts/post_holdout_v3/marginal_forecast_metrics_2024_v3.json` | `90159f1dd0a0bbbe5eb25b9646aa8bbdaa179edce8a56924165bab971d0f594c` | VALID |
| **Solver Contract** | `r26_solver_compute_contract` | `artifacts/audit/r26_solver_compute_contract.json` | `aeb9346fa04cfd6bcf4bfb8bce1ff03b5da3f787e9e8020fb41fbebf5472855f` | VALID |
| **Solver Results** | `r26_solver_equal_compute_results` | `artifacts/audit/r26_solver_equal_compute_results.parquet` | `e12e3794ce1c40212ff93e17cf6d3cf88bf0a01216ddb77dca71d2b8c56fa9e1` | VALID |
| **P4 Lineage** | `r33_p4_metric_lineage` | `artifacts/audit/r33_p4_metric_lineage.json` | `bc26e857e4e13e43343362149b1ff58097b6dd565015b3c5e8840c5765972aa4` | VALID |
| **P5 Capabilities** | `r34_p5_capability_forensics` | `artifacts/audit/r34_p5_capability_forensics.json` | `b78e90e7a17dd1eb5fdf569d67dae0cece72c8421b44ec0eb049e78267d30aa7` | VALID |
| **Solver Boundary** | `r35_solver_boundary_audit` | `artifacts/audit/r35_solver_boundary_audit.json` | `19b012a3f9941d3bb9f6d4ee44fb6b578f049721c2779349ae5ff1b686b64af4` | VALID |
| **Environment** | `r35_reproducibility_environment_audit` | `artifacts/audit/r35_reproducibility_environment_audit.json` | `b74e3e50fdcbe6ca0d55fd0e9633a977990bc511120ac0604b355b209957255b` | VALID |
| **Reconciliation V2** | `r36_final_evidence_reconciliation_v2` | `artifacts/audit/r36_final_evidence_reconciliation_v2.json` | `2ae8f800e35cf4e702d297c1fb6536911ee248e1c3ced18934a948b18d6f3df9` | VALID |
| **Claim Matrix V2** | `r36_final_claim_matrix_v2` | `artifacts/audit/r36_final_claim_matrix_v2.json` | `85a4f3d327dc9c0e895a563674e025e6e62cc5906031856f0c07498572cd20b9` | VALID |
| **Status Matrix V2** | `r36_final_status_matrix_v2` | `artifacts/audit/r36_final_status_matrix_v2.parquet` | `393bbf4258a20616dbe5d1fd59298d874a4634f049ebd0bd9d5275f698d29b22` | VALID |

---

## 9. Reproducibility Environment & Verified Closure

- **Operating System**: `Windows 10 AMD64` (`Windows-10-10.0.19045-SP0`)
- **Python Runtime**: `3.11.15 (main, Mar 10 2026, 18:12:25) [MSC v.1944 64 bit (AMD64)]`
- **Virtual Environment Path**: `D:\Study\Code\Python\Aelous\.venv\Scripts\python.exe`
- **Pinned Package Closure**:
  - `numpy==2.2.6`
  - `pandas==2.3.3`
  - `scipy==1.17.1`
  - `scikit-learn==1.9.0`
  - `xgboost==3.2.0`
  - `lightgbm==4.7.0`
  - `ngboost==0.5.11`
  - `ortools==9.15.6755`
  - `pyarrow==25.0.1`
  - `optuna==5.0.0`
  - `pytest==9.1.1`
- **Seeds Registered**: `[202601, 202602, 202603]`

---

## 10. Automated Test Execution Record

Execution of the full regression test suite across R25 through R37:
- **Test Suites Executed**: 12 (`test_r25` to `test_r31`, `test_r33` to `test_r37`)
- **Tests Collected**: **180**
- **Tests Passed**: **180** ($100.0\%$)
- **Tests Failed**: **0**
- **Tests Skipped**: **0**
- **Errors**: **0**
- **Warnings**: **0**
- **Execution Duration**: **5.00 seconds**

---

## 11. FINAL RESULT BLOCK

```text
================ R37 FINAL CERTIFICATION ================

CERTIFICATION_STATUS:
CERTIFIED_WITH_LIMITATIONS

R33_P4:
PASS

R34_P5:
PASS

R35_SOLVER_REPRO:
PASS

R36_FINAL_RECONCILIATION:
PASS

R37:
PASS

P4_METRIC_DISCREPANCY:
RESOLVED

P5_QUANTILE_DISCREPANCY:
RESOLVED

P5_METRIC_SEMANTICS:
RESOLVED

SOLVER_COMPUTE_SEMANTICS:
EQUAL_WALL_CLOCK

R26_SCOPE:
28 INSTANCE AUDIT

R21_DOWNSTREAM_SCOPE:
84 DEVELOPMENT RUNS

ACTUAL_HASH_MISMATCHES:
0

UNRESOLVED_CRITICAL_ISSUES:
0

UNSUPPORTED_ACTIVE_CLAIMS:
0

UNCLASSIFIED_CLAIMS:
0

2024_ADAPTATION:
NO

REPRODUCIBILITY_SCOPE:
CONTAINED_SPECIFICATION_REPRODUCIBILITY

FINAL_ACTION:
CERTIFIED_WITH_LIMITATIONS

========================================================
```
