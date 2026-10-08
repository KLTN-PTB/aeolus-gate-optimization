# P00 Evidence Reconciliation: Scientific Audit & Empirical Clarifications

**Phase:** `P00 — BASELINE FREEZE & EVIDENCE AUDIT`  
**Audit Date:** 2026-10-09  
**Auditor:** Senior Software Architect & ML/Optimization QA Engineer  
**Focus:** Reconciliation of quantitative claims against physical JSON/Parquet artifacts  

---

## 1. Executive Reconciliation Summary

In accordance with Phase P00 protocol, every quantitative statement in thesis reports and summary documentation was traced to its authoritative underlying data artifacts.

```
AUTHORITATIVE ARTIFACT TRACEABILITY HIERARCHY:
Physical Data Artifact (Parquet/JSON) > Execution Trace > Manifest > Code Lineage > Narrative Report
```

---

## 2. In-Depth Reconciliation of Cardinal Empirical Questions

### Question A: Does NGBoost Student-t Actually Achieve the Best CRPS?

- **Authoritative Data Sources:**
  - Historical Post-Holdout 2024: [`artifacts/post_holdout_v3/marginal_forecast_metrics_2024_v3.json`](file:///D:/Study/Code/Python/Aelous/artifacts/post_holdout_v3/marginal_forecast_metrics_2024_v3.json)
  - Forensic Metric Lineage: [`artifacts/audit/r33_p4_metric_lineage.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r33_p4_metric_lineage.json)
  - P5 Capability Forensics: [`artifacts/audit/r34_p5_capability_forensics.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r34_p5_capability_forensics.json)
  - Repaired Post-Holdout (P11-R): [`artifacts/post_holdout_re_evaluation_v1/forecast_metrics.json`](file:///D:/Study/Code/Python/Aelous/artifacts/post_holdout_re_evaluation_v1/forecast_metrics.json)
- **Empirical Metric Table:**

| Model ID | Method / Distribution | CRPS Metric Type | Development 2023 | Historical 2024 (v3) | Repaired 2024 (P11-R) | Certified Architectural Role |
| :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| **`arrival_linear_baseline_v1`** | Ridge Regression | Point MAE | $23.32\text{ m}$ | $22.91\text{ m}$ | $23.39\text{ m}$ | Fast Point Baseline |
| **`P5_quantile_regression`** | 9-Quantile Pinball | **Approx. Trapezoidal CRPS** | — | **$16.77\text{ m}$** | *N/A (Role B)* | **Role B: Marginal Quantile Champion (FORECAST_ONLY)** |
| **`P4_ngboost_student_t`** | Continuous Student-$t$ ($\mu, \sigma, \nu$) | **Exact Closed-Form CRPS** | $18.48\text{ m}$ | **$17.65\text{ m}$** | **$18.33\text{ m}$** | **Role C: Downstream Continuous Stochastic Engine** |

- **Reconciliation Verdict:**
  - **No**, NGBoost Student-t does **not** have the lowest scalar CRPS across all models. `P5_quantile_regression` achieved an approximate trapezoidal CRPS of **$16.77$ minutes** (pinball loss $6.82$ m), which is numerically superior to P4's continuous closed-form CRPS ($17.65$ m / $18.33$ m).
  - **However**, P5 generates only 9 discrete marginal quantiles without a continuous probability density function, making it strictly incapable of continuous inverse-CDF sampling for joint downstream Monte Carlo simulations.
  - Therefore, the project established a **Role Decoupling Principle**: P5 is certified as **Role B (Marginal Quantile Champion, Forecast-Only)**, while P4 is certified as **Role C (Continuous Downstream Engine)**. Any thesis claim stating "NGBoost has the best CRPS unconditionally" is scientifically inaccurate and must be framed under this decoupled role structure.

---

### Question B: Are Monte Carlo Standard Error and Confidence Intervals Mathematically Correct?

- **Authoritative Data Sources:**
  - Implementation: [`src/evaluation/mc_convergence.py#L350-L364`](file:///D:/Study/Code/Python/Aelous/src/evaluation/mc_convergence.py#L350-L364)
  - Scalability Implementation: [`src/simulation/scalability_benchmark.py#L790-L796`](file:///D:/Study/Code/Python/Aelous/src/simulation/scalability_benchmark.py#L790-L796)
  - Scalability Artifact: [`artifacts/stress_1500x50/aggregate_metrics.json`](file:///D:/Study/Code/Python/Aelous/artifacts/stress_1500x50/aggregate_metrics.json)
- **Mathematical Formulations Audited:**
  1. Sample Variance (unbiased sample variance, $ddof = 1$):
     $$s^2 = \frac{1}{N - 1} \sum_{i=1}^N (X_i - \bar{X})^2$$
  2. Monte Carlo Standard Error of the Mean:
     $$\text{SE}_{\text{MC}} = \frac{s}{\sqrt{N}}$$
  3. 95% Confidence Interval (asymptotic normal approximation, $z_{0.975} = 1.95996 \approx 1.96$):
     $$\text{CI}_{95\%} = \left[ \bar{X} - 1.96 \cdot \text{SE}_{\text{MC}}, \; \bar{X} + 1.96 \cdot \text{SE}_{\text{MC}} \right]$$
- **Numerical Audit on $N=500$ ($1500 \times 50$ Scenario):**
  - $\bar{X} = 179,468.12$, $s = 11,747.75$, $N = 500$.
  - Calculated $\text{SE} = \frac{11747.75}{\sqrt{500}} = \frac{11747.75}{22.36068} = 525.3755$. Matches artifact exactly (`525.38`).
  - Half-width $= 1.96 \cdot 525.3755 = 1029.74$.
  - $\text{CI}_{\text{lower}} = 179468.12 - 1029.74 = 178,438.38$. Matches artifact (`178438.3841`).
  - $\text{CI}_{\text{upper}} = 179468.12 + 1029.74 = 180,497.86$. Matches artifact (`180497.8559`).
- **Reconciliation Verdict:**
  - The code implementation and reported numbers are **100% mathematically correct**.
  - **Governance Note:** Historical assertions that $N=500$ is a mathematically "proven optimal sample size" or achieves an unverified "82.4% CRN variance reduction" have been formally retracted as unproven; $N=500$ is an operational engineering trade-off.

---

### Question C: Does Runtime Variability Between Replications Match Reported Results?

- **Authoritative Data Source:** [`artifacts/stress_1500x50/aggregate_metrics.json`](file:///D:/Study/Code/Python/Aelous/artifacts/stress_1500x50/aggregate_metrics.json) Section `reproducibility_audit`.
- **Audited Comparison Matrix (Run 1 vs Run 2 on $1500 \times 50$ Stress Case):**

| Solver Name | Run 1 Runtime | Run 2 Runtime | Absolute Delta ($\Delta$) | Variance Pct | Objective Identical? | Feasibility Identical? |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`DeterministicGreedy`** | $164.97\text{ ms}$ | $172.54\text{ ms}$ | $+7.57\text{ ms}$ | **$4.59\%$** | True ($182,760.0$) | True (FEASIBLE) |
| **`CPSat`** | $192,034.40\text{ ms}$ | $148,934.71\text{ ms}$ | $-43,099.69\text{ ms}$ | **$22.44\%$** | True ($600,000.0$) | True (UNKNOWN) |
| **`SimulatedAnnealing`** | $2,060.77\text{ ms}$ | $2,045.68\text{ ms}$ | $-15.09\text{ ms}$ | **$0.73\%$** | True ($182,760.0$) | True (FEASIBLE) |
| **`HybridCPSatSA`** | $1,078.96\text{ ms}$ | $1,084.04\text{ ms}$ | $+5.08\text{ ms}$ | **$0.47\%$** | True ($182,760.0$) | True (FEASIBLE) |

- **Reconciliation Verdict:**
  - Runtimes between replications are **fully consistent with the physical metrics**.
  - Greedy, SA, and Hybrid show low variance ($<5\%$).
  - CP-SAT shows $22.44\%$ runtime variability ($192.0$s vs $148.9$s) due to the heavy OS memory allocation overhead of building 8.7 million Python constraint objects across system garbage collection cycles.

---

### Question D: Does the Hybrid Solver Benchmark Account for the Full CP-SAT Phase?

- **Authoritative Code Location:** [`src/simulation/scalability_benchmark.py#L435-L490`](file:///D:/Study/Code/Python/Aelous/src/simulation/scalability_benchmark.py#L435-L490)
- **Audited Logic:**
  ```python
  # Benchmark logic for HybridCPsatSA
  if res_cpsat is not None and res_cpsat.feasible:
      incumbent = res_cpsat.assignments
  else:
      incumbent = res_greedy.assignments

  solver_sa_half = TimeBudgetedSimulatedAnnealingSolver(
      config=config,
      time_budget_seconds=config.time_limit_seconds / 2.0,  # 1.0s budget
      seed=config.random_seed,
  )
  res_hyb, trace_hyb, iters_hyb = solver_sa_half.solve(..., initial_assignments=incumbent)
  ```
- **Reconciliation Verdict:**
  - **NO.** The scalability benchmark did **not** execute or time CP-SAT inside Hybrid.
  - When standalone CP-SAT timed out, the benchmark simply defaulted the incumbent to Greedy and executed SA with half-budget ($1.0$ s).
  - In `benchmark_report.md`, Hybrid's model construction time is listed as **$0.1$ ms** and total runtime as **$1,078.96$ ms**. If CP-SAT had actually been invoked inside Hybrid, it would have spent $190$ seconds building constraints before failing.
  - This is an **empirical concession** made in the scalability benchmark script to avoid a duplicate 3-minute freeze. It must be explicitly documented as a benchmark shortcut, not as proof that Hybrid can execute CP-SAT + SA in $1.0$ s at scale.

---

### Question E: Does CP-SAT Truly Comply with the Configured Wall-Clock Budget?

- **Authoritative Code Location:** [`src/optimization/solvers/cp_sat_solver.py#L201-L208`](file:///D:/Study/Code/Python/Aelous/src/optimization/solvers/cp_sat_solver.py#L201-L208)
- **Audited Parameters:**
  ```python
  solver.parameters.max_time_in_seconds = float(self.config.time_limit_seconds) # 2.0s
  raw_status = solver.Solve(model)
  runtime_ms = (time.perf_counter() - t0) * 1000.0
  ```
- **Reconciliation Verdict:**
  - **Partially.** The C++ search engine strictly obeyed the 2.0s ceiling (`solver_execution_ms = 2000.0 ms`).
  - **However**, total wall-clock execution was **$192,034.4$ ms ($192$ seconds)** because Python model construction took $190$ seconds.
  - Therefore, the claim that CP-SAT adheres to a $2.0$s wall-clock budget is true **only for the search phase**, but false for the solver's end-to-end invocation.

---

### Question F: Are Flight Counts in Benchmarks Flight Legs or Aircraft Turns?

- **Authoritative Code Locations:**
  - Scalability Scenario: [`src/simulation/scalability_benchmark.py#L260-L271`](file:///D:/Study/Code/Python/Aelous/src/simulation/scalability_benchmark.py#L260-L271)
  - Dual Core Fixture: [`src/evaluation/dual_core_benchmark.py#L143-L163`](file:///D:/Study/Code/Python/Aelous/src/evaluation/dual_core_benchmark.py#L143-L163)
- **Reconciliation Verdict:**
  - In the **Scalability Benchmark** ($1500 \times 50$): The 1,500 records are **inbound flight legs**, each mapped $1:1$ to a synthetic turnaround ($1,500$ flight legs $\to$ $1,500$ synthetic turns).
  - In the **Dual Core Benchmark** ([`atl_1500_flights_cpsat_turnaround_schedule.csv`](file:///D:/Study/Code/Python/Aelous/src/artifacts/predictions/atl_1500_flights_cpsat_turnaround_schedule.csv)): The file contains $1,500$ total flight legs ($750$ ARR + $750$ DEP) paired into **$851$ aircraft turns** (some legs are unpaired).
  - Documentation must clearly distinguish between **Flight Legs** and **Aircraft Turns** to prevent reader confusion.

---

### Question G: Does the `OPTIMAL` Status Signify Proven Mathematical Optimality or Self-Assignment?

- **Authoritative Analysis:**
  1. **CP-SAT Solver:** When returning `OPTIMAL`, OR-Tools CP-SAT has mathematically closed the branch-and-bound search tree, proving that no assignment exists with a strictly lower objective value ($0.0\%$ optimality gap). This is a **proven mathematical optimum**.
  2. **Simulated Annealing:** SA's returned `OPTIMAL` status is **self-assigned** by a tautological code condition ([`src/optimization/sa/annealer.py#L231`](file:///D:/Study/Code/Python/Aelous/src/optimization/sa/annealer.py#L231)). It does **not** signify proven mathematical optimality.
