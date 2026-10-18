# Visual Baseline Screenshots Directory

**Status:** `VISUAL_QA_BLOCKED`  
**Reason:** The runtime environment operates in a headless Windows CLI without browser automation drivers (`playwright`, `selenium`, `puppeteer`).

Per Safety Rule **R00-M10**, no fabricated images are generated.

Please run:
```powershell
.\.venv\Scripts\streamlit.exe run dashboard/app.py
```
And capture the 18 screenshots detailed in [`../05_visual_baseline.md`](../05_visual_baseline.md) into this directory.
