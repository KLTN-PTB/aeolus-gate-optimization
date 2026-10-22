"""Current acceptance must preserve archives and reject every failing check."""
import json
from types import SimpleNamespace

import pytest

from src.pipeline import thesis_verification as verification


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.fixture
def historical_run(tmp_path, monkeypatch):
    monkeypatch.setattr(verification, "ROOT", tmp_path)
    output = tmp_path / "artifacts/thesis_completion/test_run"
    name = "web_dashboard/app.py"
    source = tmp_path / name
    source.parent.mkdir(parents=True)
    source.write_bytes(b"revised application")
    snapshot = output / "historical_input_snapshot" / name
    snapshot.parent.mkdir(parents=True)
    snapshot.write_bytes(b"published application")
    published = verification.digest(snapshot)
    write_json(tmp_path / "artifacts/reconciliation/phase1_2/source_inventory.json",
               {"inputs": {name: {"sha256": published}}})
    write_json(output / "historical_audit_blocks.json", {"published_source_revisions": [{
        "path": name, "current_sha256": verification.digest(source),
        "published_sha256": published, "historical_source_snapshot": snapshot.relative_to(tmp_path).as_posix(),
    }]})
    domain = tmp_path / "src/optimization/domain.py"
    domain.parent.mkdir(parents=True)
    domain.write_bytes(b"revised domain")
    manifest = tmp_path / "artifacts/manifests/system_freeze_manifest_v3.json"
    write_json(manifest, {"freeze_status": "FROZEN_V3", "final_holdout_year": 2024,
                         "freeze_categories": {"L_optimization": {"files": {
                             "src/optimization/domain.py": "0" * 64}}}})
    manifest.with_suffix(".sha256").write_text(verification.digest(manifest), encoding="utf-8")
    return output, source, snapshot, manifest


def test_historical_archive_validates_without_git_and_keeps_access_blocked(historical_run, monkeypatch):
    output, _, _, manifest = historical_run
    before = manifest.read_bytes()
    def forbidden(*args, **kwargs):
        raise AssertionError("Historical validation must not depend on Git HEAD")
    monkeypatch.setattr(verification.subprocess, "check_output", forbidden)
    result = verification.verify_historical_evidence(output)
    assert result["status"] == "PASS"
    assert result["legacy_v3_evaluation"] == "BLOCKED_SOURCE_REVISION"
    assert result["2024_opened"] is False
    assert result["exact_archived_sources"] == ["web_dashboard/app.py"]
    assert manifest.read_bytes() == before


def test_fresh_run_copies_exact_archives_from_versioned_baseline(historical_run):
    old_output, _, snapshot, _ = historical_run
    root = verification.ROOT
    row = json.loads((old_output / "historical_audit_blocks.json").read_text())["published_source_revisions"][0]
    write_json(root / "artifacts/thesis_completion/historical_evidence_baseline.json", {
        "version": 1, "scope": "published_phase1_2_input_source_revisions",
        "published_source_revisions": [row],
    })
    new_output = root / "artifacts/thesis_completion/new_run"
    result = verification.verify_historical_evidence(new_output)
    copied = new_output / "historical_input_snapshot/web_dashboard/app.py"
    assert copied.read_bytes() == snapshot.read_bytes()
    assert result["status"] == "PASS"
    assert json.loads((new_output / "historical_audit_blocks.json").read_text())["status"] == "ARCHIVED_PUBLISHED_SOURCES"


@pytest.mark.parametrize("target", ["source", "snapshot", "manifest"])
def test_historical_validation_rejects_unreviewed_or_corrupted_bytes(historical_run, target):
    output, source, snapshot, manifest = historical_run
    file = {"source": source, "snapshot": snapshot, "manifest": manifest}[target]
    file.write_bytes(file.read_bytes() + b"\nchanged")
    with pytest.raises((ValueError, PermissionError)):
        verification.verify_historical_evidence(output)


def test_acceptance_does_not_waive_old_test_failures(tmp_path, monkeypatch):
    monkeypatch.setattr(verification, "source_signature", lambda: "fixed-source-signature")
    def failing_check(*args, **kwargs):
        kwargs["stdout"].write("FAILED tests/test_r22_system_freeze_v3.py::test_guard_v3_verifies_all_frozen_files\n")
        return SimpleNamespace(returncode=1)
    monkeypatch.setattr(verification.subprocess, "run", failing_check)
    with pytest.raises(RuntimeError, match="python_tests failed"):
        verification.verify_checks(tmp_path)
    cache = json.loads((tmp_path / "checks_cache.json").read_text(encoding="utf-8"))
    assert cache["checks"]["python_tests"]["status"] == "FAIL"
