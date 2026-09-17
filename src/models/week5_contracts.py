"""Week-5-only contracts layered on the historical Week-4 framework.

The module deliberately reuses Week-4 fold data validation and row identity
types without expanding the list of methods that Week 4 historically allowed.
"""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal, Mapping

from src.data.preprocessing import PREPROCESSING_VERSION
from src.models.contracts import (
    CLASSIFICATION_THRESHOLD,
    FEATURE_MANIFEST_VERSION,
    RollingFold,
)
from src.models.week5_hpo_protocol import (
    EXPECTED_FOLDS,
    EXPECTED_STUDY_IDS,
    Week5HPOProtocol,
    Week5ProtocolViolation,
    assert_hpo_year_allowed,
)


Week5Method = Literal["random_forest", "hist_gradient_boosting", "xgboost"]
HPOTask = Literal["classification", "regression"]
Week5ModelFamily = Literal["tree", "boosting"]

WEEK5_METHOD_MODEL_FAMILY: Final[dict[Week5Method, Week5ModelFamily]] = {
    "random_forest": "tree",
    "hist_gradient_boosting": "boosting",
    "xgboost": "boosting",
}
WEEK5_TUNED_EXPERIMENT_CONTRACT_VERSION: Final = (
    "arrival_week5_tuned_experiment_v1"
)


@dataclass(frozen=True)
class Week5ExperimentSpec:
    """Stage-scoped metadata for tuned Week-5 rolling OOF materialization."""

    method_id: Week5Method
    model_version: str
    config_version: str
    seed: int
    feature_manifest_version: str = FEATURE_MANIFEST_VERSION
    preprocessing_version: str = PREPROCESSING_VERSION
    experiment_contract_version: str = WEEK5_TUNED_EXPERIMENT_CONTRACT_VERSION
    classification_threshold: float = CLASSIFICATION_THRESHOLD
    expected_validation_row_fingerprints: Mapping[str, str] | None = None

    def __post_init__(self) -> None:
        if self.method_id not in WEEK5_METHOD_MODEL_FAMILY:
            raise Week5ProtocolViolation(
                f"Week 5 tuned OOF does not permit method {self.method_id!r}"
            )
        if not self.model_version or not self.config_version:
            raise Week5ProtocolViolation(
                "Week-5 tuned model and config versions must be non-empty"
            )
        if self.feature_manifest_version != FEATURE_MANIFEST_VERSION:
            raise Week5ProtocolViolation("unexpected Arrival feature manifest version")
        if self.preprocessing_version != PREPROCESSING_VERSION:
            raise Week5ProtocolViolation("unexpected Arrival preprocessing version")
        if (
            self.experiment_contract_version
            != WEEK5_TUNED_EXPERIMENT_CONTRACT_VERSION
        ):
            raise Week5ProtocolViolation(
                "unexpected Week-5 tuned experiment contract version"
            )
        if self.classification_threshold != CLASSIFICATION_THRESHOLD:
            raise Week5ProtocolViolation(
                "Week-5 tuned reporting threshold is locked at 0.5"
            )
        if self.expected_validation_row_fingerprints is not None and any(
            not fold_id or not fingerprint
            for fold_id, fingerprint in self.expected_validation_row_fingerprints.items()
        ):
            raise Week5ProtocolViolation(
                "expected validation row fingerprints must be non-empty"
            )

    @property
    def model_family(self) -> Week5ModelFamily:
        return WEEK5_METHOD_MODEL_FAMILY[self.method_id]


@dataclass(frozen=True)
class Week5StudySpec:
    """Validated declaration for one frozen Week-5 Optuna study."""

    study_id: str
    study_name: str
    method_id: Week5Method
    task: HPOTask
    direction: Literal["maximize", "minimize"]
    objective_metric: str
    seed: int
    feature_manifest_version: str
    preprocessing_version: str
    protocol_hash: str
    search_space: Mapping[str, Mapping[str, Any]]
    fixed_parameters: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.method_id not in WEEK5_METHOD_MODEL_FAMILY:
            raise Week5ProtocolViolation(
                f"Week 5 does not permit HPO method {self.method_id!r}"
            )
        if self.task not in {"classification", "regression"}:
            raise Week5ProtocolViolation(f"unsupported Week-5 HPO task {self.task!r}")
        if self.study_id != f"{self.method_id}_{self.task}":
            raise Week5ProtocolViolation("study ID does not match its method and task")
        expected_direction = "maximize" if self.task == "classification" else "minimize"
        if self.direction != expected_direction:
            raise Week5ProtocolViolation("study direction conflicts with its task")
        expected_metric = (
            "mean_pr_auc_across_locked_folds"
            if self.task == "classification"
            else "mean_mae_across_locked_folds"
        )
        if self.objective_metric != expected_metric:
            raise Week5ProtocolViolation("study objective conflicts with its task")
        if not self.study_name or not self.protocol_hash or self.seed < 0:
            raise Week5ProtocolViolation("study identity, protocol hash, and seed are required")
        if not self.search_space:
            raise Week5ProtocolViolation("Week-5 HPO search space must be non-empty")

    @property
    def model_family(self) -> Week5ModelFamily:
        return WEEK5_METHOD_MODEL_FAMILY[self.method_id]


def load_week5_study_specs(
    protocol: Week5HPOProtocol,
) -> dict[str, Week5StudySpec]:
    """Project the frozen protocol into validated, task-specific study specs."""

    config = protocol.config
    studies = config.get("studies")
    if not isinstance(studies, dict) or set(studies) != EXPECTED_STUDY_IDS:
        raise Week5ProtocolViolation("Week-5 protocol must declare exactly six studies")
    task_contract = config["task_contract"]
    seed = int(config["randomness"]["model_random_state"])
    result: dict[str, Week5StudySpec] = {}
    for study_id, declaration in studies.items():
        result[study_id] = Week5StudySpec(
            study_id=study_id,
            study_name=str(declaration["study_name"]),
            method_id=declaration["method"],
            task=declaration["task_type"],
            direction=declaration["direction"],
            objective_metric=str(declaration["objective_metric"]),
            seed=seed,
            feature_manifest_version=str(task_contract["feature_manifest_version"]),
            preprocessing_version=str(task_contract["preprocessing_version"]),
            protocol_hash=protocol.protocol_hash,
            search_space=deepcopy(declaration["search_space"]),
            fixed_parameters=deepcopy(declaration["fixed_parameters"]),
        )
    return result


def load_week5_rolling_folds(
    protocol: Week5HPOProtocol,
) -> tuple[RollingFold, ...]:
    """Load only the exact four frozen folds and route every year through HPO guard."""

    configured = protocol.config.get("folds")
    if not isinstance(configured, list):
        raise Week5ProtocolViolation("Week-5 protocol lacks rolling folds")
    folds: list[RollingFold] = []
    for item in configured:
        if not isinstance(item, dict):
            raise Week5ProtocolViolation("malformed Week-5 rolling fold")
        fold_id = item.get("id")
        train_years = item.get("train_years")
        validation_year = item.get("validation_year")
        if (
            not isinstance(fold_id, str)
            or not isinstance(train_years, list)
            or not all(type(year) is int for year in train_years)
            or type(validation_year) is not int
        ):
            raise Week5ProtocolViolation("malformed Week-5 rolling fold")
        folds.append(RollingFold(fold_id, tuple(train_years), validation_year))
    observed = tuple(folds)
    validate_week5_rolling_folds(observed)
    return observed


def validate_week5_rolling_folds(folds: tuple[RollingFold, ...]) -> None:
    """Fail closed on blocked years and any deviation from the four locked folds."""

    for fold in folds:
        for year in (*fold.train_years, fold.validation_year):
            assert_hpo_year_allowed(year)
    observed = tuple(
        {
            "id": fold.fold_id,
            "train_years": list(fold.train_years),
            "validation_year": fold.validation_year,
        }
        for fold in folds
    )
    if observed != EXPECTED_FOLDS:
        raise Week5ProtocolViolation("HPO requires exactly the four locked rolling folds")


def assert_week5_result_artifact_writable(
    path: Path,
    *,
    protocol_hash: str,
) -> None:
    """Protect result artifacts from mismatched resumes and all overwrites."""

    target = Path(path)
    temporary = target.with_suffix(target.suffix + ".tmp")
    if temporary.exists():
        raise Week5ProtocolViolation(
            f"temporary Week-5 result artifact already exists: {temporary}"
        )
    if not target.exists():
        return
    try:
        existing = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise Week5ProtocolViolation("existing Week-5 result artifact is unreadable") from error
    if not isinstance(existing, dict):
        raise Week5ProtocolViolation("existing Week-5 result artifact is malformed")
    if existing.get("protocol_hash") != protocol_hash:
        raise Week5ProtocolViolation("Week-5 result artifact protocol hash mismatch")
    if existing.get("status") == "COMPLETED":
        raise Week5ProtocolViolation("refusing to overwrite a completed artifact")
    raise Week5ProtocolViolation("refusing to overwrite an existing Week-5 result artifact")
