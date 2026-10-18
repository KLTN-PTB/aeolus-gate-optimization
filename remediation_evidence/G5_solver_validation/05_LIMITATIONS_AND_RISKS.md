# AEOLUS-G5: Limitations, Assumptions, and Operational Risks

**Gate Identifier:** `AEOLUS-G5`  
**Gate Title:** Solver Correctness, Hybrid Validation & Fair Benchmark  
**Role:** Senior Operations Research Engineer, Constraint Programming Specialist, Metaheuristic Researcher, Optimization Verification Engineer  
**Date:** 2026-10-11  
**Branch:** `remediation/g5-solver-validation`  
**Status:** Certified / Complete  

---

## 1. Technical Limitations of Solvers

### 1.1 CP-SAT Combinatorial Search on Dense Airfield Instances

1. **Model Construction Overhead vs Search Time:**
   - On instances with $N=300$ flights and $M=50$ contact gates, building the CP-SAT model (`sparse_interval` formulation with 15,000 potential assignment pairs and interval variables) takes between $1.5$ and $2.5$ seconds on standard single-core execution.
   - When a strict total wall-clock budget of $5.0$ seconds is imposed, the solver has only $\sim 2.5$ to $3.0$ seconds of actual search time.
   - For ultra-dense schedules, reaching a proven `OPTIMAL` status within $5.0$ seconds is computationally prohibitive; the solver returns `FEASIBLE` with an optimality gap.
2. **Warm-Start Dependency:**
   - Without warm-start hints from `DeterministicGreedyGateSolver`, CP-SAT may spend valuable seconds finding an initial feasible incumbent on tightly packed instances.
   - With warm start enabled (`cp_sat_use_warm_start=True`), CP-SAT guarantees an incumbent within milliseconds of search start.
3. **Single-Worker Determinism vs Multi-Threaded Performance:**
   - `num_search_workers=1` is strictly enforced to guarantee bit-level reproducible trajectories and benchmark fairness across platforms.
   - In production real-time operations, enabling 8 or 16 workers (`num_search_workers=8`) significantly reduces solve time and closes the optimality gap, but sacrifices cross-platform trajectory determinism.

---

### 1.2 Simulated Annealing Metaheuristic Limitations

1. **Neighborhood Operator Granularity:**
   - The current SA operators (`generate_neighbor`) consist of single-flight relocations (`move`) and pairwise flight gate exchanges (`swap`).
   - In dense flight schedules with tightly chained turnarounds and narrow idle gaps, single-flight moves frequently create secondary conflicts with existing flights on the target gate, causing the candidate state to be rejected by `is_gate_feasible_for_flight()`.
   - While `repair_state()` attempts conflict eviction, in highly congested instances the probability of discovering an augmenting feasible move without increasing cost diminishes rapidly.
2. **Convergence on Large Instances:**
   - On $N=30$ flights, SA successfully converges to the global minimum ($71.20$), improving on Greedy by $30.0$ cost points.
   - However, on $N=100$ to $300$ flights within 300 iterations, SA maintains the greedy seed objective because random local moves cannot easily discover complex multi-flight rotational reassignments.
   - For larger instances, higher iterations (e.g. 5,000 to 20,000) or Large Neighborhood Search (LNS) operators would be necessary.

---

### 1.3 Two-Stage Hybrid Mechanics

1. **Budget Division Trade-off:**
   - Allocating $50\%$ of time budget to CP-SAT and $50\%$ to SA cuts CP-SAT's search budget in half.
   - In Scenarios where CP-SAT needs $3$ seconds to find an improved incumbent, giving CP-SAT only $2.5$ seconds can force a fallback or leave it at a sub-optimal incumbent that SA cannot easily escape.
2. **The 0% Gain Reality:**
   - Whenever CP-SAT proves optimality or finds an incumbent that is already locally optimal with respect to 1-move/swap neighborhoods, SA's contribution is zero. This must be presented transparently in the thesis as an expected theoretical property, not masked with heuristic noise.

---

## 2. Operational Assumptions

1. **Turnaround Boundaries:**
   - Assumes minimum turnaround of 45 minutes and 15 minutes separation buffer between consecutive flights on contact gates.
2. **Remote Stand Overflow Semantics:**
   - Finite remote stands enforce capacity $K \ge 1$; unbounded overflow apron absorbs any spillover at cost $W_{\text{overflow}} = 200.0$.
3. **Common Random Numbers (CRN):**
   - Benchmarking relies on `random_seed=42` and single-threaded solvers to ensure exact apples-to-apples fairness.

---

## 3. Mitigation Strategies for Production & Thesis

| Risk / Limitation | Impact | Production Mitigation | Thesis Presentation Recommendation |
|:---|:---|:---|:---|
| CP-SAT timeout on $N=300$ instances | Returns `FEASIBLE` instead of `OPTIMAL` | Set `cp_sat_fallback_to_greedy=True` and configure 15s budget | Document trade-off between exact optimality and practical dispatch latency |
| SA stagnation on large instances | $0\%$ improvement over Greedy on $N \ge 100$ | Use CP-SAT directly as primary solver; treat SA as metaheuristic baseline | Present comparative chart showing CP-SAT's dramatic superiority over SA on constrained problems |
| Memory usage during model generation | Peak RSS reaches $30-50$ MB | `sparse_interval` eliminates Cartesian variables | Highlight memory efficiency of sparse interval formulation |
