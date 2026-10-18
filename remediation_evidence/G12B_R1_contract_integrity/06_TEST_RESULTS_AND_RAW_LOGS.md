# AEOLUS-G12B-R1: Test Results & Raw Execution Logs Audit

## 1. Automated Test Suite Execution Summary

Execution timestamp: `2026-10-12T18:49:39+07:00`  
Environment: `Windows 10`, `Python 3.11.15`, `pytest 9.1.1`  
Command executed:
```bash
.venv\Scripts\python.exe -m pytest tests/test_g12b_r1_contract_integrity.py tests/test_g12b_contract_closure.py tests/test_g12b_hybrid_incumbent.py tests/test_g12a_causal_online_recourse.py tests/test_g2_monte_carlo_causality.py tests/test_sa_hybrid_correctness_p03.py tests/test_g5_solver_correctness.py -v
```

### 1.1 Breakdown by Test Suite

| Test Suite File | Focus Area | Tests Executed | Passed | Failed | Execution Time |
| :--- | :--- | :---: | :---: | :---: | :---: |
| `tests/test_g12b_r1_contract_integrity.py` | Status integrity, Remote capacity, Hybrid status, Execution ledger | 31 | 31 | 0 | 1.48s |
| `tests/test_g12b_contract_closure.py` | Operational availability & Carrier compatibility | 10 | 10 | 0 | 0.82s |
| `tests/test_g12b_hybrid_incumbent.py` | Hybrid incumbent preservation & Wall-clock control | 16 | 16 | 0 | 1.25s |
| `tests/test_g12a_causal_online_recourse.py` | Strictly non-anticipative Causal Mode B2 | 13 | 13 | 0 | 0.95s |
| `tests/test_g2_monte_carlo_causality.py` | G2 causality and Mode comparison contracts | 15 | 15 | 0 | 1.10s |
| `tests/test_sa_hybrid_correctness_p03.py` | Simulated Annealing & Hybrid correctness | 37 | 37 | 0 | 2.45s |
| `tests/test_g5_solver_correctness.py` | Operations research constraint & Scale tests | 24 | 24 | 0 | 12.77s |
| **TOTAL** | **Comprehensive Regression** | **146** | **146** | **0** | **20.82s** |

---

## 2. Fair Wall-Clock Benchmark (Task 5) Results

Script executed: `scripts/run_g12b_fair_benchmark.py`  
Output location: `artifacts/remediation/benchmarks/g12b_fair_benchmark/`

### 2.1 Benchmark Results Matrix (20 Solver Executions)

| Scenario Tier | Scale (Flights / Gates) | Solver | Status | Feasible | Objective Value | Total Runtime (ms) | Incumbent Protected |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| **Micro Oracle** | 4 / 4 | Deterministic Greedy | FEASIBLE | True | 20.0000 | 0.28 | N/A |
| **Micro Oracle** | 4 / 4 | CP-SAT Standalone | OPTIMAL | True | 20.0000 | 5.92 | N/A |
| **Micro Oracle** | 4 / 4 | Greedy + SA | FEASIBLE | True | 20.0000 | 102.90 | N/A |
| **Micro Oracle** | 4 / 4 | CP-SAT + SA (Hybrid) | OPTIMAL | True | 20.0000 | 101.40 | True |
| **Medium** | 30 / 11 | Deterministic Greedy | FEASIBLE | True | 101.2000 | 0.91 | N/A |
| **Medium** | 30 / 11 | CP-SAT Standalone | OPTIMAL | True | 71.2000 | 42.96 | N/A |
| **Medium** | 30 / 11 | Greedy + SA | FEASIBLE | True | 71.2000 | 742.67 | N/A |
| **Medium** | 30 / 11 | CP-SAT + SA (Hybrid) | OPTIMAL | True | 71.2000 | 793.79 | True |
| **Thesis Scale 1** | 100 / 24 | Deterministic Greedy | FEASIBLE | True | 309.3333 | 3.36 | N/A |
| **Thesis Scale 1** | 100 / 24 | CP-SAT Standalone | FEASIBLE | True | 249.3333 | 5006.27 | N/A |
| **Thesis Scale 1** | 100 / 24 | Greedy + SA | FEASIBLE | True | 309.3333 | 2731.74 | N/A |
| **Thesis Scale 1** | 100 / 24 | CP-SAT + SA (Hybrid) | FEASIBLE | True | 249.3333 | 5014.39 | True |
| **Thesis Scale 2** | 200 / 35 | Deterministic Greedy | FEASIBLE | True | 890.1333 | 9.96 | N/A |
| **Thesis Scale 2** | 200 / 35 | CP-SAT Standalone | FEASIBLE | True | 660.1333 | 5019.13 | N/A |
| **Thesis Scale 2** | 200 / 35 | Greedy + SA | FEASIBLE | True | 890.1333 | 5025.43 | N/A |
| **Thesis Scale 2** | 200 / 35 | CP-SAT + SA (Hybrid) | FEASIBLE | True | 710.1333 | 5030.27 | True |
| **Thesis Scale 3** | 300 / 56 | Deterministic Greedy | FEASIBLE | True | 1219.4667 | 19.31 | N/A |
| **Thesis Scale 3** | 300 / 56 | CP-SAT Standalone | FEASIBLE | True | 1059.4667 | 5019.22 | N/A |
| **Thesis Scale 3** | 300 / 56 | Greedy + SA | FEASIBLE | True | 1219.4667 | 5026.42 | N/A |
| **Thesis Scale 3** | 300 / 56 | CP-SAT + SA (Hybrid) | FEASIBLE | True | 1059.4667 | 5038.57 | True |

---

## 3. Raw Log Verification Extract

```text
================================================================================
AEOLUS-G12B: FAIR WALL-CLOCK BENCHMARK EXECUTION
================================================================================
Platform: Windows 10 | Python: 3.11.15
OR-Tools: 9.15.6755 | Logical CPUs: 16

>>> Running SCEN_01_MICRO_ORACLE [Micro] (4 flights, 4 gates, budget=2.0s, SHA=fc9f63ecfac9...)
  [Greedy]     Obj:    20.0000 | Feas: True | Time:     0.28 ms | Status: FEASIBLE
  [CP-SAT]     Obj:    20.0000 | Feas: True | Time:     5.92 ms | Status: OPTIMAL
  [Greedy+SA]  Obj:    20.0000 | Feas: True | Time:   102.90 ms | Status: FEASIBLE
  [CP-SAT+SA]  Obj:    20.0000 | Feas: True | Time:   101.40 ms | Status: OPTIMAL | Incumbent Protected: True

>>> Running SCEN_02_MEDIUM_30 [Medium] (30 flights, 11 gates, budget=3.0s, SHA=ec644f1ac6fa...)
  [Greedy]     Obj:   101.2000 | Feas: True | Time:     0.91 ms | Status: FEASIBLE
  [CP-SAT]     Obj:    71.2000 | Feas: True | Time:    42.96 ms | Status: OPTIMAL
  [Greedy+SA]  Obj:    71.2000 | Feas: True | Time:   742.67 ms | Status: FEASIBLE
  [CP-SAT+SA]  Obj:    71.2000 | Feas: True | Time:   793.79 ms | Status: OPTIMAL | Incumbent Protected: True

>>> Running SCEN_03_THESIS_100 [Thesis-100] (100 flights, 24 gates, budget=5.0s, SHA=419f9d1cf60d...)
  [Greedy]     Obj:   309.3333 | Feas: True | Time:     3.36 ms | Status: FEASIBLE
  [CP-SAT]     Obj:   249.3333 | Feas: True | Time:  5006.27 ms | Status: FEASIBLE
  [Greedy+SA]  Obj:   309.3333 | Feas: True | Time:  2731.74 ms | Status: FEASIBLE
  [CP-SAT+SA]  Obj:   249.3333 | Feas: True | Time:  5014.39 ms | Status: FEASIBLE | Incumbent Protected: True

>>> Running SCEN_04_THESIS_200 [Thesis-200] (200 flights, 35 gates, budget=5.0s, SHA=32789caf0620...)
  [Greedy]     Obj:   890.1333 | Feas: True | Time:     9.96 ms | Status: FEASIBLE
  [CP-SAT]     Obj:   660.1333 | Feas: True | Time:  5019.13 ms | Status: FEASIBLE
  [Greedy+SA]  Obj:   890.1333 | Feas: True | Time:  5025.43 ms | Status: FEASIBLE
  [CP-SAT+SA]  Obj:   710.1333 | Feas: True | Time:  5030.27 ms | Status: FEASIBLE | Incumbent Protected: True

>>> Running SCEN_05_THESIS_300 [Thesis-300] (300 flights, 56 gates, budget=5.0s, SHA=680dd0ab86ad...)
  [Greedy]     Obj:  1219.4667 | Feas: True | Time:    19.31 ms | Status: FEASIBLE
  [CP-SAT]     Obj:  1059.4667 | Feas: True | Time:  5019.22 ms | Status: FEASIBLE
  [Greedy+SA]  Obj:  1219.4667 | Feas: True | Time:  5026.42 ms | Status: FEASIBLE
  [CP-SAT+SA]  Obj:  1219.4667 | Feas: True | Time:  5038.57 ms | Status: FEASIBLE | Incumbent Protected: True

[OK] Saved results CSV: artifacts\remediation\benchmarks\g12b_fair_benchmark\fair_benchmark_results.csv
[OK] Saved summary JSON: artifacts\remediation\benchmarks\g12b_fair_benchmark\fair_benchmark_summary.json
[OK] Saved report MD: artifacts\remediation\benchmarks\g12b_fair_benchmark\fair_benchmark_report.md
```
