import { useEffect, useState } from 'react';
import { Search, ShieldCheck, ArrowDownToLine } from 'lucide-react';
import { api } from './api';
import { Gantt } from './charts';
import { fmt, timelineClock, timelineDayOffset, serviceDayMinutes, type Result, type Turn } from './types';
import type { OpenPlan, Plans } from './experimentTypes';

export function GatePage({runId, result, view, onView}: {runId: string | undefined; result: Result | null; view: OpenPlan | null; onView: (p: OpenPlan | null) => void}) {
  const [search, setSearch] = useState('');
  const [plans, setPlans] = useState<Plans | null>(null);
  const [detail, setDetail] = useState<Turn | null>(null);
  const [page, setPage] = useState(0);
  const [gatePage, setGatePage] = useState(0);
  const [sort, setSort] = useState('time');
  const [error, setError] = useState('');
  const output = view?.result || result;
  useEffect(() => {
    if (!runId || !result) return;
    let active = true;
    api<Plans>(`/runs/${runId}/plans`).then(p => {if (active) setPlans(p);}).catch(() => {/* Legacy runs remain readable. */});
    return () => {active = false;};
  }, [runId, !!result]);
  if (!output) return <div className="empty-state"><h2>Lịch phân cổng đang chờ dữ liệu</h2><p>Chạy end-to-end từ Tổng quan để tạo lịch và chẩn đoán nhu cầu.</p></div>;
  const s = output.summary;
  const fixedPlan = !!view?.caseId.endsWith('_fixed');
  const infeasibilityProven = s.solver_status === 'INFEASIBLE' && s.actual_solver === 'CP-SAT';
  const midnight = output.manifest.reference_midnight_utc;
  const dayMinutes = serviceDayMinutes(midnight);
  const clock = (m: number) => {const day=timelineDayOffset(m,midnight); return timelineClock(m,midnight)+(day ? ` (${day>0?'+':''}${day} ngày)` : '');};
  const assignmentMap = new Map(output.assignments.map(a => [a.flight_id, a]));
  const rows = output.turns.filter(t => `${t.carrier}${t.flight_number} ${t.turn_id} ${assignmentMap.get(t.turn_id)?.gate_id || ''}`.toLowerCase().includes(search.toLowerCase()));
  rows.sort((a,b) => sort === 'gate' ? (assignmentMap.get(a.turn_id)?.gate_id || '~').localeCompare(assignmentMap.get(b.turn_id)?.gate_id || '~') : a.simulated_arrival_min-b.simulated_arrival_min);
  const capacity = s.contact_gates+s.remote_gates;
  const hours = Array.from({length: dayMinutes/15}, (_, i) => {
    const from=i*15, to=from+15;
    let active=output.turns.filter(t => t.simulated_arrival_min<from && t.gate_release_min>from).length;
    let peak=active;
    const events=output.turns.flatMap(t => [[t.simulated_arrival_min,1],[t.gate_release_min,-1]])
      .filter(([minute, change]) => minute>=from && minute<to && !(minute===from && change===-1))
      .sort((a,b) => a[0]-b[0] || a[1]-b[1]);
    events.forEach(([,change]) => {active+=change; peak=Math.max(peak,active);});
    return {minute: from, demand: peak};
  });
  const maxDemand = Math.max(1, capacity, ...hours.map(h => h.demand));
  const utilization = output.gates.map(g => {
    const assigned = output.assignments.filter(a => a.gate_id === g.gate_id).sort((a,b) => a.occupancy_start_min-b.occupancy_start_min);
    // Union intervals: fixed plans may conflict; occupancy utilization never >100%.
    const intervals = assigned.map(a => [Math.max(0,a.occupancy_start_min), Math.min(dayMinutes,a.occupancy_end_min)]).filter(a => a[1]>a[0]);
    let minutes=0, end=0, gap=0;
    intervals.forEach(([a,b]) => {gap=Math.max(gap,a-end); minutes+=Math.max(0,b-Math.max(end,a)); end=Math.max(end,b);});
    gap=Math.max(gap,dayMinutes-end);
    return {...g, count: assigned.length, minutes, gap};
  });
  async function choose(id: string) {
    if (!id) {onView(null); return;}
    try {
      setError(''); const [eid, cid] = id.split('.');
      const p = await api<Result>(`/experiments/${eid}/plans/${cid}`);
      onView({result: p, label: plans?.plans.find(x => x.id === id)?.label || id, experimentId: eid, caseId: cid});
    } catch(e) {setError((e as Error).message);}
  }
  const csv = 'turn_id,arrival_leg_id,departure_leg_id,gate_id,start_min,end_min,estimated\n' + rows.map(t => [t.turn_id,t.arrival_leg_id,t.departure_leg_id,assignmentMap.get(t.turn_id)?.gate_id || '',t.simulated_arrival_min,t.gate_release_min,t.is_estimated].map(v => `"${String(v ?? '').replaceAll('"','""')}"`).join(',')).join('\n');
  return <div className="gate-page">
    <section className="panel gate-source"><header className="panel-head"><div><h2>Nguồn lịch phân cổng</h2><p>#{runId?.slice(0,8)} · {output.manifest.config.service_date} · America/New_York</p></div></header><select aria-label="Nguồn lịch phân cổng" value={view ? `${view.experimentId}.${view.caseId}` : ''} onChange={e => {setDetail(null); void choose(e.target.value);}}><option value="">Lịch pipeline</option>{plans?.plans.filter(p => p.id !== 'pipeline').map(p => <option key={p.id} value={p.id}>{p.label}</option>)}{view && !plans?.plans.some(p => p.id === `${view.experimentId}.${view.caseId}`) && <option value={`${view.experimentId}.${view.caseId}`}>{view.label}</option>}</select>{view && <p className="footnote">Đang xem: {view.label}. Có thể trở lại lịch pipeline trong danh sách.</p>}{error && <p role="alert">{error}</p>}</section>
    <div className="kpi-grid">{[
      ['Lượt bay đến / đi', `${fmt(s.arrivals)} / ${fmt(s.departures)}`, `${fmt(s.occupancy_count)} lượt chiếm dụng; ${fmt(s.estimated_occupancies)} giả định`],
      ['Lượt được phân cổng', fmt(s.assigned_count), `${fmt(Math.max(0,s.occupancy_count-s.assigned_count))} lượt chưa được phân`],
      ['Nhu cầu đỉnh / sức chứa', `${fmt(s.peak_occupancy)} / ${fmt(capacity)}`, `${s.contact_gates} cổng tiếp xúc + ${s.remote_gates} bãi xa`],
      ['Đổi cổng / dùng bãi xa', `${fmt(s.reassignments)} / ${fmt(s.remote_count)}`, `${fmt(s.baseline_covered)} lượt có cổng tham chiếu`],
    ].map(([label,value,note]) => <article className="kpi" key={label}><div className="kpi-top">{label}</div><div className="kpi-value">{value}</div><p>{note}</p></article>)}</div>
    <div className={`solver-banner ${s.feasible ? '' : 'unresolved'}`}><ShieldCheck size={21}/><div><strong>{s.optimality_proven ? 'Đã chứng minh nghiệm tối ưu' : s.feasible ? 'Đã tìm được nghiệm khả thi' : 'Chưa tìm được nghiệm khả thi'}</strong><p>{s.solver_status} · {fmt(s.solver_runtime_sec, 3)} giây · {s.feasible ? 'Đã kiểm tra ràng buộc độc lập' : view?.label.includes('Cố định') ? 'Lịch cố định có thể xung đột trong kịch bản mới' : 'Chưa công bố lịch phân cổng hợp lệ'} · chi phí {fmt(s.decision_cost,2)}</p></div><span className="chip">{s.actual_solver || output.manifest.config.solver}</span></div>
    <p className="footnote">Xung đột trong lịch đang xem: {s.assigned_count ? fmt(s.conflicts) : '—'} · Kiểm tra độc lập: {s.independent_verifier_valid ? 'Hợp lệ' : 'Chưa xác nhận lịch hợp lệ'}.</p>
    {s.peak_occupancy > capacity && <div className="alert warning">Nhu cầu đồng thời {s.peak_occupancy} vượt {capacity} vị trí: thiếu ít nhất {s.peak_occupancy-capacity} vị trí theo khoảng chiếm dụng đang dùng. Thay cấu hình ở Tổng quan để tạo lần chạy mới; sức chứa không tự tăng.</div>}
    {!s.feasible && s.peak_occupancy <= capacity && <div className="alert warning">{fixedPlan ? 'Lịch cố định vi phạm ràng buộc trong kịch bản mới. Chế độ này giữ nguyên cổng và không chạy tối ưu lại.' : infeasibilityProven ? 'CP-SAT chứng minh vô nghiệm theo ràng buộc hiện tại.' : 'Chưa tìm được nghiệm trong lượt giải này; thất bại của heuristic hoặc timeout/UNKNOWN chưa chứng minh vô nghiệm.'} Bảng dưới vẫn giữ đủ lượt và thời gian chiếm dụng.</div>}
    <section className="panel"><header className="panel-head"><div><h2>Nhu cầu vị trí theo thời gian</h2><p>Mỗi cột là đỉnh chính xác trong khoảng 15 phút, gồm buffer; ngày này dài {dayMinutes/60} giờ tại ATL.</p></div></header>
      <svg className="demand-chart" viewBox="0 0 1000 180" role="img" aria-label="Nhu cầu cổng và sức chứa">
        {hours.map((h,i) => <rect key={i} x={35+i*940/hours.length} y={150-h.demand/maxDemand*130} width={940/hours.length-1} height={h.demand/maxDemand*130} fill={h.demand>capacity ? '#c75b46' : '#7698aa'}><title>{clock(h.minute)}: {h.demand} lượt</title></rect>)}
        {[[s.contact_gates,'#df884b'],[capacity,'#537c66']].map(([n,color],i) => <g key={i}><line x1="30" x2="982" y1={150-Number(n)/maxDemand*130} y2={150-Number(n)/maxDemand*130} stroke={String(color)} strokeDasharray="5 4"/><text x="35" y={Math.max(12,145-Number(n)/maxDemand*130)} fill={String(color)}>{i ? 'Tổng vị trí' : 'Cổng tiếp xúc'}: {n}</text></g>)}
        {[0,360,720,1080,dayMinutes].map(m => <text key={m} x={35+m/dayMinutes*940} y="174">{timelineClock(m,midnight)}</text>)}
      </svg>
    </section>
    <section className="panel"><header className="panel-head"><div><h2>Lịch phân cổng · Gantt</h2><p>Mỗi thanh là một lượt chiếm dụng. Chọn một lượt để xem cả chuyến đến và chuyến đi.</p></div><label className="search-box"><Search size={14}/><input aria-label="Lọc lịch phân cổng" value={search} onChange={e => {setSearch(e.target.value); setPage(0);}} placeholder="Chuyến, cổng, mã lượt…"/></label></header><Gantt key={view?.caseId || 'pipeline'} result={output} filter={search} onSelect={setDetail}/></section>
    <section className="panel"><header className="panel-head"><h2>Chi tiết từng lượt chiếm dụng</h2><a className="text-button" href={`data:text/csv;charset=utf-8,${encodeURIComponent('\ufeff'+csv)}`} download="gate_schedule.csv"><ArrowDownToLine size={14}/>CSV đang xem</a></header><div className="filters"><select aria-label="Sắp xếp phân cổng" value={sort} onChange={e => {setSort(e.target.value); setPage(0);}}><option value="time">Theo thời gian</option><option value="gate">Theo cổng</option></select><span>{rows.length} lượt phù hợp</span></div><div className="table-scroll"><table><thead><tr><th>Chuyến / lượt</th><th>Cổng</th><th>Bắt đầu</th><th>Rời cổng</th><th>Sau buffer</th><th>Nguồn khoảng chiếm dụng</th></tr></thead><tbody>{rows.slice(page*20,(page+1)*20).map(t => <tr key={t.turn_id} onClick={() => setDetail(t)}><td><button className="flight-link" onClick={() => setDetail(t)}>{t.carrier}{t.flight_number}</button><small>{t.turn_id.slice(0,22)}</small></td><td>{assignmentMap.get(t.turn_id)?.gate_id || 'Chưa được phân'}</td><td>{clock(t.simulated_arrival_min)}</td><td>{clock(t.simulated_departure_min)}</td><td>{clock(t.gate_release_min)}</td><td>{t.is_estimated ? 'Dwell giả định' : 'Ghép cùng số đuôi'}</td></tr>)}</tbody></table></div><div className="pagination"><button disabled={!page} onClick={() => setPage(p => p-1)}>Trước</button><span>{page+1}/{Math.max(1,Math.ceil(rows.length/20))}</span><button disabled={(page+1)*20>=rows.length} onClick={() => setPage(p => p+1)}>Sau</button></div></section>
    <section className="panel"><header className="panel-head"><div><h2>Mức sử dụng từng vị trí</h2><p>Phút sử dụng là hợp các khoảng chiếm dụng trong ngày, không cộng trùng khi lịch cố định xung đột.</p></div></header>
      <div className="table-scroll"><table><thead><tr><th>Vị trí</th><th>Loại</th><th>Số lượt</th><th>Phút trong ngày</th><th>Tỷ lệ sử dụng</th><th>Khoảng trống dài nhất</th></tr></thead><tbody>{utilization.slice(gatePage*20,(gatePage+1)*20).map(g => <tr key={g.gate_id}><td>{g.gate_id}</td><td>{g.is_remote ? 'Bãi xa' : 'Tiếp xúc'}</td><td>{g.count}</td><td>{fmt(g.minutes)}</td><td>{fmt(g.minutes/dayMinutes*100,1)}%</td><td>{fmt(g.gap)} phút</td></tr>)}</tbody></table></div>
      <div className="pagination"><button disabled={!gatePage} onClick={() => setGatePage(p => p-1)}>Trước</button><span>{gatePage+1}/{Math.max(1,Math.ceil(utilization.length/20))}</span><button disabled={(gatePage+1)*20>=utilization.length} onClick={() => setGatePage(p => p+1)}>Sau</button></div>
    </section>
    <section className="panel lab-plot"><h3>Giả định và cảnh báo</h3>{output.manifest.warnings.map((w,i) => <p key={i}>{w}</p>)}</section>
    {detail && <div className="drawer-overlay" onClick={() => setDetail(null)}><aside className="detail-drawer" role="dialog" aria-modal="true" aria-label="Chi tiết lượt chiếm dụng" onClick={e => e.stopPropagation()}><button className="button secondary" autoFocus onClick={() => setDetail(null)}>Đóng</button><h2>{detail.carrier}{detail.flight_number}</h2><dl><dt>Cổng / tham chiếu</dt><dd>{assignmentMap.get(detail.turn_id)?.gate_id || 'Chưa phân'} / {detail.nominal_gate_id || 'Không có'}</dd><dt>Chiếm dụng</dt><dd>{clock(detail.simulated_arrival_min)} → {clock(detail.simulated_departure_min)}</dd><dt>Buffer</dt><dd>{detail.gate_release_min-detail.simulated_departure_min} phút</dd><dt>Ghép cặp</dt><dd>{detail.pair_type} · {detail.unmatched_status}</dd></dl>{[detail.arrival_leg_id,detail.departure_leg_id].filter(Boolean).map(id => {const p=output.predictions.find(p => p.flight_id === id); return <section key={id} className="panel lab-plot"><h3>{p ? `${p.carrier}${p.flight_number} · ${p.flight_direction}` : id}</h3><p>{p?.origin} → {p?.destination}</p><p>Giờ lịch: {p?.scheduled_event_local}</p><p>Trễ dự báo gốc: {fmt(p?.predicted_delay_min,2)} phút</p><p>{p?.model_id}</p></section>;})}<p>Thời gian chiếm dụng có thể đến từ kịch bản Monte Carlo; dự báo gốc ở trên giữ nguyên để đối chiếu. Không mô phỏng kéo tàu từ bãi xa vào cổng.</p></aside></div>}
  </div>;
}
