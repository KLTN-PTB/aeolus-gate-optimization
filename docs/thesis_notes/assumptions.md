# Assumptions register — current through Week 2

## Purpose

This register separates approved project decisions from implementation defaults, evidence-based Week-2 resolutions, and unresolved items. It records the state at the Week-2 M1 acceptance gate; it does not replace the V3 roadmaps or `docs/decisions/decision_registry.md`.

## LOCKED

| Area | Current assumption / decision | Source |
|---|---|---|
| Architecture | The project proceeds as Predict -> Simulate -> Optimize -> Evaluate, with Dashboard as the presentation layer. | D001 |
| Scope and temporal protocol | Aeolus 2016–2024; rolling development is 2016–2022, 2023 is development/model selection and downstream development, and 2024 is sealed final end-to-end holdout until full-system freeze. | D002, D011, D020 |
| Core data | Tabular is the mandatory core data source. | D003 |
| Flight Chain | The evidence-based Week-2 outcome is `NO_GO`; Tabular-only is the final core route and no Chain ablation is scheduled. Raw Chain remains read-only. | D004, E003 |
| Flight Network | Flight Network/GNN is outside the 12-week core scope. | D005 |
| Hub and flows | ATL is the experimental hub; inbound `DEST=ATL` supports ML and outbound `ORIGIN=ATL` supports synthetic simulation. | D006, D007 |
| Prediction boundary | The core information cut-off is `T = CRS_DEP_TIME - 2 hours`; any predictor must be available by that time. | D008 |
| Targets | Classification is `ARR_DELAY >= 15`; regression is signed `ARR_DELAY` minutes. | D009, D010 |
| ML scope | The comparison contains at most Logistic/Ridge, Random Forest, HistGradientBoosting, XGBoost, and Weighted Ensemble. | D012 |
| Raw data | Raw Aeolus files are read-only; generated outputs are written outside `data/raw/`. | D013 |
| Identity boundary | Real aircraft identity is neither used nor reconstructed. Future `TURN_ID` and `SIM_AIRCRAFT_ID` are synthetic only. | D014 |
| Optimization | The future sequence is Greedy -> CP-SAT -> equal-compute CP-SAT + SA. | D015 |
| Gate states | CONTACT_GATE, REMOTE_STAND, and UNASSIGNED remain distinct states. | D016 |
| Robustness | Plan robustness and recourse are distinct; pilots are 20 then 50 scenarios, with 500 only if feasible. | D017 |
| Utility comparison | Schedule-only, ML, and Oracle signed `ARR_DELAY` use the same scenario/solver; Oracle is evaluation-only. | D018 |
| Claim boundary | Synthetic gate/turn outputs are not real ATL operations and do not establish reduced real flight delay. | D019 |

## EVIDENCE-BASED WEEK-2 RESOLUTIONS

| Item | Current resolution | Evidence status |
|---|---|---|
| Canonical schema | `canonical_schema_v1`, 34 ordered fields | E004 evidence-based storage contract from all nine annual audits; not a feature-safety claim. |
| Airport index mapping | Cross-year code-to-index mappings are stable | E001 evidence result; predictor treatment remains conditional. |
| Weather core policy | Drop all six raw weather fields from candidate `X` | E002 fail-closed result because T-2h provenance remains insufficient. |
| Flight Chain | `NO_GO`; disabled, excluded from core, and no Week-6 ablation | E003 final evidence-based decision. |

## IMPLEMENTATION DEFAULTS

| Item | Current default | Status / rationale |
|---|---|---|
| Project version | `0.1.0` | Implementation version in `configs/base.yaml`; not a research result. |
| Reproducibility seed | `202601` | I001 implementation default; deterministic but not a scientific claim. |
| Flight key | `flight_key_v1` deterministic traceability hash | I002; not an ML feature or aircraft identifier. |
| Rolling folds | `expanding_window_v1`, four folds ending in validations 2019–2022 | I003; 2023 is outside HPO folds and 2024 is sealed. |
| Contact-gate default | `30` | Current V3-aligned baseline configuration for later synthetic simulation; it does not represent actual ATL gate capacity. |
| Scenario scales | `100`, `200`, `300` movements | V3 benchmark scales for later sampled/synthetic scenarios; no scenario has been generated through Week 2. |

## Evidence status and remaining TBD

| Item | Current state | Required evidence before resolution |
|---|---|---|
| Weather provenance and timing | Evidence audit complete; core policy DROP | All six raw fields remain `INSUFFICIENT_EVIDENCE` for T-2h availability and cannot support a safe lag from the released scalar data. See E002 and `weather_timing_audit.md`. |
| `FLIGHTS` semantics | TBD | Source documentation and schema evidence. |
| `ORIGIN_INDEX` / `DEST_INDEX` | Evidence audit complete | Mapping is stable under E001; predictor treatment remains conditional and inbound destination index is constant. |
| Cross-year canonical schema | Complete | Canonical schema v1 and the 2016–2024 compatibility matrix are versioned. |
| Cancelled/diverted representation | TBD | Primary source/generation documentation is still required; absence of dedicated canonical fields does not prove how omitted or retained operations were generated. |
| Risk buffer, turnaround, pairing, gate mix, objective, compute, SA, and robustness parameters | TBD | Development-only sensitivity/runtime evidence and documented pre-2024 freeze. |

## Change rule

Any change to a LOCKED decision must follow the registry change-control protocol first. An implementation default may change only with a written rationale, synchronized config/test documentation, and never because of 2024 results. A TBD must remain unresolved until its specified evidence exists.
