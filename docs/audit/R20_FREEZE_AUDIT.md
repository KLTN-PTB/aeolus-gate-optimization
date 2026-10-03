# R20 Reproducibility, Provenance & Freeze Audit

**Repository**: `D:\Study\Code\Python\Aelous`  
**Task ID**: `R20_PROVENANCE_AND_FREEZE_AUDIT`  
**Execution Date**: 2026-10-02  
**Status**: **PASS**  
**Gate**: `R20_PRE_REBUILD: AUTHORIZED`  
**Contract Reference**: `AEOLUS_V4_TEMPORAL_GOVERNANCE_PROTOCOL_V2`

---

## 1. Executive Summary & Verification Dashboard

Task **R20** establishes a rigorous, verifiable state of provenance and freeze across all result-affecting pipeline components to prepare for **R21 Targeted Rebuild**. It verifies that development evidence is sound, model selection is pre-registered, downstream semantics are locked, statistical inference is repaired, probabilistic capabilities are decoupled, 2024 data is sealed against tuning, and stale artifact reuse is prevented by fail-closed guards.

### Status Dashboard
| Audit Dimension | Forensic Verdict | Key Finding |
|---|---|---|
| **R20 Overall Status** | **PASS** | 10/10 pre-rebuild gate checks passed; R21 rebuild authorized. |
| **Repository State** | **DIRTY (AUDITED)** | Head commit `c99b3e84b403527bcfb0f9612a1e2737c9f63701`; 13 modified tracked files reflect verified R13–R20 contracts and audits. |
| **Data Provenance** | **PASS** | Raw data verified immutable; processed inbound ATL partitions traced across years 2016–2024 with zero silent overwrites. |
| **2024 Holdout Status** | **POST_HOLDOUT** | Formally classified as `POST_HOLDOUT`; zero row-level reads, zero HPO tuning, zero weight fitting on 2024. |
| **Freeze Completeness** | **COMPLETE (17/17)** | All 17 result-affecting components locked under `SYSTEM_FROZEN_V3`. |
| **Stale Artifact Guard** | **PASS** | Active guard in `src/audit/artifact_freshness.py` rejects stale timestamps, copied hashes, and metadata mismatches. |
| **Pre-Rebuild Gate** | **PASS** | Verified via `scripts/r20_pre_rebuild_gate.py`; output in `artifacts/r20_pre_rebuild_gate.json`. |
| **Claim Reconciliation** | **PASS** | 9 historical legacy claims audited and reconciled against empirical facts. |

---

## 2. Part A: Reconstructed Repository State

The current repository state is recorded in [`artifacts/r20_repository_state.json`](file:///D:/Study/Code/Python/Aelous/artifacts/r20_repository_state.json):

- **Git Head Commit**: `c99b3e84b403527bcfb0f9612a1e2737c9f63701`
- **Active Branch**: `week5-model-parameters-export`
- **Dirty Working Tree**: 13 modified tracked files:
  1. `scripts/run_phase_a_benchmark.py`
  2. `src/data/preprocessing.py`
  3. `src/data/stratified_loader.py`
  4. `src/evaluation/__init__.py`
  5. `src/features/refactored_features.py`
  6. `src/features/tabular_features.py`
  7. `src/models/baselines.py`
  8. `src/optimization/__init__.py`
  9. `tests/test_holdout_guard.py`
  10. `tests/test_phase_a.py`
  11. `tests/test_refactored_pipeline.py`
  12. `tests/test_tabular_features.py`
  13. `tests/test_temporal_split.py`
- **Environment**: Python 3.11.15 on `win32`. Key package lock verified: `scikit-learn 1.9.0`, `xgboost 3.2.0`, `lightgbm 4.7.0`, `ngboost 0.5.11`, `ortools 9.15.6755`, `scipy 1.17.1`, `numpy 2.2.6`, `pandas 2.3.3`, `pyarrow 25.0.1`, `pytest 9.1.1`.
- **Audited Runner Versions**:
  - `run_academic_point_benchmark_v2.py`: v2 common benchmark runner.
  - `run_probabilistic_benchmark.py`: v2 common probabilistic runner.
  - `run_paired_comparison.py`: v2 statistical runner with Holm-Bonferroni & day-cluster bootstrap.
  - `run_academic_model_selection.py`: v2 academic selection runner on 2023.
  - `run_downstream_model_comparison.py`: v2 scalar forecast impact benchmark runner.
  - `run_monte_carlo_comparison.py`: v2 Monte Carlo simulation runner.

---

## 3. Part B: Data Provenance & Immutability

Data lineage is documented in [`artifacts/r20_data_provenance.json`](file:///D:/Study/Code/Python/Aelous/artifacts/r20_data_provenance.json):

1. **Raw Datasets**:
   - `data/raw/tabular/` and `data/raw/chain/` covering 2016–2024.
   - Status: **`IMMUTABLE_READ_ONLY`**. Unmodified BTS Form 41 source tables.
2. **Processed Partitions**:
   - `data/processed/inbound_atl/year={year}` covering 2016 through 2024.
   - Invariants strictly enforced: `DEST == 'ATL'`, preflight cutoff at `CRS_DEP_TIME - 2h`, zero weather predictors, zero departure delay predictors, zero actual operational outcomes.
3. **Temporal Partitioning Lineage**:
   - **Rolling Folds 1–4 (2016–2022)**:
     - Fold 1: train 2016–2018 (10,500 rows), val 2019 (4,000 rows).
     - Fold 2: train 2016–2019 (14,000 rows), val 2020 (4,000 rows).
     - Fold 3: train 2016–2020 (17,500 rows), val 2021 (4,000 rows).
     - Fold 4: train 2016–2021 (21,000 rows), val 2022 (4,000 rows).
   - **Academic Model Selection (2023)**:
     - Train 2016–2022 (24,500 rows), val 2023 (4,000 rows).
   - **Post-Holdout (2024)**:
     - 5,000 evaluated instances. Sealed against exploratory access.
4. **Preprocessing Lineage**:
   - Preprocessor transforms (StandardScaler + OneHotEncoder/Ordinal) are fit strictly on the respective training window partitions; zero cross-validation or holdout leakage.

---

## 4. Part C: 2024 Holdout Safety Audit

Documented in [`artifacts/r20_2024_provenance_audit.json`](file:///D:/Study/Code/Python/Aelous/artifacts/r20_2024_provenance_audit.json):

### Forensic Invariant Check
- `dataset_2024_access`: **True** (historical read access occurred during Stage 11 execution on 2026-09-27).
- `historical_access`: **True** (evaluated post-freeze in historical Stage 11).
- `development_use`: **False** (2024 was never part of training windows).
- `tuning_use`: **False** (zero Optuna HPO, zero threshold tuning, zero ensemble weight fitting).
- `final_eval_use`: **True** (historical final post-holdout evaluation).
- `classification`: **`POST_HOLDOUT`** (strictly enforced; labels like 'untouched' or 'unseen' fail closed).

### Evidence Base
1. 2024 was opened post-freeze at `2026-09-27T18:23:46.416794+00:00` during historical Stage 11.
2. Model weights evaluated in Stage 11 were loaded directly from frozen checkpoint `model_weights_frozen_v1.joblib` without retraining or fine-tuning.
3. Audited all training scripts (`run_academic_point_benchmark_v2.py`, `run_development_end_to_end_benchmark.py`, `run_probabilistic_benchmark.py`): max training year is strictly $\le 2022$.
4. Audited Optuna HPO: objective function evaluations strictly ingested 2016–2022 rolling folds; zero 2024 rows were ever passed to Optuna.
5. Audited decision threshold selection: classification threshold 0.50 was pre-registered; zero threshold tuning occurred on 2024.
6. Audited ensemble weight fitting: weights were fit strictly on historical rolling folds 1–3 or 2023 selection data; zero 2024 rows ingested.
7. Audited Tasks R13–R20: strictly zero row-level reads were performed on `data/processed/inbound_atl/year=2024`.

---

## 5. Part D: Freeze Completeness (17 Frozen Components)

Recorded in [`artifacts/r20_freeze_manifest.json`](file:///D:/Study/Code/Python/Aelous/artifacts/r20_freeze_manifest.json):

| # | Component | Status | Source File | Notes |
|---|---|---|---|---|
| 1 | `data_split` | **FROZEN** | `src/data/stratified_loader.py` | Rolling 2016–2022, selection 2023, holdout 2024. |
| 2 | `feature_definition` | **FROZEN** | `src/features/refactored_features.py` | 11 approved features; zero weather/departure delay leakage. |
| 3 | `target_definition` | **FROZEN** | `src/data/preprocessing.py` | DEST=ATL; $y_{\text{cls}} = 1[ARR\_DELAY \ge 15]$; $y_{\text{reg}} = ARR\_DELAY$. |
| 4 | `cutoff_logic` | **FROZEN** | `src/features/tabular_features.py` | Strict preflight cutoff at `CRS_DEP_TIME - 2h`. |
| 5 | `model_registry` | **FROZEN** | `src/models/registry.py` | Exactly 5 Core Point Methods + P1–P5 probabilistic evidence layer. |
| 6 | `hyperparameter_configs` | **FROZEN** | `configs/academic_model_selection.yaml` | Pre-registered hyperparameters across all candidates. |
| 7 | `preprocessing` | **FROZEN** | `src/data/preprocessing.py` | Fit strictly on training window; zero validation/holdout leakage. |
| 8 | `oof_generation` | **FROZEN** | `src/evaluation/model_benchmark_runner.py` | Expanding-window rolling folds 1–4 generating OOF frames. |
| 9 | `model_selection_logic` | **FROZEN** | `src/evaluation/model_selection.py` | Three distinct roles: Role A (Point), Role B (Quantile Risk), Role C (Simulation). |
| 10 | `probabilistic_metric_definitions` | **FROZEN** | `src/evaluation/forecast_metrics.py` | NLL restricted to densities; PIT restricted to continuous CDFs; CRPS approximation labeled. |
| 11 | `downstream_semantics` | **FROZEN** | `src/evaluation/downstream_comparison_v2.py` | Scalar Forecast Impact Benchmark certified; unassigned $\ne$ remote $\ne$ contact. |
| 12 | `optimizer_semantics` | **FROZEN** | `src/optimization/solvers/cp_sat_solver.py` | CP-SAT exact formulation; Greedy benchmark; SA warm-start post-search. |
| 13 | `statistical_runner` | **FROZEN** | `scripts/run_paired_comparison.py` | Holm-Bonferroni FWER control across 48 families; Day-cluster bootstrap on `FL_DATE`. |
| 14 | `monte_carlo_configuration` | **FROZEN** | `configs/monte_carlo_protocol_v2.yaml` | $N=500$ scenarios; seed 202603; antithetic sampling; SE monitoring. |
| 15 | `seed_policy` | **FROZEN** | `configs/seed_registry.yaml` | Fixed seeds: screening=202601, deployment=202602, outer=202603. |
| 16 | `artifact_naming` | **FROZEN** | `artifacts/manifests/` | Versioned v2 naming conventions; SHA256 sidecars; manifest catalog. |
| 17 | `provenance_checks` | **FROZEN** | `src/audit/provenance.py` | Fail-closed provenance verification; anti-stale artifact guard active. |

---

## 6. Part E: Stale Artifact Detection & Anti-Masquerading Guard

Implemented in [`src/audit/artifact_freshness.py`](file:///D:/Study/Code/Python/Aelous/src/audit/artifact_freshness.py) and verified via [`tests/test_r20_artifact_freshness.py`](file:///D:/Study/Code/Python/Aelous/tests/test_r20_artifact_freshness.py):

### Guard Capabilities
1. **Timestamp Freshness**: Rejects artifacts older than the active run session start timestamp ([`StaleArtifactError`](file:///D:/Study/Code/Python/Aelous/src/audit/artifact_freshness.py#L20-L22)).
2. **Upstream Temporal Order**: Rejects output artifacts that have creation timestamps older than their declared upstream input source artifacts.
3. **Anti-Copy Sidecar Protection**: Maintains a registry of historical artifact SHA256 digests; any artifact identical in hash to a historical run while claiming a new `run_id` is rejected fail-closed.
4. **Cryptographic Provenance Verification**: Asserts matching `code_hash` and `config_hash` within JSON artifact headers ([`ProvenanceMismatchError`](file:///D:/Study/Code/Python/Aelous/src/audit/artifact_freshness.py#L25-L27)).
5. **Run ID Integrity**: Asserts matching `run_id` across execution steps.

---

## 7. Part G: Reconciled Historical Legacy Claims

Documented in [`artifacts/r20_claim_reconciliation.json`](file:///D:/Study/Code/Python/Aelous/artifacts/r20_claim_reconciliation.json):

| Legacy Claim | Historical Status | Reconciled Status | Reconciled Definition & Action |
|---|---|---|---|
| **SYSTEM_FROZEN** | CLAIMED (Stage 10) | **OVERSTATED** | Reconciled to `SYSTEM_FROZEN_V3`. Stage 10 froze model weights, but downstream adapters, multiplicity correction, and capability contracts required R17–R19 unification. |
| **FAIL_CLOSED_CERTIFIED** | CLAIMED (Stage 0–11) | **OVERSTATED** | Reconciled to `FAIL_CLOSED_CERTIFIED_POST_R18_R19`. Validated through automated test suites; runners previously bypassed Holm adjustment. |
| **POST_HOLDOUT_STABILIZED** | CLAIMED (Stage 11) | **INVALID_AND_OVERSTATED** | Reconciled to `POST_HOLDOUT_AUDITED_WITH_KNOWN_DEGRADATION`. 2024 conflict error reduction was $-387.2\%$ (D2 was worse than D0); downstream conflicts derived from synthetic turns. |
| **untouched 2024** | CLAIMED (Historical docs) | **INVALID** | Reconciled to `POST_HOLDOUT`. 2024 was opened and evaluated on 2026-09-27 in Stage 11; cannot be called 'untouched' or 'unseen'. |
| **7 core models** | CLAIMED (Historical docs) | **INVALID** | Reconciled to `5_CORE_POINT_METHODS_PLUS_PROBABILISTIC_EVIDENCE_LAYER`. V4 defines exactly 5 core point methods; P1–P5 are probabilistic variants. |
| **real-world gate optimization** | CLAIMED (Historical reports) | **OVERSTATED** | Reconciled to `SYNTHETIC_GATE_SIMULATION_BENCHMARK`. BTS data has zero gate numbers; results reflect synthetic turnaround simulation. |
| **optimal N=500** | CLAIMED (Historical MC) | **OVERSTATED** | Reconciled to `EMPIRICAL_CONVERGENCE_OPERATIONAL_CHOICE`. Practical computational trade-off achieving $<1.5\%$ variance; not an absolute theoretical optimum. |
| **CRPS Pinball** | CLAIMED (Historical reports) | **OVERSTATED** | Reconciled to `CRPS_QUANTILE_APPROXIMATION`. Multi-pinball trapezoidal approximation over 9 quantiles is distinct from exact continuous CRPS. |
| **SA peer solver** | CLAIMED (Historical reports) | **OVERSTATED** | Reconciled to `WARM_START_HYBRID_OR_HEURISTIC_BASELINE`. Unassisted SA fails on large instances without CP-SAT warm start. |

---

## 8. Part H & J: Pre-Rebuild Gate Verification & Test Results

Executed via [`scripts/r20_pre_rebuild_gate.py`](file:///D:/Study/Code/Python/Aelous/scripts/r20_pre_rebuild_gate.py) with output in [`artifacts/r20_pre_rebuild_gate.json`](file:///D:/Study/Code/Python/Aelous/artifacts/r20_pre_rebuild_gate.json):

```text
============================= test session starts =============================
platform win32 -- Python 3.11.15, pytest-9.1.1, pluggy-1.6.0
rootdir: D:\Study\Code\Python\Aelous
collected 37 items

tests\test_r17_downstream_semantics.py .......                           [ 18%]
tests\test_r18_statistical_inference.py .......                          [ 37%]
tests\test_r19_probabilistic_comparability.py .......                    [ 56%]
tests\test_r19_ensemble_lineage.py .....                                 [ 70%]
tests\test_r20_artifact_freshness.py ......                              [ 86%]
tests\test_r20_freeze_gate.py .....                                      [100%]

============================= 37 passed in 3.22s ==============================
```

- **Pre-Rebuild Gate Check Results (10/10 PASS)**:
  1. `repository_state`: PASS
  2. `model_registry_unambiguous`: PASS
  3. `temporal_split_integrity`: PASS
  4. `2024_holdout_safety`: PASS
  5. `statistical_runner_resolution`: PASS
  6. `downstream_semantics_resolution`: PASS
  7. `probabilistic_capability_resolution`: PASS
  8. `freeze_completeness`: PASS
  9. `stale_artifact_guard`: PASS
  10. `legacy_claim_reconciliation`: PASS

---

## 9. Conclusion & Next Step

All prerequisites for **R21 TARGETED REBUILD** are satisfied:
- **R17 = PASS** (Downstream Semantics Locked)
- **R18 = PASS** (Statistical Inference Repaired)
- **R19 = PASS** (Probabilistic Capabilities & Ensemble Decoupled)
- **R20 = PASS** (Reproducibility, Provenance & Freeze Certified)

**NEXT STEP**: **R21 Targeted Rebuild is authorized to proceed.**
