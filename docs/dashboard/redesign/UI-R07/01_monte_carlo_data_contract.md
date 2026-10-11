# AEOLUS DASHBOARD — UI-R07 MONTE CARLO DATA CONTRACT
**Artifact Path**: `artifacts/remediation/monte_carlo/`  
**Phase**: UI-R07 v2.0  
**Authors**: Principal Monte Carlo Simulation Scientist & Statistical Computing Engineer  

---

## 1. Executive Summary & File Inventory

Phase P09 evaluated gate assignment robustness against stochastic flight delay disturbances at Atlanta Hartsfield-Jackson International Airport (ATL). All Monte Carlo artifacts are frozen, unmutated, and verified by SHA-256 hashes:

| Relative File Path | Format | Records | Content & Purpose |
| :--- | :---: | :---: | :--- |
| `artifacts/remediation/monte_carlo/simulation_manifest.json` | JSON | 1 manifest | Simulation parameters: seed (202601), copula ($\rho=0.45$), Student-t marginals. |
| `artifacts/remediation/monte_carlo/fixed_plan_results.csv` | CSV | 1,500 rows | Mode A: Fixed Plan evaluations across 3 solvers × 500 realizations. |
| `artifacts/remediation/monte_carlo/recourse_results.csv` | CSV | 1,500 rows | Mode B: Reactive Recourse evaluations across 3 solvers × 500 realizations. |
| `artifacts/remediation/monte_carlo/oracle_results.csv` | CSV | 500 rows | Mode C: Greedy Perfect-Foresight Reference evaluations across 500 realizations. |
| `artifacts/remediation/monte_carlo/paired_comparison.csv` | CSV | 6 records | Precomputed paired differences between modes and solvers. |
| `artifacts/remediation/monte_carlo/statistical_summary.json` | JSON | 307 lines | Aggregated descriptive metrics, tail percentiles, CVaR90/95, MCSE. |
| `artifacts/remediation/monte_carlo/failures.json` | JSON | 8 lines | Accounting audit: 3,500 requested, 3,500 evaluated, 0 failures. |
| `artifacts/remediation/monte_carlo/scenario_index.csv` | CSV | 500 rows | Scenario metadata: mean/max arrival & departure delays, realization hashes. |

---

## 2. Observation Identity Tuple

Each evaluation record in the Monte Carlo dataset is uniquely identified by the 4-tuple:
$$\text{Observation ID} = (\text{experiment\_id}, \text{mode}, \text{solver\_name}, \text{realization\_id})$$

### Crucial Scientific Invariant: Scenarios vs Evaluations
- **500 Stochastic Scenarios**: Exactly 500 distinct flight delay perturbation vectors (`MC500_S0000` to `MC500_S0499`) sampled using a Gaussian Copula ($\rho=0.45$) and Student-t marginals ($df=4.5$ arrival, $df=4.0$ departure).
- **3 Solver Variants**: `CPSat`, `Greedy`, `Hybrid`.
- **1,500 Mode A Evaluations**: $500 \text{ scenarios} \times 3 \text{ solvers} = 1,500$ rows in `fixed_plan_results.csv`.
- **1,500 Mode B Evaluations**: $500 \text{ scenarios} \times 3 \text{ solvers} = 1,500$ rows in `recourse_results.csv`.
- **500 Mode C Evaluations**: $500 \text{ scenarios} \times 1 \text{ solver (Oracle\_Greedy)} = 500$ rows in `oracle_results.csv`.
- **Total Pipeline Runs**: 3,500 evaluations ($1500 + 1500 + 500$), recorded in `failures.json` with 0 failures.

> [!IMPORTANT]
> The dashboard strictly prohibits describing the 1,500 evaluation rows as "1,500 independent scenarios". It must always clearly declare: **500 independent stochastic scenarios evaluated across 3 baseline solvers**.

---

## 3. Schema Specification for Scenario CSVs

Each row in `fixed_plan_results.csv`, `recourse_results.csv`, and `oracle_results.csv` satisfies:

| Column Name | Type | Description | Scientific Invariant |
| :--- | :---: | :--- | :--- |
| `realization_id` | `str` | Scenario ID (`MC500_S0000` .. `MC500_S0499`) | Primary key for CRN pairing. |
| `scenario_index` | `int` | Integer index $[0, 499]$ | Matches `scenario_index.csv`. |
| `solver_name` | `str` | Nominal solver (`Greedy`, `CPSat`, `Hybrid`) | Must be filtered homogeneously per chart. |
| `mode` | `str` | Simulation protocol | `FIXED_PLAN_ROBUSTNESS`, `REACTIVE_RECOURSE`, `PERFECT_FORESIGHT_ORACLE`. |
| `feasible` | `bool` | Independent hard-constraint verification | Strictly `False` in Mode A (0%), strictly `True` in Mode B & C (100%). |
| `objective_value` | `float` | Evaluated objective cost in points | Finite positive float. Never 0.0 or fabricated. |
| `conflict_count` | `int` | Number of simultaneous contact-gate overlaps | $>0$ in 74.8% of Mode A; exactly 0 in Mode B & C. |
| `remote_count` | `int` | Number of flights assigned to remote stands | Evaluated per scenario. |
| `unassigned_count` | `int` | Number of unassigned flights | Exactly 0 across all 3,500 evaluations. |
| `reassignment_count`| `int` | Gate changes relative to initial plan | 0 in Mode A; mean 2.56 in Mode B. |
| `max_concurrent_remote`| `int` | Peak concurrent remote stand occupancy | Must be $\le 5$ (finite remote capacity). |
| `remote_capacity_violation`| `bool` | Flag if remote peak exceeds capacity (5) | False across all scenarios. |
| `runtime_ms` | `float` | Wall-clock execution time (ms) | Finite positive float. |
| `realization_hash`| `str` | SHA-256 fingerprint of realized delays | Immutable audit verification token. |
