# AEOLUS-G4 — DELIVERABLE 10: REAL-DATA END-TO-END RUN EXECUTION REPORT

## 1. Scenario Definition & Pre-Registration

To ensure scientific reproducibility and avoid post-hoc selection bias, the evaluation scenario was pre-registered prior to execution:
- **Target Hub Airport:** Hartsfield-Jackson Atlanta International Airport (`ATL`).
- **Operational Date:** **November 23, 2023 (Thanksgiving Day)** — one of the highest operational demand periods of the year at ATL.
- **Flight Scope:** 100 Real Inbound Flights (`DEST == 'ATL'`) + 100 Real Outbound Flights (`ORIGIN == 'ATL'`) = **200 Raw Flight Legs**.
- **Airport Topology:** **30 Contact Gates** (`G01` to `G30`) + **5 Finite Remote Overflow Stands** (`OVERFLOW_STAND_01` to `05`).
- **Separation Buffer:** $B_{\text{buffer}} = 15$ minutes.
- **Minimum Turnaround:** $T_{\text{turn}} = 45$ minutes.
- **Default Dwell:** $T_{\text{dwell}} = 60$ minutes for unpaired legs.

---

## 2. Multi-Solver Benchmark Results (Strict REAL_ONLY Mode, N = 200 Legs, 200 Gate Jobs)

In strict `REAL_ONLY` mode, without unauthenticated tail fabrication, the 200 real flight legs are modeled as 200 independent gate-occupying jobs (100 arrival turns + 100 departure turns) across 30 contact gates.

All three certified solvers were executed end-to-end and audited by the independent hard-constraint verifier:

| Performance Metric | CP-SAT Solver (Exact) | Deterministic Greedy | Hybrid Solver (Greedy + Local) |
| :--- | :---: | :---: | :---: |
| **Solver Status** | **`OPTIMAL`** | **`FEASIBLE`** | **`OPTIMAL`** |
| **Feasible Solution Found?** | **YES** | **YES** | **YES** |
| **Solver Objective Value** | **$0.0000$** | **$0.0000$** | **$0.0000$** |
| **Independent Re-evaluated Objective** | **$0.0000$** | **$0.0000$** | **$0.0000$** |
| **Independent Verifier Verdict** | **`PASS`** | **`PASS`** | **`PASS`** |
| **Planned Gate Conflicts** | **0** | **0** | **0** |
| **Hard Constraint Violations** | **0** | **0** | **0** |
| **Total Jobs Assigned** | 200 / 200 (100%) | 200 / 200 (100%) | 200 / 200 (100%) |
| **Contact Gate Assignments** | 200 | 200 | 200 |
| **Remote Apron Assignments** | 0 | 0 | 0 |
| **Unassigned Flights** | 0 | 0 | 0 |
| **Solver Execution Runtime** | **$1,310$ ms ($1.31$s)** | **$47$ ms ($0.05$s)** | **$20,390$ ms ($20.39$s)** |
| **Artifact Directory** | [`artifacts/.../g4_pilot/`](file:///D:/Study/Code/Python/Aelous/artifacts/remediation/native_dual_core_g4_pilot/) | [`artifacts/.../g4_pilot_greedy/`](file:///D:/Study/Code/Python/Aelous/artifacts/remediation/native_dual_core_g4_pilot_greedy/) | [`artifacts/.../g4_pilot_hybrid/`](file:///D:/Study/Code/Python/Aelous/artifacts/remediation/native_dual_core_g4_pilot_hybrid/) |

### Observations:
1. **Zero Conflict Optimality:** With 30 contact gates distributed over a 24-hour schedule window, all 200 flight legs fit into contact gates with zero temporal overlap, achieving an optimal objective value of $0.0000$ across all solvers.
2. **Computational Speed:** The Deterministic Greedy solver completed assignment in only $47$ milliseconds, while CP-SAT achieved proven optimality in $1.31$ seconds.
3. **Verifier Agreement:** For 100% of the solvers, the independent verifier confirmed that `conflict_count == 0` and `hard_constraint_violations_count == 0`.

---

## 3. Inferred Schedule Pairing Benchmark (N = 200 Legs, 141 Gate Jobs)

When `--allow-inferred-pairing` was enabled to explore schedule continuity (same carrier, chronological dwell between 45m and 180m):
- **Raw Legs Processed:** 200 (100 ARR + 100 DEP).
- **Verified Rotations:** 0 (Truthfully labeled: no tail tracking).
- **Inferred Pairs:** **59 paired turns** (linking 59 arrival legs directly to 59 departure legs).
- **Unmatched Inbound:** **41 arrival turns**.
- **Unmatched Outbound:** **41 departure turns**.
- **Total Gate Allocation Jobs:** **141 jobs** ($59 + 41 + 41 = 141$).
- **CP-SAT Solver Execution:**
  - Status: `OPTIMAL`.
  - Feasible: `True`.
  - Objective: $0.0000$.
  - Conflicts: 0.
  - Hard Violations: 0.
  - Verifier: `PASS`.
  - Artifact Directory: [`artifacts/remediation/native_dual_core_g4_pilot_inferred/`](file:///D:/Study/Code/Python/Aelous/artifacts/remediation/native_dual_core_g4_pilot_inferred/).

---

## 4. Full Evidence Lineage Verification

Every output directory contains the complete quartet of certified artifacts:
1. `run_manifest.json`: Configuration, cryptographic model hashes, runtime timestamps, and optimization metrics.
2. `predictions_sample.csv`: Standardized 14-field prediction contract records for all flights with native model SHA-256 provenance.
3. `turn_pairing_audit.json`: Pair-by-pair validation summary, linkage sources, and sample turn records.
4. `optimization_result.json`: Solver status, objective value, runtime ms, gate assignments, and diagnostic reports.
5. `integration_test_report.json`: Official PASS/FAIL verification verdict.
