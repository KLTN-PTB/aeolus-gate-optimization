// @vitest-environment jsdom
import { beforeEach, afterEach, describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/react';
import { LabPage } from './LabPage';
import { GatePage } from './GatePage';
import { Gantt } from './charts';
import { api } from './api';
import { defaults, type Result } from './types';
import type { Experiment, ExperimentResult } from './experimentTypes';

vi.mock('./api', () => ({api: vi.fn()}));
const call = vi.mocked(api);
const rid = 'r'.repeat(32);
const output: Result = {
  summary: {movement_count: 2, arrivals: 1, departures: 1, occupancy_count: 1, estimated_occupancies: 0,
    paired_occupancies: 1, peak_occupancy: 1, contact_gates: 1, remote_gates: 0, assigned_count: 1,
    remote_count: 0, reassignments: 0, baseline_covered: 1, solver_status: 'FEASIBLE', feasible: true,
    optimality_proven: false, independent_verifier_valid: true, conflicts: 0, solver_runtime_sec: .1,
    decision_cost: 0, comparison_count: 0, mae: null, rmse: null},
  predictions: [],
  turns: [{turn_id: 't1', arrival_leg_id: 'a', departure_leg_id: 'd', carrier: 'DL', flight_number: '101',
    pair_type: 'INFERRED_PAIR', nominal_gate_id: 'G001', simulated_arrival_min: 100, simulated_departure_min: 160,
    gate_release_min: 175, is_estimated: false, unmatched_status: null, probability_delay_15: .2}],
  assignments: [{flight_id: 't1', gate_id: 'G001', occupancy_start_min: 100, occupancy_end_min: 175, is_overflow: false, is_reassignment: false}],
  gates: [{gate_id: 'G001', is_remote: false}],
  manifest: {config: {...defaults, service_date: '2026-07-01'}, warnings: [], models: {}, reference_midnight_utc: '2026-07-01T04:00:00Z', created_at: '', time_basis: 'ML_PREDICTED'},
};
const experiment: Experiment = {id: 'e'.repeat(32), run_id: rid, created_at: '2026-10-18T00:00:00Z', status: 'completed', stage: 'done',
  completed: 1, total: 1, cancel_requested: 0, config: {kind: 'benchmark', mode: 'quick', seed: 202601, scenarios: 20, time_limit_sec: 5, snapshot_hash: 'hash'}};
const result: ExperimentResult = {experiment, cases: [{case_id: 'b_greedy_202601', algorithm: 'greedy', mode: 'benchmark', seed: 202601,
  status: 'FEASIBLE', feasible: true, decision_cost: 0, risk_cost: null, conflicts: 0, runtime_sec: .1}], groups: [], assumptions: [], paired: []};

beforeEach(() => {
  localStorage.clear(); vi.clearAllMocks();
  call.mockImplementation(async path => {
    if (path.endsWith('/experiments')) return [];
    if (path.endsWith('/plans')) return {ready: true, has_arrivals: true, snapshot_hash: 'hash', plans: [{id: 'pipeline', algorithm: 'greedy', seed: 202601, label: 'Pipeline Greedy'}]};
    if (path.endsWith('/results')) return result;
    if (path.includes('/plans/')) return output;
    throw Error(path);
  });
});
afterEach(cleanup);

describe('experiment pages', () => {
  it('shows fixed and recourse feasibility separately using the returned Monte Carlo groups', async () => {
    const mc = {...experiment, config: {...experiment.config, kind: 'montecarlo' as const, scenarios: 500}};
    const common = {count: 500, timeouts: 0, failures: 0, mean: 1, median: 1, std: 0, min: 1, max: 1,
      p95: 1, cvar95: 1, mean_ci95: [1, 1], rate_ci95: [0, 1], cost_sample_count: 500,
      runtime_median: .1, mean_conflicts: 0, mean_remote: 0, mean_reassignments: 0, convergence: []};
    const groups: ExperimentResult['groups'] = [
      {...common, key: 'greedy-fixed', algorithm: 'greedy', mode: 'fixed', feasible_count: 0, feasible_rate: 0},
      {...common, key: 'hybrid-recourse', algorithm: 'hybrid', mode: 'recourse', feasible_count: 500, feasible_rate: 1,
        on_time_feasible_count: 500, on_time_feasible_rate: 1},
    ];
    call.mockImplementation(async path => {
      if (path.endsWith('/experiments')) return [mc];
      if (path.endsWith('/plans')) return {ready: true, plans: []};
      if (path.endsWith('/results')) return {...result, experiment: mc, groups};
      throw Error(path);
    });
    render(<LabPage kind="montecarlo" runId={rid} result={output} onOpen={vi.fn()}/>);
    await screen.findByText('Đọc riêng hai chế độ Monte Carlo.');
    expect(screen.getByText(/Greedy 0\/500/)).toBeTruthy();
    expect(screen.getByText(/Hybrid 500\/500/)).toBeTruthy();
    expect(screen.getByText(/Chi phí rủi ro của lịch cố định và chi phí sửa lịch không cùng thước đo/)).toBeTruthy();
  });
  it('submits research Monte Carlo defaults and chosen verified plans', async () => {
    render(<LabPage kind="montecarlo" runId={rid} result={output} onOpen={vi.fn()}/>);
    await waitFor(() => expect((screen.getByLabelText('Lịch Greedy') as HTMLSelectElement).value).toBe('pipeline'));
    fireEvent.change(screen.getByLabelText('Chế độ thí nghiệm'), {target: {value: 'research'}});
    expect((screen.getByLabelText('Số kịch bản Monte Carlo') as HTMLInputElement).value).toBe('500');
    expect((screen.getByLabelText('Ngân sách thí nghiệm') as HTMLInputElement).value).toBe('5');
    call.mockResolvedValueOnce({...experiment, config: {...experiment.config, kind: 'montecarlo'}});
    fireEvent.click(screen.getByRole('button', {name: /Chạy Monte Carlo/}));
    await waitFor(() => {
      const post = call.mock.calls.find(([,options]) => options?.method === 'POST');
      expect(JSON.parse(String(post?.[1]?.body))).toMatchObject({kind: 'montecarlo', mode: 'research', scenarios: 500, time_limit_sec: 5, plan_ids: ['pipeline']});
    });
  });
  it('restores completed experiment, provides exports and opens exact Gantt plan', async () => {
    call.mockImplementation(async path => {
      if (path.endsWith('/experiments')) return [experiment];
      if (path.endsWith('/plans')) return {ready: true, plans: []};
      if (path.endsWith('/results')) return result;
      if (path.includes('/plans/')) return output;
      throw Error(path);
    });
    const open = vi.fn();
    render(<LabPage kind="benchmark" runId={rid} result={output} onOpen={open}/>);
    await screen.findByText('FEASIBLE');
    expect(screen.getByRole('link', {name: 'bundle'}).getAttribute('href')).toContain(experiment.id);
    fireEvent.click(screen.getByRole('button', {name: 'Xem Gantt'}));
    await waitFor(() => expect(open).toHaveBeenCalledWith(expect.objectContaining({experimentId: experiment.id, caseId: 'b_greedy_202601'})));
    expect(localStorage.getItem(`aeolus-experiment-${rid}-benchmark`)).toBe(experiment.id);
  });
  it('shows demand diagnosis and all turns even with no feasible assignments', async () => {
    render(<GatePage runId={rid} result={{...output, assignments: [], summary: {...output.summary, feasible: false, assigned_count: 0, peak_occupancy: 3, solver_status: 'UNKNOWN'}}} view={null} onView={vi.fn()}/>);
    expect(screen.getByText(/thiếu ít nhất 2 vị trí/)).toBeTruthy();
    expect(screen.getByText('Chưa được phân')).toBeTruthy();
    expect(screen.getByText('Chi tiết từng lượt chiếm dụng')).toBeTruthy();
    await waitFor(() => expect(call).toHaveBeenCalled());
  });
  it('pages large gate inventories and offers time windows without dropping assignments', () => {
    const gates = Array.from({length: 26}, (_,i) => ({gate_id: `G${String(i+1).padStart(3,'0')}`, is_remote: false}));
    render(<Gantt result={{...output, gates}} filter="" onSelect={vi.fn()}/>);
    fireEvent.click(screen.getByRole('checkbox', {name: 'Hiện cổng trống'}));
    expect(screen.queryByText('G026')).toBeNull();
    fireEvent.click(screen.getByRole('button', {name: 'Cổng sau'}));
    expect(screen.getByText('G026')).toBeTruthy();
    fireEvent.change(screen.getByLabelText('Cửa sổ Gantt'), {target: {value: '2'}});
    expect(screen.getByRole('button', {name: 'Sau →'})).toBeTruthy();
  });
});

it('submits a separate baseline profile without changing the budget', async () => {
  render(<LabPage kind="benchmark" runId={rid} result={output} onOpen={vi.fn()}/>);
  await waitFor(() => expect((screen.getByRole('button', {name: /Chạy benchmark/}) as HTMLButtonElement).disabled).toBe(false));
  expect((screen.getByLabelText('Cấu hình solver') as HTMLSelectElement).value).toBe('optimized');
  fireEvent.change(screen.getByLabelText('Cấu hình solver'), {target:{value:'baseline'}});
  fireEvent.change(screen.getByLabelText('Ngân sách thí nghiệm'), {target:{value:'120'}});
  call.mockResolvedValueOnce(experiment);
  fireEvent.click(screen.getByRole('button', {name:/Chạy benchmark/}));
  await waitFor(() => {
    const post=call.mock.calls.find(([,options]) => options?.method==='POST');
    expect(JSON.parse(String(post?.[1]?.body))).toMatchObject({solver_profile:'baseline',time_limit_sec:120});
  });
});

it('keeps a late initializer visible and opens its Gantt without claiming CP optimality', async () => {
  const late={...result.cases[0],algorithm:'cpsat',solver_protocol_version:2,solver_profile:'optimized',
    solution_source:'GREEDY_INITIALIZER',termination_reason:'TIME_LIMIT',budget_compliant:false,runtime_sec:120.2};
  call.mockImplementation(async path => {
    if (path.endsWith('/experiments')) return [{...experiment,config:{...experiment.config,solver_profile:'optimized',solver_protocol_version:2}}];
    if (path.endsWith('/plans')) return {ready:true,plans:[]};
    if (path.endsWith('/results')) return {...result,cases:[late]};
    if (path.includes('/plans/')) return output;
    throw Error(path);
  });
  const open=vi.fn();
  render(<LabPage kind="benchmark" runId={rid} result={output} onOpen={open}/>);
  expect(await screen.findByText('Chỉ có nghiệm Greedy khởi tạo')).toBeTruthy();
  expect(screen.getByText('TIME_LIMIT · Vượt ngân sách')).toBeTruthy();
  expect(screen.queryByText('Đã chứng minh tối ưu')).toBeNull();
  fireEvent.click(screen.getByRole('button',{name:'Xem Gantt'}));
  await waitFor(() => expect(open).toHaveBeenCalled());
});
