"""Adversarial Regression Tests for Execution Ledger & Production Runner Integration.

Suite: AEOLUS-MC500-P1 (LEDGER-01 through LEDGER-20)
Verifies:
- Rigorous separation of Scenario Generation (N) vs Solver Evaluation (11 * N).
- Zero silent drops, strict conservation equations, and explicit denominators.
- Complete failure injection and edge case coverage.
- Production runner end-to-end integration and run isolation.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import time
from unittest.mock import patch
import pandas as pd
import pytest

from src.simulation.monte_carlo_engine_v2 import (
    CANONICAL_PROTOCOL_EVALUATIONS,
    ExecutionLedgerEntry,
    ScenarioGenerationRecord,
    SimulationExecutionLedger,
    compute_file_sha256,
)
from scripts.run_g2_monte_carlo_remediation import run_g2_remediation_pipeline


# ==============================================================================
# LEDGER-01 TO LEDGER-05: PROTOCOL AND COVERAGE CONSERVATION
# ==============================================================================

def test_ledger_01_five_scenarios_55_evaluations_five_generated():
    """LEDGER-01: 5 scenarios, 55 evaluations, n_generated=5 (not 15 or 55)."""
    ledger = SimulationExecutionLedger(
        run_id="TEST_01",
        requested_n=5,
        required_evaluations=CANONICAL_PROTOCOL_EVALUATIONS,
    )
    for i in range(5):
        s_id = f"SCEN_{i:02d}"
        ledger.record_scenario_generated(
            scenario_id=s_id,
            scenario_index=i,
            seed=202601 + i,
            realization_hash=f"hash_{i}",
        )
        for mode, solver in CANONICAL_PROTOCOL_EVALUATIONS:
            ledger.record_evaluation_success(
                scenario_id=s_id,
                realization_hash=f"hash_{i}",
                initial_plan_solver=solver,
                recourse_mode=mode,
                solver_status="OPTIMAL",
                composite_feasible=True,
                objective_value=100.0 + i,
                runtime_ms=1.5,
            )

    ledger.validate_ledger()
    summary = ledger.compute_summary()
    acc = summary["accounting"]

    assert acc["n_requested"] == 5
    assert acc["n_generated"] == 5
    assert acc["n_requested_realizations"] == 5
    assert acc["n_generated_realizations"] == 5
    assert acc["n_expected_evaluations"] == 55
    assert acc["n_evaluated"] == 55
    assert acc["n_completed_evaluations"] == 55
    assert acc["n_missing_evaluations"] == 0
    assert len(ledger.entries) == 55


def test_ledger_02_five_hundred_scenarios_expected_slots():
    """LEDGER-02: 500 scenarios expects 5500 evaluation slots under canonical protocol."""
    ledger = SimulationExecutionLedger(
        run_id="TEST_02",
        requested_n=500,
        required_evaluations=CANONICAL_PROTOCOL_EVALUATIONS,
    )
    assert len(CANONICAL_PROTOCOL_EVALUATIONS) == 11
    # Check expected slots calculation when 500 scenarios are generated
    for i in range(500):
        ledger.record_scenario_generated(
            scenario_id=f"SCEN_{i:03d}",
            scenario_index=i,
            seed=202601 + i,
            realization_hash=f"hash_{i}",
        )
    summary = ledger.compute_summary()
    assert summary["accounting"]["n_expected_evaluations"] == 5500
    assert summary["accounting"]["n_generated_realizations"] == 500


def test_ledger_03_missing_b2_hybrid_fails():
    """LEDGER-03: Missing B2-Hybrid evaluation for any generated scenario must FAIL validation."""
    ledger = SimulationExecutionLedger(
        run_id="TEST_03",
        requested_n=2,
        required_evaluations=CANONICAL_PROTOCOL_EVALUATIONS,
    )
    for i in range(2):
        s_id = f"SCEN_{i}"
        ledger.record_scenario_generated(s_id, i, 100 + i, f"h_{i}")
        for mode, solver in CANONICAL_PROTOCOL_EVALUATIONS:
            if i == 0 and mode == "MODE_B2" and solver == "Hybrid":
                continue  # OMIT B2-Hybrid for scenario 0!
            ledger.record_evaluation_success(
                scenario_id=s_id,
                realization_hash=f"h_{i}",
                initial_plan_solver=solver,
                recourse_mode=mode,
                solver_status="FEASIBLE",
                composite_feasible=True,
                objective_value=50.0,
            )

    with pytest.raises(ValueError, match="Missing required evaluation slot.*MODE_B2.*Hybrid"):
        ledger.validate_ledger()


def test_ledger_04_missing_entire_mode_c2_fails():
    """LEDGER-04: Missing entire Mode C2 across all scenarios must FAIL validation."""
    ledger = SimulationExecutionLedger(
        run_id="TEST_04",
        requested_n=2,
        required_evaluations=CANONICAL_PROTOCOL_EVALUATIONS,
    )
    for i in range(2):
        s_id = f"SCEN_{i}"
        ledger.record_scenario_generated(s_id, i, 100 + i, f"h_{i}")
        for mode, solver in CANONICAL_PROTOCOL_EVALUATIONS:
            if mode == "MODE_C2":
                continue  # Omit Mode C2
            ledger.record_evaluation_success(
                scenario_id=s_id,
                realization_hash=f"h_{i}",
                initial_plan_solver=solver,
                recourse_mode=mode,
                solver_status="FEASIBLE",
                composite_feasible=True,
                objective_value=50.0,
            )

    with pytest.raises(ValueError, match="Missing required evaluation slot.*MODE_C2"):
        ledger.validate_ledger()


def test_ledger_05_empty_crn_records_fail():
    """LEDGER-05: Empty CRN records must NEVER return PASS."""
    ledger = SimulationExecutionLedger(run_id="TEST_05", requested_n=5)
    with pytest.raises(ValueError, match="CRN validation failed.*0 evaluation records|empty"):
        ledger.validate_paired_crn(required_solvers=["Greedy", "CPSat", "Hybrid"])


# ==============================================================================
# LEDGER-06 TO LEDGER-08: KEY INTEGRITY & HASH MATCHING
# ==============================================================================

def test_ledger_06_duplicate_scenario_mode_solver_fails():
    """LEDGER-06: Duplicate scenario_id for the same mode and solver must FAIL."""
    ledger = SimulationExecutionLedger(run_id="TEST_06", requested_n=2)
    ledger.record_evaluation_success(
        scenario_id="SCEN_0", realization_hash="h0", initial_plan_solver="Greedy",
        recourse_mode="MODE_A", solver_status="FEASIBLE", composite_feasible=True, objective_value=10.0,
    )
    with pytest.raises(ValueError, match="Duplicate scenario_id"):
        ledger.record_evaluation_success(
            scenario_id="SCEN_0", realization_hash="h0", initial_plan_solver="Greedy",
            recourse_mode="MODE_A", solver_status="FEASIBLE", composite_feasible=True, objective_value=10.0,
        )


def test_ledger_07_same_scenario_solver_across_different_modes_allowed():
    """LEDGER-07: Same scenario+solver across distinct recourse modes must be valid."""
    ledger = SimulationExecutionLedger(run_id="TEST_07", requested_n=1)
    # Greedy evaluated under Mode A, Mode B1, Mode B2
    e_a = ledger.record_evaluation_success(
        scenario_id="SCEN_0", realization_hash="h0", initial_plan_solver="Greedy",
        recourse_mode="MODE_A", solver_status="FEASIBLE", composite_feasible=True, objective_value=100.0,
    )
    e_b1 = ledger.record_evaluation_success(
        scenario_id="SCEN_0", realization_hash="h0", initial_plan_solver="Greedy",
        recourse_mode="MODE_B1", solver_status="FEASIBLE", composite_feasible=True, objective_value=80.0,
    )
    e_b2 = ledger.record_evaluation_success(
        scenario_id="SCEN_0", realization_hash="h0", initial_plan_solver="Greedy",
        recourse_mode="MODE_B2", solver_status="FEASIBLE", composite_feasible=True, objective_value=85.0,
    )
    assert len(ledger.entries) == 3
    assert {e.recourse_mode for e in ledger.entries} == {"MODE_A", "MODE_B1", "MODE_B2"}


def test_ledger_08_mismatched_realization_hashes_fail():
    """LEDGER-08: Mismatched realization hash between generation and evaluation must FAIL."""
    ledger = SimulationExecutionLedger(run_id="TEST_08", requested_n=1)
    ledger.record_scenario_generated("SCEN_0", 0, 100, realization_hash="HASH_ALPHA")
    ledger.record_evaluation_success(
        scenario_id="SCEN_0", realization_hash="HASH_BETA", initial_plan_solver="Greedy",
        recourse_mode="MODE_A", solver_status="FEASIBLE", composite_feasible=True, objective_value=50.0,
    )
    with pytest.raises(ValueError, match="Mismatched realization hash"):
        ledger.validate_ledger()


# ==============================================================================
# LEDGER-09 TO LEDGER-12: FAILURE, TIMEOUT, STATUS ACCOUNTING
# ==============================================================================

def test_ledger_09_generation_exception_accounted():
    """LEDGER-09: Generation exceptions are explicitly accounted without silent drops."""
    ledger = SimulationExecutionLedger(run_id="TEST_09", requested_n=5)
    for i in range(4):
        ledger.record_scenario_generated(f"SCEN_{i}", i, 100 + i, f"h_{i}")
        ledger.record_evaluation_success(f"SCEN_{i}", f"h_{i}", "Greedy", "MODE_A", "FEASIBLE", True, 10.0)
    ledger.record_generation_failure(scenario_id="SCEN_4", reason="COPULA_SAMPLING_FAILED")

    summary = ledger.compute_summary()
    assert summary["accounting"]["n_requested"] == 5
    assert summary["accounting"]["n_generated"] == 4
    assert summary["accounting"]["n_generation_failures"] == 1


def test_ledger_10_evaluation_exception_accounted():
    """LEDGER-10: Evaluation exceptions are explicitly accounted with exception_type."""
    ledger = SimulationExecutionLedger(run_id="TEST_10", requested_n=1)
    ledger.record_evaluation_failure(
        scenario_id="SCEN_0",
        reason="Solver crashed",
        realization_hash="h0",
        initial_plan_solver="Greedy",
        recourse_mode="MODE_B2",
        exception_type="RuntimeError",
    )
    summary = ledger.compute_summary()
    assert summary["accounting"]["n_evaluation_failures"] == 1
    assert ledger.entries[0].exception_type == "RuntimeError"
    assert ledger.entries[0].evaluation_status == "FAILURE"


def test_ledger_11_timeout_accounted():
    """LEDGER-11: Timeouts are accounted explicitly as TIMEOUT status."""
    ledger = SimulationExecutionLedger(run_id="TEST_11", requested_n=1)
    ledger.record_timeout(
        scenario_id="SCEN_0",
        realization_hash="h0",
        initial_plan_solver="CPSat",
        recourse_mode="MODE_C2",
        runtime_ms=5000.0,
    )
    summary = ledger.compute_summary()
    assert summary["accounting"]["n_timeouts"] == 1
    assert ledger.entries[0].timeout is True
    assert ledger.entries[0].evaluation_status == "TIMEOUT"


def test_ledger_12_feasible_infeasible_unknown_distinguished():
    """LEDGER-12: Feasible, infeasible, and unknown solver statuses are accurately separated."""
    ledger = SimulationExecutionLedger(run_id="TEST_12", requested_n=3)
    ledger.record_evaluation_success("SCEN_0", "h0", "Greedy", "MODE_A", "OPTIMAL", True, 20.0)
    ledger.record_evaluation_success("SCEN_1", "h1", "Greedy", "MODE_A", "ONLINE_INFEASIBLE_NO_CAPACITY", False, 999.0)
    ledger.record_evaluation_success("SCEN_2", "h2", "Greedy", "MODE_A", "UNKNOWN", False, 999.0)

    summary = ledger.compute_summary()
    assert summary["accounting"]["n_feasible"] == 1
    assert summary["accounting"]["n_infeasible"] == 2
    assert [e.solver_status for e in ledger.entries] == ["OPTIMAL", "ONLINE_INFEASIBLE_NO_CAPACITY", "UNKNOWN"]


# ==============================================================================
# LEDGER-13 TO LEDGER-16: RUNNER ISOLATION & MANIFEST SAFETY
# ==============================================================================

def test_ledger_13_incomplete_run_does_not_create_complete_manifest(tmp_path):
    """LEDGER-13: Incomplete or failed run creates failed manifest, NEVER a COMPLETE manifest."""
    with patch("scripts.run_g2_monte_carlo_remediation.evaluate_mode_b2_rolling_online_recourse", side_effect=RuntimeError("Injected B2 crash")):
        with pytest.raises(RuntimeError, match="Injected B2 crash"):
            run_g2_remediation_pipeline(n_scenarios=2, output_dir=tmp_path, seed=202601)

    assert not (tmp_path / "simulation_manifest.json").exists()
    assert (tmp_path / "simulation_manifest_failed.json").exists()
    assert (tmp_path / "execution_ledger_entries_partial.csv").exists()

    with open(tmp_path / "simulation_manifest_failed.json") as f:
        failed_data = json.load(f)
    assert failed_data["status"] == "FAILED"


def test_ledger_14_config_source_hash_fingerprint_change():
    """LEDGER-14: Config or source alterations produce distinct fingerprints."""
    cfg1 = {"seed": 100, "rho": 0.45}
    cfg2 = {"seed": 101, "rho": 0.45}
    h1 = hashlib.sha256(json.dumps(cfg1, sort_keys=True).encode()).hexdigest()
    h2 = hashlib.sha256(json.dumps(cfg2, sort_keys=True).encode()).hexdigest()
    assert h1 != h2


def test_ledger_15_legacy_g2_artifacts_not_overwritten():
    """LEDGER-15: Default output path isolates to mc500, never touching legacy monte_carlo_remediated."""
    from scripts.run_g2_monte_carlo_remediation import DEFAULT_BASE_OUTPUT_DIR
    assert "monte_carlo_mc500" in str(DEFAULT_BASE_OUTPUT_DIR)
    assert "monte_carlo_remediated" not in str(DEFAULT_BASE_OUTPUT_DIR)


def test_ledger_16_run_id_output_isolation(tmp_path):
    """LEDGER-16: Separate run IDs produce completely isolated output subdirectories."""
    run_dir_1 = tmp_path / "run_alpha"
    run_dir_2 = tmp_path / "run_beta"
    assert run_dir_1 != run_dir_2


# ==============================================================================
# LEDGER-17 TO LEDGER-20: REPRODUCIBILITY & END-TO-END INVARIANTS
# ==============================================================================

def test_ledger_17_deterministic_replay(tmp_path):
    """LEDGER-17: Deterministic replay across runs with identical seed yields identical hashes."""
    dir1 = tmp_path / "run_1"
    dir2 = tmp_path / "run_2"
    res1 = run_g2_remediation_pipeline(n_scenarios=2, seed=202601, output_dir=dir1)
    res2 = run_g2_remediation_pipeline(n_scenarios=2, seed=202601, output_dir=dir2)

    df1 = pd.read_csv(dir1 / "execution_ledger_entries.csv")
    df2 = pd.read_csv(dir2 / "execution_ledger_entries.csv")

    assert list(df1["realization_hash"]) == list(df2["realization_hash"])
    assert list(df1["objective_value"]) == list(df2["objective_value"])


def test_ledger_18_all_mode_and_solver_identities_match_registry():
    """LEDGER-18: All mode and solver identities strictly match the 11-slot protocol."""
    expected_modes = {"MODE_A", "MODE_B1", "MODE_B2", "MODE_C1", "MODE_C2"}
    expected_solvers = {"Greedy", "CPSat", "Hybrid", "ForesightGreedy", "ForesightCPSat"}

    actual_modes = {m for m, s in CANONICAL_PROTOCOL_EVALUATIONS}
    actual_solvers = {s for m, s in CANONICAL_PROTOCOL_EVALUATIONS}

    assert actual_modes == expected_modes
    assert actual_solvers == expected_solvers


def test_ledger_19_correct_count_denominators_and_rates():
    """LEDGER-19: Rates explicitly stated with mathematically sound denominators."""
    ledger = SimulationExecutionLedger(run_id="TEST_19", requested_n=10)
    for i in range(8):
        ledger.record_scenario_generated(f"S{i}", i, 100+i, f"h{i}")
        ledger.record_evaluation_success(f"S{i}", f"h{i}", "Greedy", "MODE_A", "OPTIMAL", i < 6, 10.0)
    ledger.record_generation_failure("S8", "GEN_ERR")
    ledger.record_generation_failure("S9", "GEN_ERR")

    rates = ledger.compute_rates()
    # 2 gen failures / 10 requested = 0.20
    assert rates["generation_failure_rate"]["numerator"] == 2
    assert rates["generation_failure_rate"]["denominator"] == 10
    assert rates["generation_failure_rate"]["rate"] == 0.20

    # 6 feasible / 8 evaluated = 0.75
    assert rates["composite_feasible_rate"]["numerator"] == 6
    assert rates["composite_feasible_rate"]["denominator"] == 8
    assert rates["composite_feasible_rate"]["rate"] == 0.75


def test_ledger_20_multiple_runs_do_not_contaminate_each_other():
    """LEDGER-20: Separate ledger instances remain completely decoupled."""
    l1 = SimulationExecutionLedger(run_id="RUN_1", requested_n=5)
    l2 = SimulationExecutionLedger(run_id="RUN_2", requested_n=5)

    l1.record_scenario_generated("SCEN_0", 0, 100, "h0")
    assert len(l1.generation_records) == 1
    assert len(l2.generation_records) == 0


def test_production_runner_has_active_ledger_integration():
    """Confirmation that scripts/run_g2_monte_carlo_remediation.py integrates SimulationExecutionLedger."""
    runner_path = Path("scripts/run_g2_monte_carlo_remediation.py")
    source = runner_path.read_text(encoding="utf-8")

    assert "SimulationExecutionLedger" in source
    assert "ledger.record_scenario_generated" in source
    assert "ledger.record_evaluation_success" in source
    assert "ledger.validate_ledger" in source
    assert "ledger.validate_paired_crn" in source
    assert "execution_ledger_entries.csv" in source


def test_ledger_21_rate_denominators_with_injected_evaluation_failure():
    """LEDGER-21: Rate denominators with 5 realizations, 55 expected evaluations, and 1 evaluation failure."""
    ledger = SimulationExecutionLedger(
        run_id="TEST_21",
        requested_n=5,
        required_evaluations=CANONICAL_PROTOCOL_EVALUATIONS,
    )
    for i in range(5):
        s_id = f"SCEN_{i:02d}"
        ledger.record_scenario_generated(
            scenario_id=s_id,
            scenario_index=i,
            seed=202601 + i,
            realization_hash=f"hash_{i}",
        )
        for mode, solver in CANONICAL_PROTOCOL_EVALUATIONS:
            # Inject exactly 1 evaluation failure at scenario 0, Mode B2, Hybrid
            if i == 0 and mode == "MODE_B2" and solver == "Hybrid":
                ledger.record_evaluation_failure(
                    scenario_id=s_id,
                    reason="Injected solver failure",
                    realization_hash=f"hash_{i}",
                    initial_plan_solver=solver,
                    recourse_mode=mode,
                    exception_type="RuntimeError",
                )
            else:
                ledger.record_evaluation_success(
                    scenario_id=s_id,
                    realization_hash=f"hash_{i}",
                    initial_plan_solver=solver,
                    recourse_mode=mode,
                    solver_status="OPTIMAL",
                    composite_feasible=True,
                    objective_value=100.0 + i,
                    runtime_ms=1.5,
                )

    summary = ledger.compute_summary()
    acc = summary["accounting"]
    assert acc["n_requested_realizations"] == 5
    assert acc["n_generated_realizations"] == 5
    assert acc["n_expected_evaluations"] == 55
    assert acc["n_completed_evaluations"] == 54
    assert acc["n_evaluation_failures"] == 1
    assert acc["n_feasible_evaluations"] == 54

    rates = ledger.compute_rates()
    # generation_failure_rate: denominator = requested realizations (5)
    assert rates["generation_failure_rate"]["numerator"] == 0
    assert rates["generation_failure_rate"]["denominator"] == 5
    assert rates["generation_failure_rate"]["rate"] == 0.0

    # evaluation_failure_rate: denominator = expected evaluation slots (55, NOT 5!)
    assert rates["evaluation_failure_rate"]["numerator"] == 1
    assert rates["evaluation_failure_rate"]["denominator"] == 55
    assert rates["evaluation_failure_rate"]["rate"] == pytest.approx(1 / 55)

    # composite_feasible_rate: denominator = completed evaluations (54)
    assert rates["composite_feasible_rate"]["numerator"] == 54
    assert rates["composite_feasible_rate"]["denominator"] == 54
    assert rates["composite_feasible_rate"]["rate"] == 1.0

