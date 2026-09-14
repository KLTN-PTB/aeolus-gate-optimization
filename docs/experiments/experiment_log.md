# Experiment log

## Week 1 — scope, audit planning, and reproducibility baseline

- **Timestamp:** 2026-08-23 19:52:01 +07:00
- **Roadmap version:** V3.0 synchronized roadmap set dated 2026-08-23.
- **Status:** Documentation and reproducibility closeout; no ML, preprocessing, simulation, optimization, or performance experiment was run.

### Actions

- Established the V3-aligned decision registry, inventory, schema-audit plan, Tabular data dictionary V0, and Flight Chain feasibility V0.
- Recorded the locked T-2h prediction boundary, target definitions, temporal roles, raw-data policy, and 2024 access guard.
- Inspected only the 2016 Tabular header and bounded 2016 Chain container metadata under the documented safety limits.
- Added configuration, access-guard, logging, unit tests, thesis/methodology notes, and a filesystem/configuration smoke test.
- Rechecked README and project-structure documentation; README now states the canonical raw Tabular and optional Chain paths.

### Files created in Week 1

- `configs/base.yaml`
- `docs/decisions/decision_registry.md`
- `docs/dataset_audit/data_inventory.md`
- `docs/dataset_audit/schema_audit_plan.md`
- `docs/dataset_audit/data_dictionary_v0.md`
- `docs/dataset_audit/flight_chain_feasibility_v0.md`
- `docs/thesis_notes/assumptions.md`
- `docs/thesis_notes/limitations.md`
- `docs/experiments/experiment_log.md`
- `src/data/access_guard.py`
- `src/data/project_logging.py`
- `tests/test_base_config.py`
- `tests/test_holdout_guard.py`
- `scripts/smoke_test.py`

### Tests

- `pytest -q`: **13 passed** in 0.07 seconds.
- `scripts/smoke_test.py`: **PASS**. It validated required structure/files, `configs/base.yaml`, 9 Tabular CSV paths, 27 Chain `.pt` paths, source-package imports, and the expected block on 2024 development access.
- No dataset-content test, training run, schema audit, or performance result was run or recorded.

### Unresolved items

- Weather provenance and availability at T-2h.
- `FLIGHTS` semantics; airport-index stability; cross-year schema compatibility; and cancelled/diverted representation.
- Flight Chain feature semantics, flight-level mapping, source-label safety, and temporal safety. Its V0 status is `PROVISIONAL_GO` for Week 2 investigation only.
- Simulation, pairing, optimization, and robustness parameters remain TBD and must be fixed using development-only evidence before 2024 access.

## Week 2 — Prompt 8 Flight Chain final feasibility gate

- **Timestamp:** 2026-08-23 22:50 +07:00
- **Roadmap version:** V3.0 synchronized roadmap set.
- **Status:** Feasibility audit completed with final `NO_GO`; no training, deep model, feature generation, tensor statistics, or model-performance access was performed.

### Actions and evidence

- Inspected 27/27 Chain archives sequentially via ZIP/container metadata and restricted `data.pkl` parsing.
- Read zero tensor-storage payload bytes and used no `torch.load`.
- Recorded `flight_chain_structure_audit_v1.json`; 2016–2023 share a five-tensor signature, while 2024 has an incompatible four-tensor signature.
- Cross-checked the local structure against official source commit `6d10cab7a5d542733ff6a8b88d1ab4d4f98b1c6f`.
- Finalized E003 `NO_GO`, updated fail-closed config, current methodology notes, access log, and documentation.

### Files created or materially updated

- `src/data/chain_inspection.py`
- `scripts/inspect_chain_structure.py`
- `tests/test_chain_inspection.py`
- `artifacts/manifests/flight_chain_structure_audit_v1.json`
- `artifacts/manifests/week2_2024_access_log.json`
- `docs/dataset_audit/flight_chain_feasibility_report.md`
- `docs/decisions/decision_include_chain.md`
- `docs/decisions/decision_registry.md`
- `configs/base.yaml`
- `README.md`, `project_structure.md`, `assumptions.md`, and `limitations.md`

### Tests

- Bounded helper tests: **2 passed** before the full run.
- `pytest -q --basetemp .pytest_tmp_week2_prompt8`: **49 passed** in 0.26 seconds. The workspace basetemp was required because the managed environment denied pytest access to the user Temp directory.
- `scripts/smoke_test.py`: **PASS**; 2024 development remained blocked.

### Remaining relevant uncertainty

- `FLIGHTS` semantics remain unresolved for Tabular, but it is blocked from candidate predictors.
- Reopening Flight Chain requires new versioned exact-mapping and point-in-time evidence under E003 change control; 2024 performance cannot be used.

## Week 2 — M1 schema, canonical-data, and protocol acceptance

- **Timestamp:** 2026-08-23 23:08 +07:00
- **Roadmap version:** V3.0 synchronized roadmap set.
- **Status:** M1 acceptance audit completed; no ML preprocessing was fitted, no model was trained, and no 2024 performance was accessed.

### Actions and evidence

- Audited Tabular 2016–2024 one year at a time using bounded chunks; all nine versioned reports are complete and cover 54,674,003 rows, 34 fields, full annual date ranges, missingness, target summaries, cardinalities, weather/index characteristics, numeric quality, and duplicate detection.
- Established `canonical_schema_v1`, a 34-field storage contract supported by all nine annual audits, plus the schema compatibility matrix and stable airport-code/index evidence E001.
- Materialized partitioned canonical, inbound `DEST=ATL`, and outbound `ORIGIN=ATL` Parquet datasets. The processed manifest records 54,674,003 canonical rows, 3,022,433 inbound rows, and 3,022,670 outbound rows; 2024 partitions remain `FINAL_HOLDOUT`.
- Finalized the T−2h leakage contract and data dictionary V1. Realized operational fields are blocked; six weather fields are excluded from candidate `X` under E002 `DROP`; unresolved `FLIGHTS` is fail-closed.
- Locked `expanding_window_v1` in I003 and versioned temporal/split manifests. HPO is limited to 2016–2022; 2023 and 2024 are blocked, and 2024 final evaluation remains blocked before a system-freeze manifest.
- Finalized Flight Chain E003 `NO_GO`; Tabular-only is the core route and no Week-6 Chain ablation is scheduled.
- Revalidated raw byte totals and stored input signatures without reading raw rows: Tabular 9 files / 15,196,366,173 bytes; Chain 27 files / 13,751,334,923 bytes; all size and modification-time signatures matched.

### Files created or materially updated during Week 2

- `src/data/load_aeolus.py`, `schema_audit.py`, `canonicalize.py`, `leakage_rules.py`, `temporal_protocol.py`, and `chain_inspection.py`
- `artifacts/manifests/schema_audit/schema_2016.json` through `schema_2024.json`
- `artifacts/manifests/canonical_schema_v1.json`, `processed_data_manifest_v1.json`, `temporal_folds_manifest.json`, `split_manifest.json`, `airport_index_mapping_audit.json`, `week2_2024_access_log.json`, and `flight_chain_structure_audit_v1.json`
- `docs/dataset_audit/schema_compatibility_matrix.md`, `canonical_schema_v1.md`, `data_dictionary_v1.md`, `leakage_audit.md`, `weather_timing_audit.md`, and `flight_chain_feasibility_report.md`
- `docs/decisions/decision_include_chain.md` and evidence/default entries E001–E004, I002, and I003 in `decision_registry.md`
- Partitioned Parquet datasets under `data/processed/tabular_by_year/`, `inbound_atl/`, and `outbound_atl/`

### Final acceptance tests

- `pytest -q --basetemp .pytest_cache/week2_prompt9_final_20260823_2310`: **49 passed** in 0.25 seconds. The workspace basetemp avoids the managed environment's inaccessible user Temp directory.
- `scripts/smoke_test.py`: **PASS**. It checked all Week-1/2 required files, raw metadata inventory, nine schema reports, canonical/processed/temporal/split/access manifests, Parquet-part presence, package imports, and the 2024 development block without reading data rows.
- `scripts/validate_processed_data.py`: **PASS**. It reconciled Parquet metadata/row counts and schemas with the processed manifest, verified all inbound/outbound filter values, source signatures, bounded 2016 target traceability, sampled flight-key uniqueness, and the 2024 development block.

### Remaining Week-2 uncertainties carried forward

- `FLIGHTS` semantics and cancelled/diverted generation/representation remain unresolved and fail-closed where relevant.
- Simulation, risk-buffer, gate-mix, objective, solver, SA, and robustness parameters remain TBD for their roadmap stages; none were selected in Week 2.

## Research protocol amendment — V4 Dual Prediction Architecture

- **Date:** 2026-08-26
- **Type:** Research protocol amendment
- **Version:** V4 / 4.0
- **Reason:** Separate Core Arrival prediction from an Auxiliary Departure
  point-in-time Weather study.
- **Status:** Baseline/config/leakage/documentation migration only. No model was
  trained, no feature engineering was performed, and no experiment result was
  produced.

### Amendment record

- Core remains inbound `DEST=ATL` Arrival classification (`ARR_DELAY >= 15`)
  plus signed `ARR_DELAY` regression, with no Weather.
- Auxiliary is outbound `ORIGIN=ATL` Departure classification
  (`DEP_DELAY >= 15`) with a future controlled Schedule-only versus Schedule +
  audited point-in-time Weather comparison; Departure regression is out of
  scope.
- The six raw Aeolus Weather fields retain E002
  `INSUFFICIENT_EVIDENCE`/`DROP`. External point-in-time Weather is a separate
  disabled `AUDIT_REQUIRED` source plan.
- Raw Flight Chain `.pt` retains E003 `FINAL — NO_GO`; reconstructed
  `schedule_chain_v1` retains E005 `GO_FOR_ABLATION` and remains disabled by
  default.
- Only Core Arrival prediction feeds downstream simulation/optimization.
- No model result was used to make this change. 2024 row-level data and target
  distributions were not accessed or used for decision making.

## Pre-Week-3 research protocol hardening — Chain feature availability

- **Date:** 2026-08-26
- **Type:** Pre-Week-3 research protocol hardening
- **Reason:** Separate dataset-level reconstructed Chain validity from
  feature-level point-in-time predictor admissibility.
- **Model results used:** NO
- **2023 results used:** NO
- **2024 results used:** NO
- **Data regenerated:** NO

### Hardening record

- Preserved `schedule_chain_v1` as `FULL_DATA_PASS / GO_FOR_ABLATION` without
  changing membership, ordering, identifiers, or production artifacts.
- Added D026 and a versioned fail-closed feature availability policy.
- Target/position-local and past-context candidates start
  `REVIEW_REQUIRED`; future/full-chain candidates start
  `BLOCKED_UNTIL_PROVEN`; identifiers remain `IDENTIFIER_ONLY`.
- ARR-B and reconstructed feature ML enablement remain disabled. No Week 3A,
  3B, or 3C implementation, feature derivation, feature artifact generation,
  model run, ablation, or row-level 2024 access occurred.

## Week 3A — Core Arrival preprocessing

- **Timestamp:** 2026-08-26 17:04 +07:00
- **Protocol:** V4.0 Dual Prediction Architecture
- **Status:** COMPLETED; preprocessing transformers only, no predictive model.
- **Environment:** Python 3.11.15; scikit-learn 1.9.0.
- **Source schema:** `canonical_schema_v1`.
- **Temporal protocol:** `expanding_window_v1`; four folds within 2016–2022.
- **Tests:** 193 passed at implementation closeout.
- **Model trained:** NO.
- **2023 fit:** NO.
- **2024 row access:** NO.
- **Weather:** excluded.
- **Reconstructed Chain:** excluded from base matrix; ARR-B remains disabled.

### Implementation record

- Added exact `y_arr_cls = 1[ARR_DELAY >= 15]` and signed `y_arr_reg` label
  construction. Missing targets are dropped and counted; no target imputation,
  absolute-value conversion, or clipping is permitted.
- Locked one common Schedule/Calendar/Carrier/Route information set. Weather,
  Departure outcomes/predictions, realized operations, identifiers, `FLIGHTS`,
  airport indices/conditional coordinates, and inbound ATL constants are not
  predictors. Unknown raw fields fail closed.
- Added linear and tree/boosting transformer families. Every median, missing
  indicator, scale, category vocabulary, ordinal code, and non-target
  flight-number frequency map is fitted on fold training rows only.
- Versioned `feature_manifest_arrival_v1`,
  `feature_pipeline_registry_arrival_v1`, and
  `outlier_and_simulation_guard_v1`.

### Bounded real-data validation

- Reproducible command: `.\.venv\Scripts\python.exe scripts/smoke_week3a_preprocessing.py`.
- Training-like scope: 1,024 projected inbound rows from 2016, read in batches
  of 256.
- Validation-like scope: 512 projected inbound rows from 2019, read in batches
  of 256.
- Projected columns: 14; approved predictors: 11.
- `fit(train_2016)` then `transform(train_2016)` and
  `transform(validation_2019)` succeeded for linear and tree families.
- Fitted medians and categorical vocabularies were unchanged after validation
  transform; identifier and target alignment passed; 732 negative signed
  regression targets were preserved in the training-like batch.
- No estimator, metric, feature-importance, model-selection, Chain, Weather,
  2023, or 2024 operation was performed.

## Week 3B.0 — Chain Feature Point-in-Time Availability Audit

- **Timestamp:** 2026-08-26 17:48 +07:00
- **Protocol:** V4.0 Dual Prediction Architecture; D026.
- **Source artifact:** `schedule_chain_v1` (`FULL_DATA_PASS /
  GO_FOR_ABLATION`).
- **Candidate features audited:** 18.
- **Final counts:** `KEEP_SAFE=0`, `REVIEW_REQUIRED=7`,
  `BLOCKED_UNTIL_PROVEN=11`, `IDENTIFIER_ONLY=4`.
- **Evidence used:** existing versioned project documentation/manifests and
  reconstruction code semantics.
- **External evidence used:** NO.
- **Schedule publication/version/snapshot evidence found:** NO.
- **Model results used:** NO.
- **2023 performance used:** NO.
- **2024 row access:** NO.
- **Feature artifact generated:** NO.
- **Reconstruction modified or rerun:** NO.

### Audit outcome

- E005 remains a dataset-level `GO_FOR_ABLATION`; E006 independently records
  that no candidate is currently approved for ML use.
- Seven local/past features remain `REVIEW_REQUIRED`.
  `is_single_leg_chain` was tightened to `BLOCKED_UNTIL_PROVEN` because it
  requires absence of both earlier and future members; ten other
  future/full-chain features remain blocked.
- Week 3B.1 may proceed diagnostic-only, and every non-approved output must
  carry `ML_ADMISSIBLE=false`. ML materialization, ARR-B, and the Chain ML
  branch remain disabled pending new primary/versioned availability evidence.

## Week 3B closure after E006

- **Timestamp:** 2026-08-26 18:03 +07:00
- **Protocol:** V4.0 Dual Prediction Architecture; E005/D026/E006 preserved.
- **Closure status:** `COMPLETED_WITH_BLOCKED_ML_BRANCH`.
- **3B.0 availability audit:** PASS.
- **KEEP_SAFE:** 0.
- **3B.1 derivation:** `SKIPPED_NOT_REQUIRED_FOR_ML`.
- **3B.2 feature statuses:** `COMPLETED_THROUGH_E006`.
- **3B.3 materialization:** `SKIPPED_OPTIONAL_DIAGNOSTIC`.
- **3B.4 ARR-B disabled gate:** PASS.
- **Chain ML branch:** `BLOCKED_PENDING_NEW_EVIDENCE`.
- **ARR-B enabled:** NO.
- **Model trained:** NO.
- **Feature artifact generated:** NO.
- **2023 performance used:** NO.
- **2024 row access:** NO.
- **Reconstruction modified or rerun:** NO.
- **Raw `.pt` opened:** NO.

Diagnostic materialization remains permitted by policy only with
`ML_ADMISSIBLE=false`, but it was not executed because it would not change the
E006 admissibility result. Core Arrival remains unaffected.

## Week 3C — Auxiliary Weather Contract Preparation

- **Timestamp:** 2026-08-26 18:22 +07:00
- **Protocol:** V4.0 Dual Prediction Architecture; D022–D024, E002, I004.
- **Contract version:** `weather_point_in_time_contract_v1`.
- **External Weather status:** `AUDIT_REQUIRED`; enabled = NO.
- **Provider selected:** NO (`TBD`).
- **Weather data downloaded:** NO.
- **API called:** NO.
- **Weather joined / feature matrix created:** NO / NO.
- **Model trained:** NO.
- **Raw Aeolus Weather promoted:** NO.
- **2023 performance used:** NO.
- **2024 row access:** NO.
- **Core Arrival affected:** NO.
- **Tests:** synthetic contract tests cover availability-before-cutoff,
  post-cutoff publication/future issue rejection, timezone awareness,
  semantic classes, source identity, raw-Weather/Arrival boundaries,
  duplicate determinism, DEP row parity, and manifest W1–W15 consistency.

Week 3C prepared the provider-agnostic provenance/schema/join decision
template only. It did not establish `POINT_IN_TIME_WEATHER_PROVENANCE = PASS`.
An unproven or failed critical gate keeps DEP-B
`BLOCKED_NOT_CORE_FAILURE`; Core Arrival can proceed to Week 4.


## Week 4 — Core Arrival baseline rolling evidence

- **Timestamp:** 2026-09-14T17:55:20.668246+07:00
- **Protocol:** V4.0 Core Arrival; `arrival_week4_experiment_v1`.
- **Status:** Linear, Random Forest, and HistGradientBoosting locked rolling runs consolidated.
- **Folds:** 2016–2018 → 2019; 2016–2019 → 2020; 2016–2020 → 2021; 2016–2021 → 2022.
- **Evidence:** Exact OOF `flight_key`, classification-label, and signed regression-label parity passed for all four folds (1,254,518 OOF rows per method); full eligible rows were used.
- **Boundaries:** No Weather, Chain, Departure auxiliary input, realized operations, row-level 2023, or row-level 2024.
- **Selection status:** No champion selection, retuning, post-hoc calibration, ensemble, or final-holdout evaluation.
- **Artifacts:** `week4_core_arrival_baselines.md` and `week4_core_arrival_baselines_summary_v1.json`.

## Week 4 final acceptance audit

- **Timestamp:** 2026-09-14 18:07 +07:00
- **Protocol:** V4.0 Core Arrival; independent W4-09 acceptance audit.
- **Week 4 status:** `PASS / COMPLETED`.
- **Critical gates:** 9/9 PASS for three methods, temporal protocol, leakage,
  preprocessing isolation, metrics/resources, OOF integrity, reproducibility,
  tests, and documentation.
- **Artifact validation:** Re-read all 12 production OOF Parquet files;
  verified exact schema/metadata, finite outputs, probability bounds,
  per-fold and cross-fold uniqueness, and exact cross-method row/target parity.
  Per-fold and pooled metrics recomputed from OOF matched production manifests
  to absolute tolerance `1e-12`. Config/manifest SHA-256 records remain current.
- **Tests:** Week-4 targeted suite `20 passed`; full suite `242 passed`;
  framework, Linear, Random Forest, and HistGradientBoosting smokes PASS;
  compile/import and explicit 2024 development-denial checks PASS.
- **Temporal access:** Week 4 row-level 2023 access = NO; row-level 2024 access
  = NO. The system-freeze manifest remains absent and 2024 remains sealed.
- **Excluded work:** No XGBoost, Optuna/HPO, ensemble, Weather experiment,
  Chain ablation, 2023 selection, 2024 evaluation, commit, or push was run.
- **Next roadmap stage:** Week 5 XGBoost plus fixed-budget Optuna; Week 5 is
  not started or marked complete by this audit.
