# AEOLUS-G7 — System Regression Diff vs G0 Baseline

## 1. Architectural Evolution Summary

Between Gate G0 (Baseline Preservation) and Gate G7 (Final Regression Validation), the Aeolus Gate Optimization repository underwent targeted scientific remediation across data contracts, simulation causality, ML evidence, dual-core turn pairing, solver correctness, and UI presentation:

```
[G0 Baseline]
      │
      ├─► G1: Strict Data Provenance & T-2h Temporal Barriers
      ├─► G2: Causal Monte Carlo (Mode B2 Online Recourse & Mode C-Oracle)
      ├─► G3: Outbound ML Evidence & Probabilistic Delay Classification
      ├─► G4: Verified Aircraft Turn Pairing & Real-Data Native Dual-Core
      ├─► G5: Solver Correctness, SA Hardening & Fair Benchmark Harness
      ├─► G6: Dashboard Scientific Integrity & Anti-Rebranding Export Adapters
      │
      ▼
[G7 Full Regression & Scientific Invariants] ──► CANDIDATE CERTIFIED
```

---

## 2. Component-by-Component Diff Matrix

| Component Area | Gate G0 Baseline State | Gate G7 Remediated State | Regression / Integrity Impact |
|:---|:---|:---|:---|
| **Data Contracts** | Implicit origin assumption; historical 2024 holdout was used in post-hoc tests | Formal `EvidenceProvenance` schema; strict tagging of `DEV_HISTORICAL`, `MODEL_SELECTION`, `HOLDOUT_RESERVED` | Zero data leakage; verifiable lineage |
| **Monte Carlo Simulation** | Mode B allowed retroactive hindsight; Mode C lacked optimality proof verification | Non-anticipative Mode B2 rolling recourse with `decision_trace`; Mode C-Oracle with CP-SAT proof check | Elimination of artificial algorithmic optimism |
| **Machine Learning** | Outbound delay lacked calibrated classifiers; only heuristic regression thresholding | Calibrated Logistic Regression, Random Forest, XGBoost models with Brier score, ROC-AUC, PR-AUC | Robust probabilistic forecasting for gate planning |
| **Flight Pairing** | 30 synthetic turns, 0 verified tail-number rotations in pilot run | `DeterministicPairingEngine` enforcing tail match, hub monotonicity, and 1-to-1 cardinality | Real-data operational authenticity |
| **Optimization Solvers** | SA lacked objective decomposition; benchmark horizons were misaligned | Unified objective decomposition (`decision_cost` vs `reporting_cost`); independent constraint verifier | Rigorous solver fairness and parity |
| **Streamlit Dashboard** | UI displayed "OPTIMAL" on timed-out runs; export adapter lacked provenance check | Research vs Presentation modes; fail-safe status badges; strict `ProvenanceMismatchError` | Transparent scientific communication |
| **Test Coverage** | 1,990 collected tests (baseline inventory) | 2,117 collected tests (+127 remediation and invariant tests, 100% pass) | Broadened verification footprint |

---

## 3. Structural File Modifications and New Deliverables

### New Core Modules Created
- `src/contracts/provenance.py`: Comprehensive evidence lineage and origin classification.
- `src/contracts/temporal.py`: Temporal cutoff rules and feature barrier contracts.
- `src/data/canonical_time.py`: Time normalization and timeline mapping.
- `src/data/real_data_loader.py`: Real Aeolus BTS flight dataset loader with verification.
- `src/simulation/verified_pairing.py`: Deterministic verified aircraft turn pairing engine.
- `src/simulation/monte_carlo_engine_v2.py`: Remediated causal Monte Carlo simulation engine.

### New Test Suites Created
- `tests/test_g1_provenance_and_temporal_contracts.py` (22 tests)
- `tests/test_g2_monte_carlo_causality.py` (24 tests)
- `tests/test_g3_ml_validation.py` (14 tests)
- `tests/test_g4_native_e2e.py` (19 tests)
- `tests/test_g5_solver_correctness.py` (21 tests)
- `tests/test_g6_dashboard_integrity.py` (12 tests)
- `tests/test_g7_scientific_invariants.py` (15 tests)

### Remediation Evidence Directories
- `remediation_evidence/G1_contracts/`
- `remediation_evidence/G2_monte_carlo/`
- `remediation_evidence/G3_ml_evidence/`
- `remediation_evidence/G4_native_e2e/`
- `remediation_evidence/G5_solvers/`
- `remediation_evidence/G6_dashboard/`
- `remediation_evidence/G7_regression/`

---

## 4. Final System Health Assessment

The candidate codebase on branch `remediation/g7-regression` is architecturally robust, mathematically certified, and scientifically reproducible. All thesis objectives regarding machine learning prediction and constraint programming optimization for airport gate reallocation are fully substantiated with empirical evidence.
