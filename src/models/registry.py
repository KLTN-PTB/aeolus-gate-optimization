"""Authoritative Model Registry for Aeolus Gate Optimization.

Eliminates heuristic filename inference by providing an explicit, machine-readable,
and fail-closed catalog of all models, their operational tasks, architectural
capabilities, and lifecycle statuses.

Rules:
1. No script may infer model status from file name or directory name.
2. Unknown model IDs or statuses fail closed immediately.
3. Legacy/Historical models (e.g. B5 NGBoost Student-T) are preserved under 'legacy_frozen'
   and are never automatically treated as the V4 core champion.
4. Core Arrival models operate with strictly NO Weather features.
5. Auxiliary Departure models are isolated and forbidden from feeding downstream optimization.
6. Core Point methods are strictly capped at 5 canonical families.
7. Downstream gate optimization queries must use is_downstream_eligible(model_id).
"""

from __future__ import annotations

from typing import Final, Sequence

from src.models.interfaces import (
    ModelCapability,
    ModelCategory,
    ModelSpec,
    ModelStatus,
    ModelTarget,
    ModelTask,
    ModelType,
)

CORE_METHOD_CAP: Final[int] = 5

_MODEL_CATALOG: dict[str, ModelSpec] = {
    # -------------------------------------------------------------------------
    # A. Current Core V4 Models — Exactly 5 Canonical Families (Cap = 5)
    # -------------------------------------------------------------------------
    "arrival_linear_baseline_v1": ModelSpec(
        model_id="arrival_linear_baseline_v1",
        family="linear",
        task=ModelTask.CORE_ARRIVAL.value,
        target=ModelTarget.ARRIVAL_DELAY_SIGNED.value,
        probabilistic=False,
        supports_predict=True,
        supports_predict_proba=True,
        supports_distribution=False,
        feature_set="schedule_calendar_carrier_route_v1",
        preprocessing="standard_scaler_one_hot_fit_on_train_only",
        seed_policy="fixed_seed_202601",
        hpo_policy="none_deterministic_baseline",
        status=ModelStatus.CURRENT_CORE.value,
        category=ModelCategory.CORE_POINT.value,
        downstream_eligible=True,
        feature_version="v1",
        preprocessing_version="v1",
        random_seed=202601,
        hpo_budget="none",
        artifact_version="v1.0",
        capabilities=frozenset([ModelCapability.POINT_REGRESSION.value, ModelCapability.POINT_CLASSIFICATION.value]),
        selection_role="core_point_linear_baseline",
        development_period="2016-2022",
        distribution_capability="point_only",
        source_path="src/models/linear_models.py",
        implementation_class="RidgeArrivalModel",
    ),
    "arrival_random_forest_baseline_v1": ModelSpec(
        model_id="arrival_random_forest_baseline_v1",
        family="random_forest",
        task=ModelTask.CORE_ARRIVAL.value,
        target=ModelTarget.ARRIVAL_DELAY_SIGNED.value,
        probabilistic=False,
        supports_predict=True,
        supports_predict_proba=True,
        supports_distribution=False,
        feature_set="schedule_calendar_carrier_route_v1",
        preprocessing="ordinal_encoder_fit_on_train_only",
        seed_policy="fixed_seed_202601",
        hpo_policy="default_scikit_learn_hyperparameters",
        status=ModelStatus.CURRENT_CORE.value,
        category=ModelCategory.CORE_POINT.value,
        downstream_eligible=True,
        feature_version="v1",
        preprocessing_version="v1",
        random_seed=202601,
        hpo_budget="none",
        artifact_version="v1.0",
        capabilities=frozenset([ModelCapability.POINT_REGRESSION.value, ModelCapability.POINT_CLASSIFICATION.value]),
        selection_role="core_point_tree_baseline",
        development_period="2016-2022",
        distribution_capability="point_only",
        source_path="src/models/random_forest_models.py",
        implementation_class="RandomForestArrivalModel",
    ),
    "arrival_hist_gradient_boosting_baseline_v1": ModelSpec(
        model_id="arrival_hist_gradient_boosting_baseline_v1",
        family="hist_gradient_boosting",
        task=ModelTask.CORE_ARRIVAL.value,
        target=ModelTarget.ARRIVAL_DELAY_SIGNED.value,
        probabilistic=False,
        supports_predict=True,
        supports_predict_proba=True,
        supports_distribution=False,
        feature_set="schedule_calendar_carrier_route_v1",
        preprocessing="native_categorical_support_fit_on_train_only",
        seed_policy="fixed_seed_202601",
        hpo_policy="default_scikit_learn_hyperparameters",
        status=ModelStatus.CURRENT_CORE.value,
        category=ModelCategory.CORE_POINT.value,
        downstream_eligible=True,
        feature_version="v1",
        preprocessing_version="v1",
        random_seed=202601,
        hpo_budget="none",
        artifact_version="v1.0",
        capabilities=frozenset([ModelCapability.POINT_REGRESSION.value, ModelCapability.POINT_CLASSIFICATION.value]),
        selection_role="core_point_hgb_baseline",
        development_period="2016-2022",
        distribution_capability="point_only",
        source_path="src/models/hist_gradient_boosting_models.py",
        implementation_class="HistGradientBoostingArrivalModel",
    ),
    "arrival_xgboost_baseline_v1": ModelSpec(
        model_id="arrival_xgboost_baseline_v1",
        family="xgboost",
        task=ModelTask.CORE_ARRIVAL.value,
        target=ModelTarget.ARRIVAL_DELAY_SIGNED.value,
        probabilistic=False,
        supports_predict=True,
        supports_predict_proba=True,
        supports_distribution=False,
        feature_set="schedule_calendar_carrier_route_v1",
        preprocessing="target_encoding_or_ordinal_fit_on_train_only",
        seed_policy="fixed_seed_202601",
        hpo_policy="default_xgboost_hyperparameters",
        status=ModelStatus.CURRENT_CORE.value,
        category=ModelCategory.CORE_POINT.value,
        downstream_eligible=True,
        feature_version="v1",
        preprocessing_version="v1",
        random_seed=202601,
        hpo_budget="none",
        artifact_version="v1.0",
        capabilities=frozenset([ModelCapability.POINT_REGRESSION.value, ModelCapability.POINT_CLASSIFICATION.value]),
        selection_role="core_point_xgboost_baseline",
        development_period="2016-2022",
        distribution_capability="point_only",
        source_path="src/models/week5_xgboost.py",
        implementation_class="XGBoostArrivalModel",
    ),
    "arrival_weighted_ensemble_v1": ModelSpec(
        model_id="arrival_weighted_ensemble_v1",
        family="weighted_ensemble",
        task=ModelTask.CORE_ARRIVAL.value,
        target=ModelTarget.ARRIVAL_DELAY_SIGNED.value,
        probabilistic=False,
        supports_predict=True,
        supports_predict_proba=True,
        supports_distribution=False,
        feature_set="schedule_calendar_carrier_route_v1",
        preprocessing="inherited_from_base_models",
        seed_policy="fixed_seed_202601",
        hpo_policy="inverse_mae_cv_weighting",
        status=ModelStatus.CURRENT_CORE.value,
        category=ModelCategory.CORE_POINT.value,
        downstream_eligible=True,
        feature_version="v1",
        preprocessing_version="v1",
        random_seed=202601,
        hpo_budget="none",
        artifact_version="v1.0",
        capabilities=frozenset([ModelCapability.POINT_REGRESSION.value]),
        selection_role="core_point_ensemble",
        development_period="2016-2022",
        distribution_capability="point_only",
        source_path="src/evaluation/model_selection.py",
        implementation_class="InverseVarianceWeightedEnsemble",
    ),

    # -------------------------------------------------------------------------
    # B. Current Core V4 Models — Week 5 HPO Tuned Variants (Under Base Families)
    # -------------------------------------------------------------------------
    "arrival_random_forest_tuned_v1_1": ModelSpec(
        model_id="arrival_random_forest_tuned_v1_1",
        family="random_forest",
        task=ModelTask.CORE_ARRIVAL.value,
        target=ModelTarget.ARRIVAL_DELAY_SIGNED.value,
        probabilistic=False,
        supports_predict=True,
        supports_predict_proba=True,
        supports_distribution=False,
        feature_set="schedule_calendar_carrier_route_v1",
        preprocessing="ordinal_encoder_fit_on_train_only",
        seed_policy="fixed_seed_202601",
        hpo_policy="optuna_10_trials_rolling_folds_1_to_4",
        status=ModelStatus.CURRENT_CORE.value,
        category=ModelCategory.TUNED_VARIANT.value,
        downstream_eligible=True,
        feature_version="v1.1",
        preprocessing_version="v1",
        random_seed=202601,
        hpo_budget="10_trials",
        artifact_version="v1.1",
        capabilities=frozenset([ModelCapability.POINT_REGRESSION.value, ModelCapability.POINT_CLASSIFICATION.value]),
        selection_role="tuned_variant",
        development_period="2016-2022",
        distribution_capability="point_only",
        source_path="src/models/week5_random_forest_hpo.py",
        implementation_class="RandomForestArrivalModel",
        variant_of="arrival_random_forest_baseline_v1",
    ),
    "arrival_hist_gradient_boosting_tuned_v1_1": ModelSpec(
        model_id="arrival_hist_gradient_boosting_tuned_v1_1",
        family="hist_gradient_boosting",
        task=ModelTask.CORE_ARRIVAL.value,
        target=ModelTarget.ARRIVAL_DELAY_SIGNED.value,
        probabilistic=False,
        supports_predict=True,
        supports_predict_proba=True,
        supports_distribution=False,
        feature_set="schedule_calendar_carrier_route_v1",
        preprocessing="native_categorical_support_fit_on_train_only",
        seed_policy="fixed_seed_202601",
        hpo_policy="optuna_10_trials_rolling_folds_1_to_4",
        status=ModelStatus.CURRENT_CORE.value,
        category=ModelCategory.TUNED_VARIANT.value,
        downstream_eligible=True,
        feature_version="v1.1",
        preprocessing_version="v1",
        random_seed=202601,
        hpo_budget="10_trials",
        artifact_version="v1.1",
        capabilities=frozenset([ModelCapability.POINT_REGRESSION.value, ModelCapability.POINT_CLASSIFICATION.value]),
        selection_role="tuned_variant",
        development_period="2016-2022",
        distribution_capability="point_only",
        source_path="src/models/week5_hist_gradient_boosting_hpo.py",
        implementation_class="HistGradientBoostingArrivalModel",
        variant_of="arrival_hist_gradient_boosting_baseline_v1",
    ),
    "arrival_xgboost_tuned_v1_1": ModelSpec(
        model_id="arrival_xgboost_tuned_v1_1",
        family="xgboost",
        task=ModelTask.CORE_ARRIVAL.value,
        target=ModelTarget.ARRIVAL_DELAY_SIGNED.value,
        probabilistic=False,
        supports_predict=True,
        supports_predict_proba=True,
        supports_distribution=False,
        feature_set="schedule_calendar_carrier_route_v1",
        preprocessing="target_encoding_fit_on_train_only",
        seed_policy="fixed_seed_202601",
        hpo_policy="optuna_10_trials_rolling_folds_1_to_4",
        status=ModelStatus.CURRENT_CORE.value,
        category=ModelCategory.TUNED_VARIANT.value,
        downstream_eligible=True,
        feature_version="v1.1",
        preprocessing_version="v1",
        random_seed=202601,
        hpo_budget="10_trials",
        artifact_version="v1.1",
        capabilities=frozenset([ModelCapability.POINT_REGRESSION.value, ModelCapability.POINT_CLASSIFICATION.value]),
        selection_role="tuned_variant",
        development_period="2016-2022",
        distribution_capability="point_only",
        source_path="src/models/week5_xgboost_hpo.py",
        implementation_class="XGBoostArrivalModel",
        variant_of="arrival_xgboost_baseline_v1",
    ),

    # -------------------------------------------------------------------------
    # C. Probabilistic Research Candidates (P1–P5 Distributional Models)
    # -------------------------------------------------------------------------
    "P1_empirical": ModelSpec(
        model_id="P1_empirical",
        family="empirical_carrier_hour",
        task=ModelTask.CORE_ARRIVAL.value,
        target=ModelTarget.ARRIVAL_DELAY_SIGNED.value,
        probabilistic=True,
        supports_predict=True,
        supports_predict_proba=True,
        supports_distribution=True,
        feature_set="schedule_calendar_carrier_route_v1",
        preprocessing="carrier_hour_empirical_fit_on_train_only",
        seed_policy="screening_seed_202601",
        hpo_policy="none",
        status=ModelStatus.RESEARCH_CANDIDATE.value,
        category=ModelCategory.PROBABILISTIC_CANDIDATE.value,
        downstream_eligible=False,
        feature_version="v1",
        preprocessing_version="v1",
        random_seed=202601,
        hpo_budget="none",
        artifact_version="v1.0",
        capabilities=frozenset([ModelCapability.PROBABILISTIC.value, ModelCapability.SAMPLING.value]),
        selection_role="probabilistic_candidate_p1",
        development_period="2016-2022",
        distribution_capability="empirical_distribution",
        source_path="src/models/probabilistic/candidate_interfaces.py",
        implementation_class="P1EmpiricalCandidate",
    ),
    "P2_xgb_gaussian_oof": ModelSpec(
        model_id="P2_xgb_gaussian_oof",
        family="xgb_gaussian_oof",
        task=ModelTask.CORE_ARRIVAL.value,
        target=ModelTarget.ARRIVAL_DELAY_SIGNED.value,
        probabilistic=True,
        supports_predict=True,
        supports_predict_proba=True,
        supports_distribution=True,
        feature_set="schedule_calendar_carrier_route_v1",
        preprocessing="target_encoding_or_ordinal_fit_on_train_only",
        seed_policy="screening_seed_202601",
        hpo_policy="none",
        status=ModelStatus.RESEARCH_CANDIDATE.value,
        category=ModelCategory.PROBABILISTIC_CANDIDATE.value,
        downstream_eligible=False,
        feature_version="v1",
        preprocessing_version="v1",
        random_seed=202601,
        hpo_budget="none",
        artifact_version="v1.0",
        capabilities=frozenset([ModelCapability.PROBABILISTIC.value, ModelCapability.SAMPLING.value]),
        selection_role="probabilistic_candidate_p2",
        development_period="2016-2022",
        distribution_capability="fixed_sigma_gaussian",
        source_path="src/models/probabilistic/candidate_interfaces.py",
        implementation_class="P2XGBoostGaussianCandidate",
    ),
    "P3_ngboost_normal": ModelSpec(
        model_id="P3_ngboost_normal",
        family="ngboost_normal",
        task=ModelTask.CORE_ARRIVAL.value,
        target=ModelTarget.ARRIVAL_DELAY_SIGNED.value,
        probabilistic=True,
        supports_predict=True,
        supports_predict_proba=True,
        supports_distribution=True,
        feature_set="schedule_calendar_carrier_route_v1",
        preprocessing="standard_scaler_fitted_on_train_only",
        seed_policy="screening_seed_202601",
        hpo_policy="none",
        status=ModelStatus.RESEARCH_CANDIDATE.value,
        category=ModelCategory.PROBABILISTIC_CANDIDATE.value,
        downstream_eligible=False,
        feature_version="v1",
        preprocessing_version="v1",
        random_seed=202601,
        hpo_budget="none",
        artifact_version="v1.0",
        capabilities=frozenset([ModelCapability.PROBABILISTIC.value, ModelCapability.SAMPLING.value]),
        selection_role="probabilistic_candidate_p3",
        development_period="2016-2022",
        distribution_capability="heteroscedastic_gaussian",
        source_path="src/models/probabilistic/candidate_interfaces.py",
        implementation_class="P3NGBoostNormalCandidate",
    ),
    "P4_ngboost_student_t": ModelSpec(
        model_id="P4_ngboost_student_t",
        family="ngboost_student_t",
        task=ModelTask.CORE_ARRIVAL.value,
        target=ModelTarget.ARRIVAL_DELAY_SIGNED.value,
        probabilistic=True,
        supports_predict=True,
        supports_predict_proba=True,
        supports_distribution=True,
        feature_set="schedule_calendar_carrier_route_v1",
        preprocessing="standard_scaler_fitted_on_train_only",
        seed_policy="screening_seed_202601",
        hpo_policy="none",
        status=ModelStatus.RESEARCH_CANDIDATE.value,
        category=ModelCategory.PROBABILISTIC_CANDIDATE.value,
        downstream_eligible=False,
        feature_version="v1",
        preprocessing_version="v1",
        random_seed=202601,
        hpo_budget="none",
        artifact_version="v1.0",
        capabilities=frozenset([ModelCapability.PROBABILISTIC.value, ModelCapability.SAMPLING.value]),
        selection_role="probabilistic_candidate_p4_heavy_tail",
        development_period="2016-2022",
        distribution_capability="heteroscedastic_student_t",
        source_path="src/models/probabilistic/candidate_interfaces.py",
        implementation_class="P4NGBoostStudentTCandidate",
    ),
    "P5_quantile_regression": ModelSpec(
        model_id="P5_quantile_regression",
        family="quantile_regression",
        task=ModelTask.CORE_ARRIVAL.value,
        target=ModelTarget.ARRIVAL_DELAY_SIGNED.value,
        probabilistic=True,
        supports_predict=True,
        supports_predict_proba=False,
        supports_distribution=True,
        feature_set="schedule_calendar_carrier_route_v1",
        preprocessing="native_or_ordinal_fit_on_train_only",
        seed_policy="screening_seed_202601",
        hpo_policy="multi_pinball_loss",
        status=ModelStatus.RESEARCH_CANDIDATE.value,
        category=ModelCategory.PROBABILISTIC_CANDIDATE.value,
        downstream_eligible=False,
        feature_version="v1",
        preprocessing_version="v1",
        random_seed=202601,
        hpo_budget="none",
        artifact_version="v1.0",
        capabilities=frozenset([ModelCapability.PROBABILISTIC.value]),
        selection_role="probabilistic_candidate_p5_quantile",
        development_period="2016-2022",
        distribution_capability="multi_pinball_quantiles",
        source_path="src/models/probabilistic/candidate_interfaces.py",
        implementation_class="P5QuantileRegressionCandidate",
    ),

    # -------------------------------------------------------------------------
    # D. Active Research Candidates (Ablation / Specialized)
    # -------------------------------------------------------------------------
    "arrival_hurdle_predictor_two_stage": ModelSpec(
        model_id="arrival_hurdle_predictor_two_stage",
        family="two_stage_hurdle",
        task=ModelTask.CORE_ARRIVAL.value,
        target=ModelTarget.ARRIVAL_DELAY_SIGNED.value,
        probabilistic=False,
        supports_predict=True,
        supports_predict_proba=True,
        supports_distribution=False,
        feature_set="schedule_calendar_carrier_route_v1",
        preprocessing="standard_and_ordinal_fit_on_train_only",
        seed_policy="fixed_seed_202601",
        hpo_policy="two_stage_independent_fit",
        status=ModelStatus.RESEARCH_CANDIDATE.value,
        category=ModelCategory.RESEARCH_CANDIDATE.value,
        downstream_eligible=False,
        feature_version="v1",
        preprocessing_version="v1",
        random_seed=202601,
        hpo_budget="none",
        artifact_version="v1.0",
        capabilities=frozenset([ModelCapability.POINT_REGRESSION.value, ModelCapability.CALIBRATED_PROBABILITY.value]),
        selection_role="hurdle_ablation_candidate",
        development_period="2016-2022",
        distribution_capability="point_and_classification_probability",
        source_path="src/models/hurdle_inference.py",
        implementation_class="HurdlePredictor",
    ),

    # -------------------------------------------------------------------------
    # E. Auxiliary Departure Task (Research only — NEVER downstream eligible)
    # -------------------------------------------------------------------------
    "departure_auxiliary_baseline_v1": ModelSpec(
        model_id="departure_auxiliary_baseline_v1",
        family="linear",
        task=ModelTask.AUXILIARY_DEPARTURE.value,
        target=ModelTarget.DEPARTURE_DELAY_BINARY_15.value,
        probabilistic=False,
        supports_predict=True,
        supports_predict_proba=True,
        supports_distribution=False,
        feature_set="departure_schedule_calendar_carrier_route_v1",
        preprocessing="standard_scaler_one_hot_fit_on_train_only",
        seed_policy="fixed_seed_202601",
        hpo_policy="none_deterministic_baseline",
        status=ModelStatus.RESEARCH_CANDIDATE.value,
        category=ModelCategory.AUXILIARY_DEPARTURE.value,
        downstream_eligible=False,
        feature_version="v1",
        preprocessing_version="v1",
        random_seed=202601,
        hpo_budget="none",
        artifact_version="v1.0",
        capabilities=frozenset([ModelCapability.POINT_CLASSIFICATION.value]),
        selection_role="auxiliary_departure_classification",
        development_period="2016-2022",
        distribution_capability="binary_classification_probability",
        source_path="src/models/linear_models.py",
        implementation_class="LogisticRegressionDepartureModel",
    ),

    # -------------------------------------------------------------------------
    # F. Core Departure Task (Dual Core V1 — predicting signed DEP_DELAY)
    # -------------------------------------------------------------------------
    "departure_linear_baseline_v1": ModelSpec(
        model_id="departure_linear_baseline_v1",
        family="linear",
        task=ModelTask.CORE_DEPARTURE.value,
        target=ModelTarget.DEPARTURE_DELAY_SIGNED.value,
        probabilistic=False,
        supports_predict=True,
        supports_predict_proba=False,
        supports_distribution=False,
        feature_set="departure_schedule_calendar_carrier_route_v1",
        preprocessing="standard_scaler_one_hot_fit_on_train_only",
        seed_policy="fixed_seed_202601",
        hpo_policy="none_deterministic_baseline",
        status=ModelStatus.RESEARCH_CANDIDATE.value,
        category=ModelCategory.CORE_DEPARTURE.value,
        downstream_eligible=False,
        feature_version="v1",
        preprocessing_version="v1",
        random_seed=202601,
        hpo_budget="none",
        artifact_version="v1.0",
        capabilities=frozenset([ModelCapability.POINT_REGRESSION.value]),
        selection_role="core_departure_linear_baseline",
        development_period="2016-2022",
        distribution_capability="point_only",
        source_path="src/models/linear_models.py",
        implementation_class="RidgeDepartureModel",
    ),
    "departure_ridge_baseline_v1": ModelSpec(
        model_id="departure_ridge_baseline_v1",
        family="linear",
        task=ModelTask.CORE_DEPARTURE.value,
        target=ModelTarget.DEPARTURE_DELAY_SIGNED.value,
        probabilistic=False,
        supports_predict=True,
        supports_predict_proba=False,
        supports_distribution=False,
        feature_set="departure_schedule_calendar_carrier_route_v1",
        preprocessing="standard_scaler_one_hot_fit_on_train_only",
        seed_policy="fixed_seed_202601",
        hpo_policy="none_deterministic_baseline",
        status=ModelStatus.RESEARCH_CANDIDATE.value,
        category=ModelCategory.CORE_DEPARTURE.value,
        downstream_eligible=False,
        feature_version="v1",
        preprocessing_version="v1",
        random_seed=202601,
        hpo_budget="none",
        artifact_version="v1.0",
        capabilities=frozenset([ModelCapability.POINT_REGRESSION.value]),
        selection_role="core_departure_ridge_baseline",
        development_period="2016-2022",
        distribution_capability="point_only",
        source_path="src/models/linear_models.py",
        implementation_class="RidgeDepartureModel",
    ),
    "departure_xgboost_baseline_v1": ModelSpec(
        model_id="departure_xgboost_baseline_v1",
        family="xgboost",
        task=ModelTask.CORE_DEPARTURE.value,
        target=ModelTarget.DEPARTURE_DELAY_SIGNED.value,
        probabilistic=False,
        supports_predict=True,
        supports_predict_proba=False,
        supports_distribution=False,
        feature_set="departure_schedule_calendar_carrier_route_v1",
        preprocessing="ordinal_frequency_fit_on_train_only",
        seed_policy="fixed_seed_202601",
        hpo_policy="none_deterministic_baseline",
        status=ModelStatus.RESEARCH_CANDIDATE.value,
        category=ModelCategory.CORE_DEPARTURE.value,
        downstream_eligible=False,
        feature_version="v1",
        preprocessing_version="v1",
        random_seed=202601,
        hpo_budget="none",
        artifact_version="v1.0",
        capabilities=frozenset([ModelCapability.POINT_REGRESSION.value]),
        selection_role="core_departure_xgboost_baseline",
        development_period="2016-2022",
        distribution_capability="point_only",
        source_path="src/models/xgboost_models.py",
        implementation_class="XGBoostDepartureModel",
    ),
    "departure_certified_point_v1": ModelSpec(
        model_id="departure_certified_point_v1",
        family="xgboost",
        task=ModelTask.CORE_DEPARTURE.value,
        target=ModelTarget.DEPARTURE_DELAY_SIGNED.value,
        probabilistic=False,
        supports_predict=True,
        supports_predict_proba=False,
        supports_distribution=False,
        feature_set="departure_schedule_calendar_carrier_route_v1",
        preprocessing="ordinal_frequency_fit_on_train_only",
        seed_policy="fixed_seed_202601",
        hpo_policy="none_deterministic_baseline",
        status=ModelStatus.DOWNSTREAM_ELIGIBLE.value,
        category=ModelCategory.CORE_DEPARTURE.value,
        downstream_eligible=True,
        feature_version="v1",
        preprocessing_version="v1",
        random_seed=202601,
        hpo_budget="none",
        artifact_version="v1.0",
        capabilities=frozenset([ModelCapability.POINT_REGRESSION.value]),
        selection_role="GATE_OUT_PREDICTION",
        development_period="2016-2022",
        distribution_capability="point_only",
        source_path="src/models/xgboost_models.py",
        implementation_class="XGBoostDepartureModel",
    ),
    "departure_empirical_residual_v1": ModelSpec(
        model_id="departure_empirical_residual_v1",
        family="empirical",
        task=ModelTask.CORE_DEPARTURE.value,
        target=ModelTarget.DEPARTURE_DELAY_SIGNED.value,
        probabilistic=True,
        supports_predict=True,
        supports_predict_proba=True,
        supports_distribution=True,
        feature_set="departure_schedule_calendar_carrier_route_v1",
        preprocessing="empirical_grouped_fit_on_train_only",
        seed_policy="fixed_seed_202601",
        hpo_policy="none_deterministic_baseline",
        status=ModelStatus.RESEARCH_CANDIDATE.value,
        category=ModelCategory.CORE_DEPARTURE.value,
        downstream_eligible=False,
        feature_version="v1",
        preprocessing_version="v1",
        random_seed=202601,
        hpo_budget="none",
        artifact_version="v1.0",
        capabilities=frozenset([
            ModelCapability.PROBABILISTIC.value,
            ModelCapability.SAMPLING.value,
            ModelCapability.POINT_REGRESSION.value,
        ]),
        selection_role="core_departure_empirical_residual_baseline",
        development_period="2016-2022",
        distribution_capability="empirical_grouped",
        source_path="src/models/probabilistic/departure_distributions.py",
        implementation_class="DepartureEmpiricalBaseline",
    ),
    "departure_gaussian_residual_v1": ModelSpec(
        model_id="departure_gaussian_residual_v1",
        family="gaussian_residual",
        task=ModelTask.CORE_DEPARTURE.value,
        target=ModelTarget.DEPARTURE_DELAY_SIGNED.value,
        probabilistic=True,
        supports_predict=True,
        supports_predict_proba=True,
        supports_distribution=True,
        feature_set="departure_schedule_calendar_carrier_route_v1",
        preprocessing="ordinal_frequency_fit_on_train_only",
        seed_policy="fixed_seed_202601",
        hpo_policy="none_deterministic_baseline",
        status=ModelStatus.RESEARCH_CANDIDATE.value,
        category=ModelCategory.CORE_DEPARTURE.value,
        downstream_eligible=False,
        feature_version="v1",
        preprocessing_version="v1",
        random_seed=202601,
        hpo_budget="none",
        artifact_version="v1.0",
        capabilities=frozenset([
            ModelCapability.PROBABILISTIC.value,
            ModelCapability.SAMPLING.value,
            ModelCapability.POINT_REGRESSION.value,
            ModelCapability.CALIBRATED_PROBABILITY.value,
        ]),
        selection_role="core_departure_gaussian_residual_candidate",
        development_period="2016-2022",
        distribution_capability="homoscedastic_gaussian",
        source_path="src/models/probabilistic/departure_distributions.py",
        implementation_class="DepartureGaussianResidualModel",
    ),
    "departure_ngboost_normal_v1": ModelSpec(
        model_id="departure_ngboost_normal_v1",
        family="ngboost_normal",
        task=ModelTask.CORE_DEPARTURE.value,
        target=ModelTarget.DEPARTURE_DELAY_SIGNED.value,
        probabilistic=True,
        supports_predict=True,
        supports_predict_proba=True,
        supports_distribution=True,
        feature_set="departure_schedule_calendar_carrier_route_v1",
        preprocessing="ordinal_frequency_fit_on_train_only",
        seed_policy="fixed_seed_202601",
        hpo_policy="none_deterministic_baseline",
        status=ModelStatus.RESEARCH_CANDIDATE.value,
        category=ModelCategory.CORE_DEPARTURE.value,
        downstream_eligible=False,
        feature_version="v1",
        preprocessing_version="v1",
        random_seed=202601,
        hpo_budget="none",
        artifact_version="v1.0",
        capabilities=frozenset([
            ModelCapability.PROBABILISTIC.value,
            ModelCapability.SAMPLING.value,
            ModelCapability.POINT_REGRESSION.value,
            ModelCapability.CALIBRATED_PROBABILITY.value,
        ]),
        selection_role="core_departure_ngboost_normal_candidate",
        development_period="2016-2022",
        distribution_capability="heteroscedastic_gaussian",
        source_path="src/models/probabilistic/departure_distributions.py",
        implementation_class="DepartureNGBoostNormalModel",
    ),
    "departure_ngboost_student_t_v1": ModelSpec(
        model_id="departure_ngboost_student_t_v1",
        family="ngboost_student_t",
        task=ModelTask.CORE_DEPARTURE.value,
        target=ModelTarget.DEPARTURE_DELAY_SIGNED.value,
        probabilistic=True,
        supports_predict=True,
        supports_predict_proba=True,
        supports_distribution=True,
        feature_set="departure_schedule_calendar_carrier_route_v1",
        preprocessing="ordinal_frequency_fit_on_train_only",
        seed_policy="fixed_seed_202601",
        hpo_policy="none_deterministic_baseline",
        status=ModelStatus.RESEARCH_CANDIDATE.value,
        category=ModelCategory.CORE_DEPARTURE.value,
        downstream_eligible=False,
        feature_version="v1",
        preprocessing_version="v1",
        random_seed=202601,
        hpo_budget="none",
        artifact_version="v1.0",
        capabilities=frozenset([
            ModelCapability.PROBABILISTIC.value,
            ModelCapability.SAMPLING.value,
            ModelCapability.POINT_REGRESSION.value,
            ModelCapability.CALIBRATED_PROBABILITY.value,
        ]),
        selection_role="core_departure_ngboost_student_t_candidate",
        development_period="2016-2022",
        distribution_capability="heteroscedastic_student_t",
        source_path="src/models/probabilistic/departure_distributions.py",
        implementation_class="DepartureNGBoostStudentTModel",
    ),
    "departure_quantile_baseline_v1": ModelSpec(
        model_id="departure_quantile_baseline_v1",
        family="quantile_regression",
        task=ModelTask.CORE_DEPARTURE.value,
        target=ModelTarget.DEPARTURE_DELAY_SIGNED.value,
        probabilistic=True,
        supports_predict=True,
        supports_predict_proba=False,
        supports_distribution=True,
        feature_set="departure_schedule_calendar_carrier_route_v1",
        preprocessing="ordinal_frequency_fit_on_train_only",
        seed_policy="fixed_seed_202601",
        hpo_policy="none_deterministic_baseline",
        status=ModelStatus.RESEARCH_CANDIDATE.value,
        category=ModelCategory.CORE_DEPARTURE.value,
        downstream_eligible=False,
        feature_version="v1",
        preprocessing_version="v1",
        random_seed=202601,
        hpo_budget="none",
        artifact_version="v1.0",
        capabilities=frozenset([
            ModelCapability.PROBABILISTIC.value,
            ModelCapability.POINT_REGRESSION.value,
        ]),
        selection_role="core_departure_quantile_baseline",
        development_period="2016-2022",
        distribution_capability="quantile_grid",
        source_path="src/models/probabilistic/departure_distributions.py",
        implementation_class="DepartureQuantileModel",
    ),
    "departure_distribution_v1": ModelSpec(
        model_id="departure_distribution_v1",
        family="ngboost_student_t",
        task=ModelTask.CORE_DEPARTURE.value,
        target=ModelTarget.DEPARTURE_DELAY_SIGNED.value,
        probabilistic=True,
        supports_predict=True,
        supports_predict_proba=True,
        supports_distribution=True,
        feature_set="departure_schedule_calendar_carrier_route_v1",
        preprocessing="ordinal_frequency_fit_on_train_only",
        seed_policy="fixed_seed_202601",
        hpo_policy="none_deterministic_baseline",
        status=ModelStatus.RESEARCH_CANDIDATE.value,
        category=ModelCategory.CORE_DEPARTURE.value,
        downstream_eligible=False,
        feature_version="v1",
        preprocessing_version="v1",
        random_seed=202601,
        hpo_budget="none",
        artifact_version="v1.0",
        capabilities=frozenset([
            ModelCapability.PROBABILISTIC.value,
            ModelCapability.SAMPLING.value,
            ModelCapability.POINT_REGRESSION.value,
            ModelCapability.CALIBRATED_PROBABILITY.value,
        ]),
        selection_role="core_departure_probabilistic_champion",
        development_period="2016-2022",
        distribution_capability="heteroscedastic_student_t",
        source_path="src/models/probabilistic/departure_distributions.py",
        implementation_class="DepartureNGBoostStudentTModel",
    ),

    # -------------------------------------------------------------------------
    # G. Legacy / Historical Frozen Models
    # -------------------------------------------------------------------------
    "b5_ngboost_student_t": ModelSpec(
        model_id="b5_ngboost_student_t",
        family="ngboost",
        task=ModelTask.CORE_ARRIVAL.value,
        target=ModelTarget.ARRIVAL_DELAY_SIGNED.value,
        probabilistic=True,
        supports_predict=True,
        supports_predict_proba=True,
        supports_distribution=True,
        feature_set="probabilistic_11_schedule_calendar_carrier_route",
        preprocessing="standard_scaler_fitted_pre_freeze",
        seed_policy="predetermined_deployment_seed_202601",
        hpo_policy="frozen_stage10_checkpoint",
        status=ModelStatus.LEGACY_FROZEN.value,
        category=ModelCategory.LEGACY_FROZEN.value,
        downstream_eligible=True,
        feature_version="stage10_frozen",
        preprocessing_version="stage10_frozen",
        random_seed=202601,
        hpo_budget="frozen",
        artifact_version="stage10_frozen_v1",
        capabilities=frozenset([
            ModelCapability.PROBABILISTIC.value,
            ModelCapability.SAMPLING.value,
            ModelCapability.POINT_REGRESSION.value,
        ]),
        selection_role="historical_probabilistic_comparator",
        development_period="2016-2022",
        distribution_capability="heteroscedastic_student_t",
        source_path="src/models/probabilistic/baselines.py",
        implementation_class="B5NGBoostStudentT",
    ),
}


def register_model(spec: ModelSpec) -> None:
    """Register a new ModelSpec or override an existing one (e.g. for testing)."""
    if not isinstance(spec, ModelSpec):
        raise TypeError(f"spec must be a ModelSpec instance, got {type(spec)}")
    _MODEL_CATALOG[spec.model_id] = spec


def unregister_model(model_id: str) -> None:
    """Unregister a model by ID (e.g. cleanup after mock testing)."""
    _MODEL_CATALOG.pop(model_id, None)


def get_model_spec(model_id: str) -> ModelSpec:
    """Return the exact ModelSpec for a model_id; fails closed on unknown names."""
    if model_id not in _MODEL_CATALOG:
        valid_ids = sorted(_MODEL_CATALOG.keys())
        raise KeyError(
            f"Unknown model_id '{model_id}'. Fail-closed: model must be explicitly "
            f"registered in src/models/registry.py. Valid IDs: {valid_ids}"
        )
    return _MODEL_CATALOG[model_id]


def list_models(
    *,
    status: str | ModelStatus | None = None,
    category: str | ModelCategory | None = None,
    task: str | ModelTask | None = None,
    probabilistic: bool | None = None,
    downstream_eligible: bool | None = None,
) -> list[ModelSpec]:
    """Filter models from the registry with fail-closed category validation."""
    status_filter: str | None = None
    if status is not None:
        status_filter = status.value if isinstance(status, ModelStatus) else str(status)
        valid_statuses = {s.value for s in ModelStatus}
        if status_filter not in valid_statuses:
            raise ValueError(f"Unknown status filter '{status_filter}'. Must be one of {valid_statuses}.")

    category_filter: str | None = None
    if category is not None:
        category_filter = category.value if isinstance(category, ModelCategory) else str(category)
        valid_categories = {c.value for c in ModelCategory}
        if category_filter not in valid_categories:
            raise ValueError(f"Unknown category filter '{category_filter}'. Must be one of {valid_categories}.")

    task_filter: str | None = None
    if task is not None:
        task_filter = task.value if isinstance(task, ModelTask) else str(task)
        valid_tasks = {t.value for t in ModelTask}
        if task_filter not in valid_tasks:
            raise ValueError(f"Unknown task filter '{task_filter}'. Must be one of {valid_tasks}.")

    results = []
    for spec in _MODEL_CATALOG.values():
        if status_filter is not None and spec.status != status_filter:
            continue
        if category_filter is not None and spec.category != category_filter:
            continue
        if task_filter is not None and spec.task != task_filter:
            continue
        if probabilistic is not None and spec.probabilistic != probabilistic:
            continue
        if downstream_eligible is not None and spec.downstream_eligible != downstream_eligible:
            continue
        results.append(spec)
    return results


def get_core_point_models() -> list[ModelSpec]:
    """Return the exactly 5 canonical Core Point models respecting the Core 5-method cap."""
    return list_models(category=ModelCategory.CORE_POINT)


def get_core_point_families() -> list[str]:
    """Return the 5 audited core method families."""
    return [
        "linear",
        "random_forest",
        "hist_gradient_boosting",
        "xgboost",
        "weighted_ensemble",
    ]


def get_current_core_models() -> list[ModelSpec]:
    """Return all models classified with status CURRENT_CORE (baselines and tuned variants)."""
    return list_models(status=ModelStatus.CURRENT_CORE)


def get_tuned_variants() -> list[ModelSpec]:
    """Return all Week 5 Optuna HPO tuned variants under core families."""
    return list_models(category=ModelCategory.TUNED_VARIANT)


def get_probabilistic_candidates() -> list[ModelSpec]:
    """Return all academic research probabilistic candidates (P1–P5)."""
    return list_models(category=ModelCategory.PROBABILISTIC_CANDIDATE)


def get_legacy_models() -> list[ModelSpec]:
    """Return all models classified as LEGACY_FROZEN or HISTORICAL."""
    return [
        spec
        for spec in _MODEL_CATALOG.values()
        if spec.status in {ModelStatus.LEGACY_FROZEN.value, ModelStatus.HISTORICAL.value}
    ]


def get_auxiliary_models() -> list[ModelSpec]:
    """Return all auxiliary departure models."""
    return list_models(category=ModelCategory.AUXILIARY_DEPARTURE)


def get_core_departure_models() -> list[ModelSpec]:
    """Return all models categorized under CORE_DEPARTURE."""
    return list_models(category=ModelCategory.CORE_DEPARTURE)


def get_downstream_eligible_models() -> list[ModelSpec]:
    """Return all models certified to feed downstream gate optimization."""
    return list_models(downstream_eligible=True)


def get_point_models() -> list[ModelSpec]:
    """Return all point regression / classification models."""
    return list_models(probabilistic=False)


def get_probabilistic_models() -> list[ModelSpec]:
    """Return all probabilistic distribution forecasting models."""
    return list_models(probabilistic=True)


def is_downstream_eligible(model_id: str) -> bool:
    """Return True if model_id is certified downstream eligible; fail closed on unknown or prohibited models."""
    if model_id not in _MODEL_CATALOG:
        return False
    spec = _MODEL_CATALOG[model_id]
    # Auxiliary departure models are NEVER eligible for gate optimization
    if spec.task == ModelTask.AUXILIARY_DEPARTURE.value:
        return False
    # Core Departure models require explicit role certification: GATE_OUT_PREDICTION
    if spec.task == ModelTask.CORE_DEPARTURE.value:
        if spec.selection_role != "GATE_OUT_PREDICTION":
            return False
        return bool(spec.downstream_eligible)
    # Core Arrival models must be explicitly downstream eligible
    if spec.task != ModelTask.CORE_ARRIVAL.value:
        return False
    # Only models explicitly flagged as downstream_eligible can pass
    return bool(spec.downstream_eligible)


def assert_downstream_eligible(model_id: str) -> None:
    """Raise KeyError or ValueError if model_id is not certified downstream eligible; fail closed."""
    if model_id not in _MODEL_CATALOG:
        raise KeyError(
            f"Unknown model_id '{model_id}' is not registered. Fail-closed: model must be "
            "registered before downstream eligibility verification."
        )
    spec = _MODEL_CATALOG[model_id]
    if not is_downstream_eligible(model_id):
        raise ValueError(
            f"Model '{model_id}' (task={spec.task}, category={spec.category}, status={spec.status}) "
            "is NOT downstream eligible for gate optimization."
        )


def validate_model_status(status_str: str) -> ModelStatus:
    """Validate a status string and return the enum; fails closed on unknown strings."""
    try:
        return ModelStatus(status_str)
    except ValueError as exc:
        valid_values = [s.value for s in ModelStatus]
        raise ValueError(
            f"Invalid model status '{status_str}'. Fail-closed: must be one of {valid_values}."
        ) from exc
