"""Build an auditable gate-assignment replay from BTS ASQP pipe-delimited records.

Observed gate-in/out times are hindsight inputs, never ML predictions. Aircraft
linkage is inferred from consecutive, same-tail events; actual gate IDs are absent.
"""

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from src.data.time_normalization import AIRPORT_IANA_TIMEZONES
from src.optimization.domain import Flight, Gate, GateResourceType


SCENARIO_ID = "SCEN_2026_07_01_1500_MOVEMENTS_150_GATES"
SERVICE_DATE = "2026-07-01"
SEED = 202601
MIN_TURN_MINUTES = 30
MAX_TURN_MINUTES = 720
BUFFER_MINUTES = 15
# Scenario topology only: these labels do not assert the real gate inventory.
CONCOURSE_CAPACITIES = {"T": 21, "A": 29, "B": 32, "C": 34, "D": 34}


def load_atl_events(source: Path, service_date: str = SERVICE_DATE) -> tuple[list[dict], dict]:
    """Normalize scheduled/actual ATL gate events, including next-day departures.

    Arrival dates are reconstructed from origin-local departure, its IANA zone,
    scheduled elapsed time and signed arrival delay. Unknown timezones, cancelled
    flights and diversions are excluded explicitly, without guessed dates.
    """
    midnight = datetime.fromisoformat(service_date).replace(tzinfo=ZoneInfo("America/New_York"))
    source_dates = {(midnight + timedelta(days=d)).strftime("%Y%m%d") for d in (0, 1)}
    counts = Counter()
    events = []
    with source.open(encoding="ascii") as stream:
        for line in stream:
            row = line.rstrip("\r\n").split("|")
            if len(row) != 71:
                raise ValueError("Expected 71 fields in the BTS ASQP release")
            if row[8] not in source_dates or "ATL" not in (row[6], row[7]):
                continue
            counts["source_atl_records"] += 1
            if row[29].strip() or row[38].strip() not in ("", "0"):
                counts["cancelled_or_diverted"] += 1
                continue
            if not row[25].strip():
                counts["missing_tail"] += 1
                continue
            if row[6] not in AIRPORT_IANA_TIMEZONES:
                counts[f"unknown_origin_timezone_{row[6]}"] += 1
                continue
            departure = datetime.strptime(row[8], "%Y%m%d").replace(
                tzinfo=ZoneInfo(AIRPORT_IANA_TIMEZONES[row[6]])
            ) + timedelta(minutes=int(row[11]) // 100 * 60 + int(row[11]) % 100)
            direction = "DEP" if row[6] == "ATL" else "ARR"
            scheduled = departure.astimezone(timezone.utc)
            if direction == "ARR":
                scheduled += timedelta(minutes=int(row[18]))
            scheduled = scheduled.astimezone(midnight.tzinfo)
            delay = int(row[20] if direction == "DEP" else row[21])
            actual = scheduled + timedelta(minutes=delay)
            clock = int(row[12] if direction == "DEP" else row[15]) % 2400
            if actual.hour * 100 + actual.minute != clock:
                counts["actual_clock_mismatch"] += 1
                continue
            events.append({
                "movement_id": "BTS_" + hashlib.sha256(line.encode("ascii")).hexdigest()[:20],
                "source_flight_date": row[8],
                "direction": direction,
                "carrier": row[4] or row[0],
                "marketing_carrier": row[0],
                "flight_number": row[5] or row[1],
                "origin": row[6], "destination": row[7],
                "tail_number": row[25].strip().upper(),
                "scheduled_event_local": scheduled.isoformat(),
                "actual_event_local": actual.isoformat(),
                "scheduled_event_min": int((scheduled - midnight).total_seconds() // 60),
                "actual_event_min": int((actual - midnight).total_seconds() // 60),
                "actual_delay_min": delay,
            })
    counts["eligible_atl_events_in_local_day"] = sum(0 <= e["actual_event_min"] < 1440 for e in events)
    return events, dict(counts)


def infer_complete_turns(events: list[dict]) -> list[dict]:
    """Match adjacent ARR->DEP events of one tail, without reusing flight legs."""
    by_tail = defaultdict(list)
    for event in events:
        by_tail[event["tail_number"]].append(event)
    turns = []
    for tail in sorted(by_tail):
        ordered = sorted(by_tail[tail], key=lambda e: (e["actual_event_min"], e["movement_id"]))
        for arrival, departure in zip(ordered, ordered[1:]):
            dwell = departure["actual_event_min"] - arrival["actual_event_min"]
            if (
                arrival["direction"] == "ARR" and departure["direction"] == "DEP"
                and arrival["carrier"] == departure["carrier"]
                and 0 <= arrival["actual_event_min"] < departure["actual_event_min"] < 1440
                and MIN_TURN_MINUTES <= dwell <= MAX_TURN_MINUTES
            ):
                turns.append({"arrival": arrival, "departure": departure, "tail_number": tail})
    return sorted(turns, key=lambda t: t["arrival"]["movement_id"])


def select_turns(turns: list[dict], count: int, seed: int = SEED) -> list[dict]:
    """Sample complete turns proportionally by carrier and arrival hour."""
    if len(turns) < count:
        raise ValueError(f"Only {len(turns)} eligible complete turns, need {count}")
    groups = defaultdict(list)
    for turn in turns:
        arrival = turn["arrival"]
        groups[(arrival["carrier"], arrival["actual_event_min"] // 60)].append(turn)
    for group in groups.values():
        group.sort(key=lambda t: t["arrival"]["movement_id"])
    keys = sorted(groups)
    exact = {key: len(groups[key]) * count / len(turns) for key in keys}
    quotas = {key: int(exact[key]) for key in keys}
    for key in sorted(keys, key=lambda k: (-(exact[k] - quotas[k]), k))[:count - sum(quotas.values())]:
        quotas[key] += 1
    rng = np.random.default_rng(seed)
    selected = []
    for key in keys:
        indices = rng.choice(len(groups[key]), quotas[key], replace=False)
        selected.extend(groups[key][int(i)] for i in sorted(indices))
    return sorted(selected, key=lambda t: (t["arrival"]["actual_event_min"], t["arrival"]["movement_id"]))


def peak_occupancy(flights: list[Flight]) -> int:
    events = sorted(
        [(f.occupancy_start_min, 1) for f in flights]
        + [(f.occupancy_end_min, -1) for f in flights]
    )
    current = peak = 0
    for _, delta in events:
        current += delta
        peak = max(peak, current)
    return peak


def build_replay(source: Path, *, turn_count: int = 750, seed: int = SEED) -> tuple[pd.DataFrame, pd.DataFrame, list[Gate], dict]:
    events, audit = load_atl_events(source)
    candidates = infer_complete_turns(events)
    selected = select_turns(candidates, turn_count, seed)
    gates = [
        Gate(f"{concourse}{number:02d}", index, resource_type=GateResourceType.CONTACT_GATE)
        for index, (concourse, number) in enumerate(
            (concourse, n) for concourse, capacity in CONCOURSE_CAPACITIES.items()
            for n in range(1, capacity + 1)
        )
    ]
    # Construct a synthetic nominal allocation from schedules, before observing delays.
    calendars = {g.gate_id: [] for g in gates}
    nominal = {}
    nominal_fallbacks = 0
    for turn in sorted(selected, key=lambda t: (t["arrival"]["scheduled_event_min"], t["arrival"]["movement_id"])):
        arrival, departure = turn["arrival"], turn["departure"]
        start = arrival["scheduled_event_min"]
        end = max(departure["scheduled_event_min"], start + MIN_TURN_MINUTES) + BUFFER_MINUTES
        free = [g for g in gates if all(end <= a or start >= b for a, b in calendars[g.gate_id])]
        if not free:
            nominal_fallbacks += 1
        gate = min(free or gates, key=lambda g: (len(calendars[g.gate_id]), g.gate_index))
        calendars[gate.gate_id].append((start, end))
        nominal[arrival["movement_id"]] = gate.gate_id

    rows, movements = [], []
    for index, turn in enumerate(selected):
        arrival, departure = turn["arrival"], turn["departure"]
        turn_id = f"ATL260701_TURN_{index + 1:04d}"
        flight = Flight(
            flight_id=turn_id, flight_index=index, carrier=arrival["carrier"],
            flight_number=f"{arrival['flight_number']}/{departure['flight_number']}",
            scheduled_arrival_min=arrival["scheduled_event_min"],
            scheduled_departure_min=departure["scheduled_event_min"],
            predicted_arrival_min=arrival["actual_event_min"],
            precomputed_gate_out_min=departure["actual_event_min"],
            min_turnaround_min=MIN_TURN_MINUTES,
            default_dwell_min=max(MIN_TURN_MINUTES, departure["scheduled_event_min"] - arrival["scheduled_event_min"]),
            buffer_min=BUFFER_MINUTES, is_paired=True,
            nominal_gate_id=nominal[arrival["movement_id"]],
        )
        rows.append({**flight.to_dict(), "tail_number": turn["tail_number"],
                     "arrival_leg_id": arrival["movement_id"], "departure_leg_id": departure["movement_id"],
                     "pairing_source": "INFERRED", "time_basis": "HISTORICAL_REPLAY"})
        movements.extend([{**event, "turn_id": turn_id} for event in (arrival, departure)])
    flights = [Flight.from_dict(row) for row in rows]
    peak = peak_occupancy(flights)
    if peak > len(gates):
        raise ValueError(f"Demand {peak} exceeds the requested {len(gates)} finite gates")
    with source.open("rb") as stream:
        source_hash = hashlib.file_digest(stream, "sha256").hexdigest()
    manifest = {
        "scenario_id": SCENARIO_ID, "service_date": SERVICE_DATE, "timezone": "America/New_York",
        "source_path": "data/raw/" + source.name, "source_sha256": source_hash,
        "source_url": "https://www.bts.gov/browse-statistical-products-and-data/bts-publications/airline-service-quality-performance-234-time",
        "seed": seed, "time_basis": "HISTORICAL_REPLAY", "information_regime": "RETROSPECTIVE",
        "prediction_source": "NONE", "data_origin": "REAL_DERIVED", "pairing_source": "INFERRED",
        "source_audit": audit, "eligible_complete_turns": len(candidates),
        "selection": "largest-remainder quotas by operating carrier and actual arrival hour; sample complete turns without replacement",
        "movement_count": len(movements), "arrival_count": turn_count, "departure_count": turn_count,
        "occupancy_count": len(rows), "contact_gate_count": len(gates),
        "concourse_capacities": CONCOURSE_CAPACITIES, "remote_capacity": 0,
        "allow_unbounded_overflow": False, "peak_concurrent_occupancy_with_buffer": peak,
        "minimum_turn_minutes_assumption": MIN_TURN_MINUTES, "buffer_minutes_assumption": BUFFER_MINUTES,
        "nominal_gate_source": "generated from scheduled intervals; not observed BTS gate assignments",
        "nominal_schedule_capacity_fallbacks": nominal_fallbacks,
        "limitations": [
            "750 complete same-day turnarounds are a selected subset, not all ATL movements or overnight parking demand.",
            "BTS domestic reporting coverage; no claim of complete international or cargo coverage.",
            "Same-tail chronological linkage is inferred, not an airport-certified rotation record.",
            "Gate inventory, nominal gates, 30-minute minimum and 15-minute buffer are scenario assumptions.",
            "Gate arrival/departure events are not runway landing/takeoff events.",
            "Actual gate times are hindsight replay inputs; not forecasts, causal decisions, or evidence of ML benefit.",
            "No aircraft type compatibility, airline leasing, towing, or ground-service resource constraints.",
            "June 30 source records are unavailable; only complete within-day turns are selected.",
        ],
    }
    return pd.DataFrame(rows), pd.DataFrame(movements), gates, manifest


def export_replay(source: Path, output_dir: Path, *, overwrite: bool = False) -> dict:
    """Write a new scenario namespace with reproducible lineage and checksums."""
    paths = {name: output_dir / f"{SCENARIO_ID}{suffix}" for name, suffix in {
        "occupancy": ".parquet", "movements": "_movements.parquet",
        "gates": "_gates.json", "manifest": "_manifest.json",
    }.items()}
    if not overwrite and any(p.exists() for p in paths.values()):
        raise FileExistsError("Scenario exists; pass --overwrite to rebuild this scenario explicitly")
    frame, movements, gates, manifest = build_replay(source)
    output_dir.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(paths["occupancy"], index=False)
    movements.to_parquet(paths["movements"], index=False)
    paths["gates"].write_text(json.dumps([g.to_dict() for g in gates], indent=2), encoding="utf-8")
    manifest["artifact_sha256"] = {
        name: hashlib.sha256(paths[name].read_bytes()).hexdigest() for name in ("occupancy", "movements", "gates")
    }
    paths["manifest"].write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest
