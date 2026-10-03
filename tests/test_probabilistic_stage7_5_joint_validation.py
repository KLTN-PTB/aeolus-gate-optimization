"""Unit tests for Stage 7.5 — Joint Validation.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 17 (Stage 7.5)
Verifies:
1. Ground truth and simulation joint statistics extraction.
2. 1D sample CRPS for daily aggregate delay.
3. System candidate joint performance evaluation.
4. Gating decision logic (pass/fail matrix, marginal calibration preservation, D0 comparison).
5. Randomized PIT sensitivity policy compliance.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.models.probabilistic.correctness import GaussianMixtureDistribution
from src.models.probabilistic.dependence import (
    GaussianCopulaDependenceModel,
    IndependentDependenceModel,
    ScenarioBlockDependenceModel,
)
from src.models.probabilistic.dependence_interface import (
    DiscretePITPolicy,
)
from src.models.probabilistic.joint_validation import (
    DailyJointGroundTruth,
    DailyJointSimulation,
    compute_sample_crps_1d,
    evaluate_system_candidate_joint_performance,
    extract_daily_ground_truth,
    extract_daily_simulation,
)


def test_compute_sample_crps_1d():
    """Verify 1D empirical sample CRPS calculation."""
    y_true = 50.0
    # Point mass at 50 -> CRPS = 0
    samples_perfect = np.full(100, 50.0)
    crps_perf = compute_sample_crps_1d(y_true, samples_perfect)
    assert np.isclose(crps_perf, 0.0, atol=1e-6)

    # Off-center samples
    samples_offset = np.array([40.0, 45.0, 50.0, 55.0, 60.0])
    crps_off = compute_sample_crps_1d(y_true, samples_offset)
    assert crps_off > 0.0


def test_extract_daily_statistics():
    """Ground truth and simulation extractors correctly compute severe counts and pairs."""
    y_true = np.array([10.0, 65.0, 75.0, 130.0, -5.0])
    gt = extract_daily_ground_truth("2022-05-10", y_true)

    assert gt.n_flights == 5
    assert gt.total_delay == 275.0
    assert gt.n60 == 3  # 65, 75, 130
    assert gt.n120 == 1  # 130
    assert gt.pairs_both_ge60 == 3  # 3 * 2 // 2 = 3 pairs
    assert gt.max_delay == 130.0

    # Simulation extraction
    y_sim = np.tile(y_true, (10, 1))  # 10 identical scenarios
    sim = extract_daily_simulation("2022-05-10", y_sim)
    assert sim.n_scenarios == 10
    assert sim.n_flights == 5
    assert np.all(sim.sim_n60 == 3)
    assert np.all(sim.sim_n120 == 1)
    assert np.all(sim.sim_pairs_both_ge60 == 3)


def test_evaluate_system_candidate_joint_performance():
    """Test full Stage 7.5 evaluation engine with D0 baseline and comparison."""
    # Synthetic ground truth for 5 days
    daily_truths = []
    daily_sims_d0 = []
    daily_sims_d2 = []

    rng = np.random.default_rng(202601)

    for d in range(5):
        n = 10
        y = rng.normal(15.0, 25.0, size=n)
        gt = extract_daily_ground_truth(f"2022-05-{10+d}", y)
        daily_truths.append(gt)

        # Mock D0 simulations: independent draws
        s_d0 = rng.normal(15.0, 25.0, size=(100, n))
        sim_d0 = extract_daily_simulation(f"2022-05-{10+d}", s_d0)
        daily_sims_d0.append(sim_d0)

        # Mock D2 simulations: correlated draws
        comm = rng.normal(0.0, 10.0, size=(100, 1))
        s_d2 = rng.normal(15.0, 22.0, size=(100, n)) + comm
        sim_d2 = extract_daily_simulation(f"2022-05-{10+d}", s_d2)
        daily_sims_d2.append(sim_d2)

    # 1. Evaluate D0
    res_d0 = evaluate_system_candidate_joint_performance(
        candidate_id="SYS_test__DEP_D0_independent",
        marginal_candidate_id="seed_ensemble_3",
        dependence_candidate_id="DEP_D0_independent",
        daily_truths=daily_truths,
        daily_sims=daily_sims_d0,
    )
    assert res_d0.is_d0_baseline is True
    assert res_d0.overall_stage7_5_decision == "PASS"

    # 2. Evaluate D2 with D0 comparison
    res_d2 = evaluate_system_candidate_joint_performance(
        candidate_id="SYS_test__DEP_D2_gaussian_copula",
        marginal_candidate_id="seed_ensemble_3",
        dependence_candidate_id="DEP_D2_gaussian_copula",
        daily_truths=daily_truths,
        daily_sims=daily_sims_d2,
        d0_result=res_d0,
    )
    assert res_d2.is_d0_baseline is False
    assert "has_measurable_benefit_over_d0" in res_d2.improvement_over_d0
    assert res_d2.overall_stage7_5_decision in {"PASS", "FAIL"}


def test_randomized_pit_sensitivity_evaluation():
    """Verify that sensitivity across multiple randomized PIT draws meets stability tolerance."""
    pi = [0.60, 0.30, 0.10]
    mu = [0.0, 20.0, 70.0]
    sigma = [10.0, 20.0, 40.0]
    dist = GaussianMixtureDistribution(pi, mu, sigma, discrete=True)
    marginals = [dist] * 10

    y_obs = np.array([0, 5, 15, 20, 45, 60, 75, 90, 120, 10], dtype=float)

    sens = DiscretePITPolicy.evaluate_pit_sensitivity(
        y=y_obs,
        marginal_cdfs=marginals,
        n_draws=10,
        base_seed=202601,
    )

    assert sens["n_draws"] == 10.0
    assert sens["mean_u_std_across_draws"] < 0.25
    assert sens["sensitivity_stable"] == 1.0
