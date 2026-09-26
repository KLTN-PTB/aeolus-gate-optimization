# Assumptions register — current through Week 3

## Purpose

This register separates approved project decisions from implementation
defaults, evidence-based Week-2 resolutions, and unresolved items. Week 1–2
evidence remains complete under its historical protocol; the architecture
amendment dated 2026-08-26 is governed by the authoritative V4 roadmaps and
`docs/decisions/decision_registry.md`. V3 roadmaps remain historical.

## LOCKED

| Area | Current assumption / decision | Source |
|---|---|---|
| Architecture | The project proceeds as Predict -> Simulate -> Optimize -> Evaluate, with Dashboard as the presentation layer. | D001 |
| Scope and temporal protocol | Aeolus 2016–2024; rolling development is 2016–2022, 2023 is development/model selection and downstream development, and 2024 is sealed final end-to-end holdout until full-system freeze. | D002, D011, D020 |
| Core data | Tabular is the mandatory core data source. | D003 |
| Original raw Flight Chain | The evidence-based Week-2 outcome remains `FINAL — NO_GO`; raw `.pt` stays read-only and is excluded from core and ablation. | D004, E003 |
| Reconstructed Schedule Flight Chain | The separate canonical-Tabular-derived `schedule_chain_v1` artifact is `GO_FOR_ABLATION`, disabled by default, and outside core. It represents schedule/service-number context only. | E005 |
| Reconstructed feature availability | E006 completed the T-2h review without schedule publication/version/snapshot evidence: no candidate is `KEEP_SAFE`; 7 local/past candidates remain `REVIEW_REQUIRED`, `is_single_leg_chain` plus 10 future/full-chain candidates are `BLOCKED_UNTIL_PROVEN`, and identifiers remain `IDENTIFIER_ONLY`. | D026, E006 |
| Flight Network | Flight Network/GNN is outside the 12-week core scope. | D005 |
| Hub and flows | ATL is the experimental hub; inbound `DEST=ATL` supports Core Arrival ML; outbound `ORIGIN=ATL` supports Auxiliary Departure ML and synthetic simulation. | D006, D007, D021 |
| Prediction boundary | Both prediction tasks use `T = CRS_DEP_TIME - 2 hours`; any predictor must be available by that time. | D008 |
| Core Arrival targets | `y_arr_cls = 1[ARR_DELAY >= 15]`; `y_arr_reg = ARR_DELAY` signed minutes. | D009, D010, D021 |
| Auxiliary Departure target | `y_dep_cls = 1[DEP_DELAY >= 15]`; no Departure regression in V4. | D021 |
| Weather boundary | Core Arrival uses no Weather and never consumes predicted Departure delay. Auxiliary Departure may compare Schedule-only with Schedule plus separately audited point-in-time Weather. | D022–D024 |
| Downstream source | Only Core Arrival prediction feeds Synthetic Aircraft Turn and gate simulation/optimization. | D025 |
| ML scope | The comparison contains at most Logistic/Ridge, Random Forest, HistGradientBoosting, XGBoost, and Weighted Ensemble. | D012 |
| Raw data | Raw Aeolus files are read-only; generated outputs are written outside `data/raw/`. | D013 |
| Identity boundary | Real aircraft identity is neither used nor reconstructed. Future `TURN_ID` and `SIM_AIRCRAFT_ID` are synthetic only. | D014 |
| Optimization | The future sequence is Greedy -> CP-SAT -> equal-compute CP-SAT + SA. | D015 |
| Gate states | CONTACT_GATE, REMOTE_STAND, and UNASSIGNED remain distinct states. | D016 |
| Robustness | Plan robustness and recourse are distinct; pilots are 20 then 50 scenarios, with 500 only if feasible. | D017 |
| Utility comparison | Schedule-only, ML, and Oracle signed `ARR_DELAY` use the same scenario/solver; Oracle is evaluation-only. | D018 |
| Claim boundary | Synthetic gate/turn outputs are not real ATL operations and do not establish reduced real flight delay. | D019 |
| Gate Environment | Aeolus lacks airport gate assignment and physical aircraft identity — entire airport topology and gate mix are synthetic simulation constructs. | D027 |

## EVIDENCE-BASED WEEK-2 RESOLUTIONS

| Item | Current resolution | Evidence status |
|---|---|---|
| Canonical schema | `canonical_schema_v1`, 34 ordered fields | E004 evidence-based storage contract from all nine annual audits; not a feature-safety claim. |
| Airport index mapping | Cross-year code-to-index mappings are stable | E001 evidence result; predictor treatment remains conditional. |
| Weather core policy | Drop all six raw weather fields from candidate `X` | E002 fail-closed result because T-2h provenance remains insufficient. |
| Original raw Flight Chain | `FINAL — NO_GO`; disabled and excluded from core/ablation | E003 final evidence-based decision. |
| Reconstructed Schedule Flight Chain | `GO_FOR_ABLATION`; optional development-only comparison, not a physical rotation | E005 full 2016–2023 evidence decision. |
| Reconstructed Chain-derived features | Week 3B `COMPLETED_WITH_BLOCKED_ML_BRANCH`; `KEEP_SAFE=[]`; ML/ARR-B disabled | E006 feature-level result. Derivation was skipped and optional diagnostic materialization was not executed; future diagnostics still require `ML_ADMISSIBLE=false`. |

## IMPLEMENTATION DEFAULTS

| Item | Current default | Status / rationale |
|---|---|---|
| Project version | `0.1.0` | Implementation version in `configs/base.yaml`; not a research result. |
| Reproducibility seed | `202601` | I001 implementation default; deterministic but not a scientific claim. |
| Flight key | `flight_key_v1` deterministic traceability hash | I002; not an ML feature or aircraft identifier. |
| Rolling folds | `expanding_window_v1`, four folds ending in validations 2019–2022 | I003; 2023 is outside HPO folds and 2024 is sealed. |
| Point-in-time Weather contract | Provider `TBD`, W1–W15 all-critical provenance gates, UTC normalization, availability-first join, and exact DEP-A/DEP-B row parity | I004; contract preparation is complete but provenance remains `AUDIT_REQUIRED` and disabled. |
| Week 3A information set | Schedule, Calendar, Carrier, and Route only; no Weather, Chain, Departure outcome/prediction, actual operation, identifier, `FLIGHTS`, airport index, or inbound ATL destination constant | `feature_manifest_arrival_v1`; selected before model training. |
| Week 3A preprocessing | Linear and tree/boosting transformer state is fit separately on each fold's training rows; `OP_CARRIER_FL_NUM` is categorical high-cardinality context encoded by a non-target training-frequency map | `feature_pipeline_registry_arrival_v1`; no estimator trained. |
| Week 3A target eligibility | Missing `ARR_DELAY` rows are dropped with explicit counts; target values are never imputed, absolutized, or clipped | `outlier_and_simulation_guard_v1`; label tests. |
| Contact-gate default | `30` | Current V3-aligned baseline configuration for later synthetic simulation; it does not represent actual ATL gate capacity. |
| Scenario scales | `100`, `200`, `300` movements | V3 benchmark scales for later sampled/synthetic scenarios; no scenario has been generated through Week 2. |

## Evidence status and remaining TBD

| Item | Current state | Required evidence before resolution |
|---|---|---|
| Weather provenance and timing | Evidence audit complete; core policy DROP | All six raw fields remain `INSUFFICIENT_EVIDENCE` for T-2h availability and cannot support a safe lag from the released scalar data. See E002 and `weather_timing_audit.md`. |
| External point-in-time Weather | Week 3C contract complete; provider `TBD`, `AUDIT_REQUIRED`, disabled | A separate source/version must pass all W1–W15 availability, timezone, location, provenance, join, parity, and leakage gates before Auxiliary DEP-B. Contract readiness is not source approval; failure blocks only the auxiliary experiment. |
| `FLIGHTS` semantics | TBD | Source documentation and schema evidence. |
| `CRS_ARR_TIME` rollover | Availability as scheduled data is accepted, but its stored date does not prove overnight/date-rollover semantics | Week 3A excludes it from `X` and does not derive elapsed duration; `CRS_ELAPSED_TIME` is used as the audited scheduled duration. |
| `ORIGIN_INDEX` / `DEST_INDEX` | Evidence audit complete | Mapping is stable under E001; predictor treatment remains conditional and inbound destination index is constant. |
| Cross-year canonical schema | Complete | Canonical schema v1 and the 2016–2024 compatibility matrix are versioned. |
| Cancelled/diverted representation | TBD | Primary source/generation documentation is still required; absence of dedicated canonical fields does not prove how omitted or retained operations were generated. |
| Risk buffer, turnaround, pairing, gate mix, objective, compute, SA, and robustness parameters | TBD | Development-only sensitivity/runtime evidence and documented pre-2024 freeze. |

## Change rule

Any change to a LOCKED decision must follow the registry change-control protocol first. An implementation default may change only with a written rationale, synchronized config/test documentation, and never because of 2024 results. A TBD must remain unresolved until its specified evidence exists.
