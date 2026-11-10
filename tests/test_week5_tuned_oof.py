from __future__ import annotations

from pathlib import Path

import pytest

from src.models.week5_hpo_protocol import Week5ProtocolViolation
from src.models.week5_hpo_protocol_v1_1 import load_week5_hpo_protocol_v1_1
from src.models.week5_tuned_oof import load_tuned_method_inputs


def test_tuned_oof_reader_uses_all_three_authoritative_hpo_sources() -> None:
    inputs = load_tuned_method_inputs(Path("."), load_week5_hpo_protocol_v1_1())

    assert set(inputs) == {"random_forest", "hist_gradient_boosting", "xgboost"}
    assert inputs["random_forest"].classification_params["n_estimators"] == 160
    assert inputs["hist_gradient_boosting"].regression_params["max_iter"] == 250
    assert inputs["xgboost"].classification_params["n_estimators"] == 150
    assert all(item.protocol_hash == "b987c0489c5d18b02500f34c786c01359f45e50b2b32bdea3de4332a161556e5" for item in inputs.values())


def test_tuned_oof_reader_fails_closed_when_authoritative_result_is_missing(
    tmp_path: Path,
) -> None:
    with pytest.raises(Week5ProtocolViolation, match="authoritative"):
        load_tuned_method_inputs(tmp_path, load_week5_hpo_protocol_v1_1())
