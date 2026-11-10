"""Phase G & Stage 9 — Aircraft Turn & Timeline Semantics Audit Runner.

Protocol: docs/roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md - Section 4
          docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 19 (Stage 9)
Step: STEP 6 — AIRCRAFT TURN / TIMELINE SEMANTICS

Executes:
1. Complete operational timeline audit:
   scheduled arrival -> sampled delay -> simulated arrival -> gate-in -> turnaround/dwell -> gate-out -> gate-release.
2. Hand-checkable boundary evaluations (delay=0, delay=10, dwell < turn, dwell > turn, buffer, back-to-back).
3. 100% parity verification across simulation, conflict detector, verifier, and CP-SAT solver.
4. Emits certified manifest:
   - artifacts/audit/phase_g_timeline_semantics_audit_manifest_v1.json
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys

# Ensure repo root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.audit.protocol_guards import POST_HOLDOUT_STATUS_DECLARATION
from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import (
    Flight,
    FlightTimeWindow,
    Gate,
    GateAssignment,
    verify_hard_constraints_independently,
)
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.simulation.aircraft_turn import AircraftTurn, AircraftTurnModel
from src.simulation.conflict_detector import detect_conflicts


def run_timeline_semantics_audit() -> dict[str, str]:
    """Execute complete Step 6 Aircraft Turn & Timeline Semantics audit."""
    print("=" * 80)
    print("STARTING STEP 6: AIRCRAFT TURN / TIMELINE SEMANTICS AUDIT")
    print("Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 19")
    print("=" * 80)

    audit_dir = PROJECT_ROOT / "artifacts" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)

    # 1. Audit Hand-Checkable Scenarios
    print("\n[Step 1] Auditing hand-checkable timeline scenarios...")

    # Scenario 1: delay = 0
    m_std = AircraftTurnModel(min_turnaround_min=45, default_dwell_min=60, separation_buffer_min=15)
    t_d0 = m_std.synthesize_turn("FL_01", "DL", "101", scheduled_arrival_min=100, sampled_delay_min=0.0)
    assert t_d0.gate_in_min == 100
    assert t_d0.gate_out_min == 160
    assert t_d0.gate_release_min == 175
    assert t_d0.physical_dwell_min == 60
    assert t_d0.turnaround_slack_min == 15
    assert t_d0.occupancy_duration_min == 75
    print("  -> Scenario 1 (delay=0): gate_in=100, gate_out=160, gate_release=175, dwell=60, slack=15 [PASS]")

    # Scenario 2: delay = 10 (absorbed by scheduled slack)
    t_d10 = m_std.synthesize_turn("FL_02", "DL", "102", scheduled_arrival_min=100, sampled_delay_min=10.0)
    assert t_d10.gate_in_min == 110
    assert t_d10.gate_out_min == 160  # Departure not pushed
    assert t_d10.gate_release_min == 175
    assert t_d10.physical_dwell_min == 50
    assert t_d10.turnaround_slack_min == 5
    print("  -> Scenario 2 (delay=10): gate_in=110, gate_out=160 (absorbed), dwell=50, slack=5 [PASS]")

    # Scenario 3: delay exceeding slack (delay=25)
    t_d25 = m_std.synthesize_turn("FL_03", "DL", "103", scheduled_arrival_min=100, sampled_delay_min=25.0)
    assert t_d25.gate_in_min == 125
    assert t_d25.gate_out_min == 170  # Pushed by 10 min
    assert t_d25.gate_release_min == 185
    assert t_d25.physical_dwell_min == 45
    assert t_d25.turnaround_slack_min == 0
    print("  -> Scenario 3 (delay=25): gate_in=125, gate_out=170 (pushed), dwell=45, slack=0 [PASS]")

    # Scenario 4: scheduled dwell < min turnaround (dwell=30, turn=45)
    m_tight = AircraftTurnModel(min_turnaround_min=45, default_dwell_min=30, separation_buffer_min=15)
    t_tight = m_tight.synthesize_turn("FL_TIGHT", "AA", "201", scheduled_arrival_min=200, sampled_delay_min=0.0)
    assert t_tight.scheduled_departure_min == 230
    assert t_tight.gate_out_min == 245  # Extended by turnaround
    assert t_tight.gate_release_min == 260
    assert t_tight.physical_dwell_min == 45
    print("  -> Scenario 4 (dwell 30 < turnaround 45): D_sched=230 -> gate_out=245 (turnaround enforced) [PASS]")

    # Scenario 5: scheduled dwell > min turnaround (dwell=90, turn=45)
    m_gen = AircraftTurnModel(min_turnaround_min=45, default_dwell_min=90, separation_buffer_min=15)
    t_gen = m_gen.synthesize_turn("FL_GEN", "UA", "301", scheduled_arrival_min=300, sampled_delay_min=40.0)
    assert t_gen.gate_in_min == 340
    assert t_gen.gate_out_min == 390  # 40 min delay fully absorbed by 45 min slack
    assert t_gen.gate_release_min == 405
    print("  -> Scenario 5 (dwell 90 > turnaround 45): delay=40 absorbed within slack -> gate_out=390 [PASS]")

    # Scenario 6: buffer > 0 vs buffer = 0
    m_b0 = AircraftTurnModel(min_turnaround_min=45, default_dwell_min=60, separation_buffer_min=0)
    t_a_b0 = m_b0.synthesize_turn("FL_A0", "DL", "1", scheduled_arrival_min=100, sampled_delay_min=0)
    t_b_b0 = m_b0.synthesize_turn("FL_B0", "DL", "2", scheduled_arrival_min=160, sampled_delay_min=0)
    assert t_a_b0.time_window.overlaps(t_b_b0.time_window) is False

    t_a_b15 = m_std.synthesize_turn("FL_A15", "DL", "1", scheduled_arrival_min=100, sampled_delay_min=0)
    t_b_b15 = m_std.synthesize_turn("FL_B15", "DL", "2", scheduled_arrival_min=160, sampled_delay_min=0)
    assert t_a_b15.time_window.overlaps(t_b_b15.time_window) is True
    assert t_a_b15.time_window.overlap_duration(t_b_b15.time_window) == 15
    print("  -> Scenario 6 (buffer 0 vs 15): buffer=0 overlap=False, buffer=15 overlap=15 min [PASS]")

    # Scenario 7: back-to-back boundary conditions
    t_f1 = m_std.synthesize_turn("F1", "DL", "1", scheduled_arrival_min=100, sampled_delay_min=0)  # [100, 175)
    t_f2_exact = m_std.synthesize_turn("F2_EXACT", "DL", "2", scheduled_arrival_min=175, sampled_delay_min=0)  # [175, 250)
    t_f2_encroach = m_std.synthesize_turn("F2_ENCROACH", "DL", "2", scheduled_arrival_min=174, sampled_delay_min=0)  # [174, 249)

    assert t_f1.time_window.overlaps(t_f2_exact.time_window) is False
    assert t_f1.time_window.overlaps(t_f2_encroach.time_window) is True
    assert t_f1.time_window.overlap_duration(t_f2_encroach.time_window) == 1
    print("  -> Scenario 7 (back-to-back boundary): arr=175 overlap=0m [PASS], arr=174 overlap=1m [PASS]")

    # 2. Audit Parity Across Simulation, ConflictDetector, Verifier, and CP-SAT
    print("\n[Step 2] Auditing interval logic parity across Simulation, ConflictDetector, Verifier, and CP-SAT...")
    t3 = m_std.synthesize_turn("F3", "DL", "3", scheduled_arrival_min=150, sampled_delay_min=0)  # [150, 225)
    test_turns = [t_f1, t_f2_exact, t3]
    test_flights = [t.to_flight(i) for i, t in enumerate(test_turns)]

    gate_g1 = Gate(gate_id="G1", gate_index=0, is_overflow=False)
    gate_ovf = Gate(gate_id="OVERFLOW", gate_index=1, is_overflow=True)
    test_gates = [gate_g1, gate_ovf]

    solver = CPSatGateSolver(config=GateOptimizationConfig())
    res = solver.solve(test_flights, test_gates)
    assert res.feasible is True
    assert res.assignments["F1"].gate_id == "G1"
    assert res.assignments["F2_EXACT"].gate_id == "G1"
    assert res.assignments["F3"].gate_id == "OVERFLOW"

    diag = verify_hard_constraints_independently(test_flights, test_gates, res.assignments)
    assert diag.is_valid is True
    assert diag.conflict_count == 0

    conf = detect_conflicts(res.assignments, test_turns, test_gates)
    assert conf.has_conflicts is False
    assert conf.conflict_count == 0
    assert conf.peak_single_gate_concurrency == 1
    print("  -> CP-SAT, Verifier, and ConflictDetector 100% in agreement on contact gate sharing! [PASS]")

    # 3. Generate Certified Manifest
    manifest = {
        "manifest_version": "phase_g_timeline_semantics_audit_manifest_v1",
        "phase": "PHASE_G_STEP_6",
        "status": "PASS",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_reference": "docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Section 19",
        "operational_timeline_pipeline": (
            "scheduled_arrival -> sampled_delay -> simulated_arrival -> gate_in -> "
            "turnaround/dwell -> gate_out -> gate_release"
        ),
        "timeline_semantics_specifications": {
            "min_turnaround": {
                "name": "min_turnaround_min",
                "default_value": 45,
                "semantics": "Physical minimum operational time required at gate to deplane, service, and board.",
                "formula": "D_min = A_sim + min_turnaround_min",
            },
            "scheduled_dwell": {
                "name": "default_dwell_min",
                "default_value": 60,
                "semantics": "Scheduled timetable turnaround duration (D_sched - A_sched) when uncoupled.",
                "formula": "D_sched = A_sched + default_dwell_min (or explicit scheduled departure)",
            },
            "buffer": {
                "name": "separation_buffer_min",
                "default_value": 15,
                "semantics": "Safety buffer required after pushback before next aircraft can occupy gate.",
                "formula": "gate_release = gate_out + separation_buffer_min",
            },
            "gate_in_formula": "gate_in = A_sim = round(A_sched + sampled_delay_min)",
            "gate_out_formula": "gate_out = D_sim = max(D_sched, A_sim + min_turnaround_min)",
            "gate_release_formula": "gate_release = gate_out + separation_buffer_min",
            "gate_occupancy_interval": "[gate_in, gate_release) half-open interval",
            "zero_double_counting_proof": (
                "Turnaround and dwell are combined via max(D_sched, D_min) and never added together. "
                "Buffer is added exactly once to simulated departure for gate release."
            ),
        },
        "hand_checkable_verifications": {
            "delay_zero": {
                "inputs": {"A_sched": 100, "delay": 0, "turn": 45, "dwell": 60, "buffer": 15},
                "outputs": {
                    "gate_in": t_d0.gate_in_min,
                    "gate_out": t_d0.gate_out_min,
                    "gate_release": t_d0.gate_release_min,
                    "physical_dwell": t_d0.physical_dwell_min,
                    "turnaround_slack": t_d0.turnaround_slack_min,
                    "occupancy_duration": t_d0.occupancy_duration_min,
                },
                "status": "PASS",
            },
            "delay_ten": {
                "inputs": {"A_sched": 100, "delay": 10, "turn": 45, "dwell": 60, "buffer": 15},
                "outputs": {
                    "gate_in": t_d10.gate_in_min,
                    "gate_out": t_d10.gate_out_min,
                    "gate_release": t_d10.gate_release_min,
                    "physical_dwell": t_d10.physical_dwell_min,
                    "turnaround_slack": t_d10.turnaround_slack_min,
                    "occupancy_duration": t_d10.occupancy_duration_min,
                },
                "status": "PASS",
            },
            "delay_exceeding_slack": {
                "inputs": {"A_sched": 100, "delay": 25, "turn": 45, "dwell": 60, "buffer": 15},
                "outputs": {
                    "gate_in": t_d25.gate_in_min,
                    "gate_out": t_d25.gate_out_min,
                    "gate_release": t_d25.gate_release_min,
                    "physical_dwell": t_d25.physical_dwell_min,
                    "turnaround_slack": t_d25.turnaround_slack_min,
                    "occupancy_duration": t_d25.occupancy_duration_min,
                },
                "status": "PASS",
            },
            "scheduled_dwell_less_than_min_turnaround": {
                "inputs": {"A_sched": 200, "delay": 0, "turn": 45, "dwell": 30, "buffer": 15},
                "outputs": {
                    "scheduled_departure": t_tight.scheduled_departure_min,
                    "gate_out": t_tight.gate_out_min,
                    "gate_release": t_tight.gate_release_min,
                    "turnaround_overridden": True,
                },
                "status": "PASS",
            },
            "scheduled_dwell_greater_than_min_turnaround": {
                "inputs": {"A_sched": 300, "delay": 40, "turn": 45, "dwell": 90, "buffer": 15},
                "outputs": {
                    "gate_in": t_gen.gate_in_min,
                    "gate_out": t_gen.gate_out_min,
                    "gate_release": t_gen.gate_release_min,
                    "delay_absorbed": True,
                },
                "status": "PASS",
            },
            "buffer_comparison": {
                "buffer_0_overlap": False,
                "buffer_15_overlap": True,
                "overlap_duration_min": 15.0,
                "status": "PASS",
            },
            "back_to_back_boundary": {
                "exact_boundary_overlap": False,
                "encroachment_1m_overlap": True,
                "encroachment_overlap_duration_min": 1.0,
                "status": "PASS",
            },
        },
        "interval_logic_parity_certified": {
            "aircraft_turn": "occupancy_interval = (simulated_arrival_min, gate_release_min)",
            "domain_flight_window": "FlightTimeWindow [start_min, end_min)",
            "overlap_formula": "max(s1, s2) < min(e1, e2)",
            "overlap_duration_formula": "max(0, min(e1, e2) - max(s1, s2))",
            "conflict_detector_parity": True,
            "cp_sat_solver_parity": True,
            "independent_verifier_parity": True,
        },
        "post_holdout_status": POST_HOLDOUT_STATUS_DECLARATION,
    }

    manifest_path = audit_dir / "phase_g_timeline_semantics_audit_manifest_v1.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"\n[Step 3] Manifest written to: {manifest_path}")

    print("\n" + "=" * 80)
    print("STEP 6 AIRCRAFT TURN / TIMELINE SEMANTICS AUDIT: PASS")
    print("=" * 80)

    return {
        "status": "PASS",
        "manifest_path": str(manifest_path),
    }


if __name__ == "__main__":
    run_timeline_semantics_audit()
