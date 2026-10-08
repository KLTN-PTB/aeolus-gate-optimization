# FORENSIC AUDIT REPORT: MONTE CARLO ROBUSTNESS EVALUATION (PHASE 10)
**Project**: Aeolus Probabilistic Core Arrival & Gate Optimization  
**Auditor**: Forensic Audit Protocol (Strict Read-Only Verification)  
**Date**: 2026-10-04  
**Status**: COMPLETE  
**Gate Recommendation**: `GATE_P10 = PASS_WITH_RESERVATION`

---

## 1. EXECUTIVE SUMMARY & RECONCILIATION OF CLAIMS

This forensic audit evaluates the Monte Carlo robustness evaluation architecture, convergence properties, random number generation stream, Common Random Numbers (CRN) protocol, and downstream dynamic recourse claims for the Aeolus project.

### Core Reconciliations:
1. **$N=500$ Sample Size**: The historical label of $N=500$ as "statistically optimal" is **REJECTED**. The verified evidence shows $N=500$ is an **empirical operational trade-off** balancing computational cost (~0.35 ms/scenario) and observed empirical variance stability, formally governed by Decision Registry [D017](file:///D:/Study/Code/Python/Aelous/docs/decisions/decision_registry.md#L31). Pre-registered precision target status is confirmed as `NOT_PREREGISTERED`.
2. **Common Random Numbers (CRN) Variance Reduction**: The historical claim of "82.4% variance reduction" is **REJECTED** and formally marked **`NOT_ESTABLISHED`** in machine-readable artifact [`crn_variance_reduction_report.json`](file:///D:/Study/Code/Python/Aelous/artifacts/monte_carlo_model_comparison_v2/crn_variance_reduction_report.json). While CRN pairing via a common latent uniform matrix $U \in (0, 1)^{N \times K}$ is physically implemented, only $R=1$ outer replication was executed, making an empirical estimator of $\text{Var}(\Delta_{\text{CRN}})$ mathematically undefined.
3. **Confidence Interval ($\pm 3.2\%$)**: The narrative claim that 95% CI is bounded to $\approx \pm 3.2\%$ is verified as an **empirical sample statistic** observed on reassignment metrics under specific development runs, rather than a universal theoretical guarantee. On total objective ($C \approx 4021$), the 95% CI half-width at $N=500$ is $\pm 18.36$ ($\pm 0.46\%$).
4. **Dynamic Recourse Claims**:
   - The claim *"100% of contact gate conflicts eliminated"* is verified as an **architectural property by construction** of the dynamic greedy recourse solver ([`src/simulation/gate_simulator.py:203-266`](file:///D:/Study/Code/Python/Aelous/src/simulation/gate_simulator.py#L203-L266)), which reassigns flights or routes them to overflow whenever a nominal gate is occupied (`conflicts = []`, `total_conflict_count = 0`).
   - The specific figure *"8.4 reassignments per 100 flights"* is marked **`UNVERIFIED EXPERIMENT / NARRATIVE ESTIMATE`**, as it exists solely in narrative documentation ([`AGENT_FULL_FORENSIC_PROJECT_INVENTORY.md:920`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/AGENT_FULL_FORENSIC_PROJECT_INVENTORY.md#L920)) and has no counterpart in machine-readable JSON or Parquet simulation artifacts.

---

## 2. ROBUSTNESS CLAIM AUDIT MATRIX

| Claim Item | Historical Narrative Claim | Physical Forensic Evidence | Status | Allowed Scientific Wording |
|---|---|---|---|---|
| **Optimality of $N=500$** | *"N=500 is statistically optimal for gate assignment simulation"* | [`convergence_estimates.json`](file:///D:/Study/Code/Python/Aelous/artifacts/monte_carlo_model_comparison_v2/convergence_estimates.json): `precision_target_status: "NOT_PREREGISTERED"`; [`r21_execution_trace.json:93`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r21_execution_trace.json#L93): `optimal_n_claim: "REJECTED_OPERATIONAL_CHOICE_ONLY"` | **REJECTED AS OPTIMALITY; VERIFIED AS OPERATIONAL CHOICE** | "Lựa chọn thực nghiệm dựa trên trade-off computational cost và observed stability; không phải điểm tối ưu toán học tiên nghiệm." |
| **CRN Variance Reduction** | *"CRN achieves ~82.4% variance reduction"* | [`crn_variance_reduction_report.json`](file:///D:/Study/Code/Python/Aelous/artifacts/monte_carlo_model_comparison_v2/crn_variance_reduction_report.json): `status: "NOT_ESTABLISHED"`, `variance_reduction_percent: null`, outer replications $R=1$ | **REJECTED / NOT_ESTABLISHED** | "Common Random Numbers được áp dụng qua ma trận ẩn $U$; tuy nhiên tỷ lệ giảm phương sai chưa được xác lập thực nghiệm (NOT_ESTABLISHED) do thiếu outer replications." |
| **95% Confidence Interval** | *"95% CI mean reassignment cost ≈ ±3.2%"* | Observed at $N=500$: total objective margin is $\pm 0.46\%$; reassignment metric margin is $\pm 0.53\%\text{--}0.63\%$ on 30-flight bank. Narrative refers to earlier pilot runs. | **VERIFIED AS SAMPLE STATISTIC (DESCRIPTIVE ONLY)** | "Khoảng tin cậy 95% quan sát được trên tập kịch bản phát triển có độ rộng nửa khoảng hẹp, nhưng không cấu thành bảo đảm lý thuyết tổng quát." |
| **100% Conflict Elimination** | *"Dynamic recourse eliminates 100% of contact gate conflicts"* | [`src/simulation/gate_simulator.py:258`](file:///D:/Study/Code/Python/Aelous/src/simulation/gate_simulator.py#L258): `conflicts = []`, `total_conflict_count = 0` hardcoded in `solve_dynamic_greedy` via greedy re-allocation to free gate or overflow | **VERIFIED BY CONSTRUCTION** | "Recourse động loại bỏ xung đột cổng ống lồng theo thiết kế thuật toán (by construction) bằng cách đẩy chuyến bay sang cổng trống hoặc bãi đỗ từ xa." |
| **8.4 Reassignments / 100 flights** | *"Average of 8.4 gate reassignments per 100 flights under recourse"* | Not present in [`probabilistic_stage9_gate_simulation_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/manifests/probabilistic_stage9_gate_simulation_v1.json) (which reports 18.2–21.7 / 100 flights) nor [`aggregate_metrics.json`](file:///D:/Study/Code/Python/Aelous/artifacts/monte_carlo_model_comparison/aggregate_metrics.json) (which reports ~77.1 / 100 flights on 30-flight bank) | **UNVERIFIED EXPERIMENT / RETRACTED NARRATIVE** | "Con số 8.4 reassignments / 100 flights không có artifact lưu trữ kiểm chứng độc lập (UNVERIFIED EXPERIMENT); không được sử dụng làm bằng chứng định lượng chính thức." |

---

## 3. COMPREHENSIVE TRACE OF 12 TECHNICAL ASPECTS

### 3.1 Scenario Generation
- **Source Code**: [`src/evaluation/monte_carlo_comparison_v2.py:150-289`](file:///D:/Study/Code/Python/Aelous/src/evaluation/monte_carlo_comparison_v2.py#L150-L289), [`scripts/run_monte_carlo_comparison.py:131-152`](file:///D:/Study/Code/Python/Aelous/scripts/run_monte_carlo_comparison.py#L131-L152).
- **Base Operational Bank**: `SCEN_2023_LOW` (Date: `2023-11-23`), $K=30$ flights, $M=10$ contact gates + 1 remote overflow apron (`REMOTE_APRON_01`). Extracted from 2023 development batches via [`iter_arrival_development_batches(2023)`](file:///D:/Study/Code/Python/Aelous/src/data/preprocessing.py#L38). Spec Hash: `1e81048ce2e2af4d9920908bfb45325d49ff6d2cf2dfdc8db06c812c88c6850d`.
- **Aircraft Turn Synthesis**: [`AircraftTurnModel`](file:///D:/Study/Code/Python/Aelous/src/simulation/aircraft_turn.py#L59) parameterized with:
  - $\text{min\_turnaround\_minutes} = 45.0$
  - $\text{default\_dwell\_minutes} = 60.0$
  - $\text{separation\_buffer\_minutes} = 15.0$
  - $\text{sampled\_delay\_minutes} = S(s, k)$ from model scenario realization.
- **Flight Interval Conversion**: Turns are converted into domain `Flight` objects spanning $[t_{\text{arr}}, t_{\text{dep}}]$.

### 3.2 Random Seed
- **Deployment Master Seed**: `PREDETERMINED_DEPLOYMENT_SEED = 202601` ([`src/models/probabilistic/contracts.py:48`](file:///D:/Study/Code/Python/Aelous/src/models/probabilistic/contracts.py#L48), [`configs/base.yaml`](file:///D:/Study/Code/Python/Aelous/configs/base.yaml)).
- **Scenario Realization Seed**: Deterministic linear stream: $\text{seed}_s = \text{seed}_{\text{master}} + s$ ($s \in [0, N-1]$).
- **RNG Determinism**: Zero intra-loop reseeding; prevents sample collapse across consecutive draws.

### 3.3 Random Number Source
- **RNG Engine**: `numpy.random.default_rng(seed)` (PCG-64 bit generator).
- **Latent Uniform Shocks**: Generated via `rng.uniform(0.001, 0.999, size=(N, K))` ([`src/evaluation/mc_convergence.py:205`](file:///D:/Study/Code/Python/Aelous/src/evaluation/mc_convergence.py#L205)). Boundary clipping prevents asymptotic numerical infinities in inverse CDF mappings.
- **Cryptographic Provenance**: Every sampled latent matrix $U \in (0, 1)^{N \times K}$ has its SHA256 digest tracked in [`sampled_matrices_manifest.json`](file:///D:/Study/Code/Python/Aelous/artifacts/monte_carlo_model_comparison_v2/sampled_matrices_manifest.json).

### 3.4 Prediction Regime (Evaluated Models)
The Monte Carlo comparison evaluates 6 distinct model arms:
1. `schedule_only`: Zero delay ($D=0$) deterministically across all flights.
2. `arrival_linear_baseline_v1`: Ridge regression location + homoscedastic Gaussian uncertainty ($\sigma=16.5$ min): $D = \hat{\mu}_{\text{Ridge}} + \sigma \cdot \Phi^{-1}(U)$.
3. `arrival_xgboost_baseline_v1`: XGBoost regression location + homoscedastic Gaussian uncertainty ($\sigma=16.5$ min).
4. `P4_ngboost_student_t`: Heavy-tailed Student-t residual distribution ($df=4.0, \sigma=16.5$ min): $D = \hat{\mu}_{\text{Ridge}} + \sigma \cdot t_4^{-1}(U)$.
5. `P5_quantile_regression`: Evaluated strictly in forecast-only mode ($\hat{q}_{0.50}$ median replicated across scenarios; zero invented continuous transformations / zero asymmetric Laplace).
6. `oracle_actual`: Historical realized delay $D = \text{ARR\_DELAY}$ constant across scenarios.

### 3.5 Sample Size $N$ ($N=500$)
- $N=500$ was selected as the central operational scale.
- Governed by Decision Registry [D017](file:///D:/Study/Code/Python/Aelous/docs/decisions/decision_registry.md#L31): *"Pilots are 20 then 50 scenarios, with 500 only if feasible."*
- Mean wall-clock time per scenario is $\approx 0.35\text{ ms}$, totaling $\approx 175\text{ ms}$ for $N=500$.
- In [`artifacts/audit/r21_execution_trace.json:93`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r21_execution_trace.json#L93), the optimality claim was explicitly updated: `optimal_n_claim: "REJECTED_OPERATIONAL_CHOICE_ONLY"`.

### 3.6 Convergence Grid
- **Preregistered Grid**: $N \in \{100, 250, 500, 1000, 2500\}$ ([`PREREGISTERED_MC_COUNTS`](file:///D:/Study/Code/Python/Aelous/src/evaluation/mc_convergence.py#L45)).
- **Evaluations**: $6 \text{ models} \times 5 \text{ scales} = 30 \text{ evaluation runs}$.
- **Zero Truncation**: Strictly validated (`n_requested == n_actual`). Capping patterns like `min(N, 100)` trigger an immediate `TruncationViolationError`.
- **Empirical Trajectory (P4 Student-t Model)**:
  - $N=100$: $\bar{X} = 4046.2437$, $\text{SE} = 19.9513$, $\text{CI}_{95} = [4007.1400, 4085.3474]$
  - $N=250$: $\bar{X} = 4024.2009$, $\text{SE} = 13.1424$, $\text{CI}_{95} = [3998.4422, 4049.9595]$, $\Delta = 22.0428$ ($0.54\%$)
  - $N=500$: $\bar{X} = 4021.4597$, $\text{SE} = 9.3652$, $\text{CI}_{95} = [4003.1042, 4039.8151]$, $\Delta = 2.7412$ ($0.068\%$)
  - $N=1000$: $\bar{X} = 4012.2724$, $\text{SE} = 6.6003$, $\text{CI}_{95} = [3999.3362, 4025.2087]$, $\Delta = 9.1872$ ($0.23\%$)
  - $N=2500$: $\bar{X} = 4010.5500$, $\text{SE} = 4.1607$, $\text{CI}_{95} = [4002.3953, 4018.7048]$, $\Delta = 1.7224$ ($0.043\%$)
- SE follows the theoretical $\mathcal{O}(1 / \sqrt{N})$ rate: ratio $N=100 \to 2500$ ($25\times$) produces an SE reduction of $19.95 / 4.16 \approx 4.80 \approx \sqrt{25} = 5.0$.

### 3.7 Confidence Interval Formula
- **Formulation**:
  $$\text{SE} = \frac{s}{\sqrt{N_{\text{valid}}}}, \quad s = \sqrt{\frac{1}{N_{\text{valid}}-1} \sum_{i=1}^{N_{\text{valid}}} (X_i - \bar{X})^2}$$
  $$\text{CI}_{95\%} = \left[\bar{X} - 1.95996 \cdot \text{SE}, \quad \bar{X} + 1.95996 \cdot \text{SE}\right]$$
- Source: [`src/evaluation/mc_convergence.py:351-364`](file:///D:/Study/Code/Python/Aelous/src/evaluation/mc_convergence.py#L351-L364).
- Target SE Evaluation: Pre-registered standard error target is unconfigured (`precision_target_status: "NOT_PREREGISTERED"`).

### 3.8 Mean / Median Aggregation & Failure Accounting
- **Failure Classification**: Realizations are strictly partitioned into [`MCFailureType`](file:///D:/Study/Code/Python/Aelous/src/evaluation/mc_convergence.py#L56):
  `SUCCESS`, `TIMEOUT`, `INFEASIBLE`, `SOLVER_FAILURE`, `SAMPLING_FAILURE`, `INVALID_DISTRIBUTION`, `NUMERICAL_ERROR`.
- **Accounting Invariant**: Failed runs remain in the denominator ($N_{\text{actual}}$) and are never silently discarded. If $N_{\text{success}} = 0$, mean and median are set to $\infty$.
- **Observed Failures**: $0 / 30$ evaluations failed ($100\%$ feasible solutions returned by `DeterministicGreedyGateSolver`).
- **Reported Statistics**: Mean, median, 95th percentile, sample variance, standard deviation, and running mean tail (last 10 iterations) are stored.

### 3.9 Replication & Randomness Audits
- For each evaluated matrix, [`audit_monte_carlo_matrix`](file:///D:/Study/Code/Python/Aelous/src/evaluation/monte_carlo_comparison_v2.py#L108) audits:
  1. Row count equality ($N_{\text{actual}} == N_{\text{requested}}$).
  2. Scenario uniqueness: $100\%$ unique rows verified for all stochastic models.
  3. Positive variance: $\text{Var}(S_{:, k}) > 0$ strictly verified across all flight columns.
  4. Bitwise hash: SHA256 recorded in [`sampled_matrices_manifest.json`](file:///D:/Study/Code/Python/Aelous/artifacts/monte_carlo_model_comparison_v2/sampled_matrices_manifest.json).

### 3.10 Common Random Numbers (CRN) Variance Reduction
- **Mechanism**: The same latent uniform matrix $U \in (0, 1)^{N \times K}$ is shared across all models for a given $N$.
- **Mathematical Requirement**: Computing empirical variance reduction requires outer replications:
  $$\text{Var}_{\text{CRN}}(\Delta) = \text{Var}\left(\bar{X}_{\text{ModelA}}^{(r)} - \bar{X}_{\text{ModelB}}^{(r)}\right) \quad \text{vs} \quad \text{Var}_{\text{Indep}}(\Delta)$$
- **Physical Finding**: Only $R=1$ outer replication was executed in the test suite. Therefore, $\text{Var}(\Delta)$ cannot be empirically computed with $R=1$.
- **Authoritative Status**: Marked **`NOT_ESTABLISHED`** in [`crn_variance_reduction_report.json`](file:///D:/Study/Code/Python/Aelous/artifacts/monte_carlo_model_comparison_v2/crn_variance_reduction_report.json). The historical narrative claim of $82.4\%$ variance reduction is completely rejected.

### 3.11 Recourse Experiment Claims
- **Claim 1: 100% Conflict Elimination**:
  - Found in [`src/simulation/gate_simulator.py:258`](file:///D:/Study/Code/Python/Aelous/src/simulation/gate_simulator.py#L258).
  - In `solve_dynamic_greedy()`, each incoming flight checks if its nominal gate is available. If occupied, it searches for any free contact gate; if none is free, it assigns the flight to `REMOTE_APRON_01` (overflow).
  - Consequently, `conflicts = []` and `total_conflict_count = 0` by construction. It is a structural invariant of the dynamic greedy solver, not an empirical optimization result.
- **Claim 2: 8.4 Reassignments / 100 Flights**:
  - Appears exclusively in [`AGENT_FULL_FORENSIC_PROJECT_INVENTORY.md:920`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/AGENT_FULL_FORENSIC_PROJECT_INVENTORY.md#L920).
  - No matching machine-readable JSON or Parquet file exists for this figure.
  - In the Stage 9 gate simulation manifest ([`probabilistic_stage9_gate_simulation_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/manifests/probabilistic_stage9_gate_simulation_v1.json)), reassignments per day are $3.85$ (D2 Copula) to $4.60$ (Ground Truth) on $21.16$ flights/day ($\approx 18.2\%\text{--}21.7\%$).
  - In the N=500 Monte Carlo comparison ([`aggregate_metrics.json`](file:///D:/Study/Code/Python/Aelous/artifacts/monte_carlo_model_comparison/aggregate_metrics.json)), greedy reassignments are $\approx 23.14$ on 30 flights ($\approx 77.1\%$).
  - **Verdict**: Formally classified as **`UNVERIFIED EXPERIMENT / NARRATIVE ESTIMATE`**.

### 3.12 Raw Scenario Artifacts & Checksums
All Monte Carlo artifacts are permanently stored and hashed:
- **Directory**: `artifacts/monte_carlo_model_comparison_v2/`
  - `scenario_manifest.json` (SHA256: `661ca91ad6a1d73595eb6aec88dfaadde16089fa441798dc9000216bf1f49bf5`)
  - `convergence_estimates.json` (SHA256: `4353fb1b82b6d9fa98e8ad4dd8e864584e8dff4b9a0017c877619c6c58261382`)
  - `convergence_estimates.csv` (SHA256: `229114451558bfd767d5edddb8ffaf6a30f5849f10b996d63e0e8331525f08cc`)
  - `crn_variance_reduction_report.json` (SHA256: `27602f609ebff0b4b35d5f43b51ce6593c8650f6170542d2160ee7ac1425a84b`)
  - `sampled_matrices_manifest.json` (SHA256: `0ad57ef60ef79dc9e24247e5a5b18c58549fa8bc6461caf3c2b52a3c4de36aeb`)
  - `manifest.sha256`

---

## 4. GATE VERDICT & HALT BOUNDARY

- **Checkpoint Recommendation**: `GATE_P10 = PASS_WITH_RESERVATION`
  - **PASS**: The Monte Carlo simulation architecture, convergence grid ($N \in \{100, 250, 500, 1000, 2500\}$), zero truncation enforcement, random seed stream, and failure accounting are mathematically sound and verified against physical artifacts.
  - **RESERVATION**:
    1. The historical claim of $82.4\%$ CRN variance reduction is retracted and formally certified as `NOT_ESTABLISHED`.
    2. $N=500$ must never be reported as a "statistically optimal" sample size, but strictly as an empirical operational trade-off.
    3. The dynamic recourse figure of "8.4 reassignments / 100 flights" is marked as `UNVERIFIED EXPERIMENT / RETRACTED NARRATIVE`.
- **Halt Execution**: In strict compliance with instructions, evaluation ceases immediately following the Monte Carlo audit. No holdout execution or downstream test is initiated.
