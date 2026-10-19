"""Protect reconciliation against source mutation, population mixing and false approval."""
import json
import math
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.reconcile_phase1_2 import (ROOT, OUT, Evidence, align_mc_mode, audit_hpo,
    classification, extract_proposal, paired_statistics, publish, regression, sha256)
from scripts.render_phase1_2_reports import generate


def test_classification_threshold_and_confusion_counts():
    result=classification([0,1,1,0],[.1,.9,.4,.8])
    assert {k:result[k] for k in ("tn","fp","fn","tp")} == dict(tn=1,fp=1,fn=1,tp=1)
    assert result["roc_auc"] == .75
    assert result["precision"] == result["recall"] == result["f1"] == .5


@pytest.mark.parametrize("labels,probability", [
    ([0,1],[0,float("nan")]), ([0,2],[0,.5]), ([0,1],[0,1.1]), ([0,1],[.5]), ([],[])])
def test_invalid_rows_are_rejected_instead_of_silently_filled(labels,probability):
    with pytest.raises(ValueError):
        classification(labels,probability)


def test_regression_keeps_negative_minutes_and_tail_population():
    result=regression([-5,0,20,100],[-10,0,10,120])
    assert result["mae"]==8.75 and result["bias"]==1.25
    assert result["rmse"]==pytest.approx(math.sqrt(131.25))
    assert result["tail_mae_ge_15"]==15 and result["tail_mae_ge_60"]==20


def test_auc_macro_is_not_pooled_even_with_equal_fold_sizes():
    folds=[([0,1],[.9,1.0]),([0,1],[.1,.2])]
    macro=np.mean([classification(y,p)["roc_auc"] for y,p in folds])
    pooled=classification([0,1,0,1],[.9,1.0,.1,.2])["roc_auc"]
    assert macro==1 and pooled==.75


@pytest.mark.parametrize("mode,source_solver,ledger_solver", [
    ("A","Greedy","Greedy"),("C2","NONE","ForesightCPSat")])
def test_mc_versioned_identity_and_csv_rounding(mode,source_solver,ledger_solver):
    frame=pd.DataFrame([dict(initial_plan_solver=source_solver,realization_hash="x",
                             objective_value=3.3333,composite_feasible=True)])
    ledger=pd.DataFrame([dict(initial_plan_solver=ledger_solver,realization_hash="x",
                              recourse_mode="MODE_"+mode,objective_value=10/3,composite_feasible=True)])
    assert align_mc_mode(frame,ledger,mode)["matches_ledger"]
    changed=ledger.copy()
    changed["objective_value"]=3.334
    assert not align_mc_mode(frame,changed,mode)["matches_ledger"]
    changed=ledger.copy()
    changed["realization_hash"]="different"
    assert not align_mc_mode(frame,changed,mode)["matches_ledger"]


def test_duplicate_mc_slot_cannot_be_matched_as_one_to_one():
    frame=pd.DataFrame([dict(initial_plan_solver="Greedy",realization_hash="x",
                             objective_value=1,composite_feasible=True)]*2)
    ledger=frame.iloc[:1].assign(recourse_mode="MODE_A")
    with pytest.raises(pd.errors.MergeError):
        align_mc_mode(frame,ledger,"A")


def test_paired_interval_uses_within_scenario_differences():
    result=paired_statistics([11,9,14],[10,10,10])
    assert result["n"]==3 and result["mean_delta"]==pytest.approx(4/3)
    assert result["ci95_t"][0]<result["mean_delta"]<result["ci95_t"][1]
    with pytest.raises(ValueError):
        paired_statistics([1,2],[1])


def test_input_guard_denies_escape_and_2024_rows(tmp_path):
    e=Evidence(tmp_path)
    with pytest.raises(ValueError): e.path("../outside.json")
    with pytest.raises(ValueError): e.path("data/processed/year=2024/a.parquet")


def test_input_guard_detects_source_mutation(tmp_path):
    source=tmp_path/"frozen.json";source.write_text('{"n":1}',encoding="utf-8")
    e=Evidence(tmp_path);e.json("frozen.json")
    assert e.unchanged()
    source.write_text('{"n":2}',encoding="utf-8")
    assert not e.unchanged()


def test_check_mode_does_not_publish_or_rewrite_files(tmp_path):
    assert publish(tmp_path,{"x.json":{"value":1}},check=True)==["x.json"]
    assert not (tmp_path/OUT).exists()
    publish(tmp_path,{"x.json":{"value":1}})
    file=tmp_path/OUT/"x.json";before=(file.stat().st_mtime_ns,sha256(file))
    assert publish(tmp_path,{"x.json":{"value":2}},check=True)==["x.json"]
    assert (file.stat().st_mtime_ns,sha256(file))==before
    with pytest.raises(ValueError):publish(tmp_path,{"../../../escape.txt":"not allowed"})


def test_optuna_audit_is_read_only_and_compares_external_parameters(tmp_path):
    for task in ("xgboost_classification","xgboost_regression"):
        base="week5_hpo_protocol_v1_1__"+task
        db=tmp_path/"artifacts/optuna_studies"/(base+".sqlite3");db.parent.mkdir(parents=True,exist_ok=True)
        maximizing=task.endswith("classification")
        with sqlite3.connect(db) as c:
            c.executescript("""
                CREATE TABLE studies(study_id INTEGER,study_name TEXT);
                CREATE TABLE study_directions(study_id INTEGER,direction TEXT);
                CREATE TABLE trials(trial_id INTEGER,number INTEGER,study_id INTEGER,state TEXT);
                CREATE TABLE trial_values(trial_id INTEGER,objective INTEGER,value REAL);
                CREATE TABLE trial_params(trial_id INTEGER,param_name TEXT,param_value REAL,distribution_json TEXT);
            """)
            c.execute("INSERT INTO studies VALUES(1,?)",(base,))
            c.execute("INSERT INTO study_directions VALUES(1,?)",("MAXIMIZE" if maximizing else "MINIMIZE",))
            c.executemany("INSERT INTO trials VALUES(?,?,1,'COMPLETE')",[(1,0),(2,1)])
            best=2.0 if maximizing else .5
            c.executemany("INSERT INTO trial_values VALUES(?,0,?)",[(1,1.0),(2,best)])
            c.execute("INSERT INTO trial_params VALUES(2,'subsample',1,?)",
                (json.dumps({"name":"CategoricalDistribution","attributes":{"choices":[.6,.8]}}),))
        manifest=tmp_path/"artifacts/manifests"/(base+"_result_v1.json");manifest.parent.mkdir(parents=True,exist_ok=True)
        manifest.write_text(json.dumps(dict(study_name=base,best_trial=1,best_objective=best,
            best_params={"subsample":.8},actual_trial_states={"COMPLETE":2,"FAIL":0})),encoding="utf-8")
    e=Evidence(tmp_path);result=audit_hpo(e)
    assert all(r["matches_manifest"] for r in result)
    assert all(r["best_params"]["subsample"]==.8 for r in result)
    assert e.unchanged()


def test_proposal_and_all_rubric_tables_are_preserved():
    path=ROOT/"CNTT-KLCN168_PhungTheBao.docx"
    if not path.exists():pytest.skip("Locally supplied original proposal needed for extraction audit")
    before=sha256(path);doc=extract_proposal(path)
    assert sha256(path)==before==doc["sha256"]
    assert len(doc["tables"])==3 and len(doc["tables"][0]["rows"])==14
    assert any("Stacking Ensemble" in p["text"] for p in doc["paragraphs"])
    assert doc["tables"][0]["rows"][6]["cells"][3]["paragraphs"][0]=="4.0"


def test_published_requirements_do_not_invent_approval_or_stacking():
    req=json.loads((ROOT/OUT/"requirements.json").read_text(encoding="utf-8"))
    assert len({r["id"] for r in req})==len(req)==35
    assert all(r["source_quotes"] for r in req)
    assert all(r["advisor_status"] in ("PENDING","NONE") for r in req)
    stacking=next(r for r in req if r["id"]=="R05")
    assert stacking["fulfillment"]=="NOT_EVIDENCED" and stacking["advisor_status"]=="PENDING"
    log=json.loads((ROOT/"docs/reconciliation/phase1_2/advisor_decisions.json").read_text(encoding="utf-8-sig"))
    assert all(d["status"]=="PENDING" and d["confirmation_date"] is None for d in log["decisions"])


def test_published_reports_are_generated_from_current_audit():
    for name,content in generate().items():
        assert (ROOT/"docs/reconciliation/phase1_2"/name).read_text(encoding="utf-8-sig")==content


def test_frozen_inputs_still_match_published_inventory():
    inventory=json.loads((ROOT/OUT/"source_inventory.json").read_text(encoding="utf-8"))
    for path,info in inventory["inputs"].items():
        assert sha256(ROOT/path)==info["sha256"],path


def test_current_claims_keep_population_and_probability_scope():
    ml=json.loads((ROOT/OUT/"ml_metrics.json").read_text(encoding="utf-8"))
    heuristic=[r for r in ml["records"] if r["evidence_status"]=="HEURISTIC_DERIVED"]
    assert heuristic and all(r["task"]=="departure_heuristic_probability" for r in heuristic)
    actual=json.loads((ROOT/OUT/"validation.json").read_text(encoding="utf-8"))
    assert actual["status"]=="PASS"



def test_all_metric_families_have_scoped_units_and_hashed_sources():
    registry=json.loads((ROOT/OUT/"metric_registry.json").read_text(encoding="utf-8"))
    tasks={r["task"] for r in registry}
    assert {"departure_classification","departure_regression","arrival_classification","gate_robustness",
            "paired_policy_comparison","xgboost_classification","regression_explanation","gate_solver_comparison"} <= tasks
    assert all(r["unit"] and r["aggregation"] and r["source_sha256"] and r["formula"] for r in registry)
    assert any(r["evidence_status"]=="HEURISTIC_DERIVED" for r in registry)


def test_current_document_links_resolve_and_revoked_numbers_are_not_claimed():
    import re
    directory=ROOT/"docs/reconciliation/phase1_2"
    for file in directory.glob("*.md"):
        text=file.read_text(encoding="utf-8-sig")
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)",text):
            if target.startswith(("http:","https:","#")):continue
            local=target.split("#",1)[0]
            assert (file.parent/local).resolve().exists(),(file.name,target)
    for name in ("07_current_thesis.md","08_defense_slides.md","09_demo_and_qa.md"):
        text=(directory/name).read_text(encoding="utf-8-sig")
        assert not re.search(r"\b0[.,](778|795)\b",text),name



def test_active_narrative_uses_the_recomputed_primary_numbers():
    records=json.loads((ROOT/OUT/"ml_metrics.json").read_text(encoding="utf-8"))["records"]
    by_id={r["id"]:r for r in records}
    clf=by_id["outbound_xgboost_calibrated_v1__2023_classifier"]["metrics"]
    reg=by_id["departure_xgboost_baseline_v1__2023_regression"]["metrics"]
    directory=ROOT/"docs/reconciliation/phase1_2"
    for name in ("07_current_thesis.md","08_defense_slides.md"):
        text=(directory/name).read_text(encoding="utf-8-sig")
        for value in [clf["roc_auc"],clf["pr_auc"],clf["brier_score"],clf["recall"],reg["mae"],reg["rmse"]]:
            assert f"{value:.5f}".replace(".",",") in text,(name,value)
    mc=json.loads((ROOT/OUT/"mc500_audit.json").read_text(encoding="utf-8"))
    c2=next(g for g in mc["groups"] if g["mode"]=="C2")
    assert c2["proven_optimal_count"]==499 and c2["solver_statuses"]=={"OPTIMAL":499,"FEASIBLE":1}
