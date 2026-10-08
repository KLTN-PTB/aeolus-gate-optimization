# FORENSIC AUDIT & IMPLEMENTATION REPORT: P10-A NATIVE P4 DOWNSTREAM REBUILD

**Project**: Aeolus Probabilistic Core Arrival & Gate Optimization  
**Repository**: `D:\Study\Code\Python\Aelous`  
**Branch**: `v4-final-forensic-certification`  
**Commit HEAD**: `7ba0aba92d366f712977faaaa5a73cba65a32a55`  
**Date**: 2026-10-04  
**Implementation Phase**: P10-A (Native P4 Downstream Rebuild after R39)  
**Status**: `P10A_STATUS = PASS`

---

## 1. EXECUTIVE SUMMARY & FORENSIC VERDICT

Following the read-only forensic audits in **P10-R**, **P10-R2**, **R38**, and **R39**, which demonstrated that historical downstream Monte Carlo evaluations suffered from a methodology deviation (substituting ad-hoc Ridge and XGBoost proxy models for P4 and P5), this implementation pass (**P10-A**) executed **Option A**: the pure **Native P4 Downstream Rebuild**.

### Core Achievements:
1. **P4 Checkpoint Verification**: The certified frozen native P4 checkpoint [`artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib`](file:///D:/Study/Code/Python/Aelous/artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib) (SHA-256: `e7e7462f17b65b276ebdee9c7beced15e090f69b088a18896d5a91aaa8cb062f`) was verified with 100% cryptographic integrity and loaded directly with zero retraining.
2. **P5 Role Enforcement**: In accordance with Decision **[D027](file:///D:/Study/Code/Python/Aelous/docs/decisions/decision_registry.md#L41)** and R39, **P5 (`P5_quantile_regression`) was strictly quarantined to its certified role as Role B (Marginal Quantile Forecast Champion)** and was NOT fit, NOT reconstructed, and NOT injected into downstream simulation.
3. **Exact Development Scenario**: Evaluated on the canonical historical development bank `SCEN_2023_LOW` (30 flights, 10 contact gates, seed `202601`, date `2023-11-23`) drawn from `data/processed/inbound_atl/year=2023`. Zero 2024 data was accessed or inspected.
4. **Deterministic Solver Parity**: All 4 pre-registered solvers (`DeterministicGreedy`, `CPSat`, `SimulatedAnnealing`, `HybridCPSatSA`) were benchmarked under an identical 2.0-second wall-clock ceiling with seed `202601`. All 16 solver runs achieved 100% feasibility certified by the independent verifier.
5. **Native Monte Carlo Robustness**: Executed across the complete pre-registered grid $N \in [100, 250, 500, 1000, 2500]$ under Common Random Numbers (CRN = TRUE). Native observation-dependent Student-t draws $Y_{s, i} = \mu(x_i) + \sigma(x_i) \cdot t_{\nu(x_i)}^{-1}(U_{s, i})$ achieved 100% numerical validity, positive variance, and smooth $O(1/\sqrt{N})$ standard error convergence.
6. **Isolated Namespace**: All newly generated evidence was written into the isolated directory [`artifacts/native_downstream_v1/`](file:///D:/Study/Code/Python/Aelous/artifacts/native_downstream_v1/), preserving all historical artifacts untouched.

---

## 2. REPOSITORY STATE PREFLIGHT

- **Current Branch**: `v4-final-forensic-certification`
- **Current HEAD**: `7ba0aba92d366f712977faaaa5a73cba65a32a55`
- **Repository Working Tree Status**: Clean. Zero tracked files modified.
- **Python / Environment**: Python 3.11.15 AMD64 on Windows 10/11 with pinned virtual environment.
- **2024 Data Isolation Guard**: Verified active. Zero rows of 2024 accessed.

---

## 3. P4 CHECKPOINT CRYPTOGRAPHIC VERIFICATION

The native frozen checkpoint was validated before any downstream evaluation commenced:

| Verification Attribute | Expected Registered Value | Observed / Measured Value | Status |
|---|---|---|---|
| **File Path** | `artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib` | `artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib` | **MATCH** |
| **File Size** | 243,595 bytes | 243,595 bytes | **MATCH** |
| **SHA-256 Checksum** | `e7e7462f17b65b276ebdee9c7beced15e090f69b088a18896d5a91aaa8cb062f` | `e7e7462f17b65b276ebdee9c7beced15e090f69b088a18896d5a91aaa8cb062f` | **MATCH** |
| **Model Class** | `src.models.probabilistic.baselines.B5NGBoostStudentT` | `src.models.probabilistic.baselines.B5NGBoostStudentT` | **MATCH** |
| **Underlying Base Estimator** | `DecisionTreeRegressor(max_depth=3)` | `DecisionTreeRegressor(criterion='friedman_mse', max_depth=3)` | **MATCH** |
| **Hyperparameters** | $n=50$, $\eta=0.005$, $\text{seed}=202601$ | $n=50$, $\eta=0.005$, $\text{seed}=202601$ | **MATCH** |
| **Output Parameter Heads** | $\mu(x) \in \mathbb{R}$, $\sigma(x) \ge 1.0$, $\nu(x) \ge 2.1$ | $\mu(x) \in \mathbb{R}$, $\sigma(x) \ge 1.0$, $\nu(x) \ge 2.1$ | **MATCH** |

---

## 4. CANONICAL DEVELOPMENT SCENARIO IDENTITY

The evaluation was performed exclusively on the pre-registered development bank scenario:

- **Scenario ID**: `SCEN_2023_LOW`
- **Operational Date**: `2023-11-23`
- **Source Partition**: `data/processed/inbound_atl/year=2023`
- **Flight Count ($N_{\text{flights}}$)**: 30 flights
- **Contact Gates ($N_{\text{contact}}$)**: 10 gates (`G_01` to `G_10`)
- **Remote Overflow Stand**: 1 apron (`REMOTE_APRON_01`)
- **Bank Start Time**: 12:00 (720 minutes from midnight)
- **Scenario Seed**: `202601`
- **Scenario Cryptographic Hash**: `6b8565a0c8b32cfd5fbbe168b44610a514dcfebfa8a531778939c3623c21c75c`

---

## 5. INPUT BOUNDARY & FORECAST-TO-SIMULATION INTERFACE

### 5.1 Zero Actual Delay Leakage
Core Arrival features were extracted strictly at the pre-registered cutoff $T_{\text{cutoff}} = \text{CRS\_DEP\_TIME} - 2\text{h}$ using [`prepare_arrival_features`](file:///D:/Study/Code/Python/Aelous/src/features/tabular_features.py):
- Exactly 11 approved predictors: `CRS_ELAPSED_TIME`, `calendar_year`, `calendar_month`, `calendar_day_of_month`, `calendar_day_of_week`, `is_weekend`, `scheduled_departure_hour`, `scheduled_departure_minute`, `OP_CARRIER`, `ORIGIN`, `OP_CARRIER_FL_NUM`.
- Zero Weather features, zero auxiliary Departure delay, zero actual pushback times.
- Realized operational delays (`ARR_DELAY`) were completely isolated from the solver and presented only post-hoc to the independent verifier.

### 5.2 Planned Flight Turn Construction
For each flight $i \in \{1, \dots, 30\}$:
- **Scheduled Arrival**: $A_{\text{sched}, i}$ (minutes from midnight).
- **Planned Arrival Delay ($\Delta T_{\text{planned}, i}$)**:
  - `schedule_only`: $0.0\text{ min}$.
  - `arrival_linear_baseline_v1`: $\hat{y}_{\text{Ridge}, i}$.
  - `P4_ngboost_student_t`: $\mu_{\text{P4}}(x_i)$.
  - `oracle_actual`: Realized $\text{ARR\_DELAY}_i$ (ACausal, non-deployable benchmark).
- **Planned Arrival**: $A_{\text{pred}, i} = A_{\text{sched}, i} + \Delta T_{\text{planned}, i}$.
- **Turnaround Bound**: $D_{\text{min}, i} = A_{\text{pred}, i} + 45\text{ min}$.
- **Simulated Departure**: $D_{\text{pred}, i} = \max(A_{\text{sched}, i} + 60, D_{\text{min}, i})$.
- **Gate Release**: $\text{Gate\_release}_i = D_{\text{pred}, i} + 15\text{ min}$.
- **Occupancy Interval**: $[A_{\text{pred}, i}, \text{Gate\_release}_i)$.

---

## 6. SOLVER BENCHMARK RESULTS (WALL-CLOCK CEILING $T = 2.0$s)

Each candidate arm was evaluated across the 4 authorized solvers with seed `202601`:

| Forecast Arm | Solver Name | Status | Feasible? | Objective | Reassigns | Contact | Remote | Unassigned | Conflicts | Runtime (ms) |
|---|---|---|---|---|---|---|---|---|---|---|
| **`schedule_only`** | `DeterministicGreedy` | `FEASIBLE` | **YES** | 4200.0 | 20 | 10 | 20 | 0 | 0 | 0.7 |
| | `CPSat` | `OPTIMAL` | **YES** | 4200.0 | 20 | 10 | 20 | 0 | 0 | 94.7 |
| | `SimulatedAnnealing` | `FEASIBLE` | **YES** | 4200.0 | 20 | 10 | 20 | 0 | 0 | 2000.5 |
| | `HybridCPSatSA` | `FEASIBLE` | **YES** | 4200.0 | 20 | 10 | 20 | 0 | 0 | 1096.1 |
| **`arrival_linear_baseline_v1`** | `DeterministicGreedy` | `FEASIBLE` | **YES** | 4210.0 | 21 | 10 | 20 | 0 | 0 | 0.5 |
| | `CPSat` | `OPTIMAL` | **YES** | 4200.0 | 20 | 10 | 20 | 0 | 0 | 93.8 |
| | `SimulatedAnnealing` | `FEASIBLE` | **YES** | 4200.0 | 20 | 10 | 20 | 0 | 0 | 2000.7 |
| | `HybridCPSatSA` | `FEASIBLE` | **YES** | 4200.0 | 20 | 10 | 20 | 0 | 0 | 1093.6 |
| **`P4_ngboost_student_t`** | `DeterministicGreedy` | `FEASIBLE` | **YES** | 4200.0 | 20 | 10 | 20 | 0 | 0 | 0.5 |
| | `CPSat` | `OPTIMAL` | **YES** | 4200.0 | 20 | 10 | 20 | 0 | 0 | 94.3 |
| | `SimulatedAnnealing` | `FEASIBLE` | **YES** | 4200.0 | 20 | 10 | 20 | 0 | 0 | 2000.6 |
| | `HybridCPSatSA` | `FEASIBLE` | **YES** | 4200.0 | 20 | 10 | 20 | 0 | 0 | 1095.7 |
| **`oracle_actual`** | `DeterministicGreedy` | `FEASIBLE` | **YES** | 4220.0 | 22 | 10 | 20 | 0 | 0 | 0.5 |
| | `CPSat` | `OPTIMAL` | **YES** | 4200.0 | 20 | 10 | 20 | 0 | 0 | 93.2 |
| | `SimulatedAnnealing` | `FEASIBLE` | **YES** | 4200.0 | 20 | 10 | 20 | 0 | 0 | 2000.8 |
| | `HybridCPSatSA` | `FEASIBLE` | **YES** | 4200.0 | 20 | 10 | 20 | 0 | 0 | 1092.9 |

### Key Solver Observations:
1. **Feasibility**: 16 out of 16 solver runs (100%) were proven feasible by the independent constraint verifier.
2. **CP-SAT Optimality**: CP-SAT solved to proven global optimality (`OPTIMAL`) within <100 ms for all 4 forecast arms.
3. **Budget Compliance**: No solver exceeded the configured 2.0-second total wall-clock budget.
4. **Greedy Performance**: Deterministic Greedy found the optimal objective ($4200.0$) for `P4_ngboost_student_t` and `schedule_only` in 0.5 ms.

---

## 7. MONTE CARLO ROBUSTNESS & CONVERGENCE RESULTS

### 7.1 Native Stochastic Sampling Setup
- **Sample Generation**: Common Random Numbers matrix $U \in (0.001, 0.999)^{2500 \times 30}$ generated with seed `202601` (SHA-256: `1ea406cf7c61bd1d6662648414d121a9b7ce9b3268d65842495a09986a05d0fc`).
- **P4 Heteroscedastic Transformation**:
  $$Y_{s, i} = \mu(x_i) + \sigma(x_i) \cdot t_{\nu(x_i)}^{-1}(U_{s, i})$$
  - $\mu(x_i) \in [-9.23, -9.02]\text{ min}$
  - $\sigma(x_i) \in [11.01, 11.52]\text{ min}$
  - $\nu(x_i) \in [2.10, 2.77]$
- **Randomness Audit**:
  - `P4_ngboost_student_t`: 2,500 unique scenarios ($100\%$), positive per-flight variance (mean variance $= 365.62$).
  - Zero non-finite draws, zero NaNs, zero Infs.

### 7.2 Convergence Across Registered Grid:

| Forecast Arm | $N$ | Mean Objective | Median Objective | Std Dev | MC Standard Error | 95% Confidence Interval | Relative Change vs Prev $N$ |
|---|---|---|---|---|---|---|---|
| **`P4_ngboost_student_t`** | **100** | 4151.40 | 4220.0 | 125.26 | 12.53 | [4126.85, 4175.95] | Baseline |
| | **250** | 4140.12 | 4220.0 | 126.54 | 8.00 | [4124.43, 4155.81] | 0.002717 (0.27%) |
| | **500** | **4138.76** | **4220.0** | **135.94** | **6.08** | **[4126.84, 4150.68]** | **0.000328 (0.03%)** |
| | **1000** | 4137.31 | 4220.0 | 133.47 | 4.22 | [4129.04, 4145.58] | 0.000350 (0.04%) |
| | **2500** | 4137.67 | 4220.0 | 134.99 | 2.70 | [4132.38, 4142.96] | 0.000087 (0.01%) |
| **`schedule_only`** | **500** | 4200.00 | 4200.0 | 0.00 | 0.00 | [4200.00, 4200.00] | 0.000000 |
| **`arrival_linear_baseline_v1`** | **500** | 3336.88 | 3410.0 | 365.55 | 16.35 | [3304.84, 3368.92] | 0.003645 |
| **`oracle_actual`** | **500** | 4220.00 | 4220.0 | 0.00 | 0.00 | [4220.00, 4220.00] | 0.000000 |

### 7.3 Convergence Analysis:
- At the canonical count $N = 500$, the 95% confidence interval for P4 mean assignment cost is tightly bounded at $[4126.84, 4150.68]$ ($\pm 0.29\%$).
- The relative change in mean objective between $N = 500$ and $N = 1000$ is only $0.035\%$, confirming stability without claiming arbitrary "statistical optimality."
- Standard error decays strictly at the theoretical rate $O(1/\sqrt{N})$ ($12.53 \to 8.00 \to 6.08 \to 4.22 \to 2.70$).

---

## 8. FAILURE ACCOUNTING

- **Solver Infeasibility**: $0 / 16$ runs ($0.0\%$).
- **Solver Timeouts**: $0 / 16$ runs ($0.0\%$).
- **Monte Carlo Numerical Errors**: $0 / 2500$ realizations ($0.0\%$).
- **Monte Carlo Infeasible Assignments**: $0 / 2500$ realizations ($0.0\%$).
- **Overall Execution Success Rate**: **100.0%**. Zero failed cases were deleted, altered, or replaced.

---

## 9. TEST SUITE RESULTS

All unit, property, and regression test suites executed and passed cleanly:

1. **Native P4 Downstream Unit Suite** ([`tests/downstream/test_native_p4_downstream.py`](file:///D:/Study/Code/Python/Aelous/tests/downstream/test_native_p4_downstream.py)):
   - `test_p4_checkpoint_verification`: **PASSED**
   - `test_p4_checkpoint_mismatch_raises`: **PASSED**
   - `test_p4_distribution_parameters`: **PASSED**
   - `test_synthetic_turn_contract`: **PASSED**
   - `test_gate_verifier_overlap_detection`: **PASSED**
   - `test_all_four_solvers_execution`: **PASSED**
   - `test_monte_carlo_grid_execution`: **PASSED**
   - **Total**: 7 / 7 tests passed in 6.74s.
2. **Full Downstream Suite** ([`tests/downstream/`](file:///D:/Study/Code/Python/Aelous/tests/downstream/)):
   - **Total**: 33 / 33 tests passed in 6.90s.
3. **Solver Parity & Reproducibility Suite** ([`tests/test_cp_sat_solver.py`](file:///D:/Study/Code/Python/Aelous/tests/test_cp_sat_solver.py), [`tests/test_r26_solver_equal_compute.py`](file:///D:/Study/Code/Python/Aelous/tests/test_r26_solver_equal_compute.py)):
   - **Total**: 18 / 18 tests passed in 0.57s.
4. **Objective Audit Suite** ([`tests/test_objective_audit.py`](file:///D:/Study/Code/Python/Aelous/tests/test_objective_audit.py), [`tests/test_r17_downstream_semantics.py`](file:///D:/Study/Code/Python/Aelous/tests/test_r17_downstream_semantics.py)):
   - **Total**: 10 / 10 tests passed in 2.81s.

---

## 10. ARTIFACTS CREATED

All new outputs were written exclusively to [`artifacts/native_downstream_v1/`](file:///D:/Study/Code/Python/Aelous/artifacts/native_downstream_v1/):

| Artifact File | Description | SHA-256 Checksum |
|---|---|---|
| `p4_checkpoint_verification.json` | Checkpoint verification and metadata | `d461e4f403ea5b8b5d1ab2ea342f8afc40bd8169f677c95462ee069f5d70e225` |
| `scenario_manifest.json` | SCEN_2023_LOW flight keys and hash | `a3f5971fe57a6e44c8d750f35a35c9f3dd1d2074654dbb4475d3e9563bda5f1a` |
| `solver_benchmark_results.json` | 16 solver run records (4 models x 4 solvers) | `4f88de7bb199d8aa39a62c85cef12e496e0cef1db3efc65ecfeb1524a79205b8` |
| `solver_benchmark_results.csv` | Tabular export of solver benchmark records | `75dea4ad4e2cf47fb33f60df7ab5ceeb8cc28a29d001f5b2c0c2a416b78caefd` |
| `paired_model_deltas.json` | Paired differences across all model pairs | `b1f20090174876a4d6159f1946bea79b2b7f861f6a2d838aa8eecc4961c3da5d` |
| `paired_model_deltas.csv` | Tabular export of paired model deltas | `a892689ac05664dffe53a859485329669cdbed2cd4819fde8633d2f23372eee1` |
| `randomness_audit.json` | Uniqueness and positive variance audit | `9669b17a4c03fa1b3519c4ee1e43624f8e5c72414f9664d4e7ea52da8940943b` |
| `monte_carlo_convergence_results.json` | Grid convergence statistics (100 to 2500) | `5551404cfd53c6da6c6819ae9718cef15ff63b96204a299c37aa2ea7e199e6c7` |
| `monte_carlo_convergence_results.csv` | Tabular export of MC convergence statistics | `dd185a0fd1f3ecb8222ea126db82922aaa03492e2b2df18eef2d44a697720267` |
| `downstream_summary.json` | Executive summary of solver and MC metrics | `f0da213b06517d4fdb04f3d1f92c8649cda1b1f06d7de1586aac12f1d2dc6d23` |
| `run_manifest.json` | Run provenance, git commit, and execution status | `0da219225f751c76171fb5855a96105b73ad6b41fe45891e64c7c8fa0a9cdeab` |
| `manifest.sha256` | Master cryptographic checksum file | Verified |

---

## 11. FILES CHANGED & UNCHANGED

- **Files Created**:
  - `src/evaluation/native_downstream_p4.py` (New P4 downstream evaluation engine)
  - `scripts/run_native_p4_downstream.py` (New runner script)
  - `tests/downstream/test_native_p4_downstream.py` (New unit & integration tests)
  - `artifacts/native_downstream_v1/*` (New isolated artifact directory)
  - `P10A_NATIVE_P4_DOWNSTREAM_REBUILD.md` (Forensic audit report)
- **Files Intentionally Unchanged**:
  - All historical manifests, configs, and notebooks remain 100% untouched.
  - Historical benchmarks (`R21`, `R26`, `artifacts/downstream_model_comparison/`) preserved intact without modification.
  - Frozen model weights (`artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib`) strictly unmodified.

---

## 12. SCIENTIFIC LIMITATIONS & CLAIM BOUNDARIES

In accordance with Decisions **[D019](file:///D:/Study/Code/Python/Aelous/docs/decisions/decision_registry.md#L33)** and **[D028](file:///D:/Study/Code/Python/Aelous/docs/decisions/decision_registry.md#L42)**:
1. **Synthetic Research Environment**: Evaluated exclusively within a stylized, synthetic gate assignment simulation based on scheduled banks. No claims regarding physical airfield gate assignments, ramp control, or real-world operations at ATL are made.
2. **Zero Operational Claim**: No claims of real flight delay reduction, actual gate conflict reduction, or airport monetary cost savings are certified.
3. **Equal Wall-Clock vs Computational Work**: All solvers operated under an equal wall-clock ceiling ($T = 2.0\text{s}$). This certifies equal time ceiling parity, NOT equal computational CPU work across disparate solver paradigms (greedy heuristic vs exact branch-and-bound vs local search).

---

## 13. REMAINING BLOCKERS & READINESS FOR P10-B

- **Blocker Status**: **ZERO REMAINING BLOCKERS FOR P10-A**.
- **P10-A Status**: **`P10A_STATUS = PASS`**.
- **Readiness for P10-B**: All downstream requirements for P10-A are satisfied. P10-B (Monte Carlo Robustness & Recourse Deep Dive / Cross-Seed Stability) may proceed upon instruction.
- **System Freeze & Holdout Notice**: This pass did NOT freeze the system and did NOT open 2024. 2024 remains completely sealed.

```text
P10A_STATUS = PASS
```
