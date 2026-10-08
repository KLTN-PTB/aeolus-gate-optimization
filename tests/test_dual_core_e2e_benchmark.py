"""Tests for End-to-End Dual Core Benchmark and Scalability Evaluation Engine.

Phase: P9 End-to-End Dual Core Validation, Fair Benchmark & Scalability
Protocol: Aeolus Dual Core Architecture Protocol V2
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
import yaml

from src.evaluation.dual_core_benchmark import (
    BenchmarkBranch,
    DEFAULT_SCHEDULE_CSV,
    SolverExecutionMetrics,
    TurnDataBundle,
    evaluate_solver_on_bundle,
    generate_contact_gates,
    get_process_metrics,
    load_and_build_branch_turns,
)
from src.simulation.dual_prediction_turn import CouplingAssumption


class TestBenchmarkGatesAndMetrics:
    """Test gate generation and system process metrics."""

    def test_generate_contact_gates_basic(self) -> None:
        gates = generate_contact_gates(10, allow_overflow=False)
        assert len(gates) == 10
        assert all(not g.is_overflow for g in gates)
        assert gates[0].gate_id == "G01"
        assert gates[-1].gate_id == "G10"

    def test_generate_contact_gates_with_default_overflow(self) -> None:
        gates = generate_contact_gates(10, allow_overflow=True)
        assert len(gates) == 11
        assert sum(1 for g in gates if not g.is_overflow) == 10
        assert sum(1 for g in gates if g.is_overflow) == 1
        assert gates[-1].gate_id == "OVERFLOW_APRON"

    def test_generate_contact_gates_with_finite_overflow(self) -> None:
        gates = generate_contact_gates(5, allow_overflow=True, max_overflow=5)
        assert len(gates) == 10  # 5 contact + 5 overflow stands
        overflow_stands = [g for g in gates if g.is_overflow]
        assert len(overflow_stands) == 5
        assert overflow_stands[0].gate_id == "OVERFLOW_STAND_01"
        assert overflow_stands[-1].gate_id == "OVERFLOW_STAND_05"

    def test_process_metrics(self) -> None:
        rss, cpu_t = get_process_metrics()
        assert rss > 0.0
        assert cpu_t >= 0.0


class TestBranchTurnsBuilder:
    """Test turn data bundle construction across all four branches."""

    @pytest.mark.skipif(not DEFAULT_SCHEDULE_CSV.exists(), reason="Schedule CSV missing")
    def test_load_and_build_all_branches(self) -> None:
        branches = [
            BenchmarkBranch.SCHEDULE_ONLY,
            BenchmarkBranch.ARRIVAL_P4_ONLY_LEGACY,
            BenchmarkBranch.DUAL_POINT,
            BenchmarkBranch.DUAL_PROBABILISTIC,
        ]
        for branch in branches:
            bundle = load_and_build_branch_turns(
                csv_path=DEFAULT_SCHEDULE_CSV,
                branch=branch,
                max_turns=20,
                n_contact_gates=5,
            )
            assert isinstance(bundle, TurnDataBundle)
            assert bundle.branch == branch
            assert len(bundle.turns) == 20
            assert len(bundle.planned_flights) == 20
            assert len(bundle.realized_flights) == 20
            assert len(bundle.gates) == 6  # 5 contact + 1 overflow

    @pytest.mark.skipif(not DEFAULT_SCHEDULE_CSV.exists(), reason="Schedule CSV missing")
    def test_coupling_assumptions_for_probabilistic(self) -> None:
        couplings = [
            CouplingAssumption.INDEPENDENT,
            CouplingAssumption.COMONOTONIC,
            CouplingAssumption.COUNTERMONOTONIC,
        ]
        for c in couplings:
            bundle = load_and_build_branch_turns(
                csv_path=DEFAULT_SCHEDULE_CSV,
                branch=BenchmarkBranch.DUAL_PROBABILISTIC,
                coupling_assumption=c,
                max_turns=15,
                n_contact_gates=5,
            )
            assert len(bundle.planned_flights) == 15
            assert bundle.planned_flights[0].precomputed_gate_out_min is not None


class TestSolverEvaluationEngine:
    """Test multi-solver evaluation on turn data bundles."""

    @pytest.fixture
    def small_bundle(self) -> TurnDataBundle:
        return load_and_build_branch_turns(
            csv_path=DEFAULT_SCHEDULE_CSV,
            branch=BenchmarkBranch.DUAL_POINT,
            max_turns=25,
            n_contact_gates=5,
            allow_overflow=True,
        )

    def test_evaluate_deterministic_greedy(self, small_bundle: TurnDataBundle) -> None:
        metrics = evaluate_solver_on_bundle(
            solver_name="DeterministicGreedy",
            bundle=small_bundle,
            time_limit_seconds=2.0,
        )
        assert isinstance(metrics, SolverExecutionMetrics)
        assert metrics.solver_name == "DeterministicGreedy"
        assert metrics.feasible is True
        assert metrics.planned_hard_violations == 0
        assert metrics.independent_audit_valid is True
        assert metrics.contact_assignments + metrics.remote_assignments == 25
        assert metrics.unassigned_turns == 0
        assert metrics.total_runtime_ms > 0.0

        d = metrics.to_dict()
        assert d["branch"] == "DUAL_POINT"
        assert "realized_post_hoc_conflicts" in d

    def test_evaluate_cp_sat_solver(self, small_bundle: TurnDataBundle) -> None:
        metrics = evaluate_solver_on_bundle(
            solver_name="CPSat",
            bundle=small_bundle,
            time_limit_seconds=3.0,
        )
        assert isinstance(metrics, SolverExecutionMetrics)
        assert metrics.solver_name == "CPSat"
        assert metrics.feasible is True
        assert metrics.planned_hard_violations == 0
        assert metrics.independent_audit_valid is True
        assert metrics.contact_assignments + metrics.remote_assignments == 25

    def test_evaluate_simulated_annealing(self, small_bundle: TurnDataBundle) -> None:
        metrics = evaluate_solver_on_bundle(
            solver_name="SimulatedAnnealing",
            bundle=small_bundle,
            time_limit_seconds=2.0,
            sa_iterations=100,
        )
        assert isinstance(metrics, SolverExecutionMetrics)
        assert metrics.solver_name == "SimulatedAnnealing"
        assert metrics.feasible is True
        assert metrics.planned_hard_violations == 0
        assert metrics.independent_audit_valid is True
        assert metrics.iterations == 100

    def test_evaluate_hybrid_solver(self, small_bundle: TurnDataBundle) -> None:
        metrics = evaluate_solver_on_bundle(
            solver_name="HybridCPSatSA",
            bundle=small_bundle,
            time_limit_seconds=3.0,
            sa_iterations=100,
        )
        assert isinstance(metrics, SolverExecutionMetrics)
        assert metrics.solver_name == "HybridCPSatSA"
        assert metrics.feasible is True
        assert metrics.planned_hard_violations == 0
        assert metrics.independent_audit_valid is True


class TestBenchmarkArtifactsIntegrity:
    """Verify that all pre-registered Phase P9 artifacts and docs exist and are valid."""

    def test_config_dual_core_benchmark_v1_exists(self) -> None:
        config_path = Path("configs/dual_core_benchmark_v1.yaml")
        assert config_path.exists(), "configs/dual_core_benchmark_v1.yaml must exist"
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        assert cfg["benchmark_protocol"] == "AEOLUS_DUAL_CORE_E2E_BENCHMARK_V1"
        assert "hypotheses" in cfg
        assert "H1_forecast_accuracy" in cfg["hypotheses"]
        assert "H2_conflict_reduction" in cfg["hypotheses"]
        assert "branches" in cfg

    def test_forecast_comparison_artifact_valid(self) -> None:
        p = Path("artifacts/dual_core/benchmarks/dual_core_forecast_comparison_v1.json")
        assert p.exists(), "Forecast comparison artifact must exist"
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["metadata"]["phase"] == "P9"
        assert "canonical_out_of_fold_point_benchmark_1_25M" in data
        assert "canonical_out_of_fold_probabilistic_benchmark_81K" in data
        assert "operational_schedule_fixture_1500_flights" in data

    def test_solver_comparison_artifact_valid(self) -> None:
        p = Path("artifacts/dual_core/benchmarks/dual_core_solver_comparison_v1.json")
        assert p.exists(), "Solver comparison artifact must exist"
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["metadata"]["phase"] == "P9"
        assert data["metadata"]["num_turns"] == 851
        assert "infinite_overflow" in data["scenarios"]
        assert "finite_overflow_max_5" in data["scenarios"]

    def test_scalability_artifact_valid(self) -> None:
        p = Path("artifacts/dual_core/benchmarks/dual_core_scalability_v1.json")
        assert p.exists(), "Scalability artifact must exist"
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["metadata"]["phase"] == "P9"
        assert data["metadata"]["total_benchmark_runs"] == 120
        assert len(data["scalability_records"]) == 120

    def test_e2e_benchmark_doc_exists(self) -> None:
        doc = Path("docs/dual_core/dual_core_e2e_benchmark_v1.md")
        assert doc.exists()
        content = doc.read_text(encoding="utf-8")
        assert "ENGINEERING_PASS" in content
        assert "SCIENTIFIC_EVIDENCE_PASS" in content
        assert "DEPLOYMENT_READY: DEFERRED_TO_P10" in content
        assert "H1" in content
        assert "H2" in content
        assert "H3" in content
        assert "H4" in content

    def test_robustness_doc_exists(self) -> None:
        doc = Path("docs/dual_core/dual_core_robustness_v1.md")
        assert doc.exists()
        content = doc.read_text(encoding="utf-8")
        assert "OPERATIONAL_ROBUSTNESS_CONFIRMED" in content
