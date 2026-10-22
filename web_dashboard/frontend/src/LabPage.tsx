import { useEffect, useRef, useState } from 'react';
import { ArrowDownToLine, Play, Square, RotateCcw, LoaderCircle, CalendarRange } from 'lucide-react';
import { api } from './api';
import { fmt, type Result } from './types';
import { algorithmNames, experimentStatus, running, profileName, timedOut, costEligible, sourceName, type Case, type Experiment, type ExperimentResult, type OpenPlan, type Plans } from './experimentTypes';

const ci = (v: number[] | null, percent = false) => v ? v.map(x => fmt(x * (percent ? 100 : 1), 2)).join(' – ') + (percent ? '%' : '') : '—';
const timingNames: Record<string,string> = {initialization_sec: 'Khởi tạo', model_build_sec: 'Dựng mô hình', search_sec: 'Giải thuật toán (gồm callback)', validation_sec: 'Kiểm chứng nghiệm', persistence_sec: 'Lưu checkpoint'};
const modeName = (s: string) => ({benchmark: 'Benchmark', fixed: 'Cố định', recourse: 'Phân cổng lại'}[s] || s);
function Plot({title, values, suffix = ''}: {title: string; values: {label: string; value: number | null; color?: string}[]; suffix?: string}) {
  const max = Math.max(1, ...values.map(v => v.value || 0));
  return <section className="panel lab-plot"><h3>{title}</h3>{values.length ? values.map((v, i) => <div className="metric-bar" key={i}><span>{v.label}</span><div><i style={{width: `${Math.max(0, (v.value || 0) / max * 100)}%`, background: v.color}}/></div><b>{fmt(v.value, 2)}{suffix}</b></div>) : <p>Chưa có mẫu đã đánh giá.</p>}</section>;
}

export function LabPage({kind, runId, result, onOpen}: {kind: 'benchmark' | 'montecarlo'; runId: string | undefined; result: Result | null; onOpen: (p: OpenPlan) => void}) {
  const [history, setHistory] = useState<Experiment[]>([]);
  const [selected, setSelected] = useState<Experiment | null>(null);
  const [data, setData] = useState<ExperimentResult | null>(null);
  const [plans, setPlans] = useState<Plans | null>(null);
  const [chosen, setChosen] = useState<string[]>([]);
  const [mode, setMode] = useState('quick');
  const [profile, setProfile] = useState('optimized');
  const [algorithms, setAlgorithms] = useState(Object.keys(algorithmNames));
  const [seed, setSeed] = useState(202601);
  const [budget, setBudget] = useState(kind === 'benchmark' ? 5 : 2);
  const [scenarios, setScenarios] = useState(20);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [casePage, setCasePage] = useState(0);
  const [filter, setFilter] = useState('all');
  const [algorithmFilter, setAlgorithmFilter] = useState('all');
  const [worstFirst, setWorstFirst] = useState(false);
  const [detail, setDetailState] = useState<Case | null>(null);
  const detailToken = useRef(0);
  const mounted = useRef(true);
  const loadToken = useRef(0);
  const inflight = useRef(false);
  const busy = running(selected);
  const mc = kind === 'montecarlo';
  const storageKey = `aeolus-experiment-${runId}-${kind}`;

  async function refreshPlans() {
    if (!runId) return;
    const p = await api<Plans>(`/runs/${runId}/plans`);
    if (!mounted.current) return;
    setPlans(p);
    setChosen(old => {
      if (old.length) return old.filter(id => p.plans.some(plan => plan.id === id));
      return Object.keys(algorithmNames).map(algorithm => p.plans.find(plan => plan.algorithm === algorithm && plan.id !== 'pipeline' && plan.seed === 202601)
        || p.plans.find(plan => plan.algorithm === algorithm)).filter(Boolean).map(plan => plan!.id);
    });
  }
  async function openExperiment(e: Experiment) {
    const token = ++loadToken.current;
    setSelected(e); setData(null); setCasePage(0); setError('');
    localStorage.setItem(storageKey, e.id);
    const output = await api<ExperimentResult>(`/experiments/${e.id}/results`);
    if (mounted.current && token === loadToken.current) setData(output);
  }
  useEffect(() => {
    mounted.current = true;
    if (!runId || !result) return;
    let active = true;
    Promise.all([api<Experiment[]>(`/runs/${runId}/experiments`), refreshPlans()]).then(([all]) => {
      if (!active) return;
      const list = all.filter(e => e.config.kind === kind); setHistory(list);
      const saved = list.find(e => e.id === localStorage.getItem(storageKey)) || list[0];
      if (saved) void openExperiment(saved).catch(e => setError(e.message));
    }).catch(e => {if (active) setError(e.message);});
    return () => {active = false; mounted.current = false;};
  }, [runId, kind, !!result]);
  useEffect(() => {
    if (!selected || !busy) return;
    let active = true;
    const timer = window.setInterval(async () => {
      if (inflight.current) return;
      inflight.current = true;
      try {
        const [e, output] = await Promise.all([api<Experiment>(`/experiments/${selected.id}`), api<ExperimentResult>(`/experiments/${selected.id}/results`)]);
        if (!active) return;
        setData(output); setSelected(e);
        if (!running(e)) {
          setHistory(old => [e, ...old.filter(x => x.id !== e.id)]);
          void refreshPlans();
        }
      } catch (e) {if (active) setError((e as Error).message);}
      finally {inflight.current = false;}
    }, 1500);
    return () => {active = false; window.clearInterval(timer);};
  }, [selected?.id, busy]);

  if (!result || !runId) return <div className="empty-state"><CalendarRange size={32}/><h2>Chưa có dữ liệu thí nghiệm</h2><p>Chạy end-to-end từ Tổng quan trước. Không sử dụng kết quả 500 kịch bản cũ để đại diện file mới.</p></div>;
  const total = mc ? scenarios * chosen.length * 2 : algorithms.length * (mode === 'research' ? 5 : 1);
  async function start() {
    setSubmitting(true); setError('');
    try {
      const e = await api<Experiment>(`/runs/${runId}/experiments`, {method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({kind, mode, solver_profile: profile, algorithms, seed, scenarios, time_limit_sec: budget, plan_ids: mc ? chosen : []})});
      setHistory(old => [e, ...old]); await openExperiment(e);
    } catch (e) {setError((e as Error).message);} finally {setSubmitting(false);}
  }
  async function action(a: 'resume' | 'cancel') {
    try {setError(''); const e = await api<Experiment>(`/experiments/${selected!.id}/${a}`, {method: 'POST'}); setSelected(e);}
    catch (e) {setError((e as Error).message);}
  }
  async function openCase(c: Case) {
    try {
      const output = await api<Result>(`/experiments/${selected!.id}/plans/${c.case_id}`);
      onOpen({result: output, label: `${algorithmNames[c.algorithm]} · ${modeName(c.mode)} · ${c.scenario == null ? `seed ${c.seed}` : `kịch bản ${c.scenario+1}`}`, experimentId: selected!.id, caseId: c.case_id});
    } catch (e) {setError((e as Error).message);}
  }
  function setDetail(c: Case | null) {
    const token = ++detailToken.current;
    setDetailState(c);
    if (c && selected) api<Case>(`/experiments/${selected.id}/cases/${c.case_id}`)
      .then(complete => {if (mounted.current && token === detailToken.current) setDetailState(complete);})
      .catch(e => {if (mounted.current) setError(e.message);});
  }
  const cases = (data?.cases || []).filter(c => (filter === 'all' || (filter === 'issues' ? !c.feasible || c.budget_compliant === false || c.solution_source === 'GREEDY_INITIALIZER' : c.mode === filter)) && (algorithmFilter === 'all' || c.algorithm === algorithmFilter));
  if (worstFirst) cases.sort((a, b) => Number(a.feasible)-Number(b.feasible) || (b.conflicts || 0)-(a.conflicts || 0) || (b.risk_cost ?? b.decision_cost ?? 0)-(a.risk_cost ?? a.decision_cost ?? 0));
  const groups = data?.groups || [];
  const terminal = selected && !busy;
  const firstCost = Math.max(1, ...cases.map(c => c.risk_cost ?? c.decision_cost ?? 0));
  const fixedGroups = groups.filter(g => g.mode === 'fixed');
  const recourseGroups = groups.filter(g => g.mode === 'recourse');
  const best = !mc ? groups.filter(g => g.feasible_count && g.median != null).sort((a,b) => a.median!-b.median!)[0] : null;
  const estimatedRemaining = data?.cases.length ? data.cases.reduce((n,c) => n+c.runtime_sec,0)/data.cases.length * Math.max(0,(selected?.total || 0)-(selected?.completed || 0)) : null;
  const gateRisk = fixedGroups.flatMap(g => {
    const eligible=(data?.cases || []).filter(c => c.mode==='fixed' && c.source_plan_id===g.source_plan_id && c.conflicts!=null);
    const counts: Record<string,number>={};
    eligible.forEach(c => Object.keys(c.gate_conflicts || {}).forEach(gate => {counts[gate]=(counts[gate] || 0)+1;}));
    return Object.entries(counts).map(([gate,n]) => ({label: `${algorithmNames[g.algorithm]} · ${gate} (${n}/${eligible.length})`, value: n/eligible.length*100}));
  });
  return <div className="lab-page">
    {error && <div className="alert error" role="alert">{error}</div>}
    <section className="panel"><header className="panel-head"><div><h2>{mc ? 'Thiết kế thí nghiệm Monte Carlo' : 'Benchmark trên cùng snapshot'}</h2><p>#{runId.slice(0, 8)} · {result.manifest.config.service_date} · {fmt(result.summary.occupancy_count)} lượt chiếm dụng · {result.summary.contact_gates} cổng + {result.summary.remote_gates} bãi xa</p></div><span className="chip">{plans?.snapshot_hash?.slice(0, 12) || 'Snapshot'}</span></header>
      {plans && !plans.ready && <div className="alert warning">{plans.reason}</div>}
      <fieldset className="lab-config" disabled={busy || submitting}>
        <label>Chế độ<select aria-label="Chế độ thí nghiệm" value={mode} onChange={e => {setMode(e.target.value); setScenarios(e.target.value === 'research' ? 500 : 20); setBudget(mc ? (e.target.value === 'research' ? 5 : 2) : (e.target.value === 'research' ? 30 : 5));}}><option value="quick">Chạy nhanh</option><option value="research">Nghiên cứu</option></select></label>
        <label>Cấu hình solver<select aria-label="Cấu hình solver" value={profile} onChange={e => setProfile(e.target.value)}><option value="optimized">Tối ưu · warm-start đầy đủ</option><option value="baseline">Baseline · CP-SAT thuần</option></select></label>
        <label>Seed<input aria-label="Seed thí nghiệm" type="number" min="0" max="2147483640" value={seed} onChange={e => setSeed(Number(e.target.value))}/></label>
        <label>Ngân sách mỗi lượt (giây)<input aria-label="Ngân sách thí nghiệm" type="number" min="1" max="120" value={budget} onChange={e => setBudget(Number(e.target.value))}/></label>
        {mc && <label>Số kịch bản<input aria-label="Số kịch bản Monte Carlo" type="number" min="10" max="1000" value={scenarios} onChange={e => setScenarios(Number(e.target.value))}/></label>}
        {!mc && <div className="algorithm-options">{Object.entries(algorithmNames).map(([key, name]) => <label className="check" key={key}><input type="checkbox" checked={algorithms.includes(key)} onChange={e => setAlgorithms(old => e.target.checked ? [...old, key] : old.filter(a => a !== key))}/>{name}</label>)}</div>}
        {mc && <div className="plan-options">{Object.entries(algorithmNames).map(([alg, name]) => <label key={alg}>{name} · lịch ban đầu<select aria-label={`Lịch ${name}`} value={chosen.find(id => plans?.plans.find(p => p.id === id)?.algorithm === alg) || ''} onChange={e => setChosen(old => [...old.filter(id => plans?.plans.find(p => p.id === id)?.algorithm !== alg), ...(e.target.value ? [e.target.value] : [])])}><option value="">Không đánh giá{!plans?.plans.some(p => p.algorithm === alg) ? ' · chưa có lịch hợp lệ' : ''}</option>{plans?.plans.filter(p => p.algorithm === alg).map(p => <option key={p.id} value={p.id}>{p.label}</option>)}</select></label>)}</div>}
      </fieldset>
      <div className="lab-actions"><button className="button primary" disabled={!plans?.ready || busy || submitting || (mc ? !chosen.length || !(plans.has_uncertainty ?? plans.has_arrivals) : !algorithms.length)} onClick={() => void start()}>{submitting ? <LoaderCircle className="spin" size={16}/> : <Play size={16}/>}Chạy {mc ? 'Monte Carlo' : 'benchmark'}</button><span>{fmt(total)} lượt đánh giá · {mode === 'research' && !mc ? '5 seed · ' : ''}{profileName(profile)} · 1 CP worker · bãi xa hữu hạn</span></div>
      <p className="footnote">{mc ? (result?.manifest.config.model_profile==='thesis_xgboost' ? 'Lấy mẫu độc lập sai số đến và đi từ OOF theo thời gian. Các thuật toán dùng chung kịch bản; lịch cố định giữ cả cổng và số phút chờ. Phân cổng lại dùng thông tin toàn kịch bản hồi cứu.' : 'Trễ đến độc lập Student-t, giữ dự báo điểm chuyến đi. Đánh giá lịch cố định và phân cổng lại hồi cứu bằng thuật toán tương ứng. Nghiên cứu 500 kịch bản có thể mất nhiều giờ.') : 'Cùng đầu vào, trọng số và ngân sách. CP-SAT tắt fallback; SA tính cả tạo nghiệm đầu Greedy; Hybrid gồm cả hai giai đoạn.'}</p>
    </section>
    <section className="panel"><header className="panel-head"><h2>Lịch sử thí nghiệm</h2><select aria-label="Chọn thí nghiệm" value={selected?.id || ''} onChange={e => {const item = history.find(x => x.id === e.target.value); if (item) void openExperiment(item).catch(x => setError(x.message));}}><option value="">Chưa chọn</option>{history.map(e => <option key={e.id} value={e.id}>#{e.id.slice(0, 8)} · {e.config.mode} · {profileName(e.config.solver_profile)} · {experimentStatus[e.status]} · {e.completed}/{e.total}</option>)}</select></header>
      {selected ? <div className="experiment-progress"><strong>{profileName(selected.config.solver_profile)} · {experimentStatus[selected.status]} · {selected.completed}/{selected.total}</strong><span>{selected.stage}</span><span>Đã tạo lúc {new Date(selected.created_at).toLocaleString('vi-VN')} · {busy ? `Ước tính phần giải còn ${fmt(estimatedRemaining == null ? null : estimatedRemaining/60,1)} phút (chưa gồm khởi động/xuất file)` : 'Các lượt đã được lưu trên máy'}</span><progress max={selected.total} value={selected.completed}/><div className="lab-actions">{busy ? <button className="button secondary" disabled={!!selected.cancel_requested} onClick={() => void action('cancel')}><Square size={14}/>{selected.cancel_requested ? 'Đang dừng…' : 'Dừng và lưu'}</button> : selected.completed < selected.total && <button className="button secondary" onClick={() => void action('resume')}><RotateCcw size={14}/>Tiếp tục phần còn lại</button>}{terminal && selected.stage === 'done' && ['bundle', 'cases.csv', 'cases.parquet', 'manifest'].map(k => <a key={k} className="text-button" href={`/api/experiments/${selected.id}/exports/${k}`}><ArrowDownToLine size={14}/>{k}</a>)}</div>{selected.error && <p role="alert">{selected.error}</p>}<small>Chạm giới hạn tìm kiếm vẫn có thể có nghiệm hợp lệ đúng hạn. Đổi trang hoặc tải lại không dừng tác vụ.</small></div> : <p className="lab-empty">Chưa chạy thí nghiệm cho file này. Các biểu đồ sẽ lấy kết quả từ tác vụ bạn khởi chạy.</p>}
    </section>
    {mc && selected && <div className="kpi-grid">{[
      ['Kịch bản yêu cầu',fmt(selected.config.scenarios)], ['Đã sinh',fmt(data?.sampling?.shape[0])],
      ['Lượt đã ghi nhận',`${selected.completed}/${selected.total}`],
      ['Chạm giới hạn / lỗi', `${data?.cases.filter(c => timedOut(c)).length || 0} / ${data?.cases.filter(c => ['ERROR','GENERATION_ERROR'].includes(c.status) || c.termination_reason === 'ERROR').length || 0}`],
    ].map(([label,value]) => <article className="kpi" key={label}><div className="kpi-top">{label}</div><div className="kpi-value">{value}</div></article>)}</div>}
    {!!groups.length && <>
      {best && <div className="alert">{algorithmNames[best.algorithm]} có trung vị chi phí thấp nhất trong các nghiệm hợp lệ đã tìm được: {fmt(best.median,2)} điểm. Đọc cùng tỷ lệ khả thi và số seed.</div>}
      {mc && !!fixedGroups.length && !!recourseGroups.length && <div className="alert"><strong>Đọc riêng hai chế độ Monte Carlo.</strong><p>Lịch cố định giữ nguyên cổng và thời gian chờ: {fixedGroups.map(g => `${algorithmNames[g.algorithm]} ${g.feasible_count}/${g.count}`).join(' · ')} lượt khả thi.</p><p>Phân cổng lại dùng thông tin toàn kịch bản: {recourseGroups.map(g => `${algorithmNames[g.algorithm]} ${g.on_time_feasible_count ?? g.feasible_count}/${g.count}`).join(' · ')} lượt có nghiệm đúng hạn. Chi phí rủi ro của lịch cố định và chi phí sửa lịch không cùng thước đo.</p></div>}
      <div className="chart-grid"><Plot title={mc ? 'Tỷ lệ khả thi · lịch cố định / phân cổng lại đúng hạn' : 'Trung vị chi phí · nghiệm solver hợp lệ đúng hạn'} values={groups.map(g => ({label: `${algorithmNames[g.algorithm]} ${mc ? modeName(g.mode) : ''}`, value: mc ? (g.mode === 'fixed' ? g.feasible_rate : (g.on_time_feasible_rate ?? g.feasible_rate)) * 100 : g.median, color: g.mode === 'fixed' ? '#7497ac' : '#e68845'}))} suffix={mc ? '%' : ''}/><Plot title="Trung vị thời gian giải (giây)" values={groups.map(g => ({label: `${algorithmNames[g.algorithm]} ${mc ? modeName(g.mode) : ''}`, value: g.runtime_median}))}/></div>
      <section className="panel"><header className="panel-head"><h2>{mc ? 'Độ vững và chi phí' : 'Thống kê theo thuật toán'}</h2></header><div className="table-scroll"><table><thead><tr><th>Thuật toán / chế độ</th><th>Khả thi / đánh giá</th><th>Chạm giới hạn / lỗi</th><th>Trung bình / trung vị</th><th>Độ lệch chuẩn</th><th>Min – max</th><th>CI95 trung bình</th>{mc && <><th>P95 / CVaR95</th><th>CI95 tỷ lệ khả thi</th><th>Xung đột TB</th><th>Đổi cổng / bãi xa TB</th></>}</tr></thead><tbody>{groups.map(g => <tr key={g.key}><td>{algorithmNames[g.algorithm]}<small>{modeName(g.mode)}</small></td><td>{g.feasible_count}/{g.count}<small>{fmt(g.feasible_rate*100, 1)}%</small>{g.mode === 'fixed' ? <small>Giữ nguyên lịch, không chạy solver</small> : <small>Solver đúng hạn: {g.on_time_feasible_count == null ? 'Không có dữ liệu' : `${g.on_time_feasible_count}/${g.count} (${fmt((g.on_time_feasible_rate || 0)*100,1)}%)`}</small>}{!!g.initializer_only_count && <small>Chỉ khởi tạo: {g.initializer_only_count}</small>}</td><td>{g.timeouts} / {g.failures}</td><td>{fmt(g.mean, 2)} / {fmt(g.median, 2)}<small>n chi phí = {g.cost_sample_count}</small></td><td>{fmt(g.std, 2)}</td><td>{fmt(g.min, 2)} – {fmt(g.max, 2)}</td><td>{ci(g.mean_ci95)}</td>{mc && <><td>{fmt(g.p95, 2)} / {fmt(g.cvar95, 2)}</td><td>{ci(g.on_time_rate_ci95 ?? g.rate_ci95, true)}</td><td>{fmt(g.mean_conflicts, 2)}</td><td>{fmt(g.mean_reassignments, 2)} / {fmt(g.mean_remote, 2)}</td></>}</tr>)}</tbody></table></div><p className="footnote">{mc ? 'Fixed: chi phí rủi ro gồm phạt xung đột. Recourse: chi phí sửa lịch, chỉ trên nghiệm hợp lệ; luôn đọc cùng tỷ lệ khả thi. P95/CVaR với ít mẫu có thể không ổn định.' : 'So sánh chi phí chỉ giữa nghiệm solver hợp lệ đúng hạn; nghiệm khởi tạo hoặc trả muộn vẫn xem được nhưng không tham gia xếp hạng; không suy ra tối ưu từ việc heuristic có chi phí thấp nhất. Tái phân bổ chỉ tính được ở lượt có cổng tham chiếu.'}</p></section>
      {!mc && <section className="panel"><header className="panel-head"><h2>Thời gian – chi phí & phân rã từng lượt hợp lệ</h2></header><svg className="scatter-plot" viewBox="0 0 600 190" role="img" aria-label="Thời gian và chi phí benchmark"><path d="M45 10V160H580" fill="none" stroke="#a0a8b0"/>{cases.filter(c => c.feasible).map(c => <g key={c.case_id}><circle cx={45+c.runtime_sec/Math.max(1, ...cases.map(x => x.runtime_sec))*520} cy={150-(c.decision_cost || 0)/firstCost*125} r="5" fill="#df884d"><title>{algorithmNames[c.algorithm]} seed {c.seed}: {fmt(c.runtime_sec, 3)}s · {fmt(c.decision_cost)} điểm</title></circle></g>)}<text x="220" y="185">Thời gian (giây) → · Chi phí ↑</text></svg><Plot title="Chi phí đổi cổng / bãi xa" values={cases.filter(c => c.feasible).flatMap(c => [{label: `${algorithmNames[c.algorithm]} ${c.seed} · đổi cổng`, value: c.breakdown?.reassignment_cost ?? null}, {label: `${algorithmNames[c.algorithm]} ${c.seed} · bãi xa`, value: c.breakdown?.overflow_cost ?? null, color: '#7497ac'}])}/></section>}
      {mc && <>
        <section className="panel lab-plot"><h3>Hội tụ tỷ lệ khả thi theo chế độ</h3><svg className="convergence-chart" viewBox="0 0 600 180" role="img" aria-label="Đường hội tụ Monte Carlo"><path d="M30 10V155H580" fill="none" stroke="#aaa"/>{groups.map((g, i) => <polyline key={g.key} points={g.convergence.map(p => `${30+p.n/Math.max(1, ...groups.map(x => x.count))*545},${155-(g.mode === 'fixed' ? p.feasible_rate : (p.on_time_feasible_rate ?? p.feasible_rate))*140}`).join(' ')} fill="none" stroke={['#e68845','#7497ac','#497b62','#b66788','#7a75b4','#a68043','#df5656','#638b88'][i%8]} strokeWidth="2"><title>{algorithmNames[g.algorithm]} · {modeName(g.mode)}</title></polyline>)}<text x="30" y="175">0</text><text x="480" y="175">Số kịch bản →</text></svg><p className="footnote">Các đường dùng cùng kịch bản. 100% ở một mẫu nhỏ chưa chứng minh độ vững ngoài mẫu.</p></section>
        <div className="chart-grid"><section className="panel lab-plot"><h3>Phân phối chi phí · tách fixed / recourse</h3>{groups.map(g => {const values = (data?.cases || []).filter(c => c.algorithm === g.algorithm && c.mode === g.mode && c.source_plan_id === g.source_plan_id && (c.mode === 'fixed' ? c.budget_compliant !== false : costEligible(c))).map(c => c.mode === 'fixed' ? c.risk_cost : c.decision_cost).filter((x): x is number => x != null); const max = Math.max(1, ...values); const counts = Array.from({length: 10}, (_, i) => values.filter(v => Math.min(9, Math.floor(v/max*10)) === i).length); return <div className="hist-row" key={g.key}><span>{algorithmNames[g.algorithm]} · {modeName(g.mode)} · n={values.length}</span><div>{counts.map((n, i) => <i key={i} style={{height: `${Math.max(1, n/Math.max(1, ...counts)*65)}px`}} title={`${fmt(i*max/10)}–${fmt((i+1)*max/10)}: ${n} mẫu`}/>)}</div></div>;})}</section><Plot title="Xác suất cổng xung đột · từng lịch cố định đã kiểm tra" suffix="%" values={gateRisk}/></div>
        {!!data?.paired.length && <section className="panel"><header className="panel-head"><h2>Chênh lệch chi phí sửa lịch ghép cặp</h2></header><div className="table-scroll"><table><thead><tr><th>Lịch A – lịch B</th><th>Số cặp cùng khả thi</th><th>Trung bình A − B</th><th>CI95 bootstrap</th></tr></thead><tbody>{data.paired.map(p => <tr key={p.a+p.b}><td>{selected?.config.plans?.find(x => x.id === p.a)?.label} − {selected?.config.plans?.find(x => x.id === p.b)?.label}</td><td>{p.pairs}</td><td>{fmt(p.mean_delta, 2)}</td><td>{ci(p.ci95)}</td></tr>)}</tbody></table></div></section>}
      </>}
    </>}
    {!!data?.cases.length && <section className="panel"><header className="panel-head"><h2>Từng lượt đánh giá</h2><span className="chip">{cases.length} lượt phù hợp</span></header><div className="filters"><select aria-label="Lọc kết quả thí nghiệm" value={filter} onChange={e => {setFilter(e.target.value); setCasePage(0);}}><option value="all">Tất cả</option><option value="issues">Chưa khả thi / lỗi</option>{mc && <><option value="fixed">Lịch cố định</option><option value="recourse">Phân cổng lại</option></>}</select><select aria-label="Lọc thuật toán" value={algorithmFilter} onChange={e => {setAlgorithmFilter(e.target.value); setCasePage(0);}}><option value="all">Mọi thuật toán</option>{Object.entries(algorithmNames).map(([k,v]) => <option key={k} value={k}>{v}</option>)}</select><label className="check"><input type="checkbox" checked={worstFirst} onChange={e => {setWorstFirst(e.target.checked); setCasePage(0);}}/>Trường hợp xấu trước</label></div><div className="table-scroll"><table><thead><tr><th>Thuật toán / lượt</th><th>Trạng thái</th><th>Chi phí</th><th>Đổi cổng / bãi xa</th><th>Xung đột / đỉnh</th><th>Thời gian</th><th>Bound / gap</th><th/></tr></thead><tbody>{cases.slice(casePage*20, (casePage+1)*20).map(c => <tr key={c.case_id}><td>{algorithmNames[c.algorithm]}<small>{modeName(c.mode)} · {c.scenario == null ? `seed ${c.seed}` : `#${c.scenario+1}`}</small></td><td><span className={`badge ${c.feasible ? 'success' : 'danger'}`}>{c.status}</span><small>{sourceName(c.solution_source)}</small><small>{c.termination_reason || 'Không có dữ liệu'} · {c.budget_compliant == null ? 'Ngân sách: không có dữ liệu' : c.budget_compliant ? 'Trong ngân sách' : 'Vượt ngân sách'}</small>{c.optimality_proven && <small>Đã chứng minh tối ưu</small>}{c.error && <small title={c.error}>{c.error.slice(0,80)}</small>}</td><td>{fmt(c.mode === 'fixed' ? c.risk_cost : c.decision_cost, 2)}</td><td>{fmt(c.reassignments)} / {fmt(c.remote_count)}</td><td>{fmt(c.conflicts)} / {fmt(c.peak)}</td><td>{fmt(c.runtime_sec, 3)}s{c.timing_complete === false && <small>Thời gian chưa đầy đủ</small>}</td><td>{fmt(c.best_bound, 2)} / {fmt(c.gap, 3)}</td><td><button className="text-button" onClick={() => setDetail(c)}>Chi tiết</button><button className="text-button" disabled={!c.feasible && c.mode !== 'fixed'} onClick={() => void openCase(c)}>Xem Gantt</button></td></tr>)}</tbody></table></div><div className="pagination"><button disabled={!casePage} onClick={() => setCasePage(p => p-1)}>Trước</button><span>{casePage+1}/{Math.max(1, Math.ceil(cases.length/20))}</span><button disabled={(casePage+1)*20 >= cases.length} onClick={() => setCasePage(p => p+1)}>Sau</button></div></section>}
    {data?.sampling && <p className="footnote mono">Ma trận {data.sampling.shape.join(' × ')} · {data.sampling.unique_scenarios} kịch bản khác nhau · SHA256 {data.sampling.hash}</p>}
    {data?.assumptions && <section className="panel lab-plot"><h3>Giả định và cách đọc kết quả</h3>{data.assumptions.map(a => <p key={a}>{a}</p>)}</section>}
    {detail && <div className="drawer-overlay" onClick={() => setDetail(null)}><aside className="detail-drawer" role="dialog" aria-modal="true" aria-label="Chi tiết thí nghiệm" onClick={e => e.stopPropagation()}><button className="button secondary" onClick={() => setDetail(null)}>Đóng</button><h2>{algorithmNames[detail.algorithm]} · {modeName(detail.mode)}</h2><dl><dt>Cấu hình solver</dt><dd>{profileName(detail.solver_profile)}</dd><dt>Nguồn nghiệm</dt><dd>{sourceName(detail.solution_source)}</dd><dt>Kết thúc</dt><dd>{detail.termination_reason || 'Không có dữ liệu'}</dd><dt>Ngân sách</dt><dd>{detail.budget_compliant == null ? 'Không có dữ liệu' : detail.budget_compliant ? 'Đúng hạn' : 'Vượt ngân sách'}</dd><dt>Có nghiệm sau (giây)</dt><dd>{fmt(detail.time_to_verified_incumbent_sec)}</dd><dt>Thời gian giai đoạn (giây)</dt><dd>{detail.timings ? Object.entries(detail.timings).map(([k,v]) => <div key={k}>{timingNames[k] || k}: {fmt(v,3)}</div>) : 'Không có dữ liệu'}</dd><dt>Seed</dt><dd>{detail.seed}</dd><dt>Nguồn nghiệm khởi tạo</dt><dd>{detail.initializer || detail.trace?.initial_solution_source || (detail.algorithm === 'sa' ? 'Greedy' : '—')}</dd><dt>Trạng thái CP-SAT</dt><dd>{detail.cp_status || detail.trace?.cp_solver_status || '—'}</dd><dt>Số bước SA</dt><dd>{fmt(detail.sa_iterations ?? detail.trace?.sa_iterations)}</dd><dt>Khởi tạo / cải thiện (ms)</dt><dd>{fmt(detail.stage1_ms ?? detail.trace?.stage1_wall_clock_ms,2)} / {fmt(detail.stage2_ms ?? detail.trace?.stage2_wall_clock_ms,2)}</dd><dt>Chi phí đầu / cuối</dt><dd>{fmt(detail.trace?.initial_cost,2)} / {fmt(detail.trace?.final_cost,2)}</dd></dl><details><summary>Dữ liệu kiểm chứng</summary><pre className="case-json">{JSON.stringify(detail, null, 2)}</pre></details><p>Trace khởi tạo/SA, chẩn đoán đầy đủ và lịch được lưu trong ZIP thí nghiệm.</p></aside></div>}
  </div>;
}
