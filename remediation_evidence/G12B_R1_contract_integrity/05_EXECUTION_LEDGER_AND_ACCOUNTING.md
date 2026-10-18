# AEOLUS-G12B-R1: Simulation Execution Accounting Ledger & Invariant Verification Audit

## 1. Scientific Motivation & Problem Statement

In Monte Carlo simulations and comparative algorithm benchmarking:
1. **Silent Drops Hazard**: Realizations that encounter timeout or numerical instability may be dropped silently from dataframes, resulting in biased sample estimates (survival bias).
2. **Ambiguous Denominators**: Stating a "failure rate of 2%" without specifying whether the denominator is $N_{\text{requested}}$, $N_{\text{generated}}$, or $N_{\text{evaluated}}$ creates statistical ambiguity.
3. **Common Random Numbers (CRN) Alignment**: In paired comparisons (e.g., comparing Greedy vs CP-SAT vs Hybrid), each solver must be evaluated on bit-for-bit identical stochastic realizations.

To eliminate these risks before embarking on 500-scenario Monte Carlo evaluations, G12B-R1 implements an immutable audit accounting ledger: `SimulationExecutionLedger`.

---

## 2. Ledger Architecture & Data Model

### 2.1 `ExecutionLedgerEntry` Schema
```python
@dataclass
class ExecutionLedgerEntry:
    run_id: str
    scenario_id: str
    realization_hash: str
    initial_plan_solver: str
    recourse_mode: str
    generation_status: str     # "SUCCESS", "FAILURE"
    evaluation_status: str     # "SUCCESS", "FAILURE", "TIMEOUT", "NOT_EVALUATED"
    solver_status: str
    composite_feasible: bool
    timeout: bool
    exception_type: str | None = None
    failure_reason: str | None = None
    objective_value: float | None = None
    runtime_ms: float = 0.0
    timestamp_start: float = 0.0
    timestamp_end: float = 0.0
    source_config_hash: str = ""
```

### 2.2 Mathematical Accounting Invariants
The ledger enforces three strict conservation laws:
$$n_{\text{requested}} = n_{\text{generated}} + n_{\text{generation\_failures}}$$
$$n_{\text{generated}} = n_{\text{evaluated}} + n_{\text{evaluation\_failures}}$$
$$n_{\text{evaluated}} = n_{\text{feasible}} + n_{\text{infeasible}}$$

### 2.3 Explicit Denominator Formulation
All rates computed by `SimulationExecutionLedger.compute_rates()` explicitly state their numerator and denominator:
$$\text{Generation Failure Rate} = \frac{n_{\text{generation\_failures}}}{n_{\text{requested}}}$$
$$\text{Evaluation Failure Rate} = \frac{n_{\text{evaluation\_failures}}}{n_{\text{generated}}}$$
$$\text{Composite Feasible Rate} = \frac{n_{\text{feasible}}}{n_{\text{evaluated}}}$$

### 2.4 Paired CRN Invariant Validation
The method `validate_paired_crn(required_solvers)` verifies:
$$\forall s \in \mathcal{S}, \quad \text{hash}(s, \text{Greedy}) = \text{hash}(s, \text{CP-SAT}) = \text{hash}(s, \text{Hybrid})$$
If any solver is omitted or if scenario realizations diverge across solvers, a `ValueError` is raised immediately, halting downstream statistical aggregation.

---

## 3. Empirical Test Verification

The test suite `tests/test_g12b_r1_contract_integrity.py` validates all 9 ledger invariants:

| Test ID | Accounting Invariant Tested | Verification Condition | Result |
| :--- | :--- | :--- | :--- |
| **STAT-LEDGER-01** | Conservation laws | $N=100$ requested, 98 evaluated, 2 gen failures | **PASS** |
| **STAT-LEDGER-02** | Omission detection | 100 requested, only 99 recorded without explicit failure record | Raises `ValueError` (**PASS**) |
| **STAT-LEDGER-03** | Timeout accounting | Solver wall-clock timeout treated as evaluated failure | **PASS** |
| **STAT-LEDGER-04** | Feasible vs Infeasible vs Failure | Infeasible optimization vs execution exception distinguished | **PASS** |
| **STAT-LEDGER-05** | Duplicate prevention | Inserting same `(scenario_id, solver)` twice | Raises `ValueError` (**PASS**) |
| **STAT-LEDGER-06** | Paired CRN tracking | Solvers Greedy, CP-SAT, Hybrid on same realization | Bit-exact hashes verified (**PASS**) |
| **STAT-LEDGER-07** | Mismatched CRN detection | Altered realization hash across solvers | Raises `ValueError` (**PASS**) |
| **STAT-LEDGER-08** | Pilot replay | Full replay of $N=20$ and $N=100$ pilot execution records | Complete conservation (**PASS**) |
| **STAT-LEDGER-09** | Explicit rate denominators | Rates computed with verifiable numerators and denominators | Exact mathematical parity (**PASS**) |

All 9 tests pass with zero tolerance for missing scenarios or silent drops.
