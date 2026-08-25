"""Create the bounded Week-2 Flight Chain structural-audit manifest."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.chain_inspection import audit_chain_archives, write_chain_audit_manifest


def main() -> int:
    manifest = audit_chain_archives(project_root=ROOT)
    output = write_chain_audit_manifest(manifest, project_root=ROOT)
    print(f"CHAIN_STRUCTURE_AUDIT: PASS ({manifest['file_count']} files)")
    print(f"OUTPUT: {output.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
