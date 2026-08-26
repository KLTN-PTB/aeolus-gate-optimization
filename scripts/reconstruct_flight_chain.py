"""CLI for deterministic schedule-only Flight Chain reconstruction.

The command reads canonical Parquet partitions and never reads raw Flight Chain
``.pt`` archives.  It must run from the repository ``.venv``.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.canonicalize import FLIGHT_KEY_VERSION
from src.data.flight_chain_reconstruction import (
    CHAIN_GROUP_COMPONENTS,
    CHAIN_ID_VERSION,
    DATETIME_STORAGE_AMENDMENT_VERSION,
    PHYSICAL_AIRCRAFT_IDENTITY,
    FlightChainReconstructor,
    assert_output_path_safe,
    assert_project_venv,
)
from src.data.leakage_rules import (
    CORE_WEATHER_POLICY,
    LEAKAGE_COLUMNS,
    TARGET_COLUMNS,
    UNCERTAIN_COLUMNS,
    WEATHER_COLUMNS,
)
from src.data.load_aeolus import load_base_config


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def parse_years(value: str) -> list[int]:
    """Parse comma-separated years/ranges into a sorted unique list."""
    years: set[int] = set()
    for token in (item.strip() for item in value.split(",")):
        if not token:
            raise ValueError("Empty year token")
        if "-" in token:
            parts = token.split("-")
            if len(parts) != 2:
                raise ValueError(f"Invalid year range: {token}")
            start, end = (int(part) for part in parts)
            if start > end:
                raise ValueError(f"Year range must be ascending: {token}")
            years.update(range(start, end + 1))
        else:
            years.add(int(token))
    unsupported = sorted(year for year in years if year not in range(2016, 2025))
    if unsupported:
        raise ValueError(f"Unsupported reconstruction year(s): {unsupported}")
    if not years:
        raise ValueError("At least one reconstruction year is required")
    return sorted(years)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build a schedule/service-number context from canonical Tabular. "
            "This is not a physical aircraft rotation."
        )
    )
    parser.add_argument(
        "--years",
        default="2016-2023",
        help="Comma-separated years/ranges (default: 2016-2023)",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help="Versioned processed-data output root",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and measure without publishing Parquet partitions",
    )
    parser.add_argument(
        "--chunk-size",
        type=_positive_int,
        default=100_000,
        help="Maximum Arrow rows per ingestion batch",
    )
    parser.add_argument(
        "--max-rows",
        type=_positive_int,
        default=None,
        help="Bound source rows per year for a smoke run",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        years = parse_years(args.years)
    except ValueError as error:
        parser.error(str(error))

    assert_project_venv(ROOT)
    config = load_base_config(project_root=ROOT)
    reconstructed_config = config["flight_chain"]["reconstructed"]
    configured_output = Path(reconstructed_config["output_path"])
    output_root = args.output_root or configured_output
    if not output_root.is_absolute():
        output_root = ROOT / output_root
    output_root = assert_output_path_safe(output_root, project_root=ROOT)

    reconstructor = FlightChainReconstructor(
        project_root=ROOT,
        output_root=output_root,
        chunk_size=args.chunk_size,
        max_rows=args.max_rows,
        dry_run=args.dry_run,
    )
    manifest = reconstructor.reconstruct_years(years)
    manifest.update(
        {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "chain_id_version": CHAIN_ID_VERSION,
            "datetime_storage_amendment_version": (
                DATETIME_STORAGE_AMENDMENT_VERSION
            ),
            "flight_key_version": FLIGHT_KEY_VERSION,
            "input_schema_version": "v1",
            "config_version": config["project"]["version"],
            "grouping_contract": {
                "fields": list(CHAIN_GROUP_COMPONENTS),
                "normalization": {
                    "source_year": "integer",
                    "FL_DATE": (
                        "ISO YYYY-MM-DD or exact-midnight canonical timestamp; "
                        "non-midnight timestamp fails closed"
                    ),
                    "OP_CARRIER": "trimmed uppercase string",
                    "OP_CARRIER_FL_NUM": "canonical integral string",
                },
            },
            "ordering_contract": {
                "primary": "scheduled_departure_timestamp(FL_DATE, CRS_DEP_TIME)",
                "crs_dep_time_2400": "next calendar day at 00:00",
                "canonical_timestamp": (
                    "same-service-date non-midnight timestamp accepted"
                ),
                "canonical_midnight": "AMBIGUOUS_CANONICAL_MIDNIGHT; abort year",
                "unexpected_date_relation": (
                    "UNEXPECTED_CANONICAL_DATE_RELATION; abort year"
                ),
                "tie_break_fields": ["ORIGIN", "DEST", "flight_key"],
                "chain_position_base": 0,
            },
            "arrival_schedule_contract": {
                "CRS_ARR_TIME_preserved": True,
                "rollover_inferred": False,
                "duration_derived": False,
                "used_for_ordering": False,
            },
            "leakage_contract": {
                "schedule_only": True,
                "target_columns_excluded": sorted(TARGET_COLUMNS),
                "actual_columns_excluded": sorted(LEAKAGE_COLUMNS),
                "weather_columns_excluded": sorted(WEATHER_COLUMNS),
                "uncertain_columns_excluded": sorted(UNCERTAIN_COLUMNS),
                "FLIGHTS_excluded": True,
                "weather_policy": CORE_WEATHER_POLICY,
                "raw_pt_labels_used": False,
            },
            "physical_aircraft_identity": PHYSICAL_AIRCRAFT_IDENTITY,
        }
    )

    manifest_path: Path | None = None
    if not args.dry_run:
        output_root.mkdir(parents=True, exist_ok=True)
        manifest_path = output_root / "reconstruction_manifest.json"
        temporary_path = manifest_path.with_suffix(".json.tmp")
        temporary_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary_path.replace(manifest_path)

    print(json.dumps(manifest, indent=2, sort_keys=True))
    if manifest_path is not None:
        print(f"MANIFEST: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
