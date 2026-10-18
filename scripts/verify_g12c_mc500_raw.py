import json
import numpy as np
import pandas as pd
from pathlib import Path

def compute_cvar(series, alpha=0.90):
    val = np.percentile(series, alpha * 100)
    tail = series[series >= val]
    return float(tail.mean()) if len(tail) > 0 else float(val)

def main():
    run_dir = Path("artifacts/remediation/monte_carlo_mc500/mc500_20261012_173538_afa5db")
    ledger_entries = pd.read_csv(run_dir / "execution_ledger_entries.csv")
    ledger_gen = pd.read_csv(run_dir / "execution_ledger_generation.csv")

    mode_a = pd.read_csv(run_dir / "fixed_plan_results.csv")
    mode_b1 = pd.read_csv(run_dir / "recourse_b1_retrospective_results.csv")
    mode_b2 = pd.read_csv(run_dir / "recourse_b2_online_results.csv")
    mode_c1 = pd.read_csv(run_dir / "foresight_c1_greedy_results.csv")
    mode_c2 = pd.read_csv(run_dir / "foresight_c2_optimal_results.csv")

    with open(run_dir / "gate_inventory.json", "r") as f:
        gate_inv = json.load(f)

    print("=== PHASE A: RAW AUDIT & VERIFICATION ===")
    print(f"Total ledger entries: {len(ledger_entries)}")
    print(f"Total generation entries: {len(ledger_gen)}")
    print(f"Unique scenario IDs in ledger: {ledger_entries['scenario_id'].nunique()}")
    print(f"Unique realization hashes: {ledger_entries['realization_hash'].nunique()}")
    
    # Primary key check
    pk = ['run_id', 'scenario_id', 'recourse_mode', 'initial_plan_solver']
    print(f"Duplicates on primary key: {ledger_entries.duplicated(subset=pk).sum()}")

    # Slots per scenario
    slots_per_scen = ledger_entries.groupby('scenario_id').size()
    print(f"Min/Max slots per scenario: {slots_per_scen.min()} / {slots_per_scen.max()}")

    # Feasibility breakdown
    print("\n--- Feasibility Breakdown ---")
    feas_table = ledger_entries.groupby(['recourse_mode', 'initial_plan_solver', 'composite_feasible']).size().unstack(fill_value=0)
    print(feas_table)

    total_feasible = (ledger_entries['composite_feasible'] == True).sum()
    total_infeasible = (ledger_entries['composite_feasible'] == False).sum()
    print(f"Total feasible: {total_feasible}, Total infeasible: {total_infeasible}, Sum: {total_feasible + total_infeasible}")

    # Objective percentiles & CVaR
    print("\n--- Objective Distribution Check ---")
    results = {}
    datasets = {
        "Mode_A_Greedy": mode_a[mode_a['initial_plan_solver'] == 'Greedy'],
        "Mode_A_All": mode_a,
        "Mode_B1_All": mode_b1,
        "Mode_B2_All": mode_b2,
        "Mode_C1": mode_c1,
        "Mode_C2": mode_c2,
    }

    for name, df in datasets.items():
        objs = df['objective_value'].values
        runtimes = df['runtime_ms'].values if 'runtime_ms' in df.columns else np.array([])
        results[name] = {
            "mean": float(np.mean(objs)),
            "std": float(np.std(objs, ddof=1)),
            "median": float(np.median(objs)),
            "min": float(np.min(objs)),
            "max": float(np.max(objs)),
            "p50": float(np.percentile(objs, 50)),
            "p90": float(np.percentile(objs, 90)),
            "p95": float(np.percentile(objs, 95)),
            "p99": float(np.percentile(objs, 99)),
            "cvar90": compute_cvar(objs, 0.90),
            "cvar95": compute_cvar(objs, 0.95),
            "runtime_mean": float(np.mean(runtimes)) if len(runtimes) else None,
            "runtime_p95": float(np.percentile(runtimes, 95)) if len(runtimes) else None,
            "runtime_max": float(np.max(runtimes)) if len(runtimes) else None,
        }
        print(f"\n{name}:")
        for k, v in results[name].items():
            print(f"  {k}: {v}")

    # Mode A physical conflict count vs buffer violations
    print("\n--- Mode A Physical Conflict & Buffer Violations ---")
    print(f"Mode A total physical contact conflicts: {mode_a['physical_contact_conflict_count'].sum()}")
    print(f"Mode A mean physical conflicts per evaluation: {mode_a['physical_contact_conflict_count'].mean()}")
    print(f"Mode A mean physical conflicts per scenario (Greedy): {mode_a[mode_a['initial_plan_solver']=='Greedy']['physical_contact_conflict_count'].mean()}")
    print(f"Mode A total buffer violations: {mode_a['buffer_violation_count'].sum()}")
    print(f"Mode A mean buffer violations: {mode_a['buffer_violation_count'].mean()}")

    # Remote stand usage audit
    print("\n--- Remote Stand Usage Audit ---")
    print(f"Resource inventory remote gate ID: {[g['gate_id'] for g in gate_inv['gates'] if g.get('is_overflow')]}")
    b2_remote = mode_b2[mode_b2['remote_count'] > 0]
    print(f"Mode B2 rows with remote_count > 0: {len(b2_remote)}")
    print(f"Unique scenarios in B2 using remote: {b2_remote['scenario_index'].unique().tolist()}")
    print(b2_remote[['scenario_index', 'initial_plan_solver', 'remote_count', 'max_concurrent_remote_usage']])

    # Mode C2 status & deadline audit
    print("\n--- Mode C2 Solver Status & Optimality Audit ---")
    print(mode_c2['solver_status'].value_counts())
    print(mode_c2['is_optimal_proven'].value_counts())
    c2_non_opt = mode_c2[mode_c2['solver_status'] != 'OPTIMAL']
    print("Non-optimal C2 rows:")
    print(c2_non_opt[['scenario_index', 'solver_status', 'is_optimal_proven', 'objective_value', 'runtime_ms']])

    # Export verified values to json
    out_path = Path("remediation_evidence/G12C_scientific_reconciliation/verified_mc500_raw_values.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nWrote verified raw values to: {out_path}")

if __name__ == "__main__":
    main()
