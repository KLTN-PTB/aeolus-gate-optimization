# AEOLUS-G2 — DELIVERABLE 02: IMPLEMENTATION REPORT

## 1. Architectural Overview

The authoritative engine `src/simulation/monte_carlo_engine_v2.py` replaces legacy P09 procedures with mathematically formal, causally sound simulation routines. It establishes an explicit state machine for operational gate allocation under stochastic delays.

```
       Canonical Schedule (T-2h Cutoff)
                     │
         ┌───────────┴───────────┐
         ▼                       ▼
   Fixed Plan Mode A       Initial Plans (Greedy / CP-SAT / Hybrid)
   (Zero Re-optimization)        │
                                 ├───► Stochastic Realizations (Copula rho=0.45)
                                 │
         ┌───────────────────────┼────────────────────────┐
         ▼                       ▼                        ▼
Mode B1 (Retrospective)   Mode B2 (Online)          Mode C (Foresight)
- Full-Information       - Event-Driven Rolling     ┌─────┴──────────────┐
- Post-Hoc Re-opt        - Non-Anticipative Filter  ▼                    ▼
- Retrospective Label    - Docked Aircraft Locked  Mode C1 (Greedy)   Mode C2 (CP-SAT)
                         - Decision Trace Audited  Heuristic Baseline Proven Optimal Oracle
```

## 2. Detailed Mode Specifications

### 2.1 Mode A: Fixed Plan Robustness (`evaluate_mode_a_fixed_plan_v2`)
- **Philosophy:** Evaluates pre-operational gate assignments without any operational recourse adjustments ($0$ re-optimizations).
- **Implementation:** Applies realized stochastic arrivals and departures to frozen initial gate assignments. Evaluates objective costs, physical contact conflicts, and buffer violations using `evaluate_gate_assignment()`.
- **Information Regime:** `InformationRegime.PRE_OPERATIONAL`.
- **Reassignments Count:** Strictly $0$.

### 2.2 Mode B1: Retrospective Recourse (`evaluate_mode_b1_retrospective_recourse`)
- **Philosophy:** Represents a theoretical full-information hindsight re-optimization benchmark where the operational controller possesses clairvoyant knowledge of all flights' realized delays across the 24-hour horizon.
- **Scientific Status:** Strictly labeled `FULL_INFORMATION_RETROSPECTIVE` and `NON_DEPLOYABLE`.
- **Formulation:** Formulates the recourse problem taking the initial planned gate as the nominal target to penalize deviations ($c_{reassign} = 100.0$). Passes all realized flight intervals to the recourse solver.
- **Solver Dispatching:** Dynamically dispatches the requested recourse solver (`DeterministicGreedyGateSolver`, `CPSatGateSolver`, or `HybridGateSolver`), correcting the legacy hardcoding flaw.

### 2.3 Mode B2: Rolling-Horizon Online Recourse (`evaluate_mode_b2_rolling_online_recourse`)
- **Philosophy:** Emulates a true real-time airport operational control center (AOCC). Decisions are strictly causal, event-driven, and non-anticipative.
- **Mathematical Information Barrier:**
  At any decision epoch $t$, the information set $\mathcal{F}_t$ contains:
  $$\mathcal{F}_t = \{ (f, t_{arr}(f), t_{dep}(f)) \mid t_{arr}(f) \le t \}$$
  Future flights with $t_{arr}(f') > t$ are uncommitted and known only by scheduled/forecasted estimates.
- **State Machine & Invariants:**
  1. **Sequential Chronological Sweep:** Events are sorted by realized arrival time: $(t_{arr}, \text{flight\_index})$.
  2. **Docked Aircraft Immutability:** Any aircraft that has arrived and docked prior to $t$ ($\text{occupancy\_start} < t$) is placed in `locked_flights`. Its gate cannot be altered by downstream events.
  3. **Non-Anticipative Collision Detection:** When flight $f_{curr}$ arrives at $t$, its assigned gate is checked for physical conflict strictly against aircraft in `locked_flights`.
  4. **Causal Real-Time Reallocation:** If a conflict exists with a locked aircraft, $f_{curr}$ is dynamically reallocated to an available contact gate that has no overlap with locked aircraft. If all contact gates are physically occupied, it is reassigned to the finite remote apron stand ($c_{overflow} = 500.0$).
  5. **Auditable Decision Log:** Every reassignment records an immutable trace record: `(decision_epoch_min, flight_id, previous_gate, reassigned_gate, reason)`.

### 2.4 Mode C1: Heuristic Greedy Foresight Benchmark (`evaluate_mode_c_greedy_foresight`)
- **Philosophy:** Provides a fast, greedy full-foresight baseline.
- **Correction:** Explicitly sets `is_optimal_proven = False` and `recourse_policy = "HEURISTIC_FULL_FORESIGHT_BENCHMARK"`. It is no longer mislabeled as an optimal oracle lower bound.

### 2.5 Mode C2: CP-SAT Mathematical Optimal Oracle (`evaluate_mode_c_optimal_foresight`)
- **Philosophy:** True mathematical optimal lower bound under complete foresight.
- **Formulation:** Solves the full realized schedule using `CPSatGateSolver` with integer linear programming / constraint programming interval disjunctions.
- **Proof Verification:** Verifies `res_cpsat.optimality_proven == True` and `res_cpsat.status == "OPTIMAL"`. Proves mathematical global optimality across the entire day.

## 3. Feasibility Decomposition Engine (`decompose_feasibility`)

Legacy P09 reported a binary feasibility boolean that caused severe distortion in Mode A. The remediated engine decomposes operational status into five orthogonal dimensions:

1. **`physical_contact_conflict_count`:** Exact count of overlapping interval pairs on contact gates:
   $$\max(t_{start, 1}, t_{start, 2}) < \min(t_{release, 1}, t_{release, 2})$$
2. **`buffer_violation_count`:** Count of flight pairs where gate clearance occurred without the mandatory 15-minute separation buffer.
3. **`remote_capacity_violation`:** Boolean flag triggered if concurrent remote stand occupancy exceeds finite stand capacity ($K = 5$).
4. **`static_slot_consistency`:** Evaluates whether flights occupied gates at the exact baseline schedule times:
   $$\Delta_{arr} = 0 \quad \text{and} \quad \Delta_{dep} = 0 \quad \forall f$$
5. **`composite_feasible`:** True operational feasibility:
   $$\text{composite} = (\text{physical\_conflicts} = 0) \land (\neg \text{remote\_viol}) \land (\text{unassigned} = 0) \land \text{compat\_ok}$$

## 4. Rigorous Statistical Engine

- **Common Random Numbers (CRN):** Aligns scenario realizations across solvers and modes using strict `scenario_index` assertions.
- **Paired Delta Computation:**
  $$\Delta_s = \text{Cost}_A(s) - \text{Cost}_B(s)$$
  $$\text{SE}_{\Delta} = \frac{s_{\Delta}}{\sqrt{N}}, \quad \text{CI}_{95\%} = \bar{\Delta} \pm 1.96 \cdot \text{SE}_{\Delta}$$
- **Distributional Granularity:** Calculates P10, P25, P50, P75, P90, P95, P99, CVaR-90, CVaR-95, and exact proportions of improved, worsened, and tied realizations.
