import { useState } from 'react';
import { BarChart3, CalendarRange } from 'lucide-react';
import { fmt, timelineClock, timelineDayOffset, serviceDayMinutes, type Result, type Turn } from './types';

export function EmptyChart({label = 'Biểu đồ sẽ xuất hiện sau khi chạy pipeline'}: {label?: string}) {
  return <div className="empty-chart"><BarChart3 size={28} strokeWidth={1.4}/><span>{label}</span></div>;
}

export function HourlyChart({result}: {result: Result | null}) {
  if (!result) return <EmptyChart/>;
  const hours = Array.from({length: 24}, () => ({arr: 0, dep: 0}));
  result.predictions.forEach(p => {const hour = Number(p.scheduled_event_local.slice(11, 13)); if (hours[hour]) hours[hour][p.flight_direction === 'ARR' ? 'arr' : 'dep']++;});
  const max = Math.max(1, ...hours.flatMap(h => [h.arr, h.dep]));
  return <div className="bar-chart"><div className="chart-axis"><span>{max}</span><span>{Math.round(max / 2)}</span><span>0</span></div>
    <div className="hour-bars">{hours.map((h, i) => <div className="bar-pair" key={i} title={`${i}h · ${h.arr} đến / ${h.dep} đi`}>
      <div className="bar-track"><i style={{height: `${h.arr / max * 100}%`}}/><i style={{height: `${h.dep / max * 100}%`}}/></div>
      <span>{i % 4 === 0 || i === 23 ? `${String(i).padStart(2, '0')}h` : ''}</span></div>)}</div></div>;
}

export function DelayChart({result}: {result: Result | null}) {
  if (!result) return <EmptyChart/>;
  const bounds = [-Infinity, 0, 15, 30, 60, Infinity];
  const labels = ['Sớm', '0–15', '15–30', '30–60', '≥60'];
  const counts = labels.map((_, i) => result.predictions.filter(p => p.predicted_delay_min >= bounds[i] && p.predicted_delay_min < bounds[i + 1]).length);
  const max = Math.max(1, ...counts);
  return <div className="distribution">{labels.map((label, i) => <div className="dist-group" key={label}>
    <div className="dist-track"><div style={{height: `${counts[i] / max * 100}%`, background: ['#6d9b91', '#739ab5', '#e6ae5f', '#e78a51', '#d9604c'][i]}}><span>{fmt(counts[i])}</span></div></div>
    <span>{label}</span></div>)}</div>;
}

export function Gantt({result, filter, onSelect}: {result: Result; filter: string; onSelect: (turn: Turn) => void}) {
  const [showIdle, setShowIdle] = useState(false);
  const [gateType, setGateType] = useState('all');
  const [windowHours, setWindowHours] = useState(0);
  const [offset, setOffset] = useState(0);
  const [gatePage, setGatePage] = useState(0);
  const [showBuffer, setShowBuffer] = useState(true);
  const turns = new Map(result.turns.map(t => [t.turn_id, t]));
  const assignmentMap = new Map<string, typeof result.assignments>();
  result.assignments.forEach(a => {
    const turn = turns.get(a.flight_id);
    if (!turn) return;
    if (filter && !`${turn.carrier}${turn.flight_number} ${a.gate_id} ${turn.turn_id}`.toLowerCase().includes(filter.toLowerCase())) return;
    const list = assignmentMap.get(a.gate_id) || []; list.push(a); assignmentMap.set(a.gate_id, list);
  });
  const gates = result.gates.filter(g => (showIdle || assignmentMap.has(g.gate_id)) && (gateType === 'all' || (gateType === 'remote') === g.is_remote));
  const allTimes = result.assignments.flatMap(a => [a.occupancy_start_min, a.occupancy_end_min]);
  const fullStart = Math.floor(Math.min(0, ...allTimes) / 120) * 120;
  const fullEnd = Math.ceil(Math.max(serviceDayMinutes(result.manifest.reference_midnight_utc), ...allTimes) / 120) * 120;
  const start = windowHours ? offset : fullStart;
  const end = windowHours ? offset + windowHours * 60 : fullEnd;
  const ticks = Array.from({length: 7}, (_, i) => start + (end - start) * i / 6);
  const midnight = result.manifest.reference_midnight_utc;
  return <>
    <div className="gantt-tools"><div className="legend"><span><i className="low"/>Thấp</span><span><i className="medium"/>Vừa</span><span><i className="high"/>Cao</span><span><i className="estimated"/>Dwell ước lượng</span></div>
      <label className="check"><input type="checkbox" checked={showIdle} onChange={e => {setShowIdle(e.target.checked); setGatePage(0);}}/>Hiện cổng trống</label>
      <label className="check"><input type="checkbox" checked={showBuffer} onChange={e => setShowBuffer(e.target.checked)}/>Hiện buffer</label>
      <select aria-label="Loại cổng" value={gateType} onChange={e => {setGateType(e.target.value); setGatePage(0);}}><option value="all">Tất cả vị trí</option><option value="contact">Cổng tiếp xúc</option><option value="remote">Bãi từ xa</option></select>
      <select aria-label="Cửa sổ Gantt" value={windowHours} onChange={e => {setWindowHours(Number(e.target.value)); setOffset(0);}}><option value="0">Toàn bộ lịch</option><option value="2">2 giờ</option><option value="4">4 giờ</option><option value="8">8 giờ</option></select>
      {!!windowHours && <><button className="text-button" disabled={offset<=fullStart} onClick={() => setOffset(v => Math.max(fullStart,v-windowHours*60))}>← Trước</button><button className="text-button" disabled={end>=fullEnd} onClick={() => setOffset(v => Math.min(fullEnd-windowHours*60,v+windowHours*60))}>Sau →</button></>}</div>
    <div className="gantt-scroll"><div className="gantt-canvas"><div className="gantt-header"><div>CỔNG ĐỖ</div><div className="gantt-scale">{ticks.map((t, i) => {const day=timelineDayOffset(t,midnight); return <span key={i} style={{left: `${i * 100 / 6}%`}}>{timelineClock(t, midnight)}{day ? ` ${day>0?'+':''}${day}d` : ''}</span>;})}</div></div>
      {gates.slice(Math.min(gatePage, Math.max(0, Math.ceil(gates.length/25)-1))*25, (Math.min(gatePage, Math.max(0, Math.ceil(gates.length/25)-1))+1)*25).map(g => <div className="gantt-row" key={g.gate_id}><div className="gate-label"><CalendarRange size={13}/>{g.gate_id}{g.is_remote && <small>XA</small>}</div>
        <div className="gantt-lane">{ticks.map((_, i) => <i className="gridline" key={i} style={{left: `${i * 100 / 6}%`}}/>)}
          {(assignmentMap.get(g.gate_id) || []).filter(a => a.occupancy_end_min>start && a.occupancy_start_min<end).map(a => {const turn = turns.get(a.flight_id)!;
            const blockStart = Math.max(start,a.occupancy_start_min);
            const blockEnd = Math.min(end, showBuffer ? a.occupancy_end_min : turn.simulated_departure_min);
            if (blockEnd<=blockStart) return null;
            const level = turn.probability_delay_15 == null ? 'unknown' : turn.probability_delay_15 >= .5 ? 'high' : turn.probability_delay_15 >= .25 ? 'medium' : 'low';
            return <button key={a.flight_id} className={`gantt-block ${level} ${turn.is_estimated ? 'assumed' : ''}`}
              style={{left: `${(blockStart - start) / (end - start) * 100}%`, width: `${(blockEnd-blockStart) / (end - start) * 100}%`}}
              title={`${turn.carrier}${turn.flight_number} · ${g.gate_id} · ${timelineClock(a.occupancy_start_min, midnight)}–${timelineClock(a.occupancy_end_min, midnight)} · chờ cổng ${a.gate_wait_min || 0} phút${turn.is_estimated ? ' · khoảng chiếm dụng giả định' : ''}`}
              onClick={() => onSelect(turn)}>{turn.carrier}{turn.flight_number}</button>;})}</div></div>)}
      {gates.length === 0 && <div className="empty-chart">Không có phân cổng phù hợp bộ lọc.</div>}
    </div></div>
    <div className="pagination"><button disabled={!gatePage} onClick={() => setGatePage(v => v-1)}>Cổng trước</button><span>Trang {Math.min(gatePage+1, Math.max(1,Math.ceil(gates.length/25)))}/{Math.max(1,Math.ceil(gates.length/25))} · {gates.length} vị trí</span><button disabled={(gatePage+1)*25>=gates.length} onClick={() => setGatePage(v => v+1)}>Cổng sau</button></div>
    <p className="footnote">America/New_York · Thanh gồm buffer giải phóng cổng. Màu xám: chưa có xác suất trễ. Nhấn một lượt để xem chi tiết.</p>
  </>;
}
