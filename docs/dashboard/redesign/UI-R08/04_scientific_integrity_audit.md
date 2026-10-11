# UI-R08 Deliverable 04: Scientific Integrity & Research Domain Audit

**Audit Date:** 2026-10-11  
**Auditor:** Principal Scientific Software Engineer & Research Integrity Auditor  
**Domain Scope:** ML Forecasting, Turn Synthesis, Operations Research Solvers, Monte Carlo Engine  
**Audit Finding:** **100% COMPLIANT** (Zero Data Leakage, Zero Fabricated Results, Verified Provenance)

---

## 1. Dual-Core Machine Learning Delay Forecasting

### 1.1. Dual-Core Pipeline Architecture
Aeolus replaces simplistic aggregate delay heuristics with a native dual-core forecasting architecture:
- **Inbound Model:** Pre-departure arrival delay forecasting based on origin departure conditions, route weather, and scheduled buffer.
- **Outbound Model:** Pushback departure delay forecasting based on aircraft turnaround status, downstream airspace congestion, and inbound propagation.

### 1.2. Target Leakage Prevention & Anti-Contamination (Findings D1-D3)
- **Mathematical Boundary:** In planning mode, dispatchers and solvers must only observe scheduled departure/arrival times, contextual weather, and predicted delay distributions. Realized/actual delays cannot enter the decision space.
- **Enforcement Mechanism:** `ScientificValidator.check_prediction_data_leakage` intercepts prediction feature vectors. Prohibited columns (`actual_arr_delay`, `arr_delay_new`, `actual_dep_delay`, `actual_arrival_min`) raise `DataLeakageError` immediately.
- **Holdout Data Quarantine:** Operational BTS OTP year `2024` is strictly quarantined in `DashboardConfig.quarantined_years` to prevent out-of-sample data leakage into models trained on curated `2023` BTS OTP datasets.

### 1.3. Explainability Provenance (TreeSHAP)
- **Model Checkpoints:** Inbound (`artifacts/models/inbound_arrival/`) and Outbound (`artifacts/models/outbound_departure/`) are frozen XGBoost estimators.
- **SHAP Artifacts:** Global feature importance and individual waterfall values are loaded from authoritative artifacts (`artifacts/remediation/ml_validation/shap_summary_inbound.csv`). No randomized or dummy explainability values are generated on-the-fly.

---

## 2. Aircraft Turn Synthesis & Separation Buffer Mechanics

### 2.1. Physical Formulation & Minimum Turnaround
A turnaround connects an inbound flight leg $A$ to an outbound flight leg $D$ executed by the same airframe:
$$D_{\text{gate\_out}} = \max\left(D_{\text{pred}}, A_{\text{pred}} + T_{\text{min}}\right)$$
$$T_{\text{release}} = D_{\text{gate\_out}} + \text{separation\_buffer}$$

Where:
- $T_{\text{min}} = 45$ minutes minimum technical turnaround (fueling, deplaning, baggage transfer, cabin cleaning).
- $\text{separation\_buffer} = 15$ minutes wingtip clearance and pushback safety buffer.

### 2.2. Buffer Presence & Double-Counting Guard
- **Single-Buffer Invariant:** The 15-minute separation buffer is enforced exactly once in total gate occupancy $[start, release)$.
- **Adapter Verification:** In `adapt_assignment_to_view` and `adapt_turn_to_view`, the buffer is added strictly to the gate clearance threshold:
  $$\text{total\_blocked\_interval} = [A_{\text{pred}}, D_{\text{gate\_out}} + 15)$$
- **Zero Double-Counting:** Domain models that already embed the buffer (`end_already_has_buffer=True`) are recognized, preventing subsequent additions from distorting gate occupancy.

### 2.3. Slack Absorption & Outbound Delay Propagation
- **Scheduled Turn Window:** $W_{\text{sched}} = D_{\text{sched}} - A_{\text{sched}}$.
- **Scheduled Slack:** $S_{\text{sched}} = \max(0, W_{\text{sched}} - T_{\text{min}})$.
- **Absorbed Delay:** Inbound delay is absorbed by slack: $\Delta_{\text{abs}} = \min(S_{\text{sched}}, \Delta_{A,\text{pred}})$.
- **Propagated Delay:** Unabsorbed delay pushes outbound departure:
  $$\Delta_{D,\text{prop}} = \max(0, \Delta_{A,\text{pred}} - S_{\text{sched}})$$

---

## 3. Airport Gate Operations & Independent Constraint Verification

### 3.1. Gate Resource Hierarchy
1. **CONTACT_GATE:** Pier/concourse gate with passenger boarding bridge (PBB). Unit capacity ($C_g = 1$). Low reassignment penalty ($W_{\text{pref}} = 10.0$).
2. **FINITE_REMOTE_STAND:** Apron bus stand with finite pooled capacity ($K = 2 \dots 5$). Remote towing penalty ($W_{\text{remote}} = 200.0$).
3. **UNBOUNDED_OVERFLOW_APRON:** Unconstrained overflow tarmac stand. Used as safety valve to prevent solver infeasibility under severe overload, heavily penalized ($W_{\text{overflow}} \ge 1000.0$).

### 3.2. Half-Open Interval Algebra & Overlap Logic
- Aircraft gate occupancy is modeled on half-open time intervals $[s, e)$.
- Adjacent intervals $[s_1, e_1)$ and $[e_1, e_2)$ do **NOT** overlap ($s_1 < e_2$ and $s_2 < e_1$). A flight releasing at 10:00 does not conflict with a subsequent flight arriving at 10:00.
- `detect_gate_conflicts` sweeps arrival and release events, validating that simultaneous occupancy never exceeds physical stand capacity $C_g$.

### 3.3. Independent Hard-Constraint Verification
- **Separation of Roles:** Solvers (Greedy, CP-SAT, SA, Hybrid) do not self-certify.
- **Authoritative Verifier:** `verify_hard_constraints_independently` from `src/optimization/evaluation.py` inspects every assignment against physical gate conflict intervals, carrier restrictions, and finite stand capacities.
- **Status Truthfulness:** Optimality is awarded strictly if `status == "OPTIMAL"` AND `verifier_passed == True`.

---

## 4. Fair Scientific Benchmarking & Solver Boundaries

### 4.1. Decision-Dependent vs Reporting Costs (P04-P06 Audit)
- **Decision Cost ($J_{\text{decision}}$):** Objective minimized by the solver during search ($W_{\text{pref}} \cdot N_{\text{reassign}} + W_{\text{remote}} \cdot N_{\text{remote}} + W_{\text{conflict}} \cdot N_{\text{conflict}}$).
- **Reporting Cost ($J_{\text{reporting}}$):** Operational evaluation metric reflecting passenger connection delays and taxi time penalties.
- Both costs are distinctly reported in Optimization Lab, preventing conflation.

### 4.2. Incompatible Comparison Guard
- `ScientificValidator.validate_benchmark_record_compatibility` blocks cross-workload comparisons:
  - Different flight counts ($N_1 \ne N_2$).
  - Infeasible or UNKNOWN runs directly ranked against feasible solutions.
  - Violations raise `IncompatibleComparisonError` and show educational error banners.

### 4.3. Scalability Boundaries & CP-SAT $N=1500$ Bound
- Scalability curve benchmarks up to 1,500 flights across 50 gates (`artifacts/remediation/cp_sat/scalability_results.csv`).
- At $N=1500$, CP-SAT under 30-second time limits halts without integer feasibility:
  - `status: "UNKNOWN"`
  - `feasible: False`
  - `objective: None`
- The dashboard displays this data honestly with clear warning callouts, highlighting the necessity of heuristic or decomposition approaches (Greedy, Hybrid) at mega-hub scale.

---

## 5. Monte Carlo Statistical Integrity & Oracle Reference Audit

### 5.1. Observation Identity & Unit of Analysis
- **500 Stochastic Scenarios:** 500 distinct operational delay realizations per protocol generated by `monte_carlo_engine_p09.py`.
- **1,500 Solver Evaluated Records:** $500 \times 3$ evaluations across CP-SAT, Greedy, and Reference.
- The UI strictly isolates single-solver distributions (`validate_single_solver_dataframe`), ensuring statistical metrics (mean, median, quantiles) reflect $N=500$ observations per solver.

### 5.2. Mode A/B/C Research Protocol Audit
- **Mode A (Fixed Plan Robustness):** Evaluates static pre-computed schedules under realization delays without recourse. Correctly reports **74.8% conflict rate** and **0.0% static feasibility**, scientifically proving why gate plans collapse without buffer absorption and dynamic reallocation.
- **Mode B (Reactive Recourse):** Applies dynamic gate reassignments during flight delays, restoring 100% operational feasibility.
- **Mode C (Oracle Reference):** Perfect-foresight reference solved post-realization using Greedy heuristic.
  - **Audit Rule:** Explicitly labeled as an idealized research reference with zero real-time deployability.
  - **Optimality Disclaimer:** Labeled as non-optimal greedy reference; prohibited from claiming theoretical global optimality proof.

### 5.3. Statistical Methods & Tail Risk Coherence
- **Common Random Numbers (CRN):** Paired differences between solvers are joined strictly on identical `realization_id` values, ensuring unbiased paired comparisons and valid paired $t$-tests / Wilcoxon signed-rank statistics.
- **Tail Risk Coherence:** Conditional Value at Risk ($CVaR_{95}$) is computed as the conditional expectation of costs exceeding the 95th percentile ($p95$). Mathematically guaranteed $CVaR_{95} \ge p95$.
