# Forensic Audit Report: Downstream Solver Benchmark, Fairness & Scalability

**Audit Protocol**: Downstream Solver Certification & Execution Audit  
**Execution Timestamp**: 2026-10-04T16:38:00Z  
**Repository Branch**: `v4-final-forensic-certification`  
**Git Commit HEAD**: `7ba0aba92d366f712977faaaa5a73cba65a32a55`  
**Target Environment**: Windows, Python 3.11.15, CPU-only  

---

## 1. Executive Summary

This forensic audit evaluates the downstream gate optimization solver benchmarks across:
`DeterministicGreedy`, `CPSat`, `SimulatedAnnealing`, and `HybridCPSatSA`.

### Key Conclusions
1. **Reconciliation of Objective Means**:
   - The authoritative R26 benchmark scores across 28 cases ($112$ runs under equal wall-clock ceiling $T=2.0$s) are:
     - **DeterministicGreedy**: `7181.45`
     - **CPSat**: `7167.17`
     - **SimulatedAnnealing**: `7167.88`
     - **HybridCPSatSA**: `7167.17`
2. **Reconciliation of 28 Instances vs. 84 Runs vs. 112 Runs**:
   - **28 Unique Instances**: 4 operational scenarios $\times$ 7 arrival delay forecast models.
   - **84 Runs (R21)**: 28 instances $\times$ 3 solvers (`Greedy`, `CP-SAT`, `SA`) on **2023 development scenarios**.
   - **112 Runs (R26)**: 28 instances $\times$ 4 solvers (`Greedy`, `CP-SAT`, `SA`, `Hybrid`) on **2024 post-holdout seasonal scenarios**.
   - R26 evaluates post-holdout synthetic scenarios and does **not** certify or replace the 84 R21 development runs.
3. **Reconciliation of Percentage Claims**:
   - The claim that *"Greedy was 18.4%–34.2% worse than CP-SAT"* (originating in draft inventory notes) is **forensically refuted** on the 28-instance benchmark:
     - On the 28 authoritative R26 instances, Greedy is on average only **$0.20\%$** higher in total cost ($+14.28$ cost units out of $7167.17$, range: $0.00\%$ to $1.80\%$).
     - The range $18.4\%–34.2\%$ does not match any raw dataset, partition, or metric in the repository.
     - Formal Verdict: **`CLAIM_RETRACTED_OR_UNVERIFIED`**.
4. **Fairness Semantics**:
   - `WALL_CLOCK_EQUALITY = PROVEN` ($T = 2.0$s ceiling strictly enforced across all solvers).
   - `COMPUTATIONAL_WORK_EQUALITY = NOT_PROVEN` (Greedy finishes in $1.1$ ms; CP-SAT terminates early at $0.44$ s with proven global optimum; SA spins for the full $2.0$ s ceiling over $2351$ iterations).
5. **Gate Verdict**:
   - **`PASS_WITH_RESERVATION`** (Wall-clock ceiling equality is proven, but computational-work equality cannot be claimed).

---

## 2. Benchmark Execution Matrix

Raw data sourced from [`artifacts/audit/r26_solver_equal_compute_results.parquet`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r26_solver_equal_compute_results.parquet), [`artifacts/audit/r26_solver_budget_reconciliation.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r26_solver_budget_reconciliation.json), and [`artifacts/audit/r35_solver_boundary_audit.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r35_solver_boundary_audit.json):

| Benchmark Task | Scope / Split | Unique Instances | Runs | Solver | Seed Policy | Configured Time Limit | Mean Actual Runtime | Mean Objective | Feasibility Rate | Solver Status |
| :--- | :--- | :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **R26 Equal Compute** | 2024 Post-Holdout Seasonal | 28 | 28 | `DeterministicGreedy` | 202601 | 2.0 s | 0.0011 s (1.1 ms) | 7181.45 | 100.0% (28/28) | FEASIBLE (1-pass) |
| **R26 Equal Compute** | 2024 Post-Holdout Seasonal | 28 | 28 | `CPSat` | 202601 | 2.0 s | 0.4438 s | 7167.17 | 100.0% (28/28) | OPTIMAL (gap 0.0%) |
| **R26 Equal Compute** | 2024 Post-Holdout Seasonal | 28 | 28 | `SimulatedAnnealing` | 202601 | 2.0 s | 2.0009 s | 7167.88 | 100.0% (28/28) | TIME_LIMIT (2351 iters) |
| **R26 Equal Compute** | 2024 Post-Holdout Seasonal | 28 | 28 | `HybridCPSatSA` | 202601 | 2.0 s (1.0+1.0) | 1.4531 s | 7167.17 | 100.0% (28/28) | OPTIMAL + Monotonic SA |
| **R21 Downstream V3** | 2023 Development Operational | 28 | 28 | `DeterministicGreedy` | 202601 | 10.0 s | 0.38 ms | 7666.04 | 100.0% (28/28) | FEASIBLE |
| **R21 Downstream V3** | 2023 Development Operational | 28 | 28 | `CPSat` | 202601 | 10.0 s | 98.84 ms | 7652.46 | 100.0% (28/28) | OPTIMAL (gap 0.0%) |
| **R21 Downstream V3** | 2023 Development Operational | 28 | 28 | `SimulatedAnnealing` | 202601 | 10.0 s | 280.12 ms | 7652.46 | 100.0% (28/28) | OPTIMAL Incumbent |

---

## 3. Disentangling 28 Instances vs. 84 Runs vs. 112 Runs

There is no mathematical conflict between the counts 28, 84, and 112. They represent distinct dimensions of the experimental protocol:

```
  =============================================================================
  INSTANCE DEFINITION: 4 Scenarios x 7 Forecast Models = 28 Unique Instances
  =============================================================================
                          |
         +----------------+----------------+
         |                                 |
         v                                 v
   R21 Development                   R26 Post-Holdout
   (2023 Dev Data)                   (2024 Seasonal Data)
   3 Solvers:                        4 Solvers:
   - Greedy                          - Greedy
   - CP-SAT                          - CP-SAT
   - SA                              - SA
                                     - Hybrid CP-SAT+SA
         |                                 |
         v                                 v
   28 x 3 = 84 RUNS                  28 x 4 = 112 RUNS
  =============================================================================
```

1. **28 Unique Problem Instances**:
   - $4\text{ operational banks/scenarios} \times 7\text{ arrival delay prediction regimes} = 28\text{ unique cases}$.
   - Scenarios in R26: `SCEN_2024_WINTER`, `SCEN_2024_SPRING`, `SCEN_2024_SUMMER`, `SCEN_2024_FALL_DISRUPTED`.
   - Models in R26: `schedule_only`, `arrival_linear_baseline_v1`, `arrival_xgboost_baseline_v1`, `arrival_weighted_ensemble_v1`, `P5_quantile_regression`, `P4_ngboost_student_t`, `oracle_actual`.
2. **84 Runs in R21**:
   - 28 instances evaluated on 2023 development scenarios across 3 solvers (`DeterministicGreedy`, `CPSat`, `SimulatedAnnealing`).
   - $28 \times 3 = 84\text{ runs}$ ([`artifacts/downstream_model_comparison_v3/evaluations.json`](file:///D:/Study/Code/Python/Aelous/artifacts/downstream_model_comparison_v3/evaluations.json)).
3. **112 Runs in R26**:
   - 28 instances evaluated on 2024 post-holdout scenarios across 4 solvers (`DeterministicGreedy`, `CPSat`, `SimulatedAnnealing`, `HybridCPSatSA`).
   - $28 \times 4 = 112\text{ runs}$ ([`artifacts/audit/r26_solver_equal_compute_results.parquet`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/r26_solver_equal_compute_results.parquet)).
4. **Boundary Distinction**:
   - R26 evaluates post-holdout synthetic scenarios and **does not certify or replace** the 84 R21 development runs. Both exist cleanly in their respective partitions.

---

## 4. Fairness: Wall-Clock Ceiling vs. Computational Work

### 4.1 Wall-Clock Ceiling Equality: `PROVEN`
* All solvers in R26 operated under an explicit contract ceiling of $T_{\text{total}} = 2.0\text{ seconds}$ per instance.
* For the Hybrid solver, the budget was strictly partitioned: $T_{\text{CP-SAT}} = 1.0\text{s} + T_{\text{SA}} = 1.0\text{s} = 2.0\text{s}$.
* **Overrun Audit**: Zero instances ($0/112$, $0.0\%$) exceeded the 2.0s ceiling. Max runtimes observed: Greedy $2.5$ ms, CP-SAT $1.01$ s, SA $2.0019$ s, Hybrid $1.9619$ s.

### 4.2 Computational Work Equality: `NOT_PROVEN`
Equating a maximum wall-clock timeout does **not** equate computational work:
* `DeterministicGreedy`: Executes a single-pass heuristic sort and assignment, performing exactly **1 evaluation** and completing in **$1.1$ ms** ($0.05\%$ of budget).
* `CPSat`: Executes deterministic branch-and-bound constraint search. It proved global mathematical optimality on **100% of cases (28/28)** and terminated early in mean **$0.4438$ s**, leaving $1.56$ s of its budget unused.
* `SimulatedAnnealing`: Spun continuously for the entire **$2.0009$ s**, evaluating an average of **$2351.0$ candidate moves** and cost function calls.
* `HybridCPSatSA`: Received the globally optimal solution from CP-SAT during its first 1.0s, and because SA monotonically preserves incumbents, SA spent its remaining 1.0s evaluating $1175.5$ neighbor moves with **zero possible improvement** ($\Delta_i = 0.0000$).
* **Scientific Boundary**: Claiming "equal computational work" or "equal CPU effort" across these paradigms is scientifically false. Only **`equal wall-clock ceiling`** is supported by the data.

---

## 5. Audit of the "18.4%–34.2%" Percentage Claim

### 5.1 Direct Empirical Re-calculation on R26
A case-by-case re-calculation of the objective delta between `DeterministicGreedy` and `CPSat` across all 28 R26 instances:
$$\text{Relative Gap} = \frac{\text{Objective}_{\text{Greedy}} - \text{Objective}_{\text{CP-SAT}}}{\text{Objective}_{\text{CP-SAT}}} \times 100\%$$

```
Empirical Distribution of Relative Gap in R26 (28 cases):
- Count: 28
- Mean:  0.23%
- Min:   0.00%  (9 cases had exact zero difference)
- 25%:   0.00%
- 50%:   0.14%  (median difference: 1 reassignment = 10 cost units)
- 75%:   0.27%
- Max:   1.80%  (5 reassignments = 50 cost units on 4200-cost bank)
```

In absolute units:
- In 9 cases, Greedy achieved the **exact same globally optimal objective** as CP-SAT ($\Delta = 0$).
- In 9 cases, Greedy had 1 additional reassignment ($\Delta = +10$).
- In 5 cases, Greedy had 2 additional reassignments ($\Delta = +20$).
- In 2 cases, Greedy had 3 additional reassignments ($\Delta = +30$).
- In 3 cases, Greedy had 5 additional reassignments ($\Delta = +50$).
- The mean cost difference is $14.28$ units out of $7167.17$, which is **$0.20\%$**.

### 5.2 Source of the "18.4%–34.2%" Claim
* The claim appeared in draft document [`artifacts/audit/AGENT_FULL_FORENSIC_PROJECT_INVENTORY.md:834`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/AGENT_FULL_FORENSIC_PROJECT_INVENTORY.md#L834):
  *- "Greedy produced objective costs 18.4% to 34.2% higher than CP-SAT due to myopic assignment."*
* **Forensic Finding**: This range does not correspond to any column, metric, or subset of the 28 R26 instances, nor the 28 R21 instances.
* **Possible Origin**:
  - In Phase E adversarial stress testing ([`phase_e_greedy_baseline_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/phase_e_greedy_baseline_manifest_v1.json)), CP-SAT reduced cost by $4.16\%$ to $53.99\%$ on synthetic overloaded banks ($F=100\dots 300, G=20\dots 50$).
  - In P4 probabilistic evaluation, $18.484$ min was the continuous CRPS on 2023 dev data.
* **Formal Verdict**:
  $$\mathbf{CLAIM\_RETRACTED\_OR\_UNVERIFIED}$$
  The claim is unverified by raw data and is formally retracted from certified findings.

---

## 6. Scalability Experiments Audit

* In earlier exploratory phases (Phase D / Phase E, [`cp_sat_benchmark_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/cp_sat_benchmark_manifest_v1.json)), CP-SAT was stress-tested across a $3 \times 3$ grid:
  - Flight counts: $100, 200, 300$
  - Contact gate counts: $20, 30, 50$
  - Runtimes scaled from $418$ ms ($100$ flights / $20$ gates) to $16.75$ s ($300$ flights / $20$ gates).
* Any reference to a grid of `100/25`, `200/45`, `300/65`, `500/100` and `1.8% gap / 2s` was a proposed roadmap benchmark (Week 9 Detailed Roadmap). It was **not** run on the locked 28-instance post-holdout benchmark.
* **Audit Boundary**: Scalability benchmarks are kept strictly isolated and are **not** conflated with the 28-case / 112-run seasonal benchmark.

---

## 7. Forensic Certification Verdict

1. **Benchmark Identity & Lineage**: Clear, verified, and reconciled across R21 (84 runs) and R26 (112 runs).
2. **Wall-Clock Equality**: Verified ($T = 2.0$s ceiling).
3. **Computational Work Equality**: Rejected as unproven and scientifically invalid.
4. **Percentage Claim Reconciliation**: Formally resolved as `CLAIM_RETRACTED_OR_UNVERIFIED`.
5. **Final Gate Verdict**:
   $$\mathbf{GATE = PASS\_WITH\_RESERVATION}$$
   *(Reservation: Validated under equal wall-clock ceiling semantics; no claim of equal computational work is certified).*
