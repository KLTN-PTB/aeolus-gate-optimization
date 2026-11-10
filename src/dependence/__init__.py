"""Dependence Modeling and Joint Sampling Package.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Sections 13, 14, 15, 16, 17
Provides:
- BaseJointSampler: Unified interface for joint sampling with dynamic daily flight count.
- IndependentJointSampler (D0): Mandatory independent control baseline.
- ScenarioBlockJointSampler (D1): Hierarchical schedule-block factor model conditioned on pre-cutoff covariates.
- GaussianCopulaJointSampler (D2): Spatial-temporal covariance kernel with PSD guarantee.
- validate_and_project_psd: PSD validation, spectral projection, and distortion reporting.
- compute_controlled_randomized_pit: Seed-controlled discrete randomized PIT.
"""

from __future__ import annotations

from src.dependence.base import (
    BaseJointSampler,
    FORBIDDEN_POST_CUTOFF_COLUMNS,
    validate_flight_batch_inputs,
)
from src.dependence.d0_independent import IndependentJointSampler
from src.dependence.d1_scenario import ScenarioBlockJointSampler
from src.dependence.d2_gaussian_copula import GaussianCopulaJointSampler
from src.dependence.pit import (
    PITSensitivityReport,
    compute_controlled_randomized_pit,
    evaluate_pit_seed_sensitivity,
)
from src.dependence.psd import (
    MIN_PSD_EIGENVALUE,
    PSDDiagnostic,
    validate_and_project_psd,
)

__all__ = [
    "BaseJointSampler",
    "FORBIDDEN_POST_CUTOFF_COLUMNS",
    "validate_flight_batch_inputs",
    "IndependentJointSampler",
    "ScenarioBlockJointSampler",
    "GaussianCopulaJointSampler",
    "PSDDiagnostic",
    "MIN_PSD_EIGENVALUE",
    "validate_and_project_psd",
    "compute_controlled_randomized_pit",
    "evaluate_pit_seed_sensitivity",
    "PITSensitivityReport",
]
