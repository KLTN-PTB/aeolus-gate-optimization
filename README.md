# Aeolus Probabilistic Core Arrival & Gate Optimization — V4

[![Certification Status](https://img.shields.io/badge/Certification-CERTIFIED__WITH__LIMITATIONS-blue.svg)](docs/audit/FINAL_EVIDENCE_CERTIFICATION_V5.md)
[![Regression Tests](https://img.shields.io/badge/Tests-180%2F180%20PASSED-success.svg)](tests/)
[![Python Version](https://img.shields.io/badge/Python-3.11.15-informational.svg)](configs/seed_registry.yaml)
[![Architecture Protocol](https://img.shields.io/badge/Protocol-V4.0%20Dual%20Prediction-orange.svg)](docs/decisions/decision_dual_prediction_architecture_v4.md)
[![Branch](https://img.shields.io/badge/Branch-v4--final--forensic--certification-brightgreen.svg)](https://github.com/KLTN-PTB/aeolus-gate-optimization/tree/v4-final-forensic-certification)

> **Official Release State**: The Aeolus research program has achieved **Phase R37 Final Forensic Certification V5** with status **`CERTIFIED_WITH_LIMITATIONS`**. All empirical claims across 13 scientific domains and 13 claim boundaries have been audited against raw on-disk artifacts and validated by a 180-test regression harness.

---

## 1. Executive Summary & Research Workflow

Aeolus investigates whether machine-learned flight arrival delay forecasts—evaluated under point, quantile, and parametric continuous probabilistic representations—can measurably improve airport flight-to-gate assignment schedules relative to conventional heuristic dispatch.

The research framework operates strictly under the **Predict $\to$ Simulate $\to$ Optimize $\to$ Evaluate** operational loop:

```text
[BTS Inbound Traffic DEST=ATL] (T - 2h cutoff)
           │
           ▼
┌────────────────────────────────────────────────────────┐
│               PREDICTION ARCHITECTURE                  │
│  • Point Regression: Ridge, HistGB, XGBoost, Ensemble  │
│  • Probabilistic Quantiles: P5 (9-Quantile Multi-LGBM) │
│  • Parametric Continuous: P4 (Student-T NGBoost)       │
└────────────────────────────────────────────────────────┘
           │ (Scalar delay forecast or generative draws)
           ▼
┌────────────────────────────────────────────────────────┐
│            SYNTHETIC TURN SIMULATION (ATL)             │
│  • Turn synthesis, buffer violations & conflict check  │
│  • Downstream operational scenarios (30-70 flights)    │
└────────────────────────────────────────────────────────┘
           │
           ▼
┌────────────────────────────────────────────────────────┐
│            GATE ASSIGNMENT OPTIMIZATION                │
│  • Deterministic Greedy (1.1 ms baseline)              │
│  • Google OR-Tools CP-SAT (Branch-and-Bound, T=2.0s)   │
│  • Simulated Annealing (Stochastic Local Search, 2.0s) │
│  • Hybrid CP-SAT + SA (Sequential Composition, 2.0s)   │
└────────────────────────────────────────────────────────┘
           │
           ▼
┌────────────────────────────────────────────────────────┐
│       FORENSIC RECONCILIATION & CERTIFICATION          │
│  • 13 Claim Boundaries audited & locked                │
│  • 180 regression tests (100% PASS)                    │
│  • Final Status: CERTIFIED_WITH_LIMITATIONS            │
└────────────────────────────────────────────────────────┘
```

---

## 2. Certified Core Experimental Results

### 2.1. Arrival Delay Prediction (Post-Holdout Calendar Year 2024)
Evaluated post-freeze under strict `POST_HOLDOUT` governance on $N = 5,000$ commercial passenger flights arriving at Atlanta Hartsfield-Jackson (`DEST = 'ATL'`), with feature cutoff at $t_{\text{cutoff}} = \text{CRS\_DEP\_TIME} - 2\text{ hours}$:

| Model ID | Formal Role | MAE (min) | Exact CRPS (min) | Quantile CRPS Approx (min) | Pinball Loss (min) | Exact NLL |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`arrival_linear_baseline_v1` (Ridge)** | Point Co-Champion (Dev 2023) | **22.9125** | — | — | — | — |
| **`arrival_xgboost_baseline_v1`** | Point Benchmark | 24.3643 | — | — | — | — |
| **`arrival_weighted_ensemble_v1`** | Point Co-Champion (Dev 2023) | 23.3175 | — | — | — | — |
| **`P5_quantile_regression`** | Probabilistic Champion (9 quantiles) | 21.6881 | — | **16.7724** | **6.8211** | N/A |
| **`P4_ngboost_student_t`** | Parametric Continuous Density | 23.2359 | **17.6532** | — | — | **4.6307** |
| **`oracle_actual`** | Acausal Theoretical Bound | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — |

*Forensic Clarifications*:
- **P4 Student-T**: Lineage audited in Phase R33. Implements analytical continuous Student-T CRPS (Jordan et al., 2019) and exact continuous NLL. Empirical calibration is disclaimed (`NOT_SEPARATELY_CERTIFIED`).
- **P5 Quantile**: Audited in Phase R34. Strictly a 9-quantile estimator (`[0.025, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.975]`). The $16.77$ min holdout metric ($16.85$ min dev) is `CRPS_QUANTILE_APPROXIMATION` (pinball loss is $6.82$ min). Continuous density/sampling is `NOT_AVAILABLE`.
- **Decoupled Roles**: Point regression and weighted ensemble tied on 2023 dev within the 0.10-min band ($|\Delta| = 0.00045$ min) but did not tie on 2024 holdout ($|\Delta| = 0.405$ min). No single overall champion is asserted.

---

### 2.2. Downstream Gate Assignment Solvers (2024 Seasonal Scenarios)
Evaluated across 28 synthetic operational cases ($4\text{ scenarios} \times 7\text{ models} = 112\text{ runs}$) under an identical wall-clock ceiling $T_{\text{total}} = 2.0$ seconds:

| Solver | Budget Type | Configured Limit | Mean Actual Runtime | Hard Feasibility | Realized Conflicts | Mean Cost Objective | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`DeterministicGreedy`** | `WALL_CLOCK` | 2.0 s | **0.0011 s (1.1 ms)** | 100% (28/28) | 0 | 7181.45 | FEASIBLE |
| **`CPSat`** | `WALL_CLOCK` | 2.0 s | **0.4438 s** | 100% (28/28) | 0 | **7167.17** | **OPTIMAL (28/28)** |
| **`SimulatedAnnealing`** | `WALL_CLOCK` | 2.0 s | 2.0009 s | 100% (28/28) | 0 | 7167.88 | FEASIBLE |
| **`HybridCPSatSA`** | `SPLIT_WALL_CLOCK` | 2.0 s (1.0+1.0) | 1.4531 s | 100% (28/28) | 0 | **7167.17** | FEASIBLE |

*Solver Fairness Semantics (R35 Audit)*:
- **`WALL_CLOCK_EQUALITY = PROVEN`**: All four solvers operate within the uniform 2.0s envelope.
- **`COMPUTATIONAL_WORK_EQUALITY = NOT_PROVEN`**: Computational operations are fundamentally disparate ($O(N \log M)$ heuristics vs. branch-and-bound search vs. stochastic local moves).
- **Hybrid Zero Marginal Gain**: In 100% of cases ($28/28$), $\Delta_i = \text{Hybrid} - \text{CP-SAT} = 0.0000$ because CP-SAT achieves proven global optimality within its 1.0s sub-budget, leaving monotonic SA unable to find any strictly better feasible solution.

---

## 3. Strict Epistemological Boundaries & Disclaimers

In accordance with Phase R36 and R37 certification standards, the following 8 claims are **BLOCKED** and strictly disclaimed:

1. **No Single Overall Champion**: Point, quantile, and continuous models serve distinct mathematical roles; asserting an overall benchmark winner is prohibited.
2. **No Oracle Equivalence**: Predictive models do not match the post-hoc realized delay Oracle bound.
3. **No Real Airfield Operations**: Evaluations are conducted in a synthetic simulation environment; no claims of live deployment at Atlanta (ATL) or airline cost savings are made.
4. **No Actual Delay Reductions**: Algorithms optimize schedule buffer assignments; they do not alter physical flight movements.
5. **Contained Reproducibility Only**: Bit-for-bit repeatability is certified strictly within Python 3.11.15 on Windows AMD64 with the pinned virtual environment; universal cross-platform bit identity is disclaimed.
6. **No 82.4% CRN Variance Reduction**: Theoretical Common Random Numbers variance reduction is marked unestablished on the gate assignment objective.
7. **No Mathematical Optimal Sample Size**: Monte Carlo $N = 500$ is an operational budget choice, not a proven asymptotic optimum.
8. **No Universal Ineffectiveness of SA**: Simulated Annealing's $\Delta = 0.0$ applies to the audited cases where CP-SAT achieved global optimality; heuristics remain valuable for open or large-scale instances.

---

## 4. Quickstart: Reproducing Certified Verification Gates

### Prerequisites
- Python `3.11.15` (Windows AMD64)
- Git 2.40+

### Setup & Test Execution
```powershell
# 1. Clone repository and checkout certified branch
git clone https://github.com/KLTN-PTB/aeolus-gate-optimization.git
cd aeolus-gate-optimization
git checkout v4-final-forensic-certification

# 2. Activate virtual environment
.\.venv\Scripts\Activate.ps1

# 3. Execute full 180-test forensic regression suite (Runtime: ~5.0 seconds)
python -m pytest tests/test_r25_point_selection_consistency.py `
                 tests/test_r26_solver_equal_compute.py `
                 tests/test_r27_certification_hardening.py `
                 tests/test_r28_probabilistic_audit.py `
                 tests/test_r29_execution_provenance.py `
                 tests/test_r30_final_reconciliation.py `
                 tests/test_r31_final_certification.py `
                 tests/test_r33_p4_metric_lineage.py `
                 tests/test_r34_p5_mathematical_audit.py `
                 tests/test_r35_solver_repro.py `
                 tests/test_r36_final_reconciliation.py `
                 tests/test_r37_final_certification.py -q
```
**Expected Outcome**: `180 passed in 4.93s` (100% clean pass rate).

---

## 5. Authoritative Documentation Roadmap

For detailed investigations, consult the specialized documentation directory:

- 📜 **Master Documentation Index**: [`docs/README.md`](docs/README.md)
- 🏛️ **Final Certification Manifest (V5)**: [`docs/audit/FINAL_EVIDENCE_CERTIFICATION_V5.md`](docs/audit/FINAL_EVIDENCE_CERTIFICATION_V5.md)
- ⚖️ **Final Evidence Reconciliation (V2)**: [`docs/audit/FINAL_EVIDENCE_RECONCILIATION_V2.md`](docs/audit/FINAL_EVIDENCE_RECONCILIATION_V2.md)
- 🔍 **Targeted Audits**:
  - P4 Metric Lineage: [`docs/audit/R33_P4_METRIC_LINEAGE.md`](docs/audit/R33_P4_METRIC_LINEAGE.md)
  - P5 Quantile & Math: [`docs/audit/R34_P5_MATHEMATICAL_AUDIT.md`](docs/audit/R34_P5_MATHEMATICAL_AUDIT.md)
  - Solver & Environment: [`docs/audit/R35_SOLVER_REPRODUCIBILITY_AUDIT.md`](docs/audit/R35_SOLVER_REPRODUCIBILITY_AUDIT.md)
- 📐 **System State & Architectural Invariants**: [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md)
- 🗺️ **Repository Directory Layout**: [`project_structure.md`](project_structure.md)
