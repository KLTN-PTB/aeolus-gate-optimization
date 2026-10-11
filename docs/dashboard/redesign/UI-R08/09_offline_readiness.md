# UI-R08 Deliverable 09: Offline Defense Readiness & Air-Gapped Runbook

**Audit Date:** 2026-10-11  
**Auditor:** Thesis Defense Reliability Lead & Air-Gapped Infrastructure Specialist  
**Verification Target:** 100% Offline Capability (Zero External Network CDN Dependencies)  
**Status:** **READY FOR OFFLINE THESIS DEFENSE**

---

## 1. Air-Gapped Operational Assurance

### 1.1. Zero Network Dependency Guarantee
During a formal thesis defense or auditorium presentation, venue Wi-Fi may be unreliable, restricted, or completely offline. The Aeolus dashboard is engineered to function 100% air-gapped:
- **No External CDN Scripts:** Font Awesome, Google Fonts, and external JS CDNs are not loaded over the internet.
- **Embedded Visualizer Runtime:** Plotly charts are rendered directly through Streamlit's native `st.plotly_chart`, using bundled local Plotly javascript.
- **Local Artifact Resolution:** All datasets, scenarios, precomputed solver runs, and machine learning models reside entirely on the local disk within `artifacts/remediation/`, `artifacts/models/`, and `data/processed/`.

---

## 2. Offline Defense Launch Runbook

### 2.1. Environment Preparation (15 Minutes Before Defense)
1. Open PowerShell terminal in project root (`D:\Study\Code\Python\Aelous`).
2. Verify local virtual environment is intact:
   ```powershell
   .venv\Scripts\python.exe --version
   ```
   *Expected output: `Python 3.11.15`*
3. Run automated preflight diagnostic check:
   ```powershell
   .venv\Scripts\python.exe -c "from dashboard.services.preflight_service import PreflightService; rep = PreflightService().run_preflight_checks(); print('Healthy:', rep.is_healthy, 'Presentation Ready:', rep.ready_for_presentation)"
   ```
   *Expected output: `Healthy: True Presentation Ready: True`*

### 2.2. Launching the Dashboard
Launch Streamlit in local headless browser mode:
```powershell
.venv\Scripts\python.exe -m streamlit run dashboard/app.py --server.headless true --server.port 8501
```

Open Google Chrome or Microsoft Edge in full-screen mode (F11):
```
http://localhost:8501
```

---

## 3. Contingency & Disaster Recovery Protocols

| Failure Scenario | Immediate Symptoms | Recovery Action | Resolution Time |
| :--- | :--- | :--- | :---: |
| **Port 8501 In Use** | Streamlit throws `Port 8501 already in use` | Launch on alternative port:<br>`.venv\Scripts\python.exe -m streamlit run dashboard/app.py --server.port 8502` | 10 seconds |
| **Browser Tab Freezes** | UI becomes unresponsive after intensive solving | Press `Ctrl + Shift + R` (Hard Reload). Streamlit session state will re-initialize to clean baseline. | 5 seconds |
| **Unexpected Cache Artifact** | Stale visual state appears | Clear cache in terminal:<br>`.venv\Scripts\python.exe -c "import streamlit as st; st.cache_data.clear()"` | 10 seconds |
| **Projector Resolution Clip** | Screen margins cropped on 1366×768 projector | Press `Ctrl + Minus (-)` in browser to scale zoom to 90%. Layout adapts smoothly. | 3 seconds |
