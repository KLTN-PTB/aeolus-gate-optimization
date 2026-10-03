"""Tests for seed reproducibility and realization hash verification (Phase 9)."""

from __future__ import annotations

import numpy as np
import pytest

from src.evaluation.monte_carlo_comparison import (
    MonteCarloDelayTransformer,
    audit_monte_carlo_randomness,
    generate_common_latent_variables,
)


def test_fixed_seed_is_bit_identical() -> None:
    """Same seed must produce bit-for-bit identical latent variables and delay matrices."""
    n_scen = 100
    n_flights = 10
    base_delays = [10.0] * n_flights

    # Run 1
    u1 = generate_common_latent_variables(n_scenarios=n_scen, n_flights=n_flights, seed=202601)
    mat1 = MonteCarloDelayTransformer.transform("P4_ngboost_student_t", u1, base_delays)
    audit1 = audit_monte_carlo_randomness(mat1, requested_n=n_scen, model_id="P4_ngboost_student_t")

    # Run 2
    u2 = generate_common_latent_variables(n_scenarios=n_scen, n_flights=n_flights, seed=202601)
    mat2 = MonteCarloDelayTransformer.transform("P4_ngboost_student_t", u2, base_delays)
    audit2 = audit_monte_carlo_randomness(mat2, requested_n=n_scen, model_id="P4_ngboost_student_t")

    np.testing.assert_array_equal(u1, u2)
    np.testing.assert_array_equal(mat1, mat2)
    assert audit1.matrix_sha256 == audit2.matrix_sha256


def test_different_seeds_produce_distinct_realizations() -> None:
    """Different seeds must produce distinct realizations and distinct hashes."""
    n_scen = 100
    n_flights = 10
    base_delays = [10.0] * n_flights

    u1 = generate_common_latent_variables(n_scenarios=n_scen, n_flights=n_flights, seed=202601)
    mat1 = MonteCarloDelayTransformer.transform("P4_ngboost_student_t", u1, base_delays)
    audit1 = audit_monte_carlo_randomness(mat1, requested_n=n_scen, model_id="P4_ngboost_student_t")

    u2 = generate_common_latent_variables(n_scenarios=n_scen, n_flights=n_flights, seed=202602)
    mat2 = MonteCarloDelayTransformer.transform("P4_ngboost_student_t", u2, base_delays)
    audit2 = audit_monte_carlo_randomness(mat2, requested_n=n_scen, model_id="P4_ngboost_student_t")

    assert not np.array_equal(u1, u2)
    assert not np.array_equal(mat1, mat2)
    assert audit1.matrix_sha256 != audit2.matrix_sha256
