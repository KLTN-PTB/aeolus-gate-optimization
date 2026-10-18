import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats

run_dir = Path("artifacts/remediation/monte_carlo_mc500/mc500_20261012_173538_afa5db")

df_a = pd.read_csv(run_dir / "fixed_plan_results.csv")
df_b1 = pd.read_csv(run_dir / "recourse_b1_retrospective_results.csv")
df_b2 = pd.read_csv(run_dir / "recourse_b2_online_results.csv")
df_c1 = pd.read_csv(run_dir / "foresight_c1_greedy_results.csv")
df_c2 = pd.read_csv(run_dir / "foresight_c2_optimal_results.csv")

def compute_detailed_stats(df, name):
    objs = df["objective_value"].values
    runtimes = df["runtime_ms"].values
    q = np.percentile(objs, [50, 90, 95, 99])
    cvar90 = objs[objs >= q[1]].mean() if len(objs[objs >= q[1]]) > 0 else q[1]
    cvar95 = objs[objs >= q[2]].mean() if len(objs[objs >= q[2]]) > 0 else q[2]
    
    return {
        "name": name,
        "count": len(df),
        "mean_obj": float(np.mean(objs)),
        "std_obj": float(np.std(objs, ddof=1)),
        "median_obj": float(np.median(objs)),
        "min_obj": float(np.min(objs)),
        "max_obj": float(np.max(objs)),
        "p50_obj": float(q[0]),
        "p90_obj": float(q[1]),
        "p95_obj": float(q[2]),
        "p99_obj": float(q[3]),
        "cvar90_obj": float(cvar90),
        "cvar95_obj": float(cvar95),
        "feasible_count": int(df["composite_feasible"].sum()),
        "feasible_rate": float(df["composite_feasible"].mean()),
        "mean_conflicts": float(df["physical_contact_conflict_count"].mean()),
        "total_conflicts": int(df["physical_contact_conflict_count"].sum()),
        "mean_buffer_viols": float(df["buffer_violation_count"].mean()),
        "mean_remote_usage": float(df["remote_count"].mean()),
        "mean_max_remote_concurrent": float(df["max_concurrent_remote_usage"].mean()),
        "max_remote_concurrent_peak": int(df["max_concurrent_remote_usage"].max()),
        "mean_unassigned": float(df["unassigned_flight_count"].mean()),
        "mean_reassignments": float(df["reassignment_count"].mean()),
        "mean_runtime_ms": float(np.mean(runtimes)),
        "p95_runtime_ms": float(np.percentile(runtimes, 95)),
        "max_runtime_ms": float(np.max(runtimes)),
    }

results = []
for solver in ["Greedy", "CPSat", "Hybrid"]:
    results.append(compute_detailed_stats(df_a[df_a["initial_plan_solver"] == solver], f"Mode_A_{solver}"))
for solver in ["Greedy", "CPSat", "Hybrid"]:
    results.append(compute_detailed_stats(df_b1[df_b1["initial_plan_solver"] == solver], f"Mode_B1_{solver}"))
for solver in ["Greedy", "CPSat", "Hybrid"]:
    results.append(compute_detailed_stats(df_b2[df_b2["initial_plan_solver"] == solver], f"Mode_B2_{solver}"))
results.append(compute_detailed_stats(df_c1, "Mode_C1_ForesightGreedy"))
results.append(compute_detailed_stats(df_c2, "Mode_C2_ForesightCPSat"))

df_stats = pd.DataFrame(results)
print(df_stats[["name", "mean_obj", "std_obj", "median_obj", "p95_obj", "cvar95_obj", "feasible_rate", "mean_remote_usage", "mean_runtime_ms"]].to_string(index=False))

# Paired Comparisons (CPSat initial as reference for CRN)
s_a = df_a[df_a["initial_plan_solver"] == "CPSat"].sort_values("scenario_index")["objective_value"].values
s_b1 = df_b1[df_b1["initial_plan_solver"] == "CPSat"].sort_values("scenario_index")["objective_value"].values
s_b2 = df_b2[df_b2["initial_plan_solver"] == "CPSat"].sort_values("scenario_index")["objective_value"].values
s_c1 = df_c1.sort_values("scenario_index")["objective_value"].values
s_c2 = df_c2.sort_values("scenario_index")["objective_value"].values

def paired_test(x, y, label):
    diff = x - y
    n = len(diff)
    mean_diff = np.mean(diff)
    std_diff = np.std(diff, ddof=1)
    se = std_diff / np.sqrt(n)
    t_crit = stats.t.ppf(0.975, df=n-1)
    ci_lower = mean_diff - t_crit * se
    ci_upper = mean_diff + t_crit * se
    t_stat = mean_diff / se if se > 0 else 0.0
    p_val = 2 * (1 - stats.t.cdf(abs(t_stat), df=n-1))
    return {
        "comparison": label,
        "mean_diff": round(mean_diff, 4),
        "std_diff": round(std_diff, 4),
        "se": round(se, 4),
        "ci_95": (round(ci_lower, 4), round(ci_upper, 4)),
        "t_stat": round(t_stat, 4),
        "p_val": p_val,
    }

pairs = [
    paired_test(s_a, s_b2, "Mode A vs Mode B2 (Benefit of Causal Recourse)"),
    paired_test(s_b1, s_b2, "Mode B1 vs Mode B2 (Hindsight vs Online)"),
    paired_test(s_b2, s_c1, "Mode B2 vs Mode C1 (Online vs Foresight Greedy)"),
    paired_test(s_b2, s_c2, "Mode B2 vs Mode C2 (Causal Recourse Gap / Price of Uncertainty)"),
    paired_test(s_c1, s_c2, "Mode C1 vs Mode C2 (Heuristic Foresight Gap)"),
]

print("\n=== PAIRED COMPARISON TESTS (N=500) ===")
for p in pairs:
    print(f"{p['comparison']}:")
    print(f"  Mean Diff: {p['mean_diff']}, SE: {p['se']}, 95% CI: {p['ci_95']}, t: {p['t_stat']}, p: {p['p_val']:.4e}")

# Save full stats table to json for reports
with open("remediation_evidence/MC500_official_experiment/detailed_statistical_metrics.json", "w", encoding="utf-8") as f:
    json.dump({"metrics": results, "paired_tests": pairs}, f, indent=2)
print("\nExported detailed_statistical_metrics.json")
