# AEOLUS-G5: Scope and Baseline Specification

**Gate Identifier:** `AEOLUS-G5`  
**Gate Title:** Solver Correctness, Hybrid Validation & Fair Benchmark  
**Role:** Senior Operations Research Engineer, Constraint Programming Specialist, Metaheuristic Researcher, Optimization Verification Engineer  
**Date:** 2026-10-11  
**Branch:** `remediation/g5-solver-validation`  
**Status:** Certified / Complete  

---

## 1. Executive Summary & Gate Mandate

The primary objective of **AEOLUS-G5** is to perform a rigorous mathematical and empirical audit of the optimization solvers in `aeolus-gate-optimization`:
1. **Deterministic Greedy Solver** (`src/optimization/solvers/greedy_solver.py`): Interval scheduling heuristic baseline.
2. **Google OR-Tools CP-SAT Solver** (`src/optimization/solvers/cp_sat_solver.py`): Exact Constraint Programming solver.
3. **Simulated Annealing Solver** (`src/optimization/sa/`): Trajectory-based local search metaheuristic.
4. **Two-Stage Hybrid Solver** (`src/optimization/solvers/hybrid_solver.py`): CP-SAT / Greedy warm start combined with SA neighborhood refinement.
5. **Exhaustive Oracle** (`src/optimization/solvers/exhaustive_oracle.py`): Ground-truth combinatorial oracle for micro-instances.

A central mission of this gate is resolving the historical ambiguity surrounding the **"Hybrid 0% Gain"** phenomenon observed in previous 40-scenario benchmarks. Rather than accepting speculation or permitting fabricated improvements, this gate establishes the exact mathematical reasons why Hybrid yields 0% improvement over proven optimal solutions, proves formulation parity with the independent verifier, and executes a fair, reproducible benchmark across problem scales up to thesis scale ($N=300$ flights, $M=50$ contact gates).

---

## 2. Solver Inventory and Architectural Mapping

```
aeolus-gate-optimization / src / optimization /
├── config.py                 # Central GateOptimizationConfig (weights, budgets, policies)
├── domain.py                 # Domain models (Flight, Gate, Window), independent verifier
├── evaluation.py             # Authoritative evaluate_gate_assignment() common evaluator
├── benchmark_harness.py      # Multi-solver execution, invariant checks, SHA-256 hash auditing
├── sa /                      # Simulated Annealing Metaheuristic Engine
│   ├── annealer.py           # SimulatedAnnealingGateSolver, geometric cooling, log tracing
│   ├── neighborhood.py       # Move & Swap operators, explicit conflict repair operator
│   ├── objective.py          # Fast state objective evaluation with penalty functions
│   └── state.py              # SAState representation, fast index lookups, copy operations
└── solvers /                 # Standalone Solver Implementations
    ├── greedy_solver.py      # DeterministicGreedyGateSolver
    ├── cp_sat_solver.py      # CPSatGateSolver (sparse_interval, sparse_pairwise, dense_pairwise)
    ├── hybrid_solver.py      # HybridGateSolver (Stage 1 CP-SAT -> Stage 2 SA refinement)
    └── exhaustive_oracle.py  # Combinatorial brute-force global optimum oracle
```

---

## 3. Mathematical Formulation Baseline

### 3.1 Hard Constraints Enforced Outside the Solver

The independent verifier (`verify_hard_constraints_independently`) strictly validates that any proposed solution satisfies:

1. **Exactly-One Assignment:**
   $$\sum_{g \in \mathcal{G}} x_{f, g} = 1 \quad \forall f \in \mathcal{F}$$
   No flight may remain unassigned, and no flight may be assigned to multiple gates simultaneously.

2. **Contact Gate Mutual Exclusion (No-Overlap):**
   For any contact gate $g \in \mathcal{G}_{\text{contact}}$ ($\text{capacity} = 1$), two flights $f_1, f_2$ assigned to $g$ must have non-overlapping half-open intervals:
   $$[s_{f_1}, e_{f_1}) \cap [s_{f_2}, e_{f_2}) = \emptyset \iff \max(s_{f_1}, s_{f_2}) \ge \min(e_{f_1}, e_{f_2})$$
   Adjacent intervals $[s_1, e_1)$ and $[e_1, e_2)$ are strictly permitted without conflict.

3. **Finite Remote Stand Capacity:**
   For any remote parking stand $g \in \mathcal{G}_{\text{remote}}$ with finite capacity $K \ge 1$:
   $$\text{concurrent\_occupancy}(g, t) = \sum_{f \in \mathcal{F}: s_f \le t < e_f} x_{f, g} \le K \quad \forall t \in \mathcal{T}$$

4. **Resource Compatibility:**
   $$x_{f, g} = 0 \quad \text{if } \text{carrier}(f) \notin \text{allowed\_carriers}(g) \lor \text{aircraft\_type}(f) \notin \text{allowed\_aircraft}(g)$$

5. **Operational Availability Windows:**
   $$x_{f, g} = 0 \quad \text{if } [s_f, e_f) \not\subseteq \text{available\_windows}(g)$$

6. **Physical Turnaround & Buffer Boundaries:**
   $$\text{stay}(f) = \text{simulated\_departure}(f) - \text{predicted\_arrival}(f) \ge \text{min\_turnaround}(f)$$
   $$e_f = \text{simulated\_departure}(f) + \text{buffer\_min}(f)$$

---

### 3.2 Soft Objective Decomposition

The authoritative common objective evaluates decision-dependent operational penalties:

$$\min \mathcal{Z} = W_{\text{reassign}} \cdot C_{\text{reassign}} + W_{\text{overflow}} \cdot C_{\text{overflow}} + W_{\text{conflict}} \cdot C_{\text{conflict}} + W_{\text{risk}} \cdot C_{\text{risk}} + W_{\text{delay}} \cdot C_{\text{delay}}$$

Standard default weights in `GateOptimizationConfig`:
- $W_{\text{reassign}} = 10.0$ (penalty per flight reassigned from nominal contact gate)
- $W_{\text{overflow}} = 200.0$ (penalty per flight assigned to remote stand or overflow apron)
- $W_{\text{conflict}} = 1000.0$ (heavy penalty per illegal contact overlap if unconstrained)
- $W_{\text{risk}} = 2.0$ (buffer risk penalty for tight turnarounds $< 15$ minutes)
- $W_{\text{delay}} = 1.0$ (exogenous delay reporting metric)

---

## 4. Key Pre-Remediation Baseline Findings

1. **CP-SAT Scalability and Formulation (P06):**
   - The native `sparse_interval` formulation using OR-Tools `AddNoOverlap` and `NewOptionalIntervalVar` is asymptotically superior to pairwise cliques.
   - For instances up to 300 flights / 50 gates, CP-SAT builds and reaches feasible incumbent solutions rapidly when supplied with warm-start hints.
2. **The Nature of the "Hybrid 0% Gain":**
   - In P06 and historical benchmarks, CP-SAT was configured with sufficient time budget on instances where the global minimum cost was proven optimal.
   - When CP-SAT yields $\text{Status} = \text{OPTIMAL}$ with an optimality gap of $0.0\%$, **no algorithm on Earth** (including Simulated Annealing) can discover a lower objective value.
   - A 0% improvement in this regime is **mathematical proof of optimality preservation**, not an engineering defect.
3. **Scientific Invariants Required for G5:**
   - **Zero False Status:** Never report `OPTIMAL` unless certified by solver status, verified independently, and achieved without heuristic fallback.
   - **Zero Fabricated Improvement:** Never claim artificial non-zero improvement when objective cost is unchanged.
   - **Monotonic Runtime Accounting:** All build, search, validation, and total wall-clock timings must use high-resolution monotonic clocks (`perf_counter_ns`) without estimation.

---

## 5. Scope of G5 Deliverables

| Deliverable Name | Description |
|:---|:---|
| `01_SCOPE_AND_BASELINE.md` | Problem definition, solver architecture, mathematical formulation baseline |
| `02_IMPLEMENTATION_REPORT.md` | Detailed report on solver audit, constraint checks, and test implementation |
| `03_TEST_RESULTS.md` | Verification report for 25 test cases (`OR-01..10`, `SA-01..05`, `HYB-01..03`, `BENCH-01..04`, `SCALE-01..03`) |
| `04_EVIDENCE_MANIFEST.json` | Machine-readable manifest tracking files, hashes, environments, and test status |
| `05_LIMITATIONS_AND_RISKS.md` | Analysis of solver trade-offs, scaling limits, timeouts, and metaheuristic risks |
| `06_GATE_REPORT.md` | Formal sign-off and recommendation for Gate G5 completion |
| `07_FORMULATION_PARITY.md` | In-depth audit proving parity between CP-SAT integer objective, SA, and evaluator |
| `08_SA_HYBRID_VALIDATION.md` | Detailed analysis of SA neighborhood operators, Metropolis rule, and Hybrid mechanics |
| `09_FAIR_BENCHMARK_RESULTS.md` | Comprehensive empirical benchmark comparing Greedy, CP-SAT, SA, and Hybrid |
| `10_SCALABILITY_AND_TIMEOUTS.md` | Scalability stress results (100, 200, 300 flights), timeout handling, and fallback |
