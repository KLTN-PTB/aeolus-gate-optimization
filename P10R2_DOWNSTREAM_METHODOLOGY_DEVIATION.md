# FORENSIC AUDIT REPORT: DOWNSTREAM METHODOLOGY DEVIATION (P10-R2)
**Project**: Aeolus Probabilistic Core Arrival & Gate Optimization  
**Auditor**: Forensic Audit Protocol (Strict Read-Only Verification)  
**Date**: 2026-10-04  
**Audit Scope**: Protocol Legitimacy, P5 Distribution Semantics, Downstream Claims Scope, Rebuild Requirements  
**Status**: `P10R2_STATUS = CLOSED`

---

## 1. EXECUTIVE SUMMARY & FORENSIC VERDICTS

This targeted audit investigates the protocol legitimacy, mathematical distribution semantics, and downstream validity scope following the discovery in P10-R that historical Monte Carlo simulations utilized synthetic prediction proxies rather than native frozen models.

### Key Conclusions:
1. **Protocol Authorization**: Both proxy implementations (`Ridge mu + fixed Student-t` and `XGBoost + piecewise Gaussian scaling`) are formally classified as **`METHODOLOGY_DEVIATION`**. Neither the locked Decision Registry ([`docs/decisions/decision_registry.md`](file:///D:/Study/Code/Python/Aelous/docs/decisions/decision_registry.md)) nor the Probabilistic Protocol ([`docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md`](file:///D:/Study/Code/Python/Aelous/docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md)) authorized substituting Ridge or invented asymmetric noise in place of certified models.
2. **P5 Semantic Identity**: The historical label `"ASYMMETRIC_LAPLACE_PROXY"` is **SCIENTIFICALLY REJECTED**. Mathematical derivation of $D = \text{base} + \text{adjustment}$ with $z = \Phi^{-1}(U)$ proves the distribution possesses Gaussian $\exp(-x^2 / 2\sigma^2)$ tails, not exponential Laplace tails. The exact distribution is a **discontinuous two-piece normal / split-normal** variable. The certified neutral designation is **`PIECEWISE_SCALED_GAUSSIAN_PROXY`**.
3. **Downstream Claims Partitioning**:
   - **Solver & Monte Carlo Infrastructure**: **`VALID AS SOLVER-INFRASTRUCTURE`** and **`VALID AS MC-INFRASTRUCTURE`**. Solver feasibility (100%), hard constraint satisfaction, runtimes (~0.35ms), MC convergence rates $\mathcal{O}(1/\sqrt{N})$, and $N=500$ sample size selection remain valid.
   - **ML Downstream Performance Claims**: **`INVALID FOR CERTIFIED P4/P5`**. All historical claims that "P4 improves gate assignment" or "P5 achieves superior downstream cost" are invalid for the certified models and apply solely to synthetic disturbance benchmarks.
4. **Rebuild Scope**: Minimal future rebuild required to restore the core thesis claim is **Category C (or E)**: running downstream evaluation feeding native P4 parameters ($\mu(x), \sigma(x), \nu(x)$ from frozen checkpoint) and evaluating P5 strictly in forecast-only median mode. The solver algorithms and benchmark infrastructure do not require modification.

---

## 2. TASK 1 — AUDIT PROTOCOL LEGITIMACY

We audited the entire pre-existing evidence hierarchy:
- **Locked Decision Registry**:
  - [D012](file:///D:/Study/Code/Python/Aelous/docs/decisions/decision_registry.md#L26): ML scope locked to 5 core methods.
  - [D025](file:///D:/Study/Code/Python/Aelous/docs/decisions/decision_registry.md#L39): Downstream prediction source: *"Only Core Arrival prediction feeds gate simulation/optimization."*
  - [D027](file:///D:/Study/Code/Python/Aelous/docs/decisions/decision_registry.md#L41): Decoupled model capabilities: *"Continuous Simulation: P4 Student-T; Quantiles: P5 multi-pinball"*.
- **Probabilistic Protocol Specification**:
  - Section 19 ([`docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md:1045`](file:///D:/Study/Code/Python/Aelous/docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md#L1045)): *"Không thay model trong giai đoạn này"* (Do not substitute models during this stage).
  - Section 20 ([`docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md:1090`](file:///D:/Study/Code/Python/Aelous/docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md#L1090)): *"Không được vì downstream tiện mà bỏ qua validation"* (Do not bypass validation merely for downstream convenience).
- **Roadmap Documents**:
  - Week 10 ([`docs/roadmap/03_Chi_tiet_tung_tuan_Roadmap_Aeolus_Gate_Optimization_V4_DONG_BO.md:694`](file:///D:/Study/Code/Python/Aelous/docs/roadmap/03_Chi_tiet_tung_tuan_Roadmap_Aeolus_Gate_Optimization_V4_DONG_BO.md#L694)): Perturbations must originate from development OOF residuals and documented assumptions.

### Legitimacy Findings:
1. **P4 Synthetic Proxy (`Ridge mu + fixed Student-t sigma/df`)**:
   - Zero preregistration exists authorizing Ridge point predictions combined with hardcoded homoscedastic parameters ($\sigma=16.5, \nu=4.0$) as a substitute for P4 NGBoost.
   - Classification: **`METHODOLOGY_DEVIATION`**.
2. **P5 Piecewise Gaussian Scaling (`XGBoost point + piecewise Gaussian quantile scaling`)**:
   - Zero preregistration exists authorizing asymmetric scaling of standard normal quantiles ($\sigma_L=19.8, \sigma_R=29.7$) onto XGBoost point forecasts.
   - In Task R4/R5 governance, P5 was explicitly restricted to forecast-only mode or required an approved distribution adapter.
   - Classification: **`METHODOLOGY_DEVIATION`**.

---

## 3. TASK 2 — SCIENTIFIC STATUS OF HISTORICAL DOWNSTREAM RESULTS

| Result Category | Actual Input Regime | Intended Regime | Validity Status | Permitted Claim / Scientific Scope |
|---|---|---|---|---|
| **1. Solver Feasibility** | 6 proxy regimes on 30-flight bank | Operational flight banks | **`VALID AS SOLVER-INFRASTRUCTURE`** | "Thuật toán giải (Greedy, CP-SAT) đã được chứng minh về khả năng tìm lời giải khả thi (100% feasible) trên ngân hàng chuyến bay tổng hợp." |
| **2. Hard-Constraint Correctness** | Verification suite on proxy assignments | Hard constraint enforcement | **`VALID AS SOLVER-INFRASTRUCTURE`** | "Cơ chế kiểm định độc lập xác nhận không có xung đột cổng đồng thời, duy trì buffer phân cách và không vi phạm tương thích tàu bay." |
| **3. Solver Runtime** | Greedy (~0.35ms), CP-SAT (2.0s ceiling) | Solver computational efficiency | **`VALID AS SOLVER-INFRASTRUCTURE`** | "Thời gian chạy và khả năng đáp ứng trần thời gian thực (wall-clock ceiling) của các bộ giải được xác nhận đầy đủ." |
| **4. Solver Objective Comparison** | Heuristic vs Exact vs Local Search | Benchmark on shared instances | **`VALID AS SOLVER-INFRASTRUCTURE`** | "So sánh hiệu năng tương đối giữa Greedy và CP-SAT trên tập kịch bản cố định giữ nguyên giá trị về mặt thuật toán tối ưu." |
| **5. P4 Downstream Performance** | Ridge + fixed Student-t ($\sigma=16.5, \nu=4.0$) | Native P4 NGBoost ($\mu(x), \sigma(x), \nu(x)$) | **`INVALID FOR CERTIFIED P4/P5`** (Valid only as synthetic proxy) | "Chi phí 4021.46 là của synthetic Student-t proxy trên nền Ridge; KHÔNG đại diện cho mô hình P4 NGBoost đã đóng băng." |
| **6. P5 Downstream Performance** | XGBoost + piecewise Gaussian scaling | Native P5 Quantiles / forecast-only median | **`INVALID FOR CERTIFIED P4/P5`** (Valid only as synthetic proxy) | "Chi phí 3710.43 là của một biến đổi bất đối xứng giả lập trên nền XGBoost; KHÔNG đại diện cho P5 quantile regression." |
| **7. Model Ranking Hierarchy** | Proxy distribution comparison | Native ML model comparison | **`INVALID FOR CERTIFIED P4/P5`** (Valid only as synthetic proxy) | "Thứ tự hiệu năng chỉ so sánh độ nhạy của bộ giải trước các dạng nhiễu tổng hợp khác nhau, không phản ánh thứ hạng các mô hình ML gốc." |
| **8. Monte Carlo Convergence** | Running mean, SE $\sim \mathcal{O}(1/\sqrt{N})$, deltas | MC convergence verification | **`VALID AS MC-INFRASTRUCTURE`** | "Hạ tầng toán học đánh giá hội tụ Monte Carlo tuân thủ quy luật O(1/sqrt(N)) và cơ chế failure accounting là hoàn toàn hợp lệ." |
| **9. N=500 Sample Size Selection** | Runtime vs variance trade-off | Operational scale choice | **`VALID AS MC-INFRASTRUCTURE`** | "Việc chọn N=500 là thỏa hiệp thực nghiệm hợp lệ giữa chi phí thời gian tính toán (~175ms) và độ ổn định phương sai mẫu." |
| **10. Robustness Distribution** | VaR / CVaR on proxy scenarios | Certified probabilistic risk profile | **`VALID AS SYNTHETIC-PROXY EXPERIMENT`** | "Chỉ số rủi ro đuôi (VaR, CVaR) chỉ có giá trị mô tả trên tập shock tổng hợp, không phản ánh rủi ro vận hành thực tế của mô hình P4/P5." |

---

## 4. TASK 3 — MATHEMATICAL AUDIT OF P5 DISTRIBUTION SEMANTICS

### Code Implementation Inspected:
In [`src/evaluation/monte_carlo_comparison.py:244-255`](file:///D:/Study/Code/Python/Aelous/src/evaluation/monte_carlo_comparison.py#L244-L255):
```python
spread_left = residual_sigma * 1.2    # 16.5 * 1.2 = 19.8
spread_right = residual_sigma * 1.8   # 16.5 * 1.8 = 29.7
z = norm.ppf(latent_u)
adjustment = np.where(z >= 0, z * spread_right, z * spread_left)
sampled = base[None, :] + adjustment
```

### Rigorous Mathematical Derivation:
Let $U \sim \text{Uniform}(0, 1)$.  
Then $Z = \Phi^{-1}(U) \sim \mathcal{N}(0, 1)$, a standard normal random variable.  
Let $\sigma_L = 19.8$ and $\sigma_R = 29.7$. The adjustment $A$ is defined as:
$$A = \begin{cases} 
\sigma_R Z & \text{if } Z \ge 0 \\
\sigma_L Z & \text{if } Z < 0 
\end{cases}$$

1. **Cumulative Distribution Function $F_A(a)$**:
   - For $a \ge 0$:
     $$F_A(a) = P(A \le a) = P(Z < 0) + P(0 \le \sigma_R Z \le a) = \frac{1}{2} + \left(\Phi\left(\frac{a}{\sigma_R}\right) - \frac{1}{2}\right) = \Phi\left(\frac{a}{\sigma_R}\right)$$
   - For $a < 0$:
     $$F_A(a) = P(A \le a) = P(\sigma_L Z \le a) = \Phi\left(\frac{a}{\sigma_L}\right)$$

2. **Probability Density Function $f_A(a)$**:
   - For $a > 0$:
     $$f_A(a) = \frac{d}{da}\Phi\left(\frac{a}{\sigma_R}\right) = \frac{1}{\sigma_R \sqrt{2\pi}} \exp\left(-\frac{a^2}{2\sigma_R^2}\right)$$
   - For $a < 0$:
     $$f_A(a) = \frac{d}{da}\Phi\left(\frac{a}{\sigma_L}\right) = \frac{1}{\sigma_L \sqrt{2\pi}} \exp\left(-\frac{a^2}{2\sigma_L^2}\right)$$

3. **Discontinuity at the Origin**:
   $$\lim_{a \to 0^+} f_A(a) = \frac{1}{\sigma_R \sqrt{2\pi}} = \frac{1}{29.7 \sqrt{2\pi}} \approx 0.01344$$
   $$\lim_{a \to 0^-} f_A(a) = \frac{1}{\sigma_L \sqrt{2\pi}} = \frac{1}{19.8 \sqrt{2\pi}} \approx 0.02015$$
   Because $\lim_{a \to 0^+} f_A(a) \ne \lim_{a \to 0^-} f_A(a)$, the density has a **finite jump discontinuity** at $a = 0$.

4. **Rejection of Asymmetric Laplace**:
   - The Asymmetric Laplace distribution has density $f(x) \propto \exp(-\kappa |x|)$, which decays **exponentially** ($e^{-|x|}$).
   - In contrast, $f_A(a)$ decays as $\exp(-a^2 / 2\sigma^2)$, which is **strictly Gaussian / normal**.
   - The label `"Asymmetric Laplace"` in historical documentation was a complete mathematical misnomer.

**Formal Semantic Designation**:
```text
P5_DISTRIBUTION_IDENTITY = PIECEWISE_SCALED_GAUSSIAN_PROXY
```
*(Alternative exact formulation: Discontinuous Split-Normal Distribution without boundary normalization).*

---

## 5. TASK 4 — CONTAMINATION AUDIT OF PREVIOUS P10 CLAIMS

We examined each claim in the P10 audit to determine the exact boundary of contamination:

| Claim in P10 | Affected by Proxy Lineage? | Contamination Status | Corrective Action |
|---|---|---|---|
| **P4 Operational Superiority** | **YES** | **CONTAMINATED / INVALID** | Retract claim that P4 NGBoost was demonstrated to reduce gate costs. Downgrade to: "Heavy-tailed Student-t synthetic disturbance model evaluated." |
| **P5 Downstream Cost Reduction** | **YES** | **CONTAMINATED / INVALID** | Retract claim that P5 quantile model achieves 3710.43 mean cost. Downgrade to: "Invented piecewise-scaled Gaussian disturbance evaluated." |
| **Model Ranking Hierarchy** | **YES** | **CONTAMINATED / INVALID** | Retract ranking as an ML model comparison. Reframe as sensitivity benchmark across synthetic disturbance distributions. |
| **Solver Benchmark Fairness (T=2.0s)** | **NO** | **UNCONTAMINATED / VALID** | Solvers operated on synthesized arrival intervals. The fairness ceiling, timeouts, and objective evaluations remain 100% valid. |
| **Hard Constraint Satisfaction** | **NO** | **UNCONTAMINATED / VALID** | Evaluator independent checks confirmed 0 gate overlaps, buffer maintenance, and 100% feasibility. Valid regardless of arrival source. |
| **Objective Formulation** | **NO** | **UNCONTAMINATED / VALID** | Cost function weights (reassignment=10, remote=200, unassigned=1000) evaluated assignments identically. |
| **Monte Carlo Convergence** | **NO** | **UNCONTAMINATED / VALID** | Mathematical rate of convergence $\mathcal{O}(1/\sqrt{N})$, delta stability, and failure accounting remain sound. |
| **$N=500$ Sample Size Selection** | **NO** | **UNCONTAMINATED / VALID** | Valid empirical operational trade-off balancing solver runtime and sample variance. |
| **Dynamic Recourse Conflict Elimination** | **NO** | **UNCONTAMINATED / VALID** | Confirmed valid by construction (`conflicts = []` in dynamic greedy solver). |
| **8.4 Reassignments / 100 flights** | **NO** (already rejected) | **RETRACTED IN P10** | Retained as `UNVERIFIED EXPERIMENT`. |

---

## 6. TASK 5 — MINIMAL SCIENTIFIC REBUILD SCOPE

To resolve the methodology deviation without unnecessary churn, we evaluated the rebuild scopes:

- **Scope A (No rebuild)**: Relabels historical experiments as synthetic proxies only. The project surrenders the core thesis claim that native P4 machine learning improves gate optimization.
- **Scope B (Relabel proxy only)**: Legally compliant but leaves the ML-to-downstream research link unproven.
- **Scope C (Re-run only P4 downstream integration)**: Minimal sufficient scope to prove native P4 thesis claims. Feeds native P4 predictions ($\mu(x), \sigma(x), \nu(x)$ from frozen checkpoint) into `AircraftTurnModel` $\to$ `DeterministicGreedyGateSolver`. Leaves solver benchmark and baseline point models untouched.
- **Scope D (Re-run only P5 downstream integration)**: Only evaluates P5 in forecast-only median mode. Insufficient alone because P5 lacks continuous density.
- **Scope E (Re-run both P4 and P5 downstream integration)**:
  - P4: Evaluated using native frozen NGBoost Student-t distribution ($Y = \mu(x) + \sigma(x) \cdot T_{\nu(x)}$).
  - P5: Evaluated in strict forecast-only median mode ($\hat{q}_{0.50}$ with zero invented transformation).
  - Baselines & Solvers: Reused without rerun.
- **Scope F (Rebuild full downstream benchmark)**: Unnecessary; wasteful of compute and violates the principle of minimal intervention.

**Determination**:
```text
REBUILD_REQUIRED = YES (if native ML-to-gate optimization claim is retained)
MINIMAL_REBUILD_SCOPE = CATEGORY_E (Re-run native P4 and clean forecast-only P5 through downstream simulation; reuse solver infrastructure)
```

---

## 7. TASK 6 — TEMPORAL SAFETY OF FROZEN ARTIFACTS FOR FUTURE REBUILD

We audited the physical availability and temporal integrity of frozen artifacts:

1. **P4 Native Model Checkpoint**:
   - Location: [`artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib`](file:///D:/Study/Code/Python/Aelous/artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib)
   - Size: 243,595 bytes, Last Modified: 2026-09-27.
   - Status: Frozen on 2016–2022 development folds. Zero 2024 data access.
2. **P4 Native Prediction Artifacts**:
   - Fold predictions: [`artifacts/probabilistic/ngboost_student_t/predictions_fold_1.parquet`](file:///D:/Study/Code/Python/Aelous/artifacts/probabilistic/ngboost_student_t/predictions_fold_1.parquet) through `predictions_fold_4.parquet`.
   - Contains observation-dependent parameters $\mu(x), \sigma(x), \nu(x)$ generated strictly before holdout unlock.
3. **P5 Native Quantile Prediction Artifacts**:
   - Location: [`artifacts/probabilistic/lightgbm_quantile/predictions_fold_1.parquet`](file:///D:/Study/Code/Python/Aelous/artifacts/probabilistic/lightgbm_quantile/predictions_fold_1.parquet) through `predictions_fold_4.parquet`.
   - Contains native pinball quantiles $\hat{q}_{0.10}, \dots, \hat{q}_{0.90}$.
   - Available to supply scalar median $\hat{q}_{0.50}$ for forecast-only downstream mode.
4. **Holdout Status**:
   - 2024 holdout remains strictly sealed. No future regeneration requires touching 2024 data.

---

## 8. TASK 7 — RECONCILIATION OF TRAINING VS SCENARIO POPULATIONS

We audited the data flow in [`scripts/run_monte_carlo_comparison.py:136-176`](file:///D:/Study/Code/Python/Aelous/scripts/run_monte_carlo_comparison.py#L136-L176) to establish unequivocal provenance:

```text
train data = Subsample of 2016–2022 development years (1,200 samples/year x 7 years = 8,400 rows) loaded via load_stratified_fold_data(train_years=[2016..2022])
scenario data = 30 inbound flights from date 2023-11-23 (SCEN_2023_LOW) extracted via iter_arrival_development_batches(2023)
validation/selection data = 1,500 samples from 2023 (unpacked as unused validation fold during Ridge fitting)
```

**Temporal Isolation Confirmation**:
- Operational year 2023 was strictly used as the **scenario population** (`X_scen`) on which flight delays and gate plans were simulated.
- 2023 was **NOT** used to fit the linear model weights (`reg_ridge.fit(X_tr_lin, y_train)`).
- 2024 was completely inaccessible (`assert_data_access_allowed(2024, "development")` failed closed).
- Provenance status: **`PROVENANCE_FULLY_RESOLVED`**.

---

## 9. EXACT FINAL FIELDS (ACCEPTANCE CRITERIA)

```text
P4_PROXY_AUTHORIZATION = METHODOLOGY_DEVIATION
P5_PROXY_AUTHORIZATION = METHODOLOGY_DEVIATION
P5_DISTRIBUTION_IDENTITY = PIECEWISE_SCALED_GAUSSIAN_PROXY
P10_P4_CLAIMS_STATUS = INVALID_FOR_CERTIFIED_P4
P10_P5_CLAIMS_STATUS = INVALID_FOR_CERTIFIED_P5
P10_SOLVER_INFRASTRUCTURE_STATUS = VALID_AS_SOLVER_INFRASTRUCTURE
P10_MC_INFRASTRUCTURE_STATUS = VALID_AS_MC_INFRASTRUCTURE
HISTORICAL_RESULTS_SCOPE = SYNTHETIC_PROXY_ONLY
REBUILD_REQUIRED = YES
MINIMAL_REBUILD_SCOPE = CATEGORY_E
WEEK9_FORECAST_GATE_MILESTONE = PARTIAL
WEEK10_SOLVER_MC_MILESTONE = PARTIAL
P10R2_STATUS = CLOSED
```

---

## 10. HALT BOUNDARY

- In strict compliance with instructions, this audit pass is complete and closed (`P10R2_STATUS = CLOSED`).
- Zero code modifications, zero retrainings, and zero experiment runs were executed.
- Execution ceases immediately. Phase 11 / Holdout evaluation is **NOT** initiated.
