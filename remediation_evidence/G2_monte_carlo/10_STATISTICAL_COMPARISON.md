# AEOLUS-G2 — DELIVERABLE 10: STATISTICAL COMPARISON

## 1. Overall Simulation Setup

- **Benchmark Scenario:** `SCEN_P09_CANONICAL_120` (120 flights, 25 contact gates, 5 remote stands)
- **Sample Size:** $N = 100$ independent realizations (aligned via Common Random Numbers)
- **Delay Generation Model:** Gaussian Copula ($\rho = 0.45$) with Student-t marginals
- **Seed:** $202601$

## 2. Cross-Mode Distributional Statistics

| Operational Mode | Information Regime | Mean Cost | Median Cost | Std Dev | MC SE | 95% CI | CVaR-90 | CVaR-95 | Physical Conflict Rate | Mean Reassignments |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Mode A (Fixed Plan)** | Pre-Operational | 1,606.43 | 1,120.57 | 1,251.01 | 125.10 | [1361.24, 1851.63] | 3,909.14 | 4,703.79 | **76.0%** | 0.00 |
| **Mode B1 (Retrospective)** | Retrospective | 134.83 | 131.03 | 26.80 | 2.68 | [129.58, 140.09] | 183.93 | 190.19 | **0.0%** | 2.84 |
| **Mode B2 (Online Recourse)** | Online Recourse | 147.43 | 146.72 | 35.73 | 3.57 | [140.43, 154.44] | 210.34 | 222.53 | **0.0%** | 4.10 |
| **Mode C1 (Greedy Foresight)** | Full Foresight | 134.83 | 131.03 | 26.80 | 2.68 | [129.58, 140.09] | 183.93 | 190.19 | **0.0%** | 2.84 |
| **Mode C2 (CP-SAT Oracle)** | Full Foresight | 122.43 | 123.03 | 16.97 | 1.70 | [119.11, 125.76] | 151.39 | 157.70 | **0.0%** | 1.60 |

### Cost Quantiles Breakdown

| Operational Mode | P10 | P25 | P50 (Median) | P75 | P90 | P95 | P99 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Mode A (Fixed Plan)** | 105.04 | 1,090.73 | 1,120.57 | 2,114.77 | 3,109.75 | 3,165.08 | 5,116.86 |
| **Mode B1 (Retrospective)** | 103.60 | 115.16 | 131.03 | 155.30 | 172.62 | 184.19 | 192.83 |
| **Mode B2 (Online Recourse)** | 103.60 | 117.33 | 146.72 | 172.05 | 191.68 | 203.28 | 232.82 |
| **Mode C1 (Greedy Foresight)**| 103.60 | 115.16 | 131.03 | 155.30 | 172.62 | 184.19 | 192.83 |
| **Mode C2 (CP-SAT Oracle)** | 100.95 | 110.55 | 123.03 | 133.60 | 144.18 | 145.84 | 162.83 |

## 3. Paired Common Random Numbers (CRN) Statistical Tests

Every scenario realization $s$ evaluated in Mode $A$ and Mode $B$ used identical stochastic delays $\omega_s$. The paired differences $\Delta_s = \text{Cost}_A(s) - \text{Cost}_B(s)$ are evaluated below:

| Hypothesis / Comparison | Mean Delta $\bar{\Delta}$ | Std Dev $s_{\Delta}$ | MC SE | 95% Confidence Interval | t-statistic | p-value | Significance | Improved % | Worsened % | Tied % |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Mode A vs Mode B2 (Online)** | +1,459.00 | 1,222.34 | 122.23 | [+1,219.42, +1,698.58] | +11.936 | $7.03 \times 10^{-21}$ | **YES ($p < 0.001$)** | 76.0% | 0.0% | 24.0% |
| **Mode B1 (Retro) vs Mode B2 (Online)** | -12.60 | 19.42 | 1.94 | [-16.41, -8.79] | -6.489 | $3.44 \times 10^{-9}$ | **YES ($p < 0.001$)** | 11.0% | 52.0% | 37.0% |
| **Mode C1 (Greedy) vs Mode C2 (CP-SAT)**| +12.40 | 13.79 | 1.38 | [+9.70, +15.10] | +8.993 | $1.72 \times 10^{-14}$ | **YES ($p < 0.001$)** | 57.0% | 0.0% | 43.0% |
| **Mode B2 (Online) vs Mode C2 (Oracle)**| +25.00 | 23.85 | 2.38 | [+20.33, +29.67] | +10.483 | $9.67 \times 10^{-18}$ | **YES ($p < 0.001$)** | 69.0% | 0.0% | 31.0% |

## 4. Key Scientific Insights

1. **The Massive Value of Operational Recourse (Mode A vs Mode B2):**
   - Without recourse, fixed plans incur severe contact conflict penalties in 76.0% of days, yielding a mean cost of 1,606.43.
   - Real-time online recourse (Mode B2) eliminates **100%** of contact conflicts by dynamically reassigning an average of 4.10 flights per day, reducing mean cost to 147.43 (saving 1,459.00 points, $p = 7.03 \times 10^{-21}$).
   - In 24.0% of days where no conflict occurred, Mode B2 performed zero reassignments and tied Mode A perfectly. In 0.0% of days was Mode B2 worse than Mode A.

2. **The Price of Online Uncertainty / Value of Information (Mode B2 vs Mode B1):**
   - Retrospective recourse achieves a mean cost of 134.83, whereas online recourse achieves 147.43.
   - The difference of $-12.60$ cost points ($p = 3.44 \times 10^{-9}$) quantifies the **Expected Value of Perfect Information (EVPI)** in real-time gate management.
   - In 52.0% of scenarios, retrospective clairvoyance found a more optimal gate reassignment than myopic real-time online dispatching.

3. **Sub-Optimality of Greedy Foresight (Mode C1 vs Mode C2):**
   - CP-SAT optimal foresight achieves a mean cost of 122.43 (1.60 reassignments) compared to Greedy's 134.83 (2.84 reassignments).
   - CP-SAT strictly improved upon Greedy foresight in 57.0% of scenarios ($p = 1.72 \times 10^{-14}$) and was never worse (0.0% worsened).
   - This decisively proves that the legacy P09 claim of Greedy being an "Oracle Lower Bound" was scientifically incorrect. CP-SAT establishes the true global mathematical lower bound.
