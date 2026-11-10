"""Test Suite for AEOLUS V4 Task R29: Execution Provenance Reconciliation.

Mandatory 14 tests required by V4 Certification Protocol:
1. test_all_required_families_classified
2. test_no_unclassified_runs
3. test_no_false_fresh_execution
4. test_r21_trace_exists
5. test_r21_run_count_reconciles
6. test_r21_to_r22_lineage
7. test_r22_to_r23_lineage
8. test_2024_post_holdout_only
9. test_no_2024_adaptation
10. test_statistics_execution_provenance
11. test_stability_execution_provenance
12. test_monte_carlo_execution_provenance
13. test_cache_hit_policy
14. test_hash_consistency

Plus compatibility tests for legacy test signatures.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]

# R29 Deliverables
PARQUET_PATH = ROOT / "artifacts" / "audit" / "r29_execution_matrix.parquet"
PARQUET_SIDECAR = ROOT / "artifacts" / "audit" / "r29_execution_matrix.parquet.sha256"

RECON_PATH = ROOT / "artifacts" / "audit" / "r29_execution_provenance_reconciliation.json"
RECON_SIDECAR = ROOT / "artifacts" / "audit" / "r29_execution_provenance_reconciliation.json.sha256"

RUN_COUNT_PATH = ROOT / "artifacts" / "audit" / "r29_run_count_reconciliation.json"
RUN_COUNT_SIDECAR = ROOT / "artifacts" / "audit" / "r29_run_count_reconciliation.json.sha256"

CHAIN_PATH = ROOT / "artifacts" / "audit" / "r29_lineage_chain.json"
CHAIN_SIDECAR = ROOT / "artifacts" / "audit" / "r29_lineage_chain.json.sha256"

DOC_PATH = ROOT / "docs" / "audit" / "R29_EXECUTION_PROVENANCE.md"
DOC_SIDECAR = ROOT / "docs" / "audit" / "R29_EXECUTION_PROVENANCE.md.sha256"

MATRIX_PATH = ROOT / "artifacts" / "audit" / "r29_execution_provenance_matrix.json"
CLOSURE_PATH = ROOT / "artifacts" / "audit" / "r29_lineage_closure.json"

# Key external lineage artifacts
R21_TRACE_PATH = ROOT / "artifacts" / "audit" / "r21_execution_trace.json"
FREEZE_MANIFEST_PATH = ROOT / "artifacts" / "manifests" / "system_freeze_manifest_v3.json"
POST_HOLDOUT_PATH = ROOT / "artifacts" / "post_holdout_v3" / "post_holdout_evaluation_manifest_v3.json"
FINAL_CERT_PATH = ROOT / "artifacts" / "manifests" / "final_evidence_certification_v3.json"
R18_STATS_PATH = ROOT / "artifacts" / "r18_paired_statistics_v2.json"
STABILITY_PATH = ROOT / "artifacts" / "manifests" / "probabilistic_stage5_stability_v1.json"

EXPECTED_FAMILIES = {
    "Point",
    "Probabilistic",
    "Statistics",
    "Stability",
    "Selection",
    "Downstream",
    "Monte Carlo",
}


def compute_sha256(path: Path) -> str:
    """Read actual raw bytes and compute hexadecimal SHA-256."""
    assert path.is_file(), f"File does not exist: {path}"
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def recon_data() -> dict:
    assert RECON_PATH.is_file(), f"Missing reconciliation: {RECON_PATH}"
    return json.loads(RECON_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def matrix_data() -> dict:
    assert MATRIX_PATH.is_file(), f"Missing matrix: {MATRIX_PATH}"
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def run_count_data() -> dict:
    assert RUN_COUNT_PATH.is_file(), f"Missing run count: {RUN_COUNT_PATH}"
    return json.loads(RUN_COUNT_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def chain_data() -> dict:
    assert CHAIN_PATH.is_file(), f"Missing chain: {CHAIN_PATH}"
    return json.loads(CHAIN_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def closure_data() -> dict:
    assert CLOSURE_PATH.is_file(), f"Missing closure: {CLOSURE_PATH}"
    return json.loads(CLOSURE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def execution_df() -> pd.DataFrame:
    assert PARQUET_PATH.is_file(), f"Missing parquet: {PARQUET_PATH}"
    return pd.read_parquet(PARQUET_PATH)


# =============================================================================
# MANDATORY 14 TESTS FOR R29
# =============================================================================

def test_all_required_families_classified(recon_data, execution_df):
    """1. Verify all 7 required families are present, classified, and required."""
    families = recon_data["families"]
    assert set(families.keys()) == EXPECTED_FAMILIES
    assert recon_data["summary"]["total_families"] == 7
    assert recon_data["summary"]["required_families"] == 7

    for f_name, f_data in families.items():
        assert f_data["required_for_certification"] is True
        assert f_data["status"] in ["FRESH_EXECUTION", "REUSED_VALID_ARTIFACT"]
        assert f_data["justification"], f"Missing justification for {f_name}"
        assert f_data["code_hashes"], f"Missing code hashes for {f_name}"
        assert f_data["data_hashes"], f"Missing data hashes for {f_name}"

    parquet_families = set(execution_df["family"].unique())
    assert parquet_families == EXPECTED_FAMILIES


def test_no_unclassified_runs(recon_data, run_count_data, execution_df):
    """2. Verify that unclassified runs count is strictly 0 across all artifacts."""
    assert recon_data["summary"]["unclassified_runs_count"] == 0
    assert run_count_data["zero_unclassified_runs"] is True
    assert run_count_data["unclassified_count"] == 0

    assert not execution_df["family"].isnull().any()
    assert not execution_df["status"].isnull().any()
    assert set(execution_df["status"].unique()) == {"FRESH_EXECUTION", "REUSED_VALID_ARTIFACT"}


def test_no_false_fresh_execution(recon_data, execution_df):
    """3. Verify that only Selection, Downstream, and MC are marked FRESH_EXECUTION."""
    families = recon_data["families"]
    assert families["Selection"]["status"] == "FRESH_EXECUTION"
    assert families["Downstream"]["status"] == "FRESH_EXECUTION"
    assert families["Monte Carlo"]["status"] == "FRESH_EXECUTION"

    # Prior fold benchmark models MUST NOT be falsely claimed as fresh executions in R21
    assert families["Point"]["status"] == "REUSED_VALID_ARTIFACT"
    assert families["Probabilistic"]["status"] == "REUSED_VALID_ARTIFACT"
    assert families["Statistics"]["status"] == "REUSED_VALID_ARTIFACT"
    assert families["Stability"]["status"] == "REUSED_VALID_ARTIFACT"

    # Check parquet rows
    fresh_families = set(execution_df[execution_df["status"] == "FRESH_EXECUTION"]["family"].unique())
    assert fresh_families == {"Selection", "Downstream", "Monte Carlo"}

    reused_families = set(execution_df[execution_df["status"] == "REUSED_VALID_ARTIFACT"]["family"].unique())
    assert reused_families == {"Point", "Probabilistic", "Statistics", "Stability"}


def test_r21_trace_exists():
    """4. Verify r21_execution_trace.json exists and has valid PASS status."""
    assert R21_TRACE_PATH.is_file(), f"Missing trace: {R21_TRACE_PATH}"
    trace = json.loads(R21_TRACE_PATH.read_text(encoding="utf-8"))
    assert trace["task_id"] == "R21_TARGETED_DEVELOPMENT_REBUILD_V3"
    assert trace["status"] == "PASS"
    assert "created_at_utc" in trace


def test_r21_run_count_reconciles(recon_data, run_count_data, execution_df):
    """5. Verify the 124 executed runs reconcile exactly without discrepancy."""
    trace = json.loads(R21_TRACE_PATH.read_text(encoding="utf-8"))
    assert trace["summary"]["total_execution_runs_rebuilt"] == 124

    assert run_count_data["reported_rebuilt_runs"] == 124
    assert run_count_data["mathematical_sum_of_decomposed_runs"] == 124
    assert run_count_data["runs_match_reported"] is True

    decomp = run_count_data["decomposition"]
    assert decomp["Selection"]["count"] == 10
    assert decomp["Downstream"]["count"] == 84
    assert decomp["Monte Carlo"]["count"] == 30
    assert decomp["Selection"]["count"] + decomp["Downstream"]["count"] + decomp["Monte Carlo"]["count"] == 124

    assert (execution_df["status"] == "FRESH_EXECUTION").sum() == 124
    assert len(execution_df) == 224


def test_r21_to_r22_lineage(chain_data):
    """6. Verify all rebuilt and reused R21 artifacts are tracked and frozen in R22."""
    assert FREEZE_MANIFEST_PATH.is_file()
    freeze = json.loads(FREEZE_MANIFEST_PATH.read_text(encoding="utf-8"))
    assert freeze["freeze_status"] == "FROZEN_V3"
    assert freeze["total_files_frozen"] == 79
    assert freeze["total_categories"] == 24

    # Check key rebuilt manifests are frozen
    categories = freeze["freeze_categories"]
    sel_files = {f.replace("\\", "/"): h for f, h in categories["H_model_selection"]["files"].items()}
    assert "artifacts/manifests/academic_model_selection_v3.json" in sel_files

    # Check lineage chain claims zero orphaned artifacts and zero unrecorded executions
    assert chain_data["zero_orphaned_artifacts"] is True
    assert chain_data["zero_unrecorded_executions"] is True


def test_r22_to_r23_lineage():
    """7. Verify R23 post-holdout manifest strictly references R22 freeze hash."""
    assert POST_HOLDOUT_PATH.is_file()
    r23 = json.loads(POST_HOLDOUT_PATH.read_text(encoding="utf-8"))
    freeze_sha = compute_sha256(FREEZE_MANIFEST_PATH)

    recorded_freeze_sha = r23.get("freeze_manifest_v3_sha256")
    assert recorded_freeze_sha == freeze_sha, (
        f"R23 freeze manifest SHA mismatch: recorded {recorded_freeze_sha} != actual {freeze_sha}"
    )


def test_2024_post_holdout_only():
    """8. Verify that 2024 was evaluated strictly post-holdout."""
    r23 = json.loads(POST_HOLDOUT_PATH.read_text(encoding="utf-8"))
    assert r23.get("evaluation_role") == "POST_HOLDOUT"
    assert r23.get("holdout_year") == 2024

    freeze = json.loads(FREEZE_MANIFEST_PATH.read_text(encoding="utf-8"))
    assert freeze.get("holdout_policy") == "POST_HOLDOUT_STRICTLY_SEALED"
    assert freeze.get("final_holdout_year") == 2024

    cert = json.loads(FINAL_CERT_PATH.read_text(encoding="utf-8"))
    assert cert["temporal_governance"]["post_holdout_role"] == "POST_HOLDOUT"
    assert cert["temporal_governance"]["post_holdout_year"] == 2024


def test_no_2024_adaptation(chain_data):
    """9. Verify zero model adaptation, training, tuning, or selection on 2024."""
    cert = json.loads(FINAL_CERT_PATH.read_text(encoding="utf-8"))
    tg = cert["temporal_governance"]
    assert tg["zero_2024_retraining_verified"] is True
    assert 2024 not in tg["outer_development_years"]
    assert tg["model_selection_year"] == 2023

    assert chain_data["zero_2024_adaptation"] is True


def test_statistics_execution_provenance(recon_data):
    """10. Verify provenance of the Statistics family (Holm-Bonferroni, 48 families)."""
    assert R18_STATS_PATH.is_file()
    actual_hash = compute_sha256(R18_STATS_PATH)
    assert actual_hash == "8060e97e1cd546e6386966dc2f97da79afdd925bccbd65a7442a355e9d6bad1d"

    stat_fam = recon_data["families"]["Statistics"]
    assert stat_fam["status"] == "REUSED_VALID_ARTIFACT"
    assert stat_fam["expected_run_count"] == 48
    assert stat_fam["hash"] == actual_hash

    stats_list = json.loads(R18_STATS_PATH.read_text(encoding="utf-8"))
    distinct_fams = set(x["correction_family"] for x in stats_list)
    assert len(distinct_fams) == 48


def test_stability_execution_provenance(recon_data):
    """11. Verify provenance of the Stability family (3 seeds x 4 folds = 12 runs)."""
    assert STABILITY_PATH.is_file()
    actual_hash = compute_sha256(STABILITY_PATH)
    assert actual_hash == "d99157f692465d832aef3696591c341408f39ee71132331cec0c36abd2a1a685"

    stab_fam = recon_data["families"]["Stability"]
    assert stab_fam["status"] == "REUSED_VALID_ARTIFACT"
    assert stab_fam["expected_run_count"] == 12
    assert stab_fam["hash"] == actual_hash


def test_monte_carlo_execution_provenance(recon_data):
    """12. Verify Monte Carlo provenance (30 runs, s/sqrt(N), no false variance reduction)."""
    trace = json.loads(R21_TRACE_PATH.read_text(encoding="utf-8"))
    mc_exp = [x for x in trace["rebuilt_experiments"] if x["experiment_id"] == "monte_carlo_convergence_2023"][0]

    assert mc_exp["truncation_applied"] is False
    assert mc_exp["convergence_se_formula"] == "s / sqrt(N)"
    assert mc_exp["fabricated_variance_reduction_claim"] == "REJECTED_MARKED_NOT_ESTABLISHED"
    assert mc_exp["optimal_n_claim"] == "REJECTED_OPERATIONAL_CHOICE_ONLY"
    assert mc_exp["evaluated_counts"] == [100, 250, 500, 1000, 2500]

    mc_fam = recon_data["families"]["Monte Carlo"]
    assert mc_fam["status"] == "FRESH_EXECUTION"
    assert mc_fam["expected_run_count"] == 30


def test_cache_hit_policy(recon_data, execution_df):
    """13. Verify cache hit policy: 0 cache hits across all rebuilt runs."""
    trace = json.loads(R21_TRACE_PATH.read_text(encoding="utf-8"))
    assert trace["summary"]["cache_hits"] == 0

    for exp in trace["rebuilt_experiments"]:
        assert exp["cache_hit"] is False

    assert recon_data["summary"]["cached_runs_count"] == 0
    assert (execution_df["cache_hit"] == True).sum() == 0


def test_hash_consistency(recon_data, chain_data):
    """14. Verify cryptographic hash consistency across all R29 artifacts."""
    artifacts = [
        (PARQUET_PATH, PARQUET_SIDECAR),
        (RECON_PATH, RECON_SIDECAR),
        (RUN_COUNT_PATH, RUN_COUNT_SIDECAR),
        (CHAIN_PATH, CHAIN_SIDECAR),
        (DOC_PATH, DOC_SIDECAR),
        (MATRIX_PATH, MATRIX_PATH.with_suffix(MATRIX_PATH.suffix + ".sha256")),
        (CLOSURE_PATH, CLOSURE_PATH.with_suffix(CLOSURE_PATH.suffix + ".sha256")),
    ]
    for path, sidecar in artifacts:
        assert path.is_file(), f"Missing file: {path}"
        assert sidecar.is_file(), f"Missing sidecar: {sidecar}"
        actual = compute_sha256(path)
        recorded = sidecar.read_text(encoding="utf-8").strip().split()[0]
        assert actual == recorded, f"Sidecar hash mismatch on {path.name}: {actual} != {recorded}"

    # Verify freeze hash in chain
    actual_freeze_sha = compute_sha256(FREEZE_MANIFEST_PATH)
    assert chain_data["chain_nodes"]["R22_FULL_SYSTEM_FREEZE_V3"]["hash"] == actual_freeze_sha


# =============================================================================
# BACKWARD COMPATIBILITY TESTS
# =============================================================================

def test_experiment_family_matrix_completeness(matrix_data):
    """Backward compatibility: verify all 7 experiment families present in matrix."""
    families = matrix_data["families"]
    assert set(families.keys()) == EXPECTED_FAMILIES
    assert matrix_data["total_families"] == 7


def test_r21_run_count_exact_124(run_count_data):
    """Backward compatibility: verify exact 124 count in run count data."""
    assert run_count_data["reported_rebuilt_runs"] == 124
    assert run_count_data["mathematical_sum_of_decomposed_runs"] == 124
    assert run_count_data["runs_match_reported"] is True


def test_zero_unclassified_runs(run_count_data):
    """Backward compatibility: verify zero unclassified runs in run count data."""
    assert run_count_data["zero_unclassified_runs"] is True
    assert run_count_data["unclassified_count"] == 0


def test_fresh_vs_reused_families(matrix_data, run_count_data):
    """Backward compatibility: verify fresh vs reused family breakdown."""
    families = matrix_data["families"]
    assert families["Selection"]["status"] == "FRESH_EXECUTION"
    assert families["Downstream"]["status"] == "FRESH_EXECUTION"
    assert families["Monte Carlo"]["status"] == "FRESH_EXECUTION"

    assert families["Point"]["status"] == "REUSED_VALID_ARTIFACT"
    assert families["Probabilistic"]["status"] == "REUSED_VALID_ARTIFACT"
    assert families["Statistics"]["status"] == "REUSED_VALID_ARTIFACT"
    assert families["Stability"]["status"] == "REUSED_VALID_ARTIFACT"

    reused = run_count_data["reused_family_accounting"]
    assert reused["total_reused_runs"] == 100
    assert reused["Point"] == 20
    assert reused["Probabilistic"] == 20
    assert reused["Statistics"] == 48
    assert reused["Stability"] == 12


def test_grand_total_development_runs(run_count_data):
    """Backward compatibility: verify grand total development runs is 224."""
    assert run_count_data["grand_total_research_evidence_runs"] == 224


def test_lineage_closure_intact(closure_data):
    """Backward compatibility: verify lineage closure across 8 evidence items."""
    assert closure_data["closure_complete"] is True
    assert closure_data["total_lineage_items_verified"] == 8
    for item in closure_data["closure_records"]:
        assert item["lineage_intact"] is True
        assert item["hash"], f"Missing hash for {item['evidence_item']}"


def test_r29_artifact_files_exist():
    """Backward compatibility: verify all R29 audit artifacts exist with sidecars."""
    for p in [MATRIX_PATH, RUN_COUNT_PATH, CLOSURE_PATH, DOC_PATH, PARQUET_PATH, RECON_PATH, CHAIN_PATH]:
        assert p.is_file(), f"Missing artifact: {p}"
        sc = p.with_suffix(p.suffix + ".sha256")
        assert sc.is_file(), f"Missing sidecar: {sc}"
