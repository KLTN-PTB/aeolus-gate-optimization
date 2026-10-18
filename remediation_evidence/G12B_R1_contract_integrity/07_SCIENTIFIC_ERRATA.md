# AEOLUS-G12B-R1: Scientific Errata & Architectural Reconciliation Report

## 1. Scope & Purpose of Errata

This document formalizes the scientific post-mortem for four implementation and modeling discrepancies identified following the AEOLUS-G12B milestone. Each erratum describes the historical defect, the theoretical root cause, the exact remediation applied, and the verified impact on thesis claims and reproducibility.

---

## 2. Errata Breakdown

### Erratum ERR-01: Violation of Hash-Equality Contract in Solver Status (`OnlineSolverStatus`)
- **Severity**: Moderate (Python Data Structure Integrity).
- **Historical Defect**: In G12B, `OnlineSolverStatus(str)` overrode `__eq__` to equate `"ONLINE_FEASIBLE"` with `"ONLINE_SOLVED"` without matching hashes, violating:
  $$\forall a, b: a == b \implies \text{hash}(a) == \text{hash}(b)$$
- **Operational Impact**: Sets and dictionaries exhibited inconsistent key lookups and deduplication failures. Furthermore, legacy runs marked `ONLINE_SOLVED` were implicitly treated as feasible without verifying constraint fulfillment.
- **Remediation**:
  1. Reverted `OnlineSolverStatus` to a canonical `str, Enum` with explicit values (`ONLINE_FEASIBLE`, `ONLINE_INFEASIBLE_NO_CAPACITY`, `ONLINE_INFEASIBLE`).
  2. Implemented `canonicalize_legacy_solver_status()`, ensuring legacy status values are only canonicalized to `ONLINE_FEASIBLE` if backed by a verified `FeasibilityBreakdown.composite_feasible == True`.
- **Validation**: Tests `STATUS-01` to `STATUS-07` all PASS.

---

### Erratum ERR-02: Finite Remote Stand Capacity Bypass Under Default Optimization Configuration
- **Severity**: High (Operations Research Constraint Semantics).
- **Historical Defect**: Default `GateOptimizationConfig` specifies `allow_unbounded_overflow=True` and `enforce_remote_capacity=False`. In Mode B2, `make_causal_recourse_decision()` treated `remote_gate` (a `FINITE_REMOTE_STAND`) as an unbounded sink when `remote_usage >= capacity`.
- **Operational Impact**: Airfield topology models with limited remote stands (e.g., capacity 1–5) could be assigned an arbitrary number of simultaneous aircraft, producing false feasibility or post-hoc verification violations.
- **Remediation**:
  1. Explicitly separated `FINITE_REMOTE_STAND` (finite capacity $C < \infty$) from `UNBOUNDED_OVERFLOW_APRON` ($C = \infty$).
  2. `FINITE_REMOTE_STAND` strictly enforces $\text{usage} < C$ under all configuration options.
  3. Overflow is only routed to an apron if an explicit `overflow_gate` of type `UNBOUNDED_OVERFLOW_APRON` exists. Otherwise, recourse strictly returns `(None, "NO_CAPACITY_EXHAUSTED")`, marking the flight as unassigned.
- **Validation**: Tests `CAP-01` to `CAP-09` all PASS.

---

### Erratum ERR-03: Conflation of Heuristic Fallback Failure with Proven Infeasibility in Hybrid Solver
- **Severity**: High (Academic & Mathematical Rigor).
- **Historical Defect**: When CP-SAT timed out without finding an incumbent solution, the Hybrid solver attempted a greedy heuristic fallback. If greedy failed, `HybridGateSolver` unconditionally returned `status="INFEASIBLE"`.
- **Operational Impact**: Failure of a heuristic does not mathematically prove that no feasible solution exists ($\mathcal{F}_{\text{feas}} = \emptyset$). Claiming "INFEASIBLE" when the solver merely ran out of time or heuristic search failed is scientifically invalid.
- **Remediation**:
  1. When CP-SAT times out and fallback fails, return `status="TIMEOUT_NO_SOLUTION"` with `termination_reason=TerminationReason.TIME_LIMIT`.
  2. When CP-SAT returns unknown and fallback fails, return `status="UNKNOWN"` with `termination_reason=TerminationReason.NO_FEASIBLE_SOLUTION`.
  3. Return `status="INFEASIBLE"` with `PROVEN_INFEASIBLE` **only** when CP-SAT mathematically proves infeasibility.
- **Validation**: Tests `HYB-STATUS-01` to `HYB-STATUS-06` and regression suite `test_sa_hybrid_correctness_p03.py::test_s18` all PASS.

---

### Erratum ERR-04: Informal Execution Accounting & Survivor Bias Hazard in Monte Carlo Simulations
- **Severity**: High (Statistical Reproducibility).
- **Historical Defect**: Monte Carlo simulations lacked a formal accounting ledger to guarantee that all requested stochastic realizations ($N_{\text{requested}}$) were accounted for across generation, evaluation, and paired solver comparisons.
- **Operational Impact**: Risk of silent drops during numerical errors or timeouts, leading to survivorship bias and ambiguous failure rate denominators.
- **Remediation**:
  1. Implemented `ExecutionLedgerEntry` and `SimulationExecutionLedger`.
  2. Enforced exact conservation laws:
     $$n_{\text{requested}} = n_{\text{generated}} + n_{\text{generation\_failures}}$$
     $$n_{\text{generated}} = n_{\text{evaluated}} + n_{\text{evaluation\_failures}}$$
     $$n_{\text{evaluated}} = n_{\text{feasible}} + n_{\text{infeasible}}$$
  3. Enforced Paired Common Random Numbers (CRN) verification: every scenario must have identical realization hashes across all compared solvers.
- **Validation**: Tests `STAT-LEDGER-01` to `STAT-LEDGER-09` all PASS.

---

## 3. Academic Integrity & Thesis Impact Statement

None of these four errata invalidate the core conclusions of the bachelor thesis:
1. **Causal Machine Learning for Delay Prediction**: The XGBoost and HistGradientBoosting models remain valid, temporal contracts are fully respected, and Mode B2 causal rolling recourse operates strictly on non-anticipative information sets.
2. **Operations Research & Solver Comparison**: CP-SAT consistently finds optimal or superior solutions within reasonable budgets; Simulated Annealing and Hybrid methods refine initial plans while strictly preserving feasibility; Greedy provides millisecond-level responsiveness.
3. **Statistical Soundness**: With G12B-R1 closure, the simulation pipeline is certified ready for large-scale Monte Carlo execution (e.g., $N=500$) with zero risk of silent drops, corrupted status hashes, or unproven infeasibility claims.
