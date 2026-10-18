# AEOLUS-G8 — Final Scientific Release Audit: Scope and Baseline Report

## 1. Executive Summary & Audit Mandate

- **Audit Identifier**: `AEOLUS-G8`
- **Gate Title**: Independent Scientific Release Audit & Final Certification Gate
- **Target Repository**: `aeolus-gate-optimization`
- **Audit Branch**: `remediation/g7-regression`
- **Evaluated Commit SHA**: `c95caef53808a561b1a7d3a5a09399cc52f754f5`
- **Audit Date**: 2026-10-11
- **Auditor Roles**: Independent Scientific Auditor, Principal Software Architect, Machine Learning Reviewer, Operations Research Reviewer, Academic Quality Assurance Lead
- **Overall Release Verdict**: **`ACCEPTED_WITH_LIMITATION`**

This gate represents the definitive independent audit of the remediation campaign (Gates G0 through G7) for the Bachelor of Science in Information Technology thesis:
> *"Ứng dụng học máy và lập trình ràng buộc trong dự báo độ trễ chuyến bay và tối ưu tái phân bổ cổng đỗ tàu bay"*

This audit enforces strict read-only evaluation. No source code, tests, model weights, or experimental figures were altered or manufactured during this audit.

---

## 2. Release Candidate Baseline & Change Inventory

### 2.1 Git Repository State
- **Active Working Branch**: `remediation/g7-regression`
- **Head Commit SHA**: `c95caef53808a561b1a7d3a5a09399cc52f754f5`
- **Commit Subject**: `feat: integrate native dual-core, ML validation, Monte Carlo engine and operational dashboard`
- **Remote Origin**: `https://github.com/mrhao165-del/aeolus-gate-optimization.git`

### 2.2 Working Tree Modifications Audit
An inspection of `git status --short` and `git diff --stat` confirms that tracked file modifications are limited to 8 operational integration files, plus the normalized byte restoration of `src/contracts/__init__.py`:

| File Path | Insertion / Deletion Lines | Issue / Remediation Requirement Addressed |
|:---|:---:|:---|
| `dashboard/adapters/export_adapter.py` | +37 / -7 | **G6 Anti-Rebranding Guard**: Blocks synthetic runs claiming `REAL_AEOLUS`. |
| `dashboard/core/config.py` | +61 / -17 | **G6 Security Hardening**: Canonical path containment for model/artifact dirs. |
| `dashboard/core/contracts.py` | +33 / -7 | **G6 View Model Mapping**: Adds `SolverRunView` and `is_optimal_proven` mapping. |
| `dashboard/services/scenario_service.py` | +57 / -14 | **G1/G6 Provenance Verification**: Rejects unverified scenario loading. |
| `scripts/run_native_dual_core_pipeline.py`| +212 / -130 | **G4 Real-Data Integration**: Thanksgiving 2023 ATL real-data execution harness. |
| `src/contracts/__init__.py` | +0 / -0 (Normalized) | **G7 Baseline Preservation**: Restored exact frozen byte hash (`77f77d2f...`). |
| `src/contracts/turn_contracts.py` | +3 / -1 | **G4 Turn Model Verification**: Normalization of `FlightLeg` and `TurnPair`. |
| `src/data/pairing_validator.py` | +3 / -0 | **G4 Pairing Guard**: Tail number validation helper. |
| `src/simulation/dual_prediction_turn.py` | +2 / -1 | **G4 Dual Core Linkage**: Arrival/Departure prediction turn integration. |

### 2.3 New Certified Modules & Test Suites
The remediation campaign introduced 6 core architectural modules and 7 dedicated test suites:
- **Core Modules**:
  1. `src/contracts/provenance.py` (Data origin & evidence lineage)
  2. `src/contracts/temporal.py` (Temporal cutoff contracts & T-2h barrier)
  3. `src/data/canonical_time.py` (Monotonic timeline normalization)
  4. `src/data/real_data_loader.py` (Fail-closed real BTS parquet loader)
  5. `src/simulation/verified_pairing.py` (Deterministic verified turn pairing engine)
  6. `src/simulation/monte_carlo_engine_v2.py` (Remediated causal Monte Carlo engine)
- **Test Suites (127 items, 100% PASS)**:
  `test_g1_provenance_and_temporal_contracts.py` (22), `test_g2_monte_carlo_causality.py` (24), `test_g3_ml_validation.py` (14), `test_g4_native_e2e.py` (19), `test_g5_solver_correctness.py` (21), `test_g6_dashboard_integrity.py` (12), `test_g7_scientific_invariants.py` (15).

---

## 3. Cryptographic Verification of Frozen Baseline Artifacts

All 5 core model checkpoints and 20 frozen evidence artifacts recorded in the Gate G0 Baseline Manifest were re-verified via SHA-256 computation:

| Artifact Role | File Path | Measured SHA-256 Hash | G0 Baseline Status |
|:---|:---|:---|:---:|
| **Arrival Continuous NGBoost** | `artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib` | `e7e7462f17b65b276ebdee9c7beced15e090f69b088a18896d5a91aaa8cb062f` | **BITWISE MATCH** |
| **Departure XGBoost Regressor** | `artifacts/dual_core/models/departure_xgboost_baseline_v1.joblib` | `e483df5fd03ce4d0eefe7b431fc289b6804589c62eda17b48fb8051849f4f6e1` | **BITWISE MATCH** |
| **Departure Tree Preprocessor** | `artifacts/dual_core/models/departure_tree_preprocessor_v1.joblib` | `ce2bb0f6f0e0ed650df3ae82306013360de5c0fafac5814307e99dfb69f62017` | **BITWISE MATCH** |
| **Departure Ridge Baseline** | `artifacts/dual_core/models/departure_ridge_baseline_v1.joblib` | `a9a9834aecd1af10cc3967cb1108c750b200a6802586e5eb41180285cbde5aae` | **BITWISE MATCH** |
| **Departure Linear Preprocessor**| `artifacts/dual_core/models/departure_linear_preprocessor_v1.joblib` | `377a2aeafbe1969e01ef86038ec6aad974fd83ee871107e39412da7d9902e7d2` | **BITWISE MATCH** |
| **Frozen Evidence Artifacts (20)**| `artifacts/remediation/`, `artifacts/development_end_to_end/` | 20 / 20 Artifacts | **BITWISE MATCH (100%)** |

---

## 4. Audit Scope Boundaries & Non-Goals

1. **Read-Only Invariant**: The auditor did not attempt to refactor code, modify tests, or overwrite historical experimental results.
2. **Independence from Prior Gates**: Conclusions from Gate Reports G0 through G7 were treated as candidate claims requiring direct source code inspection and empirical re-verification.
3. **Defense Preparation Focus**: All documented limitations are structured to provide the student and advisor with defendable, mathematically sound positions for the oral thesis defense.
