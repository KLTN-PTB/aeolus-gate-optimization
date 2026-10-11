# AEOLUS DASHBOARD — STATISTICAL METRICS & TAIL RISK VALIDATION
**Phase**: UI-R07 v2.0  
**Implementation**: `dashboard/adapters/monte_carlo_adapter.py`  

---

## 1. Statistical Estimators Specification

All statistical metrics rendered on Page 05 and exported to research tables follow standard Monte Carlo estimation theory:

### A. Central Tendency & Sample Variance
$$\text{Mean: } \hat{\mu} = \frac{1}{n} \sum_{i=1}^n x_i$$
$$\text{Median: } \hat{P}_{50} = \text{percentile}(X, 50)$$
$$\text{Sample Standard Deviation: } s = \sqrt{\frac{1}{n-1} \sum_{i=1}^n (x_i - \hat{\mu})^2} \quad (\text{Bessel-corrected, } ddof=1)$$

### B. Monte Carlo Standard Error (MCSE) & Confidence Interval
$$\text{MCSE} = \frac{s}{\sqrt{n}}$$
$$\text{95% Confidence Interval} = \left[ \hat{\mu} - 1.96 \cdot \text{MCSE}, \quad \hat{\mu} + 1.96 \cdot \text{MCSE} \right]$$

### C. Tail Quantiles & Upper-Tail Conditional Value at Risk (CVaR)
For cost variables where higher values represent unfavorable operational disruptions:
$$\text{VaR}_\alpha = P_\alpha = \text{percentile}(X, 100 \cdot \alpha)$$
$$\text{CVaR}_\alpha = \mathbb{E}\left[ X \mid X \ge \text{VaR}_\alpha \right] = \frac{1}{| \{i : x_i \ge P_\alpha\} |} \sum_{i : x_i \ge P_\alpha} x_i$$

> [!IMPORTANT]
> **CVaR is NOT equal to P95!**
> For any non-degenerate cost distribution, $\text{CVaR}_{95} \ge P_{95}$.
> In our empirical Mode A distribution: $P_{95} = 3125.41\text{ pts}$ while $\text{CVaR}_{95} = 4388.35\text{ pts}$.
> Confusing or substituting $P_{95}$ for $\text{CVaR}_{95}$ is prohibited.

---

## 2. Common Random Numbers (CRN) Paired Hypothesis Testing

To evaluate the true value of tactical recourse ($\Delta \text{Cost} = X_{\text{Mode A}} - X_{\text{Mode B}}$), evaluations must be matched by scenario key:

### Invariant: Key-Based Inner Join
```python
# Inner join strictly by scenario identifier key
merged = pd.merge(
    df_a[[id_col, "objective_value"]],
    df_b[[id_col, "objective_value"]],
    on=id_col,
    suffixes=("_a", "_b"),
)
deltas = (merged["objective_value_a"] - merged["objective_value_b"]).values
```

### Paired Statistics
$$\bar{\Delta} = \frac{1}{n} \sum_{i=1}^n \Delta_i = +1338.44\text{ pts}$$
$$s_\Delta = \sqrt{\frac{1}{n-1} \sum_{i=1}^n (\Delta_i - \bar{\Delta})^2} = 1141.47\text{ pts}$$
$$\text{MCSE}_\Delta = \frac{s_\Delta}{\sqrt{n}} = 51.05\text{ pts}$$
$$t\text{-statistic} = \frac{\bar{\Delta}}{\text{MCSE}_\Delta} = 26.22 \quad \implies \quad p\text{-value} = 6.63 \times 10^{-96} \quad (\text{Significance: } p < 0.001)$$
