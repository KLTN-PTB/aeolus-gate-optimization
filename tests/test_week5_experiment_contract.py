from __future__ import annotations

import pytest

from src.models.contracts import ExperimentSpec, Week4ContractViolation
from src.models.week5_contracts import Week5ExperimentSpec
from src.models.week5_hpo_protocol import Week5ProtocolViolation


def test_historical_week4_contract_still_rejects_xgboost() -> None:
    with pytest.raises(Week4ContractViolation, match="Week 4 does not permit"):
        ExperimentSpec(
            method_id="xgboost",  # type: ignore[arg-type]
            model_version="historically_not_week4",
            config_version="0.1.0",
            seed=202601,
        )


@pytest.mark.parametrize(
    ("method_id", "model_family"),
    [
        ("random_forest", "tree"),
        ("hist_gradient_boosting", "boosting"),
        ("xgboost", "boosting"),
    ],
)
def test_week5_tuned_contract_accepts_only_registered_methods(
    method_id: str, model_family: str
) -> None:
    spec = Week5ExperimentSpec(
        method_id=method_id,  # type: ignore[arg-type]
        model_version=f"arrival_{method_id}_tuned_rolling_run_v1_1",
        config_version="0.1.0",
        seed=202601,
    )

    assert spec.model_family == model_family
    assert spec.experiment_contract_version == "arrival_week5_tuned_experiment_v1"


def test_week5_tuned_contract_rejects_unknown_method() -> None:
    with pytest.raises(Week5ProtocolViolation, match="does not permit"):
        Week5ExperimentSpec(
            method_id="made_up_model",  # type: ignore[arg-type]
            model_version="invalid",
            config_version="0.1.0",
            seed=202601,
        )
