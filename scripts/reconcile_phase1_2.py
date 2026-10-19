"""Read-only evidence reconciliation for phases 1 and 2.

Only writes artifacts/reconciliation/phase1_2. No training, solver runs,
2024 raw/processed access, or imports of historical generator scripts.
"""
from __future__ import annotations
import argparse
import ast
import csv
import hashlib
import io
import json
import math
import sqlite3
import sys
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import (average_precision_score, brier_score_loss, confusion_matrix,
    log_loss, mean_absolute_error, mean_squared_error, precision_recall_fscore_support, roc_auc_score)

ROOT = Path(__file__).resolve().parents[1]
OUT = Path("artifacts/reconciliation/phase1_2")
DOCS = Path("docs/reconciliation/phase1_2")
PROPOSAL = "CNTT-KLCN168_PhungTheBao.docx"
MC = "artifacts/remediation/monte_carlo_mc500/mc500_20261012_173538_afa5db"
G3 = "artifacts/remediation/ml_validation"
ARR = "artifacts/model_benchmark_v2/core_point/core_point_benchmark_v2/oof"
MODELS = ["arrival_linear_baseline_v1", "arrival_random_forest_baseline_v1",
          "arrival_hist_gradient_boosting_baseline_v1", "arrival_xgboost_baseline_v1",
          "arrival_weighted_ensemble_v1"]
W = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"


class Evidence:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.inventory = {}

    def path(self, relative) -> Path:
        p = (self.root / relative).resolve()
        if not p.is_relative_to(self.root):
            raise ValueError("Evidence path escapes repository")
        rel = p.relative_to(self.root).as_posix()
        if rel.startswith("data/") and "2024" in rel:
            raise ValueError("2024 raw/processed access is outside this audit")
        if not p.is_file():
            raise FileNotFoundError(rel)
        if rel not in self.inventory:
            self.inventory[rel] = {"sha256": sha256(p), "bytes": p.stat().st_size}
        return p

    def json(self, relative):
        return json.loads(self.path(relative).read_text(encoding="utf-8-sig"))

    def csv(self, relative):
        return pd.read_csv(self.path(relative))

    def parquet(self, relative, columns=None):
        return pd.read_parquet(self.path(relative), columns=columns)

    def unchanged(self):
        return all(sha256(self.root / p) == info["sha256"] for p, info in self.inventory.items())


def extract_proposal(path: Path) -> dict:
    with zipfile.ZipFile(path) as package:
        root = ET.fromstring(package.read("word/document.xml"))
        paragraphs = []
        for p in root.findall(".//w:body//w:p", W):
            text = "".join(n.text or "" for n in p.findall(".//w:t", W)).strip()
            if text:
                paragraphs.append({"id": f"P{len(paragraphs)+1:03d}", "text": text})
        tables = []
        for index, table in enumerate(root.findall(".//w:body/w:tbl", W), 1):
            rows = []
            for ri, row in enumerate(table.findall("w:tr", W), 1):
                cells = []
                for cell in row.findall("w:tc", W):
                    texts = ["".join(n.text or "" for n in p.findall(".//w:t", W))
                             for p in cell.findall(".//w:p", W)]
                    span = cell.find("w:tcPr/w:gridSpan", W)
                    merge = cell.find("w:tcPr/w:vMerge", W)
                    cells.append({"paragraphs": texts,
                        "grid_span": int(span.get("{"+W["w"]+"}val", "1")) if span is not None else 1,
                        "vertical_merge": merge.get("{"+W["w"]+"}val", "continue") if merge is not None else None})
                rows.append({"row": ri, "cells": cells})
            tables.append({"table": index, "rows": rows})
        return {"source": PROPOSAL, "sha256": sha256(path), "paragraphs": paragraphs, "tables": tables,
                "tracked_insertions": len(root.findall(".//w:ins", W)),
                "tracked_deletions": len(root.findall(".//w:del", W)),
                "locator_note": "Paragraph IDs are extraction order, not page numbers. Rubric values are preserved; no grades are assigned."}


def classification(y, probability, threshold=.5):
    y, p = np.asarray(y), np.asarray(probability, dtype=float)
    if len(y) == 0 or len(y) != len(p) or not np.isin(y, [0, 1]).all() or not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError("Invalid labels/probabilities; never drop or fill invalid rows")
    binary = p >= threshold
    tn, fp, fn, tp = confusion_matrix(y, binary, labels=[0, 1]).ravel()
    precision, recall, f1, _ = precision_recall_fscore_support(y, binary, average="binary", zero_division=0)
    bins = np.minimum((p * 10).astype(int), 9)
    ece = sum(float(np.mean(bins == b)) * abs(float(p[bins == b].mean())-float(y[bins == b].mean()))
              for b in range(10) if np.any(bins == b))
    return {"n": int(len(y)), "prevalence": float(y.mean()),
            "roc_auc": float(roc_auc_score(y, p)) if len(np.unique(y)) == 2 else None,
            "pr_auc": float(average_precision_score(y, p)), "brier_score": float(brier_score_loss(y, p)),
            "log_loss": float(log_loss(y, p, labels=[0, 1])), "ece": float(ece), "threshold": threshold,
            "precision": float(precision), "recall": float(recall), "f1": float(f1),
            "tp": int(tp), "fp": int(fp), "tn": int(tn), "fn": int(fn)}


def regression(y, prediction):
    y, p = np.asarray(y, dtype=float), np.asarray(prediction, dtype=float)
    if len(y) == 0 or len(y) != len(p) or not np.isfinite(y).all() or not np.isfinite(p).all():
        raise ValueError("Invalid regression rows; never drop or fill them")
    return {"n": len(y), "mae": float(mean_absolute_error(y, p)),
            "rmse": float(math.sqrt(mean_squared_error(y, p))), "bias": float(np.mean(p-y)),
            "tail_mae_ge_15": float(np.mean(np.abs(p[y >= 15]-y[y >= 15]))) if np.any(y >= 15) else None,
            "tail_mae_ge_60": float(np.mean(np.abs(p[y >= 60]-y[y >= 60]))) if np.any(y >= 60) else None}


def compare(saved, calculated, decimals=5):
    result = []
    for key, value in calculated.items():
        if key not in saved or value is None:
            continue
        old = saved[key]
        if old is None or (isinstance(old, float) and np.isnan(old)):
            result.append({"field": key, "saved": None, "computed": value})
        elif not math.isclose(float(old), float(value), rel_tol=0, abs_tol=.5*10**(-decimals)+1e-10):
            result.append({"field": key, "saved": float(old), "computed": value})
    return result


def audit_ml(e: Evidence):
    rows, issues = [], []
    saved_class = e.csv(f"{G3}/classification_metrics.csv")
    saved_reg = e.csv(f"{G3}/regression_metrics.csv")
    cp = "artifacts/remediation/outbound_classification/predictions/outbound_classification_selection_2023.parquet"
    frame = e.parquet(cp)
    if frame.flight_key.duplicated().any():
        raise ValueError("Duplicate outbound classification keys")
    summary = e.csv("artifacts/remediation/outbound_classification/metrics/outbound_classification_metrics_2023.csv")
    mapping = [("prob_constant","constant_prevalence_baseline"), ("prob_logistic_raw","outbound_logistic_raw_v1"),
               ("prob_logistic_calibrated","outbound_logistic_calibrated_v1"), ("prob_xgboost_raw","outbound_xgboost_raw_v1"),
               ("prob_xgboost_calibrated","outbound_xgboost_calibrated_v1")]
    for col, model in mapping:
        metrics = classification(frame.y_true, frame[col])
        saved = summary.loc[summary.model_id.eq(model)].iloc[0].to_dict()
        differences = compare(saved, metrics)
        rows.append({"id": model+"__2023_classifier", "model_id": model, "task": "departure_classification",
                     "split": "selection_2023", "aggregation": "pooled", "source": cp, "prediction_column": col,
                     "evidence_status": "RECOMPUTED_FROM_STORED_PREDICTIONS", "metrics": metrics,
                     "historical_summary_differences": differences})
        issues.extend({"kind": "summary_difference", "model_id": model, **d} for d in differences)
    rp = "artifacts/dual_core/predictions/departure_point_selection_2023_v1.parquet"
    dep = e.parquet(rp)
    if dep.flight_key.duplicated().any():
        raise ValueError("Duplicate departure regression keys")
    joined = frame[["flight_key","y_true"]].merge(dep[["flight_key","actual_dep_delay"]], on="flight_key", validate="one_to_one")
    if len(joined) != len(frame) or len(joined) != len(dep) or not np.array_equal(joined.y_true, joined.actual_dep_delay.ge(15).astype(int)):
        raise ValueError("Classification and regression populations do not align")
    for col, model in [("pred_zero","baseline_zero"),("pred_median","baseline_median"),("pred_ridge","departure_ridge_baseline_v1"),("pred_xgboost","departure_xgboost_baseline_v1")]:
        metrics = regression(dep.actual_dep_delay, dep[col])
        old = saved_reg.loc[saved_reg.model_id.eq(model) & saved_reg.task.eq("core_departure")].iloc[0].to_dict()
        differences = compare(old, metrics, 4)
        rows.append({"id":model+"__2023_regression","model_id":model,"task":"departure_regression","split":"selection_2023",
                     "aggregation":"pooled","source":rp,"prediction_column":col,"evidence_status":"RECOMPUTED_FROM_STORED_PREDICTIONS",
                     "metrics":metrics,"historical_summary_differences":differences,
                     "limitation":"Stored median baseline; no proof of training-only median is inferred from prediction values." if col=="pred_median" else None})
        issues.extend({"kind":"summary_difference","model_id":model,**d} for d in differences)
        if col in ("pred_ridge","pred_xgboost"):
            heuristic = classification(dep.actual_dep_delay.ge(15).astype(int), 1/(1+np.exp(-(dep[col].to_numpy()-15)/10)))
            rows.append({"id":model+"__2023_heuristic_probability","model_id":model,"task":"departure_heuristic_probability",
                         "split":"selection_2023","aggregation":"pooled","source":rp,"evidence_status":"HEURISTIC_DERIVED",
                         "formula":"sigmoid((predicted_delay_minutes - 15) / 10); threshold 0.5 equals predicted delay >= 15",
                         "metrics":heuristic,"limitation":"Not probabilities from a trained classifier or calibrated density."})
    for model in MODELS:
        frames, sources, per_fold = [], [], []
        for fold in range(1,5):
            source=f"{ARR}/{model}_fold_{fold}.parquet"
            df=e.parquet(source); frames.append(df); sources.append(source)
            per_fold.append({"fold":fold,"classification":classification(df.y_true_cls,df.pred_cls_prob), "regression":regression(df.y_true_reg,df.pred_reg)})
        pooled=pd.concat(frames,ignore_index=True)
        if pooled.flight_key.duplicated().any():
            issues.append({"kind":"duplicate_oof_key","model_id":model,"count":int(pooled.flight_key.duplicated().sum())})
        for kind,metrics in [("classification",classification(pooled.y_true_cls,pooled.pred_cls_prob)),("regression",regression(pooled.y_true_reg,pooled.pred_reg))]:
            old_frame=saved_class if kind=="classification" else saved_reg
            old=old_frame.loc[old_frame.model_id.eq(model) & old_frame.task.eq("core_arrival")].iloc[0].to_dict()
            differences=compare(old,metrics,5 if kind=="classification" else 4)
            macro={key:float(np.mean([f[kind][key] for f in per_fold])) for key in metrics
                   if key not in ("n","tp","tn","fp","fn","threshold") and all(f[kind][key] is not None for f in per_fold)}
            rows.append({"id":model+"__arrival_"+kind,"model_id":model,"task":"arrival_"+kind,
                         "split":"development_oof_2019_2022_sample","aggregation":"pooled_4_folds","source":sources,
                         "evidence_status":"RECOMPUTED_FROM_STORED_PREDICTIONS","metrics":metrics,"fold_macro_metrics":macro,
                         "per_fold":[{k:v for k,v in f.items() if k in ("fold",kind)} for f in per_fold],
                         "historical_summary_differences":differences,
                         "limitation":"Historical CSV says oof_4_fold_macro, but its generator pools rows. The 16,000-row subset is not the full tuned OOF population."})
            issues.extend({"kind":"summary_difference","model_id":model,**d} for d in differences)
    fold_values, sources, all_y, all_p, all_yr, all_pr = [], [], [], [], [], []
    for fold in range(1,5):
        source=f"artifacts/predictions/arrival_xgboost_tuned_rolling_run_v1_1_fold_{fold}.parquet"
        df=e.parquet(source,columns=["flight_key","validation_year","y_arr_cls","p_arr_delay_15","y_arr_reg","predicted_arr_delay_min"])
        if not df.validation_year.eq(2018+fold).all() or df.flight_key.duplicated().any():
            raise ValueError("Tuned OOF fold identity or uniqueness failed")
        fold_values.append({"fold":fold,"n":len(df),"classification":classification(df.y_arr_cls,df.p_arr_delay_15),
                            "regression":regression(df.y_arr_reg,df.predicted_arr_delay_min)})
        sources.append(source); all_y.append(df.y_arr_cls.to_numpy()); all_p.append(df.p_arr_delay_15.to_numpy())
        all_yr.append(df.y_arr_reg.to_numpy()); all_pr.append(df.predicted_arr_delay_min.to_numpy())
    for kind,metrics in [("classification",classification(np.concatenate(all_y),np.concatenate(all_p))),("regression",regression(np.concatenate(all_yr),np.concatenate(all_pr)))]:
        macro={key:float(np.mean([f[kind][key] for f in fold_values])) for key in metrics
               if key not in ("n","tp","tn","fp","fn","threshold") and all(f[kind][key] is not None for f in fold_values)}
        rows.append({"id":"arrival_xgboost_tuned_v1_1__full_oof_"+kind,"model_id":"arrival_xgboost_tuned_v1_1",
                     "task":"arrival_"+kind,"split":"development_full_oof_2019_2022","aggregation":"pooled_4_folds",
                     "source":sources,"evidence_status":"RECOMPUTED_FROM_STORED_PREDICTIONS","metrics":metrics,
                     "fold_macro_metrics":macro,"per_fold":fold_values,
                     "limitation":"Different population from the 16,000-row subset. No like-for-like improvement is inferred."})
    issues.append({"kind":"aggregation_label","message":"P08 arrival rows are pooled, not macro. Its hardcoded tuned row is superseded by full stored OOF metrics with a different population."})
    return {"records":rows,"issues":issues,"population_alignment":{"departure_join_rows":len(joined),"labels_match":True},
            "status_note":"Recalculation verifies stored prediction arithmetic, not independent retraining, prospective validity, or advisor acceptance."}



def audit_hpo(e: Evidence):
    results=[]
    for task in ("xgboost_classification","xgboost_regression"):
        base="week5_hpo_protocol_v1_1__"+task
        manifest=e.json(f"artifacts/manifests/{base}_result_v1.json")
        db=e.path(f"artifacts/optuna_studies/{base}.sqlite3")
        with sqlite3.connect(db.resolve().as_uri()+"?mode=ro",uri=True) as conn:
            conn.execute("PRAGMA query_only=ON")
            study=conn.execute("SELECT study_id FROM studies WHERE study_name=?",(manifest["study_name"],)).fetchone()
            if not study: raise ValueError("Study not found")
            direction=conn.execute("SELECT direction FROM study_directions WHERE study_id=?",(study[0],)).fetchone()[0]
            states=dict(conn.execute("SELECT state,COUNT(*) FROM trials WHERE study_id=? GROUP BY state",(study[0],)).fetchall())
            trials=conn.execute("SELECT t.trial_id,t.number,v.value FROM trials t JOIN trial_values v ON v.trial_id=t.trial_id WHERE t.study_id=? AND t.state='COMPLETE' AND v.objective=0",(study[0],)).fetchall()
            best=sorted(trials,key=lambda row:((-row[2]) if direction=="MAXIMIZE" else row[2],row[1]))[0]
            params={}
            for name,value,dist in conn.execute("SELECT param_name,param_value,distribution_json FROM trial_params WHERE trial_id=?",(best[0],)):
                definition=json.loads(dist)
                if definition["name"]=="CategoricalDistribution": value=definition["attributes"]["choices"][int(value)]
                elif definition["name"]=="IntDistribution": value=int(value)
                params[name]=value
            matched=(best[1]==manifest["best_trial"] and math.isclose(best[2],manifest["best_objective"],abs_tol=1e-12,rel_tol=0)
                     and params==manifest["best_params"] and all(states.get(k,0)==v for k,v in manifest["actual_trial_states"].items()))
        results.append({"task":task,"study_name":manifest["study_name"],"direction":direction,"trial_states":states,
                        "best_trial":best[1],"best_value":best[2],"best_params":params,"matches_manifest":bool(matched),
                        "source":[f"artifacts/optuna_studies/{base}.sqlite3",f"artifacts/manifests/{base}_result_v1.json"],
                        "scope":"Core arrival development HPO only; not proof the deployed departure checkpoint was tuned by this study."})
    return results


def paired_statistics(left, right):
    left,right=np.asarray(left,dtype=float),np.asarray(right,dtype=float)
    if left.shape!=right.shape or left.ndim!=1 or len(left)<2 or not np.isfinite(left).all() or not np.isfinite(right).all():
        raise ValueError("Invalid paired observations")
    delta=left-right; n=len(delta); mean=float(delta.mean()); se=float(delta.std(ddof=1)/math.sqrt(n))
    critical=float(stats.t.ppf(.975,n-1))
    p=float(stats.ttest_rel(left,right).pvalue) if np.any(delta) else 1.0
    return {"n":n,"mean_delta":mean,"se":se,"ci95_t":[mean-critical*se,mean+critical*se],"p_value":p,
            "formula":"paired left minus right; Student t 95% interval; no EVPI identity asserted"}



def align_mc_mode(frame, ledger, mode):
    """Map explicitly versioned slot identities and respect CSV rounding."""
    actual=ledger.loc[ledger.recourse_mode.eq("MODE_"+mode)]
    normalized=frame.copy()
    if mode in ("C1","C2"):
        normalized["initial_plan_solver"]="ForesightGreedy" if mode=="C1" else "ForesightCPSat"
    joined=normalized.merge(actual,on=["initial_plan_solver","realization_hash"],suffixes=("_mode","_ledger"),validate="one_to_one")
    tolerance=.5e-4+1e-10
    error=float(np.abs(joined.objective_value_mode-joined.objective_value_ledger).max()) if len(joined) else None
    ok=(len(joined)==len(frame)==len(actual) and error is not None and error<=tolerance
        and np.array_equal(joined.composite_feasible_mode,joined.composite_feasible_ledger))
    return {"mode":mode,"rows":len(frame),"matches_ledger":bool(ok),
            "max_rounding_error":error,"objective_tolerance":tolerance,"key_mapping":"MODE_"+mode,
            "none_solver_mapping":str(normalized.initial_plan_solver.iloc[0]) if mode in ("C1","C2") else None}



def audit_mc(e: Evidence):
    files={"A":"fixed_plan_results.csv","B1":"recourse_b1_retrospective_results.csv",
           "B2":"recourse_b2_online_results.csv","C1":"foresight_c1_greedy_results.csv","C2":"foresight_c2_optimal_results.csv"}
    manifest=e.json(f"{MC}/simulation_manifest.json")
    ledger=e.csv(f"{MC}/execution_ledger_entries.csv")
    generation=e.csv(f"{MC}/execution_ledger_generation.csv")
    expected=e.json(f"{MC}/execution_ledger_summary.json")
    duplicate=int(ledger.duplicated(["run_id","scenario_id","recourse_mode","initial_plan_solver"]).sum())
    groups=[]; selected={}; mode_frames={}; alignment=[]
    for mode,name in files.items():
        df=e.csv(f"{MC}/{name}"); mode_frames[mode]=df
        if df.duplicated(["scenario_index","initial_plan_solver"]).any(): raise ValueError("Duplicate MC slot")
        for solver,part in df.groupby("initial_plan_solver",sort=True):
            values=part.objective_value.to_numpy(dtype=float)
            if not np.isfinite(values).all(): raise ValueError("Nonfinite MC objective")
            cvar=lambda q:float(values[values>=np.percentile(values,100*q)].mean())
            groups.append({"mode":mode,"initial_plan_solver":str(solver),"n":len(part),
                           "feasible_count":int(part.composite_feasible.sum()),"feasible_rate":float(part.composite_feasible.mean()),
                           "objective_mean":float(values.mean()),"objective_p90":float(np.percentile(values,90)),
                           "objective_p99":float(np.percentile(values,99)),"cvar90":cvar(.9),"cvar95":cvar(.95),
                           "cvar_convention":"mean(objective >= numpy percentile threshold), including ties; historical convention",
                           "physical_conflicts":int(part.physical_contact_conflict_count.sum()),
                           "buffer_violations":int(part.buffer_violation_count.sum()),
                           "solver_statuses":{str(k):int(v) for k,v in part.solver_status.value_counts().items()},
                           "proven_optimal_count":int(part.is_optimal_proven.sum()),
                           "runtime_p95_ms":float(np.percentile(part.runtime_ms,95)),
                           "runtime_max_ms":float(part.runtime_ms.max()),"source":f"{MC}/{name}"})
        solvers=sorted(df.initial_plan_solver.unique()); pick="Greedy" if "Greedy" in solvers else solvers[0]
        selected[mode]=df.loc[df.initial_plan_solver.eq(pick)].set_index("scenario_index").sort_index()
    pairs={}
    for left,right in [("A","B2"),("B1","B2"),("C1","C2"),("B2","C2")]:
        a,b=selected[left],selected[right]
        if not a.index.equals(b.index) or not a.realization_hash.equals(b.realization_hash):
            raise ValueError("Monte Carlo pair identity mismatch")
        result=paired_statistics(a.objective_value,b.objective_value)
        result.update({"left_initial_solver":str(a.initial_plan_solver.iloc[0]),"right_initial_solver":str(b.initial_plan_solver.iloc[0])})
        pairs[left+"-"+right]=result
    for mode,df in mode_frames.items():
        alignment.append(align_mc_mode(df,ledger,mode))
    count={"requested":manifest["n_scenarios"],"generated":len(generation),"unique_scenarios":int(ledger.scenario_id.nunique()),
           "evaluations":len(ledger),"min_slots_per_scenario":int(ledger.groupby("scenario_id").size().min()),
           "max_slots_per_scenario":int(ledger.groupby("scenario_id").size().max()),"duplicate_primary_keys":duplicate,
           "feasible":int(ledger.composite_feasible.sum()),"infeasible":int((~ledger.composite_feasible).sum()),
           "timeouts":int(ledger.timeout.sum()),"exception_rows":int(ledger.exception_type.notna().sum())}
    count["matches_saved_accounting"]=(count["evaluations"]==expected["accounting"]["n_completed_evaluations"] and
         count["feasible"]==expected["accounting"]["n_feasible_evaluations"] and count["infeasible"]==expected["accounting"]["n_infeasible_evaluations"])
    return {"run_id":manifest["run_id"],"accounting":count,"groups":groups,"paired":pairs,"mode_ledger_alignment":alignment,
            "assumptions":{"copula":manifest["copula"],"marginals":manifest["marginal_distributions"],
              "scope":"Synthetic simulation with configured marginals; not native ML sampling on the uploaded 2026 day.",
              "web_difference":"Web samples independent arrival Student-t marginals, holds departure point forecasts, and uses retrospective full-day recourse."}}


def audit_benchmark(e: Evidence):
    source="artifacts/remediation/benchmarks/g5_fair_benchmark/g5_fair_benchmark_results.csv"
    df=e.csv(source); manifest=e.json("artifacts/remediation/benchmarks/g5_fair_benchmark/g5_fair_benchmark_manifest.json")
    return {"source":source,"manifest":manifest,"rows":len(df),"scenarios":int(df.scenario_id.nunique()),
            "scenario_hash_consistent":bool(df.groupby("scenario_id").scenario_hash.nunique().eq(1).all()),
            "solver_summary":[{"solver":str(solver),"runs":len(part),"feasible":int(part.feasible.sum()),
                               "optimality_proven":int(part.optimality_proven.sum()),"hard_violations":int(part.hard_violations.sum()),
                               "mean_objective":float(part.objective_value.mean()),"max_runtime_ms":float(part.runtime_ms.max())}
                              for solver,part in df.groupby("solver",sort=True)],
            "scalability_rows":e.csv("artifacts/remediation/cp_sat/scalability_results.csv").replace({np.nan:None}).to_dict("records"),
            "limitation":"Reaggregated stored runs, not a new solver execution or renewed proof of runtime-budget fairness. Total gates can include remote resources."}


def audit_shap(e: Evidence, recompute=True):
    base=f"{G3}/shap_outputs"
    saved=e.json(f"{base}/summary_statistics.json"); cases=e.json(f"{base}/shap_case_studies.json")
    case_checks=[]
    for case in cases:
        reconstructed=case["base_expected_value_minutes"]+sum(a["attribution_minutes"] for a in case["feature_attributions_ordered"])
        case_checks.append({"flight_key":case["flight_metadata"]["flight_key"],
                            "rounded_additivity_error_min":abs(reconstructed-case["model_predicted_delay_minutes"])})
    result={"model_id":saved["model_id"],"saved_summary":saved,"case_checks":case_checks,
            "source":[f"{base}/summary_statistics.json",f"{base}/shap_case_studies.json"],
            "scope":"Stored departure XGBoost regression explanations, not explanations of new uploads or arrival probabilities."}
    if not recompute:
        result["status"]="SAVED_ATTRIBUTIONS_ARITHMETIC_ONLY"; return result
    data="data/processed/tabular_by_year/year=2023/part-00000.parquet"
    if not (e.root/data).exists():
        result.update(status="MISSING_OPTIONAL_SOURCE",reason="No claim of recomputed TreeSHAP without its exact source partition.")
        return result
    import joblib
    import shap
    from src.features.departure_features import prepare_departure_inference
    model_path="artifacts/dual_core/models/departure_xgboost_baseline_v1.joblib"
    prep_path="artifacts/dual_core/models/departure_tree_preprocessor_v1.joblib"
    model=joblib.load(e.path(model_path)); prep=joblib.load(e.path(prep_path))
    frame=e.parquet(data); sample=frame.loc[frame.ORIGIN.eq("ATL")].head(saved["sample_size"]).copy().reset_index(drop=True)
    batch=prepare_departure_inference(sample); x=prep.transform(batch.X)
    explainer=shap.TreeExplainer(model); values=explainer(x); predicted=model.predict(x)
    err=float(np.abs(values.base_values+values.values.sum(axis=1)-predicted).max())
    names=list(prep.get_feature_names_out()); importance=np.abs(values.values).mean(axis=0)
    old=e.csv(f"{base}/global_importance.csv").set_index("feature")
    maximum=max(abs(float(old.loc[name,"mean_abs_shap_minutes"])-float(value)) for name,value in zip(names,importance))
    result.update(status="RECOMPUTED_TREESHAP",sample_size=len(sample),model_sha256=sha256(e.root/model_path),
                  preprocessor_sha256=sha256(e.root/prep_path),max_additivity_error_min=err,
                  max_saved_importance_difference_min=maximum,matches_saved_importance=maximum<=.5e-5+1e-9,
                  source=result["source"]+[data,model_path,prep_path,f"{base}/global_importance.csv"])
    return result



def audit_lineage(e: Evidence):
    source="scripts/generate_p08_validation_artifacts.py"
    code=e.path(source).read_text(encoding="utf-8-sig"); tree=ast.parse(code)
    ablation=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="generate_feature_ablation")
    literals=[]
    for node in ast.walk(ablation):
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="records" for t in node.targets):
            try: literals=ast.literal_eval(node.value)
            except (ValueError,TypeError): pass
    catalog=e.csv(f"{G3}/feature_ablation.csv")
    e.path("src/models/registry.py"); e.path("src/evaluation/model_selection.py")
    return {"ablation":{"source":source,"literal_record_count":len(literals),"csv_rows":len(catalog),
              "status":"HARDCODED_SUMMARY_NOT_PREDICTION_LEVEL_ABLATION",
              "excluded_from_verified_claims":["B_tabular_plus_chain","C_tabular_plus_chain_plus_weather"],
              "note":"Tabular metrics can be checked separately. No numeric improvement inferred for blocked branches."},
            "ensemble":{"implemented":"Weighted ensemble","stacking_equivalence":False,
              "source":["src/models/registry.py","src/evaluation/model_selection.py"],"advisor_status":"PENDING"},
            "median_baseline":{"issue":"P08 computes arrival median on pooled evaluation labels. This is retrospective, not a proved train-only deployment baseline.","source":source},
            "cutoff":"CRS_DEP_TIME - 2h in both task feature contracts; do not replace with CRS_ARR_TIME - 2h.",
            "weather":"Insufficient point-in-time evidence; no claim all Meteostat/BTS products share identical observation provenance."}


def audit_models(e: Evidence):
    import joblib
    from src.models.registry import get_model_spec,is_downstream_eligible
    records=[]
    for path in sorted((e.root/"artifacts").rglob("*.joblib")):
        rel=path.relative_to(e.root).as_posix(); e.path(rel)
        record={"path":rel,"sha256":sha256(path),"bytes":path.stat().st_size}
        try:
            loaded=joblib.load(path)
            record.update(load_status="LOADED",object_type=type(loaded).__module__+"."+type(loaded).__name__)
        except Exception as exc:
            record.update(load_status="LOAD_FAILED",error_type=type(exc).__name__,error=str(exc).split(" on <module")[0])
        records.append(record)
    p="artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib"
    model=joblib.load(e.path(p)); specs={}
    for mid in ["P4_ngboost_student_t","b5_ngboost_student_t","departure_certified_point_v1","arrival_weighted_ensemble_v1"]:
        spec=get_model_spec(mid)
        specs[mid]={"status":str(spec.status),"task":str(spec.task),"implementation_class":spec.implementation_class,
                    "selection_role":spec.selection_role,"downstream_eligible":is_downstream_eligible(mid)}
    run=e.json("artifacts/remediation/native_dual_core_g4_pilot/run_manifest.json")
    e.path("src/simulation/native_dual_core_pipeline.py"); e.path("web_dashboard/pipeline.py"); e.path("web_dashboard/experiments.py")
    return {"checkpoint_inventory":records,"arrival_checkpoint":p,"arrival_sha256":sha256(e.root/p),
            "loaded_class":type(model).__module__+"."+type(model).__name__,"registry":specs,"native_g4_manifest":run,
            "conclusion":"Serialized class B5NGBoostStudentT; native run model b5_ngboost_student_t. The historical P4 label does not change registry identity or model status."}


def as_csv(records):
    if not records: return ""
    keys=list(dict.fromkeys(key for row in records for key in row))
    stream=io.StringIO(newline=""); writer=csv.DictWriter(stream,fieldnames=keys,lineterminator="\n"); writer.writeheader()
    for row in records:
        writer.writerow({k:json.dumps(v,ensure_ascii=False,sort_keys=True) if isinstance(v,(dict,list)) else v for k,v in row.items()})
    return stream.getvalue()



def render_tables(outputs):
    ml=outputs["ml_metrics.json"]["records"]
    lines=["# Kết quả được tính lại từ bằng chứng đã lưu", "",
           "Phạm vi: phép tính trên dự báo/ledger đã lưu; không phải tái huấn luyện hoặc nghiệm thu của GVHD.",
           "Giá trị JSON giữ độ chính xác đầy đủ; bảng dưới làm tròn 5 chữ số. IDs liên kết metric_registry.csv.", "",
           "## Phân loại departure trên selection 2023", "",
           "| Model | N | ROC-AUC | PR-AUC | Precision | Recall | F1 | Brier | ECE |",
           "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in ml:
        if r["task"]=="departure_classification":
            m=r["metrics"]
            lines.append("| "+r["model_id"]+" | "+str(m["n"])+" | "+" | ".join(f"{m[k]:.5f}" for k in ["roc_auc","pr_auc","precision","recall","f1","brier_score","ece"])+" |")
    lines+=["", "Ngưỡng phân loại = 0,5. Probability từ bộ phân loại được phân biệt với biến đổi sigmoid của hồi quy.", "",
            "## Hồi quy departure trên selection 2023", "",
            "| Model | N | MAE phút | RMSE phút | MAE trễ ≥15 | MAE trễ ≥60 |",
            "|---|---:|---:|---:|---:|---:|"]
    for r in ml:
        if r["task"]=="departure_regression":
            m=r["metrics"];lines.append("| "+r["model_id"]+" | "+str(m["n"])+" | "+" | ".join(f"{m[k]:.5f}" for k in ["mae","rmse","tail_mae_ge_15","tail_mae_ge_60"])+" |")
    lines+=["", "Median là dự báo đã lưu; tính lại sai số chưa chứng minh median được fit chỉ trên train.", "",
            "## Arrival và cách tổng hợp", "",
            "| Model | Task | Population | N | Pooled AUC hoặc MAE | Macro AUC hoặc MAE |",
            "|---|---|---|---:|---:|---:|"]
    for r in ml:
        if r["task"].startswith("arrival"):
            k="roc_auc" if r["task"].endswith("classification") else "mae"
            lines.append(f'| {r["model_id"]} | {r["task"]} | {r["split"]} | {r["metrics"]["n"]} | {r["metrics"][k]:.5f} | {r["fold_macro_metrics"][k]:.5f} |')
    lines+=["", "Không suy ra mức cải thiện giữa baseline 16.000 dòng và tuned OOF 1.254.518 dòng.",
            "Macro là trung bình metric từng fold; pooled tính một lần trên toàn bộ dòng gộp.", "",
            "## MC500 chính thức", "",
            "| Mode | Initial solver | N | Mean objective điểm | Feasible | Conflicts | Buffer violations |",
            "|---|---|---:|---:|---:|---:|---:|"]
    mc=outputs["mc500_audit.json"]
    for r in mc["groups"]:
        lines.append(f'| {r["mode"]} | {r["initial_plan_solver"]} | {r["n"]} | {r["objective_mean"]:.5f} | {r["feasible_count"]}/{r["n"]} | {r["physical_conflicts"]} | {r["buffer_violations"]} |')
    lines+=["", "Mẫu số 500 thuộc từng initial solver. Cộng các initial solver của A/B1/B2 thành 1.500 lượt, không phải 1.500 kịch bản độc lập.",
            "C2 có 499 OPTIMAL và 1 FEASIBLE. Full-day retrospective web recourse khác B2 causal online.",
            "Objective là điểm theo cấu hình mô phỏng. Marginals và copula MC500 là tham số cấu hình, không phải kết quả suy luận trên file upload.", "",
            "## So sánh ghép cặp MC500", "",
            "| Chênh lệch | N | Mean delta điểm | 95% CI Student t | p-value |",
            "|---|---:|---:|---|---:|"]
    for key,r in mc["paired"].items():
        lines.append(f'| {key} | {r["n"]} | {r["mean_delta"]:.5f} | [{r["ci95_t"][0]:.5f}, {r["ci95_t"][1]:.5f}] | {r["p_value"]:.5g} |')
    lines+=["", "A/B dùng initial plan Greedy trong bảng ghép cặp. Đã kiểm tra cùng scenario_index và realization_hash.",
            "Khoảng tin cậy Student t ở đây khác xấp xỉ normal 1,96 trong paired_comparison.csv lịch sử; không thay file gốc.",
            "B2−C2 được mô tả là khoảng cách chính sách với foresight, không khẳng định formal EVPI.", "",
            "## Benchmark G5 được tổng hợp lại", "",
            "| Solver | Runs | Feasible | Proven optimal | Mean objective điểm | Max runtime ms |",
            "|---|---:|---:|---:|---:|---:|"]
    for r in outputs["benchmark_audit.json"]["solver_summary"]:
        lines.append(f'| {r["solver"]} | {r["runs"]} | {r["feasible"]} | {r["optimality_proven"]} | {r["mean_objective"]:.5f} | {r["max_runtime_ms"]:.2f} |')
    lines+=["", "Cùng scenario hash chưa đủ để chứng minh ngân sách wall-clock bằng nhau. Không khẳng định Hybrid luôn bằng hoặc tốt hơn CP-SAT.", "",
            "## Sai lệch và giới hạn cần giữ trong báo cáo", ""]
    for issue in outputs["ml_metrics.json"]["issues"]:
        lines.append("- "+json.dumps(issue,ensure_ascii=False,sort_keys=True))
    lines+=["", "SHAP được kiểm tra riêng trong shap_audit.json. Tên model và quyền downstream lấy từ model_identity.json.",
            "Flight Chain/Weather ablation có số liệu ghi cứng được phân loại trong lineage_audit.json.", ""]
    return "\n".join(lines)


def validate_outputs(outputs):
    mc=outputs["mc500_audit.json"]; a=mc["accounting"]; shap=outputs["shap_audit.json"]
    checks={
        "proposal_requirements_have_source":all(r["source_quotes"] for r in outputs["requirements.json"]),
        "advisor_approval_not_invented":all(r["advisor_status"] in ("PENDING","NONE") for r in outputs["requirements.json"]),
        "hpo_matches_sqlite":all(r["matches_manifest"] for r in outputs["hpo_audit.json"]),
        "mc_unique_complete_accounting":a["duplicate_primary_keys"]==0 and a["generated"]==a["requested"]==a["unique_scenarios"]==500 and a["evaluations"]==5500 and a["min_slots_per_scenario"]==a["max_slots_per_scenario"]==11 and a["matches_saved_accounting"],
        "mc_mode_tables_match_ledger":all(r["matches_ledger"] for r in mc["mode_ledger_alignment"]),
        "shap_scope_and_arithmetic":shap["status"]=="RECOMPUTED_TREESHAP" and shap["sample_size"]==1000 and shap["max_additivity_error_min"]<1e-4 and shap["matches_saved_importance"],
        "inputs_unchanged":outputs["source_inventory.json"]["all_inputs_unchanged"],
    }
    return {"checks":checks,"status":"PASS" if all(checks.values()) else "FAIL",
            "meaning":"Internal evidence consistency only; not full-repository regression, G13 release certification, advisor approval, or fulfillment of every proposal requirement."}




def build_metric_registry(outputs):
    """Carry scope/units and evidence links for every published metric family."""
    inventory=outputs["source_inventory.json"]["inputs"]
    checkpoints={
        "departure_xgboost_baseline_v1":"artifacts/dual_core/models/departure_xgboost_baseline_v1.joblib",
        "departure_ridge_baseline_v1":"artifacts/dual_core/models/departure_ridge_baseline_v1.joblib",
        "outbound_logistic_raw_v1":"artifacts/remediation/outbound_classification/models/outbound_logistic_classifier_v1.joblib",
        "outbound_logistic_calibrated_v1":"artifacts/remediation/outbound_classification/models/outbound_logistic_calibrated_v1.joblib",
        "outbound_xgboost_raw_v1":"artifacts/remediation/outbound_classification/models/outbound_xgboost_classifier_v1.joblib",
        "outbound_xgboost_calibrated_v1":"artifacts/remediation/outbound_classification/models/outbound_xgboost_calibrated_v1.joblib",
    }
    records=[]
    def add(context,metrics):
        sources=context["source"] if isinstance(context["source"],list) else [context["source"]]
        context={**context,"source_sha256":{p:inventory[p]["sha256"] for p in sources},
                 "consumer":"docs/reconciliation/phase1_2/05_results.md","display_decimals":5}
        for metric,value in metrics.items():
            unit=context["unit"]
            if metric in ("n","tp","tn","fp","fn","sample_size","runs","completed_trials","physical_conflicts","buffer_violations","proven_optimal_count","feasible_count"):
                unit="count"
            elif metric in ("feasible_rate","prevalence","p_value","roc_auc","pr_auc","precision","recall","f1","brier_score","ece","log_loss","threshold"):
                unit="dimensionless"
            elif "runtime" in metric:unit="milliseconds"
            records.append({**context,"metric":metric,"unit":unit,"value":value})
    for r in outputs["ml_metrics.json"]["records"]:
        checkpoint=checkpoints.get(r["model_id"])
        context={k:r[k] for k in ("id","model_id","task","split","aggregation","source","evidence_status")}
        context.update(target=("ARR_DELAY" if r["task"].startswith("arrival") else "DEP_DELAY"),
            unit="minutes" if r["task"].endswith("regression") else "dimensionless",
            checkpoint=checkpoint,checkpoint_sha256=inventory[checkpoint]["sha256"] if checkpoint else None,
            checkpoint_relation="Model-ID path link; does not independently establish prediction-generation provenance" if checkpoint else "No checkpoint linkage asserted",
            formula=r.get("formula","scikit-learn metrics on stored columns; formulas in 04_evidence_policy.md"))
        add(context,r["metrics"])
        if "fold_macro_metrics" in r:
            add({**context,"id":r["id"]+"__macro","aggregation":"unweighted_mean_of_fold_metrics"},r["fold_macro_metrics"])
    for r in outputs["mc500_audit.json"]["groups"]:
        add({"id":"mc500_"+r["mode"]+"_"+r["initial_plan_solver"],"model_id":"configured_simulation_marginals",
             "task":"gate_robustness","target":"simulation_objective","split":"synthetic_500_CRN",
             "aggregation":"per_initial_solver","source":r["source"],"evidence_status":"RECOMPUTED_FROM_STORED_MODE_ROWS",
             "unit":"objective_points","seed":202601,"formula":r["cvar_convention"]},
            {k:r[k] for k in ("n","feasible_count","feasible_rate","objective_mean","objective_p90","objective_p99","cvar90","cvar95","physical_conflicts","buffer_violations","proven_optimal_count","runtime_p95_ms","runtime_max_ms")})
    for pair,r in outputs["mc500_audit.json"]["paired"].items():
        add({"id":"mc500_paired_"+pair,"model_id":"configured_simulation_marginals","task":"paired_policy_comparison",
             "target":"left_minus_right_objective","split":"synthetic_500_CRN","aggregation":"paired_same_scenario_and_hash",
             "source":[f"{MC}/fixed_plan_results.csv",f"{MC}/recourse_b1_retrospective_results.csv",f"{MC}/recourse_b2_online_results.csv",f"{MC}/foresight_c1_greedy_results.csv",f"{MC}/foresight_c2_optimal_results.csv"],
             "evidence_status":"RECOMPUTED_PAIRED","unit":"objective_points","formula":r["formula"]},
             {"n":r["n"],"mean_delta":r["mean_delta"],"se":r["se"],"ci95_lower":r["ci95_t"][0],"ci95_upper":r["ci95_t"][1],"p_value":r["p_value"]})
    for r in outputs["hpo_audit.json"]:
        add({"id":"hpo_"+r["task"],"model_id":r["study_name"],"task":r["task"],"target":"macro_PR_AUC" if r["direction"]=="MAXIMIZE" else "macro_MAE",
             "split":"rolling_development_2019_2022","aggregation":"study_best","source":r["source"],
             "evidence_status":"SQLITE_MATCHES_MANIFEST" if r["matches_manifest"] else "MISMATCH",
             "unit":"dimensionless" if r["direction"]=="MAXIMIZE" else "minutes","formula":"Best COMPLETE trial under stored study direction"},
             {"best_objective":r["best_value"],"completed_trials":r["trial_states"].get("COMPLETE",0)})
    shap=outputs["shap_audit.json"]
    if shap["status"]=="RECOMPUTED_TREESHAP":
        add({"id":"shap_departure_xgboost","model_id":shap["model_id"],"task":"regression_explanation","target":"DEP_DELAY",
             "split":"first_1000_outbound_rows_partition_2023_00000","aggregation":"TreeSHAP","source":shap["source"],
             "evidence_status":shap["status"],"unit":"minutes","formula":"base value + sum(SHAP) = model regression prediction"},
             {"sample_size":shap["sample_size"],"max_additivity_error_min":shap["max_additivity_error_min"],
              "max_saved_importance_difference_min":shap["max_saved_importance_difference_min"]})
    for r in outputs["benchmark_audit.json"]["solver_summary"]:
        add({"id":"g5_"+r["solver"],"model_id":r["solver"],"task":"gate_solver_comparison","target":"simulation_objective",
             "split":"five_stored_G5_scenarios","aggregation":"solver_mean_and_counts",
             "source":outputs["benchmark_audit.json"]["source"],"evidence_status":"REAGGREGATED_STORED_RUNS",
             "unit":"objective_points","formula":"summary across five scenario rows; no new runtime fairness proof"},
             {"runs":r["runs"],"feasible_count":r["feasible"],"proven_optimal_count":r["optimality_proven"],
              "objective_mean":r["mean_objective"],"runtime_max_ms":r["max_runtime_ms"]})
    return records



def collect(root=ROOT,recompute_shap=True):
    e=Evidence(root)
    proposal=extract_proposal(e.path(PROPOSAL))
    catalog=e.json(DOCS/"requirements_catalog.json")
    req=[]
    for item in catalog:
        matches=[p for p in proposal["paragraphs"] if any(needle in p["text"] for needle in item["source_contains"])]
        if not matches: raise ValueError("Unresolved proposal requirement "+item["id"])
        for path in item["implementation"]+item["evidence"]+item["tests"]: e.path(path)
        req.append({**{k:v for k,v in item.items() if k!="source_contains"},
                    "source_paragraphs":[p["id"] for p in matches],"source_quotes":[p["text"] for p in matches]})
    print("Auditing stored ML predictions...",flush=True)
    ml=audit_ml(e)
    print("Auditing read-only Optuna studies and Monte Carlo ledger...",flush=True)
    hpo=audit_hpo(e); mc=audit_mc(e); benchmark=audit_benchmark(e)
    print("Auditing SHAP and model identity...",flush=True)
    shap=audit_shap(e,recompute_shap); lineage=audit_lineage(e); models=audit_models(e)
    for name in ["system_freeze_manifest.json","DUAL_CORE_RELEASE_MANIFEST.json","configs/current_state.yaml"]: e.path(name)
    for directory in ["remediation_evidence/G9_thesis","remediation_evidence/G12C_scientific_reconciliation"]:
        for path in sorted((e.root/directory).glob("*.md")): e.path(path.relative_to(e.root))
    for path in sorted((e.root/"artifacts/manifests").glob("*.json")): e.path(path.relative_to(e.root))
    for name in ["scripts/reconcile_phase1_2.py","scripts/render_phase1_2_reports.py"]: e.path(name)
    if not e.unchanged(): raise RuntimeError("Input files changed during reconciliation")
    flat=[]
    for row in ml["records"]:
        context={k:row[k] for k in ["id","model_id","task","split","aggregation","source","evidence_status"]}
        for metric,value in row["metrics"].items(): flat.append({**context,"metric":metric,"value":value})
    outputs={"proposal_extract.json":proposal,"requirements.json":req,"requirements.csv":as_csv(req),
            "ml_metrics.json":ml,"metric_registry.csv":as_csv(flat),"hpo_audit.json":hpo,"mc500_audit.json":mc,
            "benchmark_audit.json":benchmark,"shap_audit.json":shap,"lineage_audit.json":lineage,"model_identity.json":models,
            "source_inventory.json":{"inputs":dict(sorted(e.inventory.items())),"input_count":len(e.inventory),"all_inputs_unchanged":True,
              "boundaries":["No training","No solver rerun","No 2024 row access","No legacy generator execution","No advisor approval inferred"]}}
    registry=build_metric_registry(outputs)
    outputs["metric_registry.csv"]=as_csv(registry)
    outputs["metric_registry.json"]=registry
    import importlib.metadata
    outputs["audit_metadata.json"]={"baseline_commit":"aed54a13fc330b387c303ecc488fc1280cfa1129",
        "python":sys.version.split()[0],"packages":{name:importlib.metadata.version(name) for name in ("numpy","pandas","scikit-learn","scipy","joblib","shap","xgboost","optuna")},
        "generator_sha256":sha256(e.root/"scripts/reconcile_phase1_2.py"),
        "report_renderer_sha256":sha256(e.root/"scripts/render_phase1_2_reports.py"),
        "verification_scope":"Read-only stored evidence arithmetic and source inventory, not G13 or advisor signoff"}
    outputs["results_tables.md"]=render_tables(outputs)
    outputs["validation.json"]=validate_outputs(outputs)
    return outputs


def publish(root: Path, outputs: dict, check=False):
    output=(root/OUT).resolve()
    if not output.is_relative_to(root.resolve()): raise ValueError("Output escapes repository")
    failures=[]
    if not check: output.mkdir(parents=True,exist_ok=True)
    for name,value in outputs.items():
        content=value if isinstance(value,str) else dumps(value)
        target=(output/name).resolve()
        if not target.is_relative_to(output): raise ValueError("Output filename escapes reconciliation directory")
        if check:
            if not target.exists() or target.read_text(encoding="utf-8")!=content: failures.append(name)
        else: target.write_text(content,encoding="utf-8")
    return failures


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check",action="store_true",help="Recompute and compare outputs without writing files")
    args=parser.parse_args()
    sys.path.insert(0,str(ROOT))
    outputs=collect()
    differences=publish(ROOT,outputs,args.check)
    if outputs["validation.json"]["status"]!="PASS":
        print("Evidence consistency checks failed; see validation.json"); return 1
    if differences:
        print("Out-of-date reconciliation outputs: "+", ".join(differences)); return 1
    print(("Verified" if args.check else "Published")+f" {len(outputs)} outputs; input files unchanged.")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
