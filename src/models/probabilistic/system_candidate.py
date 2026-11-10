"""Complete System Candidate Architecture for Stage 7.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 12 (Stage 7)
Each complete system candidate bundles:
- feature manifest
- representation manifest
- marginal model family
- model architecture
- training policy
- frozen weights/config
- calibration method/object
- dependence mechanism
- dependence parameters
- sampling procedure
- Monte Carlo interface
- simulation interface
- optimization interface
- seed policy
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np
import pandas as pd

from src.models.probabilistic.contracts import (
    DEFAULT_SIGMA_FLOOR,
    PROBABILISTIC_PREDICTOR_COLUMNS,
    ProbabilisticContractViolation,
)
from src.models.probabilistic.dependence import (
    GaussianCopulaDependenceModel,
    IndependentDependenceModel,
    ScenarioBlockDependenceModel,
    StudentTMarginalDistribution,
    TailDependentCopulaModel,
)
from src.models.probabilistic.dependence_interface import (
    DayFlightBatch,
    JointDependenceModel,
    MarginalDistributionProtocol,
)


@dataclass
class CompleteSystemCandidate:
    """A completely specified, frozen probabilistic forecasting system."""

    candidate_id: str
    marginal_candidate_id: str
    dependence_candidate_id: str
    feature_manifest: dict[str, Any]
    representation_manifest: dict[str, Any]
    marginal_model_family: str
    architecture: dict[str, Any]
    training_policy: dict[str, Any]
    frozen_weights_config: dict[str, Any]
    calibration_method: dict[str, Any]
    dependence_mechanism: str
    dependence_parameters: dict[str, Any]
    sampling_procedure: list[str]
    seed_policy: dict[str, Any]

    # Concrete model instances (runtime components)
    dependence_model: JointDependenceModel
    marginal_factory: Callable[[pd.DataFrame], list[MarginalDistributionProtocol]]

    # =========================================================================
    # Monte Carlo Interface
    # =========================================================================
    def sample_scenarios(
        self,
        batch: DayFlightBatch,
        n_scenarios: int = 1000,
        seed: int | None = None,
    ) -> np.ndarray:
        """Sample joint arrival delays across all flights for one operational day.

        Args:
            batch: DayFlightBatch containing strictly pre-cutoff features.
            n_scenarios: Number of Monte Carlo joint realizations (default: 1000).
            seed: Optional integer seed for reproducibility; defaults to project seed.

        Returns:
            np.ndarray of shape (n_scenarios, n_flights) containing arrival delay samples (minutes).
        """
        if n_scenarios <= 0:
            raise ValueError("n_scenarios must be strictly positive")

        rng_seed = seed if seed is not None else self.seed_policy.get("project_seed", 202601)
        rng = np.random.default_rng(rng_seed)

        # 1. Generate marginal predictive distribution objects for each flight
        marginals = self.marginal_factory(batch.flight_features)
        if len(marginals) != batch.n_flights:
            raise ProbabilisticContractViolation(
                f"Marginal count ({len(marginals)}) does not match batch flight count ({batch.n_flights})"
            )

        # 2. Jointly sample from dependence model
        y_scenarios = self.dependence_model.sample_joint(
            marginals=marginals,
            flight_features=batch.flight_features,
            n_samples=n_scenarios,
            rng=rng,
        )
        return y_scenarios

    # =========================================================================
    # Simulation Interface
    # =========================================================================
    def simulate_daily_operations(
        self,
        batch: DayFlightBatch,
        n_scenarios: int = 1000,
        seed: int | None = None,
    ) -> dict[str, Any]:
        """Downstream operational simulation interface for gate & pushback planning.

        Computes scenario-level summary statistics:
        - daily total delay distribution;
        - severe delay counts (N60, N120);
        - maximum concurrent delay;
        - tail risk probabilities.
        """
        y_scenarios = self.sample_scenarios(batch, n_scenarios=n_scenarios, seed=seed)

        # Summary statistics across scenarios
        total_daily_delays = np.sum(y_scenarios, axis=1)  # shape (n_scenarios,)
        n60_per_scenario = np.sum(y_scenarios >= 60.0, axis=1)  # shape (n_scenarios,)
        n120_per_scenario = np.sum(y_scenarios >= 120.0, axis=1)  # shape (n_scenarios,)
        max_delays = np.max(y_scenarios, axis=1)  # shape (n_scenarios,)

        return {
            "flight_date": batch.flight_date,
            "n_flights": batch.n_flights,
            "n_scenarios": n_scenarios,
            "mean_daily_total_delay": float(np.mean(total_daily_delays)),
            "std_daily_total_delay": float(np.std(total_daily_delays)),
            "q10_daily_total_delay": float(np.percentile(total_daily_delays, 10)),
            "q50_daily_total_delay": float(np.percentile(total_daily_delays, 50)),
            "q90_daily_total_delay": float(np.percentile(total_daily_delays, 90)),
            "p_any_severe_ge60": float(np.mean(n60_per_scenario > 0)),
            "mean_severe_flights_ge60": float(np.mean(n60_per_scenario)),
            "p_any_severe_ge120": float(np.mean(n120_per_scenario > 0)),
            "mean_max_delay": float(np.mean(max_delays)),
            "scenario_total_delays": total_daily_delays.tolist()[:100],  # sample preview
        }

    # =========================================================================
    # Optimization Interface
    # =========================================================================
    def get_scenario_matrix(
        self,
        batch: DayFlightBatch,
        n_scenarios: int = 1000,
        seed: int | None = None,
    ) -> np.ndarray:
        """Optimization interface feeding directly into gate assignment & pushback models.

        Returns:
            np.ndarray of shape (n_scenarios, n_flights) with integer arrival delay realizations.
        """
        return self.sample_scenarios(batch, n_scenarios=n_scenarios, seed=seed)

    # =========================================================================
    # Serialization
    # =========================================================================
    def to_manifest_dict(self) -> dict[str, Any]:
        """Return serializable metadata dictionary for candidate freeze manifest."""
        return {
            "candidate_id": self.candidate_id,
            "marginal_candidate_id": self.marginal_candidate_id,
            "dependence_candidate_id": self.dependence_candidate_id,
            "feature_manifest": self.feature_manifest,
            "representation_manifest": self.representation_manifest,
            "marginal_model_family": self.marginal_model_family,
            "architecture": self.architecture,
            "training_policy": self.training_policy,
            "frozen_weights_config": self.frozen_weights_config,
            "calibration_method": self.calibration_method,
            "dependence_mechanism": self.dependence_mechanism,
            "dependence_parameters": self.dependence_parameters,
            "sampling_procedure": self.sampling_procedure,
            "seed_policy": self.seed_policy,
            "interfaces": {
                "monte_carlo_interface": "sample_scenarios(batch: DayFlightBatch, n_scenarios, seed) -> np.ndarray",
                "simulation_interface": "simulate_daily_operations(batch: DayFlightBatch, n_scenarios, seed) -> dict",
                "optimization_interface": "get_scenario_matrix(batch: DayFlightBatch, n_scenarios, seed) -> np.ndarray",
            },
        }


# =============================================================================
# System Candidate Factory & Registration
# =============================================================================

def build_complete_system_candidate(
    *,
    marginal_candidate_id: str,
    dependence_family_id: str,
    marginal_factory: Callable[[pd.DataFrame], list[MarginalDistributionProtocol]],
    project_root: Path | None = None,
    dependence_kwargs: dict[str, Any] | None = None,
) -> CompleteSystemCandidate:
    """Factory to construct a complete, frozen system candidate combining marginal and dependence models."""
    root = project_root or Path(__file__).resolve().parents[3]
    dep_kwargs = dependence_kwargs or {}

    candidate_id = f"SYS_{marginal_candidate_id}__{dependence_family_id}"

    # 1. Feature & Representation Manifests
    feat_manifest_path = root / "artifacts" / "manifests" / "feature_manifest_arrival_v1.json"
    rep_manifest_path = root / "artifacts" / "manifests" / "representation_manifest_v1.json"
    seed_manifest_path = root / "artifacts" / "manifests" / "seed_manifest_v1.json"

    feature_manifest_meta = {
        "manifest_path": str(feat_manifest_path.as_posix()),
        "feature_set": "arrival_v1",
        "approved_predictors": sorted(PROBABILISTIC_PREDICTOR_COLUMNS),
    }

    representation_manifest_meta = {
        "manifest_path": str(rep_manifest_path.as_posix()),
        "carrier_encoding": "learnable_embedding",
        "origin_encoding": "learnable_embedding",
        "flight_freq_encoding": "frequency_map",
        "time_encoding": "cyclic_sin_cos",
    }

    seed_policy = {
        "manifest_path": str(seed_manifest_path.as_posix()),
        "project_seed": 202601,
        "screening_seed": 202601,
        "finalist_seeds": [202601, 202602, 202603],
        "generator_algorithm": "numpy.random.default_rng (PCG64)",
    }

    # 2. Marginal Architecture & Policy Specification
    if marginal_candidate_id == "seed_ensemble_3":
        marginal_family = "3-Seed Mixture Ensemble (Gaussian Mixture K=3)"
        arch = {
            "model_class": "SeedEnsembleMixture",
            "backbone": "Linear(128) -> GELU -> Linear(64) -> GELU -> Linear(32)",
            "ensemble_size": 3,
            "seeds": [202601, 202602, 202603],
            "total_effective_components": 9,
            "sigma_floor": 1.0,
            "calendar_year_included": False,
        }
        train_policy = {
            "optimizer": "AdamW",
            "lr": 1e-3,
            "weight_decay": 1e-4,
            "batch_size": 1024,
            "max_epochs": 20,
            "early_stopping_patience": 5,
            "early_stopping_metric": "discretized_mixture_nll",
        }
        weights_config = {
            "checkpoint_directory": "artifacts/checkpoints/stage5_finalist_seeds/",
            "ensemble_weights": [1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0],
            "status": "FROZEN_DEVELOPMENT_CHECKPOINTS",
        }
    elif "mixture" in marginal_candidate_id:
        with_year = ("with_year" in marginal_candidate_id)
        marginal_family = f"Stage 3 Gaussian Mixture (K=3, {'with_year' if with_year else 'no_year'})"
        arch = {
            "model_class": "Stage3DistributionModel",
            "backbone": "Linear(128) -> GELU -> Linear(64) -> GELU -> Linear(32)",
            "components_k": 3,
            "heads": ["pi_head (Linear 3 -> Softmax)", "mu_head (Linear 3)", "sigma_head (Linear 3 -> Softplus + 1.0)"],
            "sigma_floor": 1.0,
            "calendar_year_included": with_year,
        }
        train_policy = {
            "optimizer": "AdamW",
            "lr": 1e-3,
            "weight_decay": 1e-4,
            "batch_size": 1024,
            "max_epochs": 20,
            "early_stopping_patience": 5,
            "early_stopping_metric": "discretized_mixture_nll",
        }
        weights_config = {
            "checkpoint_directory": f"artifacts/checkpoints/{marginal_candidate_id}/",
            "seed": 202601,
            "status": "FROZEN_DEVELOPMENT_CHECKPOINTS",
        }
    elif marginal_candidate_id == "B5_ngboost_student_t":
        marginal_family = "NGBoost with Heavy-Tail Student-T Distribution"
        arch = {
            "model_class": "NGBoostStudentT",
            "base_learner": "DecisionTreeRegressor(max_depth=3)",
            "distribution": "scipy.stats.t",
            "parameters": ["loc (mu)", "scale (sigma)", "df (nu)"],
            "sigma_floor": 1.0,
        }
        train_policy = {
            "n_estimators": 50,
            "learning_rate": 0.005,
            "min_name_samples": 20,
        }
        weights_config = {
            "checkpoint_directory": "artifacts/probabilistic/ngboost_student_t/",
            "seed": 202601,
            "status": "FROZEN_DEVELOPMENT_CHECKPOINTS",
        }
    else:
        raise ValueError(f"Unknown marginal candidate: {marginal_candidate_id}")

    # 3. Calibration Method (Discrete randomized PIT with seed locking)
    calibration_method = {
        "method": "Discrete Randomized Probability Integral Transform",
        "formula": "U_i = F(Y_i - 1) + V_i * [F(Y_i) - F(Y_i - 1)], V_i ~ Uniform(0, 1)",
        "randomization_policy": "Deterministic pseudorandom generator locked to predetermined sequence",
        "sensitivity_tolerance": "Mean U-std across 10 randomized draws < 0.25",
    }

    # 4. Dependence Model Initialization
    if dependence_family_id == "DEP_D0_independent":
        dep_model: JointDependenceModel = IndependentDependenceModel()
        dep_mech = "Independent sampling from each flight marginal predictive distribution (mandatory baseline)."
        dep_params = {"dependence_type": "independent"}
    elif dependence_family_id == "DEP_D1_scenario_block":
        day_w = dep_kwargs.get("day_factor_weight", 0.20)
        blk_w = dep_kwargs.get("block_factor_weight", 0.25)
        dep_model = ScenarioBlockDependenceModel(day_factor_weight=day_w, block_factor_weight=blk_w)
        dep_mech = (
            "Hierarchical latent schedule-block factor model conditioned on pre-cutoff schedule variables "
            "(departure time block, carrier tier). Arbitrary daily n_flights supported via exchangeable block mapping."
        )
        dep_params = {
            "day_factor_weight": day_w,
            "block_factor_weight": blk_w,
            "idiosyncratic_weight": dep_model.idiosyncratic_weight,
            "schedule_time_blocks": ["MORN (00-11h)", "AFTN (12-17h)", "EVEN (18-23h)"],
            "carrier_tiers": ["MAIN", "REG"],
        }
    elif dependence_family_id == "DEP_D2_gaussian_copula":
        ell = dep_kwargs.get("temporal_length_scale_minutes", 120.0)
        rho_c = dep_kwargs.get("carrier_correlation", 0.15)
        dep_model = GaussianCopulaDependenceModel(temporal_length_scale_minutes=ell, carrier_correlation=rho_c)
        dep_mech = (
            "Gaussian copula with pre-cutoff spatio-temporal kernel based on scheduled departure time proximity "
            "and carrier match. Positive semi-definiteness guaranteed for arbitrary n_flights via PSD projection."
        )
        dep_params = {
            "temporal_length_scale_minutes": ell,
            "carrier_correlation": rho_c,
            "psd_minimum_eigenvalue": 1e-6,
            "psd_projection": "nearest-PSD eigenvalue clipping with unit diagonal re-normalization",
        }
    elif dependence_family_id == "DEP_D3_tail_copula":
        nu_val = dep_kwargs.get("degrees_of_freedom", 6.0)
        ell = dep_kwargs.get("temporal_length_scale_minutes", 120.0)
        rho_c = dep_kwargs.get("carrier_correlation", 0.15)
        dep_model = TailDependentCopulaModel(
            degrees_of_freedom=nu_val,
            temporal_length_scale_minutes=ell,
            carrier_correlation=rho_c,
        )
        dep_mech = (
            "Multivariate Student-T copula with common scaling shock generating strictly positive tail dependence. "
            "Conditionally opened on development data evidence gate."
        )
        dep_params = {
            "degrees_of_freedom": nu_val,
            "temporal_length_scale_minutes": ell,
            "carrier_correlation": rho_c,
            "tail_dependence_coefficient_lower": float(2 * student_t.cdf(-np.sqrt((nu_val + 1) * (1 - rho_c) / (1 + rho_c)), df=nu_val + 1)),
        }
    else:
        raise ValueError(f"Unknown dependence family: {dependence_family_id}")

    # 5. Step-by-step Sampling Procedure
    sampling_procedure = [
        "Step 1: Ingest DayFlightBatch containing strictly pre-cutoff schedule covariates known by T-2h.",
        "Step 2: Generate marginal predictive distribution objects (Discrete Gaussian Mixture or Student-T) for each flight.",
        "Step 3: Sample joint copula coordinates U in [0, 1]^(S x N) using the frozen dependence mechanism.",
        "Step 4: Invert copula coordinates through flight-specific marginal quantile functions: Y_{s, i} = Q_i(U_{s, i}).",
        "Step 5: Output integer delay scenario matrix Y in Z^(S x N) for downstream Monte Carlo simulation and optimization.",
    ]

    return CompleteSystemCandidate(
        candidate_id=candidate_id,
        marginal_candidate_id=marginal_candidate_id,
        dependence_candidate_id=dependence_family_id,
        feature_manifest=feature_manifest_meta,
        representation_manifest=representation_manifest_meta,
        marginal_model_family=marginal_family,
        architecture=arch,
        training_policy=train_policy,
        frozen_weights_config=weights_config,
        calibration_method=calibration_method,
        dependence_mechanism=dep_mech,
        dependence_parameters=dep_params,
        sampling_procedure=sampling_procedure,
        seed_policy=seed_policy,
        dependence_model=dep_model,
        marginal_factory=marginal_factory,
    )
