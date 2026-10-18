"""Export adapters for verified gate allocations and solver run manifests.

Adheres strictly to the zero-data-leakage mandate (no actual delay columns exported).
"""

import io
import json
from typing import Any, Dict, Optional, Sequence

import pandas as pd

from dashboard.core.contracts import GateTimelineView, SolverRunView
from dashboard.core.validation import ScientificValidator


def export_assignments_to_csv(
    assignments: Sequence[GateTimelineView],
    scenario_id: str,
    config_hash: str = "",
) -> str:
    """Serialize verified gate assignments to a clean, leakage-free CSV string.

    Args:
        assignments: List of GateTimelineView objects.
        scenario_id: Active scenario identifier.
        config_hash: Hash fingerprint of solver execution config.

    Returns:
        str: CSV formatted string ready for file download.
    """
    rows = []
    for a in assignments:
        row = {
            "assignment_id": a.assignment_id,
            "flight_id": a.flight_id,
            "carrier": a.carrier,
            "flight_number": a.flight_number,
            "gate_id": a.gate_id,
            "nominal_gate_id": a.nominal_gate_id or "",
            "concourse": a.concourse,
            "occupancy_start_min": a.start_min,
            "gate_out_min": a.actual_gate_out_min,
            "gate_release_min": a.actual_gate_release_min,
            "buffer_min": a.buffer_min,
            "is_reassigned": a.is_reassigned,
            "is_remote": a.is_remote,
            "has_conflict": a.has_conflict,
            "resource_type": a.resource_type,
            "scenario_id": scenario_id or a.scenario_id,
            "config_hash": config_hash,
        }
        rows.append(row)

    df = pd.DataFrame(rows)

    # Enforce zero target leakage
    if not df.empty:
        ScientificValidator.check_prediction_data_leakage(list(df.columns))

    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


def export_run_manifest_to_json(run_view: SolverRunView) -> str:
    """Serialize complete solver execution manifest to a sanitized JSON string.

    Args:
        run_view: SolverRunView view model.

    Returns:
        str: Indented JSON string formatted for audit export.
    """
    manifest: Dict[str, Any] = {
        "solver_name": run_view.solver_name,
        "scenario_id": run_view.scenario_id,
        "status": run_view.status,
        "termination_reason": run_view.termination_reason,
        "is_optimal_proven": run_view.is_optimal_proven,
        "optimality_gap": run_view.optimality_gap,
        "objective_value": run_view.objective_value,
        "decision_cost": run_view.decision_cost,
        "reporting_cost": run_view.reporting_cost,
        "reassignment_count": run_view.reassignment_count,
        "remote_gate_count": run_view.remote_gate_count,
        "conflict_count": run_view.conflict_count,
        "solve_time_sec": run_view.solve_time_sec,
        "total_assignments": len(run_view.assignments),
        "solver_config": run_view.solver_config,
        "provenance": run_view.provenance.value,
        "schema_version": run_view.schema_version,
    }
    return json.dumps(manifest, indent=2, default=str)


def export_benchmark_to_csv(
    benchmark_df: pd.DataFrame,
    experiment_id: str = "BENCH_MULTI_SOLVER",
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Export filtered benchmark runs to CSV with experiment identity preserved.
    
    Guarantees target leakage check and provenance retention.
    """
    df = benchmark_df.copy()
    if not df.empty:
        ScientificValidator.check_prediction_data_leakage(list(df.columns))
    
    if "experiment_id" not in df.columns:
        df["experiment_id"] = experiment_id
    if metadata and "timestamp_utc" in metadata and "timestamp_utc" not in df.columns:
        df["timestamp_utc"] = metadata["timestamp_utc"]

    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


def export_mc_summary_to_csv(
    mc_df_or_records: Any,
    experiment_id: str = "P09_MONTE_CARLO_500",
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Export Monte Carlo scenario evaluation results to CSV with experiment identity.
    
    Guarantees target leakage check and identity metadata.
    """
    if isinstance(mc_df_or_records, pd.DataFrame):
        df = mc_df_or_records.copy()
    elif isinstance(mc_df_or_records, list):
        df = pd.DataFrame(mc_df_or_records)
    elif isinstance(mc_df_or_records, dict):
        df = pd.DataFrame([mc_df_or_records])
    else:
        raise ValueError("Unsupported data type for Monte Carlo summary export")

    if not df.empty:
        ScientificValidator.check_prediction_data_leakage(list(df.columns))

    if "experiment_id" not in df.columns:
        df["experiment_id"] = experiment_id
    if metadata:
        for k, v in metadata.items():
            if k not in df.columns:
                df[k] = v

    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


def export_manifest_to_json(manifest_dict: Dict[str, Any]) -> str:
    """Export sanitized experiment or simulation manifest to JSON."""
    return json.dumps(manifest_dict, indent=2, default=str)
