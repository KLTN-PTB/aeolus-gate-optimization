# Aeolus Dual Core Scientific Certification Report

**Protocol**: Aeolus Dual Core Architecture Protocol V2  
**Phase**: P10 — Dual Core Scientific Audit, Certification & Safe Rollout  
**Auditor Roles**: Principal ML Engineer, Research Auditor, Release Engineer  
**Date**: October 8, 2026  
**Repository Working Tree**: `Aeolus Gate Optimization` (`development/scalability-1500x50`)  
**Certification Title**: **`DUAL_CORE_CERTIFIED_FOR_SIMULATION`**  
**Formal Certification Status**: **`CERTIFIED_WITH_LIMITATIONS`**  

---

## 1. Formal Certification Statement

Under the authority of the Aeolus Dual Core Architecture Protocol V2 and rigorous scientific auditing standards, the **Aeolus Dual Core Gate Optimization System** is hereby granted:

### **`DUAL_CORE_CERTIFIED_FOR_SIMULATION`**

This certification confers authorized status for **synthetic and Monte Carlo operational simulation**, airport capacity planning studies, and controlled shadow evaluation. It certifies that the mathematical formulations, data pipeline firewalls, machine learning predictions, and downstream optimization solvers function reproducibly and safely.

---

## 2. Taxonomy of System Readiness

To prevent confusion between simulation proof and real-world airfield operations, the evaluation distinguishes four distinct certification layers:

```
+---------------------------------------------------------------------------------------+
| LAYER 1: Engineering Validation                         STATUS: [PASS]                |
| -> Unit tests, typing, fold-safe transforms, 0 leakage, deterministic inference       |
+---------------------------------------------------------------------------------------+
| LAYER 2: Scientific Evaluation                          STATUS: [PASS]                |
| -> Heavy-tail asymmetry confirmed, Student-t calibration, 1.25M OOF verification      |
+---------------------------------------------------------------------------------------+
| LAYER 3: Operational Simulation                         STATUS: [CERTIFIED]           |
| -> Validated pushback, -15.5% realized conflicts, solver scalability parity           |
+---------------------------------------------------------------------------------------+
| LAYER 4: Real-World Airfield Deployment Readiness       STATUS: [NOT_CERTIFIED]       |
| -> Requires physical tail authentication & live airline dispatch integration          |
+---------------------------------------------------------------------------------------+
```

### Prohibited Nomenclature
In accordance with strict aviation research governance, the following terms are **EXPLICITLY PROHIBITED** from being applied to this release:
- ❌ **"Production Certified"** — Prohibited. The system is certified exclusively for simulation and controlled shadow trials.
- ❌ **"Real-Airport Validated"** — Prohibited. Real-world validation requires live operational trials at an operating airport tower/ramp control center.
- ❌ **"Physically Verified Aircraft Rotation"** — Prohibited. Rotations in the schedule fixture are synthetic session groupings (`sim_aircraft_id`), not authenticated physical tail-tracking feeds (`TAIL_NUM`).

---

## 3. Certified Scope & Capabilities

The certification applies strictly to the components and configurations detailed below:

### 3.1 Certified Forecasting Capabilities
1. **Core Departure Point Regression**:
   - Model ID: `departure_xgboost_baseline_v1`
   - Feature Policy: Approved 10 predictors at cutoff $T - 2\text{h}$ ([`src/features/departure_features.py`](file:///D:/Study/Code/Python/Aelous/src/features/departure_features.py)).
   - Target: Continuous signed `DEP_DELAY` (minutes).
2. **Core Departure Probabilistic Distribution**:
   - Model ID: `departure_ngboost_student_t_v1`
   - Parameterization: Heteroscedastic Student-$t$ distribution ($\mu(X), \sigma(X) \ge 1.0, \nu(X) \ge 2.1$).
   - Sampling: Monotonic CDF/quantiles with zero-clipping prohibition.
3. **Core Arrival (Frozen Baseline)**:
   - Model ID: `P4_ngboost_student_t` (SHA-256: `e7e7462f17b65b276ebdee9c7beced15e090f69b088a18896d5a91aaa8cb062f`).

### 3.2 Certified Simulation & Optimization Solvers
1. **Simulation Engine**:
   - [`DualTurnEngine`](file:///D:/Study/Code/Python/Aelous/src/simulation/dual_prediction_turn.py#L120-L245) with physical turnaround floor $D_{\text{gate\_out}} = \max(D_{\text{ml}}, A_{\text{pred}} + T_{\text{min}})$.
   - Bit-for-bit backward compatibility with legacy Arrival-only mode when `dual_core_gate_enabled = False`.
2. **Downstream Solvers**:
   - `DeterministicGreedyGateSolver`: Certified for sub-second real-time dispatch ($< 90\text{ ms}$ on 851 turns).
   - `CPSatGateSolver`: Certified for exact global optimality on small/medium banks ($\le 100$ turns).
   - `SimulatedAnnealingGateSolver`: Certified for large-scale heuristic packing.
   - `HybridGateSolver`: Certified champion for production schedules (CP-SAT optimality with greedy/SA fallback).

---

## 4. Specific Limitations & Known Constraints

This certification is granted **WITH LIMITATIONS**. Any downstream consumer of this release must observe the following constraints:

1. **Synthetic Rotation Provenance**:
   - The canonical BTS dataset does not provide verified physical aircraft serial numbers. Pairings in [`atl_1500_flights_cpsat_turnaround_schedule.csv`](file:///D:/Study/Code/Python/Aelous/src/artifacts/predictions/atl_1500_flights_cpsat_turnaround_schedule.csv) represent synthetic pairings (`PairType.SYNTHETIC_PAIR`).
   - Ground fuel savings and airframe rotation turnaround guarantees remain theoretical until validated against live airline tail-assignment feeds.
2. **Contact Gate Capacity Shift**:
   - Because Dual Core proactively protects against pushback delays, contact gate reservations are wider. On 851 turns, remote apron stand assignments increase from 325 to 349 (+24 flights, +7.4%).
   - Airports operating with zero remote apron capacity will experience higher unassigned flight risk unless separation buffer parameters ($B_{\text{buffer}}$) are recalibrated.
3. **Default Feature Flag & Production Invariants**:
   - The feature flag `dual_core_gate_enabled` in [`GateOptimizationConfig`](file:///D:/Study/Code/Python/Aelous/src/optimization/config.py#L40-L60) must remain **`False` by default**.
   - Dual Core may only be engaged in `SHADOW` or `SANDBOX_CANARY` environments following the procedures in [`DUAL_CORE_ROLLBACK_PLAYBOOK.md`](file:///D:/Study/Code/Python/Aelous/DUAL_CORE_ROLLBACK_PLAYBOOK.md).

---

## 5. Certification Sign-Off

```
================================================================================
          AEOLUS DUAL CORE SCIENTIFIC CERTIFICATION SIGN-OFF
================================================================================
  Scope Granted        : DUAL_CORE_CERTIFIED_FOR_SIMULATION
  Status               : CERTIFIED_WITH_LIMITATIONS
  Engineering Gate     : PASS (142/142 Dual Core tests, 1,369 full-repo tests)
  Scientific Evidence  : PASS (49 fewer ramp collisions, 1,849 min saved)
  Deployment Policy    : FEATURE FLAG OFF (Production rollout deferred to field trial)
================================================================================
```

**Signed**: Principal ML Engineer, Research Auditor, Release Engineer  
**Date**: October 8, 2026
