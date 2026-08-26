# Decision — Dual Prediction Architecture V4

Decision date: 2026-08-26  
Protocol version: 4.0  
Status: **LOCKED**

## Context

The V3 baseline centered one inbound-ATL Arrival prediction task and treated
Weather and original Flight Chain as optional inputs pending evidence. Week 2
then established that the six raw Aeolus Weather scalars lack point-in-time
provenance (E002 `DROP`) and that the original raw Flight Chain `.pt` is
`FINAL — NO_GO` (E003). A separate reconstruction from canonical Tabular later
passed full 2016–2023 validation as schedule/service-number context only (E005
`GO_FOR_ABLATION`).

V4 separates the core downstream prediction claim from a narrower auxiliary
Weather question. The amendment was made without model results and without
using 2024 for decision making.

## Previous architecture

V3 used one core Arrival ML branch (`DEST=ATL`) followed by synthetic turn
simulation and gate optimization. Weather was subject to T-2h audit, but the
roadmaps did not isolate a separate Departure experiment. Outbound
`ORIGIN=ATL` served synthetic Aircraft Turn simulation only.

## V4 change

```text
Aeolus Tabular
  ├─ Core Arrival: DEST=ATL -> ARR_DELAY classification + regression
  │    -> Synthetic Aircraft Turn -> Gate Simulation
  │    -> Greedy -> CP-SAT -> CP-SAT+SA -> Monte Carlo
  └─ Auxiliary Departure: ORIGIN=ATL -> DEP_DELAY classification
       Schedule-only vs Schedule + audited point-in-time Weather
       (research-only; no optimizer input)
```

The shared prediction cut-off for both tasks is
`T_prediction = CRS_DEP_TIME - 2 hours`.

## Core Arrival task

- Role: core research task.
- Flow: inbound flights filtered by `DEST=ATL`.
- Classification: `y_arr_cls = 1[ARR_DELAY >= 15]`.
- Regression: `y_arr_reg = ARR_DELAY`, preserving signed negative, zero, and
  positive minutes.
- Candidate families: schedule, calendar, carrier, route, and safe contextual
  features available by T-2h.
- Weather: not allowed, including both the six raw Aeolus Weather fields and
  any external Weather source.
- Forbidden: `DEP_DELAY`, predicted departure-delay probability, actual
  timestamps/durations, and realized operational outcomes.

## Auxiliary Departure task

- Role: auxiliary Weather research task, not a replacement for Arrival.
- Flow: outbound flights filtered by `ORIGIN=ATL`.
- Classification only: `y_dep_cls = 1[DEP_DELAY >= 15]`.
- Regression is outside V4 scope.
- Controlled comparison: DEP-A Schedule-only versus DEP-B Schedule plus
  audited point-in-time Weather. The arms share target rows, temporal
  protocol, preprocessing other than Weather, classifier, random seed, HPO
  budget, and metrics.
- Default controlled classifier: XGBoost Classifier. Logistic Regression may
  be retained only as an optional sanity baseline, not a second five-model
  competition.

## Weather boundary

The raw Aeolus columns `O_TEMP`, `O_PRCP`, `O_WSPD`, `D_TEMP`, `D_PRCP`, and
`D_WSPD` retain `INSUFFICIENT_EVIDENCE` and `DROP_FROM_PREDICTORS` for both
tasks. They are not forecasts, and heuristic lags must not be fabricated from
the released scalars.

External Weather, if later used, is a separate versioned source such as
`weather_point_in_time_v1`. Its current state is `AUDIT_REQUIRED` and disabled.
It becomes admissible only after evidence proves
`information_available_time <= prediction_cutoff`, with timezone, location,
valid time, issue/publication time, variables, source, version, and join
semantics audited.

If provenance fails or remains incomplete, the auxiliary Weather experiment
is `BLOCKED/LIMITATION`; the core Arrival thesis continues.

## Flight Chain role

The two Chain artifacts remain independent:

- Original Aeolus raw Flight Chain `.pt`: `FINAL — NO_GO`, read-only, excluded
  from core and ablation, and never reverse-engineered into aircraft identity.
- Reconstructed Schedule Flight Chain `schedule_chain_v1`:
  `FULL_DATA_PASS`, `GO_FOR_ABLATION`, disabled by default, and outside core.
  It is schedule/service-number context, not `TAIL_NUM` or physical rotation.

Week 3 may plan `reconstructed_chain_features_v1`; Week 6 may compare ARR-A
Tabular-only with ARR-B only when the reconstructed feature subset has passed
the D026 gate and normal Arrival leakage review. Full chain membership is
retained; `max_context_length=6` is future transformer metadata, not a
reconstruction truncation rule.

## Reconstructed Chain predictor-availability boundary

Reconstruction validity is not predictor availability. E005
`GO_FOR_ABLATION` is a dataset-level decision: it permits controlled feature
investigation while preserving full membership for provenance, deterministic
reconstruction, structural analysis, and auditing. It does not mark every
derived feature point-in-time safe.

Under D026, Week 3B must begin with a feature-level availability review against
the target cutoff `target CRS_DEP_TIME - 2 hours`. Target/position-local and
past-context candidates start as `REVIEW_REQUIRED`. Future/full-chain-dependent
candidates start as `BLOCKED_UNTIL_PROVEN`; identifiers remain
`IDENTIFIER_ONLY`. A final historical row or scheduled timestamp is not proof
that the predictor knew the membership or schedule at T-2h.

Only a feature explicitly promoted to `KEEP_SAFE` through registry-first,
versioned evidence may proceed to the separate normal Core Arrival leakage
contract. ARR-B and reconstructed Chain feature ML enablement remain disabled
by default. Audit/diagnostic materialization, if later performed, must record
`ML_ADMISSIBLE = false` for non-approved features and cannot silently populate
a predictor matrix.

### Week 3B.0 evidence outcome (E006, 2026-08-26)

The C1–C10 audit found no schedule publication timestamp, versioned schedule
snapshot, timetable issue/revision history, or equivalent evidence proving
membership knowledge at target T-2h. Therefore `KEEP_SAFE = []`: seven
target/local or past-context candidates remain `REVIEW_REQUIRED`,
`is_single_leg_chain` and ten future/full-chain candidates are
`BLOCKED_UNTIL_PROVEN`, and four identifiers remain `IDENTIFIER_ONLY`.

This does not revise E005: `schedule_chain_v1` remains dataset-level
`GO_FOR_ABLATION`. Week 3B.1 is permitted only as diagnostic materialization
with `ML_ADMISSIBLE=false`; Chain ML and ARR-B remain disabled pending new
primary/versioned availability evidence.

## Downstream optimizer boundary

Only frozen Core Arrival predictions feed Synthetic Aircraft Turn, gate
simulation, Greedy, CP-SAT, CP-SAT+SA, and Monte Carlo. Auxiliary Departure
predictions and Weather features never feed the V4 optimizer. Existing gate
states, synthetic-identity semantics, equal-compute comparison, and robustness
protocol remain unchanged.

## Temporal protocol

- 2016–2022: expanding-window rolling development and HPO.
- 2023: model selection, controlled ablation, and downstream development.
- 2024: sealed final end-to-end holdout after full-system freeze.

No 2024 row-level data or target distribution informed this amendment.

## Consequences

1. Config and leakage APIs become task-aware while defaulting to Arrival for
   compatible historical callers.
2. Arrival preprocessing has an explicit no-Weather boundary.
3. Auxiliary Weather preparation cannot block Week 3 Arrival work.
4. External Weather requires separate storage/provenance; it cannot be placed
   under Aeolus raw Tabular or represented as canonical Aeolus Weather.
5. The five-method cap continues to apply to Core Arrival only.
6. V3 roadmaps remain historical; the three V4 roadmaps are authoritative for
   current work.

## Non-goals

This amendment does not implement preprocessing, feature engineering,
Weather acquisition/API/joining, model training, HPO, SHAP, Chain ablation,
2023 selection, 2024 evaluation, simulation, optimization, or Monte Carlo. It
does not regenerate any Week 1–2 or reconstructed Chain artifact.

## Affected files

- `configs/base.yaml`
- `configs/reconstructed_chain_feature_policy.yaml`
- `src/data/leakage_rules.py`
- `src/features/chain_feature_policy.py`
- `tests/test_base_config.py`, `tests/test_leakage_rules.py`,
  `tests/test_chain_feature_policy.py`
- `scripts/smoke_test.py`
- the V4 roadmap set, decision registry, README, project structure, Weather
  audit/plan, assumptions, limitations, and experiment log

No `.docx` is changed. The thesis proposal requires a later semantic sync.

## Change-control rule

Any change to task roles, targets, threshold, T-2h cut-off, Weather boundary,
Chain status, Chain-feature availability status, temporal roles, or optimizer
input must be registry-first and synchronized across config, policy, leakage
rules, tests, all three authoritative V4 roadmaps, README, project structure,
reports, and thesis materials. It must never be selected from model
performance, 2023, or 2024 results.
