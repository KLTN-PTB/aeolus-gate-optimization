# AEOLUS-G11 — DELIVERABLE 06: RAW TEST EXECUTION & AUDIT COMMAND LOG

---

**Audit Gate:** `AEOLUS-G11` — Targeted Causality, Hybrid Invariant & Snapshot Verification  
**Date of Audit:** 2026-10-12  
**Auditor Role:** Independent Scientific Software Verification Engineer  
**Audit Directory:** `audit_exports/G11_targeted_verification/`  
**Classification:** RAW EXECUTION TRACE & REPRODUCIBILITY LOG  

---

## 1. MÔI TRƯỜNG THỰC THI KIỂM TOÁN (AUDIT RUNTIME ENVIRONMENT)

Các lệnh kiểm toán được thực thi trực tiếp trên hệ thống người dùng thông qua Python Virtualenv:

```text
Python Executable: D:\Study\Code\Python\Aelous\.venv\Scripts\python.exe
Python Version:    3.11.15 (main, Mar 10 2026, 18:12:25) [MSC v.1944 64 bit (AMD64)]
OS / Platform:     Windows-10-10.0.19045-SP0 (win32)
Git Branch:        remediation/g7-regression
Git HEAD Commit:   c95caef53808a561b1a7d3a5a09399cc52f754f5 (uncommitted working tree state)

Installed Core Dependency Versions:
  - Google OR-Tools: 9.15.6755
  - XGBoost:         3.2.0
  - NGBoost:         0.5.11
  - scikit-learn:    1.9.0
  - Streamlit:       1.65.0
  - Plotly:          7.1.0
  - SciPy:           1.17.1
  - NumPy:           2.2.6
  - Pandas:          2.3.3
  - Pytest:          9.1.1
```

---

## 2. NHẬT KÝ THỰC THI TEST 1: MODE B2 CAUSALITY & UNUSED LOCK HORIZON

### 2.1. Lệnh thực thi:
```powershell
.venv\Scripts\python.exe audit_exports\G11_targeted_verification\test_counterexample_b2_leakage.py
```

### 2.2. Kết quả thực thi (Exit Code: 0):
```text
================================================================================
TEST 1: UNUSED lock_horizon_minutes PARAMETER TEST
================================================================================
Results for lock_horizon=0:    obj=210.0000, reassignments=1
Results for lock_horizon=45:   obj=210.0000, reassignments=1
Results for lock_horizon=1000: obj=210.0000, reassignments=1
=> VERIFIED: lock_horizon_minutes has ZERO effect on logic and output. It is completely unused dead code.

================================================================================
TEST 2: FUTURE INFORMATION ACCESS & DECISION LEAKAGE TEST
================================================================================
Scenario 1 (FL_A departs at 100, FL_B arrives at 120):
  FL_B reassignments count: 0
  Decision trace: ()

Scenario 2 (FL_A departs at 140 in future, FL_B arrives at 120):
  FL_B reassignments count: 1
  Decision trace: ({'flight_id': 'FL_B', 'decision_epoch_min': 120, 'previous_gate': 'G1', 'reassigned_gate': 'REMOTE', 'reason': 'ONLINE_NON_ANTICIPATIVE_RECOURSE'},)

================================================================================
ANALYSIS OF CAUSALITY IN SCENARIOS 1 vs 2:
================================================================================
CRITICAL FINDING: DECISION LEAKAGE PROVEN!
At epoch t=120:
  In Scenario 1, FL_B was NOT reassigned (reassignment_count=0)
  In Scenario 2, FL_B WAS reassigned (reassignment_count=1, trace=({'flight_id': 'FL_B', 'decision_epoch_min': 120, 'previous_gate': 'G1', 'reassigned_gate': 'REMOTE', 'reason': 'ONLINE_NON_ANTICIPATIVE_RECOURSE'},))
The two scenarios have identical operational histories prior to t=120:
  - Both have FL_A arriving at t=60.
  - Both have FL_B arriving at t=120.
  - The only difference is FL_A's future departure timestamp (100 vs 140).
In a strictly causal real-world simulation, if FL_A's delay occurred after t=120 (e.g., ground hold announced at 125),
an arrival decision at t=120 could not anticipate a future event unless informed by an active departure forecast.
Here, evaluate_mode_b2 directly accessed precomputed_gate_out_min (the final realized departure time)!
```

---

## 3. NHẬT KÝ THỰC THI TEST 2: HYBRID MONOTONICITY & WALL-CLOCK CONTRACT

### 3.1. Lệnh thực thi:
```powershell
.venv\Scripts\python.exe audit_exports\G11_targeted_verification\test_hybrid_monotonicity_micro.py
```

### 3.2. Kết quả thực thi (Exit Code: 0):
```text
================================================================================
PART 1: SOURCE INSPECTION OF hybrid_solver.py LINE 280
================================================================================
Source code of hybrid_solver.py around line 280:
  Line 274:         final_diag = verify_hard_constraints_independently(
  Line 275:             flights=flights,
  Line 276:             gates=gate_list,
  Line 277:             assignments=sa_result.assignments,
  Line 278:         )
  Line 279:         final_feasible = bool(final_diag.is_valid and len(sa_result.assignments) == len(flights))
  Line 280: 
  Line 281:         total_wall_clock_ms = (time.perf_counter() - t0) * 1000.0
  Line 282: 
  Line 283:         # Step 9: Compute objective independently
  Line 284:         final_eval = evaluate_gate_assignment(
  Line 285:             assignments=sa_result.assignments,
  Line 286:             flights=flights,
  Line 287:             gates=gate_list,
  Line 288:             config=self.config,
  Line 289:             runtime_ms=total_wall_clock_ms,
  Line 290:             solver_status="FEASIBLE" if final_feasible else "INFEASIBLE",

Occurrences of 'best_cost' or cost-related 'min(' in hybrid_solver.py: 3
  Match: "sa_best_cost": float("inf"),
  Match: "sa_best_cost": float("inf"),
  Match: "sa_best_cost": float(sa_result.objective_value),

=> VERIFIED: hybrid_solver.py contains 'best_cost = min': False
The G10 claim that line 280 implements 'best_cost = min(initial_cost, sa_cost)' is FACTUALLY FALSE.

================================================================================
PART 2: TEST OUTER MONOTONICITY BEHAVIOR WITH SA STUB
================================================================================
Normal solve result: status=OPTIMAL, obj=0.0000
  Stage 1 initial_cost: 0.0000
  Final objective_value: 0.0000

Stubbed SA (returning worse feasible solution obj=400.0):
  Stage 1 initial_cost was: 0.0000
  Hybrid returned status:   FEASIBLE
  Hybrid returned objective:420.0000
  Hybrid assignments:       REMOTE, REMOTE
=> CRITICAL VERIFICATION:
  hybrid_solver.py returned the WORSE SA solution! It did NOT fall back to initial_cost.
  This definitively proves hybrid_solver.py lacks outer monotonicity protection.

================================================================================
PART 3: WALL-CLOCK BUDGET CONTRACT IN SA
================================================================================
SimulatedAnnealingGateSolver.solve signature: (flights: 'Sequence[Flight]', gates: 'Sequence[Gate]', *, initial_assignments: 'Mapping[str, GateAssignment] | None' = None, allow_overflow: 'bool' = True) -> 'OptimizationResult'
Has time_limit or budget parameter: False
Has wall-clock timeout check in SA annealing loop: False
=> VERIFIED: SA runs for fixed iterations unconditionally without time checking.
  When N=200 (6.5s) and N=300 (9.2s), SA alone consumed 6.5s-9.2s.
  Adding CP-SAT Stage 1 (2.5s) resulted in 9.0s and 12.5s total wall-clock time.
  The 5.0s budget was NEVER enforced across both stages.
```

---

## 4. NHẬT KÝ THỰC THI TEST 3: RECONCILIATION MÃ BĂM MẬT MÃ

### 4.1. Lệnh thực thi:
```powershell
.venv\Scripts\python.exe audit_exports\G11_targeted_verification\verify_source_hashes.py
```

### 4.2. Kết quả thực thi (Exit Code: 0):
```text
==============================================================================================================
FILE PATH                                          | DISK MATCH MANIFEST?   | DISK MATCH ZIP?  | DISK MATCH SNAPSHOT MD?
==============================================================================================================
scripts/run_g5_fair_benchmark.py                   | True                   | True             | False
scripts/train_outbound_classifiers_g3.py           | True                   | True             | False
scripts/verify_reproducibility_g7.py               | NOT_IN_MANIFEST        | NOT_IN_ZIP       | False
src/contracts/__init__.py                          | NOT_IN_MANIFEST        | NOT_IN_ZIP       | False
src/contracts/provenance.py                        | True                   | True             | False
src/contracts/temporal.py                          | True                   | True             | False
src/contracts/turn_contracts.py                    | NOT_IN_MANIFEST        | NOT_IN_ZIP       | False
src/data/canonical_time.py                         | True                   | True             | False
src/data/pairing_validator.py                      | NOT_IN_MANIFEST        | NOT_IN_ZIP       | False
src/data/real_data_loader.py                       | True                   | True             | False
src/optimization/solvers/cp_sat_solver.py          | True                   | True             | NOT_IN_SNAPSHOT
src/optimization/solvers/hybrid_solver.py          | True                   | True             | NOT_IN_SNAPSHOT
src/simulation/dual_prediction_turn.py             | NOT_IN_MANIFEST        | NOT_IN_ZIP       | False
src/simulation/monte_carlo_engine_v2.py            | True                   | True             | False
src/simulation/verified_pairing.py                 | True                   | True             | False
tests/test_g1_provenance_and_temporal_contracts.py | NOT_IN_MANIFEST        | True             | False
tests/test_g2_monte_carlo_causality.py             | NOT_IN_MANIFEST        | True             | False
tests/test_g3_ml_validation.py                     | NOT_IN_MANIFEST        | True             | False
tests/test_g4_native_e2e.py                        | NOT_IN_MANIFEST        | True             | False
tests/test_g5_solver_correctness.py                | NOT_IN_MANIFEST        | True             | False
tests/test_g6_dashboard_integrity.py               | NOT_IN_MANIFEST        | True             | False
tests/test_g7_scientific_invariants.py             | NOT_IN_MANIFEST        | True             | False
==============================================================================================================

DETAILED MISMATCH SUMMARY FOR 01_SOURCE_SNAPSHOT.md:
Total files audited: 22
Files where Disk matches Manifest: 10 / 10
Files where Disk matches ZIP:      17 / 17
Files where Disk matches 01_SOURCE_SNAPSHOT.md: 0 / 22
Number of mismatches in 01_SOURCE_SNAPSHOT.md table: 22
```
