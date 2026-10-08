# Phase P8 — Aeolus Dual Core Gate Optimizer Integration & Solver Parity Report

**System**: Aeolus Dual Core Gate Optimization System  
**Protocol**: Dual Core Architecture Protocol V2  
**Phase**: P8 — Dual Core Gate Optimizer Integration & Solver Parity  
**Date**: October 8, 2026  
**Auditor / Engineer**: Senior Operations Research Engineer & Python Software Architect  
**Quality Gate Verdict**: **`PASS_DUAL_GATE_OPTIMIZER_INTEGRATION`**  

---

## 1. Executive Summary & Architectural Context

The Aeolus optimization pipeline executes the four-stage operational sequence:

$$\text{Predict} \longrightarrow \text{Simulate} \longrightarrow \text{Optimize} \longrightarrow \text{Evaluate}$$

### Historical Context & Challenge
- **Core Arrival** models predict signed arrival delay $\Delta_{\text{arr}}$ (`ARR_DELAY`) at cutoff $T - 2\text{h}$ for inbound flights (`DEST = ATL`).
- **Core Departure** models predict signed departure delay $\Delta_{\text{dep}}$ (`DEP_DELAY`) at cutoff $T - 2\text{h}$ for outbound flights (`ORIGIN = ATL`).
- In Phase P7, the `DualTurnEngine` synthesized turnarounds integrating both predictions while enforcing the physical turnaround constraint $D_{\text{gate\_out}} \ge A_{\text{pred}} + T_{\text{min}}$.
- **The Optimization Challenge**: If gate optimization solvers continued to compute pushback internally via the legacy formula $D_{\text{old}} = \max(D_{\text{sched}}, A_{\text{pred}} + T_{\text{min}})$, ML departure predictions would be ignored downstream, breaking physical fidelity.

### Phase P8 Breakthrough
Phase P8 accomplishes end-to-end integration across all four optimization solvers:
1. **Domain Adapter Extension**: Added `precomputed_gate_out_min: int | None = None` to the [`Flight`](file:///D:/Study/Code/Python/Aelous/src/optimization/domain.py) domain entity.
   - `None`: Exactly preserves 100% legacy behavior.
   - Validated integer: Informs all downstream solvers and evaluators of validated ML pushback.
2. **Feature-Flag Parity**: Controlled via `dual_core_gate_enabled: bool = False` in [`GateOptimizationConfig`](file:///D:/Study/Code/Python/Aelous/src/optimization/config.py) (defaults strictly to `False`).
3. **Role-Based Access Control (RBAC)**: Implemented [`DualCoreGateOptimizerAdapter`](file:///D:/Study/Code/Python/Aelous/src/optimization/adapter.py) with fail-closed security firewalls:
   - Auxiliary Departure models (`ModelTask.AUXILIARY_DEPARTURE`) are strictly blocked (`RoleAccessViolationError`).
   - Core Departure models require explicit certification with `selection_role="GATE_OUT_PREDICTION"` and `downstream_eligible=True` (`UncertifiedModelError`).
   - Unregistered/unknown models fail closed immediately (`UncertifiedModelError`).
4. **All-Solver Parity & Verification**: Verified that **Deterministic Greedy**, **OR-Tools CP-SAT**, **Simulated Annealing (SA)**, and the newly implemented **Two-Stage Hybrid (`HybridGateSolver`)** operate seamlessly and pass independent verification outside the solver (`verify_hard_constraints_independently`).

---

## 2. Mathematical Formulation & Domain Invariants

```
                               ┌──────────────────────────┐
                               │   DualAircraftTurn       │
                               │   A_pred, D_gate_out     │
                               └─────────────┬────────────┘
                                             │
                       ┌─────────────────────┴─────────────────────┐
                       ▼                                           ▼
          [dual_core_gate_enabled=False]              [dual_core_gate_enabled=True]
          precomputed_gate_out_min=None               precomputed_gate_out_min=D_gate_out
                       │                                           │
                       ▼                                           ▼
          ┌──────────────────────────┐                ┌──────────────────────────┐
          │      Legacy Flight       │                │    Dual-Core Flight      │
          │ D_sim = max(Dsched,      │                │ D_sim = D_gate_out       │
          │             Apred+Tmin)  │                │ [Apred, Dgate_out+Bbuf)  │
          │ [Apred, Dsim+Bbuf)       │                │ Physical:                │
          │                          │                │ Dgate_out >= Apred+Tmin  │
          └────────────┬─────────────┘                └────────────┬─────────────┘
                       │                                           │
                       └─────────────────────┬─────────────────────┘
                                             │
                                             ▼
                       ┌───────────────────────────────────────────┐
                       │          Authoritative Solvers            │
                       │  • Deterministic Greedy                   │
                       │  • Google OR-Tools CP-SAT                 │
                       │  • Simulated Annealing (SA)               │
                       │  • Two-Stage Hybrid (CP-SAT -> SA)        │
                       └─────────────────────┬─────────────────────┘
                                             │
                                             ▼
                       ┌───────────────────────────────────────────┐
                       │      Independent Hard Constraint Audit    │
                       │     verify_hard_constraints_independently │
                       │    (0 overlaps, 0 compatibility errors)   │
                       └───────────────────────────────────────────┘
```

### Occupancy Window Invariants
For any flight $f$, its gate occupancy interval $[S_f, E_f)$ is defined authoritatively by:
$$S_f = A_{f, \text{pred}}$$
$$E_f = D_{f, \text{sim}} + B_{\text{buffer}}$$

Where:
- Under **Legacy Mode** (`dual_core_gate_enabled = False`):
  $$D_{f, \text{sim}} = \max\left(D_{f, \text{sched}}, A_{f, \text{pred}} + T_{f, \text{min}}\right)$$
- Under **Dual Core Active Mode** (`dual_core_gate_enabled = True`):
  $$D_{f, \text{sim}} = D_{f, \text{gate\_out}}$$

### Physical Feasibility Guard
In [`Flight.__post_init__`](file:///D:/Study/Code/Python/Aelous/src/optimization/domain.py#L122-L140), any attempt to initialize a `Flight` with $D_{\text{gate\_out}} < A_{\text{pred}} + T_{\text{min}}$ or non-finite values fails closed immediately:
```python
if self.precomputed_gate_out_min is not None:
    min_turn = self.predicted_arrival_min + self.min_turnaround_min
    if self.precomputed_gate_out_min < min_turn:
        raise ValueError(
            f"precomputed_gate_out_min ({self.precomputed_gate_out_min}) violates physical minimum "
            f"turnaround: must be >= predicted_arrival_min ({self.predicted_arrival_min}) + "
            f"min_turnaround_min ({self.min_turnaround_min}) = {min_turn}"
        )
```

---

## 3. Role-Based Access Control & Security Architecture

The adapter [`DualCoreGateOptimizerAdapter`](file:///D:/Study/Code/Python/Aelous/src/optimization/adapter.py) strictly enforces the project's security and leakage boundary contracts:

| Security Rule | Mechanism | Target Exception | Audit Verdict |
| :--- | :--- | :--- | :--- |
| **Auxiliary Departure Firewall** | Auxiliary Departure models (`task=auxiliary_departure`) are strictly research-only and must never influence gate optimization. | `RoleAccessViolationError` | **PASS** |
| **Departure Role Certification** | Core Departure models must have `selection_role="GATE_OUT_PREDICTION"` and `downstream_eligible=True`. Uncertified candidates are blocked. | `UncertifiedModelError` | **PASS** |
| **Fail-Closed on Unknown Model** | Unregistered or heuristic model IDs cannot feed the optimizer. | `UncertifiedModelError` | **PASS** |
| **Arrival Role Separation** | Arrival models cannot be used as departure predictors. | `RoleAccessViolationError` | **PASS** |
| **Physical Turnaround Guard** | Flights violating minimum turnaround duration are rejected before solver execution. | `ValueError` | **PASS** |
| **Numeric Finiteness Guard** | Rejects `NaN`, `Inf`, or non-finite timeline values. | `ValueError` | **PASS** |

---

## 4. Four-Solver Architecture & Two-Stage Hybrid Solver

Phase P8 guarantees unified compatibility across all four solvers:

1. **Deterministic Greedy Solver** ([`DeterministicGreedyGateSolver`](file:///D:/Study/Code/Python/Aelous/src/optimization/solvers/greedy_solver.py)):
   - Order-stable, greedy first-fit heuristic prioritizing nominal contact gates before falling back to overflow stands.
2. **Exact CP-SAT Solver** ([`CPSatGateSolver`](file:///D:/Study/Code/Python/Aelous/src/optimization/solvers/cp_sat_solver.py)):
   - Google OR-Tools exact Constraint Programming formulation enforcing zero-overlap intervals on contact gates and minimizing decomposed soft objective penalties.
3. **Simulated Annealing Solver** ([`SimulatedAnnealingGateSolver`](file:///D:/Study/Code/Python/Aelous/src/optimization/sa/annealer.py)):
   - Metaheuristic neighborhood search with strict monotonic feasibility preservation.
4. **Two-Stage Hybrid Solver** ([`HybridGateSolver`](file:///D:/Study/Code/Python/Aelous/src/optimization/solvers/hybrid_solver.py)):
   - **Stage 1**: Fast exact CP-SAT solver (budgeted to a fraction `cp_ratio=0.5` of total compute) or deterministic Greedy fallback to obtain a guaranteed hard-feasible incumbent.
   - **Stage 2**: Simulated Annealing metaheuristic search refining soft objectives starting from the Stage 1 incumbent.
   - **Monotonicity Guarantee**: The final solution is guaranteed to have objective value $\le$ Stage 1 incumbent.

---

## 5. Empirical Benchmark & Solver Parity Audit

The audit script [`scripts/run_dual_solver_parity_audit.py`](file:///D:/Study/Code/Python/Aelous/scripts/run_dual_solver_parity_audit.py) evaluated a 12-flight, 7-gate (6 contact + 1 overflow stand) scenario under both Legacy Mode and Dual Core Active Mode.

Artifact generated: [`artifacts/dual_core/benchmarks/dual_solver_parity_report_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/dual_core/benchmarks/dual_solver_parity_report_v1.json).

### Table 5.1: Legacy Parity Matrix (`dual_core_gate_enabled = False`)
Comparing assignments produced by legacy flights vs adapter with flag OFF:

| Solver | Assignment Mismatches | Objective Difference | Parity Status | Feasible | Hard Violations |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **DeterministicGreedy** | **0** | **0.0000** | **`EXACT_BIT_PARITY`** | True | 0 |
| **CPSat** | **0** | **0.0000** | **`EXACT_BIT_PARITY`** | True | 0 |
| **SimulatedAnnealing** | **0** | **0.0000** | **`EXACT_BIT_PARITY`** | True | 0 |
| **HybridCPSatSA** | **0** | **0.0000** | **`EXACT_BIT_PARITY`** | True | 0 |

### Table 5.2: Dual Core Active Performance (`dual_core_gate_enabled = True`)
Evaluating all 4 solvers with certified model `departure_certified_point_v1`:

| Solver | Status | Objective Value | Runtime (ms) | Internal Violations | Independent Hard Violations | Independent Conflicts |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **DeterministicGreedy** | `FEASIBLE` | 202.5833 | 0.12 ms | 0 | **0** | **0** |
| **CPSat** | `OPTIMAL` | 202.5833 | 9.77 ms | 0 | **0** | **0** |
| **SimulatedAnnealing** | `OPTIMAL` | 202.5833 | 59.26 ms | 0 | **0** | **0** |
| **HybridCPSatSA** | `OPTIMAL` | 202.5833 | 68.65 ms | 0 | **0** | **0** |

*Note: In this congested dual-core scenario, all four solvers successfully scheduled the expanded gate-out intervals with zero contact gate overlaps and zero operational constraint violations.*

---

## 6. Verification & Test Suite Summary

The test suite in [`tests/test_dual_optimizer_integration.py`](file:///D:/Study/Code/Python/Aelous/tests/test_dual_optimizer_integration.py) executes 18 comprehensive tests covering:
- **TestLegacyParityMatrix** (4 tests): Verifies bit-for-bit parity across Greedy, CP-SAT, SA, and Hybrid solvers.
- **TestDualCoreActiveModeMatrix** (5 tests): Verifies departure ML timeline integration and zero violations across all 4 solvers.
- **TestRoleBasedAccessControlAndGuards** (7 tests): Tests auxiliary rejection, uncertified rejection, unknown model rejection, arrival mismatch, missing model id, physical turnaround violations, and non-finite numbers.
- **TestHybridSolverArchitecture** (2 tests): Verifies degenerate zero-flight handling and parameter domain validation.

**Test Execution Result**:
```
tests/test_dual_optimizer_integration.py: 18 passed in 1.37s (100% pass rate)
Core contract & catalog suites: 64 passed in 0.63s (100% pass rate)
```

---

## 7. Quality Gate Verdict & Sign-Off

All Phase P8 success criteria have been completely satisfied:
1. `Flight` domain entity supports `precomputed_gate_out_min` with physical feasibility enforcement ($D_{\text{gate\_out}} \ge A_{\text{pred}} + T_{\text{min}}$).
2. `GateOptimizationConfig` defaults `dual_core_gate_enabled = False` (100% legacy parity).
3. All four solvers (Greedy, CP-SAT, SA, Hybrid) operate consistently with unified domain entities.
4. Role-based access control blocks Auxiliary Departure models and uncertified candidates.
5. Independent hard constraint verification confirms zero hard constraint violations across all solvers.
6. JSON benchmark artifact and documentation generated.

**Phase P8 Verdict**: **`PASS_DUAL_GATE_OPTIMIZER_INTEGRATION`**
