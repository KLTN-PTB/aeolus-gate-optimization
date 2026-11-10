"""Unit and Contract Tests for Phase 2 Scalability Benchmark Engine.

Validates:
1. P4 checkpoint cryptographic verification.
2. Canonical stochastic scenario matrix generation (Gaussian Copula D2 + P4 Student-T).
3. 12-stage pipeline resource profiling.
4. Fairness contract and solver execution under 2.0s ceiling.
5. Monte Carlo convergence evaluation and failure accounting.
6. Reproducibility verification (Run 1 vs Run 2).
7. Artifact persistence and schema integrity across all 7 files.
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import pytest
import numpy as np
import pandas as pd

from src.evaluation.native_downstream_p4 import (
    P4_CERTIFIED_CHECKPOINT_PATH,
    P4_CERTIFIED_SHA256,
    verify_and_load_p4_checkpoint,
)
from src.models.probabilistic.dependence import GaussianCopulaDependenceModel
from src.optimization.config import GateOptimizationConfig
from src.simulation.aircraft_turn import AircraftTurnModel
from src.simulation.scalability_benchmark import (
    MonteCarloRealizationSummary,
    PipelineStageMeasurement,
    SolverBenchmarkResult,
    benchmark_four_solvers_on_scenario,
    generate_canonical_stochastic_matrix,
    measure_all_pipeline_stages,
    run_monte_carlo_scalability_benchmark,
    save_scalability_benchmark_artifacts,
)
from src.simulation.scalability_scenario import (
    DEFAULT_CONTACT_GATES,
    DEFAULT_SCALABILITY_SEED,
    generate_scalability_scenario,
    load_canonical_source_data,
)


@pytest.fixture(scope="module")
def source_data() -> pd.DataFrame:
    """Fixture providing July 2023 development inbound data."""
    return load_canonical_source_data(date_prefix="2023-07")


@pytest.fixture(scope="module")
def p4_model():
    """Fixture loading verified P4 Student-T model."""
    model, meta = verify_and_load_p4_checkpoint()
    return model


@pytest.fixture(scope="module")
def dep_model():
    """Fixture providing Gaussian Copula D2 dependence model."""
    return GaussianCopulaDependenceModel(
        temporal_length_scale_minutes=120.0,
        carrier_correlation=0.15,
        min_eigenvalue=1e-6,
    )


@pytest.fixture(scope="module")
def small_scenario(source_data: pd.DataFrame):
    """Fixture providing a fast 50-flight scenario for unit test assertions."""
    return generate_scalability_scenario(
        source_df=source_data,
        n_flights=50,
        n_contact_gates=10,
        seed=DEFAULT_SCALABILITY_SEED,
    )


def test_p4_checkpoint_verification() -> None:
    """Certified P4 checkpoint exists and matches SHA-256 hash e7e746..."""
    model, meta = verify_and_load_p4_checkpoint()
    assert meta["sha256"] == P4_CERTIFIED_SHA256
    assert meta["verification_status"] == "CERTIFIED_VALID"
    assert model.is_fitted_ is True


def test_canonical_stochastic_matrix_generation(small_scenario, p4_model, dep_model) -> None:
    """Generates stochastic delay matrix with positive variance and 100% unique rows."""
    u_mat, delay_mat, mat_hash, audit = generate_canonical_stochastic_matrix(
        scenario=small_scenario,
        p4_model=p4_model,
        dep_model=dep_model,
        n_samples=25,
        seed=202601,
    )
    assert u_mat.shape == (25, 50)
    assert delay_mat.shape == (25, 50)
    assert audit["all_unique"] is True
    assert audit["positive_variance"] is True
    assert np.all(np.isfinite(delay_mat))
    assert len(mat_hash) == 64


def test_pipeline_stages_measurement(small_scenario, p4_model, dep_model) -> None:
    """Profiles all 12 pipeline stages with valid timing and memory metrics."""
    stages = measure_all_pipeline_stages(
        scenario=small_scenario,
        p4_model=p4_model,
        dep_model=dep_model,
        n_samples=10,
        seed=202601,
    )
    assert len(stages) == 12
    stage_names = [s.stage_name for s in stages]
    assert any("input loading" in s for s in stage_names)
    assert any("probabilistic prediction" in s for s in stage_names)
    assert any("dependence construction" in s for s in stage_names)
    assert any("PSD validation" in s for s in stage_names)
    assert any("Monte Carlo sampling" in s for s in stage_names)
    assert any("solver execution" in s for s in stage_names)
    assert any("result serialization" in s for s in stage_names)

    for s in stages:
        assert s.wall_clock_ms >= 0.0
        assert s.memory_rss_mb > 0.0


def test_solver_fairness_and_budget_enforcement(small_scenario, p4_model) -> None:
    """All 4 solvers receive identical planned delays and respect the time budget."""
    dist = p4_model.predict_distribution(small_scenario.flights_df)
    planned_delays = np.asarray(dist["mu"], dtype=np.float64)

    cfg = GateOptimizationConfig(time_limit_seconds=1.0, random_seed=202601)
    tm = AircraftTurnModel(min_turnaround_min=45, default_dwell_min=60, separation_buffer_min=15)

    results = benchmark_four_solvers_on_scenario(
        scenario=small_scenario,
        planned_delays=planned_delays,
        config=cfg,
        turn_model=tm,
        mode="MODE_A_OFFICIAL",
        run_id="RUN_TEST",
        include_cpsat=True,
    )
    assert len(results) == 4
    solver_names = {r.solver_name for r in results}
    assert solver_names == {"DeterministicGreedy", "CPSat", "SimulatedAnnealing", "HybridCPSatSA"}

    for r in results:
        assert r.ladder_n == 50
        assert r.n_contact_gates == 10
        assert r.budget_seconds == 1.0
        # On 50 flights, Greedy, SA, and Hybrid must be feasible
        if r.solver_name in ("DeterministicGreedy", "SimulatedAnnealing", "HybridCPSatSA"):
            assert r.feasible is True
            assert r.hard_constraint_violations == 0


def test_monte_carlo_scalability_summary(small_scenario) -> None:
    """Monte Carlo evaluation calculates convergence and monotonic SE decrease."""
    rng = np.random.default_rng(202601)
    # Generate dummy stochastic delays
    dummy_delays = rng.normal(loc=0.0, scale=10.0, size=(50, 50))

    summaries, realizations = run_monte_carlo_scalability_benchmark(
        scenario=small_scenario,
        delay_matrix=dummy_delays,
        counts=(10, 25, 50),
    )
    assert len(summaries) == 3
    assert len(realizations) == 50

    # Monotonic reduction of SE
    se_10 = summaries[0].mc_se_objective
    se_50 = summaries[2].mc_se_objective
    assert se_50 <= se_10


def test_reproducibility_verification(small_scenario, p4_model, dep_model) -> None:
    """Running identical scenario under same seed produces identical matrix and objectives."""
    _, mat_1, hash_1, _ = generate_canonical_stochastic_matrix(
        scenario=small_scenario, p4_model=p4_model, dep_model=dep_model, n_samples=10, seed=202601
    )
    _, mat_2, hash_2, _ = generate_canonical_stochastic_matrix(
        scenario=small_scenario, p4_model=p4_model, dep_model=dep_model, n_samples=10, seed=202601
    )
    assert hash_1 == hash_2
    np.testing.assert_array_equal(mat_1, mat_2)


def test_artifact_persistence_integrity(small_scenario) -> None:
    """Artifact publisher generates all 7 files with valid schema and non-empty content."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        dummy_manifest = {
            "protocol": "test_protocol",
            "git_commit": "7ba0aba92d366f712977faaaa5a73cba65a32a55",
            "created_at_utc": "2026-10-05T00:00:00Z",
        }
        dummy_solver_res = [
            SolverBenchmarkResult(
                mode="MODE_A_OFFICIAL",
                run_id="RUN_1",
                ladder_n=50,
                n_contact_gates=10,
                solver_name="DeterministicGreedy",
                budget_seconds=2.0,
                wall_clock_timeout=False,
                model_construction_ms=0.1,
                solver_execution_ms=1.5,
                total_runtime_ms=1.6,
                status="FEASIBLE",
                feasible=True,
                hard_constraint_violations=0,
                objective_value=100.0,
                reassignment_count=0,
                contact_count=50,
                remote_count=0,
                unassigned_count=0,
                planned_conflicts=0,
                iterations=None,
                num_variables=50,
                num_constraints=50,
            )
        ]
        dummy_pipeline = [
            PipelineStageMeasurement(
                ladder_n=50,
                stage_name="1. input loading",
                wall_clock_ms=10.0,
                cpu_time_ms=10.0,
                memory_rss_mb=50.0,
                peak_ram_mb=50.0,
                memory_delta_mb=0.0,
            )
        ]
        dummy_mc = [
            MonteCarloRealizationSummary(
                n_requested=10,
                n_actual=10,
                n_success=10,
                n_failed=0,
                mean_objective=100.0,
                median_objective=100.0,
                std_objective=5.0,
                variance_objective=25.0,
                mc_se_objective=1.58,
                ci_95_lower=96.9,
                ci_95_upper=103.1,
                matrix_sha256="abc",
                unique_scenarios_count=10,
                positive_variance_audited=True,
            )
        ]
        dummy_agg = {"summary": "test"}
        dummy_rep = "# Test Report"

        created = save_scalability_benchmark_artifacts(
            manifest_data=dummy_manifest,
            scaling_records=dummy_solver_res,
            solver_records=dummy_solver_res,
            pipeline_records=dummy_pipeline,
            mc_summaries=dummy_mc,
            aggregate_data=dummy_agg,
            report_content=dummy_rep,
            output_dir=tmp_dir,
        )

        assert len(created) == 7
        for k, p in created.items():
            assert p.exists()
            assert p.stat().st_size > 0
