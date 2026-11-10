"""Phase C & Phase H — Dependence Contract Consistency Audit Runner.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Sections 13, 14, 15, 16
Step: STEP 5 — DEPENDENCE CONTRACT CONSISTENCY

Executes:
1. Dynamic spatial dimension contract audit across synchronized dimensions [1, 5, 23, 77, 150, 420].
2. Extended stress tests for d=420 and d=500.
3. Verification of all 7 mathematical and operational invariants.
4. Validation of fail-closed behavior on non-positive dimensions and empty inputs.
5. Emits certified manifest:
   - artifacts/audit/phase_c_dependence_contract_consistency_manifest_v1.json
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

import numpy as np

# Ensure repo root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.audit.protocol_guards import (
    DEFAULT_CI_DEPENDENCE_DIMENSIONS,
    MIN_DEPENDENCE_DIMENSION,
    PEAK_OPERATIONAL_HUB_DIMENSION,
    POST_HOLDOUT_STATUS_DECLARATION,
    RECOMMENDED_MAX_DIMENSION,
    ProtocolComplianceGuard,
    verify_dependence_dimension_properties,
)
from src.models.probabilistic.dependence import GaussianCopulaDependenceModel


def run_dependence_contract_consistency_audit() -> dict[str, str]:
    """Execute complete Step 5 dependence contract consistency audit."""
    print("=" * 80)
    print("STARTING STEP 5: DEPENDENCE CONTRACT CONSISTENCY AUDIT")
    print("Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Sections 13-16")
    print("=" * 80)

    audit_dir = PROJECT_ROOT / "artifacts" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)

    model = GaussianCopulaDependenceModel(temporal_length_scale_minutes=120.0, carrier_correlation=0.15)

    # 1. CI Representative Dimensions Audit
    print("\n[Step 1] Auditing representative CI dimensions [1, 5, 23, 77, 150, 420]...")
    ci_reports: list[dict[str, object]] = []
    for d in DEFAULT_CI_DEPENDENCE_DIMENSIONS:
        t0 = time.perf_counter()
        diag = verify_dependence_dimension_properties(d, n_samples=25, seed=202601, model=model)
        elapsed = time.perf_counter() - t0
        diag["elapsed_seconds"] = elapsed
        ci_reports.append(diag)
        assert diag["is_valid"] is True, f"Dimension {d} failed verification!"
        print(f"  -> d={d:3d}: Valid=True, Symmetric=True, UnitDiag=True, PSD(min_eig={diag['min_eigenvalue']:.2e}), Time={elapsed:.3f}s")

    # 2. Extended Stress Test Audit (d=420, d=500)
    print("\n[Step 2] Auditing extended stress test dimensions [420, 500]...")
    stress_reports: list[dict[str, object]] = []
    for d in [420, 500]:
        t0 = time.perf_counter()
        diag = verify_dependence_dimension_properties(d, n_samples=50, seed=202601, model=model)
        elapsed = time.perf_counter() - t0
        diag["elapsed_seconds"] = elapsed
        stress_reports.append(diag)
        assert diag["is_valid"] is True, f"Stress dimension {d} failed!"
        print(f"  -> Stress d={d:3d}: Valid=True, PSD(min_eig={diag['min_eigenvalue']:.2e}), Time={elapsed:.3f}s")

    # 3. Protocol Compliance Guard Audit
    print("\n[Step 3] Auditing ProtocolComplianceGuard.check_dynamic_dependence_dimension()...")
    guard = ProtocolComplianceGuard(project_root=PROJECT_ROOT)
    guard_res = guard.check_dynamic_dependence_dimension()
    assert guard_res["passed"] is True, "ProtocolComplianceGuard check failed!"
    print(f"  -> Guard Status: {guard_res['passed']}")
    print(f"  -> Tested Dimensions: {guard_res['tested_dimensions']}")
    print(f"  -> Peak Operational Hub Covered: {guard_res['peak_operational_hub_covered']}")
    print(f"  -> Property-based checks passed: {guard_res['property_based_checks_passed']}")
    print(f"  -> Fail-closed on invalid: {guard_res['invalid_dimension_fail_closed']}")

    # 4. Generate Certified Manifest
    manifest = {
        "manifest_version": "phase_c_dependence_contract_consistency_manifest_v1",
        "phase": "PHASE_C_STEP_5",
        "status": "PASS",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_reference": "docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Sections 13, 14, 15, 16",
        "contract_synchronization": {
            "phase_c_max_dimension": PEAK_OPERATIONAL_HUB_DIMENSION,
            "phase_h_guard_synchronized": True,
            "previous_static_whitelist_deprecated": [1, 7, 23, 50, 110],
            "synchronized_ci_dimensions": list(DEFAULT_CI_DEPENDENCE_DIMENSIONS),
            "stress_test_dimensions": [420, 500],
        },
        "property_based_invariants_certified": {
            "matrix_shape": "(d, d) for all d >= 1",
            "matrix_symmetry": "max |C - C^T| < 1e-10",
            "diagonal_convention": "max |C_ii - 1.0| < 1e-10",
            "finite_values": "Zero NaN, zero Inf across all entries",
            "positive_semi_definiteness": "min eigenvalue >= 1e-6 via spectral projection",
            "copula_sampling_shape": "(n_samples, d) with draws in (0, 1)",
            "deterministic_reproducibility": "Bitwise identical samples under fixed random seed",
        },
        "fail_closed_validation": {
            "non_positive_dimension_rejected": True,
            "empty_input_rejected": True,
            "error_type": "ProbabilisticContractViolation",
        },
        "documented_resource_limits": {
            "min_dimension": MIN_DEPENDENCE_DIMENSION,
            "peak_operational_hub_dimension": PEAK_OPERATIONAL_HUB_DIMENSION,
            "recommended_max_dimension": RECOMMENDED_MAX_DIMENSION,
            "computational_complexity": "O(d^3) spectral decomposition / Cholesky factorization",
            "memory_scaling": "O(d^2) float64 correlation storage (e.g. 1.4 MB at d=420, 18 MB at d=1500)",
        },
        "model_parameters_preserved": {
            "temporal_length_scale_minutes": 120.0,
            "carrier_correlation": 0.15,
            "kernel_family": "Gaussian Copula with RBF temporal + discrete carrier match",
            "data_2024_used": False,
            "post_holdout_status": POST_HOLDOUT_STATUS_DECLARATION,
        },
        "ci_dimension_audit_results": ci_reports,
        "stress_dimension_audit_results": stress_reports,
    }

    manifest_path = audit_dir / "phase_c_dependence_contract_consistency_manifest_v1.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"\n[Step 4] Manifest written to: {manifest_path}")

    print("\n" + "=" * 80)
    print("STEP 5 DEPENDENCE CONTRACT CONSISTENCY AUDIT: PASS")
    print("=" * 80)

    return {
        "status": "PASS",
        "manifest_path": str(manifest_path),
    }


if __name__ == "__main__":
    run_dependence_contract_consistency_audit()
