# Chẩn đoán timeout tại trang 4 — So sánh thuật toán

Ngày kiểm tra: 19/10/2026. Chạy trực tiếp bằng Python của dự án, không mở trình duyệt,
notebook hoặc khởi động server. Không thay đổi lịch sử thí nghiệm, database dashboard,
mô hình ML hoặc cấu hình solver đang phục vụ ứng dụng.

## Dữ liệu và cách tái hiện

Đúng snapshot của các lượt người dùng gặp lỗi:

- Run: `4603faa63a244eea995410e9575c8574`.
- Snapshot hash: `8954188c9e38ac952268c61ac751e379f05fe29afd251616c383921be9e72c2f`.
- SHA-256 file: `ba597fceade5feca0a660a97ffd8ca7e2656aab7d9bf934b92a5e5130a0f9bb5`.
- 1.193 lượt chiếm dụng; 150 cổng tiếp xúc + 30 bãi xa hữu hạn, mỗi tài nguyên sức chứa 1.
- Nhu cầu đỉnh 178; mọi lượt đều tương thích cả 180 tài nguyên.
- Cùng objective, seed 202601, 1 worker, tắt CP-SAT warm-start/fallback như trang so sánh.
- SA dùng đủ 1.000 vòng. Kết quả được kiểm chứng lại bằng common evaluator.

Database được đọc bằng SQLite `mode=ro`. Các thí nghiệm cũ có ngân sách 35 và 120
**được lưu đúng giá trị**; không có bằng chứng frontend bỏ qua giá trị 120.
Lượt `7c7a5b19f15a4046a654317d80976f6b` có SA khả thi sau 120,083 giây;
lượt `4b4fc1bba1004bacaaebb72794e26b11` lại bị hủy ở cùng mức 120 giây.

Máy kiểm tra có khoảng 16,9 GB RAM; lúc bắt đầu chỉ còn khoảng 0,9 GB RAM khả dụng,
và đang có các ứng dụng khác chạy. Thời gian là đo trên máy hiện tại, một lượt/biến thể,
không phải kết quả benchmark thống kê. Một số thử nghiệm chẩn đoán có chạy chồng lấn.
Không kết luận hệ số tăng tốc sẽ giữ nguyên trên máy khác hoặc mọi snapshot.

## Kết quả chạy trực tiếp

| Thử nghiệm | Giới hạn thời gian solver | Thời gian gọi solver | Kết quả |
|---|---|---:|---|
| Greedy nguyên bản | Không | 0,441 giây | FEASIBLE, cost 20.270, đủ 1.193 lượt, 0 xung đột |
| SA nguyên bản, 1.000 vòng | Không | 160,941 giây | FEASIBLE, cost 20.240, đủ 1.193 lượt, 0 xung đột |
| SA thử cache cửa sổ thời gian, 1.000 vòng | Không | 53,180 giây | FEASIBLE, cost 20.240; toàn bộ assignments giống hệt SA nguyên bản |
| SA nguyên bản, dừng theo ngân sách | 5 giây | 5,133 giây; gồm kiểm tra thêm là 5,155 giây | Có nghiệm hợp lệ, nhưng đã vượt mốc supervisor 5,10 giây |
| CP-SAT nguyên bản | Không | Quan sát 341,412 giây | Chưa ghi nhận incumbent; chủ động dừng tiến trình chẩn đoán |
| Hybrid nguyên bản | Không | Quan sát 791,991 giây | Vẫn ở CP stage, chưa ghi nhận incumbent; chủ động dừng tiến trình chẩn đoán |
| CP-SAT + cache + Greedy complete hints | 60 giây | 65,613 giây; gồm kiểm tra thêm là 65,618 giây | FEASIBLE, cost 20.270, đủ 1.193 lượt, 0 xung đột; chưa cải thiện Greedy, gap khoảng 99,31% |

SA trước/sau cache cùng 722 accepted moves và 1.001 trace entries. Tối ưu thử nghiệm
nhanh khoảng 3,03 lần, giảm 66,96% thời gian ở lượt đo này; không bỏ bước kiểm chứng
và không giảm số vòng. Caching chỉ được bật trong tiến trình chẩn đoán riêng,
**chưa áp dụng vào code sản phẩm**.

Các dòng quan sát không có time cap trong solver. Việc chủ động dừng là kết thúc
thử nghiệm thủ công, **không phải solver chứng minh vô nghiệm** và không phải thời
gian hội tụ. Cả hai log ghi `max_time_in_seconds: inf`. Hybrid chưa chuyển sang SA
trong thời gian quan sát. Không có tiến trình chẩn đoán nào được để chạy tiếp.

Thử nghiệm complete hints thay đổi initializer và bật cache, nên không coi là
baseline CP-SAT thuần. Log xác nhận hint đầy đủ và khả thi ngay tại presolve;
solver cuối cùng vẫn giữ nguyên chi phí của Greedy. Nghiệm là hợp lệ nhưng lượt
này **không đáp ứng ngân sách end-to-end 60 giây**. Warm-start chưa giải quyết việc
chứng minh tối ưu hoặc trả kết quả đúng hạn. Số liệu gọn và SHA-256 các tệp bằng
chứng được lưu tại [algorithm_timeout_measurements.json](algorithm_timeout_measurements.json).

## Nguyên nhân đã xác định trong mã nguồn

1. **Ngân sách solver và hard watchdog không chừa thời gian trả nghiệm.**
   `web_dashboard/experiments.py::solve_case` cấp toàn bộ budget cho tìm kiếm,
   sau đó tiếp tục đánh giá và serialize. `experiment_worker.py::supervised_case`
   giết worker khi vượt `budget + 0.1`, và loại cả output đã có nếu runtime vượt
   mức này. SA chỉ kiểm tra deadline ở đầu mỗi vòng; một vòng, repair và kiểm chứng
   cuối có thể vượt phần dư 0,1 giây. Vì vậy timeout trong UI không chứng minh thuật
   toán chưa từng có nghiệm hợp lệ. Tăng 35 lên 120 không sửa xung đột hai deadline.

2. **SA tính và kiểm tra lại dữ liệu bất biến quá nhiều.**
   Profile riêng 30 vòng có 30.081.071 lời gọi, 2.265.465 lần lấy `Flight.time_window`,
   121 lần `SAState.is_feasible` và 124 lần gọi independent verifier.
   `Flight.time_window` tạo lại `FlightTimeWindow` ở mỗi truy cập. Nhánh move/swap,
   repair, generate_neighbor và vòng annealer nhiều lần xác minh toàn bộ lịch.
   Profile có overhead đo đạc, chỉ dùng để xác định điểm nóng; không lấy 16 giây của
   lượt profile để ngoại suy thời gian 1.000 vòng.

3. **CP-SAT có mô hình lớn và tìm nghiệm từ đầu.**
   1.193 × 180 = **214.740 biến Bool + 214.740 optional intervals**, 180 NoOverlap,
   1.193 ràng buộc chọn đúng một cổng. Log còn ghi hơn 5,1 triệu binary clauses
   phát sinh trong probing. Nhu cầu đỉnh 178/180 khiến bài toán khá chật.
   Trang so sánh ép 1 worker và tắt warm-start, trong khi snapshot pipeline lưu
   4 workers và warm-start bật. Đây là lựa chọn benchmark hiện tại, không phải
   cùng chế độ thực thi với pipeline. Bản thân run pipeline này cũng có
   `raw_solver_status=UNKNOWN` và `actual_solver=Deterministic Greedy (CP-SAT fallback)`;
   kết quả pipeline khả thi không chứng minh CP-SAT đã giải nhanh.

4. **Hybrid kế thừa chi phí CP-SAT, rồi vẫn có thể bị mất nghiệm ở bước cuối.**
   CP dùng `time_limit_seconds = total * cp_ratio`, nhưng `cp_config` giữ nguyên
   `total_wall_clock_budget_seconds` của cả Hybrid. Vì vậy CP build + search có
   thể vượt tỷ lệ stage dự kiến. Sau CP timeout, Hybrid còn chạy Greedy fallback,
   kiểm chứng incumbent, SA và kiểm chứng cuối; deadline ngoài chỉ cho dư 0,1 giây.
   Khi bỏ toàn bộ giới hạn, Hybrid cũng không có mốc chuyển stage từ CP sang SA:
   stage 1 có thể tiếp tục tìm/chứng minh tối ưu rất lâu.

## Hướng xử lý theo thứ tự

1. **Sửa giao thức deadline và giữ incumbent hợp lệ trước.** Tách thời gian
   deserialize/build/search/verify/export; cấp solver một soft deadline sớm hơn
   hard deadline. Chừa thời gian dựa trên overhead đo thực tế và cỡ dữ liệu,
   không dùng cứng 0,1 giây. Lưu incumbent nguyên tử trong lúc giải; khi hết thời
   gian, xuất incumbent đã kiểm chứng với trạng thái FEASIBLE và termination
   TIME_LIMIT. Chỉ ghi TIMEOUT_NO_SOLUTION khi thật sự không có incumbent hợp lệ.
   Tách `solution_feasible`, `termination_reason` và `budget_compliant`: có nghiệm
   hợp lệ nhưng quá giờ không được tự tính thành lượt đạt ngân sách trong benchmark.
   Nếu chỉ còn initializer Greedy mà chưa có CP incumbent đã được solver xác nhận,
   phải ghi rõ `INITIALIZER_ONLY` hoặc `GREEDY_FALLBACK`, không gán là CP-SAT thuần.
   Không lấy nghiệm từ lượt khác, không chấp nhận output quá budget âm thầm.

2. **Áp dụng cache cửa sổ thời gian cho Flight bất biến.** Đây là phương án đã
   có thử nghiệm cho kết quả giống hệt. Khi dùng `dataclasses.replace` để tạo
   Flight mới trong Monte Carlo, instance mới phải có cache mới. Sau đó mới tối ưu
   kiểm tra move/swap theo cổng bị thay đổi và delta objective, vẫn giữ independent
   verifier ở đầu/cuối, và test đối chiếu đầy đủ cho repair, buffer, pooled capacity.

3. **Tách chế độ tương tác và benchmark có thể tái lập.** Trong chế độ tương tác,
   dùng một Greedy incumbent đã kiểm chứng cho CP-SAT/Hybrid, hint đầy đủ cả biến
   0 và 1, xuất liên tục nghiệm tốt nhất; cân nhắc 4 workers nếu đủ RAM. Nếu thay
   initializer hay số luồng trong nghiên cứu, phải tạo cấu hình/nhãn thí nghiệm mới,
   tính cả chi phí initializer, giữ nguyên snapshot/objective/seed, không đổi tên
   thành baseline CP-SAT thuần hoặc sửa lịch sử cũ. Tăng workers có thể tốn thêm RAM
   và làm giảm tính tái lập theo thời gian thực.

4. **Chặn stage CP của Hybrid theo phần ngân sách thật.** Stage budget phải bao
   gồm dựng mô hình; giữ thời gian cho fallback và SA. Trong chế độ không giới hạn
   toàn lượt, vẫn cần quy tắc chuyển stage rõ ràng như dừng CP khi đạt gap hoặc có
   incumbent, nếu muốn SA thực sự được chạy; quy tắc đó phải được công bố.

5. **Giảm mô hình bằng biến thể được kiểm chứng.** Đo mô hình gate-index integer
   cho các khoảng thời gian cố định; tận dụng nhóm cổng/bãi xa tương đương và các
   ràng buộc tổng sức chứa để tăng bound. Đối chiếu tính khả thi/chi phí với mô
   hình hiện tại trên ca nhỏ có nghiệm tối ưu. Không tự giới hạn top-K cổng nếu
   chưa chấp nhận đánh đổi vì có thể loại nghiệm hợp lệ hoặc tối ưu. Với benchmark
   phục vụ đề tài, nên có dải 100–300 lượt và full-day 1.193 lượt riêng để đánh giá
   độ mở rộng, không giảm dữ liệu rồi báo là cùng một bài toán.

Không khuyến nghị bỏ giới hạn thời gian mặc định trên dashboard: thao tác đó chỉ
làm tác vụ chạy lâu hơn, không giải quyết kiểm chứng lặp hay quy mô mô hình.

## Chạy lại bằng dòng lệnh

Script [diagnose_dashboard_comparison.py](../../scripts/diagnose_dashboard_comparison.py)
không mở ứng dụng; đọc snapshot và ghi kết quả vào đường dẫn chỉ định. Không truyền
`--budget` nghĩa là time limit của solver là vô hạn (`inf`), và bỏ watchdog dashboard.
Cấu hình cho phép `inf` chỉ tồn tại trong script, không thay validation của ứng dụng.
Thêm `--budget 120` để đo cách solver trả nghiệm có giới hạn. Thời gian vẫn tính cả
xử lý nội bộ solver; lệnh không qua HTTP hay supervisor của trang 4.

```powershell
.\.venv\Scripts\python.exe -u -X utf8 scripts/diagnose_dashboard_comparison.py artifacts/web_dashboard/runs/4603faa63a244eea995410e9575c8574/snapshot.json --algorithm sa --output artifacts/dashboard_runtime/timeout_diagnosis/sa_repeat.json
```

Thay `sa` bằng `cpsat`, `hybrid` hoặc `greedy`. Snapshot trên là runtime cục bộ,
không được đóng gói cùng Git; trên máy khác cần dùng snapshot của run đã hoàn tất.
`--cache-windows` bật prototype caching riêng cho tiến trình đó; thêm
`--warm-start --complete-hints` để thử Greedy hint đầy đủ. `--profile` ghi profile
và `--log-search` in tiến độ CP-SAT.

Bằng chứng cục bộ nằm ở `artifacts/dashboard_runtime/timeout_diagnosis/`: JSON kết
quả, profile, log CP-SAT và lịch sử benchmark trích xuất chỉ đọc. Không ghi đè
kết quả chính thức MC500/G12C hoặc dữ liệu thí nghiệm cũ của dashboard.

Tham chiếu OR-Tools: [hướng dẫn logging, workers và trạng thái solver](https://github.com/google/or-tools/blob/stable/ortools/sat/docs/troubleshooting.md),
[định nghĩa tham số max_time_in_seconds mặc định vô hạn](https://github.com/google/or-tools/blob/stable/ortools/sat/sat_parameters.proto).


## Kiểm tra công cụ chẩn đoán

- 4 tests về cấu hình chẩn đoán và validation đã đạt. Validation ứng dụng vẫn từ
  chối ngân sách vô hạn; không thay chế độ mặc định của dashboard.
- Smoke test offline với snapshot 7 lượt: Hybrid không giới hạn hoàn tất và CP-SAT
  complete hints cho nghiệm tối ưu, đều được common evaluator xác nhận.
- Trên snapshot 1.193 lượt, đã đối chiếu toàn bộ assignments của SA trước/sau cache
  bằng giá trị, không chỉ so sánh chi phí hoặc số lượng.
- SHA-256 snapshot trước/sau các lượt hoàn thành giữ nguyên. Không mở server mới,
  không ghi database thí nghiệm và không hủy tiến trình do người dùng khởi động.

Báo cáo này đưa ra hướng khắc phục và prototype đã đo được; chưa áp dụng các thay
đổi deadline, cache hay initializer vào ứng dụng đang chạy.
