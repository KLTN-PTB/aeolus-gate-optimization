# AEOLUS-G7 — Scientific Invariants & Metamorphic Properties Report

## 1. Overview

To mathematically and empirically guarantee that the Aeolus Gate Optimization candidate system preserves scientific integrity under transformations, 10 property/metamorphic invariants (`INV-01` through `INV-10`) and 5 integration flows (`FLOW-A` through `FLOW-E`) were formalized and verified in `tests/test_g7_scientific_invariants.py`.

All 15 tests passed with 100% success rate.

---

## 2. Invariant Specifications & Verification Evidence

### INV-01: Permutation Invariance of Verified Aircraft Turn Pairing
- **Definition**: Given an input collection of flight legs $\mathcal{L}$, any arbitrary permutation $\pi(\mathcal{L})$ of the input DataFrame or dictionary yields identical paired turns:
  $$\text{Pair}(\pi(\mathcal{L})) \equiv \text{Pair}(\mathcal{L})$$
- **Verification Result**: Verified with 3 distinct random shuffling seeds (42, 1337, 9999). In all cases, identical pairing IDs, leg linkages, and turnaround durations were produced.
- **Verdict**: **PASSED**

---

### INV-02: Future-Only Delay Mutation Invariance (Non-Anticipativity / Causality)
- **Definition**: In rolling-horizon online recourse (Mode B2), mutating the realization of a flight occurring at epoch $t_{\text{future}} \gg t$ must strictly NOT alter decisions executed for flights at epochs $\le t$:
  $$\delta_{\text{recourse}}(f_{\le t} \mid \omega') = \delta_{\text{recourse}}(f_{\le t} \mid \omega) \quad \forall \, \omega, \omega' \text{ differing only on } f_{> t}$$
- **Verification Result**: In a 3-flight instance, mutating the distant future flight F3 from 15 min to 120 min delay produced identical early conflict resolution decisions for F2 at gate G2.
- **Verdict**: **PASSED**

---

### INV-03: Independent Hard Constraint Satisfaction
- **Definition**: Any solution marked `feasible=True` by CP-SAT or Deterministic Greedy must satisfy 100% of hard constraints when evaluated by the independent verifier outside the solver:
  $$\text{feasible} \implies \text{conflicts} = 0 \land \text{hard\_violations} = 0$$
- **Verification Result**: Tested on multi-flight instances across both solvers. Independent verifier confirmed `is_valid == True` and `conflict_count == 0`.
- **Verdict**: **PASSED**

---

### INV-04: Combinatorial Oracle Parity on Small Instances
- **Definition**: On small-scale problem instances ($N=3, M=2$), the brute-force exhaustive combinatorial oracle and CP-SAT proven optimum must agree to within numerical tolerance:
  $$|z_{\text{oracle}}^* - z_{\text{cp\_sat}}^*| < 10^{-4}$$
- **Verification Result**: Combinatorial oracle enumerated all candidate assignments and verified global optimum matches CP-SAT optimal objective value (10.0 vs 10.0, diff = 0.0).
- **Verdict**: **PASSED**

---

### INV-05: Deterministic Reproducibility
- **Definition**: Executing solvers with identical problem instances, configuration parameters, and random seeds yields bitwise and structurally identical assignment solutions:
  $$\text{Solve}(P, \theta, s)_1 \equiv \text{Solve}(P, \theta, s)_2$$
- **Verification Result**: Consecutive CP-SAT runs with `seed=42` produced identical gate assignment mappings and objective values.
- **Verdict**: **PASSED**

---

### INV-06: Paired Statistical Comparison Invariance
- **Definition**: Paired sample statistics ($\Delta = \text{Cost}_A - \text{Cost}_B$) preserve sample mean and sample standard deviation regardless of the ordering of realized scenario evaluations:
  $$\mathbb{E}[\pi(\Delta)] = \mathbb{E}[\Delta], \quad \mathbb{V}[\pi(\Delta)] = \mathbb{V}[\Delta]$$
- **Verification Result**: Shuffling scenario realization order preserved sample mean and sample standard deviation to float precision.
- **Verdict**: **PASSED**

---

### INV-07: Anti-Rebranding Provenance Guard
- **Definition**: Export adapters strictly reject exporting synthetic scenario assignments under a claimed `REAL_AEOLUS` origin:
  $$\text{Export}(\text{Synthetic}, \text{claim}=\text{REAL\_AEOLUS}) \implies \text{ProvenanceMismatchError}$$
- **Verification Result**: Adapter raised `ProvenanceMismatchError` with explicit violation description.
- **Verdict**: **PASSED**

---

### INV-08: Fail-Closed Real Inference Guard
- **Definition**: In strict real-data mode, missing model checkpoint files fail closed immediately without silent fallback to dummy/random heuristics:
  $$\text{Inference}(\text{Path}_{\text{missing}}, \text{mode}=\text{STRICT}) \implies \text{Fail Closed}$$
- **Verification Result**: Path validator strictly blocked non-allowlisted / non-existent model checkpoint paths.
- **Verdict**: **PASSED**

---

### INV-09: Objective Metric Invariance Under Flight Ordering
- **Definition**: Objective evaluation function is symmetric with respect to input flight list indexing when flight IDs and windows are preserved:
  $$\text{Eval}(\text{Reorder}(\mathcal{F})) = \text{Eval}(\mathcal{F})$$
- **Verification Result**: Reversing flight list order produced identical objective value and decision cost ($< 10^{-6}$ diff).
- **Verdict**: **PASSED**

---

### INV-10: Truth-in-Labeling Solver Status Mapping
- **Definition**: Solver status mapping never presents unproven solutions (`UNKNOWN` or `FEASIBLE` terminated on `TIME_LIMIT`) as `OPTIMAL` or "Tối ưu tuyệt đối":
  $$\text{map\_status}(S) \neq \text{OPTIMAL} \quad \forall \, S \notin \{\text{OPTIMAL\_PROVEN}\}$$
- **Verification Result**: `map_solver_status_to_badge` verified for `UNKNOWN` and `TIME_LIMIT` inputs; `is_optimal` is `False`.
- **Verdict**: **PASSED**

---

## 3. End-to-End Integration Flows (FLOW-A .. FLOW-E)

- **FLOW-A (Real Data $\to$ ML $\to$ Turn $\to$ CP-SAT)**: Successfully ingested dual-direction flight legs, executed verified tail-number pairing, mapped to optimization domain flights with predicted delays, and solved to optimality using CP-SAT.
- **FLOW-B (Synthetic Scenario $\to$ Solver $\to$ Independent Evaluator)**: Successfully generated synthetic scenario, solved with Deterministic Greedy, and verified that independent evaluator matched solver reported cost.
- **FLOW-C (Monte Carlo $\to$ Paired Metrics $\to$ Dashboard)**: Successfully executed multi-realization simulation, computed paired deltas between Mode A and Mode B, and verified dashboard view models.
- **FLOW-D (ML Evidence $\to$ Metrics Lineage $\to$ Reports)**: Successfully evaluated probabilistic classifications, verified Brier score calibration ($< 0.10$), and validated reporting metrics lineage.
- **FLOW-E (Dashboard Scenario $\to$ Solver $\to$ Export)**: Successfully triggered solver run from view model and exported verified JSON run manifest and CSV gate assignments.
