"""Test Suite for AEOLUS V4 Task R30: Final Evidence Reconciliation.

Verifies:
1. test_all_domains_have_status
2. test_all_claims_reconciled
3. test_exact_13_claims
4. test_no_contradictory_point_selection
5. test_2024_post_holdout
6. test_p4_p5_role_separation
7. test_scalar_downstream_semantics
8. test_synthetic_environment_boundary
9. test_oracle_language_boundary
10. test_crn_claim_boundary
11. test_mc_n_optimality_boundary
12. test_reproducibility_claim_boundary
13. test_weather_boundary
14. test_departure_boundary
15. test_actual_outcome_boundary
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import pandas as pd
import pytest
from typing import Final

ROOT = Path(__file__).resolve().parents[1]

RECON_PATH: Final = ROOT / "artifacts" / "audit" / "r30_final_evidence_reconciliation.json"
RECON_SIDECAR: Final = ROOT / "artifacts" / "audit" / "r30_final_evidence_reconciliation.json.sha256"

PARQUET_PATH: Final = ROOT / "artifacts" / "audit" / "r30_final_status_matrix.parquet"
PARQUET_SIDECAR: Final = ROOT / "artifacts" / "audit" / "r30_final_status_matrix.parquet.sha256"

DOC_PATH: Final = ROOT / "docs" / "audit" / "R30_FINAL_EVIDENCE_RECONCILIATION.md"
DOC_SIDECAR: Final = ROOT / "docs" / "audit" / "R30_FINAL_EVIDENCE_RECONCILIATION.md.sha256"

EXPECTED_18_DOMAINS: Final[set[str]] = {
    "Core Arrival point prediction",
    "Core Arrival probabilistic prediction",
    "Auxiliary Departure",
    "Weather",
    "Flight Chain",
    "Temporal governance",
    "Statistical inference",
    "Point model selection",
    "Probabilistic model selection",
    "Synthetic Turn",
    "Gate Simulation",
    "Greedy",
    "CP-SAT",
    "SA",
    "CP-SAT + SA",
    "Monte Carlo",
    "Reproducibility",
    "Certification tests",
}

EXPECTED_13_CLAIM_IDS: Final[tuple[str, ...]] = (
    "CLAIM_01_TEMPORAL_POST_HOLDOUT",
    "CLAIM_02_POINT_CHAMPION_SELECTION",
    "CLAIM_03_PROBABILISTIC_P5_CRPS",
    "CLAIM_04_PROBABILISTIC_P4_STUDENT_T",
    "CLAIM_05_SINGLE_OVERALL_CHAMPION",
    "CLAIM_06_CRN_VARIANCE_REDUCTION",
    "CLAIM_07_MC_N500_OPTIMALITY",
    "CLAIM_08_REAL_WORLD_GATE_OPERATIONS",
    "CLAIM_09_ORACLE_EQUIVALENCE",
    "CLAIM_10_DOWNSTREAM_SEMANTICS",
    "CLAIM_11_STATISTICAL_SIGNIFICANCE",
    "CLAIM_12_AUXILIARY_DEPARTURE_DELAY",
    "CLAIM_13_REPRODUCIBILITY_STANDARDS",
)

VALID_STATUSES: Final[set[str]] = {"PASS", "LIMITED", "BLOCKED"}


def compute_sha256(path: Path) -> str:
    """Read actual raw bytes and compute hexadecimal SHA-256."""
    assert path.is_file(), f"File does not exist: {path}"
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def recon_data() -> dict:
    assert RECON_PATH.is_file(), f"Missing reconciliation: {RECON_PATH}"
    return json.loads(RECON_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def status_df() -> pd.DataFrame:
    assert PARQUET_PATH.is_file(), f"Missing parquet: {PARQUET_PATH}"
    return pd.read_parquet(PARQUET_PATH)


# =============================================================================
# MANDATORY 15 TESTS FOR R30
# =============================================================================

def test_all_domains_have_status(recon_data, status_df):
    """1. Verify all 18 domains have a valid status and complete audit fields."""
    domains = recon_data["domains"]
    assert set(domains.keys()) == EXPECTED_18_DOMAINS
    assert recon_data["summary"]["total_domains_audited"] == 18
    assert len(status_df) == 18

    for d_name, d_info in domains.items():
        assert d_info["status"] in VALID_STATUSES
        assert d_info["evidence_path"], f"Domain {d_name} missing evidence_path"
        assert d_info["evidence_hash"], f"Domain {d_name} missing evidence_hash"
        assert d_info["source_run_id"], f"Domain {d_name} missing source_run_id"
        assert d_info["limitations"], f"Domain {d_name} missing limitations"
        assert d_info["allowed_claims"], f"Domain {d_name} missing allowed_claims"
        assert d_info["forbidden_claims"], f"Domain {d_name} missing forbidden_claims"

        ev_path = ROOT / d_info["evidence_path"]
        assert ev_path.exists(), f"Evidence path missing on disk: {ev_path} for domain {d_name}"


def test_all_claims_reconciled(recon_data):
    """2. Verify all 13 claims have complete reconciliation fields and audit history."""
    claims = recon_data["claims"]
    assert len(claims) == 13

    for cid, c in claims.items():
        assert c["claim_id"] == cid
        assert c["exact_current_wording"], f"Claim {cid} missing wording"
        assert c["status"], f"Claim {cid} missing status"
        assert c["supporting_artifact"], f"Claim {cid} missing supporting artifact"
        assert c["supporting_run"], f"Claim {cid} missing supporting run"
        assert c["evidence_strength"], f"Claim {cid} missing evidence strength"
        assert c["allowed_scope"], f"Claim {cid} missing allowed scope"
        assert c["prohibited_scope"], f"Claim {cid} missing prohibited scope"
        assert c["post_R25_change"], f"Claim {cid} missing post_R25_change"
        assert c["post_R26_change"], f"Claim {cid} missing post_R26_change"
        assert c["post_R27_change"], f"Claim {cid} missing post_R27_change"
        assert c["post_R28_change"], f"Claim {cid} missing post_R28_change"
        assert c["post_R29_change"], f"Claim {cid} missing post_R29_change"


def test_exact_13_claims(recon_data):
    """3. Verify exactly 13 claim IDs exist with no duplicates or omissions."""
    claims = recon_data["claims"]
    assert tuple(claims.keys()) == EXPECTED_13_CLAIM_IDS
    assert recon_data["summary"]["total_claims_reconciled"] == 13
    assert recon_data["summary"]["zero_duplicate_claims"] is True
    assert recon_data["summary"]["zero_missing_claims"] is True
    assert recon_data["summary"]["zero_unclassified_claims"] is True


def test_no_contradictory_point_selection(recon_data):
    """4. Enforce: 2023 dev tie vs 2024 holdout non-tie; no single overall point champion."""
    c2 = recon_data["claims"]["CLAIM_02_POINT_CHAMPION_SELECTION"]
    assert "tie within the 0.10 min indifference band on the 2023 model selection slice" in c2["exact_current_wording"]
    assert "2024 post-holdout, the difference is 0.4050 min (> 0.10 min) and models are not tied" in c2["exact_current_wording"]
    assert "no single overall point champion is asserted" in c2["exact_current_wording"]

    pt_bounds = recon_data["epistemological_boundaries"]["point_selection"]
    assert pt_bounds["dev_2023_status"] == "TIED_WITHIN_INDIFFERENCE_BAND"
    assert pt_bounds["dev_2023_delta_min"] == 0.00045
    assert pt_bounds["holdout_2024_status"] == "NOT_TIED"
    assert pt_bounds["holdout_2024_delta_min"] == 0.4050
    assert pt_bounds["single_overall_point_champion_allowed"] is False

    # Single overall champion must remain BLOCKED
    c5 = recon_data["claims"]["CLAIM_05_SINGLE_OVERALL_CHAMPION"]
    assert c5["status"] == "BLOCKED"


def test_2024_post_holdout(recon_data):
    """5. Enforce: 2024 is strictly post-holdout, not untouched or blind."""
    c1 = recon_data["claims"]["CLAIM_01_TEMPORAL_POST_HOLDOUT"]
    assert c1["status"] == "CORRECTED"
    assert "POST_HOLDOUT protocol governance" in c1["exact_current_wording"]
    assert "zero parameter, hyperparameter, or threshold adaptation" in c1["exact_current_wording"]

    prohibited = c1["prohibited_scope"].lower()
    assert "untouched" in prohibited
    assert "never-before-seen" in prohibited
    assert "pristine" in prohibited


def test_p4_p5_role_separation(recon_data):
    """6. Enforce: P4 continuous density (not certified calibrated) vs P5 discrete quantiles."""
    c3 = recon_data["claims"]["CLAIM_03_PROBABILISTIC_P5_CRPS"]
    assert "continuous density is not available" in c3["exact_current_wording"]
    assert "P5 provides a full continuous predictive density" in c3["prohibited_scope"]

    c4 = recon_data["claims"]["CLAIM_04_PROBABILISTIC_P4_STUDENT_T"]
    assert "empirical calibration is not separately certified" in c4["exact_current_wording"]
    assert "P4 is an empirically certified calibrated distribution" in c4["prohibited_scope"]

    p_bounds = recon_data["epistemological_boundaries"]["probabilistic_capabilities"]
    assert p_bounds["P4_student_t"]["calibration_certified"] is False
    assert p_bounds["P4_student_t"]["calibration_status"] == "NOT_SEPARATELY_CERTIFIED"
    assert p_bounds["P5_quantile"]["continuous_density"] is False
    assert p_bounds["P5_quantile"]["exact_continuous_nll"] is False


def test_scalar_downstream_semantics(recon_data):
    """7. Enforce: Downstream operates strictly under SCALAR_FORECAST_IMPACT."""
    c10 = recon_data["claims"]["CLAIM_10_DOWNSTREAM_SEMANTICS"]
    assert "SCALAR_FORECAST_IMPACT" in c10["exact_current_wording"]
    assert "Full uncertainty-aware downstream optimization" in c10["prohibited_scope"]
    assert recon_data["epistemological_boundaries"]["downstream_semantics"] == "SCALAR_FORECAST_IMPACT"


def test_synthetic_environment_boundary(recon_data):
    """8. Enforce: Simulation claims bounded to synthetic scenarios; no real airfield claims."""
    c8 = recon_data["claims"]["CLAIM_08_REAL_WORLD_GATE_OPERATIONS"]
    assert "simulated synthetic research environment" in c8["exact_current_wording"]
    assert "Real airfield deployment at ATL" in c8["prohibited_scope"]
    assert "Operational savings for Delta Air Lines" in c8["prohibited_scope"]


def test_oracle_language_boundary(recon_data):
    """9. Enforce: Oracle is non-deployable analytical reference; no predictive equivalence."""
    c9 = recon_data["claims"]["CLAIM_09_ORACLE_EQUIVALENCE"]
    assert "Oracle remains an acausal, non-deployable theoretical reference" in c9["exact_current_wording"]
    assert "Equivalent to Oracle" in c9["prohibited_scope"]
    assert "Predictive equivalence to Oracle" in c9["prohibited_scope"]


def test_crn_claim_boundary(recon_data):
    """10. Enforce: CRN variance reduction claim is marked NOT_SUPPORTED / NOT_ESTABLISHED."""
    c6 = recon_data["claims"]["CLAIM_06_CRN_VARIANCE_REDUCTION"]
    assert c6["status"] == "NOT_SUPPORTED"
    assert "NOT_ESTABLISHED" in c6["exact_current_wording"]
    assert "82.4% variance reduction proven" in c6["prohibited_scope"]
    assert recon_data["epistemological_boundaries"]["monte_carlo_crn"] == "NOT_ESTABLISHED"


def test_mc_n_optimality_boundary(recon_data):
    """11. Enforce: N=500 is operational choice only, not mathematically optimal."""
    c7 = recon_data["claims"]["CLAIM_07_MC_N500_OPTIMALITY"]
    assert c7["status"] == "NOT_SUPPORTED"
    assert "operational choice, not an optimal sample size" in c7["exact_current_wording"]
    assert "N=500 is mathematically optimal" in c7["prohibited_scope"]
    assert recon_data["epistemological_boundaries"]["monte_carlo_optimal_n"] == "OPERATIONAL_CHOICE_ONLY"


def test_reproducibility_claim_boundary(recon_data):
    """12. Enforce: Certified With Limitations; no 100% reproducibility claims."""
    c13 = recon_data["claims"]["CLAIM_13_REPRODUCIBILITY_STANDARDS"]
    assert "Certified With Limitations" in c13["exact_current_wording"]
    assert "100% reproducible" in c13["prohibited_scope"]
    assert "Perfect reproducibility" in c13["prohibited_scope"]
    assert "Meets top-tier ML/OR standards" in c13["prohibited_scope"]
    assert recon_data["epistemological_boundaries"]["reproducibility"] == "CERTIFIED_WITH_LIMITATIONS"


def test_weather_boundary(recon_data):
    """13. Enforce: Weather features are quarantined from Core Arrival (V4 Invariant #1)."""
    weather_dom = recon_data["domains"]["Weather"]
    assert weather_dom["status"] == "LIMITED"
    assert "excluded from Core Arrival" in weather_dom["allowed_claims"]
    assert "Real-time METAR/TAF weather feeds core arrival models" in weather_dom["forbidden_claims"]
    assert recon_data["epistemological_boundaries"]["weather_quarantine"] == "EXCLUDED_FROM_CORE_ARRIVAL"


def test_departure_boundary(recon_data):
    """14. Enforce: Departure delay models quarantined; no feed to arrival gate solver."""
    c12 = recon_data["claims"]["CLAIM_12_AUXILIARY_DEPARTURE_DELAY"]
    assert c12["status"] == "NOT_SUPPORTED"
    assert "strictly isolated research-only benchmarks and do not feed arrival" in c12["exact_current_wording"]
    assert "Departure delay feeds arrival gate solver" in c12["prohibited_scope"]

    dep_dom = recon_data["domains"]["Auxiliary Departure"]
    assert dep_dom["status"] == "LIMITED"
    assert recon_data["epistemological_boundaries"]["departure_quarantine"] == "EXCLUDED_FROM_CORE_ARRIVAL"


def test_actual_outcome_boundary(recon_data):
    """15. Enforce: Arrival predictions use strictly T-2h point-in-time features without actual delays."""
    arr_dom = recon_data["domains"]["Core Arrival point prediction"]
    assert arr_dom["status"] == "PASS"
    assert "T-2h" in arr_dom["allowed_claims"]
    assert recon_data["epistemological_boundaries"]["actual_outcome_quarantine"] == "ZERO_REALIZED_DELAY_LEAKAGE"


# =============================================================================
# INTEGRITY & SIDECAR TESTS
# =============================================================================

def test_r30_artifacts_and_sidecars():
    """Verify all R30 artifacts exist with bitwise valid SHA256 sidecars."""
    artifacts = [
        (RECON_PATH, RECON_SIDECAR),
        (PARQUET_PATH, PARQUET_SIDECAR),
        (DOC_PATH, DOC_SIDECAR),
    ]
    for path, sidecar in artifacts:
        assert path.is_file(), f"Missing file: {path}"
        assert sidecar.is_file(), f"Missing sidecar: {sidecar}"
        actual = compute_sha256(path)
        recorded = sidecar.read_text(encoding="utf-8").strip().split()[0]
        assert actual == recorded, f"Sidecar mismatch on {path.name}: {actual} != {recorded}"
