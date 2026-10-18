# AEOLUS-G12B Fair Wall-Clock Benchmark Results

- Generated at: 2026-10-12T11:50:41Z
- Platform: Windows 10
- OR-Tools: 9.15.6755

## Tiered Performance Matrix

| Scenario | Flights | Gates | Solver | Status | Feasible | Optimality | Obj Value | Incumbent | Runtime (ms) | SA Accepted | Rejection Reason |
|---|---|---|---|---|---|---|---|---|---|---|---|
| SCEN_01_MICRO_ORACLE | 4 | 4 | Greedy | FEASIBLE | True | False | 20.0 | 20.0 | 0.28 | False | N/A_STANDALONE |
| SCEN_01_MICRO_ORACLE | 4 | 4 | CP-SAT | OPTIMAL | True | True | 20.0 | 20.0 | 5.92 | False | N/A_STANDALONE |
| SCEN_01_MICRO_ORACLE | 4 | 4 | Greedy+SA | FEASIBLE | True | False | 20.0 | 20.0 | 102.9 | True | NONE |
| SCEN_01_MICRO_ORACLE | 4 | 4 | CP-SAT+SA | OPTIMAL | True | True | 20.0 | 20.0 | 101.4 | True | None |
| SCEN_02_MEDIUM_30 | 30 | 11 | Greedy | FEASIBLE | True | False | 101.2 | 101.2 | 0.91 | False | N/A_STANDALONE |
| SCEN_02_MEDIUM_30 | 30 | 11 | CP-SAT | OPTIMAL | True | True | 71.2 | 71.2 | 42.96 | False | N/A_STANDALONE |
| SCEN_02_MEDIUM_30 | 30 | 11 | Greedy+SA | FEASIBLE | True | False | 71.2 | 101.2 | 742.67 | True | NONE |
| SCEN_02_MEDIUM_30 | 30 | 11 | CP-SAT+SA | OPTIMAL | True | True | 71.2 | 71.2 | 793.79 | True | None |
| SCEN_03_THESIS_100 | 100 | 24 | Greedy | FEASIBLE | True | False | 309.3333 | 309.3333 | 3.36 | False | N/A_STANDALONE |
| SCEN_03_THESIS_100 | 100 | 24 | CP-SAT | FEASIBLE | True | False | 249.3333 | 249.3333 | 5006.27 | False | N/A_STANDALONE |
| SCEN_03_THESIS_100 | 100 | 24 | Greedy+SA | FEASIBLE | True | False | 309.3333 | 309.3333 | 2731.74 | True | NONE |
| SCEN_03_THESIS_100 | 100 | 24 | CP-SAT+SA | FEASIBLE | True | False | 249.3333 | 249.3333 | 5014.39 | True | None |
| SCEN_04_THESIS_200 | 200 | 35 | Greedy | FEASIBLE | True | False | 890.1333 | 890.1333 | 9.96 | False | N/A_STANDALONE |
| SCEN_04_THESIS_200 | 200 | 35 | CP-SAT | FEASIBLE | True | False | 660.1333 | 660.1333 | 5019.13 | False | N/A_STANDALONE |
| SCEN_04_THESIS_200 | 200 | 35 | Greedy+SA | FEASIBLE | True | False | 890.1333 | 890.1333 | 5025.43 | True | NONE |
| SCEN_04_THESIS_200 | 200 | 35 | CP-SAT+SA | FEASIBLE | True | False | 710.1333 | 710.1333 | 5030.27 | True | None |
| SCEN_05_THESIS_300 | 300 | 56 | Greedy | FEASIBLE | True | False | 1219.4667 | 1219.4667 | 19.31 | False | N/A_STANDALONE |
| SCEN_05_THESIS_300 | 300 | 56 | CP-SAT | FEASIBLE | True | False | 1059.4667 | 1059.4667 | 5019.22 | False | N/A_STANDALONE |
| SCEN_05_THESIS_300 | 300 | 56 | Greedy+SA | FEASIBLE | True | False | 1219.4667 | 1219.4667 | 5026.42 | True | NONE |
| SCEN_05_THESIS_300 | 300 | 56 | CP-SAT+SA | FEASIBLE | True | False | 1219.4667 | 1219.4667 | 5038.57 | True | None |
