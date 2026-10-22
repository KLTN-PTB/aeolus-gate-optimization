"""Temporal stack integrity and independently checkable waiting decisions."""
import itertools
import time
from dataclasses import replace

import joblib
import numpy as np
import pandas as pd
import pytest

from src.models.thesis_models import ScheduleEncoder, ThesisBundle, temporal_meta_training
from src.optimization.domain import Flight, Gate, GateAssignment, GateResourceType
from src.optimization.waiting import WaitingConfig, solve_waiting, check, anneal


def flights():
    return [Flight("a", 0, "DL", "1", 0, 60, 0, nominal_gate_id="G", precomputed_gate_out_min=60),
            Flight("b", 1, "DL", "2", 55, 115, 55, nominal_gate_id="G", precomputed_gate_out_min=115)]


def test_waiting_cost_trades_off_against_finite_remote():
    f, gates = flights(), [Gate("G"), Gate("R", is_overflow=True)]
    cheap_wait = solve_waiting(f, gates, WaitingConfig(), budget=2)
    assert cheap_wait["optimality_proven"] and cheap_wait["decision_cost"] == 20
    assert cheap_wait["total_gate_wait_min"] == 20 and cheap_wait["remote_count"] == 0
    expensive_wait = solve_waiting(f, gates, WaitingConfig(wait_weight=20), budget=2)
    assert expensive_wait["optimality_proven"] and expensive_wait["decision_cost"] == 210
    assert expensive_wait["remote_count"] == 1 and expensive_wait["total_gate_wait_min"] == 0


def test_tight_wait_and_outbound_only_cannot_create_capacity():
    f = flights()
    result = solve_waiting(f, [Gate("G")], WaitingConfig(max_gate_wait_min=10), budget=2)
    assert not result["feasible"] and result["status"] == "INFEASIBLE"
    result = solve_waiting(f, [Gate("G")], WaitingConfig(allowed_wait_ids=()), budget=2)
    assert not result["feasible"]


def test_checker_rejects_forged_wait_or_shrunken_dwell():
    f = flights()[:1]
    a = GateAssignment("a", "G", occupancy_start_min=5, occupancy_end_min=65)
    with pytest.raises(ValueError, match="preserve"):
        check({"a": a}, f, [Gate("G")], WaitingConfig())
    a = replace(a, occupancy_start_min=31, occupancy_end_min=106)
    with pytest.raises(ValueError, match="bound"):
        check({"a": a}, f, [Gate("G")], WaitingConfig())


def test_cp_waiting_matches_exhaustive_small_problem():
    f, gates, cfg = flights(), [Gate("G"), Gate("R", is_overflow=True)], WaitingConfig(max_gate_wait_min=25)
    optimum = float("inf")
    for choices in itertools.product(range(2), repeat=2):
        for waits in itertools.product(range(26), repeat=2):
            a = {fl.flight_id: GateAssignment(fl.flight_id, gates[g].gate_id,
                 occupancy_start_min=fl.occupancy_start_min+w, occupancy_end_min=fl.occupancy_end_min+w)
                 for fl, g, w in zip(f, choices, waits)}
            diagnostic, _, costs, _ = check(a, f, gates, cfg)
            if diagnostic.is_valid:
                optimum = min(optimum, costs["decision_cost"])
    actual = solve_waiting(f, gates, cfg, budget=2)
    assert actual["optimality_proven"] and actual["decision_cost"] == optimum


@pytest.mark.parametrize("algorithm", ["greedy", "cpsat", "sa", "hybrid"])
def test_waiting_all_algorithms_return_independently_valid_windows(algorithm):
    result = solve_waiting(flights(), [Gate("G"), Gate("R", is_overflow=True)], algorithm=algorithm, budget=1)
    assert result["feasible"] and result["diagnostic"]["is_valid"]
    assert result["budget_compliant"]
    assert result["decision_cost"] >= 0
    if algorithm == "hybrid":
        assert result["decision_cost"] <= result["trace"]["initial_cost"]


def test_sa_can_improve_a_verified_suboptimal_initial_solution():
    f, gates, cfg = flights()[:1], [Gate("G"), Gate("R", is_overflow=True)], WaitingConfig()
    initial = {"a": GateAssignment("a", "R", is_overflow=True, occupancy_start_min=0, occupancy_end_min=75)}
    improved, trace = anneal(f, gates, cfg, time.perf_counter()+2, 202601, initial)
    assert trace["sa_best_cost"] == 0 and improved["a"].gate_id == "G"


def test_meta_learner_never_sees_outer_or_future_labels():
    rng = np.random.default_rng(3)
    oof = pd.DataFrame({"year": np.repeat([2017, 2018, 2019], 50), "flight_key": [str(i) for i in range(150)],
        "y": rng.integers(0, 2, 150), "linear": rng.random(150), "random_forest": rng.random(150),
        "xgboost_fixed": rng.random(150)})
    first, audit = temporal_meta_training(oof, 2019, "classification")
    changed = oof.copy()
    changed.loc[changed.year >= 2019, "y"] = 1-changed.loc[changed.year >= 2019, "y"]
    second, _ = temporal_meta_training(changed, 2019, "classification")
    np.testing.assert_array_equal(first.coef_, second.coef_)
    assert audit["last_year"] == 2018 and audit["rows"] == 100


def test_no_future_io_before_evaluation(tmp_path):
    from src.pipeline.thesis_training import Training
    runner = object.__new__(Training)
    runner.evaluation_open = False
    with pytest.raises(PermissionError):
        runner.read_year("arrival", 2024)
    with pytest.raises(PermissionError):
        runner.read_year("arrival", 2023)


def test_subcent_costs_keep_exact_cp_objective():
    cfg = WaitingConfig(wait_weight=.000001, reassignment_weight=.000003, remote_weight=.00001)
    result = solve_waiting(flights(), [Gate('G'), Gate('R', is_overflow=True)], cfg, budget=2)
    assert result['optimality_proven']
    assert result['best_bound'] == pytest.approx(result['decision_cost'], abs=1e-12)
    assert result['remote_count'] == 1


def test_wait_zero_matches_fixed_intervals_and_cross_midnight_capacity():
    f = [replace(x, predicted_arrival_min=x.predicted_arrival_min+1400,
                 precomputed_gate_out_min=x.simulated_departure_min+1400) for x in flights()]
    result = solve_waiting(f, [Gate('G', capacity=2, resource_type=GateResourceType.FINITE_REMOTE_STAND,
                                   available_windows=((1400, 1600),))],
                           WaitingConfig(max_gate_wait_min=0), budget=2)
    assert result['feasible'] and result['total_gate_wait_min'] == 0
    assert result['assignments'][0]['occupancy_end_min'] > 1440
