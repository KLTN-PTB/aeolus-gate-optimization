"""Run the isolated binary classification experiment; never opens a browser."""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Limit nested BLAS/OpenMP before importing numeric packages.
for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(name, "8")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if __name__ == "__main__":
    from src.models.binary_improvement_execution import main
    main()
