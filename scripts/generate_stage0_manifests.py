"""Generate versioned Stage 0 manifests for Probabilistic Core Arrival.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md
Artifacts generated:
1. artifacts/manifests/probabilistic_protocol_v1.json
2. artifacts/manifests/representation_manifest_v1.json
3. artifacts/manifests/seed_manifest_v1.json
4. artifacts/manifests/distribution_candidate_manifest_v1.json
5. artifacts/manifests/dependence_candidate_manifest_v1.json
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.models.probabilistic.contracts import (
    CALIBRATION_80_BOUNDS,
    CALIBRATION_90_BOUNDS,
    CATEGORICAL_EMBEDDING_COLUMNS,
    CYCLIC_SOURCE_COLUMNS,
    DEFAULT_SIGMA_FLOOR,
    DELTA_SCREEN,
    DEPENDENCE_CANDIDATE_VERSION,
    DISTRIBUTION_CANDIDATE_VERSION,
    FINALIST_SEEDS,
    FORECAST_EFFECT_SIZE_DELTA,
    GRADIENT_CLIP_NORM,
    JOINT_DEPENDENCE_FAMILIES,
    K5_MIN_COMPONENT_WEIGHT,
    K5_MIN_CRPS_IMPROVEMENT_DELTA,
    K5_MIN_EFFECTIVE_COMPONENTS,
    NUMERIC_SCALED_COLUMNS,
    PREDETERMINED_DEPLOYMENT_SEED,
    PRIMARY_LIKELIHOOD_SPECIFICATION,
    PROBABILISTIC_PREDICTOR_COLUMNS,
    PROBABILISTIC_PROTOCOL_VERSION,
    QUANTILE_CROSSING_CORRECTION,
    REPRESENTATION_VERSION,
    SCREENING_SEED,
    SECONDARY_LIKELIHOOD_SPECIFICATION,
    SEED_ENSEMBLE_CANDIDATE_ID,
    SEED_MANIFEST_VERSION,
    SEED_POLICY,
    SIGMA_FLOOR_SENSITIVITY_GRID,
    STAGE_1_BASELINES,
    STAGE_2_REPRESENTATIONS,
    STAGE_3_DISTRIBUTIONS,
    TAIL_BRIER_60_MAX_GAP,
    TARGET_COLUMN,
    TARGET_QUANTIZATION_INTERVAL,
    TARGET_SEMANTICS_DECISION,
    TARGET_STORAGE_DTYPE,
    TARGET_VALUE_GRANULARITY_MINUTES,
)
from src.models.probabilistic.splitting import FROZEN_PROBABILISTIC_FOLDS


def compute_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate_manifests() -> None:
    root = Path(__file__).resolve().parent.parent
    manifests_dir = root / "artifacts" / "manifests"
    manifests_dir.mkdir(parents=True, exist_ok=True)

    protocol_doc = root / "docs" / "Aeolus_Probabilistic_Core_Arrival_Protocol.md"
    feature_manifest = manifests_dir / "feature_manifest_arrival_v1.json"
    temporal_manifest = manifests_dir / "temporal_folds_manifest.json"
    base_config = root / "configs" / "base.yaml"

    protocol_sha256 = compute_sha256(protocol_doc)
    feature_manifest_sha256 = compute_sha256(feature_manifest)
    temporal_manifest_sha256 = compute_sha256(temporal_manifest)
    base_config_sha256 = compute_sha256(base_config)

    created_at_utc = "2026-09-27T08:55:00Z"

    # 1. probabilistic_protocol_v1.json
    probabilistic_protocol = {
        "manifest_version": PROBABILISTIC_PROTOCOL_VERSION,
        "created_at_utc": created_at_utc,
        "protocol_document": "docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md",
        "protocol_document_sha256": protocol_sha256,
        "task": "arrival_core",
        "hub": "ATL",
        "flow": "inbound",
        "target_filter": "DEST=ATL",
        "prediction_cutoff": "CRS_DEP_TIME - 2 hours",
        "target_semantics_audit": {
            "status": "AUDITED_PASS",
            "target_column": TARGET_COLUMN,
            "inspected_years": [2016, 2017, 2018, 2019, 2020, 2021, 2022],
            "total_inspected_rows": 2380528,
            "storage_dtype": TARGET_STORAGE_DTYPE,
            "fractional_value_count": 0,
            "fractional_value_frequency": 0.0,
            "min_delay_minutes": -202.0,
            "max_delay_minutes": 2108.0,
            "value_granularity_minutes": TARGET_VALUE_GRANULARITY_MINUTES,
            "source_semantics": (
                "BTS TranStats airline on-time performance reporting: integer minutes difference "
                "between actual gate arrival (ARR_TIME) and scheduled gate arrival (CRS_ARR_TIME)"
            ),
            "decision_record": TARGET_SEMANTICS_DECISION,
            "primary_likelihood_specification": PRIMARY_LIKELIHOOD_SPECIFICATION,
            "secondary_likelihood_specification": SECONDARY_LIKELIHOOD_SPECIFICATION,
            "quantization_interval": TARGET_QUANTIZATION_INTERVAL,
        },
        "temporal_protocol": {
            "expanding_window_version": "expanding_window_v1",
            "temporal_manifest": "artifacts/manifests/temporal_folds_manifest.json",
            "temporal_manifest_sha256": temporal_manifest_sha256,
            "rolling_development_years": [2016, 2017, 2018, 2019, 2020, 2021, 2022],
            "model_selection_year": 2023,
            "final_holdout_year": 2024,
            "outer_folds": [
                {
                    "fold_id": f.fold_id,
                    "train_years": list(f.outer_train_years),
                    "validation_year": f.outer_val_year,
                }
                for f in FROZEN_PROBABILISTIC_FOLDS
            ],
            "inner_folds_for_early_stopping": [
                {
                    "fold_id": f.fold_id,
                    "inner_train_years": list(f.inner_train_years),
                    "inner_val_year": f.inner_val_year,
                }
                for f in FROZEN_PROBABILISTIC_FOLDS
            ],
        },
        "early_stopping_procedure": {
            "step_1": "Fit inner preprocessor (scaler/vocabs) strictly on inner_train.",
            "step_2": "Train candidate neural net on inner_train; select best_epoch from inner_val loss.",
            "step_3": "Discard inner model weights completely (do NOT reuse).",
            "step_4": "Fit fresh outer preprocessor on full outer_train.",
            "step_5": "Train fresh model on full outer_train for exactly best_epoch epochs (no validation callback).",
            "step_6": "Transform outer_val; evaluate out-of-fold predictions with zero feedback into training.",
        },
        "non_negotiable_safety_rules": [
            "2024 access is sealed FINAL_HOLDOUT and prohibited before explicit final holdout stage.",
            "2023 is DEVELOPMENT_MODEL_SELECTION and prohibited during development.",
            "Weather features are strictly prohibited in Core Arrival.",
            "DEP_DELAY and actual-operation fields are strictly prohibited from Core Arrival predictors.",
            "No in-sample residual uncertainty estimation; OOF/cross-fitted residuals only.",
            "OP_CARRIER_FL_NUM is treated as service/schedule identity, not tail/aircraft identity.",
            "No random splitting; expanding window only.",
        ],
    }

    # 2. representation_manifest_v1.json
    representation_manifest = {
        "manifest_version": REPRESENTATION_VERSION,
        "created_at_utc": created_at_utc,
        "feature_manifest_version": "feature_manifest_arrival_v1",
        "feature_manifest_sha256": feature_manifest_sha256,
        "approved_predictors_count": len(PROBABILISTIC_PREDICTOR_COLUMNS),
        "approved_predictors": list(PROBABILISTIC_PREDICTOR_COLUMNS),
        "representation_structure": {
            "cyclic_features": {
                "time_of_day": {
                    "source_columns": ["scheduled_departure_hour", "scheduled_departure_minute"],
                    "formula": "t = 60 * scheduled_departure_hour + scheduled_departure_minute",
                    "period": 1440.0,
                    "encoded_columns": ["sin_time_of_day", "cos_time_of_day"],
                    "sin_formula": "sin(2 * pi * t / 1440.0)",
                    "cos_formula": "cos(2 * pi * t / 1440.0)",
                },
                "calendar_month": {
                    "source_columns": ["calendar_month"],
                    "period": 12.0,
                    "encoded_columns": ["sin_calendar_month", "cos_calendar_month"],
                    "sin_formula": "sin(2 * pi * (calendar_month - 1) / 12.0)",
                    "cos_formula": "cos(2 * pi * (calendar_month - 1) / 12.0)",
                },
                "calendar_day_of_week": {
                    "source_columns": ["calendar_day_of_week"],
                    "period": 7.0,
                    "encoded_columns": ["sin_calendar_day_of_week", "cos_calendar_day_of_week"],
                    "sin_formula": "sin(2 * pi * (calendar_day_of_week - 1) / 7.0)",
                    "cos_formula": "cos(2 * pi * (calendar_day_of_week - 1) / 7.0)",
                },
            },
            "scaled_numeric_features": {
                "source_columns": list(NUMERIC_SCALED_COLUMNS),
                "imputation": "SimpleImputer(strategy='median', fit on fold-train only)",
                "scaling": "StandardScaler(fit on fold-train only)",
                "encoded_columns": [f"{c}_scaled" for c in NUMERIC_SCALED_COLUMNS],
            },
            "categorical_embedding_features": {
                "source_columns": list(CATEGORICAL_EMBEDDING_COLUMNS),
                "vocabulary_policy": "fold-train unique categories sorted deterministically",
                "indexing": "0 to K - 1",
                "dedicated_unknown_index": "K (non-negative integer, vocabulary_size = K + 1)",
                "sentinel_policy": "NO negative indices (-1, -2) and NO tree-frequency zero sentinels",
                "semantic_meaning": {
                    "OP_CARRIER": "operating carrier code",
                    "ORIGIN": "scheduled departure airport",
                    "OP_CARRIER_FL_NUM": "service/schedule identity (NOT physical aircraft or tail entity)",
                },
            },
        },
        "total_continuous_features": 10,
        "total_categorical_embedding_features": 3,
        "fit_scope": "EACH_FOLD_TRAINING_ROWS_ONLY",
    }

    # 3. seed_manifest_v1.json
    seed_manifest = {
        "manifest_version": SEED_MANIFEST_VERSION,
        "created_at_utc": created_at_utc,
        "base_config_sha256": base_config_sha256,
        "project_seed_source": "configs/base.yaml:reproducibility.project_seed",
        "project_seed": SCREENING_SEED,
        "screening_seed": SCREENING_SEED,
        "finalist_seeds": list(FINALIST_SEEDS),
        "policy": SEED_POLICY,
        "predetermined_deployment_seed": PREDETERMINED_DEPLOYMENT_SEED,
        "finalist_evaluation_scope": (
            "Assess algorithmic stability (mean +- SD across 3 seeds and successful-run rate)"
        ),
        "registered_seed_ensemble_candidate": {
            "candidate_id": SEED_ENSEMBLE_CANDIDATE_ID,
            "description": "Pre-registered mixture average of predictive distributions from seeds [202601, 202602, 202603]",
            "status": "PRE_REGISTERED_CANDIDATE",
        },
    }

    # 4. distribution_candidate_manifest_v1.json
    distribution_manifest = {
        "manifest_version": DISTRIBUTION_CANDIDATE_VERSION,
        "created_at_utc": created_at_utc,
        "ladder_candidates": {
            "D1_k1_fixed_sigma": {
                "components": 1,
                "mean": "mu(x)",
                "sigma": "fixed global sigma",
                "description": "Homogeneous Gaussian baseline",
            },
            "D2_k1_heteroscedastic": {
                "components": 1,
                "mean": "mu(x)",
                "sigma": "softplus(raw_sigma(x)) + sigma_floor",
                "description": "Heteroscedastic Gaussian",
            },
            "D3_k3_mixture": {
                "components": 3,
                "weights": "softmax(raw_pi(x))",
                "means": "mu_k(x)",
                "sigmas": "softplus(raw_sigma_k(x)) + sigma_floor",
                "description": "3-component Gaussian mixture",
            },
            "D4_k5_mixture_conditional": {
                "components": 5,
                "weights": "softmax(raw_pi(x))",
                "means": "mu_k(x)",
                "sigmas": "softplus(raw_sigma_k(x)) + sigma_floor",
                "description": "5-component Gaussian mixture (CONDITIONALLY OPENED ONLY)",
            },
        },
        "k5_opening_criteria": {
            "condition_1_effective_components": {
                "metric": "N_eff = 1 / sum(pi_k^2)",
                "threshold": K5_MIN_EFFECTIVE_COMPONENTS,
                "requirement": "Must exceed 2.50 on validation set across all 4 development folds",
            },
            "condition_2_min_component_weight": {
                "metric": "min_k pi_bar_k",
                "threshold": K5_MIN_COMPONENT_WEIGHT,
                "requirement": "Every component must have mean validation weight >= 0.05 (no degenerate components)",
            },
            "condition_3_crps_improvement": {
                "metric": "Delta CRPS = CRPS(D2) - CRPS(D3)",
                "threshold": K5_MIN_CRPS_IMPROVEMENT_DELTA,
                "requirement": "95% day-block bootstrap CI lower bound > 0.05 min",
            },
        },
        "sigma_parameterization": {
            "formula": "sigma(x) = softplus(raw_sigma(x)) + sigma_floor",
            "default_sigma_floor": DEFAULT_SIGMA_FLOOR,
            "sensitivity_grid": list(SIGMA_FLOOR_SENSITIVITY_GRID),
            "gradient_clip_norm": GRADIENT_CLIP_NORM,
        },
        "pruning_rules_stage_6_5": {
            "delta_screen": DELTA_SCREEN,
            "rule": "CRPS_candidate <= CRPS_best + 0.20 min AND calibration_guard_passed AND tail_guard_passed",
            "calibration_guard": f"80% coverage in [{CALIBRATION_80_BOUNDS[0]}, {CALIBRATION_80_BOUNDS[1]}] and 90% coverage in [{CALIBRATION_90_BOUNDS[0]}, {CALIBRATION_90_BOUNDS[1]}]",
            "tail_guard": f"Brier score on Y >= 60 min no worse than best candidate by > {TAIL_BRIER_60_MAX_GAP}",
        },
        "forecast_effect_size_delta": {
            "metric": "CRPS",
            "delta": FORECAST_EFFECT_SIZE_DELTA,
            "interpretation": "Practical superiority requires lower bound of paired day-block bootstrap 95% CI > 0.10 min (6 seconds)",
        },
        "quantile_crossing_correction": {
            "method": QUANTILE_CROSSING_CORRECTION,
            "reference": "Chernozhukov et al. (2010)",
        },
        "heavy_tail_candidate": {
            "candidate_id": "B5_ngboost_student_t",
            "estimator": "NGBoost with Student-T distribution",
            "degrees_of_freedom": "nu in [3, 10] or learned with lower bound nu >= 2.1",
        },
    }

    # 5. dependence_candidate_manifest_v1.json
    dependence_manifest = {
        "manifest_version": DEPENDENCE_CANDIDATE_VERSION,
        "created_at_utc": created_at_utc,
        "candidate_families": {
            "DEP_D0_independent": {
                "family": "independent",
                "description": "Independent sampling from marginal predictive distributions (mandatory baseline)",
            },
            "DEP_D1_scenario_block": {
                "family": "scenario_block",
                "description": "Pre-cutoff schedule-conditioned block/scenario sampling",
            },
            "DEP_D2_gaussian_copula": {
                "family": "gaussian_copula",
                "description": "Gaussian copula with pre-cutoff correlation kernel or latent common factors",
            },
            "DEP_D3_tail_copula": {
                "family": "tail_copula",
                "description": "Tail-dependent copula (conditionally opened on development co-exceedance failure of D2)",
            },
        },
        "dependence_construction_requirements": {
            "variable_daily_n": "Must support arbitrary daily flight count n_d without fixed n x n matrix assumption",
            "pre_cutoff_conditioning_only": "Conditioning strictly restricted to pre-cutoff schedule covariates (time, carrier mix, density)",
            "no_realized_conditioning": "Conditioning on realized delays, cancellations, or actual weather is strictly prohibited",
            "psd_safety_enforcement": "Kernel/factor structure or nearest-PSD projection with minimum eigenvalue >= 1e-6",
            "no_double_counting": "Dependence layer must not inject variance already captured in marginal distributions",
        },
        "discrete_pit_policy": {
            "randomized_pit_formula": "U_i = F(Y_i - 1) + V_i * [F(Y_i) - F(Y_i - 1)], V_i ~ Uniform(0, 1)",
            "randomization_seed_control": "Fixed pseudo-random seed generator",
            "sensitivity_evaluation": "Assess copula parameter stability across 10 randomized PIT draws",
        },
    }

    manifests = {
        manifests_dir / "probabilistic_protocol_v1.json": probabilistic_protocol,
        manifests_dir / "representation_manifest_v1.json": representation_manifest,
        manifests_dir / "seed_manifest_v1.json": seed_manifest,
        manifests_dir / "distribution_candidate_manifest_v1.json": distribution_manifest,
        manifests_dir / "dependence_candidate_manifest_v1.json": dependence_manifest,
    }

    for path, content in manifests.items():
        path.write_text(json.dumps(content, indent=2, sort_keys=False) + "\n", encoding="utf-8")
        print(f"Generated: {path.name}")


if __name__ == "__main__":
    generate_manifests()
