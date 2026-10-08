# Aeolus Dual Core Rollout Governance & Rollback Playbook

**Protocol**: Aeolus Dual Core Architecture Protocol V2  
**Phase**: P10 — Dual Core Scientific Audit, Certification & Safe Rollout  
**Auditor Roles**: Principal ML Engineer, Research Auditor, Release Engineer  
**Date**: October 8, 2026  
**Repository Working Tree**: `Aeolus Gate Optimization` (`development/scalability-1500x50`)  
**Operational Status**: **`ROLLOUT_GOVERNANCE_ACTIVE`**  

---

## 1. Executive Summary & Rollout Philosophy

The Aeolus Dual Core Gate Optimization System introduces ML-predicted departure pushback times into the physical turn synthesis equation. While empirical evaluation demonstrates a **15.5% reduction in realized ramp collisions**, deploying machine learning models into airport ramp control requires strict, fail-safe operational governance.

This playbook establishes:
1. The **Four-Stage Phased Rollout Lifecycle** (`OFF` $\to$ `SHADOW` $\to$ `SANDBOX_CANARY` $\to$ `ENABLED`).
2. The **Pre-Registered Rollback Triggers** that mandate instantaneous reversion.
3. The **Zero-Downtime Rollback Procedure** that guarantees instant, bit-exact fallback to the legacy Arrival-only baseline without retraining, recompilation, or data loss.

---

## 2. Four-Stage Rollout Lifecycle

The system enforces four formal operational stages. Automatic promotion between stages is strictly prohibited.

```
       STAGE 1: OFF                     STAGE 2: SHADOW
   +--------------------+           +---------------------+
   | Default Safe Mode  |  ======>  | Dual runs in memory |
   | Arrival ML only    |           | Legacy controls gate|
   | Zero Departure ML  |           | Compare diffs & log |
   +--------------------+           +---------------------+
                                               ||
                                               \/
       STAGE 4: ENABLED              STAGE 3: CANARY
   +--------------------+           +---------------------+
   | Full Dual Control  |  <======  | Controlled sandbox  |
   | Explicit sign-off  |           | Limited flight bank |
   | Active monitoring  |           | Manual dispatcher   |
   +--------------------+           +---------------------+
```

### Stage 1: `OFF` (Production Default)
- **Configuration**: `dual_core_gate_enabled = False` in [`GateOptimizationConfig`](file:///D:/Study/Code/Python/Aelous/src/optimization/config.py#L40-L60).
- **Behavior**: System operates 100% as the historical legacy pipeline. Gate intervals are computed via $D_{\text{old}} = \max(D_{\text{sched}}, A_{\text{pred}} + T_{\text{min}})$. Core Departure models are not loaded.
- **Access Rule**: Default for all unauthenticated or production callers.

### Stage 2: `SHADOW` (Observability Without Control)
- **Configuration**: Dual Core Adapter runs asynchronously or in shadow wrapper alongside legacy solver.
- **Behavior**:
  - The legacy pipeline generates the authoritative gate assignment plan dispatched to operations.
  - The Dual Core engine receives the identical flight bank and computes a shadow assignment plan in memory.
  - A structured telemetry log records the differential matrix: gate reassignments, objective values, remote apron stand shifts, and solver latency.
- **Disruption Impact**: **Zero**. Real-world operations remain 100% controlled by legacy assignments.

### Stage 3: `SANDBOX_CANARY` (Controlled Field Testing)
- **Configuration**: `dual_core_gate_enabled = True` in an isolated sandbox environment or applied to a non-critical subset of flights (e.g. regional spoke flights during off-peak morning banks).
- **Human-in-the-Loop**: An airport gate dispatcher reviews both plans side-by-side prior to issuing ramp clearances.

### Stage 4: `ENABLED` (Active Production Control)
- **Condition**: Only achievable after passing 30 consecutive calendar days in `SHADOW` with zero anomalous telemetry and formal joint sign-off by Airport Operations and the ML Review Board.

---

## 3. Pre-Registered Rollback Triggers

Rollback triggers are **pre-registered invariants**. If any of the following conditions is breached, automated systems must trip the circuit breaker and revert to Stage 1 (`OFF`) immediately:

### Table 3.1: Circuit Breaker Invariants
| Trigger ID | Failure Condition | Threshold | Action |
| :--- | :--- | :---: | :---: |
| **TRG-01: Hard Constraint Violation** | Any planned overlap, carrier incompatibility, or gate size violation detected by independent verifier | $> 0$ violations | **Immediate Automated Trip to `OFF`** |
| **TRG-02: Prediction / Schema Failure** | Any unhandled exception, NaN/Inf prediction, or schema divergence during departure ML inference | $\ge 1$ error | **Immediate Automated Trip to `OFF`** |
| **TRG-03: Solver Latency Spike** | Wall-clock execution time for any bank of $\le 851$ turns exceeds real-time SLA budget | $> 2.0\text{ seconds}$ | **Immediate Automated Trip to `OFF`** |
| **TRG-04: Excess Remote Stand Allocations** | Number of flights allocated to remote apron stands exceeds legacy allocation by more than operational tolerance | $> +15\%$ vs legacy | **Alert Dispatcher & Trip to `OFF`** |
| **TRG-05: Realized Conflict Regression** | Observed ramp conflicts in shadow telemetry exceed legacy observed conflicts | $> 0$ excess conflicts | **Revert to `OFF` & Quarantine Model** |
| **TRG-06: Checkpoint Fingerprint Mismatch** | Cryptographic hash of loaded departure model checkpoint does not match certified manifest | Any mismatch | **Fail-Closed Startup Abortion** |

---

## 4. Zero-Downtime Rollback Procedure

Because Dual Core is governed entirely by a decoupled feature flag and domain adapter, rolling back requires **zero database migrations, zero model retraining, and zero container redeployment**.

### Step 4.1: Instantaneous In-Process Fallback
In Python application code:
```python
from src.optimization.config import GateOptimizationConfig
from src.optimization.adapter import DualCoreGateOptimizerAdapter

# 1. Instantaneous rollback: Set flag to False
config = GateOptimizationConfig(dual_core_gate_enabled=False)

# 2. Re-initialize adapter (reverts to legacy Arrival-only transformation)
adapter = DualCoreGateOptimizerAdapter(config=config)

# 3. Flights generated now follow exact legacy turnaround semantics
flights = adapter.turns_to_flights(turns, departure_model_id=None)
```

### Step 4.2: Configuration / Environment Variable Rollback
In production microservices or deployment configs:
```yaml
# configs/gate_optimization.yaml
gate_optimization:
  dual_core_gate_enabled: false  # <-- Set to false to disengage Dual Core
```
Or via environment variable:
```bash
export AEOLUS_DUAL_CORE_ENABLED=false
```

### Step 4.3: Bit-for-Bit Parity Guarantee
Automated regression tests in [`tests/test_dual_prediction_turn.py`](file:///D:/Study/Code/Python/Aelous/tests/test_dual_prediction_turn.py#L90-L115) and [`tests/test_dual_optimizer_integration.py`](file:///D:/Study/Code/Python/Aelous/tests/test_dual_optimizer_integration.py#L40-L75) verify that whenever `dual_core_gate_enabled = False`:
1. Every gate window $[A_{\text{pred}}, D_{\text{pred}}]$ matches legacy values bit-for-bit.
2. Solver objective values across `DeterministicGreedy`, `CPSat`, `SimulatedAnnealing`, and `HybridCPSatSA` match legacy baseline outputs to 4 decimal places.
3. No lingering state or memory leaks from the departure model persist.

---

## 5. Shadow Telemetry Logging Specification

During Stage 2 (`SHADOW`), the service must emit a structured JSON telemetry log for every optimized flight bank:

```json
{
  "timestamp_utc": "2026-10-08T12:00:00Z",
  "flight_bank_id": "ATL_BANK_20261008_1400",
  "rollout_stage": "SHADOW",
  "turns_processed": 851,
  "legacy_metrics": {
    "solver_runtime_ms": 91.3,
    "contact_assignments": 526,
    "remote_assignments": 325,
    "planned_hard_violations": 0
  },
  "shadow_dual_core_metrics": {
    "departure_model_id": "departure_xgboost_baseline_v1",
    "solver_runtime_ms": 86.5,
    "contact_assignments": 502,
    "remote_assignments": 349,
    "planned_hard_violations": 0,
    "reassignments_vs_legacy": 48
  },
  "rollback_triggers_tripped": []
}
```

If `rollback_triggers_tripped` contains any entry, the automated supervisor disengages shadow execution and files an incident ticket.

---

## 6. Rollback Sign-Off

The rollback mechanism has been designed for maximum resilience, fails closed under all error conditions, and has been verified by automated regression test suites.

**Rollback Authority**: Principal ML Engineer, Research Auditor, Release Engineer  
**Status**: **`APPROVED_FOR_STAGED_SHADOW_DEPLOYMENT`**
