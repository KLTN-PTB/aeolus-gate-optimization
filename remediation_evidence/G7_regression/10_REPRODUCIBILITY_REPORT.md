# AEOLUS-G7 — Deterministic Reproducibility Verification Report

## 1. Executive Summary

To satisfy Task `G7.6` and guarantee scientific reproducibility, a dedicated verification harness (`scripts/verify_reproducibility_g7.py`) was executed across 6 representative workloads. Each workload was executed in two independent, sequential runs with fixed seeds and configurations.

- **Verification Verdict**: **OVERALL PASS**
- **Deterministic Workloads**: 6 of 6 (100%)
- **Bitwise / Numeric Match**: 100%

---

## 2. Multi-Run Workload Comparison

| Workload ID | Workload Domain | Run 1 Metric / Hash | Run 2 Metric / Hash | Parity Status |
|:---|:---|:---|:---|:---:|
| **WL-1** | Native Inference Sample | SHA: `a6a923dc...0b1d` | SHA: `a6a923dc...0b1d` | **BITWISE EQUAL** |
| **WL-2** | Verified Aircraft Turn Pairing | 2 pairs (`TURN_0001`, `TURN_0002`) | 2 pairs (`TURN_0001`, `TURN_0002`) | **STRUCTURALLY EQUAL** |
| **WL-3** | Small Solver Benchmark | CP-SAT: 10.0, Greedy: 20.0 | CP-SAT: 10.0, Greedy: 20.0 | **NUMERICALLY EQUAL** |
| **WL-4** | Monte Carlo Pilot (10 Realizations) | Hash: `49ff6cb8...b723` | Hash: `49ff6cb8...b723` | **BITWISE EQUAL** |
| **WL-5** | Metric Recomputation | Obj: 0.0, IsValid: `True` | Obj: 0.0, IsValid: `True` | **NUMERICALLY EQUAL** |
| **WL-6** | Dashboard Export (JSON & CSV) | JSON SHA: `241394...eb7c`<br>CSV SHA: `5a2ec7...da54` | JSON SHA: `241394...eb7c`<br>CSV SHA: `5a2ec7...da54` | **BITWISE EQUAL** |

---

## 3. Workload Details & Technical Invariants

### WL-1: Native Inference Sample
- Evaluates pseudo-random feature extraction and model inference pipeline.
- Both runs generated identical array buffers with SHA-256: `a6a923dc70cc5cc7f078bacac60adbf4bb52d35985dee0db431e0772fa8b0b1d`.

### WL-2: Verified Aircraft Turn Pairing
- Evaluates `DeterministicPairingEngine` across arrival and departure flight legs.
- Pairing engine produced identical turn IDs, leg linkages, and turnaround durations across both runs.

### WL-3: Small Solver Benchmark
- Evaluates `CPSatGateSolver` and `DeterministicGreedyGateSolver` on micro problem instance.
- CP-SAT optimal objective is exactly 10.0 in both runs. Greedy objective is exactly 20.0 in both runs. All flight-to-gate assignments are identical.

### WL-4: Monte Carlo Scenario Pilot
- Evaluates `MonteCarloScenarioGenerator` with calibrated Student-t and Gaussian Copula sampling ($N=10$, $\rho=0.45$, `seed=42`).
- Generated 10 realizations. Realization hashes across all 10 scenarios matched bit-for-bit between Run 1 and Run 2.

### WL-5: Metric Recomputation
- Evaluates independent hard constraint verifier and decomposed objective evaluator.
- Both runs yielded identical zero decision cost, zero conflicts, and `is_valid == True`.

### WL-6: Dashboard Export
- Evaluates serialization of `export_run_manifest_to_json` and `export_assignments_to_csv`.
- Generated JSON payload has identical SHA-256 `24139406ccae5c6da84714fe1d5174479004e07883a48fbea78e2bab7d5deb7c`.
- Generated CSV payload has identical SHA-256 `5a2ec7789430e79562e48fb4c3294ad8b8c0917c6fc4479cf169781c1c09da54`.

---

## 4. Machine-Readable Evidence File

The authoritative raw execution output is stored in:
`remediation_evidence/G7_regression/reproducibility_harness_output.json`
