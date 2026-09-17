"""Fail-closed contract for the frozen Week-5 HPO protocol.

This module validates configuration, temporal access, protocol identity and
resume eligibility.  It deliberately contains no production objective loop,
data loader, model training run or Optuna storage creation.
"""

from __future__ import annotations

import json
import math
import platform
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Final, Mapping, Sequence

import yaml
from optuna.pruners import NopPruner
from optuna.samplers import TPESampler

from src.data.access_guard import assert_data_access_allowed
from src.data.load_aeolus import load_base_config, resolve_project_root


PROTOCOL_VERSION: Final = "week5_hpo_protocol_v1"
EXPECTED_PROTOCOL_HASH: Final = (
    "b00ddf190776a12032b1e6b5b284beff8b48204017fe4c397140ac7a4da6844a"
)
DEFAULT_CONFIG_PATH: Final = Path("configs/week5_hpo.yaml")
DEFAULT_MANIFEST_PATH: Final = Path(
    "artifacts/manifests/week5_hpo_protocol_v1.json"
)
EXPECTED_STUDY_IDS: Final = frozenset(
    {
        "random_forest_classification",
        "random_forest_regression",
        "hist_gradient_boosting_classification",
        "hist_gradient_boosting_regression",
        "xgboost_classification",
        "xgboost_regression",
    }
)
EXPECTED_ALLOWED_YEARS: Final = tuple(range(2016, 2023))
EXPECTED_BLOCKED_YEARS: Final = (2023, 2024)
EXPECTED_DEPENDENCIES: Final = {
    "python": "3.11.15",
    "xgboost": "3.2.0",
    "optuna": "5.0.0",
    "numpy": "2.2.6",
    "pandas": "2.3.3",
    "pyarrow": "25.0.1",
    "scikit_learn": "1.9.0",
}
EXPECTED_SCOPE_GUARDS: Final = {
    "weather_allowed": False,
    "departure_target_allowed": False,
    "predicted_departure_delay_allowed": False,
    "actual_operational_outcomes_allowed": False,
    "chain_features_allowed": False,
    "arr_b_enabled": False,
    "auxiliary_weather_enabled": False,
    "shap_allowed": False,
    "ensemble_allowed": False,
    "champion_selection_allowed": False,
    "production_hpo_allowed_in_this_step": False,
}
EXPECTED_RESUME_POLICY: Final = {
    "resumable_statuses": ["INTERRUPTED", "BLOCKED_INCOMPLETE"],
    "completed_status": "COMPLETED",
    "protocol_hash_required": True,
    "mismatch_action": "FAIL_CLOSED",
}
EXPECTED_FORBIDDEN_TUNING_DIMENSIONS: Final = [
    "feature_set",
    "target_definition",
    "rolling_folds",
    "prediction_cutoff",
    "classification_threshold",
    "row_population",
    "class_weight",
]
EXPECTED_SOURCE_CONTRACTS: Final = [
    "configs/base.yaml",
    "artifacts/manifests/feature_manifest_arrival_v1.json",
    "artifacts/manifests/temporal_folds_manifest.json",
    "artifacts/manifests/split_manifest.json",
]
EXPECTED_FOLDS: Final = (
    {"id": "fold_1", "train_years": [2016, 2017, 2018], "validation_year": 2019},
    {
        "id": "fold_2",
        "train_years": [2016, 2017, 2018, 2019],
        "validation_year": 2020,
    },
    {
        "id": "fold_3",
        "train_years": [2016, 2017, 2018, 2019, 2020],
        "validation_year": 2021,
    },
    {
        "id": "fold_4",
        "train_years": [2016, 2017, 2018, 2019, 2020, 2021],
        "validation_year": 2022,
    },
)


class Week5ProtocolViolation(ValueError):
    """Raised before HPO when a frozen Week-5 invariant is violated."""


@dataclass(frozen=True)
class Week5HPOProtocol:
    """Validated config and manifest pair for later production HPO."""

    protocol_version: str
    protocol_hash: str
    _config: dict[str, Any]
    _manifest: dict[str, Any]

    @property
    def config(self) -> dict[str, Any]:
        """Return an isolated copy so the frozen protocol cannot be mutated."""

        return deepcopy(self._config)

    @property
    def manifest(self) -> dict[str, Any]:
        """Return an isolated copy of the validated evidence manifest."""

        return deepcopy(self._manifest)


def canonical_protocol_hash(payload: Mapping[str, Any]) -> str:
    """Hash parsed YAML semantics rather than platform-specific text layout."""

    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return sha256(canonical).hexdigest()


def load_week5_hpo_protocol(
    *,
    project_root: Path | None = None,
    config_path: Path | None = None,
    manifest_path: Path | None = None,
) -> Week5HPOProtocol:
    """Load and validate the pre-production protocol without opening row data."""

    root = resolve_project_root(project_root)
    resolved_config = config_path or root / DEFAULT_CONFIG_PATH
    resolved_manifest = manifest_path or root / DEFAULT_MANIFEST_PATH
    config = _read_yaml_mapping(resolved_config, label="Week-5 HPO config")
    manifest = _read_json_mapping(resolved_manifest, label="Week-5 HPO manifest")
    observed_hash = canonical_protocol_hash(config)
    if manifest.get("protocol_sha256") != observed_hash:
        raise Week5ProtocolViolation("Week-5 config/protocol hash mismatch")
    if observed_hash != EXPECTED_PROTOCOL_HASH:
        raise Week5ProtocolViolation("Week-5 frozen protocol hash mismatch")

    _validate_config(config, root=root)
    _validate_manifest(manifest, config=config, protocol_hash=observed_hash)
    _validate_runtime_dependencies(config["dependencies"], root=root)
    return Week5HPOProtocol(
        protocol_version=PROTOCOL_VERSION,
        protocol_hash=observed_hash,
        _config=deepcopy(config),
        _manifest=deepcopy(manifest),
    )


def assert_hpo_year_allowed(year: int) -> None:
    """Route all future Week-5 HPO partition access through the shared guard."""

    assert_data_access_allowed(year, "hpo")


def build_optuna_components(
    protocol: Week5HPOProtocol,
) -> tuple[TPESampler, NopPruner]:
    """Instantiate only the frozen sampler and no-op pruner."""

    randomness = protocol.config["randomness"]
    if randomness.get("sampler") != "TPESampler" or randomness.get("pruner") != "NopPruner":
        raise Week5ProtocolViolation("unsupported Week-5 sampler or pruner")
    return TPESampler(seed=int(randomness["sampler_seed"])), NopPruner()


def aggregate_classification_objective(fold_pr_auc: Sequence[float]) -> float:
    """Return the equal-weight mean PR-AUC across exactly four locked folds."""

    values = _four_finite_values(fold_pr_auc, label="classification PR-AUC")
    if any(value < 0.0 or value > 1.0 for value in values):
        raise Week5ProtocolViolation("classification PR-AUC must be within [0, 1]")
    return sum(values) / 4.0


def aggregate_regression_objective(fold_mae: Sequence[float]) -> float:
    """Return the equal-weight mean signed-target MAE across four folds."""

    values = _four_finite_values(fold_mae, label="regression MAE")
    if any(value < 0.0 for value in values):
        raise Week5ProtocolViolation("regression MAE must be nonnegative")
    return sum(values) / 4.0


def assert_study_resume_allowed(
    protocol: Week5HPOProtocol,
    *,
    study_name: str,
    stored_protocol_hash: str,
    study_status: str,
    completed_trials: int,
) -> None:
    """Fail closed on unknown, mismatched, non-interrupted or completed studies."""

    known_names = {
        entry["study_name"] for entry in protocol.config["studies"].values()
    }
    if study_name not in known_names:
        raise Week5ProtocolViolation(f"unknown Week-5 study {study_name!r}")
    if stored_protocol_hash != protocol.protocol_hash:
        raise Week5ProtocolViolation("Week-5 resume protocol hash mismatch")
    if study_status == protocol.config["resume_policy"]["completed_status"]:
        raise Week5ProtocolViolation("refusing to overwrite a completed study")
    if study_status not in protocol.config["resume_policy"]["resumable_statuses"]:
        raise Week5ProtocolViolation(
            f"study status {study_status!r} is not resumable under the frozen protocol"
        )
    required_trials = int(protocol.config["budget"]["completed_trials_required"])
    if type(completed_trials) is not int or completed_trials < 0:
        raise Week5ProtocolViolation("completed trial count must be a nonnegative integer")
    if completed_trials >= required_trials:
        raise Week5ProtocolViolation(
            f"study already has {required_trials} completed trials and may not resume"
        )


def _validate_config(config: dict[str, Any], *, root: Path) -> None:
    if config.get("protocol_version") != PROTOCOL_VERSION:
        raise Week5ProtocolViolation("unexpected Week-5 protocol version")
    if config.get("status") != "FROZEN_PRE_PRODUCTION":
        raise Week5ProtocolViolation("Week-5 protocol must be frozen before production HPO")

    base = load_base_config(project_root=root)
    seed = base.get("reproducibility", {}).get("project_seed")
    if seed != 202601:
        raise Week5ProtocolViolation("base config project seed changed")
    randomness = config.get("randomness")
    if (
        not isinstance(randomness, dict)
        or randomness.get("sampler") != "TPESampler"
        or randomness.get("pruner") != "NopPruner"
    ):
        raise Week5ProtocolViolation("Week-5 sampler/pruner contract changed")
    if randomness.get("sampler_seed") != seed or randomness.get("model_random_state") != seed:
        raise Week5ProtocolViolation("Week-5 randomness must use the project seed")
    if randomness.get("parallel_optuna_trials") is not False:
        raise Week5ProtocolViolation("parallel Optuna trials are prohibited")

    expected_task = {
        "task": "arrival_core",
        "flow": "inbound",
        "population": "DEST=ATL",
        "classification_target": "y_arr_cls = 1[ARR_DELAY >= 15]",
        "regression_target": "y_arr_reg = signed ARR_DELAY minutes",
        "prediction_cutoff": "CRS_DEP_TIME - 2 hours",
        "feature_manifest_version": "feature_manifest_arrival_v1",
        "preprocessing_version": "arrival_preprocessing_v1",
    }
    if config.get("task_contract") != expected_task:
        raise Week5ProtocolViolation("Core Arrival task contract changed")
    if config.get("scope_guards") != EXPECTED_SCOPE_GUARDS:
        raise Week5ProtocolViolation("Week-5 scope guards changed")

    if config.get("folds") != list(EXPECTED_FOLDS):
        raise Week5ProtocolViolation("Week-5 folds differ from the locked protocol")
    configured_folds = base.get("temporal", {}).get("rolling_folds", {}).get("folds")
    temporal_manifest = _read_json_mapping(
        root / "artifacts/manifests/temporal_folds_manifest.json",
        label="temporal folds manifest",
    )
    observed_folds = [
        {
            "id": fold.get("id"),
            "train_years": fold.get("train_years"),
            "validation_year": fold.get("validation_year"),
        }
        for fold in temporal_manifest.get("rolling_folds", [])
        if isinstance(fold, dict)
    ]
    if configured_folds != list(EXPECTED_FOLDS) or observed_folds != list(EXPECTED_FOLDS):
        raise Week5ProtocolViolation("Week-4 temporal manifests no longer match Week 5")

    data_contract = config.get("data_contract", {})
    if data_contract != {
        "allowed_hpo_years": list(EXPECTED_ALLOWED_YEARS),
        "blocked_hpo_years": list(EXPECTED_BLOCKED_YEARS),
        "access_guard_purpose": "hpo",
        "preprocessing_fit_scope": "EACH_FOLD_TRAIN_ROWS_ONLY",
        "exact_locked_folds_required": True,
        "random_split_allowed": False,
    }:
        raise Week5ProtocolViolation("Week-5 HPO data contract changed")
    for year in EXPECTED_ALLOWED_YEARS:
        assert_hpo_year_allowed(year)

    budget = config.get("budget", {})
    if budget != {
        "n_trials_per_study": 10,
        "execution_parallelism": 1,
        "timeout_seconds_per_study": 14400,
        "timeout_role": "SAFETY_CEILING_ONLY",
        "incomplete_timeout_status": "BLOCKED_INCOMPLETE",
        "completed_trials_required": 10,
        "automatic_trial_reduction_allowed": False,
    }:
        raise Week5ProtocolViolation("Week-5 fixed budget changed")

    _validate_objectives(config.get("objectives"))
    _validate_studies(config.get("studies"), seed=seed)
    if config.get("forbidden_tuning_dimensions") != EXPECTED_FORBIDDEN_TUNING_DIMENSIONS:
        raise Week5ProtocolViolation("forbidden tuning dimensions changed")
    storage = config.get("storage", {})
    if storage != {
        "directory": "artifacts/optuna_studies",
        "url_template": "sqlite:///artifacts/optuna_studies/{study_name}.sqlite3",
        "gitignored": True,
        "overwrite_completed_study": False,
        "resume_requires_matching_protocol_hash": True,
    }:
        raise Week5ProtocolViolation("Week-5 study storage contract changed")
    gitignore = (root / ".gitignore").read_text(encoding="utf-8")
    if "artifacts/optuna_studies/**" not in gitignore:
        raise Week5ProtocolViolation("Optuna study storage is not gitignored")
    if config.get("resume_policy") != EXPECTED_RESUME_POLICY:
        raise Week5ProtocolViolation("Week-5 resume policy changed")


def _validate_objectives(objectives: Any) -> None:
    if not isinstance(objectives, dict):
        raise Week5ProtocolViolation("Week-5 objectives are missing")
    classification = objectives.get("classification", {})
    regression = objectives.get("regression", {})
    if (
        classification.get("direction") != "maximize"
        or classification.get("metric") != "mean_pr_auc_across_locked_folds"
        or classification.get("fold_weighting") != "equal"
        or classification.get("prediction_method") != "predict_proba"
        or classification.get("fixed_threshold") != 0.5
        or classification.get("threshold_tuning_allowed") is not False
    ):
        raise Week5ProtocolViolation("classification objective contract changed")
    if (
        regression.get("direction") != "minimize"
        or regression.get("metric") != "mean_mae_across_locked_folds"
        or regression.get("fold_weighting") != "equal"
        or regression.get("signed_target") is not True
    ):
        raise Week5ProtocolViolation("regression objective contract changed")


def _validate_studies(studies: Any, *, seed: int) -> None:
    if not isinstance(studies, dict) or set(studies) != EXPECTED_STUDY_IDS:
        raise Week5ProtocolViolation("Week-5 must define exactly six studies")
    names: set[str] = set()
    for study_id, study in studies.items():
        if not isinstance(study, dict):
            raise Week5ProtocolViolation(f"study {study_id} is malformed")
        expected_name = f"{PROTOCOL_VERSION}__{study_id}"
        if study.get("study_name") != expected_name or expected_name in names:
            raise Week5ProtocolViolation("study names must be unique and deterministic")
        names.add(expected_name)
        is_classification = study_id.endswith("classification")
        expected_method = study_id.removesuffix("_classification").removesuffix(
            "_regression"
        )
        if study.get("method") != expected_method:
            raise Week5ProtocolViolation(f"study {study_id} method changed")
        if study.get("task_type") != ("classification" if is_classification else "regression"):
            raise Week5ProtocolViolation(f"study {study_id} task type changed")
        if study.get("direction") != ("maximize" if is_classification else "minimize"):
            raise Week5ProtocolViolation(f"study {study_id} direction changed")
        expected_metric = (
            "mean_pr_auc_across_locked_folds"
            if is_classification
            else "mean_mae_across_locked_folds"
        )
        if study.get("objective_metric") != expected_metric:
            raise Week5ProtocolViolation(f"study {study_id} objective changed")
        _validate_search_space(study_id, study.get("search_space"))
        fixed = study.get("fixed_parameters", {})
        if fixed.get("random_state") != seed:
            raise Week5ProtocolViolation(f"study {study_id} random state changed")
        if "class_weight" in study.get("search_space", {}):
            raise Week5ProtocolViolation("class weights may not be tuned")
        if study_id.startswith("hist_gradient_boosting") and fixed.get("early_stopping") is not False:
            raise Week5ProtocolViolation("HGB early stopping must remain disabled")
        if study_id.startswith("xgboost"):
            if (
                fixed.get("tree_method") != "hist"
                or fixed.get("device") != "cpu"
                or fixed.get("max_bin") != 256
                or fixed.get("n_jobs") != 1
            ):
                raise Week5ProtocolViolation("XGBoost must use single-job histogram trees")
    if studies["xgboost_classification"]["fixed_parameters"].get("objective") != "binary:logistic":
        raise Week5ProtocolViolation("XGBoost classifier objective changed")
    if studies["xgboost_regression"]["fixed_parameters"].get("objective") != "reg:squarederror":
        raise Week5ProtocolViolation("XGBoost regressor objective changed")


def _validate_search_space(study_id: str, search_space: Any) -> None:
    if not isinstance(search_space, dict) or not search_space:
        raise Week5ProtocolViolation(f"study {study_id} lacks a bounded search space")
    for parameter_name, parameter in search_space.items():
        if not isinstance(parameter, dict):
            raise Week5ProtocolViolation(f"study {study_id} parameter {parameter_name} is malformed")
        kind = parameter.get("type")
        if kind in {"int", "float"}:
            low, high = parameter.get("low"), parameter.get("high")
            if not isinstance(low, (int, float)) or not isinstance(high, (int, float)) or low >= high:
                raise Week5ProtocolViolation(f"study {study_id} parameter {parameter_name} is unbounded")
        elif kind == "categorical":
            if not isinstance(parameter.get("choices"), list) or not parameter["choices"]:
                raise Week5ProtocolViolation(f"study {study_id} parameter {parameter_name} lacks choices")
        else:
            raise Week5ProtocolViolation(f"study {study_id} parameter {parameter_name} has unknown type")


def _validate_manifest(
    manifest: dict[str, Any],
    *,
    config: dict[str, Any],
    protocol_hash: str,
) -> None:
    if manifest.get("protocol_version") != PROTOCOL_VERSION:
        raise Week5ProtocolViolation("manifest protocol version mismatch")
    if manifest.get("status") != "PROTOCOL_FROZEN":
        raise Week5ProtocolViolation("manifest is not frozen")
    if manifest.get("protocol_sha256") != protocol_hash:
        raise Week5ProtocolViolation("manifest protocol hash mismatch")
    if manifest.get("dependencies") != config.get("dependencies"):
        raise Week5ProtocolViolation("manifest dependency versions mismatch")
    if manifest.get("production_hpo_started") is not False or manifest.get("study_results") != []:
        raise Week5ProtocolViolation("protocol manifest contains production HPO results")
    if manifest.get("row_level_2023_accessed") is not False:
        raise Week5ProtocolViolation("protocol step accessed row-level 2023")
    if manifest.get("row_level_2024_accessed") is not False:
        raise Week5ProtocolViolation("protocol step accessed row-level 2024")
    expected_projection = {
        "manifest_version": "week5_hpo_protocol_manifest_v1",
        "protocol_hash_algorithm": "sha256_canonical_parsed_yaml_v1",
        "source_config": "configs/week5_hpo.yaml",
        "source_contracts": EXPECTED_SOURCE_CONTRACTS,
        "task": "arrival_core",
        "population": "inbound DEST=ATL",
        "classification_target": "y_arr_cls = 1[ARR_DELAY >= 15]",
        "regression_target": "y_arr_reg = signed ARR_DELAY minutes",
        "prediction_cutoff": "CRS_DEP_TIME - 2 hours",
        "n_studies": 6,
        "study_ids": list(config["studies"]),
        "trials_per_study": 10,
        "execution_parallelism": 1,
        "timeout_seconds_per_study": 14400,
        "sampler": "TPESampler(seed=202601)",
        "pruner": "NopPruner",
        "classification_objective": (
            "maximize equal-fold mean PR-AUC from predict_proba"
        ),
        "regression_objective": (
            "minimize equal-fold mean MAE on signed ARR_DELAY"
        ),
        "hpo_allowed_years": list(EXPECTED_ALLOWED_YEARS),
        "hpo_blocked_years": list(EXPECTED_BLOCKED_YEARS),
        "study_storage": "artifacts/optuna_studies/",
        "resume_policy": (
            "matching protocol hash and interrupted/incomplete status only"
        ),
        "scope_guards": {
            "weather_allowed": False,
            "departure_target_or_prediction_allowed": False,
            "actual_operational_outcomes_allowed": False,
            "chain_features_allowed": False,
            "arr_b_enabled": False,
            "auxiliary_weather_enabled": False,
            "shap_allowed": False,
            "ensemble_allowed": False,
            "champion_selection_allowed": False,
        },
    }
    observed_projection = {
        key: manifest.get(key) for key in expected_projection
    }
    if observed_projection != expected_projection:
        raise Week5ProtocolViolation("Week-5 manifest projection mismatch")


def _validate_runtime_dependencies(
    dependencies: Mapping[str, str], *, root: Path
) -> None:
    if dict(dependencies) != EXPECTED_DEPENDENCIES:
        raise Week5ProtocolViolation("frozen Week-5 dependency contract changed")
    observed = {
        "python": platform.python_version(),
        "xgboost": _package_version("xgboost"),
        "optuna": _package_version("optuna"),
        "numpy": _package_version("numpy"),
        "pandas": _package_version("pandas"),
        "pyarrow": _package_version("pyarrow"),
        "scikit_learn": _package_version("scikit-learn"),
    }
    if observed != EXPECTED_DEPENDENCIES:
        raise Week5ProtocolViolation(
            f"runtime dependency versions differ from frozen protocol: {observed!r}"
        )
    requirement_lines = {
        line.strip().lower()
        for line in (root / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    required_pins = {
        "numpy==2.2.6",
        "pandas==2.3.3",
        "pyarrow==25.0.1",
        "scikit-learn==1.9.0",
        "xgboost==3.2.0",
        "optuna==5.0.0",
    }
    if not required_pins.issubset(requirement_lines):
        raise Week5ProtocolViolation("requirements.txt lacks frozen dependency pins")


def _package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError as error:
        raise Week5ProtocolViolation(f"required dependency {name!r} is not installed") from error


def _four_finite_values(values: Sequence[float], *, label: str) -> tuple[float, ...]:
    observed = tuple(float(value) for value in values)
    if len(observed) != 4 or not all(math.isfinite(value) for value in observed):
        raise Week5ProtocolViolation(f"{label} requires exactly four finite fold values")
    return observed


def _read_yaml_mapping(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise Week5ProtocolViolation(f"{label} is unreadable") from error
    if not isinstance(payload, dict):
        raise Week5ProtocolViolation(f"{label} must contain a mapping")
    return payload


def _read_json_mapping(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise Week5ProtocolViolation(f"{label} is unreadable") from error
    if not isinstance(payload, dict):
        raise Week5ProtocolViolation(f"{label} must contain a mapping")
    return payload
