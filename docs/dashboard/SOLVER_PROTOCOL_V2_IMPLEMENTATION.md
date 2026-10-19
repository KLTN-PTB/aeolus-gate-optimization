# Nghiệm thu sửa timeout trang so sánh thuật toán

Ngày triển khai: 19/10/2026. Giao thức solver v2, phân tích v3. Bản này triển khai
hướng xử lý đã chốt trong [báo cáo chẩn đoán](ALGORITHM_TIMEOUT_DIAGNOSIS.md).

## Thay đổi đã triển khai

- Chọn độc lập cấu hình `optimized` hoặc `baseline`; mặc định optimized, một CPU
  worker, warm-start đầy đủ 0/1 cho CP-SAT. Baseline giữ CP-SAT tìm từ đầu.
- Một deadline chung cho mỗi lượt, có deadline mềm để dành thời gian kiểm chứng
  và ghi file; watchdog dừng worker theo ngân sách thật. Không dùng grace 0,1 giây.
- CP-SAT có callback, deadline trong dựng mô hình và yêu cầu StopSearch. Hybrid
  cấp nửa thời gian còn lại cho cả dựng/giải CP, sau đó chạy SA với phần còn lại.
- Checkpoint nghiệm được kiểm chứng và ghi nguyên tử. Khi worker lỗi hoặc bị hủy
  vì quá giờ, kiểm tra lại checkpoint trước khi công bố. Không mất mọi nghiệm chỉ
  vì tiến trình kết thúc muộn. Cancel giữ các lượt hoàn tất; lượt dở chạy lại từ
  đầu và không nhận miễn phí nghiệm từ lần thử trước.
- `Flight.time_window` cache theo instance bất biến; `replace` tạo cache mới cho
  từng kịch bản. Không thay move/swap, repair, objective hoặc giảm vòng SA.
- Phân biệt nguồn solver, Greedy initializer và fallback. Lịch initializer được
  gắn nhãn Greedy khi dùng cho Monte Carlo, không biến thành CP-SAT thuần.
- Giao diện, Gantt, thống kê, CI ghép cặp và export dùng cùng điều kiện chi phí:
  nghiệm solver hợp lệ và đúng ngân sách. Mọi timeout/lỗi vẫn ở mẫu số. Fixed-plan
  vẫn giữ chi phí rủi ro khi lịch xung đột. Có cả tỷ lệ có nghiệm và tỷ lệ solver
  có nghiệm đúng hạn; các số này có thể khác nhau.
- Giữ nguyên export và cách đọc dữ liệu giao thức cũ; chặn resume trộn giao thức.
  Không thay bảng SQLite, checkpoint ML hoặc các kết quả nghiên cứu chính thức.

## Hợp đồng và cách đọc kết quả

POST tạo thí nghiệm nhận thêm `solver_profile` (`optimized` mặc định, `baseline`
để chạy CP-SAT thuần). Phiên bản thực thi do server gán, không nhận từ client.
Ngân sách vẫn từ 1 đến 120 giây, gồm khởi tạo, dựng, giải, kiểm chứng và lưu kết
quả lượt; không gồm khởi động interpreter hoặc ZIP tổng hợp.

Kết quả thêm `solution_source`, `termination_reason`, `budget_compliant`,
`time_to_verified_incumbent_sec`, `timings` và phiên bản/profile. `feasible` chỉ
xác nhận tính hợp lệ của lịch. `FEASIBLE + TIME_LIMIT + budget_compliant=true`
là trạng thái bình thường khi solver dừng ở deadline mềm và trả nghiệm đúng hạn;
không phải solver chứng minh tối ưu. Nghiệm trả muộn vẫn được xem nhưng không
tham gia thống kê chi phí đúng hạn. Lỗi worker được ghi riêng với TIME_LIMIT.

Runtime không bị gán bằng ngân sách. Nếu worker dừng giữa ghi output và ghi
completion marker, thời gian toàn lượt không xác định: giữ giá trị đã đo với
`timing_complete=false`, không công nhận đạt ngân sách và không tự tạo thêm thời
gian. Các số thời gian giai đoạn là chẩn đoán: thời gian giải có gồm callback,
kiểm chứng/lưu trong callback được báo riêng; không cộng chúng như các pha rời nhau.

## Kết quả trên dữ liệu người dùng

Snapshot `8954188c9e38ac952268c61ac751e379f05fe29afd251616c383921be9e72c2f`:
1.193 lượt chiếm dụng, 150 cổng tiếp xúc + 30 bãi xa hữu hạn, đỉnh 178. Seed
202601, optimized, một worker, ngân sách 120 giây cho từng thuật toán.

| Thuật toán | Thời gian toàn lượt | Chi phí | Kết quả |
|---|---:|---:|---|
| Greedy | 0,373 giây | 20.270 | FEASIBLE, đúng hạn |
| CP-SAT warm-start | 108,415 giây | 20.270 | FEASIBLE, đúng hạn, dừng tìm kiếm theo giới hạn |
| SA | 45,246 giây | 20.240 | FEASIBLE, đúng hạn, đủ 1.000 vòng |
| Hybrid | 101,382 giây | 20.040 | FEASIBLE, đúng hạn |

Cả bốn phân đủ 1.193 lượt và không có xung đột, nguồn nghiệm SOLVER. Không có
thuật toán nào tự nhận chứng minh tối ưu ở lượt đo này. Lượt xác nhận metadata
Hybrid riêng đạt 101,317 giây, cùng chi phí 20.040 và có thời gian dựng mô hình
6,584 giây. Đây là một seed trên máy hiện tại, không thay benchmark khoa học.

Ba lượt SA không giới hạn, cùng seed và đủ 1.000 vòng, đều có **toàn bộ assignments
giống hệt** kết quả SA trước tối ưu. Thời gian: 48,259 / 45,253 / 47,776 giây;
trung vị **47,776 giây**, so với 160,941 giây của phép đo chẩn đoán ban đầu.
Các điều kiện tải máy khác nhau, nên không suy rộng hệ số tăng tốc cho mọi ca.

Số liệu và SHA-256 nguồn được lưu ở
[solver_protocol_v2_measurements.json](solver_protocol_v2_measurements.json).
Kết quả thô cục bộ: `artifacts/dashboard_runtime/solver_protocol_v2_acceptance_20261019/`,
`artifacts/dashboard_runtime/solver_protocol_v2_hybrid_timing_confirmation/` và
`artifacts/dashboard_runtime/sa_protocol_v2_parity_1.json` đến `_3.json`.
Snapshot và checkpoint gốc giữ nguyên hash; không cập nhật database dashboard thật.

## Kiểm thử và sử dụng

Kiểm thử gồm deadline trong dựng mô hình, callback/full hints với chỉ số chuyến
không liên tục và ba formulation, cache sau replace, incumbent trả muộn, worker
crash, checkpoint sai hoặc ghi dở, cancel/resume, thống kê không tính nhầm initializer,
Gantt, legacy export giữ nguyên hash và API chặn resume giao thức cũ. Frontend có
kiểm thử chọn baseline và hiển thị lịch khởi tạo quá giờ.

Bản frontend đã build; người dùng cần tự khởi động lại backend và tải lại trình
duyệt, chọn Tối ưu rồi tạo thí nghiệm mới. Lịch sử cũ không được tính lại thành kết
quả mới. Không mở browser/notebook/server trong đợt này; các worker được tạo chỉ
phục vụ kiểm thử CLI và đều được thu hồi. Không commit hoặc push.

Kết quả kiểm tra cuối: **679 tests Python đạt** trong phạm vi web dashboard,
dashboard nghiên cứu, domain, CP-SAT, SA/Hybrid, downstream và native pipeline;
**24 tests đối chiếu đạt**, **15 tests frontend đạt**, TypeScript/Vite production
build đạt. Các kiểm thử Python không được trình bày thành full test suite của
repo. Cảnh báo quan sát được là deprecation từ thư viện, không có lỗi kiểm thử.

Trên Windows, kiểm thử export cần thư mục tạm ngoài workspace nếu VS Code đang
giữ ZIP để lập chỉ mục. Kiểm tra khóa file xác nhận chủ thể giữ file là VS Code;
không đóng ứng dụng hay tiến trình của người dùng để vượt qua kiểm thử.
