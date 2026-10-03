"""Locked statistical and methodology contracts for Probabilistic Core Arrival.

Protocol reference: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md
Scope: Distributional forecasting at T-2h, calibration, proper scoring,
       representation ablation, joint dependence, and simulation integration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from src.features.tabular_features import APPROVED_PREDICTOR_COLUMNS


PROBABILISTIC_PROTOCOL_VERSION: Final = "probabilistic_core_arrival_v1"
REPRESENTATION_VERSION: Final = "arrival_nn_representation_v1"
SEED_MANIFEST_VERSION: Final = "seed_manifest_v1"
DISTRIBUTION_CANDIDATE_VERSION: Final = "distribution_candidate_manifest_v1"
DEPENDENCE_CANDIDATE_VERSION: Final = "dependence_candidate_manifest_v1"

# Target Semantics Audit
TARGET_COLUMN: Final = "ARR_DELAY"
TARGET_STORAGE_DTYPE: Final = "float64"
TARGET_VALUE_GRANULARITY_MINUTES: Final = 1.0
TARGET_SEMANTICS_DECISION: Final = "integer_quantized_1min"
TARGET_QUANTIZATION_INTERVAL: Final = "[y - 0.5, y + 0.5]"
PRIMARY_LIKELIHOOD_SPECIFICATION: Final = "discretized_gaussian_mixture"
SECONDARY_LIKELIHOOD_SPECIFICATION: Final = "continuous_gaussian_mixture"

# Predictor contract: 11 approved features
PROBABILISTIC_PREDICTOR_COLUMNS: Final = APPROVED_PREDICTOR_COLUMNS
CYCLIC_SOURCE_COLUMNS: Final = (
    "scheduled_departure_hour",
    "scheduled_departure_minute",
    "calendar_month",
    "calendar_day_of_week",
)
NUMERIC_SCALED_COLUMNS: Final = (
    "CRS_ELAPSED_TIME",
    "calendar_year",
    "calendar_day_of_month",
    "is_weekend",
)
CATEGORICAL_EMBEDDING_COLUMNS: Final = (
    "OP_CARRIER",
    "ORIGIN",
    "OP_CARRIER_FL_NUM",
)

# Baseline candidates (Stage 1)
B1_EMPIRICAL: Final = "B1_empirical"
B2_XGB_GAUSSIAN_OOF: Final = "B2_xgb_gaussian_oof"
B3_NGBOOST_NORMAL: Final = "B3_ngboost_normal"
B4_LIGHTGBM_QUANTILE: Final = "B4_lightgbm_quantile"
B5_NGBOOST_STUDENT_T: Final = "B5_ngboost_student_t"
STAGE_1_BASELINES: Final = (
    B1_EMPIRICAL,
    B2_XGB_GAUSSIAN_OOF,
    B3_NGBOOST_NORMAL,
    B4_LIGHTGBM_QUANTILE,
    B5_NGBOOST_STUDENT_T,
)

# Representation candidates (Stage 2)
R0_NN_POINT_ONEHOT: Final = "R0_nn_point_onehot"
R1_NN_POINT_FREQ: Final = "R1_nn_point_freq"
R2_NN_POINT_EMBEDDING: Final = "R2_nn_point_embedding"
STAGE_2_REPRESENTATIONS: Final = (
    R0_NN_POINT_ONEHOT,
    R1_NN_POINT_FREQ,
    R2_NN_POINT_EMBEDDING,
)

# Distribution ladder candidates (Stage 3)
D1_K1_FIXED_SIGMA: Final = "D1_k1_fixed_sigma"
D2_K1_HETEROSCEDASTIC: Final = "D2_k1_heteroscedastic"
D3_K3_MIXTURE: Final = "D3_k3_mixture"
D4_K5_MIXTURE_CONDITIONAL: Final = "D4_k5_mixture_conditional"
STAGE_3_DISTRIBUTIONS: Final = (
    D1_K1_FIXED_SIGMA,
    D2_K1_HETEROSCEDASTIC,
    D3_K3_MIXTURE,
    D4_K5_MIXTURE_CONDITIONAL,
)

# Joint dependence candidate families (Stage 7.5 / Section 13)
DEP_D0_INDEPENDENT: Final = "DEP_D0_independent"
DEP_D1_SCENARIO_BLOCK: Final = "DEP_D1_scenario_block"
DEP_D2_GAUSSIAN_COPULA: Final = "DEP_D2_gaussian_copula"
DEP_D3_TAIL_COPULA: Final = "DEP_D3_tail_copula"
JOINT_DEPENDENCE_FAMILIES: Final = (
    DEP_D0_INDEPENDENT,
    DEP_D1_SCENARIO_BLOCK,
    DEP_D2_GAUSSIAN_COPULA,
    DEP_D3_TAIL_COPULA,
)

# Seed Policy
SCREENING_SEED: Final = 202601
FINALIST_SEEDS: Final = (202601, 202602, 202603)
SEED_POLICY: Final = "evaluation_only_with_predetermined_deployment_seed"
PREDETERMINED_DEPLOYMENT_SEED: Final = 202601
SEED_ENSEMBLE_CANDIDATE_ID: Final = "seed_ensemble_3"

# Candidate Expansion & Pruning Rules
FORECAST_EFFECT_SIZE_DELTA: Final = 0.10  # minutes (6 seconds) for CRPS
DELTA_SCREEN: Final = 0.20  # minutes for Stage 6.5 pruning
CALIBRATION_80_BOUNDS: Final = (0.75, 0.85)
CALIBRATION_90_BOUNDS: Final = (0.85, 0.95)
TAIL_BRIER_60_MAX_GAP: Final = 0.0050
QUANTILE_CROSSING_CORRECTION: Final = "monotonic_rearrangement"
DEFAULT_SIGMA_FLOOR: Final = 1.0  # minutes
SIGMA_FLOOR_SENSITIVITY_GRID: Final = (0.1, 0.5, 1.0, 2.0)
GRADIENT_CLIP_NORM: Final = 1.0

# K=5 Opening Criteria thresholds
K5_MIN_EFFECTIVE_COMPONENTS: Final = 2.50
K5_MIN_COMPONENT_WEIGHT: Final = 0.05
K5_MIN_CRPS_IMPROVEMENT_DELTA: Final = 0.05


class ProbabilisticContractViolation(ValueError):
    """Raised when an operation violates the probabilistic research protocol."""


class ProbabilisticTemporalError(ValueError):
    """Raised when temporal split, holdout, or early-stopping boundaries are violated."""


@dataclass(frozen=True)
class CandidateExpansionRules:
    """Pre-registered criteria for candidate opening, pruning, and selection."""

    delta_forecast_effect_size: float = FORECAST_EFFECT_SIZE_DELTA
    delta_screen: float = DELTA_SCREEN
    k5_min_effective_components: float = K5_MIN_EFFECTIVE_COMPONENTS
    k5_min_component_weight: float = K5_MIN_COMPONENT_WEIGHT
    k5_min_crps_improvement: float = K5_MIN_CRPS_IMPROVEMENT_DELTA
    quantile_crossing_correction: str = QUANTILE_CROSSING_CORRECTION
    default_sigma_floor: float = DEFAULT_SIGMA_FLOOR
    sigma_floor_sensitivity_grid: tuple[float, ...] = SIGMA_FLOOR_SENSITIVITY_GRID
    heavy_tail_candidate: str = B5_NGBOOST_STUDENT_T

    def evaluate_k5_opening(
        self,
        effective_components: float,
        min_component_weight: float,
        crps_improvement_ci_lower: float,
    ) -> bool:
        """Return True if and only if all three pre-registered K=5 criteria are met."""
        return (
            effective_components >= self.k5_min_effective_components
            and min_component_weight >= self.k5_min_component_weight
            and crps_improvement_ci_lower > self.k5_min_crps_improvement
        )

    def evaluate_pruning(
        self,
        candidate_crps: float,
        best_crps: float,
        coverage_80: float,
        coverage_90: float,
        brier_60: float,
        best_brier_60: float,
    ) -> tuple[bool, str]:
        """Return (pass_pruning, reason) for Stage 6.5 pruning."""
        if candidate_crps > best_crps + self.delta_screen:
            return (
                False,
                f"CRPS ({candidate_crps:.4f}) exceeds best ({best_crps:.4f}) + delta_screen ({self.delta_screen:.4f})",
            )
        if not (CALIBRATION_80_BOUNDS[0] <= coverage_80 <= CALIBRATION_80_BOUNDS[1]):
            return (
                False,
                f"80% coverage ({coverage_80:.4f}) outside [{CALIBRATION_80_BOUNDS[0]}, {CALIBRATION_80_BOUNDS[1]}]",
            )
        if not (CALIBRATION_90_BOUNDS[0] <= coverage_90 <= CALIBRATION_90_BOUNDS[1]):
            return (
                False,
                f"90% coverage ({coverage_90:.4f}) outside [{CALIBRATION_90_BOUNDS[0]}, {CALIBRATION_90_BOUNDS[1]}]",
            )
        if brier_60 > best_brier_60 + TAIL_BRIER_60_MAX_GAP:
            return (
                False,
                f"Brier-60 ({brier_60:.4f}) exceeds best ({best_brier_60:.4f}) + gap ({TAIL_BRIER_60_MAX_GAP:.4f})",
            )
        return True, "PASS"
