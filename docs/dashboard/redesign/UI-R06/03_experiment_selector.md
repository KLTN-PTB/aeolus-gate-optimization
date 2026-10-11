# AEOLUS DASHBOARD — WORKLOAD & EXPERIMENT SELECTOR SPECIFICATION
**Phase**: UI-R06 v2.0  
**Implementation**: `dashboard/pages/page_04_optimization_lab.py`  
**State Key**: `st.session_state["opt_lab_workload"]`  

---

## 1. Overview & Architecture

The **Workload & Experiment Selector** is the core interactive control in Page 04 (Optimization Lab). Rather than presenting a confusing, aggregate view across arbitrary runs, the page mandates that all benchmark metrics, Pareto frontiers, and runtime breakdowns be scoped to **one active workload tier at a time**.

```
[ Active Workload Tier Selector ] 
       │
       ├── SCEN_TIER_A_10F_3G   (10 flights, 3 gates — Micro-scale baseline)
       ├── SCEN_TIER_A_20F_6G   (20 flights, 6 gates — Small-scale baseline)
       ├── SCEN_TIER_B_100F_20G (100 flights, 20 gates — Medium hub)
       ├── SCEN_TIER_B_200F_30G (200 flights, 30 gates — Large hub)
       └── SCEN_TIER_B_300F_50G (300 flights, 50 gates — Mega-hub benchmark)
```

---

## 2. Interaction & State Management

1. **State Persistence**:
   - The selected workload is stored in `st.session_state["opt_lab_workload"]`.
   - Default initialization: `SCEN_TIER_B_100F_20G` (or active session scenario if present in the benchmark suite).
2. **Dynamic Workload Metadata Card**:
   When a user switches workloads, the page immediately displays an executive header detailing:
   - **Workload Tier**: E.g., Tier B (Medium Hub).
   - **Scale**: E.g., 100 turns, 20 gates, 5 contact / 15 remote.
   - **Benchmark Provenance**: Total runs available (e.g. 15 runs across 5 solver variants, 3 repetitions each).
   - **Fairness Assurance Banner**: Explicit visual certification that all displayed solvers operated under identical turn distributions and constraint budgets.
3. **Solver Multi-Select Filter**:
   - Allows users to selectively view or isolate specific solver families:
     - Deterministic Greedy (`GREEDY_STANDALONE`)
     - CP-SAT (`CP_SAT_STANDALONE`)
     - Simulated Annealing Standalone (`SA_STANDALONE`)
     - SA from CP-SAT Incumbent (`SA_FROM_PRECOMPUTED_INCUMBENT`)
     - Hybrid Two-Stage (`HYBRID_STANDALONE`)

---

## 3. Passive Execution Guarantee

In accordance with UI-R02 session state safety rules:
- **No solver processes are launched** when changing the dropdown selector or checkboxes.
- All filtering operates strictly over pre-loaded, frozen artifact records in memory.
- Instantaneous switching ($< 10\text{ ms}$) without UI freeze or state contamination.
