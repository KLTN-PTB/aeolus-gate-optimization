"""Upload-specific orchestration using the existing verified ML/solver engines."""
from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, time, timezone
import json
import math
import hashlib
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo
import zipfile

import numpy as np
import pandas as pd

from src.contracts.turn_contracts import FlightLeg, LegDirection, LinkageSource, PairType, TurnPair
from src.optimization.adapter import DualCoreGateOptimizerAdapter
from src.optimization.config import GateOptimizationConfig
from src.optimization.domain import Gate, GateResourceType, verify_hard_constraints_independently
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver
from src.optimization.solvers.hybrid_solver import HybridGateSolver
from src.simulation.dual_prediction_turn import DualTurnEngine, SimulationMode
from src.simulation.native_dual_core_pipeline import NativeDualCorePipeline, NativeDualCorePipelineConfig

from web_dashboard.contracts import MAX_SELECTED_LEGS, RunRequest
from web_dashboard.normalization import InputError, OUTCOMES

ROOT = Path(__file__).resolve().parents[1]


def json_write(path: Path, value) -> None:
    # allow_nan=False ensures invalid solver values never leak into HTTP JSON.
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def finite_metadata(value):
    """Infeasible solver traces may contain undefined costs (+inf).

    Preserve their meaning as null in metadata, never a manufactured zero.
    Predictions are validated separately and must always be finite.
    """
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: finite_metadata(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [finite_metadata(item) for item in value]
    return value


def make_legs(frame: pd.DataFrame, service_date: str) -> dict[str, FlightLeg]:
    midnight = datetime.combine(datetime.fromisoformat(service_date).date(), time(), ZoneInfo("America/New_York"))
    reference = midnight.astimezone(timezone.utc)
    legs = {}
    for row in frame.to_dict("records"):
        local = datetime.fromisoformat(row["scheduled_event_local"])
        utc = datetime.fromisoformat(row["scheduled_event_utc"])
        fid = row["flight_key"]
        legs[fid] = FlightLeg(
            flight_id=fid, direction=LegDirection(row["direction"]), carrier=row["OP_CARRIER"],
            flight_number=str(row["OP_CARRIER_FL_NUM"]), origin=row["ORIGIN"], destination=row["DEST"],
            scheduled_event_local=local, scheduled_event_utc=utc, event_timezone="America/New_York",
            scheduled_elapsed_min=row["CRS_ELAPSED_TIME"], tail_number=row.get("TAIL_NUM"),
            normalized_timeline_min=int((utc - reference).total_seconds() // 60),
        )
    return legs


def pair_schedule_legs(legs: dict[str, FlightLeg], minimum: int) -> list[TurnPair]:
    """Only consecutive same-tail ARR->DEP events, never carrier-only matching.

    A raw historical tail is not authenticated point-in-time rotation evidence:
    label these INFERRED_PAIR rather than upgrading them to VERIFIED_PAIR.
    """
    by_tail: dict[str, list[FlightLeg]] = {}
    for leg in legs.values():
        if leg.tail_number:
            by_tail.setdefault(leg.tail_number, []).append(leg)
    pairs, used = [], set()
    for tail in sorted(by_tail):
        events = sorted(by_tail[tail], key=lambda leg: (leg.normalized_timeline_min, leg.flight_id))
        for arrival, departure in zip(events, events[1:]):
            dwell = departure.normalized_timeline_min - arrival.normalized_timeline_min
            if (arrival.direction == LegDirection.ARR and departure.direction == LegDirection.DEP
                    and minimum <= dwell <= 720 and arrival.flight_id not in used and departure.flight_id not in used):
                pairs.append(TurnPair(
                    pair_id=f"TURN_{arrival.flight_id}", arrival_leg_id=arrival.flight_id,
                    departure_leg_id=departure.flight_id, pair_type=PairType.INFERRED_PAIR,
                    linkage_source=LinkageSource.SCHEDULE_CHAIN_HEURISTIC,
                    scheduled_turnaround_min=dwell, evidence_metadata={"tail_number": tail,
                    "matching_mode": "CONSECUTIVE_SAME_TAIL_SCHEDULE", "authenticated_rotation": False},
                ))
                used.update((arrival.flight_id, departure.flight_id))
    for leg in sorted(legs.values(), key=lambda leg: (leg.normalized_timeline_min, leg.flight_id)):
        if leg.flight_id not in used:
            arrival = leg.direction == LegDirection.ARR
            pairs.append(TurnPair(
                pair_id=f"TURN_{leg.flight_id}", arrival_leg_id=leg.flight_id if arrival else None,
                departure_leg_id=None if arrival else leg.flight_id,
                pair_type=PairType.UNMATCHED_ARR if arrival else PairType.UNMATCHED_DEP,
                linkage_source=LinkageSource.UNPAIRED,
            ))
    covered = [fid for p in pairs for fid in (p.arrival_leg_id, p.departure_leg_id) if fid]
    if len(covered) != len(legs) or set(covered) != set(legs):
        raise ValueError("Không bảo toàn được số lượt bay khi ghép cặp.")
    return sorted(pairs, key=lambda pair: pair.pair_id)


def run_pipeline(frame: pd.DataFrame, request: RunRequest, output: Path,
                 source_manifest: dict, progress: Callable[[str], None] = lambda _: None) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    service_date = request.service_date.isoformat()
    selected = frame.loc[frame.service_date.eq(service_date)].copy().reset_index(drop=True)
    if selected.empty:
        raise InputError("Không có lượt bay ATL trong ngày đã chọn.")
    if len(selected) > MAX_SELECTED_LEGS:
        raise InputError(f"Ngày đã chọn có {len(selected)} lượt, vượt giới hạn {MAX_SELECTED_LEGS}; không tự cắt dữ liệu.")
    config = NativeDualCorePipelineConfig(airport="ATL")
    # Resolve checkpoint paths independently of cwd; still use existing hashes,
    # registry eligibility, and allowlist validation inside the native pipeline.
    config.arrival_checkpoint_path = ROOT / config.arrival_checkpoint_path
    config.departure_checkpoint_path = ROOT / config.departure_checkpoint_path
    config.departure_preprocessor_path = ROOT / config.departure_preprocessor_path
    native = NativeDualCorePipeline(config)
    progress("models")
    models = native.load_and_verify_models()
    progress("prediction")
    # Never pass evaluation columns to any estimator or pairing operation.
    features = selected.drop(columns=list(OUTCOMES), errors="ignore")
    predictions, lookup = native.run_native_inference(
        features.loc[features.direction.eq("ARR")].reset_index(drop=True),
        features.loc[features.direction.eq("DEP")].reset_index(drop=True), models,
    )
    expected = set(features.flight_key)
    if set(lookup) != expected or len(predictions) != len(expected) or not all(math.isfinite(v) for v in lookup.values()):
        raise ValueError("Dự báo thiếu, trùng hoặc không hữu hạn; không được thay thế bằng 0.")
    source_lookup = selected.set_index("flight_key").to_dict("index")
    prediction_rows = []
    for pred in predictions:
        row = source_lookup[pred.flight_id]
        actual = row["ARR_DELAY" if pred.flight_direction == "ARR" else "DEP_DELAY"]
        prediction_rows.append({**pred.to_dict(), "prediction_cutoff_utc": row["prediction_cutoff_utc"],
            "carrier": row["OP_CARRIER"], "flight_number": str(row["OP_CARRIER_FL_NUM"]),
            "origin": row["ORIGIN"], "destination": row["DEST"],
            "scheduled_event_local": row["scheduled_event_local"],
            "actual_delay_min": float(actual) if pd.notna(actual) else None})

    progress("pairing")
    legs = make_legs(features, service_date)
    pairs = pair_schedule_legs(legs, request.min_turnaround_min)
    engine = DualTurnEngine(min_turnaround_min=request.min_turnaround_min,
                            default_dwell_min=request.default_dwell_min, separation_buffer_min=request.buffer_min)

    def build_turns(delays):
        result = []
        for pair in pairs:
            turn = engine.synthesize_turn(
                pair, legs, delays[pair.arrival_leg_id] if pair.arrival_leg_id else 0.0,
                delays[pair.departure_leg_id] if pair.departure_leg_id else None,
                mode=SimulationMode.DUAL_POINT,
            )
            if pair.pair_type == PairType.UNMATCHED_DEP:
                # Explicitly opted-in estimated pre-departure dwell (not observed occupancy).
                turn = replace(turn, unmatched_status="ASSUMED_PREDEPARTURE_DWELL")
            result.append(turn)
        return result

    turns = build_turns(lookup)
    solver_config = GateOptimizationConfig(
        reassignment_weight=10, overflow_weight=200, delay_weight=0, risk_weight=0,
        separation_buffer_minutes=request.buffer_min, min_turnaround_minutes=request.min_turnaround_min,
        default_dwell_minutes=request.default_dwell_min, dual_core_gate_enabled=True,
        allow_unbounded_overflow=False, enforce_remote_capacity=True,
        time_limit_seconds=request.time_limit_sec, num_search_workers=4, random_seed=202601,
        cp_sat_use_warm_start=True, cp_sat_fallback_to_greedy=request.solver == "cpsat" and request.greedy_fallback,
    )
    adapter = DualCoreGateOptimizerAdapter(solver_config)

    def convert(items):
        return adapter.turns_to_flights(items, departure_model_id=config.departure_model_id,
                                       arrival_model_id=config.arrival_model_id)

    gates = [Gate(gate_id=f"G{i + 1:03d}", gate_index=i, capacity=1,
                  resource_type=GateResourceType.CONTACT_GATE) for i in range(request.contact_gates)]
    gates += [Gate(gate_id=f"R{i + 1:03d}", gate_index=request.contact_gates + i, capacity=1,
                   resource_type=GateResourceType.FINITE_REMOTE_STAND, is_overflow=True)
              for i in range(request.remote_gates)]
    # A schedule-only simulated reference, not observed airport gate assignments.
    baseline = DeterministicGreedyGateSolver(solver_config).solve(
        convert(build_turns({fid: 0.0 for fid in lookup})), gates, allow_overflow=bool(request.remote_gates))
    nominal = {fid: assignment.gate_id for fid, assignment in baseline.assignments.items()
               if assignment.gate_id in {gate.gate_id for gate in gates}}
    turns = [replace(turn, nominal_gate_id=nominal.get(turn.turn_id)) for turn in turns]
    flights = convert(turns)
    progress("optimization")
    solver = {"cpsat": CPSatGateSolver, "greedy": DeterministicGreedyGateSolver,
              "hybrid": HybridGateSolver}[request.solver](solver_config)
    solved = solver.solve(flights, gates, allow_overflow=bool(request.remote_gates))
    progress("verification")
    diagnostic = verify_hard_constraints_independently(flights, gates, solved.assignments)
    if solved.feasible and not diagnostic.is_valid:
        raise ValueError("Nghiệm bị loại vì không vượt qua kiểm tra ràng buộc độc lập.")
    finite_gates = {gate.gate_id for gate in gates}
    assignments = [assignment.to_dict() for assignment in solved.assignments.values()
                   if assignment.gate_id in finite_gates] if solved.feasible else []
    turns_rows = []
    for turn in turns:
        probs = [p["probability_delay_15"] for p in prediction_rows
                 if p["flight_id"] in (turn.arrival_leg_id, turn.departure_leg_id)
                 and p.get("probability_delay_15") is not None]
        turns_rows.append({**turn.to_dict(), "nominal_gate_id": turn.nominal_gate_id,
                           "is_estimated": not turn.pair_type in (PairType.INFERRED_PAIR, PairType.VERIFIED_PAIR),
                           "probability_delay_15": max(probs) if probs else None})
    comparisons = [(p["actual_delay_min"], p["predicted_delay_min"]) for p in prediction_rows
                   if p["actual_delay_min"] is not None]
    errors = np.array([pred - actual for actual, pred in comparisons])
    events = sorted([(f.occupancy_start_min, 1) for f in flights]
                    + [(f.occupancy_end_min, -1) for f in flights])
    active = peak = 0
    for _, change in events:
        active += change
        peak = max(peak, active)
    warnings = ["Quy mô/cổng là giả định thử nghiệm, không phải cấu hình thực tế ATL.",
                "Phân cổng cố định; không mô phỏng kéo tàu từ bãi xa vào cổng.",
                "Ngày vận hành không bao gồm tàu đã đỗ từ ngày trước nếu raw không có bằng chứng; chuyến lẻ dùng dwell giả định.",
                "Khoảng chiếm dụng có thể kéo sang ngày liền kề; không cắt tại 00:00."]
    if request.service_date.year > 2023:
        warnings.append("Dữ liệu ngoài giai đoạn phát triển mô hình; chưa có bảo đảm chất lượng dự báo cho năm này.")
    if any(t["is_estimated"] for t in turns_rows):
        warnings.append("Có chuyến lẻ: khoảng chiếm dụng được giả định, không phải quan sát thực tế.")
    if not baseline.feasible:
        warnings.append("Phương án tham chiếu lịch bay không đầy đủ; chỉ đếm tái phân bổ ở lượt có cổng tham chiếu.")
    if not solved.feasible:
        warnings.append("Chưa có nghiệm khả thi. Xem trạng thái bộ giải; thử tăng cổng/bãi xa hoặc điều chỉnh giả định.")
    if peak > len(gates):
        warnings.append(f"Đỉnh nhu cầu {peak} vị trí lớn hơn tổng năng lực {len(gates)}; cần ít nhất {peak - len(gates)} vị trí bổ sung với các khoảng chiếm dụng hiện tại.")
    fallback_used = bool(solved.solver_configuration.get("fallback_used", False))
    actual_solver = {"greedy": "Deterministic Greedy", "cpsat": "CP-SAT", "hybrid": "Hybrid (CP-SAT/Greedy → SA)"}[request.solver]
    if request.solver == "cpsat" and fallback_used:
        actual_solver = "Deterministic Greedy (CP-SAT fallback)"
        warnings.append("CP-SAT chưa có nghiệm trong ngân sách: dùng Greedy đã xác minh theo tùy chọn fallback. Đây không phải nghiệm do CP-SAT chứng minh tối ưu.")
    summary = {
        "movement_count": len(selected), "arrivals": int(selected.direction.eq("ARR").sum()),
        "departures": int(selected.direction.eq("DEP").sum()), "occupancy_count": len(turns),
        "estimated_occupancies": sum(t["is_estimated"] for t in turns_rows),
        "paired_occupancies": sum(p.is_paired for p in pairs), "peak_occupancy": peak,
        "contact_gates": request.contact_gates, "remote_gates": request.remote_gates,
        "assigned_count": len(assignments), "remote_count": sum(a["is_overflow"] for a in assignments),
        "reassignments": sum(a["is_reassignment"] for a in assignments),
        "baseline_covered": len(nominal), "baseline_kind": "SIMULATED_SCHEDULE_GREEDY",
        "solver_status": solved.status, "feasible": solved.feasible, "optimality_proven": solved.optimality_proven,
        "actual_solver": actual_solver, "fallback_used": fallback_used,
        "raw_solver_status": solved.solver_configuration.get("raw_solver_status", solved.solver_configuration.get("cp_solver_status", solved.status)),
        "independent_verifier_valid": diagnostic.is_valid, "conflicts": diagnostic.conflict_count,
        "solver_runtime_sec": round(solved.runtime_ms / 1000, 3),
        "decision_cost": solved.objective_breakdown.decision_cost if solved.feasible else None,
        "comparison_count": len(comparisons), "mae": float(np.abs(errors).mean()) if len(errors) else None,
        "rmse": float(np.sqrt((errors ** 2).mean())) if len(errors) else None,
    }
    model_metadata = {key: {"model_id": entry["spec"].model_id, "status": entry["spec"].status,
                           "version": entry["spec"].artifact_version, **entry["meta"]}
                      for key, entry in models.items()}
    manifest = {"pipeline": "UPLOAD_NATIVE_INFERENCE_V1", "created_at": datetime.now(timezone.utc).isoformat(),
        "config": request.model_dump(mode="json"), "seed": 202601, "source": source_manifest,
        "models": model_metadata, "summary": summary, "warnings": warnings,
        "pairing": [asdict(pair) for pair in pairs], "diagnostic": diagnostic.to_dict(),
        "solver_configuration": finite_metadata(solved.solver_configuration),
        "information_regime": "SCHEDULE_ONLY_HISTORICAL_BATCH", "time_basis": "ML_PREDICTED",
        "data_origin": "USER_UPLOADED_UNVERIFIED", "prediction_source": "NATIVE_INFERENCE",
        "reference_timezone": "America/New_York", "timeline_basis": "elapsed minutes from service midnight UTC"}
    manifest["reference_midnight_utc"] = datetime.combine(request.service_date, time(), ZoneInfo("America/New_York")).astimezone(timezone.utc).isoformat()
    result = {"summary": summary, "predictions": prediction_rows, "turns": turns_rows,
              "assignments": assignments, "gates": [{"gate_id": gate.gate_id, "is_remote": gate.is_overflow}
                                                     for gate in gates], "manifest": manifest}
    progress("export")
    # Frozen numeric problem shared by every downstream experiment. Preserve
    # full precision distribution parameters independently of rounded UI values.
    from src.simulation.native_dual_core_pipeline import prepare_arrival_features_for_inference
    arrival_frame = features.loc[features.direction.eq("ARR")].reset_index(drop=True)
    marginals = {}
    if not arrival_frame.empty:
        arrival_x, _ = prepare_arrival_features_for_inference(arrival_frame)
        distribution = models['arrival']['model'].predict_distribution(arrival_x)
        for i, fid in enumerate(arrival_frame.flight_key):
            marginals[fid] = {key: float(distribution[key][i]) for key in ('mu', 'sigma', 'df')}
    snapshot = {'version': 1, 'flights': [f.to_dict() for f in flights],
                'gates': [g.to_dict() for g in gates], 'solver_config': asdict(solver_config),
                'marginals': marginals, 'pairing': manifest['pairing'],
                'predictions': {fid: float(value) for fid, value in lookup.items()},
                'config': request.model_dump(mode='json'), 'models': model_metadata}
    snapshot['hash'] = hashlib.sha256(json.dumps(snapshot, sort_keys=True, allow_nan=False).encode()).hexdigest()
    json_write(output / 'snapshot.json', snapshot)
    manifest['snapshot_hash'] = snapshot['hash']
    selected.to_parquet(output / "normalized.parquet", index=False)
    for name, data in (("predictions", prediction_rows), ("occupancies", turns_rows), ("assignments", assignments)):
        table = pd.DataFrame(data)
        table.to_csv(output / f"{name}.csv", index=False)
        table.to_parquet(output / f"{name}.parquet", index=False)
    json_write(output / "manifest.json", manifest)
    json_write(output / "result.json", result)
    with zipfile.ZipFile(output / "bundle.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output.iterdir()):
            if path.name != "bundle.zip" and path.suffix in (".json", ".csv", ".parquet"):
                archive.write(path, path.name)
    return result
