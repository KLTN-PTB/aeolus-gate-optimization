import sys
from pathlib import Path
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import numpy as np

data_path = PROJECT_ROOT / 'src' / 'artifacts' / 'predictions' / 'atl_2024_01_01_full_day_1500_flights.parquet'
df = pd.read_parquet(data_path)
df = df.sort_values('sched_time_min').reset_index(drop=True)

for num_gates in [180, 190, 195]:
    all_gates = [f"G{i:02d}" if i < 100 else f"G{i}" for i in range(1, num_gates + 1)]
    
    # 1. Initial Schedule (No delay)
    gate_free_at = {g: 0 for g in all_gates}
    initial_gate = {}
    
    for idx, r in df.iterrows():
        f_id = r['flight_key']
        sched = int(r['sched_time_min'])
        turn = int(r['turnaround_time_min']) if pd.notna(r['turnaround_time_min']) else int(r['dwell_time_min'])
        start = max(0, sched - 15)
        end = sched + turn + 15
        
        best_g = None
        for g in all_gates:
            if gate_free_at[g] <= start:
                best_g = g
                break
        if best_g is None:
            best_g = min(all_gates, key=lambda g: gate_free_at[g])
        initial_gate[f_id] = best_g
        gate_free_at[best_g] = end
        
    df['initial_gate'] = df['flight_key'].map(initial_gate)
    
    # 2. Dynamic with ML delays
    eff_delays = (df['p_delay'] * df['delay_est_min']).round().astype(int)
    df['eff_delay_min'] = eff_delays
    df['pred_start_min'] = np.maximum(0, df['sched_time_min'] + df['eff_delay_min'] - 15)
    durations = df['turnaround_time_min'].fillna(df['dwell_time_min']).astype(int)
    df['pred_end_min'] = df['sched_time_min'] + df['eff_delay_min'] + durations + 15
    
    # Detect initial conflicts
    conflicted = 0
    for g, group in df.groupby('initial_gate'):
        group = group.sort_values('pred_start_min')
        prev_end = -1
        for _, r in group.iterrows():
            if r['pred_start_min'] < prev_end:
                conflicted += 1
            prev_end = max(prev_end, r['pred_end_min'])
            
    # 3. Dynamic Reassignment
    dynamic_gate = {}
    gate_timeline = {g: [] for g in all_gates}
    df_sorted = df.sort_values('pred_start_min').reset_index(drop=True)
    
    reassigned = 0
    unassigned = 0
    
    for _, r in df_sorted.iterrows():
        f_id = r['flight_key']
        s = r['pred_start_min']
        e = r['pred_end_min']
        init_g = initial_gate[f_id]
        
        conflict = any(not (e <= occ_s or s >= occ_e) for occ_s, occ_e in gate_timeline[init_g])
        if not conflict:
            dynamic_gate[f_id] = init_g
            gate_timeline[init_g].append((s, e))
        else:
            alt_g = None
            for g in all_gates:
                if not any(not (e <= occ_s or s >= occ_e) for occ_s, occ_e in gate_timeline[g]):
                    alt_g = g
                    break
            if alt_g is not None:
                dynamic_gate[f_id] = alt_g
                gate_timeline[alt_g].append((s, e))
                reassigned += 1
            else:
                dynamic_gate[f_id] = "OVERFLOW"
                unassigned += 1
                reassigned += 1
                
    print(f"=== Số cổng: {num_gates} ===")
    print(f"  Số chuyến xung đột do trễ ML: {conflicted}")
    print(f"  Số chuyến phải đổi cổng: {reassigned} ({reassigned/len(df)*100:.2f}%)")
    print(f"  Số chuyến giữ nguyên cổng cũ: {len(df) - reassigned} ({(len(df)-reassigned)/len(df)*100:.2f}%)")
    print(f"  Số chuyến bị tràn cổng (không còn cổng trống): {unassigned}")
