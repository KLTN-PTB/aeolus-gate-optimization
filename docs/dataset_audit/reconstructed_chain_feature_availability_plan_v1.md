# Reconstructed Chain Feature Availability Plan V1

Plan date: 2026-08-26  
Source artifact: `schedule_chain_v1`  
Current status: `AUDIT_REQUIRED`  
ML enablement: `false`

## Purpose

This document is a plan and audit contract, not evidence that any derived
feature has passed. The dataset-level decision
`schedule_chain_v1 = FULL_DATA_PASS / GO_FOR_ABLATION` establishes provenance,
deterministic reconstruction, structural auditability, and eligibility to
investigate an Arrival ablation. It does **not** automatically establish that
every feature derived from full reconstructed membership is predictor-safe.

The mandatory separation is:

```text
full reconstruction membership
!=
ML predictor availability
```

Full membership remains intact for provenance, structural analysis, auditing,
and future feature derivation. Feature-level ML use remains disabled until the
information needed by that feature is independently shown to be available at
the target prediction time.

## Prediction-time boundary

For each inbound target flight:

```text
target_cutoff = target CRS_DEP_TIME - 2 hours
```

A derived feature is admissible only if **all information required to compute
it was available by `target_cutoff`**. The cutoff must be constructed from the
canonical target `FL_DATE` and `CRS_DEP_TIME`; actual departure, arrival, or
duration fields must not participate.

Passing this availability gate is necessary but not sufficient. A feature
marked `KEEP_SAFE` must still pass the normal Core Arrival leakage contract
before it may enter candidate `X`:

```text
candidate feature
  -> Chain feature availability gate
  -> normal Arrival leakage gate
  -> candidate X
```

There is no direct path from `GO_FOR_ABLATION` to `KEEP_SAFE`.

## Source-membership semantics

`schedule_chain_v1` is historically reconstructed schedule/service-number
context. Membership groups canonical rows by source year, service date,
operating carrier, and operating flight number, ordered by scheduled departure
with deterministic tie-breakers. It is not a physical aircraft rotation and
does not identify an airframe or `TAIL_NUM`.

Reconstructed membership describes what can be assembled from the final
historical dataset. It is distinct from a versioned schedule snapshot known to
a predictor at T-2h. The existence of a row or scheduled timestamp in the
historical dataset is not evidence that the schedule, the future member, or
the absence of another member was known at `target_cutoff`.

No reconstruction field, membership, ordering, `chain_id`, or production
Parquet is changed by this plan.

## Availability statuses

| Status | Meaning for ML |
|---|---|
| `KEEP_SAFE` | Feature passed this audit and may proceed to the separate Core Arrival leakage gate. |
| `REVIEW_REQUIRED` | Availability is plausible but not proven; feature is blocked from predictor matrices. |
| `BLOCKED_UNTIL_PROVEN` | Feature depends on future/full-chain knowledge or another strong availability assumption; fail closed. |
| `DROP` | Feature is excluded by policy and cannot enter predictor matrices. |
| `IDENTIFIER_ONLY` | Field is limited to traceability, joining, and auditing; never a predictor. |

No current Week-3B candidate is automatically promoted to `KEEP_SAFE`.

## Feature families and initial classification

| Feature | Semantic group | Required members/context | Future/full-chain dependency | Initial availability status | Reason |
|---|---|---|---|---|---|
| `chain_position` | Target/position local | Target membership plus ordered members before target | No explicit future member, but position depends on reconstructed ordering/membership | `REVIEW_REQUIRED` | Must prove the position known at T-2h is reproducible from an available schedule snapshot. |
| `legs_before_target` | Target/position local | Target position and preceding membership | No explicit future member | `REVIEW_REQUIRED` | Historical position is not itself publication-time evidence. |
| `is_first_chain_leg` | Target/position local | Proof that no prior member precedes target | Depends on completeness before target | `REVIEW_REQUIRED` | Absence of an earlier member must be supported by cutoff-compatible schedule knowledge. |
| `is_single_leg_chain` | Target/position local | Proof that neither prior nor future member belongs to the chain | May require final/full membership and proof no future member exists | `REVIEW_REQUIRED` | Special review required; if derivation uses final membership, reclassify as `BLOCKED_UNTIL_PROVEN`. |
| `minutes_from_chain_first_departure` | Past-context | Target plus first preceding/target scheduled departure | Past-side membership only if target is not first | `REVIEW_REQUIRED` | Must prove every contributing member and schedule timestamp was known by target cutoff. |
| `minutes_since_previous_scheduled_departure` | Past-context | Target plus immediately preceding scheduled member | Previous member | `REVIEW_REQUIRED` | Scheduled timestamps alone do not prove snapshot availability. |
| `has_previous_chain_leg` | Past-context | Existence of immediately preceding member | Previous member | `REVIEW_REQUIRED` | Historical existence must be tied to cutoff-compatible membership evidence. |
| `previous_leg_destination_matches_target_origin` | Past-context | Previous member destination and target origin | Previous member | `REVIEW_REQUIRED` | Structural endpoint context may be admissible only after member availability proof; it is not aircraft identity. |
| `chain_length` | Future/full-chain | All members and final membership count | Yes: final chain length | `BLOCKED_UNTIL_PROVEN` | Full membership retained does not make the final count predictor-safe. |
| `legs_after_target` | Future/full-chain | All future members after target | Yes | `BLOCKED_UNTIL_PROVEN` | Requires knowledge of future membership. |
| `is_last_chain_leg` | Future/full-chain | Proof no later member exists | Yes: absence of future member | `BLOCKED_UNTIL_PROVEN` | Fails closed without schedule-snapshot evidence. |
| `chain_length_gt_6` | Future/full-chain | Final membership count | Yes | `BLOCKED_UNTIL_PROVEN` | Chains longer than six remain reconstructed, but their final length is not automatically available at T-2h. |
| `minutes_to_chain_last_departure` | Future/full-chain | Target plus final member scheduled departure | Yes | `BLOCKED_UNTIL_PROVEN` | Requires the identity and time of the final future member. |
| `minutes_to_next_scheduled_departure` | Future/full-chain | Target plus immediately next scheduled member | Yes | `BLOCKED_UNTIL_PROVEN` | Requires future member existence and schedule knowledge. |
| `has_next_chain_leg` | Future/full-chain | Existence of a later member | Yes | `BLOCKED_UNTIL_PROVEN` | Historical future membership is not point-in-time evidence. |
| `next_leg_origin_matches_target_destination` | Future/full-chain | Next member origin and target destination | Yes | `BLOCKED_UNTIL_PROVEN` | Requires future member availability and remains structural context only. |
| `chain_schedule_span_minutes` | Future/full-chain | First and final member scheduled departures | Yes: complete span | `BLOCKED_UNTIL_PROVEN` | Depends on final/full-chain membership. |
| `chain_position_fraction` | Future/full-chain | Target position and final chain length | Yes: denominator is full length | `BLOCKED_UNTIL_PROVEN` | Position alone is insufficient; the final length is unproven. |

## Identifier isolation

The following fields remain `IDENTIFIER_ONLY`:

```text
flight_key
chain_id
source_year
source_row_number
```

They may be used only for traceability, deterministic joins, and auditing.
They must not enter `X`, categorical encoders, frequency encoders, embeddings,
interactions, or model-derived feature selection.

## Evidence required for promotion

Promotion from `REVIEW_REQUIRED` or `BLOCKED_UNTIL_PROVEN` to `KEEP_SAFE`
requires a versioned, reviewable evidence record that identifies the exact
feature definition and source/version. Acceptable evidence may include:

- documented primary-source schedule publication and revision semantics;
- a versioned schedule snapshot with an explicit information-availability
  timestamp at or before the target cutoff;
- deterministic proof that the implementation uses only target/past members
  whose complete required schedule/context was known by the cutoff;
- another primary evidence source establishing the same availability claim;
- tests and a manifest recording member direction, inputs, cutoff derivation,
  feature status, policy version, and normal Arrival leakage-gate result.

The evidence must support the exact information set used. A scheduled
`valid/departure` timestamp is not a publication or availability timestamp.

The following are never promotion evidence:

- model performance, correlation, feature importance, or SHAP;
- improved ROC-AUC, PR-AUC, MAE, RMSE, or downstream objective;
- 2023 model-selection or ablation performance;
- any 2024 performance/result, row, distribution, or final-holdout behavior;
- intuition based on operational familiarity;
- the mere presence of a member or timestamp in the final historical dataset.

## Feature availability audit gates

| Gate | Requirement | PASS evidence | Fail-closed outcome |
|---|---|---|---|
| C1 Source semantics | Record that `schedule_chain_v1` is historically reconstructed schedule/service-number context, not physical rotation. | Versioned source/contract reference and feature manifest. | `DROP` if feature relies on aircraft identity; otherwise remain blocked. |
| C2 Target cutoff construction | Derive target cutoff only from canonical target schedule fields. | Deterministic test for `FL_DATE + CRS_DEP_TIME - 2h`; no actual time. | `BLOCKED_UNTIL_PROVEN`. |
| C3 Member time direction | Label every contributing member `past`, `target`, `future`, or `full-chain` relative to target. | Per-feature dependency specification and tests. | `BLOCKED_UNTIL_PROVEN`. |
| C4 Schedule availability | Prove required schedule/membership information was available by cutoff. Final historical presence is insufficient. | Publication/snapshot/availability evidence with source and version. | `BLOCKED_UNTIL_PROVEN`. |
| C5 No actual outcome | Exclude `ARR_DELAY`, `DEP_DELAY`, actual departure/arrival/durations, Weather, `FLIGHTS`, and other realized outcomes. | Static schema/input test plus manifest. | `DROP` or audit FAIL. |
| C6 No target leakage | No direct or indirect derivation from Arrival target or labels. | Dependency lineage and leakage test. | `DROP` or audit FAIL. |
| C7 No future membership assumption | Future member existence/absence, final length, and last member require explicit availability evidence. | Snapshot evidence covering the exact future/full-chain inputs. | `BLOCKED_UNTIL_PROVEN`. |
| C8 Deterministic derivation | Same source/version/config produces the same feature. | Versioned definition, stable ordering/tie-break, repeatability test/fingerprint. | `REVIEW_REQUIRED` or audit FAIL. |
| C9 Identifier isolation | Identifiers stay out of predictor matrices and encoders. | Matrix/schema test and manifest roles. | `IDENTIFIER_ONLY`; predictor build fails. |
| C10 Temporal-fold compatibility | No global statistic or fitted transform uses future folds, 2023, or 2024. | Fold-scoped tests and fit lineage. | Audit FAIL; feature cannot enter `X`. |

Every applicable gate must PASS before registry-first promotion to `KEEP_SAFE`.
An unknown feature or missing evidence fails closed.

## Audit workflow and artifact rule

Week 3B must execute in this order:

```text
3B.0 availability audit
  -> 3B.1 derive candidates
  -> 3B.2 assign per-feature status
  -> 3B.3 materialize a traceable optional artifact
  -> 3B.4 keep ARR-B disabled
```

A blocked/review feature may optionally be materialized only for audit or
research diagnostics. Its manifest must state `ML_ADMISSIBLE = false`, retain
the feature-level status/reason/policy version, and prevent silent inclusion in
predictor matrices. Materialization alone is not promotion evidence.

## PASS/FAIL criteria

Feature-level PASS requires C1–C10 as applicable, explicit `KEEP_SAFE` in the
versioned policy and registry-first change control, tests, manifest lineage,
and a separate PASS through the Core Arrival leakage contract.

Any missing provenance, unknown feature, future/full-chain assumption without
evidence, identifier exposure, actual outcome dependency, nondeterministic
derivation, or temporal-fold contamination is FAIL/BLOCKED. If no candidate
passes, ARR-B remains disabled; the Core Arrival pipeline continues.

## Current decision

```text
CHAIN_FEATURE_POINT_IN_TIME_AVAILABILITY_GATE = AUDIT_REQUIRED
reconstructed_chain_features.ml_enabled = false
ARR-B enabled = false
```

This plan does not perform the audit, derive a feature, read reconstructed
Parquet, generate `reconstructed_chain_features_v1`, run an ablation, train a
model, or access row-level 2024.
