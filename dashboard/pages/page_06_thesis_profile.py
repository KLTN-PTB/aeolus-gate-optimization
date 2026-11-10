"""Proposal workflow using exactly the same inference and optimization backend."""
import json
from pathlib import Path
import tempfile
from uuid import uuid4

import pandas as pd
import streamlit as st

from web_dashboard.contracts import RunRequest
from web_dashboard.normalization import normalize_files
from web_dashboard.pipeline import ROOT, run_pipeline
from web_dashboard.thesis_profile import profiles, profile, explain


def render_page():
    st.title('Đề cương · dự báo và phân cổng')
    st.caption('Dùng chung backend XGBoost và cơ chế chờ cổng với dashboard web. Weather và Flight Chain không thuộc phạm vi đã chọn.')
    available = next(p for p in profiles() if p['id'] == 'thesis_xgboost')
    if not available['ready']:
        st.info(available['reason'])
        return
    p = profile()
    rows = [{'model': name, **rec['metrics'], 'threshold': rec['threshold']} for name, rec in p['comparison'].items()]
    st.subheader('So sánh mô hình')
    st.caption('Đánh giá lịch sử 2023 đã từng được xem; không coi đây là tập kiểm định chưa từng sử dụng.')
    st.dataframe(pd.DataFrame(rows), hide_index=True)
    global_path = ROOT / p['model_run'] / 'shap_global.json'
    if global_path.exists():
        with st.expander('TreeSHAP toàn cục · 1.000 mẫu / mô hình'):
            st.json(json.loads(global_path.read_text()))
    st.subheader('Chạy lịch bay bằng cùng backend')
    uploaded = st.file_uploader('Raw lịch bay Parquet', type=['parquet'], key='thesis_schedule')
    if uploaded is not None:
        try:
            with tempfile.TemporaryDirectory(prefix='aeolus_thesis_') as temporary:
                source = Path(temporary) / 'upload.parquet'
                source.write_bytes(uploaded.getvalue())
                frame, report = normalize_files([source])
            if not report['can_run']:
                st.error('Dữ liệu chưa hợp lệ.')
                st.json(report)
                return
            day = st.selectbox('Ngày vận hành', [d['date'] for d in report['dates']])
            gates = st.number_input('Cổng tiếp xúc', 1, 300, 20)
            remote = st.number_input('Bãi xa hữu hạn', 0, 100, 5)
            algorithm = st.selectbox('Thuật toán', ['greedy', 'cpsat', 'hybrid'])
            wait = st.number_input('Chờ cổng tối đa (phút)', 0, 120, 30)
            budget = st.number_input('Ngân sách bộ giải (giây)', 1, 120, 10)
            if st.button('Dự báo và phân cổng', key='thesis_run'):
                output = ROOT / 'artifacts/web_dashboard/streamlit' / uuid4().hex
                request = RunRequest(dataset_id='0'*32, service_date=day, preset='custom', contact_gates=gates,
                    remote_gates=remote, solver=algorithm, time_limit_sec=budget, model_profile='thesis_xgboost',
                    gate_time_mode='bounded_wait', max_gate_wait_min=wait)
                with st.spinner('Đang chạy và kiểm tra ràng buộc…'):
                    result = run_pipeline(frame, request, output, report)
                st.session_state['thesis_result'] = result
                st.session_state['thesis_frame'] = frame.loc[frame.service_date.eq(day)].copy()
                st.session_state['thesis_bundle'] = (output / 'bundle.zip').read_bytes()
        except Exception as exc:
            st.error(str(exc))
    result = st.session_state.get('thesis_result')
    if result:
        st.json(result['summary'])
        st.dataframe(pd.DataFrame(result['assignments']), hide_index=True)
        st.download_button('Tải kết quả', st.session_state['thesis_bundle'], file_name='thesis_run.zip')
        predictions = result['predictions']
        fid = st.selectbox('Giải thích dự báo chuyến bay', [r['flight_id'] for r in predictions])
        kind = st.selectbox('Bài toán SHAP', ['regression', 'classification'])
        if st.button('Tính TreeSHAP', key='thesis_shap'):
            frame = st.session_state['thesis_frame']
            raw = frame.loc[frame.flight_key.eq(fid)]
            task = 'arrival' if raw.direction.iloc[0] == 'ARR' else 'departure'
            st.json(explain(raw, task, kind))
    for name in ('benchmark_summary.json', 'monte_carlo_summary.json'):
        path = ROOT / p['model_run'] / 'experiments' / name
        if path.exists():
            with st.expander(name):
                st.json(json.loads(path.read_text()))
