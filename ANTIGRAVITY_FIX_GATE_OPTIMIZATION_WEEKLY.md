# YÊU CẦU ANTIGRAVITY — ỔN ĐỊNH CP-SAT / GREEDY / SIMULATED ANNEALING CHO TURNAROUND SESSIONS

## 0. Mục tiêu của task

Repo: `KLTN-PTB/aeolus-gate-optimization`  
Branch làm việc: `CP-SAT`

Dataset cần chạy được ở giai đoạn hiện tại:

```text
src/artifacts/predictions/atl_2024_01_01_full_day_1500_flights_turnaround_sessions.parquet
```

Dataset này hiện là artifact mới nhất do pipeline ML của nhóm sinh ra. Nó có các cửa sổ:

```text
sched_start_min
sched_end_min
sched_duration_min

pred_start_min
pred_end_min
pred_duration_min

actual_start_min
actual_end_min
```

và các trường dự báo/rủi ro như:

```text
p_delay_max
arr_delay_est_min
dep_delay_est_min
aircraft_type
session_type
session_id
```

Nhưng dataset **không có `initial_gate/current_gate`** do bước export đã bỏ quên trường này.

### Mục tiêu ngắn hạn

Không cố hoàn thiện toàn bộ mô hình nghiên cứu ở task này.

Task này chỉ nhằm:

1. Làm cho **Greedy, CP-SAT, CP-SAT + Simulated Annealing** chạy ổn định trên dataset Turnaround Sessions mới nhất.
2. Tự sinh một **lịch cổng ban đầu P0 (`initial_gate`)** từ `sched_*`.
3. Dùng **cùng P0** cho Greedy, CP-SAT và CP-SAT+SA.
4. Khi lập kế hoạch/tái phân bổ, sử dụng trực tiếp cửa sổ `pred_*` của artifact mới; **không tính lại bằng `p × delay_est`**.
5. Chạy benchmark và xuất kết quả.
6. Tạo một file báo cáo Markdown tổng hợp:
   - những gì đã sửa;
   - kết quả Greedy;
   - kết quả CP-SAT;
   - kết quả CP-SAT+SA;
   - đánh giá hiện trạng, điểm mạnh/yếu, các vấn đề chưa giải quyết.

### Không phải mục tiêu của task này

Tạm thời **KHÔNG** triển khai sâu các mục sau:

- rolling `t_decision`;
- khóa phiên đã vào cổng;
- REMOTE/overflow gate;
- viết lại toàn bộ soft objective;
- calibrate Monte Carlo;
- sửa phân phối delay Monte Carlo;
- recourse;
- đổi buffer 15/30 phút;
- tuning SA quy mô lớn 200k iterations;
- thay đổi kiến trúc ML;
- thay đổi các quyết định nghiên cứu LOCKED.

Những mục này chỉ ghi lại trong phần `Known limitations / Next steps` của báo cáo.

---

# 1. Nguyên tắc bắt buộc

## 1.1. Không dùng ground truth để tối ưu

Trong bước:

```text
P0 generation
Greedy reassignment
CP-SAT reassignment
Simulated Annealing
```

**KHÔNG được đọc hoặc sử dụng**:

```text
actual_start_min
actual_end_min
arr_true_delay_min
dep_true_delay_min
actual_delay_min
ARR_DELAY
DEP_DELAY
```

Các trường `actual_*` chỉ được dùng **sau khi solver đã tạo assignment**, ở bước đánh giá/replay.

Nếu code hiện tại có `Flight.actual_delay_min`, không cần refactor lớn trong task này, nhưng tuyệt đối không để solver sử dụng nó trong planning path mới.

---

## 1.2. P0 phải chỉ dùng `sched_*`

Lịch ban đầu P0 phải được tạo từ:

```text
sched_start_min
sched_end_min
sched_duration_min
```

Không được sử dụng:

```text
pred_*
p_delay*
delay_est*
actual_*
```

để chọn P0.

---

## 1.3. Cùng một P0 cho cả ba phương pháp

Trong một scenario cùng số gate:

```text
P0
 ├── Greedy reassignment
 ├── CP-SAT reassignment
 └── CP-SAT -> SA
```

Tuyệt đối không cho mỗi solver tự tạo P0 khác nhau.

---

## 1.4. Giữ backward compatibility

Các API và test legacy đang tồn tại phải tiếp tục chạy nếu không có lý do bắt buộc phải thay đổi.

Không xóa các mode cũ:

```text
expected
worst_case
realized
```

Chỉ bổ sung path mới cho Turnaround Sessions.

---

# 2. Quyết định tạm thời cho báo cáo tuần này

## D1 — Sinh P0

Chọn phương án:

```text
Greedy spread / worst-fit theo sched_*
```

Ưu tiên tái sử dụng policy hiện có:

```python
policy="earliest_free"
```

trong `greedy_baseline.py`, vì policy hiện tại chọn gate đã rảnh lâu nhất và có xu hướng dàn các phiên ra nhiều gate.

Nếu sau khi đọc code thấy `earliest_free` không đúng hành vi "spread" trên dữ liệu thực tế, hãy tạo policy riêng:

```text
p0_spread
```

với yêu cầu:

- deterministic;
- chỉ dùng scheduled windows;
- ưu tiên gate hợp lệ có thời điểm kết thúc gần nhất trong quá khứ nhỏ nhất / gate đã rảnh lâu nhất;
- không nhìn `pred_*`, probability hay actual;
- không tối ưu reassignment vì P0 chưa có gate cũ.

Không dùng:

```text
first-fit
best-fit
```

làm P0 mặc định.

---

## D2 — Số gate

Chạy ba scenario:

```text
147 gates  -> stress scenario
161 gates  -> MAIN WEEKLY SCENARIO
175 gates  -> relaxed scenario
```

**161 gates là scenario chính** cho báo cáo tuần hiện tại.

Lý do: dữ liệu đã được audit trước đó cho thấy peak overlap của `pred_*` có buffer hiện tại xấp xỉ 151; 147 có thể vô nghiệm khi chưa có overflow gate. Không được coi 147 infeasible là bug nếu lower bound xác nhận điều đó.

Nếu recompute trên artifact local cho ra lower bound khác, ghi số thực tế vào report và giải thích; không được âm thầm thay đổi scenario.

---

## D3 — Buffer

Giữ nguyên semantics hiện tại trong code cho task này.

Nếu hiện code đang dùng:

```text
±15 phút mỗi đầu
```

thì không đổi trong task hiện tại.

Báo cáo phải ghi rõ điều này có thể tương đương khoảng cách 30 phút giữa hai raw sessions và cần được thống nhất sau.

---

## D4 — Aircraft compatibility

Để tránh thêm giả định mới trong báo cáo tuần, **không tự phát minh topology wide/narrow mới** nếu repo chưa có gate map cố định được phê duyệt.

Với benchmark tạm thời, có thể giữ cách tạo gate hiện tại:

```python
compatible_types=["ALL"]
```

để tập trung kiểm tra pipeline reassignment.

Tuy nhiên:

- phải giữ lại `aircraft_type` trong dữ liệu;
- báo cáo phải ghi rõ compatibility wide/narrow hiện chưa được kích hoạt trong benchmark tạm thời nếu thực tế đang dùng `ALL`;
- không được tuyên bố benchmark đã kiểm tra áp lực widebody nếu gate topology vẫn là `ALL`.

Nếu repo đã có một gate topology deterministic, approved, tương thích trực tiếp với `NARROWBODY/WIDEBODY`, có thể dùng nó, nhưng phải ghi rõ nguồn cấu hình trong report.

---

# 3. Vấn đề code hiện tại cần sửa

## 3.1. `current_gate=None` làm objective reassignment của CP-SAT suy biến

Hiện `dataframe_to_problem_instance()` đọc Turnaround Sessions theo kiểu:

```python
cur_gate = row.get("current_gate")
current_gate_str = str(cur_gate) if pd.notna(cur_gate) else None
```

Dataset mới không có field này.

Hệ quả:

```text
Flight.current_gate = None
          ↓
không tạo y_f
          ↓
CP-SAT không còn objective minimize reassignment
```

Greedy `min_reassignment` và SA reassignment cost cũng mất ý nghĩa.

### Yêu cầu sửa

Adapter phải chấp nhận cả:

```text
initial_gate
current_gate
```

Ưu tiên:

```text
initial_gate > current_gate
```

khi cả hai tồn tại.

Trong canonical `Flight` hiện tại có thể tiếp tục dùng:

```python
Flight.current_gate
```

như tên nội bộ để tránh refactor lớn.

Nhưng artifact/output phải dùng tên rõ:

```text
initial_gate
```

---

# 4. Không được tính lại `pred_*` bằng `p × delay_est`

## Vấn đề hiện tại

Dataset mới đã có:

```text
pred_start_min
pred_end_min
pred_duration_min
```

nhưng `occupancy_window(mode="expected")` hiện tính:

```python
eff_delay = flight.p_delay * flight.delay_est_min
```

rồi dịch scheduled time thêm lần nữa.

Đối với pipeline mới, cách này là sai mục đích.

### Yêu cầu

Bổ sung một planning path dùng trực tiếp window đã được artifact tạo.

Khuyến nghị implementation:

### 4.1. Mở rộng `Flight` tối thiểu

Thêm hai field optional, tên có thể tương đương nhưng phải rõ nghĩa:

```python
base_start_min: Optional[int] = None
base_end_min: Optional[int] = None
```

Không bắt buộc đúng tên nếu có thiết kế tốt hơn.

### 4.2. Bổ sung `mode="fixed"` trong `occupancy_window()`

Nếu:

```python
mode == "fixed"
```

và `base_start_min/base_end_min` có giá trị:

```python
start = base_start_min - buffer_time_min
end   = base_end_min   + buffer_time_min
```

sau đó clamp start >= 0 như logic hiện tại.

Trong path `fixed`:

- không dùng `p_delay`;
- không dùng `delay_est_min`;
- không dùng `actual_delay_min`;
- không gọi lại logic `p × delay_est`.

Legacy modes giữ nguyên.

---

# 5. Thêm `time_basis` cho Turnaround Sessions adapter

Trong:

```python
dataframe_to_problem_instance(...)
```

hoặc một adapter chuyên biệt nếu code sạch hơn, hỗ trợ:

```python
time_basis="sched"
time_basis="pred"
```

## `time_basis="sched"`

Với session dataset:

```python
base_start_min = sched_start_min
base_end_min   = sched_end_min
dwell_time_min = sched_duration_min
```

## `time_basis="pred"`

```python
base_start_min = pred_start_min
base_end_min   = pred_end_min
dwell_time_min = pred_duration_min
```

Nếu `pred_duration_min` thiếu nhưng start/end có đủ, có thể tính:

```python
pred_duration = pred_end_min - pred_start_min
```

và ghi warning.

Nếu `pred_start_min` hoặc `pred_end_min` thiếu, **fail clearly** cho Turnaround Sessions thay vì âm thầm chuyển sang `p × delay_est`.

Không được dùng `actual_*` làm fallback.

---

# 6. Tạo module sinh P0

Khuyến nghị tạo:

```text
src/optimization/p0_builder.py
```

hoặc tên tương đương.

API gợi ý:

```python
build_initial_gate_schedule(
    df_sessions,
    num_gates: int,
    buffer_time_min: int = 15,
    policy: str = "earliest_free",
) -> P0Result
```

`P0Result` tối thiểu chứa:

```text
assignment: dict[session_id, gate_id]
status
solve_time_sec
unassigned_count
gates_used
```

Logic:

```text
df sessions
    ↓
dataframe_to_problem_instance(time_basis="sched")
    ↓
greedy_assign(mode="fixed", policy="earliest_free")
    ↓
initial_gate
```

P0 phải deterministic.

Sau đó tạo DataFrame mới:

```python
df_with_p0["initial_gate"] = ...
```

Không ghi đè parquet input gốc.

---

# 7. Xây dựng predicted reassignment instance

Sau khi có P0:

```python
pred_instance = dataframe_to_problem_instance(
    df_with_p0,
    num_gates=...,
    time_basis="pred",
)
```

Trong quá trình chuyển đổi:

```python
Flight.current_gate = row["initial_gate"]
```

Sau đó tất cả solver dùng:

```python
mode="fixed"
```

---

# 8. Greedy reassignment

Chạy:

```python
greedy_assign(
    pred_instance,
    mode="fixed",
    policy="min_reassignment",
    allow_unassigned=True,
)
```

Mục tiêu tạm thời:

1. cố giữ `initial_gate`;
2. nếu conflict thì chọn gate khả thi theo logic Greedy hiện tại;
3. không phá hard constraints trên những session đã assign;
4. nếu không tìm được gate, ghi `unassigned`, không crash toàn benchmark.

Report:

```text
assigned_count
unassigned_count
reassigned_count
reassignment_rate
gates_used
runtime
predicted_conflicts
```

Nếu `unassigned_count > 0`:

```text
feasible_full_assignment = False
```

Không được gọi kết quả là fully feasible.

---

# 9. CP-SAT reassignment

Chạy CP-SAT trên cùng `pred_instance`.

Vì `Flight.current_gate` đã có P0, objective hiện tại:

```text
minimize Σ y_f
```

phải có ý nghĩa trở lại.

Yêu cầu:

- không thay đổi objective lớn trong task này;
- giữ `AddNoOverlap`;
- giữ exactly-one;
- dùng `mode="fixed"`;
- nếu 147 gates infeasible, report `INFEASIBLE`, không coi là crash;
- 161 là main scenario;
- 175 relaxed scenario.

Thu thập:

```text
status
wall_time
reassigned_count
reassignment_rate
gates_used
predicted_conflicts
```

Nếu status `OPTIMAL`, diễn giải chính xác:

> OPTIMAL đối với objective hiện tại là minimize số lần đổi cổng, dưới hard constraints hiện tại.

Không được diễn giải là tối ưu mọi soft criterion.

---

# 10. Simulated Annealing

Pipeline chính:

```text
CP-SAT feasible assignment
        ↓
Simulated Annealing
```

Không đổi pipeline này.

Chạy SA với cùng `pred_instance`, `mode="fixed"`.

### Không tuning sâu trong task này

Giữ default hiện tại nếu cần để benchmark nhanh:

```text
t0=100
alpha=0.95
iterations=2000
seed=42
```

Nhưng report phải đánh dấu đây là **implementation default chưa được tune**.

### Quan trọng: đánh giá đúng `soft_cost`

Hiện `soft_cost()` có term:

```python
p_delay * delay_est_min
```

term này không phụ thuộc assignment.

Không cần viết lại risk objective trong task này.

Nhưng phải bổ sung hàm phân rã cost để report thấy rõ:

```python
soft_cost_breakdown(...)
```

Tối thiểu trả về:

```text
reassignment_cost
delay_risk_cost
load_balance_cost
remote_gate_cost
total
```

Nếu `delay_risk_cost` giống hệt giữa các assignment, report phải nói rõ:

> Thành phần delay-risk hiện tại là hằng số theo assignment nên chưa thật sự hướng dẫn SA chọn gate.

Không được tuyên bố SA đã tối ưu buffer/risk nếu code chưa làm.

Thu thập cho SA:

```text
initial_cost
best_cost
improvement
iterations
runtime
reassigned_count
reassignment_rate
gates_used
predicted_conflicts
cost breakdown
```

---

# 11. Evaluation harness mới

Tạo script riêng, ví dụ:

```text
scripts/run_turnaround_reassignment_weekly.py
```

Không ghi đè các script/report cũ.

Script phải chạy end-to-end:

```text
load parquet
   ↓
for gates in [147, 161, 175]
   ↓
build P0 from sched_*
   ↓
attach initial_gate
   ↓
build pred instance from pred_*
   ↓
Greedy min_reassignment
   ↓
CP-SAT
   ↓
CP-SAT+SA if CP-SAT feasible
   ↓
evaluate
   ↓
write artifacts + Markdown report
```

---

# 12. Evaluation trên predicted windows

Viết evaluator độc lập đủ đơn giản để kiểm tra:

```text
no overlap
all assigned / unassigned
reassignment vs initial_gate
gates used
```

Đối với full feasible solution:

```text
predicted_conflicts == 0
```

Nếu không bằng 0, coi là bug và điều tra trước khi báo cáo.

---

# 13. Replay trên `actual_*` — CHỈ ĐỂ ĐÁNH GIÁ

Sau khi tất cả assignment đã được tạo xong, được phép dùng:

```text
actual_start_min
actual_end_min
```

để replay cùng assignment.

Tính:

```text
actual_conflicting_pairs
actual_sessions_in_conflict
actual_conflict_rate
```

Không dùng actual để thay đổi assignment.

Report phải tách rõ:

```text
Planning metrics (pred_*)
Evaluation-only actual replay
```

Không được để actual leak ngược vào solver.

---

# 14. Output artifacts

Không overwrite input parquet.

Tạo ít nhất:

## 14.1. CSV/Parquet kết quả scenario chính 161 gates

Ví dụ:

```text
src/artifacts/predictions/atl_2024_01_01_turnaround_reassignment_weekly_161g.csv
```

Các cột tối thiểu:

```text
session_id
session_type
aircraft_type

sched_start_min
sched_end_min
pred_start_min
pred_end_min

initial_gate

greedy_gate
cpsat_gate
sa_gate

greedy_reassigned
cpsat_reassigned
sa_reassigned
```

Có thể thêm actual fields vào artifact evaluation, nhưng không được dùng chúng trong planning.

---

## 14.2. Metrics JSON hoặc CSV

Khuyến nghị:

```text
src/artifacts/predictions/turnaround_reassignment_weekly_metrics.json
```

Chứa metrics cho:

```text
147
161
175
```

và:

```text
P0
Greedy
CP-SAT
CP-SAT+SA
```

---

# 15. Báo cáo Markdown bắt buộc

Sau khi code chạy xong, tự động tạo:

```text
docs/thesis_notes/weekly_gate_optimization_status_turnaround_sessions.md
```

Báo cáo phải được tạo từ kết quả run thật, **không hard-code số liệu**.

## Cấu trúc bắt buộc

### 1. Executive Summary

Nêu:

- dataset;
- số sessions;
- scenario chính;
- P0 được tạo thế nào;
- ba solver có chạy được không;
- kết luận ngắn về tình trạng hiện tại.

---

### 2. Data Contract hiện tại

Ghi rõ các field đã dùng:

```text
sched_*
pred_*
p_delay*
aircraft_type
session_type
```

Ghi rõ:

```text
initial_gate không có trong input gốc;
được optimization layer tự sinh.
```

Ghi rõ `actual_*` chỉ dùng evaluation.

---

### 3. Những thay đổi code đã thực hiện

Liệt kê từng file được sửa/tạo:

```text
file
mục đích
thay đổi chính
```

Không mô tả chung chung.

---

### 4. P0 — Initial Gate Schedule

Báo cáo:

```text
policy
time_basis
gate count
assigned/unassigned
gates used
runtime
```

Và giải thích:

> P0 là lịch mô phỏng từ scheduled windows, không phải lịch cổng thật của ATL.

---

### 5. Scenario Configuration

Bảng:

| Scenario | Gates | Ý nghĩa |
|---|---:|---|
| Stress | 147 | gần/ngưỡng dưới, có thể infeasible |
| Main | 161 | báo cáo tuần chính |
| Relaxed | 175 | nhiều slack hơn |

Ghi buffer semantics đang giữ nguyên.

---

### 6. Bảng kết quả tổng hợp

Bảng ít nhất:

| Method | Gates | Status | Assigned | Unassigned | Reassigned | Reassign % | Pred Conflicts | Actual Replay Conflicts | Gates Used | Runtime |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|

Không bỏ các run thất bại; ghi rõ `INFEASIBLE`, `SKIPPED`, hoặc error.

---

### 7. Đánh giá Greedy hiện tại

Trả lời rõ:

- Greedy đang làm được gì?
- Có full feasible ở 161 không?
- Số reassignment?
- Điểm mạnh:
  - nhanh;
  - baseline dễ hiểu;
  - ưu tiên giữ P0.
- Điểm yếu:
  - local/greedy;
  - có thể unassigned dù global feasible solution tồn tại;
  - không đảm bảo tối ưu.

Kết luận trạng thái:

```text
WORKING / PARTIALLY WORKING / BLOCKED
```

và lý do.

---

### 8. Đánh giá CP-SAT hiện tại

Trả lời:

- objective reassignment đã hoạt động trở lại chưa?
- status 161 gates;
- số reassignment;
- runtime;
- hard constraints;
- 147 nếu infeasible thì vì sao.

Điểm mạnh:

- exact feasibility;
- minimize reassignment objective hiện tại;
- deterministic model definition.

Điểm yếu:

- chưa có overflow;
- chưa có t_decision/locked sessions;
- chưa có đầy đủ soft objective;
- gate topology hiện còn đơn giản nếu `ALL`.

Kết luận:

```text
WORKING / PARTIALLY WORKING / BLOCKED
```

---

### 9. Đánh giá Simulated Annealing hiện tại

Báo cáo:

```text
initial CP-SAT cost
best cost
improvement
runtime
iterations
```

In bảng cost breakdown.

Phải nói rõ:

- SA có giữ feasibility không?
- có cải thiện objective hiện tại không?
- term delay risk hiện có phụ thuộc assignment không?
- cooling schedule hiện chưa tune.

Không được tuyên bố SA tốt hơn nếu số liệu không cho thấy.

Kết luận:

```text
WORKING / PARTIALLY WORKING / BLOCKED
```

---

### 10. So sánh Greedy vs CP-SAT vs CP-SAT+SA

Trả lời bằng số liệu:

- phương pháp nào ít reassignment nhất?
- phương pháp nào nhanh nhất?
- SA có cải thiện CP-SAT không?
- actual replay robustness của từng phương pháp ra sao?
- chênh lệch 147 / 161 / 175 thế nào?

Không ép phải có winner.

Nếu CP-SAT+SA chưa hơn Greedy, ghi đúng sự thật và phân tích nguyên nhân.

---

### 11. Known Limitations

Bắt buộc ghi:

1. `initial_gate` là synthetic P0, không phải gate thật ATL.
2. 2024 artifact ở task này chỉ dùng **engineering smoke/integration test**, không được coi là final thesis holdout result.
3. Buffer semantics chưa chốt lại.
4. `t_decision` và locked sessions chưa có.
5. CP-SAT chưa có overflow/REMOTE.
6. SA delay-risk term hiện tại có thể là constant theo assignment.
7. SA temperature/iterations chưa tune.
8. Monte Carlo chưa sửa trong task này.
9. Nếu gate compatibility đang `ALL`, wide/narrow constraint chưa thực sự tạo áp lực.

---

### 12. Next Steps

Không triển khai, chỉ đề xuất theo thứ tự:

```text
1. lock optimization input schema
2. t_decision + locked sessions
3. remote/overflow
4. risk-aware slack objective
5. SA tuning + multi-seed
6. Monte Carlo calibration + early arrivals + recourse
7. deterministic aircraft-gate compatibility topology
8. final experiment protocol
```

---

### 13. Test & Reproducibility

Ghi:

```text
git branch
git commit hash trước khi sửa
Python version
pytest result
dataset path
dataset row count
scenario configs
random seed
```

Nếu có test fail, liệt kê tên test và nguyên nhân.

---

# 16. Tests bắt buộc phải thêm

Tạo unit/integration tests cho path mới.

## T1 — P0 chỉ dùng sched

Tạo hai DataFrame giống `sched_*` nhưng khác hoàn toàn `pred_*`.

Kết quả P0 phải giống nhau.

---

## T2 — P0 không phụ thuộc actual

Thay đổi `actual_*`.

P0 phải không đổi.

---

## T3 — Pred instance dùng đúng pred window

Với một row:

```text
pred_start_min = 100
pred_end_min = 180
buffer = 15
```

`occupancy_window(mode="fixed")` phải trả:

```text
85, 195
```

(trừ logic clamp ở biên ngày).

---

## T4 — Không nhân lại `p × delay_est`

Giữ `pred_start/end` cố định nhưng thay đổi:

```text
p_delay_max
arr_delay_est_min
dep_delay_est_min
```

Trong `mode="fixed"`, occupancy window phải không đổi.

---

## T5 — initial_gate alias

DataFrame có:

```text
initial_gate="G05"
```

sau adapter:

```python
Flight.current_gate == "G05"
```

---

## T6 — CP-SAT objective reassignment hoạt động

Toy case có P0 feasible.

CP-SAT phải giữ P0 nếu không có lý do phải đổi.

---

## T7 — Same P0

Benchmark harness phải xác nhận Greedy / CP-SAT / SA cùng so với đúng một `initial_gate` map.

---

## T8 — No actual leakage

Planning functions phải chạy được nếu drop toàn bộ:

```text
actual_*
*_true_delay_*
```

khỏi DataFrame.

---

## T9 — Actual replay không sửa assignment

Chạy replay với hai bộ actual windows khác nhau.

Assignment solver output trước replay phải giữ nguyên.

---

## T10 — Legacy regression

Chạy toàn bộ test hiện có.

Không chấp nhận sửa path mới mà làm hỏng hàng loạt legacy tests.

---

# 17. Acceptance Criteria

Task chỉ hoàn thành khi thỏa tất cả:

- [ ] Load được `atl_2024_01_01_full_day_1500_flights_turnaround_sessions.parquet`.
- [ ] Sinh được deterministic P0 từ `sched_*`.
- [ ] Có `initial_gate` cho mọi session trong main scenario hoặc ghi rõ nếu P0 infeasible.
- [ ] Build được `pred_instance` trực tiếp từ `pred_*`.
- [ ] Path planning mới không dùng `p × delay_est` để dựng occupancy.
- [ ] Greedy chạy và xuất metrics.
- [ ] CP-SAT chạy trên main 161 gates và xuất metrics, hoặc nếu infeasible phải có bằng chứng/lower-bound giải thích rõ.
- [ ] SA chạy từ CP-SAT nếu CP-SAT feasible.
- [ ] Cả ba cùng dùng một P0.
- [ ] Full feasible assignments có `predicted_conflicts == 0`.
- [ ] `actual_*` chỉ được đọc ở evaluation/replay.
- [ ] Có artifact output cho scenario 161.
- [ ] Có metrics 147/161/175.
- [ ] Có báo cáo `weekly_gate_optimization_status_turnaround_sessions.md`.
- [ ] Report có đánh giá riêng Greedy / CP-SAT / SA.
- [ ] Report không phóng đại SA hoặc robustness.
- [ ] Test mới pass.
- [ ] Test legacy pass hoặc mọi failure được ghi rõ và sửa trước khi kết thúc.

---

# 18. Cách làm việc yêu cầu Antigravity

1. **Đọc code hiện tại trước khi sửa.**
2. Xác minh các nhận xét trong task bằng code thật.
3. Không coi nhận xét cũ là sự thật nếu code hiện tại khác.
4. Thay đổi tối thiểu, ưu tiên adapter/harness thay vì sửa logic ở nhiều nơi.
5. Không duplicate occupancy logic giữa Greedy, CP-SAT và SA.
6. Dùng chung `occupancy_window()` / canonical helper.
7. Không overwrite input dataset.
8. Không xóa report cũ.
9. Không thay đổi LOCKED research decisions nếu không cần.
10. Không commit/push tự động nếu chưa được yêu cầu.

---

# 19. Kết quả cuối cùng Antigravity phải trả về cho người dùng

Sau khi thực thi xong, phản hồi cuối phải gồm:

### A. Files changed

```text
modified:
...
created:
...
```

### B. Test result

Ví dụ:

```text
pytest: XX passed, YY failed
```

### C. Main 161-gate result

Một bảng ngắn:

```text
P0
Greedy
CP-SAT
CP-SAT+SA
```

với:

```text
status
reassigned
unassigned
pred conflicts
actual replay conflicts
runtime
```

### D. 147 / 161 / 175 sensitivity

Bảng ngắn, kể cả scenario infeasible.

### E. Assessment

Nêu riêng:

```text
Greedy: WORKING / PARTIALLY WORKING / BLOCKED
CP-SAT: WORKING / PARTIALLY WORKING / BLOCKED
SA: WORKING / PARTIALLY WORKING / BLOCKED
```

và lý do ngắn.

### F. Report path

Phải cung cấp:

```text
docs/thesis_notes/weekly_gate_optimization_status_turnaround_sessions.md
```

---

# 20. Ghi chú nghiên cứu quan trọng

Dataset `2024-01-01` hiện đang được sử dụng vì đây là artifact tích hợp mới nhất mà nhóm cung cấp.

Tuy nhiên repo hiện có protocol coi 2024 là final holdout.

Vì vậy report task này phải gắn nhãn rõ:

> **ENGINEERING / INTEGRATION SMOKE TEST — NOT FINAL THESIS EVALUATION**

Không sử dụng các kết quả tuần này để tuyên bố performance cuối cùng của hệ thống.

---

# 21. Ưu tiên nếu gặp xung đột thời gian

Nếu không đủ thời gian để hoàn thành toàn bộ:

## Priority 1

```text
P0 + initial_gate
pred_* direct occupancy
Greedy
CP-SAT
161-gate benchmark
```

## Priority 2

```text
CP-SAT -> SA
soft cost breakdown
147/175 sensitivity
```

## Priority 3

```text
actual replay metrics
report polish
```

Nhưng **report Markdown vẫn bắt buộc phải được tạo**, kể cả khi một số solver đang PARTIALLY WORKING hoặc BLOCKED.

Mục đích của report là phản ánh đúng trạng thái hiện tại, không phải chứng minh tất cả phương pháp đều tốt.
