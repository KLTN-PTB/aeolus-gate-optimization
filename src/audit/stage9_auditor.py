"""Audit Engine for Stage 9: Downstream Gate Simulation & Operational Utility.

Audits:
1. Data provenance: whether the 25 days / 529 flights were pre-registered or excluded from Stage 8;
2. Overlap analysis between Stage 8 selection sample and Stage 9 simulation sample;
3. Ground truth semantics (synthetic turn simulation vs actual airport operations);
4. Configuration consistency between simulation parameters and Stage 10 freeze manifest.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any


@dataclass
class Stage9AuditResult:
    """Findings from auditing Stage 9 downstream gate simulation."""

    stage_id: str
    audit_status: str  # "POST_SELECTION_REUSE", "INVALID_FOR_CLAIM", "FAIL"
    days_evaluated: int
    flights_evaluated: int
    were_days_preregistered_before_stage8: bool
    were_days_excluded_from_stage8: bool
    overlap_with_stage8_data_percent: float
    data_reuse_verdict: str
    ground_truth_type: str  # "SYNTHETIC_SIMULATION_UNDER_HISTORICAL_DELAYS"
    claim_semantics_valid: bool
    simulation_config_matches_freeze_manifest: bool
    config_discrepancies: list[str]
    audit_findings: list[str]
    provenance_chain: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def audit_stage9_downstream(project_root: Path | None = None) -> Stage9AuditResult:
    """Audit the Stage 9 downstream gate simulation and data independence."""
    root = project_root or Path(__file__).resolve().parents[2]
    manifest_dir = root / "artifacts" / "manifests"
    s8_path = manifest_dir / "selected_system_manifest_v1.json"
    s9_path = manifest_dir / "probabilistic_stage9_gate_simulation_v1.json"
    s10_path = manifest_dir / "full_system_freeze_manifest_v1.json"

    findings: list[str] = []
    discrepancies: list[str] = []

    if not s9_path.exists():
        return Stage9AuditResult(
            stage_id="STAGE_9_GATE_SIMULATION",
            audit_status="FAIL",
            days_evaluated=0,
            flights_evaluated=0,
            were_days_preregistered_before_stage8=False,
            were_days_excluded_from_stage8=False,
            overlap_with_stage8_data_percent=0.0,
            data_reuse_verdict="MISSING_MANIFEST",
            ground_truth_type="UNKNOWN",
            claim_semantics_valid=False,
            simulation_config_matches_freeze_manifest=False,
            config_discrepancies=["Missing probabilistic_stage9_gate_simulation_v1.json"],
            audit_findings=["Stage 9 manifest does not exist"],
            provenance_chain={},
        )

    s9_data = json.loads(s9_path.read_text(encoding="utf-8"))
    sim_params = s9_data.get("simulation_parameters", {})
    days_count = sim_params.get("total_days_evaluated", 25)
    flights_count = sim_params.get("total_flights_evaluated", 529)

    # 1. Check Data Overlap with Stage 8
    # In both scripts, load_stratified_fold_data(val_year=2023, sample_val=5000, random_state=202601)
    # is called and dates are sorted by value_counts() >= 8.
    # Stage 8 takes top 30 days, Stage 9 takes top 25 days.
    overlap_pct = 100.0  # Exactly the first 25 of the 30 days evaluated in Stage 8
    preregistered = False  # Days were not pre-registered in Stage 0 or Stage 7 manifests
    excluded = False  # Days were not excluded from Stage 8 model selection

    findings.append(
        "CRITICAL: The 25 operational days (529 flights) evaluated in Stage 9 overlap 100% with the "
        "2023 selection data used in Stage 8. They were NOT held out or pre-registered as an independent test set."
    )
    findings.append(
        "Downstream utility on 2023 is a post-selection re-use of the development selection partition, "
        "meaning Stage 9 downstream results cannot be claimed as independent out-of-sample confirmation."
    )

    # 2. Check Ground Truth Nature
    # In Stage 9, historical_ground_truth is derived by synthesizing turns from actual delays on nominal plan
    gt_type = "SYNTHETIC_SIMULATION_UNDER_HISTORICAL_DELAYS"
    findings.append(
        "CRITICAL: 'historical_ground_truth' does NOT represent actual airport gate occupancy or real-world "
        "gate assignments. It is an artificial simulation using an assumed 45m turnaround, 60m dwell, 30 contact gates, "
        "and a greedy nominal schedule applied to observed arrival delays."
    )

    # 3. Check Configuration Consistency with Stage 10 Freeze Manifest
    config_match = True
    if s10_path.exists():
        s10_data = json.loads(s10_path.read_text(encoding="utf-8"))
        opt_cfg_10 = s10_data.get("item_16_optimization_configuration", {}).get("weights", {})
        sim_cfg_10 = s10_data.get("item_15_simulation_configuration", {})

        freeze_reassign_pen = opt_cfg_10.get("reassignment_penalty", 10.0)
        freeze_overflow_pen = opt_cfg_10.get("remote_overflow_penalty", 1000.0)

        # In run_probabilistic_stage9_simulation.py lines 330-334:
        # GateSimulator(n_contact_gates=args.n_gates, overflow_penalty=100.0, reassignment_penalty=1.0)
        script_reassign_pen = 1.0
        script_overflow_pen = 100.0

        if freeze_reassign_pen != script_reassign_pen:
            config_match = False
            msg = f"Reassignment penalty mismatch: Freeze manifest records {freeze_reassign_pen}, but script executed with {script_reassign_pen}."
            discrepancies.append(msg)
            findings.append(msg)

        if freeze_overflow_pen != script_overflow_pen:
            config_match = False
            msg = f"Overflow penalty mismatch: Freeze manifest records {freeze_overflow_pen}, but script executed with {script_overflow_pen}."
            discrepancies.append(msg)
            findings.append(msg)

    # 4. Status Determination
    # Must be marked as POST_SELECTION_REUSE because it re-evaluated Stage 8 selection data
    audit_status = "POST_SELECTION_REUSE"

    return Stage9AuditResult(
        stage_id="STAGE_9_GATE_SIMULATION",
        audit_status=audit_status,
        days_evaluated=days_count,
        flights_evaluated=flights_count,
        were_days_preregistered_before_stage8=preregistered,
        were_days_excluded_from_stage8=excluded,
        overlap_with_stage8_data_percent=overlap_pct,
        data_reuse_verdict="CIRCULAR_DOWNSTREAM_REUSE_OF_SELECTION_DATA",
        ground_truth_type=gt_type,
        claim_semantics_valid=False,
        simulation_config_matches_freeze_manifest=config_match,
        config_discrepancies=discrepancies,
        audit_findings=findings,
        provenance_chain={
            "stage8_manifest": str(s8_path.as_posix()),
            "stage9_manifest": str(s9_path.as_posix()),
            "evaluation_year": 2023,
            "sample_val": 5000,
            "seed": 202601,
            "overlap_days_count": days_count,
        },
    )
