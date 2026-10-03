# Day 3 LightGBM diagnostics

Date: 2026-09-21

This note records the two follow-up diagnostics after the default LightGBM
native-categorical benchmark. They use the locked rolling protocol: V1.1,
25,000 training rows per year, 25,000 validation rows, seeds 42--46, and
validation years 2019--2022. Row-level access is restricted to 2016--2022;
2023 and 2024 were not opened.

Artifacts:

- `artifacts/manifests/day3_lightgbm_l1_ordinal_v1.json`
- `artifacts/manifests/day3_lightgbm_l2_reduced_v1.json`

## Diagnostic 1 — L1 ordinal

Configuration: `objective="regression_l1"`, `metric="mae"`,
`num_leaves=31`, `learning_rate=0.05`, `n_estimators=500`,
`min_data_in_leaf=20`. The model matrix is produced by the same
`build_v1_1_tree_preprocessor()` used by XGBoost B2. This removes native
categorical handling from the comparison while keeping the feature set and
capacity defaults aligned.

| Model | Fold 4 skill | Macro 4-fold skill | Fold 4 MAE | Macro MAE |
|---|---:|---:|---:|---:|
| XGBoost B2 | -0.2519% | +0.4091% | 19.8864 | 16.8225 |
| LightGBM default native L1 | -0.8292% | -0.8615% | 20.0005 | 17.0201 |
| LightGBM L1 ordinal | +0.0491% | -0.2402% | 19.8266 | 16.9179 |

L1 ordinal improves over default native L1 by `+0.8783pp` on Fold 4 and
`+0.6213pp` on macro. Therefore the native-categorical representation is a
material contributor to the default LightGBM failure under this protocol.
This diagnostic does not isolate which categorical column is responsible;
the high-cardinality `OP_CARRIER_FL_NUM` remains a plausible contributor,
but that claim requires a separate ablation.

L1 ordinal is still below B2 on the canonical macro metric by `-0.6493pp`,
although its Fold 4 result is `+0.3010pp` better than B2. Therefore the
result is not “LightGBM is approximately B2 and only needs parameter tuning”
on the rolling protocol. The algorithm/parameter combination remains behind
B2 in macro performance.

Per-fold L1 ordinal skill was:

| Validation year | 2019 | 2020 | 2021 | 2022 |
|---|---:|---:|---:|---:|
| Skill | -0.0506% | -0.1518% | -0.8077% | +0.0491% |

This is not a monotone decline: 2021 to 2022 improves by `+0.8568pp`, but
the 2021 result is weak and the macro remains negative.

## Diagnostic 2 — L2 reduced capacity

Configuration: native categorical V1.1, `objective="regression"` (LightGBM
L2), `metric="mae"`, `num_leaves=15`, `n_estimators=200`,
`min_data_in_leaf=50`, `lambda_l2=1.0`, and `learning_rate=0.05`.

| Model | Fold 4 skill | Macro 4-fold skill | Fold 4 MAE | Macro MAE |
|---|---:|---:|---:|---:|
| XGBoost B2 | -0.2519% | +0.4091% | 19.8864 | 16.8225 |
| LightGBM L2 reduced native | -5.2815% | -16.7483% | 20.8835 | 19.5074 |

Compared with B2, the reduced L2 model is `-5.0296pp` worse on Fold 4 and
`-17.1574pp` worse on macro. It is also much worse than default native L1.
The capacity-reduction hypothesis is therefore not supported: this tested
reduced-capacity configuration does not approach B2.

## Decision

1. Native categorical handling is harmful relative to the ordinal
   preprocessor for LightGBM L1 in this benchmark.
2. Removing native categoricals does not make LightGBM competitive with B2
   on macro; the model class/configuration remains inferior under the tested
   defaults.
3. Reduced-capacity LightGBM L2 is decisively worse and is rejected as a
   candidate configuration.
4. XGBoost B2 remains the reference model. No HPO, ensemble, V1.3
   interaction run, or Decision Registry update was performed in this
   diagnostic task. The existing temporal/generalization warning remains.

The benchmark artifacts contain the complete parameter dictionaries, seeds,
sample sizes, protocol years, input-manifest hashes, and runner hash needed
for reproduction.
