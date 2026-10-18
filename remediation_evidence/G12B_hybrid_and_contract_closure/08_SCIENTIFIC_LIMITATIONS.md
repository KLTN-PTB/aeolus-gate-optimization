# 08_SCIENTIFIC_LIMITATIONS.md

## AEOLUS-G12B Academic & Scientific Limitations Disclosure

**Author:** Academic Quality Assurance Lead, Operations Research Auditor  
**Date:** October 12, 2026  
**Context:** Bachelor Thesis: *"Ứng dụng học máy và lập trình ràng buộc trong dự báo độ trễ chuyến bay và tối ưu tái phân bổ cổng đỗ tàu bay"*

---

### 1. Purpose of Disclosure

In academic research, scientific integrity requires explicit disclosure of boundary conditions, structural trade-offs, and empirical limitations. This document records the four primary operational and methodological limitations of the remediated optimization and simulation system for defense reporting.

---

### 2. Disclosed Limitations

#### 2.1 Fixed Budget Partitioning Trade-off ($r_{\text{CP}}$)
- **Mechanism:** The Hybrid solver divides the total wall-clock budget $T_{\text{total}}$ using a fixed ratio $r_{\text{CP}} = 0.5$, allocating $50\%$ to Stage 1 CP-SAT and $50\%$ to Stage 2 SA.
- **Empirical Effect:** In large problem instances (e.g., 300 flights across 56 gates with a 5.0-second total budget), CP-SAT receives only $2.5$ seconds. Because CP-SAT's tree-search needs more than $2.5$ seconds on this density, it times out before generating an initial incumbent, prompting a fallback to Greedy ($1,219.47$). In contrast, standalone CP-SAT with the full $5.0$ seconds discovers a superior solution ($1,059.47$).
- **Defense Recommendation:** Disclose that a static 50/50 time partition penalizes exact solvers on dense instances. Future extensions should incorporate adaptive budget allocation where CP-SAT continues running if making rapid progress on the primal-dual gap.

#### 2.2 Neighborhood Scalability of Simulated Annealing in Dense Schedules
- **Mechanism:** The Stage 2 SA metaheuristic generates neighborhood moves via flight reassignments (`try_move_flight`) and pairwise swaps (`try_swap_flights`).
- **Empirical Effect:** On small and medium instances (30 flights), SA effectively improves greedy seeds by $29.6\%$. However, on large schedules (100–300 flights), the schedule matrix is densely packed. Random perturbations have a very high probability of violating physical non-overlap or buffer constraints, resulting in a low move acceptance rate.
- **Defense Recommendation:** In dense large-scale airport schedules, SA primarily functions as a local soft-metric polisher rather than a primary optimizer. The outer incumbent guard is essential to guarantee that SA's inability to find improving neighbors never degrades the certified Stage 1 incumbent.

#### 2.3 Event-Driven Heuristic Recourse in Mode B2 vs. Rolling-Horizon CP-SAT
- **Mechanism:** In Mode B2 (Rolling Online Recourse), when a conflict emerges, `make_causal_recourse_decision()` applies a greedy lowest-cost compatible gate assignment over observable flights.
- **Empirical Effect:** This policy strictly satisfies non-anticipativity and causality ($0$ future gate-out leakage) and executes in microseconds ($< 1\text{ ms}$ per decision epoch). However, it does not re-solve a multi-flight CP-SAT optimization at each decision epoch. A rolling-horizon CP-SAT recourse could theoretically find better downstream reassignments, but would require substantial computational overhead that challenges real-time dispatch feasibility.
- **Defense Recommendation:** Clarify that Mode B2 represents an *operational real-time dispatch policy*, balancing sub-millisecond responsiveness with strict causal validity.

#### 2.4 Deterministic Single-Worker Reproducibility vs. Multi-Core Parallelism
- **Mechanism:** All benchmarks and simulations enforce `num_search_workers = 1` and explicit seeds to guarantee bit-for-bit reproducibility.
- **Empirical Effect:** Modern hardware features 8–16 logical CPUs. Running CP-SAT with multiple workers (e.g., 8 threads) would explore search branches faster, potentially solving the 300-flight instance within 2.5 seconds. However, parallel search in OR-Tools is non-deterministic due to thread scheduling races.
- **Defense Recommendation:** Highlight that single-worker execution was deliberately chosen to ensure 100% scientific reproducibility and auditor verification across machines.
