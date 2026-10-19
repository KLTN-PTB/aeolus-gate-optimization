# Dashboard web end-to-end — Aeolus

Frontend React/TypeScript dựng lại 5 màn hình theo wireframe đã cung cấp; backend
FastAPI tái sử dụng checkpoint và các bộ giải hiện có. Chạy cục bộ, không sử dụng
CDN, không tự đăng tải dữ liệu hoặc huấn luyện lại mô hình.

## Khởi động trên Windows

Từ thư mục gốc dự án, lần đầu trên máy khác:

```powershell
.\scripts\start_web_dashboard.cmd -Setup
```

Các lần sau:

```powershell
.\scripts\start_web_dashboard.cmd
```

Mở **http://127.0.0.1:8000**. Dừng bằng Ctrl+C. Sau khi sửa frontend, dùng `-Build`.
Máy cần cài Python 3.11 64-bit và Node.js 22+ (kèm npm). `-Setup` tự tạo `.venv`
nếu chưa có, cài `requirements-app.txt` gồm cả ML, solver, Streamlit và web,
kiểm tra SHA-256/nạp checkpoint, rồi cài và build frontend. Sau mỗi lần pull
cập nhật, chạy lại `-Setup` để đồng bộ thư viện và giao diện. Không dùng `--reload` hoặc nhiều
Uvicorn worker: phiên bản local chỉ cho phép một job tính toán tại một thời điểm.

Model/preprocessor được lưu trực tiếp trong Git, không cần Git LFS hoặc tải
checkpoint riêng. Repo cũng đóng gói raw Parquet nhỏ
`data/raw/ATL_20260701_02_schedule_raw.parquet` để upload và hai kịch bản
Streamlit trong `data/simulation/`. Với raw mẫu, chọn `2026-07-01`, 150 cổng,
30 bãi xa và Greedy để thử luồng đầy đủ. Dữ liệu chỉ chứa ngày khởi hành
01–02/07 nên vẫn có giới hạn bao phủ chuyến qua nửa đêm nêu bên dưới.
File `.asc` toàn tháng và dữ liệu huấn luyện thô nhiều năm không cần để chạy demo.

Chạy riêng trong quá trình phát triển:

```powershell
.\.venv\Scripts\python.exe -m uvicorn web_dashboard.app:app --host 127.0.0.1 --port 8000
# Terminal khác, tại web_dashboard/frontend:
npm ci
npm run dev
```

Không thay thế dashboard Streamlit tại cổng 8501. Liên kết Historical Replay chỉ
hoạt động khi Streamlit đã được khởi động riêng theo README_DASHBOARD.md.


## Kiểm tra lệnh khởi động mà không mở ứng dụng

Từ thư mục gốc, dùng cùng lệnh trong PowerShell hoặc Command Prompt:

```powershell
.\scripts\start_web_dashboard.cmd -Check
```

Chế độ này kiểm tra Python, dependency và frontend đã build rồi thoát. Không
cài thư viện, build, chạy server hoặc mở trình duyệt/trình soạn thảo.

Để tự chạy dashboard, bỏ -Check. Terminal giữ server hoạt động và in URL; người
dùng tự nhập http://127.0.0.1:8000 vào trình duyệt. Dừng bằng Ctrl+C.
Đổi cổng bằng -Port 8001 nếu cần.

Nếu chạy file .ps1 qua thao tác mở file của Windows, ứng dụng được mở có thể là
Notepad do file association. Launcher .cmd gọi powershell.exe với -NoProfile
và -File để thực thi script trực tiếp. Không sửa file association hoặc execution
policy của toàn máy. Bypass chỉ áp dụng cho tiến trình PowerShell của lần chạy đó.

Có thể gọi PowerShell trực tiếp:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_web_dashboard.ps1
```

## Luồng sử dụng

1. Tổng quan → chọn/kéo thả một file raw Parquet tổng hợp, hoặc hai file đến/đi.
2. Xem báo cáo chuẩn hóa. Bất kỳ dòng ATL bị lỗi đều chặn chạy; không tự bỏ dòng.
3. Chọn một ngày vận hành theo giờ ATL, quy mô và số cổng.
4. Bật bãi xa nếu cần và nhập số vị trí hữu hạn. Tắt tương đương 0 vị trí.
5. Nhấn **Chạy end-to-end**. Có thể chuyển trang trong khi worker tính toán.
6. Xem Dự báo độ trễ và Lịch phân cổng. Click chuyến/thanh Gantt để xem chi tiết.
7. Tải CSV hoặc gói ZIP. Dữ liệu và cấu hình mỗi lần chạy được lưu độc lập.

Quy mô mặc định lớn/vừa/nhỏ là **150/50/20 cổng mô phỏng**, không phải phân loại
hay số cổng thực tế của sân bay. Sân bay duy nhất có mô hình trong phiên bản này
là ATL. Tùy chỉnh cho phép 1–300 cổng tiếp xúc, 0–100 vị trí bãi xa.

Nếu không đủ năng lực, ứng dụng vẫn giữ dự báo và báo cáo, nhưng không công bố
phân cổng thiếu như một nghiệm khả thi. `UNKNOWN` không có nghĩa đã chứng minh
vô nghiệm; cần phân biệt với `INFEASIBLE`. Khi đỉnh chiếm dụng vượt tổng vị trí,
manifest ghi rõ cận dưới năng lực cần bổ sung.

CP-SAT mặc định cho phép fallback sang Greedy khi chưa tìm được nghiệm; có thể
tắt checkbox này để yêu cầu kết quả thuần CP-SAT. Fallback được xác minh độc lập,
hiển thị đúng bộ giải thực tế và không được gắn nhãn optimal. Hybrid hiện có là
CP-SAT/Greedy khởi tạo rồi Simulated Annealing cải thiện, không phải chỉ Greedy
kết hợp CP-SAT; UI mới dùng đúng tên thuật toán theo mã nguồn.

## Hợp đồng raw Parquet

Cột bắt buộc: `FL_DATE`, `OP_CARRIER`, `OP_CARRIER_FL_NUM`, `ORIGIN`, `DEST`,
`CRS_DEP_TIME`, `CRS_ARR_TIME`, `CRS_ELAPSED_TIME`.

- Nhận ngày ISO hoặc YYYYMMDD; giờ HHMM nguyên, HH:MM hoặc timestamp lịch bay.
- Nhận bí danh BTS: FlightDate, Operating_Airline/Reporting_Airline,
  Flight_Number_Operating_Airline/Flight_Number_Reporting_Airline, Origin, Dest,
  CRSDepTime, CRSArrTime, CRSElapsedTime, Tail_Number, ArrDelay, DepDelay.
- Ưu tiên tên chuẩn; nếu chưa có thì ưu tiên hãng khai thác trước hãng báo cáo.
- Tự tạo MONTH, DAY_OF_MONTH, DAY_OF_WEEK. Nếu có sẵn mà mâu thuẫn thì báo lỗi.
- `TAIL_NUM` tùy chọn. Thiếu số đuôi không ngăn dự báo; không ghép theo cùng hãng.
- `ARR_DELAY`/`DEP_DELAY` tùy chọn, chỉ để tính MAE/RMSE đối chiếu. Không sử dụng
  actual time, weather, cancellation/diversion outcomes hoặc flight chain làm
  đặc trưng, điều kiện chọn ngày, hoặc căn cứ ghép cặp.
- Không nhận file kịch bản đã có predicted_arrival_min/predicted_delay_min thay
  cho raw. Đặc biệt file 750 turnaround của Historical Replay không phải raw.
- Trùng định danh lịch bay bị chặn. Dòng không liên quan ATL được đếm riêng.
- Giới hạn: tổng upload 500 MiB, tối đa 2 file, 5 triệu dòng/file, 2 GiB dữ liệu
  Parquet giải nén/file, 3.000 lượt ATL/ngày. Không cắt mẫu âm thầm.
- Năm 2024 vẫn bị cách ly, không được sử dụng để demo qua tính năng upload.

File có thể chứa nhiều ngày; lựa chọn ngày dùng **ngày sự kiện theo lịch tại ATL**,
không phải mặc nhiên FL_DATE (ngày khởi hành ở sân bay nguồn). Ngày đến được tính
từ lịch khởi hành, múi giờ nguồn và CRS_ELAPSED_TIME rồi kiểm tra với CRS_ARR_TIME.
Không dựa vào ARR_TIME/ARR_DELAY để suy ra ngày. Nếu múi giờ không biết, giờ DST
mơ hồ hoặc lịch không nhất quán, ứng dụng báo lỗi thay vì đoán.

Luồng upload có bảng bổ sung 6 múi giờ BGR/TVC/HHH, RNO, RAP và FAR, đối chiếu
[dữ liệu sân bay OpenFlights](https://raw.githubusercontent.com/jpatokal/openflights/master/data/airports.dat).
Bảng này độc lập với bảng nghiên cứu, nên không làm thay đổi replay đã đóng băng.

Trong giao diện có liên kết tải file **ILLUSTRATIVE_ONLY_ATL_schedule.parquet**:
lịch minh họa 14 lượt, không có nhãn thực tế; không được dùng làm bằng chứng dữ
liệu sân bay thật. Hệ thống không tự sử dụng file này làm fallback.

### Chuyển file BTS .asc hiện có sang raw Parquet

```powershell
.\.venv\Scripts\python.exe scripts/prepare_web_raw_parquet.py `
  --start-date 2026-07-01 --end-date 2026-07-02 `
  --output data/raw/ATL_20260701_02_schedule_raw.parquet
```

Script không ghi đè file đã tồn tại và không thay đổi `.asc` gốc. Dữ liệu này
chứa 3.787 bản ghi ATL có FL_DATE 01–02/07, trước mọi dự báo. Vì không có bản ghi
ngày khởi hành 30/06, không được khẳng định đầy đủ tất cả chuyến đến ATL ngày
01/07. Tải thêm ngày nguồn liền kề khi cần phân tích đầy đủ qua nửa đêm.

## Mô hình và giả định khoa học

Arrival: `b5_ngboost_student_t` (hiển thị đúng trạng thái legacy theo registry).
Departure: `departure_certified_point_v1`, checkpoint XGBoost + preprocessor.
Các checkpoint được kiểm tra SHA-256 và quyền sử dụng downstream trước khi chạy.
Không fit preprocessor trên file upload. Dự báo thiếu/không hữu hạn gây lỗi,
không được thay bằng 0, trễ thực tế hoặc dự báo lưu từ kịch bản cũ.

Nguồn là USER_UPLOADED_UNVERIFIED: việc có raw không tự chứng minh độ tin cậy hay
chất lượng dự báo. Năm ngoài giai đoạn phát triển (ví dụ 2026) có cảnh báo rõ.
P(delay≥15) chỉ hiện với mô hình cung cấp xác suất. MAE/RMSE là đối chiếu trên
nhãn hợp lệ của file này, không phải chứng nhận lại mô hình. Chưa có SHAP/ROC
cho file mới; không tái sử dụng đồ thị từ tập dữ liệu khác.

Ghép cặp chỉ trên hai sự kiện kế tiếp ARR→DEP cùng số đuôi và dwell hợp lệ.
Đây là INFERRED_PAIR, không phải rotation được xác nhận. Mỗi lượt bay được dùng
đúng một lần. Chuyến lẻ sử dụng dwell giả định (mặc định 60 phút); quay đầu tối
thiểu 45 phút và buffer 15 phút đều điều chỉnh được. Buffer cộng đúng một lần.

Không tuyên bố đầy đủ tồn kho tàu đầu/cuối ngày. Không giả định tất cả chuyến lẻ
đều là turnaround hoàn chỉnh. Có thể có khoảng chiếm dụng sang ngày kế tiếp.
Phân cổng cố định; chưa mô phỏng đợi cổng, kéo tàu, loại tàu hoặc phân khu hãng.
Tái phân bổ được tính so với **Greedy trên lịch bay mô phỏng**, không phải cổng
thực tế. Mục tiêu là điểm chi phí quyết định, không quy đổi thành tiền hay tuyên
bố phân cổng làm giảm độ trễ ML đã dự báo.

## Lưu trữ, API và vận hành

Runtime nằm trong `artifacts/web_dashboard/` (được gitignore): SQLite metadata,
dữ liệu chuẩn hóa theo dataset UUID, kết quả và worker.log theo run UUID.
Raw upload chỉ được lưu tạm trong lúc chuẩn hóa rồi xóa bản tạm; file gốc trên
máy người dùng không bị thay đổi. Kết quả có thể mở lại sau khi khởi động lại.
Job chưa xong khi dừng ứng dụng chuyển sang interrupted, không giả vờ hoàn tất.
Ngân sách tìm kiếm CP-SAT mặc định 30 giây, chưa gồm dựng mô hình. Worker có
watchdog 10 phút cho toàn bộ pipeline. Không tự xóa kết quả đã hoàn tất.

API tài liệu tại `/docs`; các route chính:

- POST `/api/datasets`, GET `/api/datasets/{id}`
- GET `/api/airport-profiles`, GET `/api/health`
- POST `/api/runs`, GET `/api/runs`, GET `/api/runs/{id}`
- GET `/api/runs/{id}/results`
- GET `/api/runs/{id}/exports/{kind}`

Export kind: bundle, manifest, normalized, predictions.csv/parquet,
occupancies.csv/parquet, assignments.csv/parquet. ZIP chứa manifest, kết quả và
dữ liệu đã chuẩn hóa. Thay cấu hình không sửa lần chạy đã lưu; UI đánh dấu stale.
Chưa có tài khoản, TLS hoặc phân quyền nhiều người: **chỉ bind loopback**, không
đưa trực tiếp ứng dụng này lên LAN/Internet. Upload không nhận model/joblib/path
tùy ý. Pipeline chính chưa có nút hủy; dừng server sẽ dừng worker. Các thí nghiệm
benchmark/Monte Carlo có nút dừng và tiếp tục như hướng dẫn dưới đây.

## Lịch phân cổng và thí nghiệm mới

Ba trang dùng dữ liệu của lần chạy đang chọn. Lần chạy từ phiên bản cũ vẫn xem
được nhưng cần chạy end-to-end lại để tạo `snapshot.json` trước khi chạy thí nghiệm.
Snapshot chứa bài toán phân cổng, tham số Student-t đầy đủ, cặp chuyến, tài nguyên,
trọng số và hash mô hình. Thí nghiệm không dự báo lại theo từng thuật toán.

### Lịch phân cổng

- Xem lịch pipeline hoặc mở lịch benchmark/Monte Carlo bằng **Xem Gantt**.
- Gantt có cửa sổ 2/4/8 giờ, di chuyển thời gian, bật buffer/cổng trống, lọc và
  phân trang 25 cổng. Bảng lượt chiếm dụng và mức sử dụng cổng phân trang riêng.
- Khi thiếu sức chứa hoặc solver chưa có nghiệm, vẫn hiển thị nhu cầu, bảng lượt,
  chẩn đoán và trạng thái; không tạo lịch phân cổng giả để lấp biểu đồ.
- Biểu đồ nhu cầu dùng đỉnh trong từng khoảng 15 phút; tỷ lệ sử dụng tính hợp
  các khoảng chiếm dụng trong ngày, tránh cộng trùng lịch cố định bị xung đột.
- CSV đang xem có thể tải trực tiếp; khoảng chiếm dụng vượt ngày được giữ nguyên.

### So sánh thuật toán

Chọn **Chạy nhanh** (1 seed, 5 giây/lượt) hoặc **Nghiên cứu** (5 seed, 30 giây/lượt).
Mặc định chạy Greedy, CP-SAT, SA độc lập và Hybrid. Mỗi thuật toán dùng cùng
snapshot và mục tiêu `10 × tái phân bổ + 200 × lượt bãi xa`, 1 CP worker.

CP-SAT độc lập tắt fallback. SA tự tạo nghiệm đầu bằng Greedy, gồm cả thời gian
khởi tạo; SA/Hybrid dùng 1.000 bước SA tối đa và ngân sách toàn lượt. Hybrid chạy
CP-SAT/Greedy → SA. Trace và chẩn đoán đầy đủ nằm trong ZIP từng thí nghiệm.

Ngân sách bao gồm chuyển đổi bài toán, khởi tạo, dựng mô hình, tìm kiếm và kiểm tra.
Import Python/khởi động host được ghi ngoài ngân sách giải; host tái sử dụng giữa
các lượt, bị dừng và tạo lại khi timeout. Có 0,1 giây dung sai giám sát tiến trình.
Kết quả trả quá ngân sách bị giữ trạng thái timeout, không công bố chi phí nghiệm.
Heuristic không được gắn nhãn đã chứng minh tối ưu; CP-SAT giữ bound/gap nếu có.

### Monte Carlo

1. Chạy benchmark để có lịch từ nhiều thuật toán, hoặc chọn lịch pipeline hợp lệ.
2. Chọn tối đa một lịch ban đầu cho mỗi thuật toán trên cùng snapshot.
3. Chọn chế độ nhanh (20 mẫu, 2 giây/lượt) hoặc nghiên cứu (500 mẫu, 5 giây/lượt).
4. Chạy cả lịch cố định và phân cổng lại bằng thuật toán tương ứng với lịch ban đầu.

Lấy mẫu Student-t cho trễ đến, độc lập giữa các chuyến; giữ dự báo điểm chuyến đi
và tính lại turnaround, giữ nguyên chính sách dwell giả định của pipeline.
Không cắt đuôi độ trễ và không dùng actual delay trong file để sinh mẫu.
Mọi thuật toán dùng cùng ma trận mẫu và hash. Có thể đặt 10–1.000 kịch bản,
ngân sách mỗi lượt 1–120 giây, seed mặc định 202601.

**Lịch cố định:** giữ lựa chọn cổng, thay timestamp theo mẫu rồi kiểm tra lại.
**Phân cổng lại:** biết toàn bộ kịch bản trong ngày, là thí nghiệm hồi cứu, chưa
phải điều hành online. Số lần đổi cổng và chi phí sửa lịch lấy mốc là lịch ban đầu
được chọn. Lịch dùng Greedy fallback được nhận diện đúng là Greedy.

Chi phí fixed là chỉ số rủi ro gồm phạt xung đột; chi phí recourse chỉ thống kê trên
nghiệm hợp lệ, đọc cùng tỷ lệ khả thi. Tỷ lệ khả thi giữ timeout/lỗi trong mẫu số.
CI tỷ lệ dùng Wilson; CI trung bình/chênh lệch dùng bootstrap 2.000 lần với seed
cố định. CVaR95 là trung bình 5% quan sát xấu nhất, làm tròn số mẫu lên. So sánh
ghép cặp chỉ dùng cùng kịch bản có nghiệm hợp lệ ở cả hai bên, công bố số cặp.

Với 500 mẫu, 4 lịch, hai chế độ đánh giá có **4.000 lượt**; có thể mất nhiều giờ
trên dữ liệu lớn. UI có tiến độ, ước lượng thời gian giải còn lại, dừng/lưu và tiếp
tục. Từng lượt hoàn tất được lưu trước khi chuyển lượt tiếp theo. Khởi động lại
đánh dấu gián đoạn; tiếp tục giữ nguyên mẫu và không chạy lại lượt đã ghi nhận.
Một tác vụ tính toán nặng được nhận tại một thời điểm trên cùng kho runtime.

API bổ sung:

- GET `/api/runs/{id}/plans`, GET/POST `/api/runs/{id}/experiments`.
- GET `/api/experiments/{id}`, GET `/api/experiments/{id}/results`.
- POST `/api/experiments/{id}/cancel`, POST `/api/experiments/{id}/resume`.
- GET `/api/experiments/{id}/plans/{case_id}` để xem lại lịch.
- GET `/api/experiments/{id}/exports/{kind}`; kind: bundle, manifest,
  cases.csv, cases.parquet, results.

ZIP chứa manifest có snapshot, ma trận mẫu, số liệu tổng hợp và kết quả từng lượt.
Tác vụ hoàn tất nghĩa là đã ghi nhận đủ lượt yêu cầu, kể cả các lượt timeout hoặc
không có nghiệm; không đồng nghĩa mọi kịch bản đều khả thi.

## Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m pytest tests/web_dashboard tests/dashboard tests/test_native_dual_core_pipeline_p07.py -q
cd web_dashboard/frontend
npm ci
npm run build
npm test
```

Khi backend đang chạy, kiểm tra HTTP + subprocess + checkpoint + xuất ZIP:

```powershell
.\.venv\Scripts\python.exe scripts/smoke_web_dashboard.py --solver cpsat
# Với raw thực tế, có thể cần thêm năng lực theo đỉnh khoảng chiếm dụng dự báo:
.\.venv\Scripts\python.exe scripts/smoke_web_dashboard.py `
  --file data/raw/ATL_20260701_02_schedule_raw.parquet --date 2026-07-01 `
  --solver cpsat --gates 150 --remote 30
# Benchmark + Monte Carlo trên file thực tế:
.\.venv\Scripts\python.exe scripts/smoke_dashboard_experiments.py `
  --file data/raw/ATL_20260701_02_schedule_raw.parquet --budget 2
# Nghiệm thu sổ 500 kịch bản với bộ minh họa nhỏ và bốn lịch ban đầu:
.\.venv\Scripts\python.exe scripts/smoke_dashboard_experiments.py `
  --research --scenarios 500 --gates 3 --remote 1 --budget 2
```

Kiểm thử UI chạy qua React Testing Library/jsdom; không thay thế nghiệm thu
visual trên Chrome/Edge thật. Cần kiểm tra desktop/mobile và trình duyệt thực
tế khi có kết nối browser automation hoặc người dùng trực tiếp mở ứng dụng.

## Cấu hình solver và timeout từ giao thức v2

Trang 4 có hai cấu hình: **Tối ưu** mặc định (CP-SAT warm-start đầy đủ) và
**Baseline** (CP-SAT tìm từ đầu). Cả hai dùng một worker, cùng dữ liệu, seed và
objective; chi phí Greedy khởi tạo được tính trong ngân sách. Không gộp số liệu
hai cấu hình; manifest lưu `solver_profile` và `solver_protocol_version`.

Khi solver chạm giới hạn tìm kiếm, lượt vẫn có thể hiển thị **FEASIBLE** và
**Trong ngân sách**: đó là nghiệm đã kiểm chứng, tìm kiếm dừng ở deadline mềm
để còn thời gian trả kết quả. Nghiệm trả muộn hoặc chỉ còn Greedy khởi tạo vẫn
xem được qua Gantt nhưng không được dùng xếp hạng chi phí solver đúng hạn.
Chi phí fixed-plan vẫn gồm rủi ro xung đột; không được loại kịch bản khỏi mẫu số.

Để nhận bản cập nhật, người dùng tự dừng server bằng Ctrl+C ở terminal đang chạy,
rồi chạy lại `.\scripts\start_web_dashboard.cmd` và tải lại trang. Tạo thí nghiệm
mới để đo lại; kết quả lịch sử vẫn giữ nguyên. Thí nghiệm dùng giao thức cũ không
resume vào engine mới vì sẽ trộn hai cách tính thời gian trong cùng một lượt.

Không cần mở server để nghiệm thu bộ solver trên snapshot đã có:

```powershell
.\.venv\Scripts\python.exe -u -X utf8 scripts/validate_dashboard_solver_protocol.py artifacts/web_dashboard/runs/RUN_ID/snapshot.json --output artifacts/dashboard_runtime/acceptance_NEW_ID --budget 120
```

Thư mục output phải mới. Thêm `--profile baseline` nếu cần; kết quả gồm status,
nguồn nghiệm, ngân sách, thời gian từng giai đoạn và checkpoint. Xem
[SOLVER_PROTOCOL_V2_IMPLEMENTATION.md](SOLVER_PROTOCOL_V2_IMPLEMENTATION.md) để đọc
bằng chứng nghiệm thu và giới hạn diễn giải.
