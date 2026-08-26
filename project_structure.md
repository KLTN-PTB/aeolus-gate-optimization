# Project structure — Baseline V4

Current protocol: **V4.0 Dual Prediction Architecture**, dated 2026-08-26.
Week 1–2 evidence and reconstructed Chain production artifacts are preserved.
Week 3A Core Arrival preprocessing is complete. Week 3B is
`COMPLETED_WITH_BLOCKED_ML_BRANCH`; Week 3C contract preparation and Week 3
closeout are complete. Core Arrival is ready for Week 4.

## Reading order

1. `docs/decisions/decision_registry.md` — current decision source of truth.
2. `docs/decisions/decision_dual_prediction_architecture_v4.md` — V4
   architecture boundary.
3. Three `docs/roadmap/*_V4_DONG_BO.md` files — authoritative 12-week plan,
   technology stack, and weekly execution detail.
4. `docs/dataset_audit/leakage_audit.md` and `weather_timing_audit.md` —
   preserved evidence plus dated V4 addenda.
5. `docs/dataset_audit/point_in_time_weather_plan_v1.md` — future external
   Weather audit plan, not approval.
6. `docs/dataset_audit/weather_point_in_time_contract_v1.md` — reviewed W1–W15
   execution contract/template; provider remains TBD and disabled.
7. `docs/dataset_audit/reconstructed_chain_feature_availability_plan_v1.md` —
   pre-Week-3 feature-level T-2h audit contract, not feature approval.
8. `docs/dataset_audit/reconstructed_chain_feature_availability_audit_v1.md` —
   completed E006 result: no current `KEEP_SAFE` Chain features.

The three V3 roadmap files remain unchanged as historical protocol artifacts.
They are not the current source of truth after the V4 amendment.

## Data boundaries

```text
data/
├── raw/
│   ├── tabular/<2016-2024>/       # Original Aeolus Tabular; immutable
│   └── chain/<2016-2024>/         # Original Aeolus .pt; immutable, FINAL_NO_GO
├── external/
│   └── weather/                   # Conceptual future point-in-time source only
├── processed/
│   ├── tabular_by_year/year=<YYYY>/
│   ├── inbound_atl/year=<YYYY>/   # Core Arrival input flow, DEST=ATL
│   ├── outbound_atl/year=<YYYY>/  # Auxiliary Departure + simulation, ORIGIN=ATL
│   └── flight_chain_reconstructed_v1/
└── simulation/                    # Future generated synthetic scenarios
```

`data/raw/**` is the original Aeolus source boundary: no rewrite, rename, move,
delete, conversion, normalization, overwrite, or reserialization. Generated
artifacts must never be written there.

`data/external/weather/` is a **planned conceptual location** for a separately
sourced point-in-time Weather artifact. This migration does not create the
directory, download a provider dataset, or join Weather. External Weather must
not be mixed into `data/raw/tabular` or represented as canonical Aeolus
Weather.

2024 processed partitions and their existing metadata retain
`FINAL_HOLDOUT`; row-level 2024 cannot be used in development.

## Repository tree

```text
Aeolus/
├── configs/
│   ├── base.yaml
│   ├── outlier_and_simulation_guard.yaml       # signed target vs future simulation
│   └── reconstructed_chain_feature_policy.yaml # fail-closed V1 policy
├── data/                           # Local/untracked data boundary
│   ├── raw/                        # Immutable Aeolus originals
│   ├── processed/                  # Existing versioned derived datasets
│   └── simulation/                 # Future generated simulation artifacts
├── docs/
│   ├── roadmap/
│   │   ├── 01_*_V3_DONG_BO.md      # Historical, preserved
│   │   ├── 02_*_V3_DONG_BO.md      # Historical, preserved
│   │   ├── 03_*_V3_DONG_BO.md      # Historical, preserved
│   │   ├── 01_*_V4_DONG_BO.md      # Current authoritative roadmap
│   │   ├── 02_*_V4_DONG_BO.md      # Current authoritative tech stack
│   │   └── 03_*_V4_DONG_BO.md      # Current authoritative weekly detail
│   ├── decisions/
│   │   ├── decision_registry.md
│   │   ├── decision_dual_prediction_architecture_v4.md
│   │   ├── decision_include_chain.md
│   │   └── decision_reconstructed_chain.md
│   ├── dataset_audit/
│   │   ├── canonical_schema_v1.md
│   │   ├── leakage_audit.md
│   │   ├── weather_timing_audit.md
│   │   ├── point_in_time_weather_plan_v1.md
│   │   ├── weather_point_in_time_contract_v1.md
│   │   ├── reconstructed_chain_feature_availability_plan_v1.md
│   │   ├── reconstructed_chain_feature_availability_audit_v1.md
│   │   ├── flight_chain_feasibility_report.md
│   │   └── flight_chain_reconstruction_report.md
│   ├── experiments/experiment_log.md
│   ├── thesis_notes/
│   │   ├── assumptions.md
│   │   └── limitations.md
│   └── superpowers/                # Historical implementation specs/plans
├── src/
│   ├── data/
│   │   ├── access_guard.py
│   │   ├── canonicalize.py
│   │   ├── leakage_rules.py        # V4 task-aware fail-closed contract
│   │   ├── preprocessing.py        # Week 3A transformers + bounded dev IO
│   │   ├── weather_contract.py     # Week 3C pure metadata/time/parity validation
│   │   ├── temporal_protocol.py
│   │   └── flight_chain_reconstruction.py
│   ├── features/
│   │   ├── tabular_features.py     # Week 3A labels/base Arrival feature contract
│   │   └── chain_feature_policy.py # policy validation only; no feature derivation
│   ├── models/                     # ML not implemented/trained
│   ├── simulation/                 # Downstream implementation pending
│   ├── optimization/               # Downstream implementation pending
│   └── evaluation/
├── scripts/
│   ├── smoke_test.py               # Metadata-only V4 structural validation
│   ├── smoke_week3a_preprocessing.py # Bounded 2016/2019 transformer smoke
│   ├── materialize_canonical_data.py
│   ├── create_temporal_manifests.py
│   └── reconstruct_flight_chain.py # Existing pipeline; do not rerun for V4
├── tests/
├── artifacts/manifests/            # Preserved evidence + Week 3 contracts
│   ├── reconstructed_chain_feature_availability_audit_v1.json
│   ├── feature_manifest_arrival_v1.json
│   ├── feature_pipeline_registry_arrival_v1.json
│   └── weather_point_in_time_contract_v1.json # template, not source data
├── reports/
├── results/
├── dashboard/
├── requirements.txt
└── README.md
```

## V4 code contracts

`configs/base.yaml` contains two explicit prediction tasks:

- `prediction.arrival_core`: core, inbound `DEST=ATL`, `ARR_DELAY >= 15`
  classification, signed `ARR_DELAY` regression, no Weather, reconstructed
  Chain optional/disabled.
- `prediction.departure_auxiliary`: auxiliary, outbound `ORIGIN=ATL`,
  `DEP_DELAY >= 15` classification, regression disabled, raw Weather DROP,
  external point-in-time Weather `AUDIT_REQUIRED`/disabled.

`src/data/leakage_rules.py` mirrors those tasks. `arrival_core` is the default
for backward-compatible callers. Unknown tasks, unknown columns, conditional
fields without explicit review, raw Weather, identifiers, outcomes, and
flow-specific ATL constants fail closed.

`flight_chain.reconstructed.feature_engineering` references
`configs/reconstructed_chain_feature_policy.yaml`. E006 now records
`audit_status=completed`, `keep_safe_feature_count=0`, `ml_enabled=false`,
`arr_b_enabled=false`, diagnostic materialization allowed, ML materialization
disallowed, and `ml_branch_status=blocked_pending_new_evidence`.
`src/features/chain_feature_policy.py` validates only this metadata; it does not
read Parquet or implement feature derivation.

The policy also records `diagnostic_materialization_executed=false` and the
closed substage disposition. Diagnostic materialization remains allowed in
principle but was skipped because E006 approved no ML-safe feature.

## Reconstructed Schedule Flight Chain

The existing derived root is
`data/processed/flight_chain_reconstructed_v1/`, partitioned into
`chain_groups`, `chain_members`, and `inbound_target_map`. The source universe
is canonical `tabular_by_year`; only the target map filters `DEST=ATL`.

`chain_id` means same `source_year`, `FL_DATE`, `OP_CARRIER`, and
`OP_CARRIER_FL_NUM` ordered by scheduled departure with deterministic
tie-breakers. It is not a tail number, registration, physical airframe, or
same-aircraft rotation. Production 2016–2023 is `FULL_DATA_PASS` and
`GO_FOR_ABLATION`, disabled by default and outside core. No `year=2024`
reconstructed partition exists.

The original raw `.pt` archives independently remain `FINAL — NO_GO`. Their
status is not superseded by reconstruction.

E005 `GO_FOR_ABLATION` is dataset-level only. Final historical membership is
not automatically a schedule snapshot available at target T-2h. E006 found no
publication/version/snapshot evidence and approved no `KEEP_SAFE` feature: 7
local/past candidates remain `REVIEW_REQUIRED`; `is_single_leg_chain` and 10
future/full-chain candidates are `BLOCKED_UNTIL_PROVEN`; identifiers remain
`IDENTIFIER_ONLY`. Only a future evidence-backed `KEEP_SAFE` subset may proceed
to the separate normal Arrival leakage contract; ARR-B remains disabled.

## Week 3 status and boundaries

Week 3A is **COMPLETED**. `src/features/tabular_features.py` creates exact
Arrival labels, filters/reports target eligibility, derives audited calendar
and departure-clock features, preserves identifiers separately, and fails
closed on unknown input. `src/data/preprocessing.py` provides train-fold-only
linear and tree/boosting transformer builders plus year-partitioned,
column-projected, batch-aware reads restricted to 2016–2022. The manifests
under `artifacts/manifests/` version the common information set and transformer
registry. No estimator is present.

Week 3B is closed fail-closed. 3B.0 and 3B.4 are completed PASS; 3B.2 is
completed through the E006 manifest/policy; 3B.1 is
`SKIPPED_NOT_REQUIRED_FOR_ML`; 3B.3 is `SKIPPED_OPTIONAL_DIAGNOSTIC`. These
skips are not failures. Week 3C completed only the point-in-time Weather
source specification, provenance, deterministic join, W1–W15 audit template,
and pure synthetic contract tests.

No reconstructed Chain feature artifact, Weather data, model, optimization
output, or Monte Carlo result has been created through Week 3. ARR-B remains
disabled. Provider selection and source ingestion remain future work; Weather
provenance is `AUDIT_REQUIRED`. This auxiliary state does not block Core
Arrival, so `READY_FOR_WEEK_4 = YES`.

## Temporal and downstream boundaries

The existing `expanding_window_v1` folds remain unchanged: development
2016–2022, 2023 model selection/controlled ablation/downstream development,
and 2024 sealed final end-to-end holdout. The access guard remains the code
boundary for 2024 development.

Only Core Arrival prediction feeds Synthetic Aircraft Turn, Gate Simulation,
Greedy, CP-SAT, CP-SAT+SA, and Monte Carlo. Auxiliary Departure output remains
research-only in V4.
