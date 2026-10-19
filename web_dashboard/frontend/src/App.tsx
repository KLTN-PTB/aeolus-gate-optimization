import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Activity, AlertTriangle, ArrowDownToLine, ArrowRight, ArrowUpRight, BarChart3,
  CalendarDays, CalendarRange, Check, ChevronRight, Clock3, Database, Dices, FileCheck2,
  GitCompareArrows, History, Info, LayoutDashboard, LoaderCircle, Plane, PlaneLanding,
  PlaneTakeoff, Play, Search, Settings2, ShieldCheck, Upload, X } from 'lucide-react';
import { api } from './api';
import { GatePage } from './GatePage';
import { LabPage } from './LabPage';
import type { OpenPlan } from './experimentTypes';
import { DelayChart, HourlyChart } from './charts';
import { configMatches, defaults, fmt, isBusy, riskLevel, solverNames, stageNames, stages,
  timelineClock, type Config, type Dataset, type Prediction, type Result, type Run, type Turn } from './types';

const pages = [
  {id: 'overview', title: 'Tổng quan', icon: LayoutDashboard, description: 'Một góc nhìn xuyên suốt ngày vận hành.'},
  {id: 'predictions', title: 'Dự báo độ trễ', icon: Activity, description: 'Từ lịch bay đến những quyết định có cơ sở.'},
  {id: 'gates', title: 'Lịch phân cổng', icon: CalendarRange, description: 'Đúng chuyến bay. Đúng cổng. Đúng thời điểm.'},
  {id: 'comparison', title: 'So sánh thuật toán', icon: GitCompareArrows, description: 'Đối chiếu hiệu quả trên cùng một kịch bản.'},
  {id: 'montecarlo', title: 'Monte Carlo', icon: Dices, description: 'Đánh giá độ vững trước những biến động.'},
];
const presetNames = {large: 'Lớn · 150 cổng', medium: 'Vừa · 50 cổng', small: 'Nhỏ · 20 cổng', custom: 'Tùy chỉnh'};
const statusNames = {queued: 'Đang chờ', running: 'Đang xử lý', completed: 'Hoàn tất', failed: 'Thất bại', interrupted: 'Bị gián đoạn'};

function Panel({title, subtitle, action, children, className = ''}: {title: string; subtitle?: string; action?: ReactNode; children: ReactNode; className?: string}) {
  return <section className={`panel ${className}`}><header className="panel-head"><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div>{action}</header>{children}</section>;
}
function Kpi({label, value, unit, note, icon, accent = false}: {label: string; value: ReactNode; unit?: string; note: string; icon: ReactNode; accent?: boolean}) {
  return <article className={`kpi ${accent ? 'accent' : ''}`}><div className="kpi-top"><span>{label}</span>{icon}</div><div className="kpi-value">{value}<small>{unit}</small></div><p>{note}</p></article>;
}
function Alert({children, tone = 'warning'}: {children: ReactNode; tone?: string}) {
  return <div className={`alert ${tone}`} role={tone === 'error' ? 'alert' : 'status'}><AlertTriangle size={17}/><div>{children}</div></div>;
}
function PredictTable({rows, onSelect}: {rows: Prediction[]; onSelect: (p: Prediction) => void}) {
  const [page, setPage] = useState(0);
  useEffect(() => setPage(0), [rows]);
  const visible = rows.slice(page * 20, (page + 1) * 20);
  return <><div className="table-scroll"><table><thead><tr><th>Chuyến bay</th><th>Chặng bay</th><th>Chiều</th><th>Giờ lịch</th><th>Trễ dự báo</th><th>P(trễ ≥15m)</th><th>Thực tế</th><th/></tr></thead><tbody>
    {visible.map(p => <tr key={p.flight_id} onClick={() => onSelect(p)}><td><button className="flight-link" onClick={() => onSelect(p)}>{p.carrier}<strong>{p.flight_number}</strong></button></td><td>{p.origin}<span className="route-arrow">→</span>{p.destination}</td>
      <td><span className={`direction ${p.flight_direction === 'ARR' ? 'arrival' : ''}`}>{p.flight_direction === 'ARR' ? <PlaneLanding size={12}/> : <PlaneTakeoff size={12}/>} {p.flight_direction === 'ARR' ? 'Đến' : 'Đi'}</span></td>
      <td>{p.scheduled_event_local.slice(11, 16)}</td><td><span className={`delay ${riskLevel(p)}`}>{p.predicted_delay_min > 0 ? '+' : ''}{fmt(p.predicted_delay_min, 1)} phút</span></td>
      <td>{p.probability_delay_15 == null ? <span className="muted">Không có</span> : `${fmt(p.probability_delay_15 * 100, 1)}%`}</td>
      <td>{p.actual_delay_min == null ? '—' : `${fmt(p.actual_delay_min, 1)} phút`}</td><td><ChevronRight size={14}/></td></tr>)}
    {!rows.length && <tr><td colSpan={8} className="table-empty">Không có chuyến bay phù hợp.</td></tr>}
  </tbody></table></div><footer className="table-footer"><span>{fmt(rows.length)} lượt bay · Giờ địa phương ATL</span><div><button className="text-button" disabled={page === 0} onClick={() => setPage(page - 1)}>Trước</button><span>{page + 1}/{Math.max(1, Math.ceil(rows.length / 20))}</span><button className="text-button" disabled={(page + 1) * 20 >= rows.length} onClick={() => setPage(page + 1)}>Sau</button></div></footer></>;
}

export default function App() {
  const [page, setPage] = useState('overview');
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [config, setConfig] = useState<Config>({...defaults});
  const [run, setRun] = useState<Run | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [gateView, setGateView] = useState<OpenPlan | null>(null);
  useEffect(() => setGateView(null), [result]);
  const [history, setHistory] = useState<Run[]>([]);
  const [error, setError] = useState('');
  const [uploading, setUploading] = useState(false);
  const [starting, setStarting] = useState(false);
  const [online, setOnline] = useState(false);
  const [search, setSearch] = useState('');
  const [direction, setDirection] = useState('all');
  const [detail, setDetail] = useState<Prediction | Turn | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const loadToken = useRef(0);
  const busy = isBusy(run);
  const stale = !!run && !configMatches(config, run.config);
  const meta = pages.find(p => p.id === page)!;
  const s = result?.summary;

  const update = <K extends keyof Config>(key: K, value: Config[K]) => setConfig(c => ({...c, [key]: value}));
  const refreshHistory = () => api<Run[]>('/runs').then(setHistory);
  async function openRun(item: Run) {
    const token = ++loadToken.current;
    setError(''); setDetail(null); setResult(null); setRun(item); setConfig({...item.config});
    localStorage.setItem('aeolus-last-run', item.id);
    try {
      const [report, output] = await Promise.all([api<Dataset>(`/datasets/${item.config.dataset_id}`),
        item.status === 'completed' ? api<Result>(`/runs/${item.id}/results`) : Promise.resolve(null)]);
      if (token === loadToken.current) {setDataset(report); setResult(output);}
    } catch (e) {if (token === loadToken.current) setError((e as Error).message);}
  }
  useEffect(() => {
    api('/health').then(() => setOnline(true)).catch(() => setError('Chưa kết nối backend. Kiểm tra ứng dụng đang chạy trên localhost:8000.'));
    api<Run[]>('/runs').then(items => {setHistory(items); const saved = items.find(item => item.id === localStorage.getItem('aeolus-last-run')); if (saved) void openRun(saved);}).catch(e => setError(e.message));
  }, []);
  useEffect(() => {
    if (!run || !isBusy(run)) return;
    let active = true;
    const id = run.id;
    const timer = window.setInterval(async () => {
      try {
        const updated = await api<Run>(`/runs/${id}`);
        if (!active) return;
        if (updated.status === 'completed') {
          const output = await api<Result>(`/runs/${id}/results`);
          if (active) {setResult(output); void refreshHistory();}
        } else if (updated.status === 'failed' || updated.status === 'interrupted') {
          setError(updated.error || 'Tác vụ không hoàn tất.'); void refreshHistory();
        }
        if (active) setRun(updated);
      } catch (e) {if (active) setError((e as Error).message);}
    }, 1000);
    return () => {active = false; window.clearInterval(timer);};
  }, [run?.id, run?.status]);
  useEffect(() => {
    const escape = (e: KeyboardEvent) => {if (e.key === 'Escape') setDetail(null);};
    window.addEventListener('keydown', escape); return () => window.removeEventListener('keydown', escape);
  }, []);

  async function upload(files: FileList | File[]) {
    if (busy || uploading || !files.length) return;
    ++loadToken.current;
    setUploading(true); setError(''); setRun(null); setResult(null); setDataset(null); setDetail(null);
    localStorage.removeItem('aeolus-last-run');
    try {
      const form = new FormData(); Array.from(files).forEach(file => form.append('files', file));
      const report = await api<Dataset>('/datasets', {method: 'POST', body: form});
      setDataset(report); setConfig(c => ({...c, dataset_id: report.id, service_date: report.dates[0]?.date || ''}));
    } catch (e) {setError((e as Error).message);}
    finally {setUploading(false); if (fileInput.current) fileInput.current.value = '';}
  }
  async function start() {
    setError(''); setStarting(true); setResult(null); setDetail(null);
    try {
      const item = await api<Run>('/runs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(config)});
      setRun(item); localStorage.setItem('aeolus-last-run', item.id); void refreshHistory();
    } catch (e) {setError((e as Error).message);}
    finally {setStarting(false);}
  }
  const filtered = (result?.predictions || []).filter(p => (direction === 'all' || p.flight_direction === direction)
    && `${p.carrier}${p.flight_number} ${p.origin} ${p.destination}`.toLowerCase().includes(search.toLowerCase()));
  const exportLink = (kind: string) => `/api/runs/${run?.id}/exports/${kind}`;
  const canRun = !!dataset?.can_run && !!config.service_date && !busy && !uploading && !starting;
  const step = run?.status === 'completed' ? stages.length - 1 : Math.max(0, stages.indexOf(run?.stage || 'validation'));

  return <div className="app-shell">
    <aside className="sidebar"><a className="brand" href="#" onClick={e => {e.preventDefault(); setPage('overview');}}><span className="brand-mark"><Plane size={23}/></span><div>aeolus<span>FLIGHT OPERATIONS</span></div></a>
      <div className="workspace-label">KHÔNG GIAN VẬN HÀNH</div><nav aria-label="Điều hướng chính">{pages.map((p, i) => <button key={p.id} className={page === p.id ? 'active' : ''} onClick={() => {setPage(p.id); setSearch('');}}><p.icon size={18}/><span>{p.title}</span><small>0{i + 1}</small></button>)}</nav>
      <div className="sidebar-note"><div className="note-icon"><ShieldCheck size={19}/></div><strong>Dữ liệu ở lại trên máy bạn</strong><p>Dự báo và tối ưu cục bộ. Không tải dữ liệu lên dịch vụ bên ngoài.</p><span><i/> LOCAL WORKSPACE</span></div>
      <a className="legacy-link" href="http://127.0.0.1:8501" target="_blank" rel="noreferrer"><History size={15}/>Historical Replay<ArrowUpRight size={14}/></a>
      <div className="sidebar-bottom"><span className="avatar">A</span><div>Đồ án Aeolus<small>Predict · Optimize · Evaluate</small></div><span className="version">v1</span></div>
    </aside>
    <main className="main"><header className="topbar"><div className="breadcrumb">Không gian vận hành<ChevronRight size={13}/><strong>{meta.title}</strong></div><div className="connection"><i className={online ? 'online' : ''}/>{online ? 'Hệ thống sẵn sàng' : 'Đang kết nối'}</div></header>
      <div className="content"><div className="page-heading"><div><div className="eyebrow">FLIGHT DELAY & GATE REASSIGNMENT</div><h1>{meta.title}</h1><p>{meta.description}</p></div>
        {result && run?.status === 'completed' && <a className="button secondary" href={exportLink('bundle')}><ArrowDownToLine size={16}/>Xuất kết quả</a>}</div>
        <div className="context-bar"><span><Plane size={15}/><b>ATL</b> Atlanta</span><span><CalendarDays size={15}/>{run?.config.service_date || config.service_date || 'Chưa chọn ngày'}</span><span><CalendarRange size={15}/>{run?.config.contact_gates || config.contact_gates} cổng tiếp xúc</span><span className="context-model">{run ? solverNames[run.config.solver] : 'Schedule-only inference'}</span><span className="context-tag">{run ? `RUN ${run.id.slice(0, 8).toUpperCase()}` : 'CHƯA CÓ LẦN CHẠY'}</span></div>
        {error && <Alert tone="error"><div className="alert-flex"><span>{error}</span><button aria-label="Đóng thông báo" onClick={() => setError('')}><X size={15}/></button></div></Alert>}
        {stale && <Alert>Cấu hình đã thay đổi. Kết quả đang hiển thị thuộc lần chạy trước; nhấn “Chạy end-to-end” để tạo kết quả mới.</Alert>}
        {busy && <div className="run-progress" aria-live="polite"><LoaderCircle className="spin" size={19}/><div><strong>{stageNames[run!.stage] || run!.stage}</strong><p>Tiến trình tiếp tục chạy khi bạn chuyển giữa các màn hình.</p></div><span>Bước {Math.min(step + 1, 7)}/7</span><div className="progress-track"><i style={{width: `${Math.max(4, step / 7 * 100)}%`}}/></div></div>}

        {page === 'overview' && <>
          <div className="kpi-grid"><Kpi label="Lượt bay trong ngày" value={fmt(s?.movement_count)} note={s ? `${fmt(s.arrivals)} đến · ${fmt(s.departures)} đi` : 'Chọn dữ liệu để bắt đầu'} icon={<Plane size={18}/>} accent/>
            <Kpi label="Lượt chiếm dụng cổng" value={fmt(s?.occupancy_count)} note={s ? `${fmt(s.paired_occupancies)} cặp · ${fmt(s.estimated_occupancies)} lượt ước lượng` : 'Cặp đến–đi được tính một lần'} icon={<CalendarRange size={18}/>}/>
            <Kpi label="Xung đột sau tối ưu" value={s?.feasible ? fmt(s.conflicts) : '—'} note={s?.feasible ? 'Đã kiểm tra ràng buộc độc lập' : 'Chưa có nghiệm được xác minh'} icon={<ShieldCheck size={18}/>}/>
            <Kpi label="Đỉnh nhu cầu cổng" value={fmt(s?.peak_occupancy)} unit="vị trí" note="Bao gồm buffer giải phóng cổng" icon={<BarChart3 size={18}/>}/></div>
          <div className="workspace-grid"><Panel title="Bắt đầu một ngày vận hành" subtitle="RAW PARQUET → ML INFERENCE → GATE OPTIMIZATION" action={<span className="chip">End-to-end</span>}>
            <div className={`upload-zone ${uploading ? 'loading' : ''}`} onDragOver={e => e.preventDefault()} onDrop={e => {e.preventDefault(); void upload(e.dataTransfer.files);}}>
              <input ref={fileInput} id="raw-upload" type="file" accept=".parquet" multiple disabled={busy || uploading} onChange={e => {if (e.target.files) void upload(e.target.files);}}/>
              <span className="upload-icon">{uploading ? <LoaderCircle size={25} className="spin"/> : <Upload size={25}/>}</span>
              <h3>{uploading ? 'Đang chuẩn hóa lịch bay…' : dataset ? 'Đã nhận dữ liệu lịch bay' : 'Đưa lịch bay của bạn vào đây'}</h3>
              <p>{dataset ? dataset.filenames.join(' + ') : 'Kéo thả raw Parquet hoặc chọn file từ máy tính'}</p>
              <button className="button secondary" disabled={busy || uploading} onClick={() => fileInput.current?.click()}>{dataset ? 'Chọn dữ liệu khác' : 'Chọn file Parquet'}<ArrowUpRight size={14}/></button>
              <small>1 file tổng hợp hoặc 2 file đến/đi · Tối đa 500 MB</small>
            </div>
            {dataset && <div className="validation"><div className="validation-heading"><FileCheck2 size={18}/><strong>{dataset.can_run ? 'Dữ liệu đã sẵn sàng' : 'Cần kiểm tra lại dữ liệu'}</strong><span className={`badge ${dataset.can_run ? 'success' : 'danger'}`}>{dataset.can_run ? 'Hợp lệ' : `${dataset.invalid_rows} lỗi`}</span></div>
              <div className="data-stats"><span><b>{fmt(dataset.input_rows)}</b>Tổng dòng</span><span><b>{fmt(dataset.valid_rows)}</b>Lượt ATL hợp lệ</span><span><b>{fmt(dataset.non_atl_rows)}</b>Ngoài ATL</span></div>
              {!!dataset.errors.length && <div className="validation-errors">{dataset.errors.slice(0, 8).map((e, i) => <p key={i}>File {e.source_index + 1}, dòng {e.row}: {e.message}</p>)}{dataset.invalid_rows > 8 && <p>Và {dataset.invalid_rows - 8} dòng lỗi khác. Sửa file trước khi chạy.</p>}</div>}
              <details><summary>Xem các cột và bản ghi chuẩn hóa</summary><div className="table-scroll"><table><thead><tr><th>Chuyến</th><th>Chặng</th><th>Ngày vận hành</th><th>Giờ tại ATL</th></tr></thead><tbody>{dataset.preview.map((r, i) => <tr key={i}><td>{String(r.OP_CARRIER)}{String(r.OP_CARRIER_FL_NUM)}</td><td>{String(r.ORIGIN)} → {String(r.DEST)}</td><td>{String(r.service_date)}</td><td>{String(r.scheduled_event_local).slice(11, 16)}</td></tr>)}</tbody></table></div></details>
            </div>}
            <div className="upload-help"><Info size={15}/><span>Chỉ dùng lịch bay để dự báo. Các cột độ trễ thực tế được tách riêng để đối chiếu.</span></div>
            <a className="sample-link" href="/api/example.parquet" download><ArrowDownToLine size={13}/>Tải file mẫu minh họa (không phải dữ liệu thực tế)</a>
          </Panel>
          <Panel title="Cấu hình vận hành" subtitle="Thiết lập năng lực cho lần thử nghiệm" action={<Settings2 size={18}/>}>
            <fieldset className="config-form" disabled={busy || uploading || starting}>
              <label>Sân bay<select aria-label="Sân bay" value="ATL" disabled><option>ATL — Hartsfield–Jackson Atlanta</option></select></label>
              <label>Ngày vận hành<select aria-label="Ngày vận hành" value={config.service_date} onChange={e => update('service_date', e.target.value)} disabled={!dataset?.dates.length}><option value="">Chọn ngày từ file đã tải</option>{dataset?.dates.map(d => <option key={d.date} value={d.date}>{d.date} · {fmt(d.total)} lượt bay</option>)}</select></label>
              <div className="form-row"><label>Quy mô thử nghiệm<select aria-label="Quy mô thử nghiệm" value={config.preset} onChange={e => {const preset = e.target.value as Config['preset']; setConfig(c => ({...c, preset, contact_gates: preset === 'custom' ? c.contact_gates : {large: 150, medium: 50, small: 20}[preset]}));}}>{Object.entries(presetNames).map(([key, name]) => <option key={key} value={key}>{name}</option>)}</select></label>
                <label>Số cổng tiếp xúc<input aria-label="Số cổng tiếp xúc" type="number" min="1" max="300" value={config.contact_gates} onChange={e => setConfig(c => ({...c, preset: 'custom', contact_gates: Number(e.target.value)}))}/></label></div>
              <label className="remote-toggle"><span>Bãi đỗ từ xa<small>Năng lực hữu hạn, không tự thêm bãi tràn</small></span><input aria-label="Bật bãi đỗ từ xa" type="checkbox" checked={config.remote_gates > 0} onChange={e => update('remote_gates', e.target.checked ? 5 : 0)}/></label>
              {config.remote_gates > 0 && <label>Số vị trí bãi xa<input aria-label="Số vị trí bãi xa" type="number" min="1" max="100" value={config.remote_gates} onChange={e => update('remote_gates', Number(e.target.value))}/></label>}
              <label>Phương pháp tối ưu<select aria-label="Phương pháp tối ưu" value={config.solver} onChange={e => update('solver', e.target.value as Config['solver'])}>{Object.entries(solverNames).map(([key, name]) => <option key={key} value={key}>{name}</option>)}</select></label>
              {config.solver === 'cpsat' && <label className="check fallback-check"><input type="checkbox" checked={config.greedy_fallback} onChange={e => update('greedy_fallback', e.target.checked)}/>Dùng Greedy nếu CP-SAT chưa có nghiệm (ghi rõ nguồn kết quả)</label>}
              <details className="advanced"><summary>Thông số nâng cao</summary><div className="form-row"><label>Quay đầu tối thiểu (phút)<input type="number" min="15" max="180" value={config.min_turnaround_min} onChange={e => update('min_turnaround_min', Number(e.target.value))}/></label><label>Dwell chuyến lẻ (phút)<input type="number" min="15" max="720" value={config.default_dwell_min} onChange={e => update('default_dwell_min', Number(e.target.value))}/></label></div><div className="form-row"><label>Buffer (phút)<input type="number" min="0" max="120" value={config.buffer_min} onChange={e => update('buffer_min', Number(e.target.value))}/></label><label>Giới hạn tìm kiếm (giây)<input type="number" min="1" max="120" value={config.time_limit_sec} onChange={e => update('time_limit_sec', Number(e.target.value))}/></label></div></details>
              <div className="assumption-note"><Info size={13}/><span>Quy mô là giả định mô phỏng, không phải số cổng thực tế của ATL.</span></div>
            </fieldset><button className="button primary run-button" disabled={!canRun} onClick={() => void start()}>{busy || starting ? <LoaderCircle className="spin" size={17}/> : <Play size={16}/>} {busy ? 'Đang chạy pipeline' : 'Chạy end-to-end'}<ArrowRight size={16}/></button>
          </Panel></div>
          <Panel title="Quy trình hệ thống" subtitle="Từ dữ liệu lịch bay đến phương án phân cổng được xác minh" className="pipeline-panel"><div className="pipeline-steps">{[{icon: Database, title: 'Raw Parquet', note: 'Chuẩn hóa & kiểm tra'}, {icon: Activity, title: 'Dự báo ML', note: 'Arrival + Departure'}, {icon: CalendarRange, title: 'Khoảng chiếm dụng', note: 'Ghép cặp & giả định'}, {icon: GitCompareArrows, title: 'Phân bổ cổng', note: 'Greedy / CP-SAT / Hybrid'}, {icon: ShieldCheck, title: 'Kiểm chứng', note: 'Ràng buộc độc lập'}].map((item, i) => <div className="pipeline-step" key={item.title}><span><item.icon size={20}/></span><div><strong><small>0{i + 1}</small>{item.title}</strong><p>{item.note}</p></div>{i < 4 && <ChevronRight className="step-arrow" size={16}/>}</div>)}</div></Panel>
          <div className="chart-grid"><Panel title="Lưu lượng theo giờ" subtitle="Lượt bay theo lịch tại ATL" action={<div className="legend"><span><i className="blue"/>Đến</span><span><i className="orange"/>Đi</span></div>}><HourlyChart result={result}/></Panel>
            <Panel title="Phân bố độ trễ dự báo" subtitle="Số lượt bay theo nhóm phút trễ"><DelayChart result={result}/></Panel></div>
          <Panel title="Lịch sử chạy" subtitle="Các lần chạy được lưu trên máy này" action={<History size={17}/>}><div className="table-scroll"><table><thead><tr><th>Mã lần chạy</th><th>Ngày vận hành</th><th>Năng lực</th><th>Phương pháp</th><th>Trạng thái</th><th/></tr></thead><tbody>{history.slice(0, 10).map(item => <tr key={item.id}><td><button className="flight-link" disabled={busy || uploading} onClick={() => void openRun(item)}>#{item.id.slice(0, 8)}</button></td><td>{item.config.service_date}</td><td>{item.config.contact_gates} cổng · {item.config.remote_gates} bãi xa</td><td>{solverNames[item.config.solver]}</td><td><span className={`badge ${item.status === 'completed' ? 'success' : item.status === 'failed' ? 'danger' : ''}`}>{statusNames[item.status]}</span></td><td><button className="text-button" disabled={busy || uploading} onClick={() => void openRun(item)}>Mở<ArrowUpRight size={13}/></button></td></tr>)}{!history.length && <tr><td className="table-empty" colSpan={6}>Chưa có lần chạy. Bắt đầu bằng một file raw Parquet.</td></tr>}</tbody></table></div></Panel>
        </>}

        {page === 'predictions' && <>
          <div className="kpi-grid"><Kpi label="Lượt bay đã dự báo" value={fmt(s?.movement_count)} note="Dự báo trực tiếp từ checkpoint đã xác minh" icon={<Activity size={18}/>} accent/>
            <Kpi label="MAE đối chiếu" value={fmt(s?.mae, 2)} unit="phút" note={s?.comparison_count ? `${fmt(s.comparison_count)} lượt có nhãn thực tế` : 'Cần nhãn thực tế hợp lệ để tính'} icon={<BarChart3 size={18}/>}/>
            <Kpi label="RMSE đối chiếu" value={fmt(s?.rmse, 2)} unit="phút" note="Không phải kết quả kiểm định mô hình mới" icon={<Activity size={18}/>}/>
            <Kpi label="Dự báo trễ ≥15 phút" value={result ? fmt(result.predictions.filter(p => p.predicted_delay_min >= 15).length) : '—'} note="Theo giá trị trễ dự báo, không phải xác suất" icon={<Clock3 size={18}/>}/></div>
          {!result ? <EmptyState title="Chưa có dự báo cho ngày vận hành" text="Tải raw Parquet và chạy end-to-end từ màn hình Tổng quan." onBack={() => setPage('overview')}/> : <>
            <div className="model-cards">{Object.entries(result.manifest.models).map(([key, model]) => <div className="model-card" key={key}><span className="model-icon">{key === 'arrival' ? <PlaneLanding size={20}/> : <PlaneTakeoff size={20}/>}</span><div><small>CORE {key.toUpperCase()}</small><strong>{model.model_id}</strong><span>{model.status} · {model.version}</span></div><ShieldCheck size={18}/></div>)}</div>
            <Panel title="Dự báo từng chuyến bay" subtitle="Thời gian thực tế chỉ dùng để đối chiếu, không làm đầu vào dự báo" action={<a className="text-button" href={exportLink('predictions.csv')}><ArrowDownToLine size={14}/>Tải CSV</a>}>
              <div className="filters"><label className="search-box"><Search size={16}/><input aria-label="Tìm chuyến bay" value={search} onChange={e => setSearch(e.target.value)} placeholder="Tìm số hiệu, hãng hoặc chặng bay…"/></label><select aria-label="Chiều bay" value={direction} onChange={e => setDirection(e.target.value)}><option value="all">Tất cả chiều bay</option><option value="ARR">Chuyến đến</option><option value="DEP">Chuyến đi</option></select><span className="chip"><ShieldCheck size={12}/>Schedule-only</span></div>
              <PredictTable rows={filtered} onSelect={setDetail}/></Panel>
            <div className="chart-grid"><Panel title="Phân bố độ trễ dự báo" subtitle="Signed delay · giữ nguyên dự báo đến sớm"><DelayChart result={result}/></Panel><Panel title="Khả năng giải thích & giới hạn" subtitle="Thông tin đúng theo mô hình đang sử dụng"><div className="explanation"><ShieldCheck size={28}/><h3>Dự báo có nguồn gốc rõ ràng</h3><p>Mã mô hình, phiên bản, mã băm và thời điểm cutoff được lưu theo từng chuyến. Mở chi tiết chuyến để kiểm tra.</p><p>Chưa có SHAP cho file mới. Không dùng lại SHAP hoặc ROC-AUC của một thí nghiệm khác để đại diện dữ liệu này.</p><a className="text-button" href={exportLink('manifest')}>Tải manifest kiểm chứng<ArrowUpRight size={13}/></a></div></Panel></div>
          </>}
        </>}

        {page === 'gates' && <GatePage key={run?.id} runId={run?.id} result={result} view={gateView} onView={setGateView}/>}
        {['comparison', 'montecarlo'].includes(page) && <LabPage key={`${run?.id}-${page}`} kind={page === 'comparison' ? 'benchmark' : 'montecarlo'} runId={run?.id} result={result} onOpen={p => {setGateView(p); setPage('gates');}}/>}

        <footer className="page-footer"><span><Plane size={13}/>AEOLUS · Predict then Optimize</span><span>ATL · America/New_York · Local research workspace</span></footer>
      </div>
    </main>
    {detail && <div className="drawer-overlay" onClick={() => setDetail(null)}><aside className="detail-drawer" role="dialog" aria-modal="true" aria-label="Chi tiết chuyến bay" onClick={e => e.stopPropagation()}><header><span>CHI TIẾT VẬN HÀNH</span><button autoFocus aria-label="Đóng chi tiết" onClick={() => setDetail(null)}><X size={20}/></button></header>
      {'flight_direction' in detail ? <><h2>{detail.carrier}{detail.flight_number}</h2><div className="detail-route">{detail.origin}<ArrowRight size={20}/>{detail.destination}</div><dl><dt>Chiều bay</dt><dd>{detail.flight_direction}</dd><dt>Giờ theo lịch tại ATL</dt><dd>{detail.scheduled_event_local}</dd><dt>Trễ dự báo</dt><dd>{fmt(detail.predicted_delay_min, 2)} phút</dd><dt>P(trễ ≥15 phút)</dt><dd>{detail.probability_delay_15 == null ? 'Mô hình không cung cấp' : `${fmt(detail.probability_delay_15 * 100, 2)}%`}</dd><dt>Trễ thực tế (chỉ đối chiếu)</dt><dd>{fmt(detail.actual_delay_min, 2)} phút</dd><dt>Mô hình</dt><dd>{detail.model_id}</dd><dt>Cutoff lịch bay (UTC)</dt><dd>{detail.prediction_cutoff_utc}</dd><dt>SHA-256 checkpoint</dt><dd className="mono">{detail.model_sha256}</dd></dl></> : <><h2>{detail.carrier}{detail.flight_number}</h2><span className="badge">{detail.is_estimated ? 'Dwell giả định' : 'Ghép cùng số đuôi từ lịch'}</span><dl><dt>Cổng phân bổ</dt><dd>{result?.assignments.find(a => a.flight_id === detail.turn_id)?.gate_id || 'Chưa có'}</dd><dt>Cổng tham chiếu mô phỏng</dt><dd>{detail.nominal_gate_id || 'Không có'}</dd><dt>Bắt đầu chiếm dụng</dt><dd>{timelineClock(detail.simulated_arrival_min, result!.manifest.reference_midnight_utc)}</dd><dt>Rời cổng</dt><dd>{timelineClock(detail.simulated_departure_min, result!.manifest.reference_midnight_utc)}</dd><dt>Giải phóng sau buffer</dt><dd>{timelineClock(detail.gate_release_min, result!.manifest.reference_midnight_utc)}</dd><dt>Loại lượt</dt><dd>{detail.pair_type}</dd><dt>Mã lượt đến / đi</dt><dd className="mono">{detail.arrival_leg_id || 'Không có'}<br/>{detail.departure_leg_id || 'Không có'}</dd></dl><p className="assumption-note">Không tự chuyển tàu từ bãi xa vào cổng.</p></>}
    </aside></div>}
  </div>;
}

function EmptyState({title, text, onBack}: {title: string; text: string; onBack: () => void}) {
  return <div className="empty-state"><span><CalendarRange size={32}/></span><h2>{title}</h2><p>{text}</p><button className="button primary" onClick={onBack}><Upload size={15}/>Tải raw Parquet<ArrowRight size={15}/></button></div>;
}
