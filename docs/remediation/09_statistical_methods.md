# Statistical Methodology & Mathematical Inference (Phase P09)

**Document ID**: `P09-STAT-METHODS`  
**Protocol Version**: `v4.0-P09`  
**Authoritative Scope**: Mathematical Formulations, Monte Carlo Error Bounds, Tail Risk Estimation, and Hypothesis Testing  

---

## 1. Overview & Mathematical Foundations

Monte Carlo simulation evaluates the expected performance of gate assignment policies over a stochastic probability space $(\Omega, \mathcal{F}, \mathbb{P})$. In airport gate scheduling, the objective metric $Y = f(x, \omega)$ is a random variable representing operational decision cost or constraint violations under stochastic delay realization $\omega \in \Omega$.

This document establishes the exact mathematical formulations used to estimate expectations, uncertainty intervals, tail risk, and paired statistical superiority across the 500 Monte Carlo realizations.

---

## 2. Point Estimation & Monte Carlo Uncertainty Bounds

Let $Y_1, Y_2, \dots, Y_N$ denote $N = 500$ independent and identically distributed realizations of the evaluation metric for a specified solver and simulation mode.

### 2.1 Sample Mean & Variance
The sample mean $\bar{Y}$ is the unbiased point estimator of the expected operational cost $\mathbb{E}[Y]$:

$$\bar{Y} = \frac{1}{N} \sum_{s=1}^N Y_s$$

The sample variance $s^2$ is computed using Bessel's correction with $N - 1$ degrees of freedom (`ddof=1`):

$$s^2 = \frac{1}{N - 1} \sum_{s=1}^N (Y_s - \bar{Y})^2$$

The sample standard deviation is $s = \sqrt{s^2}$.

### 2.2 Monte Carlo Standard Error (MCSE)
By the Central Limit Theorem, the distribution of the sample mean $\bar{Y}$ converges asymptotically to $\mathcal{N}\left(\mathbb{E}[Y], \frac{\sigma^2}{N}\right)$. The Monte Carlo Standard Error (MCSE) measures the sampling uncertainty of the simulation:

$$\text{MCSE}(\bar{Y}) = \frac{s}{\sqrt{N}}$$

For $N = 500$ scenarios:
$$\text{MCSE} = \frac{s}{\sqrt{500}} \approx \frac{s}{22.3607}$$

### 2.3 95% Confidence Intervals
Under asymptotic normality, the two-sided 95% confidence interval for the true expected cost $\mathbb{E}[Y]$ is given by:

$$\text{CI}_{0.95} = \left[ \bar{Y} - z_{1 - \alpha/2} \cdot \text{MCSE}, \; \bar{Y} + z_{1 - \alpha/2} \cdot \text{MCSE} \right]$$

where $z_{0.975} \approx 1.960$.

In Phase P09 empirical results:
- **Mode A (Fixed Plan)**: $\bar{Y} = 1469.17$, $\text{MCSE} = 51.96 \implies \text{CI}_{0.95} = [1367.32, \; 1571.02]$
- **Mode B (Reactive Recourse)**: $\bar{Y} = 130.73$, $\text{MCSE} = 1.13 \implies \text{CI}_{0.95} = [128.51, \; 132.95]$

---

## 3. Tail Risk Metrics (Quantiles & CVaR)

Aviation gate scheduling is highly asymmetric: dispatchers are concerned not only with average delay costs, but especially with extreme disruption scenarios (irregular operations / IROPS).

### 3.1 Empirical Quantiles & Value-at-Risk (VaR)
For a confidence level $\alpha \in (0, 1)$, the Value-at-Risk $\text{VaR}_\alpha$ represents the $(100 \cdot \alpha)$-th percentile of the cost distribution:

$$\text{VaR}_\alpha(Y) = q_\alpha = \inf \{ y \in \mathbb{R} : F_Y(y) \ge \alpha \}$$

Phase P09 evaluates quantiles at $\alpha \in \{0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99\}$, with monotonic ordering guaranteed:
$$p_{10} \le p_{25} \le p_{50} \le p_{75} \le p_{90} \le p_{95} \le p_{99}$$

### 3.2 Conditional Value-at-Risk (CVaR / Expected Shortfall)
While VaR identifies the threshold cost, Conditional Value-at-Risk ($\text{CVaR}_\alpha$) quantifies the **expected loss given that the loss exceeds $\text{VaR}_\alpha$**:

$$\text{CVaR}_\alpha(Y) = \mathbb{E}\left[ Y \mid Y \ge \text{VaR}_\alpha(Y) \right]$$

Empirically, for sample realizations $Y_1, \dots, Y_N$:

$$\widehat{\text{CVaR}}_\alpha = \frac{\sum_{s=1}^N Y_s \cdot \mathbf{1}_{\{Y_s \ge q_\alpha\}}}{\sum_{s=1}^N \mathbf{1}_{\{Y_s \ge q_\alpha\}}}$$

**Tail Risk Comparison (Phase P09)**:
| Simulation Mode | Median ($p_{50}$) | 90th Pct ($p_{90}$) | 95th Pct ($p_{95}$) | CVaR-90 | CVaR-95 |
|---|---|---|---|---|---|
| **Mode A (Fixed Plan)** | 1,109.96 | 3,106.27 | 3,125.41 | 3,751.65 | 4,388.35 |
| **Mode B (Recourse)** | 126.29 | 163.48 | 177.37 | 182.45 | 195.56 |

*Finding*: Mode A suffers from severe tail risk ($\text{CVaR}_{95} = 4,388.35$) due to compounding gate overlap penalties. Mode B bounds tail risk to $\text{CVaR}_{95} = 195.56$, demonstrating strong operational resilience under extreme disruption.

---

## 4. Paired Hypothesis Testing & Effect Size

Comparing two dispatch strategies $A$ and $B$ evaluated on independent realizations would introduce excess variance. Phase P09 enforces **Common Random Numbers (CRN)**: both strategies are evaluated on the exact same 500 scenario realizations.

### 4.1 Paired Differences
For each scenario $s \in \{1, \dots, N\}$, the paired cost delta is:

$$d_s = Y_A(s) - Y_B(s)$$

The sample mean difference $\bar{d}$ and sample variance $s_d^2$ are:

$$\bar{d} = \frac{1}{N} \sum_{s=1}^N d_s, \qquad s_d^2 = \frac{1}{N - 1} \sum_{s=1}^N (d_s - \bar{d})^2$$

The paired standard error is:

$$\text{SE}(\bar{d}) = \frac{s_d}{\sqrt{N}}$$

### 4.2 Paired Student's t-Test
The null and alternative hypotheses are:
- $H_0: \mathbb{E}[d] = 0$ (no significant performance difference between strategies)
- $H_1: \mathbb{E}[d] \neq 0$ (statistically significant performance difference)

The test statistic follows Student's t-distribution with $N - 1 = 499$ degrees of freedom:

$$t = \frac{\bar{d}}{\text{SE}(\bar{d})} = \frac{\bar{d} \sqrt{N}}{s_d}$$

The two-tailed p-value is:
$$p = 2 \cdot \left(1 - F_{t, 499}(|t|)\right)$$

### 4.3 Degenerate & Zero-Variance Cases
When comparing identical solutions or solvers with identical outputs (e.g. Greedy vs CP-SAT initial plans), $d_s = 0$ for all $s$. In this degenerate case:
$$s_d = 0, \quad \text{SE}(\bar{d}) = 0, \quad t = 0.0, \quad p = 1.0$$
The implementation handles this boundary condition safely without zero division.

**Mode A vs Mode B Empirical Test Results**:
$$\bar{d} = +1,338.44, \quad s_d = 1,141.47, \quad \text{SE}(\bar{d}) = 51.05$$
$$t = \frac{1,338.44}{51.05} = 26.2193, \quad p = 6.63 \times 10^{-96} < 0.001$$
The rejection of $H_0$ is definitive: online recourse provides a statistically incontrovertible benefit over fixed execution.

---

## 5. Copula Dependence & Joint Distribution Sampling

### 5.1 Gaussian Copula Model
Let $U_{\text{arr}}, U_{\text{dep}} \sim \mathcal{U}(0, 1)$ denote the marginal quantiles of arrival and departure delays. Sklar's Theorem states that the joint distribution can be uniquely represented by a copula $C$:

$$F(x_{\text{arr}}, x_{\text{dep}}) = C(F_{\text{arr}}(x_{\text{arr}}), F_{\text{dep}}(x_{\text{dep}}))$$

Using a Gaussian Copula with correlation matrix $\Sigma$:

$$C_\Sigma(u_1, u_2) = \Phi_\Sigma\left( \Phi^{-1}(u_1), \Phi^{-1}(u_2) \right)$$

where $\Phi$ is the standard normal cumulative distribution function and $\Phi_\Sigma$ is the bivariate normal CDF with covariance $\Sigma = \begin{pmatrix} 1 & \rho \\ \rho & 1 \end{pmatrix}$.

### 5.2 Positive-Definiteness Certification
For any correlation $\rho \in (-1, 1)$, the eigenvalues of $\Sigma$ are:

$$\lambda_1 = 1 - \rho, \qquad \lambda_2 = 1 + \rho$$

At the calibrated parameter $\rho = 0.45$:
$$\lambda_1 = 0.55 > 0, \qquad \lambda_2 = 1.45 > 0$$
Because all eigenvalues are strictly positive, $\Sigma$ is symmetric positive-definite (SPD). Cholesky decomposition $\Sigma = L L^T$ is well-conditioned with condition number $\kappa = \frac{1.45}{0.55} \approx 2.64$.

### 5.3 Quantile Inversion Procedure
To sample a realization for flight $i$ in scenario $s$:
1. Sample bivariate standard normal $(Z_{\text{arr}}, Z_{\text{dep}}) \sim \mathcal{N}_2(0, \Sigma)$.
2. Transform to uniform marginal quantiles: $U_{\text{arr}} = \Phi(Z_{\text{arr}})$, $U_{\text{dep}} = \Phi(Z_{\text{dep}})$.
3. Clip strictly to $[\epsilon, 1 - \epsilon]$ with $\epsilon = 10^{-4}$ to prevent infinite quantile evaluations.
4. Evaluate parametric Student-t percent point functions (PPF):
   $$\Delta T_{\text{arr}} = F_{t, \nu_{\text{arr}}}^{-1}(U_{\text{arr}} \mid \mu_{\text{arr}}, \sigma_{\text{arr}})$$
   $$\Delta T_{\text{dep}} = F_{t, \nu_{\text{dep}}}^{-1}(U_{\text{dep}} \mid \mu_{\text{dep}}, \sigma_{\text{dep}})$$
5. Apply the physical minimum turnaround filter:
   $$\Delta T_{\text{dep}} \leftarrow \max\left(\Delta T_{\text{dep}}, A_{\text{sched}} + \Delta T_{\text{arr}} + 45 - D_{\text{sched}}\right)$$
