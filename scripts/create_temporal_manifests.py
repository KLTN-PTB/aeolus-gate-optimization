"""Create the Week-2 canonical temporal manifests and reconstructed 2024 access log."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.temporal_protocol import build_temporal_manifests, build_week2_2024_access_log


def main() -> int:
    build_temporal_manifests(project_root=ROOT)
    build_week2_2024_access_log(project_root=ROOT)
    print("TEMPORAL_MANIFESTS: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
