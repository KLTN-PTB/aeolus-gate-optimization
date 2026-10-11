"""Command-Line Interface Orchestrator for Native Dual-Core Predict-Then-Optimize Pipeline.

Protocol: Aeolus Dual Core Architecture Protocol V2
Phase: P07 Native Dual-Core Predict-Then-Optimize Pipeline

Usage:
    python scripts/run_native_dual_core_pipeline.py [OPTIONS]

Options:
    --config            Path to pipeline JSON/YAML configuration file.
    --data              Path to canonical flight dataset directory or parquet/CSV file.
    --model-manifest    Path to model manifest JSON.
    --airport           Target hub airport code (default: ATL).
    --start-date        Filter schedule start date (YYYY-MM-DD).
    --end-date          Filter schedule end date (YYYY-MM-DD).
    --prediction-cutoff Operational prediction cutoff in hours before departure (default: 2.0).
    --solver            Solver algorithm: CPSat, Greedy, SimulatedAnnealing, Hybrid (default: CPSat).
    --capacity-policy   Remote stand capacity policy: FINITE, UNBOUNDED, POOLED (default: FINITE).
    --seed              Predetermined deployment random seed (default: 202601).
    --output-dir        Artifact export directory (default: artifacts/remediation/native_dual_core).
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sys
import time
from typing import Any

# Add workspace root to sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from src.contracts.turn_contracts import (
    FlightLeg,
    LegDirection,
    LinkageSource,
    PairType,
    TurnPair,
    ValidationStatus,
)
from src.simulation.dual_prediction_turn import CouplingAssumption, SimulationMode
from src.simulation.native_dual_core_pipeline import (
    DEP_TREE_PREPROCESSOR_PATH,
    DEP_TREE_PREPROCESSOR_SHA256,
    DEP_XGB_CHECKPOINT_PATH,
    DEP_XGB_SHA256,
    NativeDualCorePipeline,
    NativeDualCorePipelineConfig,
    NativeDualCorePipelineResult,
    P4_ARRIVAL_CHECKPOINT_PATH,
    P4_ARRIVAL_SHA256,
    ProvenanceMode,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
LOGGER = logging.getLogger("run_native_dual_core_pipeline")

DEFAULT_OUTPUT_DIR: Path = ROOT / "artifacts" / "remediation" / "native_dual_core"


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Native Dual-Core Predict-Then-Optimize Pipeline (P07)."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to pipeline configuration JSON file.",
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=None,
        help="Path to canonical flight dataset directory or file.",
    )
    parser.add_argument(
        "--model-manifest",
        type=Path,
        default=None,
        help="Path to model manifest JSON file.",
    )
    parser.add_argument(
        "--airport",
        type=str,
        default="ATL",
        help="Target hub airport code (default: ATL).",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default="2023-11-23",
        help="Filter start date YYYY-MM-DD (default: 2023-11-23).",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default="2023-11-23",
        help="Filter end date YYYY-MM-DD (default: 2023-11-23).",
    )
    parser.add_argument(
        "--prediction-cutoff",
        type=float,
        default=2.0,
        help="Prediction cutoff hours before departure (default: 2.0).",
    )
    parser.add_argument(
        "--solver",
        type=str,
        default="CPSat",
        choices=["CPSat", "Greedy", "SimulatedAnnealing", "Hybrid"],
        help="Solver algorithm (default: CPSat).",
    )
    parser.add_argument(
        "--capacity-policy",
        type=str,
        default="FINITE",
        choices=["FINITE", "UNBOUNDED", "POOLED"],
        help="Remote overflow stand capacity policy (default: FINITE).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=202601,
        help="Predetermined random seed (default: 202601).",
    )
    parser.add_argument(
        "--simulation-mode",
        type=str,
        default="DUAL_POINT",
        choices=["DUAL_POINT", "ARRIVAL_ONLY_LEGACY", "DUAL_PROBABILISTIC"],
        help="Turn simulation mode (default: DUAL_POINT).",
    )
    parser.add_argument(
        "--n-gates",
        type=int,
        default=20,
        help="Number of contact gates (default: 20).",
    )
    parser.add_argument(
        "--max-overflow",
        type=int,
        default=5,
        help="Maximum remote overflow stands (default: 5).",
    )
    parser.add_argument(
        "--time-limit",
        type=float,
        default=5.0,
        help="Ceiling solver time limit in seconds (default: 5.0).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory to save run artifacts (default: {DEFAULT_OUTPUT_DIR}).",
    )
    return parser.parse_args()


def load_canonical_data_slices(
    data_path: Path | None,
    airport: str,
    start_date: str,
    end_date: str,
    limit_flights: int = 50,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, FlightLeg], list[TurnPair]]:
    """Load canonical inbound and outbound flight slices and pair them into turns."""
    LOGGER.info(f"Loading canonical flight data for {airport} ({start_date} to {end_date})...")

    # Locate canonical processed parquet directories
    inbound_dir = ROOT / "data" / "processed" / "inbound_atl" / "year=2023"
    outbound_dir = ROOT / "data" / "processed" / "outbound_atl" / "year=2023"

    if data_path is not None and data_path.exists():
        if (data_path / "inbound_atl").exists():
            inbound_dir = data_path / "inbound_atl" / "year=2023"
            outbound_dir = data_path / "outbound_atl" / "year=2023"
        elif data_path.suffix == ".parquet":
            df_custom = pd.read_parquet(data_path)
            inbound_df = df_custom[df_custom["DEST"] == airport].copy().head(limit_flights)
            outbound_df = df_custom[df_custom["ORIGIN"] == airport].copy().head(limit_flights)
            return build_legs_and_pairs_from_frames(inbound_df, outbound_df, airport)

    # Read native 2023 parquet files
    if not inbound_dir.exists() or not outbound_dir.exists():
        LOGGER.warning("Processed parquet partitions not found, building synthetic canonical slice...")
        return build_synthetic_canonical_data(limit_flights, airport)

    df_in = pd.read_parquet(inbound_dir)
    df_out = pd.read_parquet(outbound_dir)

    # Filter date
    df_in["FL_DATE_STR"] = df_in["FL_DATE"].astype(str).str.slice(0, 10)
    df_out["FL_DATE_STR"] = df_out["FL_DATE"].astype(str).str.slice(0, 10)

    in_slice = df_in[(df_in["FL_DATE_STR"] >= start_date) & (df_in["FL_DATE_STR"] <= end_date)]
    out_slice = df_out[(df_out["FL_DATE_STR"] >= start_date) & (df_out["FL_DATE_STR"] <= end_date)]

    if in_slice.empty or out_slice.empty:
        LOGGER.warning("No records found in date window, taking first available slice...")
        in_slice = df_in.head(limit_flights)
        out_slice = df_out.head(limit_flights)
    else:
        in_slice = in_slice.head(limit_flights)
        out_slice = out_slice.head(limit_flights)

    return build_legs_and_pairs_from_frames(in_slice, out_slice, airport)


def build_legs_and_pairs_from_frames(
    inbound_df: pd.DataFrame,
    outbound_df: pd.DataFrame,
    airport: str,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, FlightLeg], list[TurnPair]]:
    """Synthesize flight legs and TurnPairs from inbound and outbound dataframes."""
    legs: dict[str, FlightLeg] = {}
    pairs: list[TurnPair] = []

    inbound_df = inbound_df.reset_index(drop=True)
    outbound_df = outbound_df.reset_index(drop=True)

    n_pairs = min(len(inbound_df), len(outbound_df))

    # Match turns by pairing index
    for i in range(n_pairs):
        in_row = inbound_df.iloc[i]
        out_row = outbound_df.iloc[i]

        arr_id = f"LEG_ARR_{i+1:04d}"
        dep_id = f"LEG_DEP_{i+1:04d}"
        pair_id = f"TURN_{i+1:04d}"

        # Parse schedule clock
        dep_ts_in = pd.to_datetime(in_row["CRS_DEP_TIME"])
        arr_ts_in = dep_ts_in + pd.Timedelta(minutes=float(in_row.get("CRS_ELAPSED_TIME", 120.0)))
        arr_clock_min = arr_ts_in.hour * 60 + arr_ts_in.minute

        dep_ts_out = pd.to_datetime(out_row["CRS_DEP_TIME"])
        dep_clock_min = dep_ts_out.hour * 60 + dep_ts_out.minute
        # Ensure chronological feasibility for matched turn
        turnaround_slack = 75
        if dep_clock_min <= arr_clock_min + 45:
            dep_clock_min = arr_clock_min + turnaround_slack
        dep_event_local = arr_ts_in + pd.Timedelta(minutes=dep_clock_min - arr_clock_min)

        # Check for matching tail number if present
        tail_in = in_row.get("TAIL_NUM") or in_row.get("OP_CARRIER_FL_NUM")
        tail_out = out_row.get("TAIL_NUM") or out_row.get("OP_CARRIER_FL_NUM")
        is_same_airframe = (tail_in == tail_out) and pd.notna(tail_in)

        arr_leg = FlightLeg(
            flight_id=arr_id,
            direction=LegDirection.ARR,
            carrier=str(in_row["OP_CARRIER"]),
            flight_number=str(in_row["OP_CARRIER_FL_NUM"]),
            origin=str(in_row["ORIGIN"]),
            destination=airport,
            scheduled_event_local=arr_ts_in.to_pydatetime(),
            scheduled_elapsed_min=float(in_row.get("CRS_ELAPSED_TIME", 120.0)),
            normalized_timeline_min=arr_clock_min,
            tail_number=str(tail_in) if pd.notna(tail_in) else None,
        )
        dep_leg = FlightLeg(
            flight_id=dep_id,
            direction=LegDirection.DEP,
            carrier=str(out_row["OP_CARRIER"]),
            flight_number=str(out_row["OP_CARRIER_FL_NUM"]),
            origin=airport,
            destination=str(out_row["DEST"]),
            scheduled_event_local=dep_event_local.to_pydatetime(),
            scheduled_elapsed_min=float(out_row.get("CRS_ELAPSED_TIME", 120.0)),
            normalized_timeline_min=dep_clock_min,
            tail_number=str(tail_out) if pd.notna(tail_out) else None,
        )

        legs[arr_id] = arr_leg
        legs[dep_id] = dep_leg

        pair_type = PairType.VERIFIED_PAIR if is_same_airframe else PairType.SYNTHETIC_PAIR
        pairs.append(
            TurnPair(
                pair_id=pair_id,
                arrival_leg_id=arr_id,
                departure_leg_id=dep_id,
                pair_type=pair_type,
                linkage_source=LinkageSource.VERIFIED_ROTATION if is_same_airframe else LinkageSource.SIMULATION_SESSION,
                validation_status=ValidationStatus.VALID,
                scheduled_turnaround_min=float(dep_clock_min - arr_clock_min),
                scenario_id="SCEN_2023_CANONICAL",
            )
        )

    # Attach flight_key to dataframes for alignment
    inbound_df["flight_key"] = [f"LEG_ARR_{i+1:04d}" for i in range(len(inbound_df))]
    outbound_df["flight_key"] = [f"LEG_DEP_{i+1:04d}" for i in range(len(outbound_df))]

    return inbound_df.head(n_pairs), outbound_df.head(n_pairs), legs, pairs


def build_synthetic_canonical_data(
    n_turns: int,
    airport: str,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, FlightLeg], list[TurnPair]]:
    """Build synthetic canonical fixture when disk parquet is unavailable."""
    in_records: list[dict[str, Any]] = []
    out_records: list[dict[str, Any]] = []
    legs: dict[str, FlightLeg] = {}
    pairs: list[TurnPair] = []

    for i in range(n_turns):
        arr_id = f"SYNTH_ARR_{i+1:04d}"
        dep_id = f"SYNTH_DEP_{i+1:04d}"
        pair_id = f"SYNTH_TURN_{i+1:04d}"

        sched_arr_min = 360 + (i * 25)
        sched_dep_min = sched_arr_min + 75

        carrier = ["DL", "AA", "UA", "WN"][i % 4]
        fl_num = f"{1000 + i}"

        in_records.append({
            "flight_key": arr_id,
            "FL_DATE": "2023-11-23 00:00:00",
            "OP_CARRIER": carrier,
            "OP_CARRIER_FL_NUM": fl_num,
            "ORIGIN": "ORD",
            "DEST": airport,
            "CRS_DEP_TIME": f"2023-11-23 {sched_arr_min // 60:02d}:{sched_arr_min % 60:02d}:00",
            "CRS_ELAPSED_TIME": 120.0,
            "MONTH": 11,
            "DAY_OF_MONTH": 23,
            "DAY_OF_WEEK": 4,
        })

        out_records.append({
            "flight_key": dep_id,
            "FL_DATE": "2023-11-23 00:00:00",
            "OP_CARRIER": carrier,
            "OP_CARRIER_FL_NUM": fl_num,
            "ORIGIN": airport,
            "DEST": "LGA",
            "CRS_DEP_TIME": f"2023-11-23 {sched_dep_min // 60:02d}:{sched_dep_min % 60:02d}:00",
            "CRS_ELAPSED_TIME": 120.0,
            "MONTH": 11,
            "DAY_OF_MONTH": 23,
            "DAY_OF_WEEK": 4,
        })

        legs[arr_id] = FlightLeg(
            flight_id=arr_id,
            direction=LegDirection.ARR,
            carrier=carrier,
            flight_number=fl_num,
            origin="ORD",
            destination=airport,
            scheduled_event_local=datetime(2023, 11, 23, sched_arr_min // 60, sched_arr_min % 60),
            normalized_timeline_min=sched_arr_min,
        )
        legs[dep_id] = FlightLeg(
            flight_id=dep_id,
            direction=LegDirection.DEP,
            carrier=carrier,
            flight_number=fl_num,
            origin=airport,
            destination="LGA",
            scheduled_event_local=datetime(2023, 11, 23, sched_dep_min // 60, sched_dep_min % 60),
            normalized_timeline_min=sched_dep_min,
        )

        pairs.append(
            TurnPair(
                pair_id=pair_id,
                arrival_leg_id=arr_id,
                departure_leg_id=dep_id,
                pair_type=PairType.SYNTHETIC_PAIR,
                linkage_source=LinkageSource.SIMULATION_SESSION,
                validation_status=ValidationStatus.VALID,
                scheduled_turnaround_min=75.0,
                scenario_id="SYNTH_SCENARIO",
            )
        )

    return pd.DataFrame(in_records), pd.DataFrame(out_records), legs, pairs


def main() -> int:
    args = parse_arguments()
    LOGGER.info("=" * 70)
    LOGGER.info("PHASE P07: NATIVE DUAL-CORE PREDICT-THEN-OPTIMIZE PIPELINE")
    LOGGER.info("=" * 70)

    # 1. Resolve capacity policy
    allow_overflow = True
    max_overflow = args.max_overflow
    pooled_remote = False
    if args.capacity_policy == "UNBOUNDED":
        max_overflow = None
    elif args.capacity_policy == "POOLED":
        pooled_remote = True

    # 2. Build Pipeline Configuration
    pipeline_cfg = NativeDualCorePipelineConfig(
        airport=args.airport,
        simulation_mode=SimulationMode(args.simulation_mode),
        solver_name=args.solver,
        time_limit_seconds=args.time_limit,
        random_seed=args.seed,
        n_contact_gates=args.n_gates,
        allow_overflow=allow_overflow,
        max_overflow=max_overflow,
        pooled_remote=pooled_remote,
    )

    # Override config from JSON file if provided
    if args.config is not None and args.config.exists():
        LOGGER.info(f"Loading external configuration file: {args.config}")
        with open(args.config, "r", encoding="utf-8") as f:
            custom_cfg = json.load(f)
            for k, v in custom_cfg.items():
                if hasattr(pipeline_cfg, k):
                    setattr(pipeline_cfg, k, v)

    # 3. Load Flight Data
    inbound_df, outbound_df, legs, pairs = load_canonical_data_slices(
        data_path=args.data,
        airport=args.airport,
        start_date=args.start_date,
        end_date=args.end_date,
        limit_flights=30,
    )

    LOGGER.info(
        f"Input Data Summary: Inbound={len(inbound_df)} flights, "
        f"Outbound={len(outbound_df)} flights, Turn Pairs={len(pairs)}"
    )

    # 4. Instantiate & Run Pipeline
    pipeline = NativeDualCorePipeline(config=pipeline_cfg)
    result: NativeDualCorePipelineResult = pipeline.run(
        inbound_df=inbound_df,
        outbound_df=outbound_df,
        legs=legs,
        pairs=pairs,
        output_dir=args.output_dir,
    )

    # 5. Export Test Report
    test_report = {
        "report_id": "P07_NATIVE_DUAL_CORE_INTEGRATION_REPORT",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if result.optimization_result.feasible and result.constraint_diagnostic.is_valid else "FAIL",
        "provenance_mode": result.config.provenance_mode.value,
        "solver": result.config.solver_name,
        "feasible": result.optimization_result.feasible,
        "hard_constraints_valid": result.constraint_diagnostic.is_valid,
        "objective_value": result.optimization_result.objective_value,
        "re_evaluated_objective": result.re_evaluated_objective,
        "runtime_ms": result.optimization_result.runtime_ms,
        "summary": {
            "flights_assigned": len(result.optimization_result.assignments),
            "contact_assignments": result.constraint_diagnostic.contact_count,
            "remote_assignments": result.constraint_diagnostic.remote_count,
            "unassigned_count": result.constraint_diagnostic.unassigned_count,
            "planned_conflicts": result.constraint_diagnostic.conflict_count,
            "reassignments": result.manifest["optimization"]["reassignments_count"],
        },
    }
    with open(args.output_dir / "integration_test_report.json", "w", encoding="utf-8") as f:
        json.dump(test_report, f, indent=2)

    # 6. Report Verdict
    LOGGER.info("=" * 70)
    LOGGER.info("EXECUTION SUMMARY & VERDICT")
    LOGGER.info("=" * 70)
    LOGGER.info(f"Solver Status:          {result.optimization_result.status}")
    LOGGER.info(f"Feasible:               {result.optimization_result.feasible}")
    LOGGER.info(f"Objective Value:        {result.optimization_result.objective_value:.4f}")
    LOGGER.info(f"Re-evaluated Objective: {result.re_evaluated_objective:.4f}")
    LOGGER.info(f"Verifier Status:        {'PASS' if result.constraint_diagnostic.is_valid else 'FAIL'}")
    LOGGER.info(f"Conflicts Count:        {result.constraint_diagnostic.conflict_count}")
    LOGGER.info(f"Hard Violations Count:  {result.constraint_diagnostic.hard_constraint_violations_count}")
    LOGGER.info(f"Artifacts Saved To:     {args.output_dir}")
    LOGGER.info("=" * 70)

    return 0 if (result.optimization_result.feasible and result.constraint_diagnostic.is_valid) else 1


if __name__ == "__main__":
    sys.exit(main())
