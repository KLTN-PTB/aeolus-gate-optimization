from scripts.run_day3_lightgbm_diagnostics import (
    _reference_row,
    diagnostic_mode,
    build_diagnostic_regressor,
)


def test_l1_ordinal_uses_default_l1_capacity():
    model = build_diagnostic_regressor("l1_ordinal", seed=42)

    assert diagnostic_mode("l1_ordinal") == "ordinal"
    assert model.get_params()["objective"] == "regression_l1"
    assert model.get_params()["num_leaves"] == 31
    assert model.get_params()["n_estimators"] == 500
    assert model.get_params()["min_data_in_leaf"] == 20


def test_l2_reduced_uses_explicit_reduced_capacity():
    model = build_diagnostic_regressor("l2_reduced_native", seed=42)

    assert diagnostic_mode("l2_reduced_native") == "native"
    assert model.get_params()["objective"] == "regression"
    assert model.get_params()["num_leaves"] == 15
    assert model.get_params()["n_estimators"] == 200
    assert model.get_params()["min_data_in_leaf"] == 50
    assert model.get_params()["lambda_l2"] == 1.0


def test_reference_row_supports_b2_and_default_lightgbm_artifact_shapes():
    b2 = {
        "fold_summary": {
            "b2": {"fold_4": {"skill_mean": -0.25, "mae_mean": 19.88}}
        }
    }
    native = {
        "fold_summary": {
            "fold_4": {
                "lightgbm": {
                    "skill_score_vs_carrier_hour": {"mean": -0.83},
                    "mae": {"mean": 20.00},
                }
            }
        }
    }

    assert _reference_row(b2, "fold_4", model_key="b2") == {
        "skill_mean": -0.25,
        "mae_mean": 19.88,
    }
    assert _reference_row(native, "fold_4", model_key="lightgbm") == {
        "skill_mean": -0.83,
        "mae_mean": 20.00,
    }
