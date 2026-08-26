# Reconstructed Chain Feature Availability Audit V1

Audit date: 2026-08-26  
Protocol: Research Protocol V4.0  
Source artifact: `schedule_chain_v1`  
Dataset-level status: `FULL_DATA_PASS / GO_FOR_ABLATION`  
Prediction cutoff: `target CRS_DEP_TIME - 2 hours`  
Audit status: **COMPLETED**  
External evidence used: **NO**

## Decision

The available evidence does not establish that the final historical schedule
membership reconstructed by `schedule_chain_v1` was a versioned schedule
snapshot published and available at target T-2h. Therefore:

```text
KEEP_SAFE_FEATURES = []
CHAIN_ML_BRANCH = BLOCKED_PENDING_NEW_EVIDENCE
ARR-B enabled = false
```

This is a successful fail-closed audit result. It does not reverse E005:
`schedule_chain_v1` remains a valid historical structural artifact and remains
`GO_FOR_ABLATION` at dataset level. E006 separately records that no derived
candidate is currently approved for ML predictor use.

## Evidence inspected

The audit inspected these existing versioned project sources without reading
row-level Parquet or opening raw `.pt` archives:

1. `docs/decisions/decision_registry.md`, especially D004, D008, D011, D026,
   E003, E005, and the unchanged temporal/change-control rules.
2. `docs/decisions/decision_dual_prediction_architecture_v4.md` and
   `docs/decisions/decision_reconstructed_chain.md`.
3. `docs/dataset_audit/reconstructed_chain_feature_availability_plan_v1.md`.
4. `docs/dataset_audit/flight_chain_reconstruction_report.md`,
   `canonical_schema_v1.md`, `data_dictionary_v1.md`, `leakage_audit.md`, and
   the preserved raw-Chain feasibility report.
5. `artifacts/manifests/flight_chain_reconstructed_manifest_v1.json`.
6. `configs/base.yaml`, `configs/reconstructed_chain_feature_policy.yaml`,
   `src/features/chain_feature_policy.py`,
   `src/data/flight_chain_reconstruction.py`, `src/data/leakage_rules.py`, and
   `src/data/temporal_protocol.py`.
7. All three authoritative V4 roadmap documents.

The repository-wide primary-evidence search found no schedule publication
timestamp, schedule snapshot version, timetable issue timestamp, schedule
revision history, or equivalent field proving complete membership availability
at T-2h.

## Evidence not available

No inspected source provides any of the following:

- a timestamp showing when each scheduled row or membership relation was
  published or made available;
- a versioned schedule snapshot representing the information state at target
  cutoff;
- revision/cancellation history supporting positive or negative membership
  claims at cutoff;
- equivalent primary evidence that the final same-day carrier/flight-number
  group was completely knowable at T-2h.

The final historical presence of a row proves only that the row exists in the
released historical data. Historical absence proves only absence from that
final dataset. Neither is a point-in-time publication fact.

```text
EXTERNAL_EVIDENCE_USED = NO
```

No external research was needed: current project evidence is sufficient to
reach the conservative no-promotion outcome. No evidence was selected merely
because it would allow a feature to pass.

## Method

For every candidate, the audit recorded:

1. contributing target, past, future, or full-chain rows;
2. exact scheduled/provenance fields needed;
3. whether member existence or member absence must be known;
4. whether final length or future membership is required;
5. whether point-in-time publication/snapshot evidence exists;
6. whether the same value could in principle be computed from a complete
   versioned point-in-time snapshot;
7. C4 schedule-availability and C7 future-membership results;
8. a final fail-closed policy status independent of model performance.

No feature was derived. No model, correlation, SHAP, metric, 2023 performance,
or 2024 row was used. The audit did not use actual operations to infer prior
membership.

## Feature-by-feature decision table

All rows below use scheduled/provenance fields only. “Conditional snapshot”
means deterministic computation would be possible only if a complete,
versioned schedule snapshot with `available_time <= target_cutoff` were later
provided; no such snapshot currently exists.

| Feature | Initial status | Required information | Past/future/full dependency | Evidence available? | C4 schedule availability | C7 future membership | Final status | Reason |
|---|---|---|---|---|---|---|---|---|
| `chain_position` | `REVIEW_REQUIRED` | Target plus all ordered preceding members; group fields, scheduled departure, deterministic tie-break fields | Past + target | NO | `UNPROVEN` | N/A | `REVIEW_REQUIRED` | Final historical order does not timestamp when complete preceding membership became known. |
| `legs_before_target` | `REVIEW_REQUIRED` | Complete preceding membership and order | Past + target | NO | `UNPROVEN` | N/A | `REVIEW_REQUIRED` | An earlier scheduled time is not schedule-publication evidence. |
| `is_first_chain_leg` | `REVIEW_REQUIRED` | Proof no earlier same-group member exists | Past + target; absence claim | NO | `UNPROVEN` | N/A | `REVIEW_REQUIRED` | Historical absence does not establish point-in-time snapshot completeness. |
| `is_single_leg_chain` | `REVIEW_REQUIRED` | Proof no earlier **and** no future same-group member exists; final member count | Past + target + future + full-chain | NO | `UNPROVEN` | `FAIL_CLOSED_UNPROVEN` | `BLOCKED_UNTIL_PROVEN` | This is a full-membership claim, so the initial local classification is tightened. |
| `minutes_from_chain_first_departure` | `REVIEW_REQUIRED` | Target and earliest preceding/target scheduled departure | Past + target | NO | `UNPROVEN` | N/A | `REVIEW_REQUIRED` | Scheduled clocks are deterministic, but identity/availability of the first member is unproven. |
| `minutes_since_previous_scheduled_departure` | `REVIEW_REQUIRED` | Target and immediately previous scheduled departure, or proof none exists | Past + target; existence/absence | NO | `UNPROVEN` | N/A | `REVIEW_REQUIRED` | Historical adjacency is not a cutoff-time schedule snapshot; actual occurrence cannot substitute. |
| `has_previous_chain_leg` | `REVIEW_REQUIRED` | Existence or complete absence of a previous member | Past + target; existence/absence | NO | `UNPROVEN` | N/A | `REVIEW_REQUIRED` | Membership availability has no publication timestamp. |
| `previous_leg_destination_matches_target_origin` | `REVIEW_REQUIRED` | Previous-member identity/destination and target origin, or proof none exists | Past + target | NO | `UNPROVEN` | N/A | `REVIEW_REQUIRED` | Endpoint fields are scheduled, but the previous-member relation is unproven and is not aircraft identity. |
| `chain_length` | `BLOCKED_UNTIL_PROVEN` | Complete final membership count | Full-chain | NO | `UNPROVEN` | `FAIL_CLOSED_UNPROVEN` | Final length is hindsight from the completed historical table. |
| `legs_after_target` | `BLOCKED_UNTIL_PROVEN` | Every future member and proof the list is complete | Future + full-chain | NO | `UNPROVEN` | `FAIL_CLOSED_UNPROVEN` | Future membership is not proven known at cutoff. |
| `is_last_chain_leg` | `BLOCKED_UNTIL_PROVEN` | Proof no later member exists | Future absence | NO | `UNPROVEN` | `FAIL_CLOSED_UNPROVEN` | A negative future-membership claim requires snapshot completeness. |
| `chain_length_gt_6` | `BLOCKED_UNTIL_PROVEN` | Complete final count compared with six | Future + full-chain | NO | `UNPROVEN` | `FAIL_CLOSED_UNPROVEN` | Full reconstruction of long chains does not make final length predictor-safe. |
| `minutes_to_chain_last_departure` | `BLOCKED_UNTIL_PROVEN` | Identity/time of final member and proof no later member exists | Future + full-chain | NO | `UNPROVEN` | `FAIL_CLOSED_UNPROVEN` | Last-member knowledge requires complete future membership. |
| `minutes_to_next_scheduled_departure` | `BLOCKED_UNTIL_PROVEN` | Immediately next scheduled member/time, or proof none exists | Future | NO | `UNPROVEN` | `FAIL_CLOSED_UNPROVEN` | Final historical presence is not a publication/availability timestamp. |
| `has_next_chain_leg` | `BLOCKED_UNTIL_PROVEN` | Existence or complete absence of a later member | Future | NO | `UNPROVEN` | `FAIL_CLOSED_UNPROVEN` | Future-member existence/absence is unproven at T-2h. |
| `next_leg_origin_matches_target_destination` | `BLOCKED_UNTIL_PROVEN` | Next-member identity/origin and target destination, or proof none exists | Future | NO | `UNPROVEN` | `FAIL_CLOSED_UNPROVEN` | The relation requires an unproven future member and remains structural only. |
| `chain_schedule_span_minutes` | `BLOCKED_UNTIL_PROVEN` | First/last member scheduled departures and complete endpoints | Past + future + full-chain | NO | `UNPROVEN` | `FAIL_CLOSED_UNPROVEN` | The final endpoint and complete span are unavailable without a snapshot. |
| `chain_position_fraction` | `BLOCKED_UNTIL_PROVEN` | Target position and final chain length denominator | Past + target + future + full-chain | NO | `UNPROVEN` | `FAIL_CLOSED_UNPROVEN` | Final chain length is required and unavailable. |
| `flight_key` | `IDENTIFIER_ONLY` | Target row identity | Identifier | N/A | N/A | N/A | `IDENTIFIER_ONLY` | Traceability/join/audit only; never encoded or used in `X`. |
| `chain_id` | `IDENTIFIER_ONLY` | Reconstructed group identity | Identifier | N/A | N/A | N/A | `IDENTIFIER_ONLY` | Traceability/join/audit only; not an aircraft identity and never a predictor. |
| `source_year` | `IDENTIFIER_ONLY` | Partition/provenance | Identifier | N/A | N/A | N/A | `IDENTIFIER_ONLY` | Temporal routing and audit only; never a predictor. |
| `source_row_number` | `IDENTIFIER_ONLY` | Source row traceability | Identifier | N/A | N/A | N/A | `IDENTIFIER_ONLY` | Audit/row identity only; never a predictor. |

Every membership-derived candidate would be deterministically reconstructable
from an appropriate complete point-in-time snapshot. That conditional
computability is not current availability evidence and grants no promotion.

## C1-C10 results

| Gate | Result | Evidence/consequence |
|---|---|---|
| C1 Source semantics | `PASS` | `schedule_chain_v1` is historical schedule/service-number context, not physical aircraft rotation. |
| C2 Target cutoff | `PASS` | The audit uses `target CRS_DEP_TIME - 2 hours`; no actual time. |
| C3 Member direction | `PASS` | Every candidate is classified by past/target/future/full-chain direction. |
| C4 Schedule availability | `UNPROVEN` | No schedule publication/snapshot/availability evidence exists; no candidate is `KEEP_SAFE`. |
| C5 No actual outcome | `PASS` | Definitions require schedule/provenance fields only. Actual operations, outcomes, Weather, and `FLIGHTS` are prohibited. |
| C6 No target leakage | `PASS` | No candidate definition uses `ARR_DELAY` or Arrival labels. |
| C7 No future assumption | `PASS_FAIL_CLOSED` | Every future/full-chain feature, including `is_single_leg_chain`, is blocked. |
| C8 Deterministic derivation | `PENDING_IMPLEMENTATION` | Source grouping/order is deterministic; Week 3B.0 did not implement or execute feature derivation. |
| C9 Identifier isolation | `PASS` | Four identifiers remain `IDENTIFIER_ONLY`. |
| C10 Temporal-fold compatibility | `PASS_POLICY_ONLY` | No fitted state/performance was used; any future implementation remains subject to fold tests. |

`C4=UNPROVEN` and `C8=PENDING_IMPLEMENTATION` are feature-evidence outcomes,
not failures of this audit. The audit passes because they are recorded and
enforced fail closed.

## Approved, review, and blocked subsets

### Approved ML subset

```text
KEEP_SAFE_FEATURES = []
```

### Review-required subset

```text
chain_position
legs_before_target
is_first_chain_leg
minutes_from_chain_first_departure
minutes_since_previous_scheduled_departure
has_previous_chain_leg
previous_leg_destination_matches_target_origin
```

These seven features remain blocked from predictor matrices. `REVIEW_REQUIRED`
does not mean provisionally safe.

### Blocked subset

```text
is_single_leg_chain
chain_length
legs_after_target
is_last_chain_leg
chain_length_gt_6
minutes_to_chain_last_departure
minutes_to_next_scheduled_departure
has_next_chain_leg
next_leg_origin_matches_target_destination
chain_schedule_span_minutes
chain_position_fraction
```

### Identifier-only fields

```text
flight_key
chain_id
source_year
source_row_number
```

## Branch and materialization decision

Week 3B.1 is permitted only on the documented diagnostic path. A future
diagnostic artifact may include review/blocked fields for structural research
only when every such field and the artifact manifest state:

```text
ML_ADMISSIBLE=false
```

The diagnostic artifact must have no code path into Core Arrival `X`.
ML-directed materialization is not permitted, and ARR-B remains disabled.
No `reconstructed_chain_features_v1` artifact was generated by this audit.

## Limitations

This result does not claim that reconstructed features are inherently leaky or
can never become safe. It states that availability is **not established** by
the current evidence. A new primary/versioned schedule source could change the
feature-level result if it records snapshot completeness and information
availability at or before each target cutoff.

The audit does not test derivation determinism, join coverage, or fold behavior
because Week 3B.1 was explicitly outside scope. It uses no evidence from 2023
performance or row-level 2024.

## Change-control rule

Any promotion requires all of the following before predictor use:

1. new primary/versioned publication, revision, or point-in-time snapshot
   evidence for the exact required membership information;
2. registry-first update preserving E005/E006 history;
3. updated policy YAML, audit manifest, feature manifest, and tests;
4. deterministic Week 3B.1 lineage and identifier-isolation evidence;
5. a separate PASS through the normal Core Arrival leakage contract.

Model performance, correlation, SHAP, 2023 selection, and 2024 results can
never promote a feature.

## Final decision

```text
WEEK_3B_0_CHAIN_FEATURE_AVAILABILITY_AUDIT = PASS
KEEP_SAFE_FEATURE_COUNT = 0
READY_FOR_WEEK_3B_1_ML = NO
READY_FOR_WEEK_3B_1_DIAGNOSTIC_ONLY = YES
CHAIN_ML_BRANCH = BLOCKED_PENDING_NEW_EVIDENCE
ARR-B enabled = false
```
