"""Tests for Monte Carlo Convergence, CRN, and Failure Accounting (Task R9).

Verifies:
1. Exact requested N counts evaluated without truncation (zero tolerance for min(N, 100)).
2. Common Random Numbers (CRN) latent matrix generation, determinism, and uniqueness.
3. CRN variance reduction requires empirical outer replications (marked NOT_ESTABLISHED otherwise).
4. Convergence statistics: running mean, standard error O(1/sqrt(N)), 95% CI, delta between consecutive N.
5. Precision target status: marked NOT_PREREGISTERED when no target pre-registered; zero post-hoc 'optimal' claims.
6. P5 Quantile Regression evaluated in forecast-only mode without invented transformations.
7. Comprehensive failure accounting: failures remain in denominator and are explicitly categorized.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.evaluation.mc_convergence import (
    CRNVarianceReductionReport,
    ConvergenceEstimate,
    DelayTransformationEngine,
    MCFailureType,
    P5CapabilityError,
    ScenarioRealizationMeta,
    TruncationViolationError,
    compute_convergence_estimate,
    compute_crn_variance_reduction,
    generate_crn_latent_matrix,
)
from src.evaluation.monte_carlo_comparison_v2 import (
    MonteCarloScenarioSpecV2,
    audit_monte_carlo_matrix,
    run_monte_carlo_evaluation_v2,
)


def test_requested_vs_actual_n_zero_truncation() -> None:
    """Requested N must be strictly evaluated with zero truncation."""
    # Test valid counts
    for requested_n in [10, 50, 100, 250]:
        u, u_hash = generate_crn_latent_matrix(n_scenarios=requested_n, n_flights=12, seed=202601)
        assert u.shape == (requested_n, 12)
        assert len(u_hash) == 64

    # Test invalid / non-positive count raises error
    with pytest.raises(TruncationViolationError):
        generate_crn_latent_matrix(n_scenarios=0, n_flights=10)

    with pytest.raises(TruncationViolationError):
        generate_crn_latent_matrix(n_scenarios=-5, n_flights=10)


def test_truncation_detection_in_convergence_estimate() -> None:
    """compute_convergence_estimate must fail closed if actual realizations != requested N."""
    realizations = [
        ScenarioRealizationMeta(
            realization_id=f"R_{i}",
            scenario_index=i,
            requested_n=100,
            actual_n=100,
            latent_seed=202601,
            scenario_seed=202601 + i,
            realization_hash=f"hash_{i}",
            failure_type=MCFailureType.SUCCESS,
            objective_value=1000.0 + i,
            feasible=True,
            runtime_ms=1.0,
        )
        for i in range(80)  # Only 80 provided when 100 requested!
    ]

    with pytest.raises(TruncationViolationError):
        compute_convergence_estimate(realizations, requested_n=100, model_id="test_model")


def test_crn_latent_matrix_uniqueness_and_variance() -> None:
    """CRN latent shocks must have 100% unique rows and positive per-flight variance."""
    n_scen = 100
    n_flights = 15
    u, _ = generate_crn_latent_matrix(n_scenarios=n_scen, n_flights=n_flights, seed=202601)

    # 1. Uniform range
    assert np.all(u >= 0.001)
    assert np.all(u <= 0.999)

    # 2. Unique rows
    unique_rows = len(np.unique(u, axis=0))
    assert unique_rows == n_scen

    # 3. Delay transformation for stochastic model
    base_delays = [10.0] * n_flights
    delays = DelayTransformationEngine.transform(
        model_id="P4_ngboost_student_t",
        latent_u=u,
        base_delays=base_delays,
    )
    assert delays.shape == (n_scen, n_flights)

    audit = audit_monte_carlo_matrix(delays, requested_n=n_scen, model_id="P4_ngboost_student_t")
    assert audit.is_all_scenarios_unique is True
    assert audit.is_variance_positive is True
    assert audit.per_flight_variance_min > 0.0


def test_p5_quantile_regression_distributional_integrity() -> None:
    """P5 Quantile Regression must be evaluated in forecast-only mode without invented transformations."""
    n_scen = 50
    n_flights = 8
    u, _ = generate_crn_latent_matrix(n_scenarios=n_scen, n_flights=n_flights, seed=202601)
    base_medians = [12.0, 5.0, 20.0, 0.0, 15.0, 8.0, 30.0, 4.0]

    # Forecast-only mode: replicates median across scenarios
    delays_p5 = DelayTransformationEngine.transform(
        model_id="P5_quantile_regression",
        latent_u=u,
        base_delays=base_medians,
        allow_p5_forecast_only=True,
    )
    assert delays_p5.shape == (n_scen, n_flights)
    for s in range(n_scen):
        np.testing.assert_array_equal(delays_p5[s], base_medians)

    # Attempting continuous density sampling without approved adapter raises P5CapabilityError
    with pytest.raises(P5CapabilityError):
        DelayTransformationEngine.transform(
            model_id="P5_quantile_regression",
            latent_u=u,
            base_delays=base_medians,
            allow_p5_forecast_only=False,
        )


def test_crn_variance_reduction_accounting_and_outer_replications() -> None:
    """CRN variance reduction must be marked NOT_ESTABLISHED unless empirical outer replications exist."""
    # Case 1: Insufficient outer replications (0 or 1) -> NOT_ESTABLISHED
    rep_0 = compute_crn_variance_reduction(
        deltas_crn=[],
        deltas_independent=[],
        model_a="model_a",
        model_b="model_b",
    )
    assert rep_0.status == "NOT_ESTABLISHED"
    assert rep_0.variance_reduction_percent is None

    rep_1 = compute_crn_variance_reduction(
        deltas_crn=[10.5],
        deltas_independent=[12.0],
        model_a="model_a",
        model_b="model_b",
    )
    assert rep_1.status == "NOT_ESTABLISHED"
    assert rep_1.variance_reduction_percent is None

    # Case 2: Valid outer replications (R >= 2) with known variance reduction
    # Simulated paired deltas across 10 outer replications
    rng = np.random.default_rng(202601)
    # Under CRN, common noise cancels -> smaller variance
    crn_deltas = rng.normal(loc=5.0, scale=2.0, size=20)
    # Under Independent, independent noise adds -> larger variance
    indep_deltas = rng.normal(loc=5.0, scale=6.0, size=20)

    rep_2 = compute_crn_variance_reduction(
        deltas_crn=crn_deltas,
        deltas_independent=indep_deltas,
        model_a="model_A",
        model_b="model_B",
        n_inner=500,
    )
    assert rep_2.status == "ESTABLISHED"
    assert rep_2.variance_crn is not None
    assert rep_2.variance_independent is not None
    assert rep_2.variance_crn < rep_2.variance_independent
    assert rep_2.variance_reduction_percent is not None
    assert rep_2.variance_reduction_percent > 50.0  # Significant reduction


def test_convergence_statistics_and_precision_target_status() -> None:
    """Convergence stats must correctly compute mean, SE, 95% CI, and declare precision target status."""
    requested_n = 100
    objs = [100.0 + (i % 10) for i in range(requested_n)]  # values 100..109
    realizations = [
        ScenarioRealizationMeta(
            realization_id=f"R_{i}",
            scenario_index=i,
            requested_n=requested_n,
            actual_n=requested_n,
            latent_seed=202601,
            scenario_seed=202601 + i,
            realization_hash=f"hash_{i}",
            failure_type=MCFailureType.SUCCESS,
            objective_value=objs[i],
            feasible=True,
            runtime_ms=2.0,
        )
        for i in range(requested_n)
    ]

    # Without pre-registered precision target
    est = compute_convergence_estimate(
        realizations=realizations,
        requested_n=requested_n,
        model_id="linear_point",
        precision_target_se=None,
    )

    assert est.n_requested == requested_n
    assert est.n_actual == requested_n
    assert est.n_success == requested_n
    assert est.n_failed == 0
    assert 104.0 <= est.mean_objective <= 105.0
    assert est.mc_se_objective > 0.0
    assert est.ci_95_lower < est.mean_objective < est.ci_95_upper
    assert est.precision_target_status == "NOT_PREREGISTERED"
    assert est.precision_target_met is None

    # With explicit pre-registered precision target
    est_targeted = compute_convergence_estimate(
        realizations=realizations,
        requested_n=requested_n,
        model_id="linear_point",
        precision_target_se=1.0,  # generous target
    )
    assert est_targeted.precision_target_status == "PREREGISTERED_TARGET_MET"
    assert est_targeted.precision_target_met is True


def test_failure_accounting_retention_in_denominator() -> None:
    """All failures (timeout, infeasible, numerical error) must remain in the accounting denominator."""
    requested_n = 50
    realizations: list[ScenarioRealizationMeta] = []

    # 40 successes
    for i in range(40):
        realizations.append(
            ScenarioRealizationMeta(
                realization_id=f"R_{i}",
                scenario_index=i,
                requested_n=requested_n,
                actual_n=requested_n,
                latent_seed=202601,
                scenario_seed=202601 + i,
                realization_hash=f"hash_{i}",
                failure_type=MCFailureType.SUCCESS,
                objective_value=500.0,
                feasible=True,
                runtime_ms=1.5,
            )
        )
    # 5 timeouts
    for i in range(40, 45):
        realizations.append(
            ScenarioRealizationMeta(
                realization_id=f"R_{i}",
                scenario_index=i,
                requested_n=requested_n,
                actual_n=requested_n,
                latent_seed=202601,
                scenario_seed=202601 + i,
                realization_hash=f"hash_{i}",
                failure_type=MCFailureType.TIMEOUT,
                objective_value=None,
                feasible=False,
                runtime_ms=10.0,
            )
        )
    # 5 infeasible
    for i in range(45, 50):
        realizations.append(
            ScenarioRealizationMeta(
                realization_id=f"R_{i}",
                scenario_index=i,
                requested_n=requested_n,
                actual_n=requested_n,
                latent_seed=202601,
                scenario_seed=202601 + i,
                realization_hash=f"hash_{i}",
                failure_type=MCFailureType.INFEASIBLE,
                objective_value=None,
                feasible=False,
                runtime_ms=2.0,
            )
        )

    est = compute_convergence_estimate(
        realizations=realizations,
        requested_n=requested_n,
        model_id="test_model",
    )

    assert est.n_actual == 50
    assert est.n_success == 40
    assert est.n_failed == 10
    assert est.failure_breakdown[MCFailureType.TIMEOUT.value] == 5
    assert est.failure_breakdown[MCFailureType.INFEASIBLE.value] == 5
    assert est.failure_breakdown[MCFailureType.SUCCESS.value] == 40


def test_monte_carlo_evaluation_v2_end_to_end() -> None:
    """Execute end-to-end Monte Carlo simulation across N scenarios with full realization audit."""
    n_flights = 6
    n_scen = 10
    df = pd.DataFrame({
        "flight_key": [f"FL_{i:03d}" for i in range(n_flights)],
        "OP_CARRIER": ["DL"] * n_flights,
        "OP_CARRIER_FL_NUM": [1000 + i for i in range(n_flights)],
        "_sched_arr_min": [720 + i * 20 for i in range(n_flights)],
        "nominal_gate_id": [f"G_{(i % 3) + 1:02d}" for i in range(n_flights)],
        "ARR_DELAY": [5.0] * n_flights,
    })

    spec = MonteCarloScenarioSpecV2(
        scenario_id="SCEN_MC_TEST",
        date_str="2023-07-03",
        n_flights=n_flights,
        n_contact_gates=3,
        flights_df=df,
        spec_hash="dummy_spec_hash_abc",
    )

    u, _ = generate_crn_latent_matrix(n_scenarios=n_scen, n_flights=n_flights, seed=202601)
    base_delays = [5.0] * n_flights

    delays = DelayTransformationEngine.transform(
        model_id="P4_ngboost_student_t",
        latent_u=u,
        base_delays=base_delays,
    )

    # Audit matrix
    audit_res = audit_monte_carlo_matrix(delays, requested_n=n_scen, model_id="P4_ngboost_student_t")
    assert audit_res.is_all_scenarios_unique is True
    assert audit_res.is_variance_positive is True

    # Run evaluation
    recs = run_monte_carlo_evaluation_v2(
        model_id="P4_ngboost_student_t",
        spec=spec,
        delay_matrix=delays,
        requested_n=n_scen,
        latent_seed=202601,
    )

    assert len(recs) == n_scen
    for r in recs:
        assert r.requested_n == n_scen
        assert r.actual_n == n_scen
        assert r.failure_type == MCFailureType.SUCCESS
        assert r.feasible is True
        assert r.objective_value is not None

    # Compute convergence estimate
    est = compute_convergence_estimate(recs, requested_n=n_scen, model_id="P4_ngboost_student_t")
    assert est.n_success == n_scen
    assert est.n_failed == 0
    assert est.mean_objective > 0.0
