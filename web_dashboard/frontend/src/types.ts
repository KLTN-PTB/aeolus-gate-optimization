export interface Config {
  dataset_id: string; service_date: string; airport: 'ATL';
  preset: 'large' | 'medium' | 'small' | 'custom'; contact_gates: number; remote_gates: number;
  min_turnaround_min: number; default_dwell_min: number; buffer_min: number;
  solver: 'cpsat' | 'greedy' | 'hybrid'; time_limit_sec: number;
  greedy_fallback: boolean;
}
export interface Dataset {
  id: string; filenames: string[]; input_rows: number; valid_rows: number; invalid_rows: number;
  non_atl_rows: number; can_run: boolean; warnings: string[];
  dates: {date: string; arrivals: number; departures: number; total: number}[];
  errors: {source_index: number; row: number; message: string}[];
  preview: Record<string, unknown>[];
}
export interface Run {
  id: string; created_at: string; status: 'queued' | 'running' | 'completed' | 'failed' | 'interrupted';
  stage: string; error: string | null; config: Config;
}
export interface Prediction {
  flight_id: string; flight_direction: 'ARR' | 'DEP'; carrier: string; flight_number: string;
  origin: string; destination: string; scheduled_event_local: string;
  predicted_delay_min: number; probability_delay_15?: number | null; actual_delay_min: number | null;
  model_id: string; model_version: string; model_sha256: string; prediction_cutoff_utc: string;
}
export interface Turn {
  turn_id: string; arrival_leg_id: string | null; departure_leg_id: string | null;
  carrier: string; flight_number: string; pair_type: string; nominal_gate_id: string | null;
  simulated_arrival_min: number; simulated_departure_min: number; gate_release_min: number;
  is_estimated: boolean; unmatched_status: string | null; probability_delay_15: number | null;
}
export interface Assignment {
  flight_id: string; gate_id: string; occupancy_start_min: number; occupancy_end_min: number;
  is_overflow: boolean; is_reassignment: boolean;
}
export interface Summary {
  movement_count: number; arrivals: number; departures: number; occupancy_count: number;
  estimated_occupancies: number; paired_occupancies: number; peak_occupancy: number;
  contact_gates: number; remote_gates: number; assigned_count: number; remote_count: number;
  reassignments: number; baseline_covered: number; solver_status: string; feasible: boolean;
  optimality_proven: boolean; independent_verifier_valid: boolean; conflicts: number;
  solver_runtime_sec: number; decision_cost: number | null; comparison_count: number;
  mae: number | null; rmse: number | null;
  actual_solver?: string; fallback_used?: boolean; raw_solver_status?: string;
}
export interface Result {
  summary: Summary; predictions: Prediction[]; turns: Turn[]; assignments: Assignment[];
  gates: {gate_id: string; is_remote: boolean}[];
  manifest: {config: Config; warnings: string[]; models: Record<string, {model_id: string; status: string; version: string; sha256: string}>;
    reference_midnight_utc: string; created_at: string; time_basis: string};
}
export const defaults: Config = {
  dataset_id: '', service_date: '', airport: 'ATL', preset: 'large', contact_gates: 150, remote_gates: 0,
  min_turnaround_min: 45, default_dwell_min: 60, buffer_min: 15, solver: 'cpsat', time_limit_sec: 30, greedy_fallback: true,
};
export const solverNames = {greedy: 'Deterministic Greedy', cpsat: 'CP-SAT', hybrid: 'Hybrid (CP-SAT/Greedy → SA)'};
export const stages = ['validation', 'models', 'prediction', 'pairing', 'optimization', 'verification', 'export', 'done'];
export const stageNames: Record<string, string> = {
  validation: 'Kiểm tra đầu vào', models: 'Xác minh mô hình', prediction: 'Dự báo độ trễ',
  pairing: 'Tạo lượt chiếm dụng', optimization: 'Tối ưu phân cổng', verification: 'Kiểm tra ràng buộc',
  export: 'Xuất kết quả', done: 'Hoàn tất', timeout: 'Vượt thời gian', worker: 'Tiến trình tính toán',
};
export const fmt = (value: number | null | undefined, decimals = 0) => value == null ? '—' : value.toLocaleString('vi-VN', {maximumFractionDigits: decimals});
export const isBusy = (run: Run | null) => !!run && ['queued', 'running'].includes(run.status);
export const configMatches = (a: Config, b: Config) => Object.keys(defaults).every(key => a[key as keyof Config] === b[key as keyof Config]);
export const riskLevel = (p: Pick<Prediction, 'probability_delay_15' | 'predicted_delay_min'>) =>
  p.probability_delay_15 != null ? (p.probability_delay_15 >= .5 ? 'high' : p.probability_delay_15 >= .25 ? 'medium' : 'low')
    : p.predicted_delay_min >= 30 ? 'high' : p.predicted_delay_min >= 15 ? 'medium' : 'low';
export function timelineClock(minute: number, midnight: string) {
  if (!midnight) return `${Math.floor(minute / 60)}:${String(Math.round(minute % 60)).padStart(2, '0')}`;
  const instant = new Date(new Date(midnight).getTime() + minute * 60_000);
  return new Intl.DateTimeFormat('vi-VN', {timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit', hourCycle: 'h23'}).format(instant);
}

export function timelineDayOffset(minute: number, midnight: string) {
  if (!midnight) return Math.floor(minute/1440);
  const calendar = (date: Date) => {
    const p = new Intl.DateTimeFormat('en-US', {timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit'}).formatToParts(date);
    const get = (type: string) => Number(p.find(x => x.type === type)!.value);
    return Date.UTC(get('year'), get('month')-1, get('day'));
  };
  const reference = new Date(midnight);
  return Math.round((calendar(new Date(reference.getTime()+minute*60_000))-calendar(reference))/86_400_000);
}
export function serviceDayMinutes(midnight: string) {
  return [1380,1440,1500].find(m => timelineClock(m,midnight)==='00:00' && timelineDayOffset(m,midnight)===1) || 1440;
}
