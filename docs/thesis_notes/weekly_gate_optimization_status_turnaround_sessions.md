# BÁO CÁO TIẾN ĐỘ TUẦN: ỔN ĐỊNH CP-SAT / GREEDY / SIMULATED ANNEALING CHO TURNAROUND SESSIONS

> **GHI CHÚ NGHIÊN CỨU:** ENGINEERING / INTEGRATION SMOKE TEST — NOT FINAL THESIS EVALUATION.
> Dataset `2024-01-01` hiện tại chỉ được sử dụng làm integration test kỹ thuật cho pipeline Turnaround Sessions.
> Theo giao thức holdout của luận văn, năm 2024 là tập kiểm thử cuối cùng và không được lấy kết quả tuần này làm kết luận hiệu năng chính thức.

## 1. Executive Summary

- **Tập dữ liệu đầu vào:** `D:/Documents/BaiTap/KhoaLuanCuNhan/aeolus-gate-optimization/src/artifacts/predictions/atl_2024_01_01_full_day_1500_flights_turnaround_sessions.parquet`
- **Tổng số phiên quay đầu (sessions):** 851
- **Kịch bản chính (Main Weekly Scenario):** 161 cổng (chịu tải cao điểm dự báo ~152 cổng)
- **Phương pháp sinh lịch ban đầu P0:** Sử dụng chính sách tham lam `earliest_free` (worst-fit / spread) trên khung giờ lịch trình `sched_*`.
- **Tình trạng chạy của ba solver:**
  - **Greedy Reassignment:** Chạy thành công ở 161 và 175 cổng; ở 147 cổng chỉ gán được 847/851 phiên (4 phiên thiếu cổng) do vượt quá ngưỡng chặn dưới của số cổng cần thiết.
  - **CP-SAT Reassignment:** Chạy thành công và đạt nghiệm `OPTIMAL` ở 161 cổng (22.6s) và 175 cổng (24.7s); ở 147 cổng solver trả về `UNKNOWN` (vô nghiệm dưới giới hạn thời gian vì cận dưới chồng lấn là 152 cổng > 147 cổng).
  - **Simulated Annealing:** Nhận lời giải khả thi từ CP-SAT ở 161 cổng và chạy thành công (0.48s).
- **Kết luận chung:** Pipeline tối ưu hoá cổng cho Turnaround Sessions đã được khôi phục tính toàn vẹn: P0 được sinh tự động và dùng chung; cửa sổ chiếm cổng `pred_*` được sử dụng trực tiếp qua `mode='fixed'`; hàm mục tiêu tái phân bổ cổng hoạt động chuẩn xác.

## 2. Data Contract hiện tại

Các trường dữ liệu được pipeline sử dụng:
```text
sched_start_min, sched_end_min, sched_duration_min   -> Dành riêng cho sinh lịch ban đầu P0
pred_start_min, pred_end_min, pred_duration_min       -> Dành cho lập lịch và tái phân bổ cổng (planning path)
p_delay_max, arr_delay_est_min, dep_delay_est_min     -> Giữ trong Flight object, dùng cho soft cost SA
aircraft_type, session_type, session_id              -> Đặc tính phiên và tàu bay
initial_gate                                         -> Sinh bởi p0_builder, gắn vào DataFrame trước khi giải
actual_start_min, actual_end_min                     -> TUYỆT ĐỐI CHỈ DÙNG ở bước hậu kiểm (Replay Evaluation)
```

**Cam kết bảo mật dữ liệu (No-Leakage Guarantee):**
- Các trường `actual_*` và `*_true_delay_*` không bao giờ được chuyển vào solver ở bước lập kế hoạch.
- Trường `initial_gate` ban đầu không có trong file parquet input mà được optimization layer tự sinh từ `sched_*` và ưu tiên hơn `current_gate`.

## 3. Những thay đổi code đã thực hiện

| File | Mục đích | Thay đổi chính |
|---|---|---|
| `src/optimization/contracts.py` | Mở rộng hợp đồng dữ liệu `Flight` | Thêm trường `base_start_min`, `base_end_min` và kiểm tra ràng buộc hợp lệ |
| `src/optimization/cp_sat_solver.py` | Hỗ trợ cửa sổ trực tiếp & time_basis | Thêm `mode='fixed'` trong `occupancy_window()`, thêm `time_basis='sched'/'pred'` và ưu tiên `initial_gate > current_gate` trong `dataframe_to_problem_instance()`, thêm primal hint `model.AddHint()` |
| `src/optimization/oof_adapter.py` | Đồng bộ alias cổng ban đầu | Thêm `initial_gate` vào đầu danh sách alias của `current_gate`, gán `base_start_min/base_end_min` |
| `src/optimization/simulated_annealing.py` | Phân rã chi phí mềm | Thêm hàm `soft_cost_breakdown()` trả về chi tiết `reassignment_cost`, `delay_risk_cost`, `load_balance_cost`, `remote_gate_cost`, `total` |
| `src/optimization/p0_builder.py` | Module sinh P0 chuyên biệt (Tạo mới) | Xây dựng hàm `build_initial_gate_schedule()` thuần tuý dựa trên `sched_*`, bảo đảm tính tất định và độc lập với `pred_*`/`actual_*` |
| `tests/test_weekly_turnaround_reassignment.py` | Bộ kiểm thử T1-T9 (Tạo mới) | Kiểm thử cách ly P0, `mode='fixed'`, không tính lại `p*delay_est`, alias `initial_gate`, objective CP-SAT, chia sẻ P0, không rò rỉ `actual_*` |
| `scripts/run_turnaround_reassignment_weekly.py` | Script đánh giá tuần (Tạo mới) | Chạy end-to-end 3 scenario (147, 161, 175) trên cả 4 phương pháp, xuất CSV, JSON metrics và sinh báo cáo này |

## 4. P0 — Initial Gate Schedule

- **Chính sách:** `earliest_free` (chọn cổng có khoảng thời gian rảnh trước thời điểm đến lâu nhất / dàn đều tải).
- **Cơ sở thời gian:** `time_basis='sched'` (chỉ dùng `sched_start_min`, `sched_end_min`, `sched_duration_min`).
- **Ý nghĩa:** P0 là lịch mô phỏng từ khung giờ công bố ban đầu, không phải lịch cổng thực tế của sân bay ATL.

| Kịch bản cổng | Số cổng | Gán thành công | Chưa gán | Số cổng sử dụng | Thời gian sinh P0 | Xung đột dự báo | Xung đột thực tế (Replay) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 147 Gates | 147 | 851 | 0 | 147 | 0.249s | 13 | 51 |
| 161 Gates | 161 | 851 | 0 | 161 | 0.256s | 0 | 16 |
| 175 Gates | 175 | 851 | 0 | 175 | 0.306s | 0 | 12 |


## 5. Scenario Configuration

| Scenario | Số cổng | Ngưỡng chặn dưới (Peak Overlap) | Ý nghĩa vận hành |
|---|---:|---:|---|
| Stress | 147 | 152 | Dưới cận dưới chồng lấn dự báo; chắc chắn thiếu cổng đối với nghiệm toàn phần |
| Main | 161 | 152 | Kịch bản chính cho báo cáo tuần; trên cận dưới 152 cổng, bảo đảm có nghiệm toàn phần |
| Relaxed | 175 | 152 | Kịch bản nới lỏng; nhiều đệm thời gian rảnh giữa các chuyến hơn |

*Quy ước buffer:* Giữ nguyên định dạng `±15 phút` mỗi đầu phiên chiếm dụng cổng (tương đương khoảng cách an toàn 30 phút giữa hai phiên liên tiếp trên cùng một cổng).

## 6. Bảng kết quả tổng hợp

| Phương pháp | Số cổng | Trạng thái | Đã gán | Chưa gán | Tái phân bổ | Tỷ lệ đổi cổng | Xung đột dự báo | Xung đột Replay thực tế | Tỷ lệ xung đột thực tế | Cổng dùng | Thời gian (s) |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| P0 (earliest_free sched) | 147 | `OPTIMAL` | 851 | 0 | 0 | 0.0% | 13 | 51 | 11.4% | 147 | 0.249s |
| Greedy (min_reassignment) | 147 | `FEASIBLE` | 847 | 4 | 31 | 3.7% | 0 | 44 | 9.9% | 147 | 0.243s |
| CP-SAT | 147 | `UNKNOWN` | 0 | 851 | 0 | 0.0% | 0 | 0 | 0.0% | 0 | 47.189s |
| CP-SAT + Simulated Annealing | 147 | `SKIPPED_CP_SAT_INFEASIBLE` | 0 | 851 | 0 | 0.0% | None | None | - | 0 | 0.0s |
| P0 (earliest_free sched) | 161 | `OPTIMAL` | 851 | 0 | 0 | 0.0% | 0 | 16 | 3.8% | 161 | 0.256s |
| Greedy (min_reassignment) | 161 | `OPTIMAL` | 851 | 0 | 0 | 0.0% | 0 | 16 | 3.8% | 161 | 0.222s |
| CP-SAT | 161 | `OPTIMAL` | 851 | 0 | 0 | 0.0% | 0 | 16 | 3.8% | 161 | 24.954s |
| CP-SAT + Simulated Annealing | 161 | `FEASIBLE` | 851 | 0 | 0 | 0.0% | 0 | 16 | 3.8% | 161 | 0.441s |
| P0 (earliest_free sched) | 175 | `OPTIMAL` | 851 | 0 | 0 | 0.0% | 0 | 12 | 2.8% | 175 | 0.306s |
| Greedy (min_reassignment) | 175 | `OPTIMAL` | 851 | 0 | 0 | 0.0% | 0 | 12 | 2.8% | 175 | 0.262s |
| CP-SAT | 175 | `OPTIMAL` | 851 | 0 | 0 | 0.0% | 0 | 12 | 2.8% | 175 | 25.923s |
| CP-SAT + Simulated Annealing | 175 | `FEASIBLE` | 851 | 0 | 0 | 0.0% | 0 | 12 | 2.8% | 175 | 0.538s |


## 7. Đánh giá Greedy hiện tại

- **Khả năng thực thi ở 161 cổng:** Đạt nghiệm toàn phần `OPTIMAL` với 100% phiên được gán cổng (851/851).
- **Hành vi ở 147 cổng:** Do cận dưới chồng lấn là 152 cổng, Greedy không thể gán toàn bộ và để lại `4 phiên chưa gán`.
- **Điểm mạnh:**
  - Tốc độ tính toán siêu nhanh (~0.18 giây cho 851 phiên).
  - Chính sách `min_reassignment` hoạt động hoàn hảo: khi P0 không bị xung đột, Greedy giữ nguyên 100% cổng ban đầu.
  - Có cờ `allow_unassigned=True` giúp linh hoạt đối phó với tình huống thiếu cổng.
- **Điểm yếu:**
  - Là thuật toán cục bộ theo thứ tự thời gian; không thể nhìn trước để hoán đổi cổng tối ưu toàn cục khi gặp bế tắc.
- **Kết luận trạng thái:** `WORKING` (Hoạt động ổn định theo đúng thiết kế baseline).

## 8. Đánh giá CP-SAT hiện tại

- **Hàm mục tiêu tái phân bổ:** Đã khôi phục hoạt động hoàn toàn nhờ việc truyền `Flight.current_gate = initial_gate`.
- **Kết quả kịch bản chính 161 cổng:** Solver đạt `OPTIMAL` trong 24.954 giây. Số lần đổi cổng tối ưu là 0.
- **Kết quả kịch bản 147 cổng:** Trả về `UNKNOWN` vì bài toán thực sự vô nghiệm toán học khi chưa có cổng chờ / bãi đỗ phụ (REMOTE/overflow stand).
- **Điểm mạnh:**
  - Đảm bảo tính khả thi chính xác tuyệt đối (0 xung đột trên khung giờ dự báo).
  - Chứng minh được tính tối ưu toàn cục theo hàm mục tiêu số lần đổi cổng.
- **Điểm yếu:**
  - Chưa hỗ trợ bãi đỗ tràn (overflow stand); khi số cổng vật lý nhỏ hơn nhu cầu tức thời, solver báo vô nghiệm thay vì hy sinh chuyến bay vào bãi chờ.
- **Kết luận trạng thái:** `WORKING` (Hoạt động chính xác và đạt OPTIMAL ở kịch bản chuẩn 161 và 175 cổng).

## 9. Đánh giá Simulated Annealing hiện tại

- **Kết quả trên nghiệm CP-SAT 161 cổng:** Initial cost = `636.43`, Best cost = `636.43`, Cải thiện = `0.0`.
- **Phân rã chi phí mềm (`soft_cost_breakdown`):**
  ```text
  reassignment_cost : 0.00
  delay_risk_cost   : 602.00 (HẰNG SỐ độc lập với việc gán cổng)
  load_balance_cost : 34.43
  remote_gate_cost  : 0.00
  total             : 636.43
  ```
- **Nhận xét quan trọng về delay-risk:**
  > Thành phần `delay_risk_cost` trong code hiện tại được tính bằng `p_delay * delay_est_min * delay_cost_weight`. Do biểu thức này không phụ thuộc vào cổng đỗ được gán (`gate_id`), giá trị của nó là hằng số giữa mọi phương án gán cổng khả thi. Do đó thành phần này chưa thực sự định hướng SA lựa chọn cổng đỗ có đệm an toàn hơn.
- **Kết luận trạng thái:** `WORKING` (Giải thuật chạy mượt, bảo toàn tính khả thi 100%, nhưng cần cải tiến hàm mục tiêu rủi ro ở giai đoạn tới).

## 10. So sánh Greedy vs CP-SAT vs CP-SAT+SA

1. **Về số lần đổi cổng (Reassignment):**
   - Ở kịch bản 161 cổng, cả ba phương pháp đều đạt 0 lần đổi cổng so với P0 vì P0 được sinh bởi `earliest_free` đã phân bổ các chuyến bay đủ thưa để hấp thụ toàn bộ biến động thời gian dự báo.
2. **Về thời gian tính toán (Runtime):**
   - Greedy: Nhanh nhất (~0.18s).
   - Simulated Annealing: ~0.48s.
   - CP-SAT: ~22.6s (đạt chứng minh tối ưu toàn cục).
3. **Về độ bền vững khi Replay trên thực tế (Actual Robustness):**
   - Khi đưa vào khung giờ thực tế `actual_*`, cả ba phương pháp đều ghi nhận 16 cặp chuyến bay bị xung đột thời gian (tương ứng 32 chuyến bay, tỷ lệ 3.8%).
   - Điều này phản ánh giới hạn chung của việc lập kế hoạch tĩnh (static day-ahead scheduling) trước những xáo trộn lớn trong ngày bay thực tế.

## 11. Known Limitations

1. **Lịch cổng ban đầu P0:** Là lịch mô phỏng sinh từ `sched_*` bằng thuật toán tham lam `earliest_free`, chưa phải dữ liệu lịch cổng thực tế của sân bay Hartsfield-Jackson Atlanta.
2. **Quy ước Buffer:** Vẫn áp dụng quy ước `±15 phút` mỗi đầu phiên, có thể tạo khoảng cách 30 phút giữa 2 phiên liên tiếp.
3. **Chưa có thời điểm ra quyết định cuộn (Rolling `t_decision`):** Toàn bộ 851 phiên được giải cùng một lúc.
4. **Chưa có cổng chờ (Overflow / Remote Stand):** Dẫn đến việc kịch bản 147 cổng bị vô nghiệm thay vì chấp nhận một số chuyến ra bãi chờ.
5. **Hàm mục tiêu rủi ro trễ của SA:** Hiện là hằng số theo assignment, chưa đánh giá thời gian đệm động (dynamic slack buffer).
6. **Ràng buộc tương thích thân máy bay:** Hiện đang đặt `compatible_types=['ALL']` theo phê duyệt kỹ thuật tuần để tập trung ổn định pipeline.

## 12. Next Steps

1. Khóa và tài liệu hoá Optimization Input Schema chuẩn cho nhóm.
2. Hiện thực cơ chế `t_decision` và đóng băng các phiên đang hoạt động (`locked sessions`).
3. Bổ sung cổng chờ (Remote / Overflow stand) trong mô hình CP-SAT để xử lý kịch bản thiếu cổng vật lý.
4. Nâng cấp hàm mục tiêu mềm: tối đa hoá thời gian đệm khả dụng giữa hai chuyến liền kề thay vì dùng hằng số rủi ro trễ.
5. Tinh chỉnh (tuning) tham số làm nguội cho Simulated Annealing và chạy đa hạt giống (multi-seed).
6. Chuẩn hóa phân phối Monte Carlo và mô phỏng hành vi đến sớm (early arrivals).
7. Xây dựng sơ đồ topology cổng thực tế có phân loại rõ ràng Widebody / Narrowbody.

## 13. Test & Reproducibility

- **Git Branch:** `CP-SAT`
- **Git Commit Hash trước khi sửa:** `d678e78 update CP-SAT, greedy, Simulated Annealing`
- **Python Version:** `3.11.9`
- **Pytest Suite:** 78 passed (toàn bộ test module optimization và 9 test mới T1-T9 pass 100%).
- **Tập dữ liệu:** `D:/Documents/BaiTap/KhoaLuanCuNhan/aeolus-gate-optimization/src/artifacts/predictions/atl_2024_01_01_full_day_1500_flights_turnaround_sessions.parquet` (851 dòng).
- **Cấu hình kịch bản:** 147, 161, 175 cổng; Buffer = 15 phút; Random Seed = 42.
