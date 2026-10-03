from __future__ import annotations

from scripts.run_phase_a_benchmark_mae import (
    build_tuned_xgb_regressor,
    summarize_seed_metric,
)


def test_day2_xgb_builder_keeps_tuned_params_and_allows_objective_override():
    model = build_tuned_xgb_regressor("reg:absoluteerror", seed=42)

    params = model.get_params()
    assert params["objective"] == "reg:absoluteerror"
    assert params["n_estimators"] == 200
    assert params["max_depth"] == 4
    assert params["learning_rate"] == 0.062477640978226154
    assert params["tree_method"] == "hist"
    assert params["device"] == "cpu"
    assert params["n_jobs"] == 1
    assert params["random_state"] == 42


def test_day2_metric_summary_reports_mean_and_population_std():
    result = summarize_seed_metric(
        [{"metric": 1.0}, {"metric": 3.0}],
        key="metric",
    )

    assert result == {"mean": 2.0, "std": 1.0}
