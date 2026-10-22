# Aeolus Dashboard

Nh?nh ph?t h?nh g?n: `release/dashboard-portable-20261022`. Ch?a m? ngu?n,
checkpoint c?n cho suy lu?n, d? li?u demo v? c?c b?ng nh? ???c dashboard
Streamlit ??c tr?c ti?p. B?o c?o nghi?n c?u, k?t qu? hu?n luy?n trung gian,
ZIP v? notebook kh?ng n?m trong b?n ph?t h?nh.

## C?i ??t v? ch?y dashboard web

C?n Python 3.11 64-bit, Node.js 22+ (k?m npm) v? Internet trong l?n c?i ??u:

```powershell
git clone --depth 1 --branch release/dashboard-portable-20261022 https://github.com/KLTN-PTB/aeolus-gate-optimization.git
cd aeolus-gate-optimization
.\scripts\start_web_dashboard.cmd -Setup
```

`-Setup` t?o `.venv`, c?i dependency, x?c minh checkpoint v? build frontend,
sau ?? ch?y server t?i **http://127.0.0.1:8000**. L?nh kh?ng t? m? tr?nh duy?t.
D?ng server b?ng Ctrl+C. C?c l?n sau d?ng:

```powershell
.\scripts\start_web_dashboard.cmd
```

Sau khi pull b?n c?p nh?t, ch?y l?i v?i `-Setup`. D?ng `-Check` ?? ki?m tra
m?i tr??ng v? b?n build m? kh?ng kh?i ??ng server. N?u c?ng 8000 b?n, th?m
`-Port 8001`.

C? th? upload tr?c ti?p `data/raw/ATL_20260701_02_schedule_raw.parquet`, ch?n
ng?y `2026-07-01`. C?c k?ch b?n Streamlit n?m trong `data/simulation/`.
Profile ?? c??ng d?ng 4 checkpoint XGBoost v? 2 ng?n h?ng sai s?; s? li?u
so s?nh 16 model l? k?t qu? ??nh gi? l?ch s?, kh?ng ph?i k?t qu? c?a file v?a upload.
To?n b? model c?n ?? ch?y ???c l?u trong Git, kh?ng ph?i t?i ri?ng hay hu?n luy?n l?i.

## Dashboard Streamlit

Sau khi ?? ch?y `-Setup`, d?ng terminal kh?c t?i th? m?c d? ?n:

```powershell
.\.venv\Scripts\streamlit.exe run dashboard/app.py
```

Streamlit ch?y ri?ng t?i **http://127.0.0.1:8501**. L?nh n?y d?nh cho c?c
k?ch b?n l?ch s? v? trang nghi?n c?u; dashboard web ch?y ? c?ng 8000.
