"""Turnaround and Gate Occupancy Simulator for Aeolus Gate Optimization.

This module converts raw/scenario flight records (inbound and outbound) into
coherent airport gate occupancy sessions (Turns / Dwell intervals) by:
1. Coupling inbound (ARR) and outbound (DEP) flights into synthetic turnaround pairs
   (same carrier, compatible aircraft type, minimum turnaround buffer).
2. Handling unmatched flights (overnight arrivals, early morning departures) as single-leg dwell sessions.
3. Calculating 3 distinct gate occupancy windows for every session:
   - Schedule Baseline: [A_sched, D_sched]
   - ML-Predicted (Dual Flow): [A_pred, max(D_sched, D_pred_direct, A_pred + T_turn) + B_risk]
   - Ground Truth (Actual BTS): [A_actual, D_actual]
4. Producing clean, standardized datasets ready for CP-SAT, Greedy, and Metaheuristic gate solvers.
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final, Optional

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT: Final = Path(__file__).resolve().parent.parent.parent
DEFAULT_SCENARIOS_DIR: Final = REPO_ROOT / "src" / "artifacts" / "scenarios"


@dataclass
class GateOccupancySession:
    """Represents a discrete gate occupancy demand interval at the airport."""

    session_id: str
    sim_aircraft_id: str
    session_type: str  # "PAIRED_TURN", "UNMATCHED_ARR", "UNMATCHED_DEP"
    carrier: str
    aircraft_type: str  # "NARROWBODY" or "WIDEBODY"
    turnaround_time_min: int
    dwell_time_min: int

    # Flight identifiers
    arr_flight_key: Optional[str]
    dep_flight_key: Optional[str]
    arr_fl_num: Optional[int]
    dep_fl_num: Optional[int]
    origin: Optional[str]
    dest: Optional[str]
    chain_group_id: Optional[str]

    # Mode 1: Schedule Baseline (Minute of day: 0..1439)
    sched_start_min: int
    sched_end_min: int
    sched_duration_min: int

    # Mode 2: ML-Predicted (Dual Flow)
    pred_start_min: int
    pred_end_min: int
    pred_duration_min: int
    risk_buffer_min: int
    p_delay_max: float
    arr_delay_est_min: float
    dep_delay_est_min: float

    # Mode 3: Ground Truth (Actual BTS operations)
    actual_start_min: int
    actual_end_min: int
    actual_duration_min: int
    arr_true_delay_min: float
    dep_true_delay_min: float


class TurnaroundSimulator:
    """Couples inbound and outbound flights and simulates gate occupancy intervals."""

    def __init__(
        self,
        min_narrowbody_turnaround: int = 40,
        min_widebody_turnaround: int = 75,
        default_dwell_time: int = 45,
        max_turn_window_min: int = 240,  # Max allowable turn connection (4 hours)
        risk_buffer_multiplier: float = 15.0,  # B_risk = round(15 * p_delay)
    ) -> None:
        self.min_narrowbody_turn = min_narrowbody_turnaround
        self.min_widebody_turn = min_widebody_turnaround
        self.default_dwell_time = default_dwell_time
        self.max_turn_window_min = max_turn_window_min
        self.risk_buffer_multiplier = risk_buffer_multiplier

    def simulate_from_dataframe(self, df_flights: pd.DataFrame) -> pd.DataFrame:
        """Process flight DataFrame and return standard gate occupancy sessions."""
        logger.info("Bắt đầu mô phỏng ghép cặp và tính cửa sổ đỗ cổng cho %d chuyến bay...", len(df_flights))

        arr_df = df_flights[df_flights["direction"] == "ARR"].copy().sort_values("sched_arr_min")
        dep_df = df_flights[df_flights["direction"] == "DEP"].copy().sort_values("sched_dep_min")

        used_arr_keys: set[str] = set()
        used_dep_keys: set[str] = set()
        sessions: list[GateOccupancySession] = []
        turn_counter = 0

        # Phase 1: High-affinity pairing via exact chain_group_id
        for chain_id, group in df_flights.groupby("chain_group_id"):
            g_arr = group[group["direction"] == "ARR"]
            g_dep = group[group["direction"] == "DEP"]
            if len(g_arr) == 1 and len(g_dep) == 1:
                a_row = g_arr.iloc[0]
                d_row = g_dep.iloc[0]
                t_turn = int(a_row.get("turnaround_time_min", self.min_narrowbody_turn))
                arr_t = int(a_row["sched_arr_min"])
                dep_t = int(d_row["sched_dep_min"])

                # Valid connection check
                if (arr_t + t_turn <= dep_t) and (dep_t - arr_t <= self.max_turn_window_min):
                    turn_counter += 1
                    session = self._create_paired_session(
                        turn_counter=turn_counter,
                        arr_row=a_row,
                        dep_row=d_row,
                    )
                    sessions.append(session)
                    used_arr_keys.add(str(a_row["flight_key"]))
                    used_dep_keys.add(str(d_row["flight_key"]))

        logger.info("  ✓ Đã ghép cặp chuỗi chính xác (chain_group_id): %d cặp", turn_counter)

        # Phase 2: Chronological Carrier + Aircraft Type pairing for remaining flights
        rem_arr = arr_df[~arr_df["flight_key"].isin(used_arr_keys)].sort_values("sched_arr_min")
        rem_dep = dep_df[~dep_df["flight_key"].isin(used_dep_keys)].sort_values("sched_dep_min")
        carrier_pairs_count = 0

        for _, a_row in rem_arr.iterrows():
            arr_key = str(a_row["flight_key"])
            if arr_key in used_arr_keys:
                continue

            t_turn = int(a_row.get("turnaround_time_min", self.min_narrowbody_turn))
            min_dep_t = int(a_row["sched_arr_min"]) + t_turn
            max_dep_t = int(a_row["sched_arr_min"]) + self.max_turn_window_min

            # Find matching outbound candidates
            cands = rem_dep[
                (~rem_dep["flight_key"].isin(used_dep_keys))
                & (rem_dep["carrier"] == a_row["carrier"])
                & (rem_dep["aircraft_type"] == a_row["aircraft_type"])
                & (rem_dep["sched_dep_min"] >= min_dep_t)
                & (rem_dep["sched_dep_min"] <= max_dep_t)
            ]

            if not cands.empty:
                # Greedy earliest feasible departure
                d_row = cands.iloc[0]
                dep_key = str(d_row["flight_key"])

                turn_counter += 1
                carrier_pairs_count += 1
                session = self._create_paired_session(
                    turn_counter=turn_counter,
                    arr_row=a_row,
                    dep_row=d_row,
                )
                sessions.append(session)
                used_arr_keys.add(arr_key)
                used_dep_keys.add(dep_key)

        logger.info("  ✓ Đã ghép cặp cùng Hãng & Loại tàu bay: %d cặp", carrier_pairs_count)
        logger.info("  -> Tổng số cặp quay đầu hoàn chỉnh: %d cặp (%d chuyến bay)", turn_counter, turn_counter * 2)

        # Phase 3: Unmatched Inbound (Overnight arrivals / late flights)
        unmatched_arr = arr_df[~arr_df["flight_key"].isin(used_arr_keys)]
        unmatched_arr_count = 0
        for _, a_row in unmatched_arr.iterrows():
            turn_counter += 1
            unmatched_arr_count += 1
            session = self._create_unmatched_arr_session(turn_counter=turn_counter, arr_row=a_row)
            sessions.append(session)

        # Phase 4: Unmatched Outbound (Early morning departures / origin flights)
        unmatched_dep = dep_df[~dep_df["flight_key"].isin(used_dep_keys)]
        unmatched_dep_count = 0
        for _, d_row in unmatched_dep.iterrows():
            turn_counter += 1
            unmatched_dep_count += 1
            session = self._create_unmatched_dep_session(turn_counter=turn_counter, dep_row=d_row)
            sessions.append(session)

        logger.info("  ✓ Chuyến đến đơn lẻ (Overnight ARR): %d lượt", unmatched_arr_count)
        logger.info("  ✓ Chuyến đi đơn lẻ (Early DEP): %d lượt", unmatched_dep_count)
        logger.info("=> TỔNG CỘNG LƯỢT ĐỖ CỔNG (Gate Sessions): %d lượt", len(sessions))

        # Convert to DataFrame and sort chronologically by scheduled start time
        df_sessions = pd.DataFrame([asdict(s) for s in sessions])
        df_sessions = df_sessions.sort_values(by=["sched_start_min", "session_id"]).reset_index(drop=True)
        return df_sessions

    def _create_paired_session(
        self,
        turn_counter: int,
        arr_row: pd.Series,
        dep_row: pd.Series,
    ) -> GateOccupancySession:
        """Compute occupancy bounds for a paired turnaround (ARR + DEP)."""
        session_id = f"TURN_{turn_counter:04d}"
        sim_aircraft_id = f"SIM_AC_{turn_counter:04d}"
        carrier = str(arr_row["carrier"])
        ac_type = str(arr_row["aircraft_type"])
        t_turn = int(max(arr_row.get("turnaround_time_min", self.min_narrowbody_turn),
                         dep_row.get("turnaround_time_min", self.min_narrowbody_turn)))
        t_dwell = int(arr_row.get("dwell_time_min", self.default_dwell_time))

        # 1. Mode 1: Schedule
        sched_start = int(arr_row["sched_arr_min"])
        sched_end = int(dep_row["sched_dep_min"])
        if sched_end <= sched_start:
            sched_end = sched_start + t_turn
        sched_dur = sched_end - sched_start

        # 2. Mode 2: ML Predicted (Dual Flow Predict & Optimize)
        a_pred = int(arr_row["predicted_arr_min"])
        d_pred_direct = int(dep_row["predicted_dep_min"])
        d_turn_min = a_pred + t_turn
        # Final predicted departure considers scheduled time, direct dep delay, and turnaround chain
        d_pred = max(sched_end, d_pred_direct, d_turn_min)

        p_delay = float(max(arr_row.get("p_delay", 0.0), dep_row.get("p_delay", 0.0)))
        b_risk = int(np.round(self.risk_buffer_multiplier * p_delay))

        pred_start = a_pred
        pred_end = d_pred + b_risk
        pred_dur = pred_end - pred_start

        # 3. Mode 3: Ground Truth (Actual BTS)
        act_start = int(arr_row["actual_arr_min"])
        act_end = int(dep_row["actual_dep_min"])
        if act_end <= act_start:
            act_end = act_start + t_turn
        act_dur = act_end - act_start

        return GateOccupancySession(
            session_id=session_id,
            sim_aircraft_id=sim_aircraft_id,
            session_type="PAIRED_TURN",
            carrier=carrier,
            aircraft_type=ac_type,
            turnaround_time_min=t_turn,
            dwell_time_min=t_dwell,
            arr_flight_key=str(arr_row["flight_key"]),
            dep_flight_key=str(dep_row["flight_key"]),
            arr_fl_num=int(arr_row["fl_num"]),
            dep_fl_num=int(dep_row["fl_num"]),
            origin=str(arr_row["origin"]),
            dest=str(dep_row["dest"]),
            chain_group_id=str(arr_row.get("chain_group_id", "")),
            sched_start_min=sched_start,
            sched_end_min=sched_end,
            sched_duration_min=sched_dur,
            pred_start_min=pred_start,
            pred_end_min=pred_end,
            pred_duration_min=pred_dur,
            risk_buffer_min=b_risk,
            p_delay_max=round(p_delay, 4),
            arr_delay_est_min=float(arr_row.get("delay_est_min", 0.0)),
            dep_delay_est_min=float(dep_row.get("delay_est_min", 0.0)),
            actual_start_min=act_start,
            actual_end_min=act_end,
            actual_duration_min=act_dur,
            arr_true_delay_min=float(arr_row.get("arr_delay_min", 0.0)),
            dep_true_delay_min=float(dep_row.get("dep_delay_min", 0.0)),
        )

    def _create_unmatched_arr_session(
        self,
        turn_counter: int,
        arr_row: pd.Series,
    ) -> GateOccupancySession:
        """Create dwell session for an unmatched inbound flight."""
        session_id = f"TURN_{turn_counter:04d}"
        sim_aircraft_id = f"SIM_AC_{turn_counter:04d}"
        carrier = str(arr_row["carrier"])
        ac_type = str(arr_row["aircraft_type"])
        t_turn = int(arr_row.get("turnaround_time_min", self.min_narrowbody_turn))
        t_dwell = int(arr_row.get("dwell_time_min", self.default_dwell_time))

        p_delay = float(arr_row.get("p_delay", 0.0))
        b_risk = int(np.round(self.risk_buffer_multiplier * p_delay))

        # Sched
        sched_start = int(arr_row["sched_arr_min"])
        sched_end = min(1439, sched_start + t_dwell)

        # Pred
        pred_start = int(arr_row["predicted_arr_min"])
        pred_end = min(1439, pred_start + t_dwell + b_risk)

        # Actual
        act_start = int(arr_row["actual_arr_min"])
        act_end = min(1439, act_start + t_dwell)

        return GateOccupancySession(
            session_id=session_id,
            sim_aircraft_id=sim_aircraft_id,
            session_type="UNMATCHED_ARR",
            carrier=carrier,
            aircraft_type=ac_type,
            turnaround_time_min=t_turn,
            dwell_time_min=t_dwell,
            arr_flight_key=str(arr_row["flight_key"]),
            dep_flight_key=None,
            arr_fl_num=int(arr_row["fl_num"]),
            dep_fl_num=None,
            origin=str(arr_row["origin"]),
            dest="ATL",
            chain_group_id=str(arr_row.get("chain_group_id", "")),
            sched_start_min=sched_start,
            sched_end_min=sched_end,
            sched_duration_min=sched_end - sched_start,
            pred_start_min=pred_start,
            pred_end_min=pred_end,
            pred_duration_min=pred_end - pred_start,
            risk_buffer_min=b_risk,
            p_delay_max=round(p_delay, 4),
            arr_delay_est_min=float(arr_row.get("delay_est_min", 0.0)),
            dep_delay_est_min=0.0,
            actual_start_min=act_start,
            actual_end_min=act_end,
            actual_duration_min=act_end - act_start,
            arr_true_delay_min=float(arr_row.get("arr_delay_min", 0.0)),
            dep_true_delay_min=0.0,
        )

    def _create_unmatched_dep_session(
        self,
        turn_counter: int,
        dep_row: pd.Series,
    ) -> GateOccupancySession:
        """Create pre-service dwell session for an unmatched outbound flight."""
        session_id = f"TURN_{turn_counter:04d}"
        sim_aircraft_id = f"SIM_AC_{turn_counter:04d}"
        carrier = str(dep_row["carrier"])
        ac_type = str(dep_row["aircraft_type"])
        t_turn = int(dep_row.get("turnaround_time_min", self.min_narrowbody_turn))
        t_dwell = int(dep_row.get("dwell_time_min", self.default_dwell_time))

        p_delay = float(dep_row.get("p_delay", 0.0))
        b_risk = int(np.round(self.risk_buffer_multiplier * p_delay))

        # Sched
        sched_end = int(dep_row["sched_dep_min"])
        sched_start = max(0, sched_end - t_dwell)

        # Pred
        d_pred = int(dep_row["predicted_dep_min"])
        pred_end = min(1439, d_pred + b_risk)
        pred_start = max(0, d_pred - t_dwell)

        # Actual
        act_end = int(dep_row["actual_dep_min"])
        act_start = max(0, act_end - t_dwell)

        return GateOccupancySession(
            session_id=session_id,
            sim_aircraft_id=sim_aircraft_id,
            session_type="UNMATCHED_DEP",
            carrier=carrier,
            aircraft_type=ac_type,
            turnaround_time_min=t_turn,
            dwell_time_min=t_dwell,
            arr_flight_key=None,
            dep_flight_key=str(dep_row["flight_key"]),
            arr_fl_num=None,
            dep_fl_num=int(dep_row["fl_num"]),
            origin="ATL",
            dest=str(dep_row["dest"]),
            chain_group_id=str(dep_row.get("chain_group_id", "")),
            sched_start_min=sched_start,
            sched_end_min=sched_end,
            sched_duration_min=sched_end - sched_start,
            pred_start_min=pred_start,
            pred_end_min=pred_end,
            pred_duration_min=pred_end - pred_start,
            risk_buffer_min=b_risk,
            p_delay_max=round(p_delay, 4),
            arr_delay_est_min=0.0,
            dep_delay_est_min=float(dep_row.get("delay_est_min", 0.0)),
            actual_start_min=act_start,
            actual_end_min=act_end,
            actual_duration_min=act_end - act_start,
            arr_true_delay_min=0.0,
            dep_true_delay_min=float(dep_row.get("dep_delay_min", 0.0)),
        )


def process_scenario_to_sessions(
    scenario_path: Path,
    output_path: Optional[Path] = None,
) -> Path:
    """Read a standardized scenario parquet and generate turnaround sessions parquet."""
    if not scenario_path.exists():
        raise FileNotFoundError(f"Scenario not found: {scenario_path}")

    logger.info("Nạp dữ liệu kịch bản: %s", scenario_path.name)
    df = pd.read_parquet(scenario_path)

    simulator = TurnaroundSimulator()
    df_sessions = simulator.simulate_from_dataframe(df)

    if output_path is None:
        out_name = scenario_path.stem + "_turnaround_sessions.parquet"
        output_path = scenario_path.parent / out_name

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_sessions.to_parquet(output_path, index=False)
    logger.info("✓ ĐÃ XUẤT THÀNH CÔNG %d LƯỢT ĐỖ CỔNG TẠI: %s", len(df_sessions), output_path)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate gate occupancy sessions from ATL scenario.")
    parser.add_argument(
        "--scenario",
        type=str,
        default=str(DEFAULT_SCENARIOS_DIR / "atl_2024_01_01_full_day_1500_flights.parquet"),
        help="Path to scenario parquet file.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path to save output turnaround sessions parquet.",
    )
    args = parser.parse_args()

    scen_path = Path(args.scenario)
    out_path = Path(args.output) if args.output else None
    process_scenario_to_sessions(scen_path, out_path)


if __name__ == "__main__":
    main()
