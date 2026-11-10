# Aeolus Dashboard

Nhánh phát hành: `release/dashboard-portable-20261022`. Ứng dụng dự báo độ trễ
chuyến bay và tối ưu phân cổng tại sân bay ATL, gồm dashboard web React/FastAPI
và dashboard Streamlit chạy độc lập.

Bản phát hành chứa mã nguồn, mô hình đã lưu, dữ liệu demo và các bảng nhỏ phục vụ
giao diện Streamlit. Dữ liệu huấn luyện đầy đủ, báo cáo nghiên cứu, ZIP kết quả,
notebook và bản sao lưu không được đóng gói. Có thể chạy suy luận và demo mà
không tải checkpoint riêng hoặc huấn luyện lại.

## 1. Cài đặt và chạy trên Windows

Cần Git, Python **3.11 64-bit** và Node.js **22 trở lên** kèm npm. Lần setup đầu
cần Internet để cài thư viện Python và frontend. Sau khi cài các công cụ này,
mở lại PowerShell để cập nhật PATH.

```powershell
git clone --depth 1 --branch release/dashboard-portable-20261022 https://github.com/KLTN-PTB/aeolus-gate-optimization.git
cd aeolus-gate-optimization
.\scripts\start_web_dashboard.cmd -Setup
```

`--depth 1` chỉ tải phiên bản mới nhất, tránh tải các báo cáo và artifact lớn còn
trong lịch sử Git. Lệnh setup tạo `.venv` nếu chưa có, kiểm tra Python 3.11, cài
thư viện từ [requirements-app.txt](requirements-app.txt), kiểm tra dependency,
xác minh checkpoint, cài frontend bằng `npm ci` và build giao diện. Sau đó lệnh
khởi động server tại **http://127.0.0.1:8000**.

Tự nhập URL vào trình duyệt. Launcher không tự mở trình duyệt, notebook hoặc
trình soạn thảo. Giữ terminal hoạt động khi dùng dashboard; nhấn **Ctrl+C** để dừng.

Các lần chạy tiếp theo, tại thư mục gốc dự án:

```powershell
.\scripts\start_web_dashboard.cmd
```

Sau khi pull bản cập nhật trên nhánh này, đồng bộ lại môi trường và giao diện:

```powershell
git pull --ff-only
.\scripts\start_web_dashboard.cmd -Setup
```

### Các tùy chọn launcher

| Lệnh | Hành vi |
| --- | --- |
| `.\scripts\start_web_dashboard.cmd` | Kiểm tra môi trường và profile đề cương, sau đó chạy server; build nếu chưa có frontend. |
| `.\scripts\start_web_dashboard.cmd -Setup` | Cài/cập nhật dependency, xác minh model, build frontend và chạy server. |
| `.\scripts\start_web_dashboard.cmd -Build` | Build lại frontend và chạy server; không cập nhật toàn bộ thư viện Python. |
| `.\scripts\start_web_dashboard.cmd -Check` | Kiểm tra Python, dependency, profile và frontend đã build rồi thoát; không cài đặt, build hoặc chạy server. |
| `.\scripts\start_web_dashboard.cmd -Port 8001` | Chạy web tại cổng 8001 khi cổng 8000 đang bận. |

Chạy `-Check` riêng, không ghép với `-Setup` hoặc `-Build`. Ưu tiên launcher
`.cmd`: file này gọi PowerShell trực tiếp, tránh Windows mở `.ps1` bằng ứng dụng
được gán cho loại file đó.

## 2. Chạy demo web từ dữ liệu có sẵn

1. Mở trang **Tổng quan** và tải file
   [ATL_20260701_02_schedule_raw.parquet](data/raw/ATL_20260701_02_schedule_raw.parquet).
2. Kiểm tra báo cáo đầu vào, chọn ngày **2026-07-01** theo giờ ATL.
3. Chọn **150 cổng**, **30 bãi xa** và **Greedy** để thử luồng đầy đủ trước.
   Cấu hình mặc định ban đầu là 150 cổng, 0 bãi xa và CP-SAT; cần đổi các giá trị
   này nếu muốn dùng cấu hình demo vừa nêu.
4. Để dùng profile mới, nhấn **Chọn nhanh · Đề cương XGBoost + chờ cổng**.
   Nút chỉ đổi profile và chế độ chờ cổng, giữ nguyên các thông số khác trong biểu mẫu.
5. Chạy pipeline, xem dự báo và lịch phân cổng. Chỉ kết luận khả thi khi kết quả
   đã qua kiểm tra ràng buộc; thời gian giải và sức chứa có thể ảnh hưởng kết quả.
6. Khi đã có kết quả, mở **So sánh thuật toán** hoặc **Monte Carlo** để chạy
   thí nghiệm từ cùng dữ liệu và cấu hình đã lưu.

| Trang web | Nội dung |
| --- | --- |
| Tổng quan | Tải dữ liệu, kiểm tra đầu vào, cấu hình và chạy pipeline. |
| Dự báo độ trễ | Dự báo chuyến đến/đi, kết quả phân loại, bảng tham chiếu model và SHAP. |
| Lịch phân cổng | Gantt, bảng phân cổng, lượt chiếm dụng và chẩn đoán sức chứa. |
| So sánh thuật toán | Đánh giá Greedy, CP-SAT, SA và Hybrid trên cùng đầu vào. |
| Monte Carlo | Đánh giá lịch cố định và phân cổng lại qua các kịch bản biến động. |

Giao diện cũng cung cấp file lịch minh họa để tải xuống. File raw đi kèm chỉ bao
phủ ngày khởi hành 01–02/07/2026, nên không đại diện cho toàn bộ chuỗi quay đầu
qua các ngày trước/sau. Không dùng các file kịch bản đã xử lý trong
`data/simulation/` làm file raw để upload lên dashboard web.

## 3. Định dạng dữ liệu đầu vào

Web nhận một file Parquet tổng hợp hoặc hai file Parquet đến/đi. Mỗi file cần
các cột lịch bay sau; bộ đọc cũng hỗ trợ các tên tương đương BTS có trong mã chuẩn hóa.

| Cột | Ý nghĩa |
| --- | --- |
| `FL_DATE` | Ngày khởi hành theo lịch tại sân bay xuất phát, dạng `YYYY-MM-DD`. |
| `OP_CARRIER` | Mã hãng khai thác. |
| `OP_CARRIER_FL_NUM` | Số hiệu chuyến bay. |
| `ORIGIN`, `DEST` | Mã sân bay xuất phát và đến. |
| `CRS_DEP_TIME`, `CRS_ARR_TIME` | Giờ khởi hành/đến theo lịch tại sân bay tương ứng, dạng HHMM. |
| `CRS_ELAPSED_TIME` | Thời lượng bay theo lịch, tính bằng phút. |

`TAIL_NUM` là cột tùy chọn phục vụ ghép lượt đến–đi cùng tàu bay. Các cột
`ARR_DELAY` và `DEP_DELAY` chỉ dùng đối chiếu kết quả nếu có, không làm đầu vào
dự báo hoặc căn cứ ghép chuyến. Thiếu số đuôi có thể làm tăng số lượt chiếm dụng
dùng thời gian giả định; ghép từ lịch không đồng nghĩa với chuỗi vận hành đã xác thực.

Tổng dung lượng upload tối đa là **500 MiB**; mỗi file không quá **5 triệu dòng**
và **2 GiB dữ liệu giải nén**. Ngày được chọn có tối đa **3.000 lượt bay ATL**.
Các dòng ngoài ATL được thống kê riêng. Lỗi ở dòng ATL phải được xử lý theo báo
cáo kiểm tra trước khi chạy; ứng dụng không tự bỏ âm thầm các dòng lỗi này.

Ngày vận hành và trục thời gian được hiển thị theo **America/New_York**, có tính
đến thay đổi giờ mùa hè. Dữ liệu năm **2024 bị cách ly** theo chính sách holdout
của dự án và không được nạp cho demo.

## 4. Mô hình và thông số phân cổng

### Hai profile dự báo

| Profile | Vai trò |
| --- | --- |
| Native hiện có (`legacy_native`) | Profile mặc định; dùng NGBoost cho chuyến đến và XGBoost cho chuyến đi. |
| Đề cương · XGBoost (`thesis_xgboost`) | Dùng 4 checkpoint XGBoost: phân loại và hồi quy cho cả chuyến đến lẫn chuyến đi; kèm 2 ngân hàng sai số cho Monte Carlo. |

Nhánh chứa **25 file `.joblib`**: 19 checkpoint/preprocessor legacy và 6 file của
profile đề cương; ngoài ra có các model legacy dạng JSON. File
[active_profile.json](artifacts/thesis_completion/active_profile.json) ghi đường
dẫn, SHA-256, ngưỡng phân loại và số liệu tham chiếu của profile mới. Setup xác
minh các checkpoint cần thiết và khả năng nạp model trên CPU.

Với profile đề cương, cảnh báo trễ ≥15 phút dùng xác suất và ngưỡng đã lưu của
từng model; không mặc định lấy ngưỡng 0,5 hoặc thay bằng phép so sánh số phút trễ
hồi quy. Bảng so sánh 16 model là **kết quả đánh giá lịch sử năm 2023**, không
phải điểm đánh giá của file vừa upload; ngưỡng được chọn từ dự đoán ngoài mẫu
theo thời gian của năm 2022.

TreeSHAP theo từng chuyến giải thích checkpoint XGBoost của profile đề cương.
Hồi quy được giải thích bằng phút trễ có dấu; phân loại được giải thích bằng
log-odds gốc trước hiệu chỉnh xác suất. SHAP toàn cục và SHAP từng chuyến có phạm
vi khác nhau, không thể dùng làm bằng chứng về độ chính xác trên dữ liệu mới.

### Thời gian và sức chứa

- **Buffer (thời gian đệm):** khoảng thời gian sau khi tàu rời cổng trước khi
  cổng được giải phóng cho lượt kế tiếp. Mặc định 15 phút; đây không phải thời
  gian chờ tìm cổng.
- **Quay đầu tối thiểu:** thời gian phục vụ tối thiểu giữa lượt đến và đi, mặc
  định 45 phút. **Dwell chuyến lẻ** là thời gian chiếm dụng giả định khi thiếu
  lượt ghép, mặc định 60 phút và phải lớn hơn hoặc bằng thời gian quay đầu tối thiểu.
- **Chờ cổng hữu hạn:** cho phép dịch cả giờ vào và ra cổng, giữ thời gian phục
  vụ và buffer; mặc định chờ tối đa 30 phút. Lượt chỉ có chuyến đi không được chờ.
  Trọng số mặc định: 1 điểm/phút chờ, 10 điểm/đổi cổng và 200 điểm/dùng bãi xa.
- **Sức chứa:** các quy mô có sẵn là 150, 50 và 20 cổng; dùng Tùy chỉnh để nhập
  số khác. Bãi xa là nguồn lực hữu hạn; mặc định 0 vị trí. Dùng bãi xa không
  đồng nghĩa với việc ứng dụng mô phỏng kéo tàu trở lại cổng.

## 5. So sánh thuật toán và Monte Carlo

Pipeline chính có Greedy, CP-SAT và Hybrid; SA độc lập nằm trong trang so sánh.
Giới hạn tìm kiếm pipeline mặc định 30 giây. Ngân sách thí nghiệm cho từng lượt
có thể đặt từ 1 đến 120 giây; đây không phải tổng thời gian của toàn thí nghiệm.
Khởi động tiến trình, chuẩn bị dữ liệu và xuất kết quả cũng góp vào thời gian chờ.
Chạm giới hạn tìm kiếm vẫn có thể có nghiệm khả thi; cần đọc trạng thái, nguồn
nghiệm và kết quả kiểm chứng. Nghiệm khả thi chưa nhất thiết đã được chứng minh tối ưu.

| Chế độ | Benchmark | Monte Carlo |
| --- | --- | --- |
| Chạy nhanh | Mặc định 5 giây/lượt. | Mặc định 20 kịch bản, 2 giây/lượt. |
| Nghiên cứu | Mặc định 5 seed, 30 giây/lượt. | Mặc định 500 kịch bản, 5 giây/lượt. |

Monte Carlo hỗ trợ 10–1.000 kịch bản. Trong benchmark, CP-SAT tắt fallback;
SA tính cả bước tạo nghiệm Greedy ban đầu, còn Hybrid tính cả hai giai đoạn.
Đọc chi phí cùng tỷ lệ khả thi, ngân sách và số lượt đã hoàn thành.

- **Lịch cố định:** giữ cổng và số phút chờ của lịch ban đầu, rồi đánh giá dưới
  biến động. Nhóm này không chạy lại solver; tỷ lệ khả thi phản ánh độ vững của lịch.
- **Phân cổng lại:** giải lại với thông tin toàn kịch bản đã biết. Đây là đánh
  giá hồi cứu, không phải cam kết về một hệ thống ra quyết định trực tuyến.
- Chi phí rủi ro của lịch cố định và chi phí quyết định khi phân cổng lại có ý
  nghĩa khác nhau; không xếp hạng chung chỉ bằng cách so trực tiếp hai con số.

Profile đề cương lấy mẫu sai số đến/đi từ ngân hàng sai số dự đoán ngoài mẫu theo
thời gian; profile legacy dùng biến động đến Student-t và giữ dự báo điểm chuyến
đi. Các thuật toán trong cùng thí nghiệm dùng chung kịch bản. Chế độ nghiên cứu
có thể mất nhiều thời gian; dùng **Dừng và lưu** hoặc **Tiếp tục phần còn lại**.
Đổi trang hoặc tải lại trình duyệt không tự dừng tác vụ backend.

## 6. Dashboard Streamlit và tài liệu thiết kế

Sau khi setup hoàn tất, mở terminal khác tại thư mục gốc dự án:

```powershell
.\.venv\Scripts\streamlit.exe run dashboard/app.py --server.headless true
```

Tự mở **http://127.0.0.1:8501**. Streamlit chạy riêng với web ở cổng 8000;
`--server.headless true` ngăn Streamlit tự mở trình duyệt. Hai dashboard không
tự khởi động lẫn nhau.

Các kịch bản gồm lịch mặc định 120 lượt, kịch bản 85 lượt, 30 lượt quay đầu
dual-core, stress 1.500 lượt/50 cổng và lịch sử BTS 01/07/2026 gồm 750 lượt đến
và 750 lượt đi, ghép thành 750 lượt quay đầu/150 cổng. Kịch bản lịch sử sử dụng
thời gian thực tế để tái hiện, không được xem là kết quả dự báo cho năm 2026.
Các file kịch bản đã xử lý nằm trong `data/simulation/` và các bảng demo được đóng gói.

[HTML wireframe](dashboard/Dashboard%20Wireframes%20-%20Flight%20Delay%20%26%20Gate%20Reassignment.html)
là bản tham khảo thiết kế đóng gói, không phải ứng dụng web hiện hành. Khởi động
dashboard bằng launcher thay vì mở file HTML này.

## 7. Dependency, kết quả và kiểm thử

| File dependency | Cách sử dụng |
| --- | --- |
| `requirements-app.txt` | Đầu vào setup; môi trường đầy đủ cho web, Streamlit, model và solver. |
| `requirements.txt` | Bộ thư viện nền được file ứng dụng và các luồng nghiên cứu sử dụng. |
| `requirements-web.txt` | Dependency web bổ sung; không phải môi trường ML đầy đủ khi cài riêng. |
| `requirements-dashboard.txt` | Dependency giao diện Streamlit/Plotly; không đủ để thay setup toàn ứng dụng. |
| `requirements-binary.txt`, `requirements-binary-v3.txt` | Môi trường cho các luồng nghiên cứu cải thiện phân loại; không cần cài riêng để chạy dashboard. |

Các nguồn huấn luyện đã đóng băng được giữ nguyên. Mã nghiên cứu còn trong nhánh
không có nghĩa toàn bộ dữ liệu và artifact để tái lập nghiên cứu đã được đóng gói.

Dữ liệu chuẩn hóa, metadata SQLite, lượt chạy và thí nghiệm mới được lưu cục bộ
trong `artifacts/web_dashboard/`, đã được Git bỏ qua. Dùng các nút xuất trên giao
diện để tải manifest, bảng dữ liệu hoặc ZIP kết quả. ZIP do người dùng xuất khi
chạy là kết quả cục bộ, không phải ZIP có sẵn trong mã nguồn phát hành.

Kiểm thử phần dashboard từ thư mục gốc:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/web_dashboard tests/dashboard -q
```

Kiểm thử và build frontend từ thư mục frontend, sau khi đã setup:

```powershell
cd web_dashboard/frontend
npm.cmd test
npm.cmd run build
```

Bộ kiểm thử nghiên cứu toàn dự án có thể cần các dữ liệu/báo cáo không thuộc bản
phát hành. Các lệnh trên dành cho phạm vi dashboard; không dùng chúng để tuyên
bố đã tái lập toàn bộ kết quả nghiên cứu.

## 8. Xử lý sự cố

| Hiện tượng | Cách xử lý |
| --- | --- |
| Không tìm thấy Python phù hợp hoặc `.venv` dùng sai phiên bản | Cài Python 3.11 64-bit, mở lại PowerShell và kiểm tra phiên bản môi trường trước khi setup lại. Launcher không tự thay môi trường đã có bằng một phiên bản Python khác. |
| Thiếu dependency | Chạy lại launcher với `-Setup` tại thư mục gốc dự án; không chỉ cài riêng dependency giao diện. |
| Thiếu checkpoint hoặc sai SHA-256 | Kiểm tra đang dùng đúng nhánh phát hành và khôi phục file đúng từ Git. Không đổi hash hoặc huấn luyện lại để bỏ qua kiểm tra. |
| Mở `.ps1` lại hiện trình soạn thảo | Dùng `.\scripts\start_web_dashboard.cmd` trong terminal. |
| Cổng 8000 đã được dùng | Thêm `-Port 8001`, rồi truy cập đúng URL mà terminal in ra. |
| Giao diện cũ sau khi pull | Dừng server, chạy lại `-Setup` để đồng bộ dependency và build; nếu chỉ sửa frontend, dùng `-Build`. Sau đó tải lại trang. |
| `-Check` báo chưa có frontend | Chạy `-Setup` hoặc `-Build` trước; `-Check` không tự tạo bản build. |
| Không tải được file Parquet | Xem báo cáo đầu vào, kiểm tra cột bắt buộc, giới hạn dung lượng, ngày được chọn và định dạng raw. |
| Solver chạm giới hạn hoặc chưa có nghiệm | Xem chẩn đoán sức chứa, buffer, mức chờ, nguồn nghiệm và ngân sách; thử Greedy để kiểm tra luồng. Tăng ngân sách không bảo đảm tồn tại nghiệm khả thi. |
