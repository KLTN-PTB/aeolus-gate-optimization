"""Create the 1,500-movement / 150-gate historical replay dashboard scenario."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.simulation.bts_daily_replay import export_replay


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "data/raw/ontime.td.202607.asc")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/simulation")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    result = export_replay(args.source, args.output_dir, overwrite=args.overwrite)
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
