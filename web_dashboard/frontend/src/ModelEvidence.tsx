import {useEffect, useState} from 'react';
import {api} from './api';
import {fmt} from './types';

interface Comparison {scope: string; models: Record<string,{task:string; kind:string; family:string; threshold:number; metrics:Record<string,number>}>;
  global_shap?: Record<string,{sample_count:number; features:{feature:string; mean_abs_shap:number}[]}>;}
interface Explanation {model_sha256:string; output_space:string; features:string[]; values:number[][]; base_values:number[]; raw_predictions:number[];}

export function ModelComparison() {
  const [data,setData]=useState<Comparison|null>(null);
  const [error,setError]=useState('');
  useEffect(()=>{api<Comparison>('/model-comparison').then(setData).catch(e=>setError(e.message));},[]);
  return <section className="panel"><header className="panel-head"><div><h2>So sánh 16 mô hình theo đề cương</h2><p>Bảng tham chiếu của profile đề cương, đánh giá lịch sử 2023; không phải điểm đánh giá của file vừa tải lên. Mô hình thực sự dùng trong lượt chạy nằm ở thẻ bên dưới. Ngưỡng được chọn từ OOF 2022, không chỉnh theo 2023. AP/F1/AUC càng cao càng tốt; MAE/RMSE tính bằng phút, càng thấp càng tốt.</p></div></header>
    {error && <p className="footnote">{error}</p>}
    {data && <><div className="table-scroll"><table><thead><tr><th>Chiều</th><th>Bài toán</th><th>Thuật toán</th><th>AP / MAE</th><th>F1 / RMSE</th><th>Precision</th><th>Recall</th><th>AUC</th><th>Ngưỡng</th></tr></thead><tbody>
      {Object.entries(data.models).map(([id,m])=><tr key={id}><td>{m.task==='arrival'?'Đến':'Đi'}</td><td>{m.kind==='classification'?'Trễ ≥15 phút':'Số phút trễ'}</td><td>{m.family}</td><td>{fmt(m.metrics.ap??m.metrics.mae,4)}</td><td>{fmt(m.metrics.f1??m.metrics.rmse,4)}</td><td>{fmt(m.metrics.precision,4)}</td><td>{fmt(m.metrics.recall,4)}</td><td>{fmt(m.metrics.roc_auc,4)}</td><td>{m.kind==='classification'?fmt(m.threshold,4):'—'}</td></tr>)}
    </tbody></table></div>{data.global_shap && <details><summary>TreeSHAP toàn cục của XGBoost</summary>{Object.entries(data.global_shap).map(([id,g])=><div key={id}><h3>{id} · {g.sample_count} mẫu</h3>{g.features.slice(0,10).map(f=><p key={f.feature}>{f.feature}: {fmt(f.mean_abs_shap,4)}</p>)}</div>)}</details>}</>}
  </section>;
}

export function FlightExplanation({runId,flightId}:{runId:string;flightId:string}) {
  const [kind,setKind]=useState('regression');
  const [data,setData]=useState<Explanation|null>(null);
  const [error,setError]=useState('');
  const [loading,setLoading]=useState(false);
  useEffect(()=>{setData(null);setError('');},[runId,flightId,kind]);
  async function load(){setLoading(true);setError('');try{setData(await api<Explanation>(`/runs/${runId}/explanation/${encodeURIComponent(flightId)}?kind=${kind}`));}catch(e){setError((e as Error).message);}finally{setLoading(false);}}
  const rows=data?data.features.map((f,i)=>({f,v:data.values[0][i]})).sort((a,b)=>Math.abs(b.v)-Math.abs(a.v)):[];
  return <section className="panel lab-plot"><h3>Giải thích XGBoost của chuyến này</h3><select aria-label="Bài toán SHAP" value={kind} onChange={e=>setKind(e.target.value)}><option value="regression">Số phút trễ</option><option value="classification">Nhị phân</option></select><button className="button secondary" disabled={loading} onClick={()=>void load()}>{loading?'Đang tính…':'Tính TreeSHAP'}</button>
    {error&&<p role="alert">{error}</p>}{data&&<><p>{data.output_space==='signed_delay_minutes'?'Đơn vị: phút trễ có dấu.':'Đơn vị: log-odds gốc, trước hiệu chỉnh xác suất.'} Giá trị gốc {fmt(data.base_values[0],4)} + đóng góp = {fmt(data.raw_predictions[0],4)}.</p>{rows.slice(0,12).map(r=><p key={r.f}>{r.f}: {r.v>0?'+':''}{fmt(r.v,4)}</p>)}<small>SHA-256: {data.model_sha256}</small></>}
  </section>;
}
