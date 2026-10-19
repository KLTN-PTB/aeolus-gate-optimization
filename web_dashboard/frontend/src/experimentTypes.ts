import type { Result } from './types';
export const algorithmNames: Record<string, string> = {greedy: 'Greedy', cpsat: 'CP-SAT', sa: 'SA độc lập', hybrid: 'Hybrid'};
export interface Plan {id: string; label: string; algorithm: string; seed: number; snapshot_hash: string}
export interface Plans {plans: Plan[]; ready: boolean; reason?: string; snapshot_hash?: string; has_arrivals?: boolean}
export interface Experiment {
  id: string; run_id: string; created_at: string; status: string; stage: string; error?: string;
  completed: number; total: number; cancel_requested: number;
  config: {kind: 'benchmark' | 'montecarlo'; mode: string; seed: number; scenarios: number; time_limit_sec: number; snapshot_hash: string; plans?: Plan[]};
}
export interface Case {
  case_id: string; algorithm: string; mode: string; seed: number; status: string; feasible: boolean;
  scenario?: number; source_plan_id?: string; realization_hash?: string;
  decision_cost: number | null; risk_cost: number | null; conflicts: number | null;
  runtime_sec: number; assigned_count?: number; remote_count?: number; reassignments?: number;
  peak?: number; optimality_proven?: boolean; best_bound?: number | null; gap?: number | null;
  error?: string; gate_conflicts?: Record<string, number>;
  initializer?: string | null; cp_status?: string | null; sa_iterations?: number | null;
  stage1_ms?: number | null; stage2_ms?: number | null;
  trace?: {initial_solution_source?: string; cp_solver_status?: string; sa_iterations?: number;
    initial_cost?: number; final_cost?: number; stage1_wall_clock_ms?: number; stage2_wall_clock_ms?: number};
  breakdown?: {reassignment_cost: number; overflow_cost: number};
}
export interface Group {
  key: string; algorithm: string; mode: string; source_plan_id?: string;
  count: number; feasible_count: number; timeouts: number; failures: number; feasible_rate: number;
  mean: number | null; median: number | null; std: number | null; min: number | null; max: number | null;
  p95: number | null; cvar95: number | null; mean_ci95: number[] | null; rate_ci95: number[] | null;
  cost_sample_count: number; runtime_median: number; mean_conflicts: number | null;
  mean_remote: number | null; mean_reassignments: number | null;
  convergence: {n: number; feasible_rate: number}[];
}
export interface ExperimentResult {
  experiment: Experiment; cases: Case[]; groups: Group[]; assumptions: string[];
  sampling?: {hash: string; shape: number[]; unique_scenarios: number; arrival_ids: string[]};
  paired: {a: string; b: string; pairs: number; mean_delta: number | null; ci95: number[] | null}[];
}
export interface OpenPlan {result: Result; label: string; experimentId: string; caseId: string}
export const running = (e: Experiment | null) => !!e && ['queued', 'running'].includes(e.status);
export const experimentStatus: Record<string, string> = {queued: 'Đang chờ', running: 'Đang chạy', completed: 'Hoàn tất',
  cancelled: 'Đã dừng', interrupted: 'Gián đoạn', failed: 'Lỗi', partial: 'Hoàn tất một phần'};
