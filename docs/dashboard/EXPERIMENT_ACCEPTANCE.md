# Nghiệm thu dashboard thí nghiệm — 18/10/2026

## Kiểm thử tự động

- Python: **447 passed**, nhóm `tests/web_dashboard`, `tests/dashboard` và
  `tests/test_native_dual_core_pipeline_p07.py`.
- Frontend: TypeScript/Vite build thành công; **13 passed** với Vitest/jsdom.
- Có kiểm thử hồi quy ngăn tải ZIP trước khi xuất xong, kiểm tra xung đột theo
  timestamp mô phỏng mới, snapshot bị sửa, giữ timeout trong mẫu số, dừng/tiếp tục,
  không trùng lượt, bốn bộ giải và ngày chuyển DST tại ATL.

## Nghiệm thu HTTP với dữ liệu thực tế

File: `data/raw/ATL_20260701_02_schedule_raw.parquet`, ngày chọn 01/07/2026.
Cấu hình: 150 cổng tiếp xúc + 30 bãi xa, pipeline Greedy; benchmark 2 giây/lượt.

- Run: `e3d3ad94181d4d9c93de0e673ddc3d38`.
- 1.848 lượt bay: 907 đến + 941 đi; 1.193 lượt chiếm dụng, đỉnh 178 vị trí.
- Benchmark: `4bf139dff2ab4ad5b7da8b15e0784491`, đủ 4 thuật toán.
- CP-SAT/SA/Hybrid timeout trong ngân sách ngắn; Greedy có nghiệm hợp lệ.
- Monte Carlo: `49f4df9779124c2ebfe89f7ec67401e0`, 20 kịch bản × 1 lịch ×
  2 chế độ = 40 lượt; đủ kết quả, xem lại Gantt và tải ZIP thành công.
- Lịch cố định: 0/20 kịch bản không xung đột. Phân cổng lại Greedy: 19/20 khả thi.
- Hash ma trận `[20, 907]`:
  `0b9b66bb123a4b2605968b25309014ca9341c69b498e2e57f90a9deaf0302444`.

Đây là nghiệm thu chức năng ở ngân sách ngắn, không phải kết luận thuật toán tốt
nhất. Các giả định ghép cặp, dwell và thiếu tồn tàu đầu ngày vẫn áp dụng.

## Nghiệm thu 500 kịch bản và benchmark nhiều seed

Bộ lịch **minh họa 14 lượt bay**, 7 lượt chiếm dụng, 3 cổng + 1 bãi xa:

- Run: `6dbbb6f76f804ba99215545d348948e0`.
- Monte Carlo: `7b9db80f83b64df595c71f0d1ad0f92b`.
- 500 kịch bản × 4 lịch × 2 chế độ = **4.000 lượt**, đủ và không trùng mã lượt.
- Mỗi thuật toán có 500 lượt lịch cố định và 500 lượt phân cổng lại.
- Cả bốn chính sách phân cổng lại có 500/500 nghiệm hợp lệ trên bộ minh họa này.
- Hash ma trận `[500, 7]`:
  `e1bcda0402f865acd38d61ea97f9b197071d8ecb8d8fe63e4eebe13559b66522`.
- ZIP 6.777.479 byte đã kiểm tra CRC đầy đủ; API xem lại Gantt trả HTTP 200.
- Benchmark nghiên cứu riêng: `660a68e3d76b45eda1299f4e6a363003`, 5 seed ×
  4 thuật toán = 20 lượt; nằm trong kho QA `artifacts/web_dashboard/acceptance_raw`.

Kết quả bộ minh họa không đại diện cho toàn bộ ngày ATL thực tế. Thí nghiệm 500
kịch bản trên đầy đủ dữ liệu thực tế có thể mất nhiều giờ và do người dùng chọn
chạy trong dashboard.

Không có trình duyệt Chrome/Edge được kết nối trong phiên nghiệm thu này.
Kiểm thử giao diện qua jsdom không thay thế kiểm tra bố cục trực quan trên máy người dùng.


## Fresh checkout verification - 2026-10-19

- Verified a checkout containing only staged/tracked files, with a separate new
  Python 3.11 environment installed from `requirements-app.txt` and frontend
  dependencies installed with `npm ci` from the committed package lock.
- Python application suite: **447 passed, 1 skipped**, 4 dependency warnings.
  Scope: `tests/web_dashboard`, `tests/dashboard`, and
  `tests/test_native_dual_core_pipeline_p07.py`.
- The skipped integration test rebuilds the replay from the optional full-month
  BTS `.asc` source, which is not shipped. A separate always-active test checks
  SHA-256 hashes of all bundled replay artifacts against their saved manifest.
- TypeScript/Vite production build passed; frontend tests: **13 passed**.
- `pip check` passed. SHAP is included in the application environment.
- HTTP smoke test used the bundled raw Parquet, date `2026-07-01`, Greedy,
  150 contact gates and 30 finite remote stands: 1,848 movements, 1,193
  occupancies assigned, independent verification passed, zero conflicts,
  predictions and assignment ZIP export succeeded.
- All 19 saved model/preprocessor files are ordinary Git files (about 7.5 MB
  combined). Runtime databases/logs and dependency/build directories are ignored.
- The PowerShell launcher creates `.venv` when missing with `-Setup`, installs
  the complete application dependencies, verifies checkpoints and builds the UI.
