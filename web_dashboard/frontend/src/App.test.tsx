// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import App from './App';
import { api } from './api';
import { defaults, type Config, type Dataset, type Result, type Run } from './types';

vi.mock('./api', () => ({api: vi.fn()}));
const call = vi.mocked(api);
const id = 'a'.repeat(32);
const config: Config = {...defaults, dataset_id: id, service_date: '2026-07-01'};
const dataset: Dataset = {id, filenames: ['schedule.parquet'], input_rows: 2, valid_rows: 2, invalid_rows: 0,
  non_atl_rows: 0, can_run: true, warnings: [], dates: [{date: '2026-07-01', total: 2, arrivals: 1, departures: 1}], errors: [], preview: []};
const run: Run = {id: 'b'.repeat(32), created_at: '2026-10-18T00:00:00Z', status: 'queued', stage: 'validation', error: null, config};
const result: Result = {
  summary: {movement_count: 2, arrivals: 1, departures: 1, occupancy_count: 1, estimated_occupancies: 0,
    paired_occupancies: 1, peak_occupancy: 1, contact_gates: 150, remote_gates: 0, assigned_count: 1,
    remote_count: 0, reassignments: 0, baseline_covered: 1, solver_status: 'FEASIBLE', feasible: true,
    optimality_proven: false, independent_verifier_valid: true, conflicts: 0, solver_runtime_sec: .1,
    decision_cost: 0, comparison_count: 0, mae: null, rmse: null},
  predictions: [], turns: [], assignments: [], gates: [],
  manifest: {config, models: {}, warnings: ['Dwell là giả định.'], reference_midnight_utc: '2026-07-01T04:00:00Z', created_at: '', time_basis: 'ML_PREDICTED'},
};
beforeEach(() => {
  localStorage.clear(); vi.clearAllMocks();
  call.mockImplementation(async (path: string) => {
    if (path === '/health') return {status: 'ok'};
    if (path === '/runs') return [];
    if (path === '/datasets') return dataset;
    if (path === `/datasets/${id}`) return dataset;
    if (path === `/runs/${run.id}`) return {...run, status: 'completed', stage: 'done'};
    if (path === `/runs/${run.id}/results`) return result;
    throw Error(`Unexpected request: ${path}`);
  });
});
afterEach(cleanup);

async function upload() {
  fireEvent.change(document.querySelector('input[type=file]')!, {target: {files: [new File(['parquet'], 'schedule.parquet')]}});
  await screen.findByText('Dữ liệu đã sẵn sàng');
}

describe('workspace interactions', () => {
  it('shows empty honest metrics and all five wireframe screens', async () => {
    render(<App/>);
    expect(screen.getAllByText('—').length).toBe(4);
    expect(screen.getByRole('button', {name: /Chạy end-to-end/}).hasAttribute('disabled')).toBe(true);
    fireEvent.click(screen.getByRole('button', {name: /Monte Carlo/}));
    expect(screen.getByText(/Không sử dụng kết quả 500 kịch bản cũ/)).toBeTruthy();
    await screen.findByText('Hệ thống sẵn sàng');
  });
  it('uploads Parquet, selects a date, and changes presets without changing the airport', async () => {
    render(<App/>); await upload();
    expect((screen.getByLabelText('Ngày vận hành') as HTMLSelectElement).value).toBe('2026-07-01');
    fireEvent.change(screen.getByLabelText('Quy mô thử nghiệm'), {target: {value: 'small'}});
    expect((screen.getByLabelText('Số cổng tiếp xúc') as HTMLInputElement).value).toBe('20');
    fireEvent.change(screen.getByLabelText('Số cổng tiếp xúc'), {target: {value: '33'}});
    expect((screen.getByLabelText('Quy mô thử nghiệm') as HTMLSelectElement).value).toBe('custom');
    expect(screen.getByLabelText('Sân bay').hasAttribute('disabled')).toBe(true);
    fireEvent.click(screen.getByLabelText('Bật bãi đỗ từ xa'));
    expect((screen.getByLabelText('Số vị trí bãi xa') as HTMLInputElement).value).toBe('5');
  });
  it('polls the worker and displays its result after navigating during execution', async () => {
    call.mockImplementation(async (path, options) => {
      if (path === '/health') return {};
      if (path === '/datasets') return dataset;
      if (path === '/runs' && options?.method === 'POST') return run;
      if (path === '/runs') return [];
      if (path === `/runs/${run.id}`) return {...run, status: 'completed', stage: 'done'};
      if (path.endsWith('/results')) return result;
      throw Error(path);
    });
    render(<App/>); await upload();
    fireEvent.click(screen.getByRole('button', {name: /Chạy end-to-end/}));
    await screen.findByText('Đang chạy pipeline');
    fireEvent.click(screen.getByRole('button', {name: /Lịch phân cổng/}));
    await screen.findByText('Đã tìm được nghiệm khả thi', {}, {timeout: 3000});
    expect(screen.queryByText('Đang chạy pipeline')).toBeNull();
    expect(screen.getByText('Dwell là giả định.')).toBeTruthy();
  });
  it('does not run a file with validation errors', async () => {
    call.mockImplementation(async path => path === '/datasets' ? {...dataset, can_run: false, invalid_rows: 1,
      errors: [{source_index: 0, row: 2, message: 'Sai giờ đến'}]} : path === '/runs' ? [] : {});
    render(<App/>);
    fireEvent.change(document.querySelector('input[type=file]')!, {target: {files: [new File(['x'], 'bad.parquet')]}});
    await screen.findByText(/Sai giờ đến/);
    expect(screen.getByRole('button', {name: /Chạy end-to-end/}).hasAttribute('disabled')).toBe(true);
  });
  it('applies the proposal profile without resetting operational inputs', async () => {
    call.mockImplementation(async path => {
      if (path === '/health') return {};
      if (path === '/model-profiles') return [{id: 'legacy_native', ready: true}, {id: 'thesis_xgboost', ready: true, label: 'Đề cương'}];
      if (path === '/runs') return [];
      if (path === '/datasets') return dataset;
      throw Error(path);
    });
    render(<App/>); await upload();
    fireEvent.change(screen.getByLabelText('Số cổng tiếp xúc'), {target: {value: '33'}});
    fireEvent.change(screen.getByLabelText('Giới hạn tìm kiếm (giây)'), {target: {value: '45'}});
    const quick = await screen.findByRole('button', {name: /Chọn nhanh · Đề cương/});
    fireEvent.click(quick);
    expect((screen.getByLabelText('Mô hình dự báo') as HTMLSelectElement).value).toBe('thesis_xgboost');
    expect((screen.getByLabelText('Thời gian vào cổng') as HTMLSelectElement).value).toBe('bounded_wait');
    expect((screen.getByLabelText('Số cổng tiếp xúc') as HTMLInputElement).value).toBe('33');
    expect((screen.getByLabelText('Giới hạn tìm kiếm (giây)') as HTMLInputElement).value).toBe('45');
    expect((screen.getByLabelText('Ngày vận hành') as HTMLSelectElement).value).toBe('2026-07-01');
  });
  it('does not offer a quick preset for an unavailable model', async () => {
    call.mockImplementation(async path => {
      if (path === '/health') return {};
      if (path === '/runs') return [];
      if (path === '/model-profiles') return [{id: 'legacy_native', ready: true}, {id: 'thesis_xgboost', ready: false, reason: 'Thiếu mô hình'}];
      throw Error(path);
    });
    render(<App/>);
    await screen.findByText('Thiếu mô hình');
    expect(screen.getByRole('button', {name: /Chọn nhanh · Đề cương/}).hasAttribute('disabled')).toBe(true);
    expect((screen.getByLabelText('Mô hình dự báo') as HTMLSelectElement).value).toBe('legacy_native');
  });
  it('counts classification alerts independently from predicted minutes', async () => {
    const proposal = {...config, model_profile: 'thesis_xgboost' as const};
    const saved = {...run, status: 'completed' as const, stage: 'done', config: proposal};
    const base = {flight_direction: 'ARR' as const, carrier: 'DL', flight_number: '100', origin: 'JFK', destination: 'ATL',
      scheduled_event_local: '2023-01-15T10:00:00', actual_delay_min: null, model_id: 'thesis_arrival_xgboost',
      model_version: 'full_20261022', model_sha256: 'a'.repeat(64), prediction_cutoff_utc: '2023-01-15T08:00:00Z',
      decision_threshold: .2};
    const proposalResult: Result = {...result, manifest: {...result.manifest, config: proposal}, predictions: [
      {...base, flight_id: 'flight-1', predicted_delay_min: 5, probability_delay_15: .3, predicted_delayed: true},
      {...base, flight_id: 'flight-2', flight_number: '101', predicted_delay_min: 10, probability_delay_15: .1, predicted_delayed: false},
    ]};
    localStorage.setItem('aeolus-last-run', saved.id);
    call.mockImplementation(async path => {
      if (path === '/health') return {};
      if (path === '/model-profiles') return [{id: 'legacy_native', ready: true}, {id: 'thesis_xgboost', ready: true}];
      if (path === '/runs') return [saved];
      if (path === `/datasets/${id}`) return dataset;
      if (path === `/runs/${saved.id}/results`) return proposalResult;
      if (path === '/model-comparison') return {scope: 'historical_2023', models: {}};
      throw Error(path);
    });
    render(<App/>);
    fireEvent.click(screen.getByRole('button', {name: /Dự báo độ trễ/}));
    const label = await screen.findByText('Cảnh báo trễ ≥15 phút');
    expect(label.closest('article')?.querySelector('.kpi-value')?.textContent).toBe('1');
    expect(screen.getByText(/Có thể tính TreeSHAP riêng cho từng chuyến/)).toBeTruthy();
    expect(screen.getByText(/Bảng tham chiếu của profile đề cương/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', {name: /DL\s*100/}));
    const detail = screen.getByRole('dialog');
    expect(detail.textContent).toContain('30%');
    expect(detail.textContent).toContain('20%');
  });
});
