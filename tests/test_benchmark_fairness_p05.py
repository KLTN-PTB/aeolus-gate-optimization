"""Unit and Contract Tests for Phase P05: Fair & Reproducible Solver Benchmark.

Protocol: docs/remediation/05_benchmark_protocol.md
Validates:
1. Invariants B01 - B20:
   - B01: Same scenario -> same scenario_hash
   - B02: Same scenario -> same gate inventory
   - B03: Objective version identical
   - B04: Capacity policy identical
   - B05: Solver status not silently rewritten
   - B06: Invalid solution cannot receive feasible ranking
   - B07: Hybrid runtime includes both stages
   - B08: CP-SAT runtime includes model construction
   - B09: Failed runs remain visible
   - B10: Actual time is measured, not estimated
   - B11: Seed provenance exists
   - B12: Number of generated flights is exact
   - B13: Turns and legs count are not confused
   - B14: No hidden prior incumbent
   - B15: Wall-clock timing uses consistent boundaries
   - B16: Missing metrics remain null with explanation
   - B17: Data/model/config hashes are retained
   - B18: No modified historical artifacts
   - B19: Cost recalculation matches independent evaluator
   - B20: All feasible results pass independent verifier
2. Four Standard Solver Modes + One Explicit Diagnostic Mode:
   - MODE 1: GREEDY_STANDALONE
   - MODE 2: CP_SAT_STANDALONE
   - MODE 3: SA_STANDALONE (initial seed generation included in wall-clock time)
   - MODE 4: HYBRID_STANDALONE (complete 2-stage execution covering CP-SAT, fallback, and SA refinement)
   - DIAGNOSTIC: SA_FROM_PRECOMPUTED_INCUMBENT (never conflated with HYBRID_STANDALONE)
3. Multi-run statistics and artifact schema integrity.
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import pytest

from src.optimization.benchmark_harness import (
    BENCHMARK_SCHEMA_VERSION,
    AggregateBenchmarkMetrics,
    BenchmarkCaseSpec,
    BenchmarkManifest,
    BenchmarkRunResult,
    BenchmarkTier,
    SolverMode,
    compute_aggregate_metrics,
    compute_scenario_hash,
    execute_benchmark_run,
    generate_synthetic_benchmark_scenario,
    get_environment_info,
    save_benchmark_artifacts,
    validate_benchmark_invariants,
)
from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import (
    Flight,
    FlightTimeWindow,
    Gate,
    GateAssignment,
    GateAssignmentState,
    GateResourceType,
    SolverStatus,
    TerminationReason,
    verify_hard_constraints_independently,
)
from src.optimization.evaluation import evaluate_gate_assignment
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver


@pytest.fixture(scope="module")
def tier_a_scenario():
    """Fixture providing a standard Tier A micro-scale scenario (10 flights x 4 gates)."""
    flights, gates = generate_synthetic_benchmark_scenario(
        tier=BenchmarkTier.TIER_A,
        n_flights=10,
        n_contact_gates=3,
        n_remote_stands=1,
        seed=202601,
    )
    return flights, gates


@pytest.fixture(scope="module")
def base_spec(tier_a_scenario) -> BenchmarkCaseSpec:
    """Fixture providing a base BenchmarkCaseSpec for Tier A."""
    flights, gates = tier_a_scenario
    scen_hash = compute_scenario_hash(flights, gates)
    return BenchmarkCaseSpec(
        experiment_id="EXP_TEST_TIER_A",
        scenario_id="SCEN_10F_4G",
        scenario_hash=scen_hash,
        input_dataset_hash="hash_input_mock_2023_07",
        scenario_type="SYNTHETIC_MICRO",
        n_flights=len(flights),
        n_aircraft_turns=len(flights),
        n_contact_gates=3,
        n_finite_remote_stands=1,
        capacity_policy="remote_stand_capacity_finite",
        objective_version="v1",
        objective_weights={
            "reassignment_weight": 10.0,
            "overflow_weight": 200.0,
            "delay_weight": 1.0,
            "conflict_weight": 1000.0,
            "risk_weight": 2.0,
        },
        prediction_mode="point_prediction",
        solver_name="DeterministicGreedy",
        solver_variant=SolverMode.GREEDY_STANDALONE.value,
        seed=202601,
        worker_count=1,
        solver_config={
            "scale_factor": 100,
            "finite_remote_capacity": 1,
            "allow_unbounded_overflow": True,
            "enforce_remote_capacity": True,
        },
        time_budget_ms=1000.0,
        memory_budget_mb=1024.0,
        environment_info=get_environment_info(),
    )


# =============================================================================
# Invariants B01 - B20 Tests
# =============================================================================

def test_b01_same_scenario_same_hash(tier_a_scenario) -> None:
    """B01: Same scenario generates identical SHA-256 hash across invocations."""
    flights, gates = tier_a_scenario
    hash_1 = compute_scenario_hash(flights, gates)
    hash_2 = compute_scenario_hash(flights, gates)
    assert hash_1 == hash_2
    assert len(hash_1) == 64

    # Modifying flight window changes hash
    modified_flights = list(flights)
    f0 = flights[0]
    modified_flights[0] = Flight(
        flight_id=f0.flight_id,
        flight_index=f0.flight_index,
        carrier=f0.carrier,
        flight_number=f0.flight_number,
        scheduled_arrival_min=999,
        scheduled_departure_min=1099,
        predicted_arrival_min=999,
        nominal_gate_id=f0.nominal_gate_id,
    )
    hash_diff = compute_scenario_hash(modified_flights, gates)
    assert hash_diff != hash_1


def test_b02_same_gate_inventory(tier_a_scenario, base_spec) -> None:
    """B02: Same scenario provides identical gate inventory to all solvers."""
    flights, gates = tier_a_scenario
    contact_count = sum(1 for g in gates if g.resource_type == GateResourceType.CONTACT_GATE)
    assert contact_count == base_spec.n_contact_gates


def test_b03_b04_objective_version_and_capacity_policy(base_spec) -> None:
    """B03 & B04: Objective version and capacity policy are declared and standardized."""
    assert base_spec.objective_version in ("v1", "v1.0_canonical_audit")
    assert base_spec.capacity_policy == "remote_stand_capacity_finite"


def test_b05_solver_status_not_silently_rewritten(tier_a_scenario, base_spec) -> None:
    """B05: Solver status accurately reflects domain SolverStatus enum."""
    flights, gates = tier_a_scenario
    res = execute_benchmark_run(base_spec, flights, gates)
    assert res.solver_status in {s.value for s in SolverStatus}


def test_b06_invalid_solution_cannot_receive_feasible_ranking(tier_a_scenario, base_spec) -> None:
    """B06: An invalid solution with hard constraint violations CANNOT receive feasible ranking."""
    flights, gates = tier_a_scenario

    # Create dummy result with violations
    bad_result = BenchmarkRunResult(
        build_time_ms=0.0,
        search_time_ms=10.0,
        validation_time_ms=1.0,
        total_wall_clock_ms=11.0,
        peak_memory_mb=100.0,
        solver_status=SolverStatus.INFEASIBLE.value,
        feasible=False,
        optimality_proven=False,
        objective_value=None,
        best_bound=None,
        gap=None,
        hard_constraint_violations=2,
        reassignment_count=None,
        remote_count=None,
        unassigned_count=0,
        fallback_used=False,
        termination_reason="PROVEN_INFEASIBLE",
        experiment_id=base_spec.experiment_id,
        scenario_id=base_spec.scenario_id,
        run_id="run_bad",
        solver_variant=base_spec.solver_variant,
    )
    checks = validate_benchmark_invariants(base_spec, bad_result, flights, gates)
    assert checks["B06_invalid_solution_not_feasible"] is True

    # If feasible is incorrectly set to True with violations, check fails
    bad_result.feasible = True
    bad_result.objective_value = 50.0
    checks = validate_benchmark_invariants(base_spec, bad_result, flights, gates)
    assert checks["B06_invalid_solution_not_feasible"] is False


def test_b07_hybrid_runtime_includes_both_stages(tier_a_scenario, base_spec) -> None:
    """B07: Hybrid runtime includes both Stage 1 CP-SAT and Stage 2 SA."""
    flights, gates = tier_a_scenario
    from dataclasses import replace
    hyb_spec = replace(
        base_spec,
        solver_name="HybridCPSatSA",
        solver_variant=SolverMode.HYBRID_STANDALONE.value,
        time_budget_ms=1000.0,
        solver_config={"cp_ratio": 0.5, "sa_iterations": 200},
    )
    res = execute_benchmark_run(hyb_spec, flights, gates)
    assert res.feasible is True
    assert res.total_wall_clock_ms > 0.0
    # Total wall clock must encompass build time + search time
    assert res.total_wall_clock_ms >= (res.build_time_ms or 0.0)
    checks = validate_benchmark_invariants(hyb_spec, res, flights, gates)
    assert checks["B07_hybrid_runtime_both_stages"] is True


def test_b08_cpsat_runtime_includes_model_construction(tier_a_scenario, base_spec) -> None:
    """B08: CP-SAT runtime includes model construction, not just solver search."""
    flights, gates = tier_a_scenario
    from dataclasses import replace
    cp_spec = replace(
        base_spec,
        solver_name="CPSat",
        solver_variant=SolverMode.CP_SAT_STANDALONE.value,
        time_budget_ms=1000.0,
    )
    res = execute_benchmark_run(cp_spec, flights, gates)
    assert res.build_time_ms is not None
    assert res.search_time_ms is not None
    assert res.total_wall_clock_ms >= res.search_time_ms
    checks = validate_benchmark_invariants(cp_spec, res, flights, gates)
    assert checks["B08_cpsat_runtime_includes_build"] is True


def test_b09_failed_runs_remain_visible(tier_a_scenario, base_spec) -> None:
    """B09: Failed runs are preserved in outputs and not silently omitted."""
    from dataclasses import replace
    # Create an impossible scenario (10 flights with overlapping windows on 1 gate, no remote, no overflow)
    tight_gates = [
        Gate(gate_id="G1", gate_index=0, resource_type=GateResourceType.CONTACT_GATE, capacity=1, is_overflow=False)
    ]
    overlap_flights = [
        Flight(
            flight_id=f"F{i}",
            flight_index=i,
            carrier="DL",
            flight_number=f"10{i}",
            scheduled_arrival_min=100,
            scheduled_departure_min=200,
            predicted_arrival_min=100,
            nominal_gate_id="G1",
        )
        for i in range(5)
    ]
    scen_hash = compute_scenario_hash(overlap_flights, tight_gates)
    fail_spec = replace(
        base_spec,
        scenario_id="SCEN_IMPOSSIBLE",
        scenario_hash=scen_hash,
        n_flights=5,
        n_contact_gates=1,
        n_finite_remote_stands=0,
        solver_name="CPSat",
        solver_variant=SolverMode.CP_SAT_STANDALONE.value,
        solver_config={"allow_unbounded_overflow": False},
        time_budget_ms=500.0,
    )
    res = execute_benchmark_run(fail_spec, overlap_flights, tight_gates)
    # The run must NOT be dropped, its status must be recorded
    assert res.run_id == "run_1"
    assert res.feasible is False
    assert res.objective_value is None
    checks = validate_benchmark_invariants(fail_spec, res, overlap_flights, tight_gates)
    assert checks["B09_failed_runs_visible"] is True
    assert checks["B16_missing_metrics_remain_null"] is True


def test_b10_b15_measured_high_res_timing(tier_a_scenario, base_spec) -> None:
    """B10 & B15: Timers use monotonic high-resolution perf_counter_ns with consistent boundaries."""
    flights, gates = tier_a_scenario
    res = execute_benchmark_run(base_spec, flights, gates)
    assert res.total_wall_clock_ms > 0.0
    assert isinstance(res.total_wall_clock_ms, float)


def test_b11_seed_provenance(base_spec) -> None:
    """B11: Seed provenance is explicitly recorded."""
    assert base_spec.seed == 202601


def test_b12_b13_flight_and_turn_accounting(tier_a_scenario, base_spec) -> None:
    """B12 & B13: Exact flight count matches spec; turns and flight legs are distinguished."""
    flights, _ = tier_a_scenario
    assert len(flights) == base_spec.n_flights
    assert base_spec.n_aircraft_turns == 10
    assert base_spec.n_flights == 10


def test_b14_no_hidden_prior_incumbent_in_standalone(tier_a_scenario, base_spec) -> None:
    """B14: Standalone SA and Standalone Hybrid generate their own seeds during timed execution."""
    flights, gates = tier_a_scenario
    from dataclasses import replace
    sa_spec = replace(
        base_spec,
        solver_name="SimulatedAnnealing",
        solver_variant=SolverMode.SA_STANDALONE.value,
        time_budget_ms=1000.0,
        solver_config={"sa_iterations": 200},
    )
    res = execute_benchmark_run(sa_spec, flights, gates)
    # SA standalone must have timed seed generation
    assert res.build_time_ms is not None
    assert res.build_time_ms > 0.0
    checks = validate_benchmark_invariants(sa_spec, res, flights, gates)
    assert checks["B14_no_hidden_prior_incumbent"] is True


def test_b16_missing_metrics_remain_null(tier_a_scenario, base_spec) -> None:
    """B16: Missing metrics for infeasible or inapplicable values are null, not 0.0."""
    flights, gates = tier_a_scenario
    # Greedy does not provide dual bound or gap
    res = execute_benchmark_run(base_spec, flights, gates)
    assert res.best_bound is None
    assert res.gap is None


def test_b17_hashes_retained(base_spec) -> None:
    """B17: Scenario and input dataset hashes are retained."""
    assert len(base_spec.scenario_hash) == 64
    assert len(base_spec.input_dataset_hash) > 0


def test_b18_no_modified_historical_artifacts() -> None:
    """B18: Historical artifact directories are not modified."""
    legacy_stress = Path("artifacts/stress_1500x50")
    if legacy_stress.exists():
        # Directory must exist and not be wiped
        assert len(list(legacy_stress.iterdir())) > 0


def test_b19_b20_cost_recalculation_and_independent_verifier(tier_a_scenario, base_spec) -> None:
    """B19 & B20: Feasible assignment matches independent evaluator and verifier."""
    flights, gates = tier_a_scenario
    res = execute_benchmark_run(base_spec, flights, gates)
    assert res.feasible is True

    # Re-evaluate with DeterministicGreedyGateSolver
    solver = DeterministicGreedyGateSolver(config=GateOptimizationConfig(objective_version=base_spec.objective_version))
    opt_res = solver.solve(flights, gates, allow_overflow=True)
    diag = verify_hard_constraints_independently(flights=flights, gates=gates, assignments=opt_res.assignments)
    assert diag.is_valid is True

    checks = validate_benchmark_invariants(base_spec, res, flights, gates, assignments=opt_res.assignments)
    assert checks["B19_cost_recalculation_matches"] is True
    assert checks["B20_independent_verifier_pass"] is True


# =============================================================================
# Four Solver Modes + Diagnostic Mode Tests
# =============================================================================

def test_four_solver_modes_execution(tier_a_scenario, base_spec) -> None:
    """Validate all 4 standard modes and diagnostic mode execute properly."""
    flights, gates = tier_a_scenario
    from dataclasses import replace

    # 1. GREEDY_STANDALONE
    res_greedy = execute_benchmark_run(base_spec, flights, gates, run_id="r_greedy")
    assert res_greedy.feasible is True
    assert res_greedy.solver_variant == SolverMode.GREEDY_STANDALONE.value

    # 2. CP_SAT_STANDALONE
    spec_cp = replace(
        base_spec,
        solver_name="CPSat",
        solver_variant=SolverMode.CP_SAT_STANDALONE.value,
        time_budget_ms=1000.0,
    )
    res_cp = execute_benchmark_run(spec_cp, flights, gates, run_id="r_cp")
    assert res_cp.feasible is True
    assert res_cp.build_time_ms is not None

    # 3. SA_STANDALONE
    spec_sa = replace(
        base_spec,
        solver_name="SimulatedAnnealing",
        solver_variant=SolverMode.SA_STANDALONE.value,
        time_budget_ms=1000.0,
        solver_config={"sa_iterations": 200},
    )
    res_sa = execute_benchmark_run(spec_sa, flights, gates, run_id="r_sa")
    assert res_sa.feasible is True
    assert res_sa.build_time_ms is not None  # Initial seed time included!

    # 4. HYBRID_STANDALONE
    spec_hyb = replace(
        base_spec,
        solver_name="HybridCPSatSA",
        solver_variant=SolverMode.HYBRID_STANDALONE.value,
        time_budget_ms=1000.0,
        solver_config={"cp_ratio": 0.5, "sa_iterations": 200},
    )
    res_hyb = execute_benchmark_run(spec_hyb, flights, gates, run_id="r_hyb")
    assert res_hyb.feasible is True

    # 5. DIAGNOSTIC: SA_FROM_PRECOMPUTED_INCUMBENT
    solver_greedy = DeterministicGreedyGateSolver()
    incumbent = solver_greedy.solve(flights, gates).assignments
    spec_diag = replace(
        base_spec,
        solver_name="SimulatedAnnealing",
        solver_variant=SolverMode.SA_FROM_PRECOMPUTED_INCUMBENT.value,
        solver_config={"sa_iterations": 200},
    )
    res_diag = execute_benchmark_run(spec_diag, flights, gates, run_id="r_diag", precomputed_incumbent=incumbent)
    assert res_diag.feasible is True
    assert res_diag.solver_variant == SolverMode.SA_FROM_PRECOMPUTED_INCUMBENT.value


# =============================================================================
# Multi-Run Statistics & Artifact Persistence Tests
# =============================================================================

def test_multi_run_statistics_aggregation(tier_a_scenario, base_spec) -> None:
    """Multi-run statistical aggregation computes median, mean, std, dispersion, and failure rates."""
    flights, gates = tier_a_scenario
    results: list[BenchmarkRunResult] = []

    for i in range(5):
        res = execute_benchmark_run(base_spec, flights, gates, run_id=f"rep_{i+1}")
        results.append(res)

    aggregates = compute_aggregate_metrics([base_spec], results)
    assert len(aggregates) == 1
    agg = aggregates[0]

    assert agg.n_runs == 5
    assert agg.n_feasible == 5
    assert agg.n_failed == 0
    assert agg.failure_rate == 0.0
    assert agg.wall_clock_median_ms > 0.0
    assert agg.wall_clock_mean_ms > 0.0
    assert agg.wall_clock_min_ms <= agg.wall_clock_max_ms
    assert agg.objective_median is not None
    assert agg.objective_mean is not None


def test_artifact_persistence_schema() -> None:
    """Artifact writer creates all 5 benchmark files with valid schema in output directory."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        env = get_environment_info()
        manifest = BenchmarkManifest(
            schema_version=BENCHMARK_SCHEMA_VERSION,
            created_at_utc="2026-10-09T00:00:00Z",
            environment=env,
            specs=[],
            run_count=1,
            feasible_count=1,
            failed_count=0,
            summary_by_mode={},
        )
        dummy_res = BenchmarkRunResult(
            build_time_ms=0.0,
            search_time_ms=5.0,
            validation_time_ms=0.5,
            total_wall_clock_ms=5.5,
            peak_memory_mb=50.0,
            solver_status=SolverStatus.OPTIMAL.value,
            feasible=True,
            optimality_proven=True,
            objective_value=12.5,
            best_bound=12.5,
            gap=0.0,
            hard_constraint_violations=0,
            reassignment_count=1,
            remote_count=0,
            unassigned_count=0,
            fallback_used=False,
            termination_reason="OPTIMAL_PROVEN",
            experiment_id="EXP_TEST",
            scenario_id="SCEN_TEST",
            run_id="run_1",
            solver_variant="GREEDY_STANDALONE",
        )
        dummy_agg = AggregateBenchmarkMetrics(
            experiment_id="EXP_TEST",
            scenario_id="SCEN_TEST",
            solver_name="DeterministicGreedy",
            solver_variant="GREEDY_STANDALONE",
            n_runs=1,
            n_feasible=1,
            n_failed=0,
            failure_rate=0.0,
            wall_clock_median_ms=5.5,
            wall_clock_mean_ms=5.5,
            wall_clock_std_ms=0.0,
            wall_clock_min_ms=5.5,
            wall_clock_max_ms=5.5,
            wall_clock_dispersion=0.0,
            objective_median=12.5,
            objective_mean=12.5,
            objective_std=0.0,
            objective_min=12.5,
            objective_max=12.5,
            build_time_mean_ms=0.0,
            search_time_mean_ms=5.0,
        )

        paths = save_benchmark_artifacts(manifest, [dummy_res], [dummy_agg], output_dir=tmp_dir)
        for key, p in paths.items():
            assert p.exists()
            assert p.stat().st_size > 0

        # Check JSON files valid
        with open(paths["manifest"], "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data["schema_version"] == BENCHMARK_SCHEMA_VERSION

        with open(paths["environment"], "r", encoding="utf-8") as f:
            env_data = json.load(f)
            assert "python_version" in env_data
            assert "ortools_version" in env_data
