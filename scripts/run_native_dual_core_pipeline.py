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
from src.data.real_data_loader import (
    DataLoaderMode,
    DataLoadError,
    EmptyDateRangeError,
    MissingPartitionError,
    RealDataLoader,
    SchemaContractViolation,
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
from src.simulation.verified_pairing import (
    DeterministicPairingEngine,
    VerifiedPairingResult,
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
        "--loader-mode",
        type=str,
        default="REAL_ONLY",
        choices=["REAL_ONLY", "ALLOW_SYNTHETIC"],
        help="Data loader mode: REAL_ONLY fails on missing data/synthetic; ALLOW_SYNTHETIC enables test fixtures (default: REAL_ONLY).",
    )
    parser.add_argument(
        "--limit-flights",
        type=int,
        default=50,
        help="Maximum flights to load per direction (default: 50).",
    )
    parser.add_argument(
        "--allow-inferred-pairing",
        action="store_true",
        default=False,
        help="Allow heuristic schedule inference when physical tail is missing (default: False).",
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
    loader_mode: str = "REAL_ONLY",
    allow_inferred_pairing: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, FlightLeg], list[TurnPair]]:
    """Load canonical inbound and outbound flight slices and pair them deterministically."""
    LOGGER.info(f"Loading canonical flight data for {airport} ({start_date} to {end_date}) in mode={loader_mode}...")

    base_dir = data_path if (data_path is not None and data_path.is_dir()) else (ROOT / "data" / "processed")
    loader = RealDataLoader(mode=DataLoaderMode(loader_mode), base_dir=base_dir)

    loaded = loader.load_atl_data(
        year=2023,
        start_date=start_date,
        end_date=end_date,
        limit_legs=limit_flights,
        hub_airport=airport,
    )

    # Deterministic pairing engine
    pairing_engine = DeterministicPairingEngine(hub_airport=airport)
    pairing_res = pairing_engine.pair_flights(
        legs=loaded.legs,
        scenario_id=f"SCEN_{airport}_{start_date}",
        allow_inferred_pairing=allow_inferred_pairing,
    )

    LOGGER.info(
        f"Pairing Complete: {pairing_res.metrics['verified_turns_count']} verified turns, "
        f"{pairing_res.metrics['inferred_turns_count']} inferred turns, "
        f"{pairing_res.metrics['unmatched_arr_count']} unmatched ARR, "
        f"{pairing_res.metrics['unmatched_dep_count']} unmatched DEP"
    )

    return loaded.inbound_df, loaded.outbound_df, loaded.legs, pairing_res.all_pairs


def build_legs_and_pairs_from_frames(
    inbound_df: pd.DataFrame,
    outbound_df: pd.DataFrame,
    airport: str,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, FlightLeg], list[TurnPair]]:
    """Synthesize flight legs and TurnPairs from inbound and outbound dataframes using deterministic pairing."""
    from src.data.canonical_time import build_canonical_scheduled_datetime

    legs: dict[str, FlightLeg] = {}
    inbound_df = inbound_df.reset_index(drop=True)
    outbound_df = outbound_df.reset_index(drop=True)

    if "flight_key" not in inbound_df.columns:
        inbound_df["flight_key"] = [f"LEG_ARR_{i+1:04d}" for i in range(len(inbound_df))]
    if "flight_key" not in outbound_df.columns:
        outbound_df["flight_key"] = [f"LEG_DEP_{i+1:04d}" for i in range(len(outbound_df))]

    for i, row in inbound_df.iterrows():
        fid = str(row["flight_key"])
        t_obj = build_canonical_scheduled_datetime(row["FL_DATE"], row.get("CRS_ARR_TIME", row.get("CRS_DEP_TIME")), airport)
        tail = row.get("TAIL_NUM")
        tail_str = str(tail).strip().upper() if pd.notna(tail) and str(tail).strip() else None
        legs[fid] = FlightLeg(
            flight_id=fid,
            direction=LegDirection.ARR,
            carrier=str(row["OP_CARRIER"]).strip().upper(),
            flight_number=str(row["OP_CARRIER_FL_NUM"]),
            origin=str(row["ORIGIN"]).strip().upper(),
            destination=airport,
            scheduled_event_local=t_obj.local_datetime,
            scheduled_event_utc=t_obj.utc_datetime,
            event_timezone=t_obj.timezone_name,
            scheduled_elapsed_min=float(row.get("CRS_ELAPSED_TIME", 120.0)),
            normalized_timeline_min=t_obj.timeline_minute,
            tail_number=tail_str,
        )

    for i, row in outbound_df.iterrows():
        fid = str(row["flight_key"])
        t_obj = build_canonical_scheduled_datetime(row["FL_DATE"], row.get("CRS_DEP_TIME"), airport)
        tail = row.get("TAIL_NUM")
        tail_str = str(tail).strip().upper() if pd.notna(tail) and str(tail).strip() else None
        legs[fid] = FlightLeg(
            flight_id=fid,
            direction=LegDirection.DEP,
            carrier=str(row["OP_CARRIER"]).strip().upper(),
            flight_number=str(row["OP_CARRIER_FL_NUM"]),
            origin=airport,
            destination=str(row["DEST"]).strip().upper(),
            scheduled_event_local=t_obj.local_datetime,
            scheduled_event_utc=t_obj.utc_datetime,
            event_timezone=t_obj.timezone_name,
            scheduled_elapsed_min=float(row.get("CRS_ELAPSED_TIME", 120.0)),
            normalized_timeline_min=t_obj.timeline_minute,
            tail_number=tail_str,
        )

    engine = DeterministicPairingEngine(hub_airport=airport)
    res = engine.pair_flights(legs, scenario_id="CANONICAL_MATCHED")
    return inbound_df, outbound_df, legs, res.all_pairs

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
        limit_flights=args.limit_flights,
        loader_mode=args.loader_mode,
        allow_inferred_pairing=args.allow_inferred_pairing,
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
