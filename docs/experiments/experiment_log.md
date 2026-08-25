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
