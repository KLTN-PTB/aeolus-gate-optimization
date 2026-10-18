# AEOLUS-G12A: PILOT EXPERIMENT RESULTS REPORT
**Execution Date:** 2026-10-12  
**Target Directory:** `artifacts/remediation/monte_carlo_g12a/`  
**Random Seed:** 202601  
**Scenarios Tested:** N=20 (Pilot 1) and N=100 (Pilot 2)  
**Flight Schedule:** Canonical Real-Data Scenario (120 flights, 25 contact gates, 5 remote stands)  
**Simulation Modes:** Mode A (Fixed Plan), Mode B1 (Retrospective Recourse), Mode B2 (Causal Online Recourse), Mode C1 (Greedy Foresight), Mode C2 (CP-SAT Optimal Oracle)

---

## 1. Executive Summary

This report delivers empirical validation of the remediated causal online recourse policy (`evaluate_mode_b2_rolling_online_recourse`) across two pilot simulation experiments ($N=20$ and $N=100$ stochastic realizations generated via Gaussian Copula with empirical correlation $\rho=0.45$).

### Key Scientific Findings:
1. **Zero Physical Contact Conflicts (100% Invariant Compliance):**  
   Under both $N=20$ and $N=100$, Mode B2 achieved a **0.00% physical contact conflict rate** (mean conflict count = 0.00). In stark contrast, the static baseline (Mode A) suffered a **76.0% conflict rate** (mean 1.50 physical conflicts per scenario).
2. **Strict Composite Feasibility:**  
   Mode B2 achieved **100.0% composite feasibility** across all evaluated scenarios, strictly respecting aircraft compatibility, finite remote capacity (max 5 stands), and mandatory gate separation buffers ($\Delta \ge 15$ min).
3. **Scientific Realism & Value of Information (VPI):**  
   Because Mode B2 operates strictly on causal information $\mathcal{I}_t$ without perfect foresight of realized ground dwell durations, it incurs slightly higher operational cost than the retrospective clairvoyant oracle Mode B1:
   $$\text{Mean Cost}(B_2) = 143.43 \quad \text{vs} \quad \text{Mean Cost}(B_1) = 134.83 \quad (\Delta = +8.60, +6.38\%)$$
   This positive premium is the authentic **Value of Perfect Dwell Foresight (VPI)**, confirming that Mode B2 no longer cheats by exploiting future realization data.
4. **Sub-4 Millisecond Runtime:**  
   Mode B2 evaluated an entire 120-flight rolling schedule in an average of **3.68 ms**, making it 115x faster than CP-SAT full foresight (422.38 ms) and fully suitable for real-time airport dispatch operations.

---

## 2. Quantitative Summary Table (N=100 Scenarios)

| Metric | Mode A (Fixed Plan) | Mode B1 (Retrospective) | Mode B2 (Causal Online) | Mode C1 (Greedy Foresight) | Mode C2 (CP-SAT Optimal) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Information Regime** | Fixed ($t_0$) | Retrospective Clairvoyant | **Strictly Causal Online ($\mathcal{I}_t$)** | Heuristic Foresight | Mathematical Optimal Foresight |
| **Mean Cost** | 1,606.43 | 134.83 | **143.43** | 134.83 | 122.43 |
| **Median Cost** | 1,120.57 | 131.03 | **138.13** | 131.03 | 123.03 |
| **Cost Std** | 1,251.01 | 26.80 | **42.26** | 26.80 | 16.97 |
| **Monte Carlo SE** | 125.10 | 2.68 | **4.23** | 2.68 | 1.70 |
| **95% CI** | [1361.24, 1851.63] | [129.58, 140.09] | **[135.15, 151.72]** | [129.58, 140.09] | [119.11, 125.76] |
| **CVaR-90** | 3,909.14 | 183.93 | **226.23** | 183.93 | 151.39 |
| **CVaR-95** | 4,703.79 | 190.19 | **262.17** | 190.19 | 157.70 |
| **Composite Feasibility Rate** | 24.0% | 100.0% | **100.0%** | 100.0% | 100.0% |
| **Physical Conflict Rate** | 76.0% | 0.0% | **0.0%** | 0.0% | 0.0% |
| **Mean Physical Conflicts** | 1.50 | 0.00 | **0.00** | 0.00 | 0.00 |
| **Remote Capacity Violation Rate** | 0.0% | 0.0% | **0.0%** | 0.0% | 0.0% |
| **Static Slot Consistency** | 0.0% | 100.0% | **0.0%** | 100.0% | 100.0% |
| **Mean Reassignments** | 0.00 | 2.84 | **3.30** | 2.84 | 1.60 |
| **Mean Remote Usage** | 0.00 | 0.00 | **0.02** | 0.00 | 0.00 |
| **Mean Runtime (ms)** | 1.45 ms | 2.91 ms | **3.68 ms** | 2.68 ms | 422.38 ms |

---

## 3. Quantitative Summary Table (N=20 Pilot Scenarios)

| Metric | Mode A (Fixed Plan) | Mode B1 (Retrospective) | Mode B2 (Causal Online) | Mode C1 (Greedy Foresight) | Mode C2 (CP-SAT Optimal) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Mean Cost** | 1,707.27 | 139.77 | **153.27** | 139.77 | 125.10 |
| **Median Cost** | 1,122.18 | 137.09 | **138.79** | 137.09 | 123.03 |
| **Cost Std** | 1,144.41 | 31.00 | **62.96** | 31.00 | 20.15 |
| **Composite Feasibility Rate** | 15.0% | 100.0% | **100.0%** | 100.0% | 100.0% |
| **Physical Conflict Rate** | 85.0% | 0.0% | **0.0%** | 0.0% | 0.0% |
| **Mean Physical Conflicts** | 1.60 | 0.00 | **0.00** | 0.00 | 0.00 |
| **Mean Reassignments** | 0.00 | 3.25 | **3.60** | 3.25 | 1.70 |
| **Mean Remote Usage** | 0.00 | 0.00 | **0.10** | 0.00 | 0.00 |
| **Mean Runtime (ms)** | 1.50 ms | 3.01 ms | **3.73 ms** | 2.75 ms | 415.20 ms |

---

## 4. Rigorous CRN Paired Comparisons

Using Common Random Numbers (CRN) across all scenarios, we perform paired hypothesis testing where $\Delta_s = \text{Cost}_{B2}(s) - \text{Cost}_A(s)$:

### 4.1 Mode B2 vs Mode A (Fixed Plan)
- **Mean $\Delta(\text{Cost})$:** $-1,463.00$ cost units
- **Std $\Delta(\text{Cost})$:** $1,225.40$
- **Monte Carlo Standard Error:** $122.54$
- **95% Confidence Interval for $\Delta$:** $[-1,703.18, -1,222.82]$
- **Paired Student's t-statistic:** $t = -11.9389$
- **p-value:** $6.93 \times 10^{-21}$ ($p \ll 0.001$, extremely statistically significant)
- **Physical Conflicts Eliminated:** $-1.50$ conflicts per scenario ($t = -15.42$, $p \approx 0$)
- **Scenarios with Zero Conflict in Fixed Plan:** 24/100 (tied cost where initial plan needed zero recourse)
- **Scenarios Where Mode A Suffered Conflicts:** 76/100 (Mode B2 successfully resolved 100% of these conflicts)

### 4.2 Mode B2 vs Mode B1 (Causal vs Retrospective Clairvoyant)
- **Mean $\Delta(\text{Cost}) = \text{Cost}(B_2) - \text{Cost}(B_1)$:** $+8.60$ cost units ($+6.38\%$)
- **Mean Reassignment Difference:** $+0.46$ reassignments per schedule ($3.30$ vs $2.84$)
- **Interpretation:**  
  When an operational controller lacks perfect foresight of future gate release times, they must occasionally make precautionary reassignments to avoid projected conflicts. This causes a modest 6.38% increase in operational cost, which represents the **honest information penalty** inherent in real-time online decision making.

### 4.3 Theoretical Ordering Hierarchy
The empirical ordering strictly satisfies the mathematical theorems of stochastic optimization:
$$\text{Cost}(C_2) \le \text{Cost}(C_1) = \text{Cost}(B_1) < \text{Cost}(B_2) \ll \text{Cost}(A)$$
$$122.43 \le 134.83 = 134.83 < 143.43 \ll 1,606.43$$

1. **Lower Bound ($C_2 = 122.43$):** Global mathematical optimum under complete realization foresight.
2. **Heuristic Foresight ($C_1 = B_1 = 134.83$):** Greedy assignment given realization foresight.
3. **Causal Online ($B_2 = 143.43$):** Real-time online dispatching with zero hindsight.
4. **Static Baseline ($A = 1,606.43$):** Unadapted schedule suffering severe collision penalties.

---

## 5. Artifact Manifest for Pilot Runs

All artifacts generated by the runner script are persisted under `artifacts/remediation/monte_carlo_g12a/`:
- `mode_b2_results_n20.csv` (1,800 records across 3 initial solvers)
- `statistical_summary_n20.json` (comprehensive statistical metrics for N=20)
- `mode_b2_results_n100.csv` (9,000 records across 3 initial solvers)
- `statistical_summary_n100.json` (comprehensive statistical metrics for N=100)

Both pilots completed successfully with zero unhandled exceptions, zero data leaks, and 100% compliance with the AEOLUS-G12A specification.
