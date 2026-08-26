# Limitations — current through Week 3

This project is deliberately scoped to the claims supported by the V4
protocol and preserved Week 1–2 evidence. The following limitations must
remain visible in later reports, dashboard, and thesis materials.

- Future gate assignments and Aircraft Turns are synthetic constructs for controlled simulation; they are not real ATL gate operations or gate schedules.
- The project does not use or reconstruct real `TAIL_NUM` or other real aircraft identity. Synthetic identifiers, if later created, do not establish physical aircraft rotation.
- The original Aeolus raw Flight Chain `.pt` received and retains `FINAL — NO_GO`: exact sample-to-Tabular mapping and T−2h safety are not evidenced, while 2024 also has undocumented structural drift.
- The separate Reconstructed Schedule Flight Chain is approved only for later ablation. It groups carrier, operating flight number, and service date; it is not physical aircraft rotation and does not establish predictive improvement. Full membership was retained even when chain length exceeded six.
- Historical final schedule membership cannot automatically be assumed to be
  a point-in-time schedule snapshot. Dataset-level `GO_FOR_ABLATION` therefore
  does not prove that a derived feature was available at target T−2h.
- Future/full-chain structural features require separate availability
  evidence; target/local and past-context candidates also remain under review.
  This is an `availability not yet proven` boundary, not a claim that leakage
  has been observed.
- E006 completed the feature-level audit with no schedule publication,
  version, or point-in-time snapshot evidence. Consequently no reconstructed
  Chain feature is currently `KEEP_SAFE`: 7 remain `REVIEW_REQUIRED`, 11 are
  `BLOCKED_UNTIL_PROVEN`, and the Chain ML branch is
  `BLOCKED_PENDING_NEW_EVIDENCE`. The historical structural artifact remains
  valid; this outcome does not establish that leakage occurred and does not
  block the Tabular-only Core Arrival thesis.
- Week 3B closure did not derive or materialize diagnostic Chain features.
  This was a bounded execution decision—not evidence that the reconstructed
  schedule/service-number context is useless. Availability remains not
  established, and the Core Arrival path is unaffected.
- The Week-2 timing audit found insufficient point-in-time provenance for all six raw weather fields. The core pipeline therefore drops them from candidate `X` while retaining them in stored data; they cannot be promoted without new versioned T-2h evidence.
- Core Arrival deliberately uses no Weather and does not consume predicted
  Departure delay. Its claim is schedule/context-based Arrival prediction.
- Weather is isolated to an auxiliary outbound Departure classification study.
  Schedule+Weather may run only after a separately versioned source proves
  point-in-time availability; otherwise that experiment is
  `BLOCKED_NOT_CORE_FAILURE` and the core thesis continues.
- Week 3C defines the W1–W15 admissibility contract but does not prove that any
  provider satisfies it. Provider selection, Weather acquisition, joining,
  and feature construction remain unperformed; provenance is
  `AUDIT_REQUIRED` and external Weather remains disabled.
- `schedule_chain_v1` and future `reconstructed_chain_features_v1` encode only
  service-number/schedule context. They do not identify a physical aircraft,
  even when adjacent leg endpoints appear to connect.
- The 2016–2024 Tabular schemas were audited year by year and canonical schema v1 is versioned; this does not justify assuming future/raw revisions remain compatible without re-audit.
- Canonical schema compatibility is a storage contract, not proof that every field is point-in-time safe or admissible as an ML predictor. `FLIGHTS` semantics remain unresolved and the field is blocked from candidate predictors.
- The canonical `CRS_ARR_TIME` date component does not prove overnight-arrival
  rollover. Week 3A therefore derives no naive scheduled duration or overnight
  flag from `CRS_DEP_TIME`/`CRS_ARR_TIME`; it uses the separately audited
  scheduled `CRS_ELAPSED_TIME` field.
- Week 3A high-cardinality flight-number frequency maps, categorical
  vocabularies, imputers, and scalers are fold-training statistics. Their
  unknown-category fallbacks preserve transformability but do not establish
  semantic equivalence for unseen carriers/routes.
- Year 2024 is sealed for final end-to-end evaluation after full-system freeze. It cannot be used for development, feature/model/HPO selection, pairing, gate configuration, solver settings, or robustness tuning.
- Future 100/200/300 movement scenarios are sampled/synthetic benchmarks, not representations of all ATL operations in a day.
- Optimizer outcomes address simulated gate-related consequences of delay; they do not demonstrate a reduction in real flight delay minutes.
- Source Chain train/val/test filenames are not the thesis temporal split and cannot replace the locked year-based protocol.

These limitations do not invalidate the planned study; they define the boundary for defensible interpretation.
