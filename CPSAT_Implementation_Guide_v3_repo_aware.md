# Hướng dẫn triển khai CP-SAT — Aeolus Gate Optimization
### Dự báo trễ chuyến bay và tối ưu hóa tái phân bổ cổng đỗ tàu bay (CNTT-KLCN168)

> **Dành cho:** AI coding agent chạy trong Visual Studio Code hoặc Antigravity IDE, làm việc trực tiếp trên repo hiện tại của nhóm.
> **Cách dùng:** Đọc toàn bộ tài liệu, thực hiện **Bước 0 trước tiên và bắt buộc** (khảo sát API thật của repo), sau đó mới viết code theo các Bước tiếp theo. Không tự suy đoán chữ ký hàm (function signature) khi chưa mở file thật để kiểm tra.

---

## 0. Bắt buộc: khảo sát repo hiện có trước khi viết bất kỳ dòng code nào

Tài liệu này được soạn dựa trên cây thư mục (`structure.txt`) của dự án, KHÔNG dựa trên nội dung thật của từng file (agent chưa được cung cấp). Vì vậy, trước khi cài đặt Bước 1 trở đi, agent phải tự mở và tóm tắt lại các file sau, rồi đối chiếu với giả định trong tài liệu này (mục nào giả định sai, agent phải tự điều chỉnh code cho khớp API thật, không được bịa hàm không tồn tại):

| File cần mở | Mục đích khảo sát | Giả định tạm trong guide này (cần agent xác minh) |
|---|---|---|
| `src/models/contracts.py` | Tìm định nghĩa kiểu dữ liệu đầu ra của mô hình dự báo (có tách `p_delay` và `delay_est` không, hay gộp chung) | Giả định có 2 đại lượng tách biệt: xác suất trễ và số phút trễ ước tính (kiến trúc "dual prediction" theo `docs/decisions/decision_dual_prediction_architecture_v4.md`) |
| `src/models/artifacts.py` | Tìm hàm load model đã huấn luyện từ đĩa | Giả định có hàm dạng `load_artifact(path) -> model` |
| `src/models/rolling.py` | Cách mô hình sinh dự báo theo rolling window | Giả định có thể gọi để `predict(df)` trên một tập chuyến bay mới |
| `docs/decisions/decision_dual_prediction_architecture_v4.md` | Xác nhận kiến trúc dự báo kép (phân loại + hồi quy) | Guide này viết theo giả định đây là 2 model riêng |
| `src/data/access_guard.py` | Cơ chế chặn truy cập `2024 Final Holdout` | Guide giả định: **Monte Carlo Simulation KHÔNG được gọi access_guard để mở khóa 2024**; toàn bộ trễ "thực tế" trong Monte Carlo là dữ liệu **tổng hợp (synthetic)**, không phải 2024 thật |
| `src/data/temporal_protocol.py`, `src/data/leakage_rules.py` | Quy tắc chống rò rỉ đang áp dụng cho mô hình dự báo | Module tối ưu hoá phải tuân theo cùng triết lý: không dùng nhãn thật làm input |
| `src/data/flight_chain_reconstruction.py`, `src/data/chain_inspection.py` | Hàm/API đọc `chain_groups`, `chain_members`, `inbound_target_map` (3 dataset dưới `src/data/processed/flight_chain_reconstructed_v1/`) | Giả định `chain_members` cho biết từng chuyến bay thuộc `chain_group` nào (đại diện 1 tàu bay/1 ngày); dùng để ghép cặp chuyến đến–đi liên tiếp của cùng nhóm |
| `configs/outlier_and_simulation_guard.yaml` | **Rất quan trọng — tên file gợi ý đã có sẵn quy tắc guard cho việc mô phỏng (simulation)** | Guide giả định file này CHƯA áp dụng cho gate simulation; nếu đã có, agent phải tái sử dụng thay vì tạo guard mới trùng lặp |
| `docs/thesis_notes/assumptions.md`, `docs/thesis_notes/limitations.md` | Nơi tập trung ghi các giả định/giới hạn của khóa luận | Agent phải **thêm** (không thay thế) giả định "Aeolus không có dữ liệu cổng đỗ/loại tàu bay — toàn bộ môi trường sân bay là mô phỏng" vào 2 file này thay vì chỉ ghi trong code comment |
| `docs/roadmap/*_V4_DONG_BO.md` | Roadmap 12 tuần bản mới nhất | Guide này bám theo mốc Tuần 7–10 của bản V4; nếu V3 mới là bản hiệu lực, agent điều chỉnh số tuần tương ứng |
| Nếu tồn tại `docs/superpowers/specs/` và `docs/superpowers/plans/` với quy trình spec→plan→thực thi | Xác định có đang dùng quy trình spec-driven development theo skill/plugin agent hay không | Nếu có, agent nên **chuyển nội dung Bước 1–8 dưới đây thành 1 spec file** (`docs/superpowers/specs/<ngày>-cp-sat-gate-assignment-design.md`) và 1 plan file tương ứng theo đúng khuôn mẫu các file cũ trong 2 thư mục đó, thay vì chỉ dùng độc lập file markdown này |

**Nguyên tắc xử lý khi giả định sai:** nếu API thật khác với giả định trong bảng trên, agent sửa lại đoạn pseudocode ở Bước tương ứng cho khớp, đồng thời ghi 1 dòng note ở đầu file code mới (`# ĐÃ ĐIỀU CHỈNH so với guide: <lý do>`) để người review biết chỗ nào lệch với tài liệu gốc.

---

## 1. Quy tắc bắt buộc (không đổi bất kể API thật ra sao)

1. **Không đưa nhãn thật (`ARR_DELAY`, `DEP_DELAY` thật) vào bộ giải CP-SAT/Simulated Annealing.** Đầu vào hợp lệ duy nhất là đầu ra dự báo của mô hình (xác suất trễ `p_delay` và mức trễ ước tính `delay_est_min`).
2. **Bộ dữ liệu Aeolus không có dữ liệu cổng đỗ, loại tàu bay, cấu hình sân bay.** Toàn bộ phần này là **mô phỏng**, phải tách riêng khỏi dữ liệu Aeolus gốc và ghi rõ trong `docs/thesis_notes/assumptions.md`.
3. **Không được mở khóa `2024 Final Holdout`** (đã seal theo `access_guard.py`) cho bất kỳ mục đích nào trong module tối ưu hoá/mô phỏng — kể cả Monte Carlo Simulation. Chỉ dùng 2024 đúng một lần, ở giai đoạn đánh giá cuối cùng của toàn bộ khóa luận (ngoài phạm vi module này).
4. **Mọi module mới đều phải có test đi kèm trong `tests/` (theo đúng quy ước phẳng, không tạo thư mục con), cùng chuẩn mực nghiêm ngặt đã áp dụng ở Tuần 1–4** (leakage rules, holdout guard đều có test riêng — module tối ưu cũng vậy).
5. **Đơn vị thời gian:** phút kể từ 00:00 của ngày lập lịch (`planning_date`), nhất quán với cách các module `src/data/*` đang biểu diễn thời gian (kiểm tra `canonical_schedule_datetime_audit.py` để đồng bộ định dạng).
6. Bản đặc tả CP-SAT trong `CNTT-KLCN168_Đặng_Gia_Hào.docx`, mục 3.4 (báo cáo Tuần 1–4) là **bản nháp ban đầu, đã lỗi thời** — cụ thể còn thiếu ràng buộc tương thích loại tàu bay/cổng, khung giờ khả dụng cổng, và dùng cách diễn đạt dễ gây hiểu lầm dùng trực tiếp `ARR_Delay`/`DEP_Delay` thật. Tài liệu này **thay thế hoàn toàn** mục 3.4 đó; khi cập nhật báo cáo tiến độ, nhóm nên dẫn lại theo Mục 3–8 dưới đây.

---

## 2. Vị trí đặt code trong repo hiện có

Bám theo cây thư mục đã có (không tạo cấu trúc song song mới):

```
src/
├── optimization/                  # ĐÃ CÓ __init__.py — nơi đặt CP-SAT + Simulated Annealing
│   ├── contracts.py               # MỚI — dataclass Flight, Gate, CostParams, ProblemInstance
│   │                               #        (đặt tên "contracts.py" để nhất quán với src/models/contracts.py)
│   ├── cp_sat_solver.py           # MỚI — Bước 5
│   ├── simulated_annealing.py     # MỚI — Bước 6
│   └── greedy_baseline.py         # MỚI — Bước 7
├── simulation/                     # ĐÃ CÓ __init__.py — nơi đặt môi trường sân bay mô phỏng + Monte Carlo
│   ├── simulate_airport.py        # MỚI — Bước 3 (sinh gates.json, aircraft_type)
│   └── monte_carlo.py             # MỚI — Bước 8
├── evaluation/                     # ĐÃ CÓ __init__.py — nơi so sánh Greedy/CP-SAT/CP-SAT+SA
│   └── compare_gate_strategies.py # MỚI
└── data/                            # KHÔNG đụng vào — chỉ import từ đây (load_aeolus, flight_chain_reconstruction...)

configs/
├── week7_gate_simulation.yaml      # MỚI — tham số môi trường mô phỏng (n_gates, tỉ lệ wide-body...)
├── week8_cp_sat.yaml               # MỚI — buffer_time, time_limit_sec, trọng số ràng buộc mềm ban đầu
├── week9_simulated_annealing.yaml  # MỚI — t0, alpha, iterations, trọng số w1..w5
└── week10_monte_carlo.yaml         # MỚI — n_scenarios, seed, tham số phân phối trễ tổng hợp

tests/
├── test_gate_optimization_contracts.py
├── test_simulate_airport.py
├── test_cp_sat_solver.py
├── test_simulated_annealing.py
├── test_greedy_baseline.py
├── test_monte_carlo.py
└── test_compare_gate_strategies.py

docs/
├── decisions/
│   └── decision_gate_optimization_input_contract.md   # MỚI — ghi quyết định theo đúng khuôn decision_registry.md
└── thesis_notes/
    ├── assumptions.md      # CẬP NHẬT — thêm giả định môi trường sân bay là mô phỏng
    └── limitations.md      # CẬP NHẬT — thêm giới hạn của occupancy-window (expected vs worst-case)
```

Nếu agent xác nhận đang dùng quy trình `docs/superpowers/specs` + `docs/superpowers/plans` (xem Bước 0), toàn bộ Mục 3–8 dưới đây được chuyển thể thành 1 spec + 1 plan theo đúng khuôn của các file đã có trong 2 thư mục đó, thay vì giữ nguyên dạng guide độc lập.

---

## 3. `src/optimization/contracts.py` — Data contract

```python
"""Contracts cho module gate optimization.
Đặt cùng phong cách với src/models/contracts.py — agent kiểm tra lại
để dùng chung quy ước đặt tên (vd BaseModel/dataclass, kiểu Enum...).
"""
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Flight:
    flight_id: str                  # khớp khoá đã dùng ở src/data (kiểm tra load_aeolus.py để lấy đúng tên cột id)
    direction: str                   # "ARR" | "DEP"
    aircraft_type: str               # MÔ PHỎNG — không có trong Aeolus
    sched_time_min: int
    p_delay: float                   # ĐẦU RA mô hình phân loại (dual prediction) — không phải nhãn thật
    delay_est_min: float             # ĐẦU RA mô hình hồi quy (dual prediction) — không phải nhãn thật
    dwell_time_min: int
    chain_group_id: Optional[str] = None   # lấy từ chain_members (Bước 0 xác minh tên cột thật)
    current_gate: Optional[str] = None
    priority_weight: float = 1.0

@dataclass
class Gate:
    gate_id: str
    compatible_types: list[str]
    is_contact_gate: bool = True
    available_from_min: int = 0
    available_to_min: int = 1440
    adjacent_gates: list[str] = field(default_factory=list)

@dataclass
class CostParams:
    buffer_time_min: int = 15
    delay_cost_weight: float = 1.0
    reassignment_cost_default: float = 50.0
    remote_gate_cost: float = 20.0

@dataclass
class ProblemInstance:
    airport: str
    planning_date: str
    horizon_min: int
    flights: list[Flight]
    gates: list[Gate]
    cost_params: CostParams
```

Test tối thiểu (`tests/test_gate_optimization_contracts.py`): JSON round-trip, và một test khẳng định **không thể** gán giá trị từ cột `ARR_DELAY`/`DEP_DELAY` thô vào `p_delay`/`delay_est_min` (assert kiểu dữ liệu/khoảng giá trị hợp lệ, ví dụ `0 <= p_delay <= 1`).

---

## 4. `src/simulation/simulate_airport.py` — Bước 3: môi trường sân bay mô phỏng

```python
import random
from src.optimization.contracts import Gate

AIRCRAFT_TYPES = ["A319", "A320", "A321", "B737", "B738", "B739", "WIDEBODY"]

def generate_gates(n_gates: int, seed: int, wide_capable_ratio: float = 0.2) -> list[Gate]:
    rng = random.Random(seed)
    gates = []
    for k in range(n_gates):
        is_wide_capable = rng.random() < wide_capable_ratio
        compatible = AIRCRAFT_TYPES if is_wide_capable else AIRCRAFT_TYPES[:-1]
        gates.append(Gate(
            gate_id=f"G{k+1:02d}",
            compatible_types=compatible,
            is_contact_gate=rng.random() < 0.7,
            adjacent_gates=[f"G{k:02d}", f"G{k+2:02d}"] if 0 < k < n_gates - 1 else [],
        ))
    return gates

def assign_aircraft_type(rng: random.Random, widebody_share: float = 0.08) -> str:
    if rng.random() < widebody_share:
        return "WIDEBODY"
    return rng.choice(AIRCRAFT_TYPES[:-1])
```

Tham số `n_gates`, `wide_capable_ratio`, `widebody_share`, `seed` đọc từ `configs/week7_gate_simulation.yaml` — agent kiểm tra cách các baseline cũ đọc YAML (`base.yaml` + `week4_*.yaml`) để dùng đúng loader hiện có trong repo (có thể đã có sẵn ở `src/data` hoặc một module config chung), không tự viết loader YAML mới nếu đã tồn tại.

**Ghi log bắt buộc:** số cổng tương thích thân rộng, tỉ lệ contact/remote thực tế sau khi sinh — log này cần đưa vào báo cáo, không chỉ để trong code.

---

## 5. `src/optimization/cp_sat_solver.py` — Bước 5: model CP-SAT

Dùng `NewOptionalIntervalVar` theo từng cặp (chuyến, cổng) + `AddNoOverlap` theo từng cổng (idiom chuẩn của OR-Tools cho bài toán gán + lập lịch kết hợp):

```python
from ortools.sat.python import cp_model
from collections import defaultdict
from src.optimization.contracts import ProblemInstance

def occupancy_window(flight, buffer_time_min: int, mode: str = "expected"):
    eff_delay = flight.p_delay * flight.delay_est_min if mode == "expected" else flight.delay_est_min
    start = int(flight.sched_time_min + eff_delay - buffer_time_min)
    end = start + flight.dwell_time_min
    return max(0, start), max(max(0, start) + 1, end)

def solve_gate_assignment(instance: ProblemInstance, time_limit_sec: int = 60, mode: str = "expected"):
    model = cp_model.CpModel()
    x, y = {}, {}
    intervals_by_gate = defaultdict(list)

    for f in instance.flights:
        start_i, end_i = occupancy_window(f, instance.cost_params.buffer_time_min, mode)
        assigned_vars = []
        for g in instance.gates:
            var = model.NewBoolVar(f"x_{f.flight_id}_{g.gate_id}")
            x[f.flight_id, g.gate_id] = var
            assigned_vars.append(var)

            if f.aircraft_type not in g.compatible_types:
                model.Add(var == 0)
                continue
            if start_i < g.available_from_min or end_i > g.available_to_min:
                model.Add(var == 0)
                continue

            interval = model.NewOptionalIntervalVar(
                start_i, end_i - start_i, end_i, var, f"iv_{f.flight_id}_{g.gate_id}"
            )
            intervals_by_gate[g.gate_id].append(interval)

        model.Add(sum(assigned_vars) == 1)

        if f.current_gate is not None:
            yv = model.NewBoolVar(f"y_{f.flight_id}")
            y[f.flight_id] = yv
            key = (f.flight_id, f.current_gate)
            model.Add(yv == 1 - x[key]) if key in x else model.Add(yv == 1)

    for intervals in intervals_by_gate.values():
        model.AddNoOverlap(intervals)

    if y:
        model.Minimize(sum(y.values()))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_sec
    solver.parameters.num_search_workers = 8
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError(f"CP-SAT không khả thi: {solver.StatusName(status)}")

    assignment = {
        f.flight_id: next(g.gate_id for g in instance.gates if solver.Value(x[f.flight_id, g.gate_id]) == 1)
        for f in instance.flights
    }
    return assignment, solver.StatusName(status), solver.WallTime()
```

**Ghép cặp đến/đi cùng tàu bay:** thay vì tính `dwell_time_min` cố định như trên cho MỌI chuyến, agent cần dùng `chain_group_id` (Bước 0 xác minh cách lấy từ `chain_members`) để với 2 chuyến cùng nhóm (1 ARR + 1 DEP), tính `end_i` từ thời điểm khởi hành của chuyến DEP thay vì `dwell_time_min` mặc định — chỉ dùng `dwell_time_min` mặc định cho chuyến không ghép được cặp.

**Test bắt buộc (`tests/test_cp_sat_solver.py`):**
- Không có 2 chuyến chồng lấn thời gian tại cùng 1 cổng trong lời giải.
- Không có chuyến nào gán vào cổng không tương thích loại tàu bay.
- Mọi chuyến được gán đúng 1 cổng.
- Case tay: 1 cổng, 2 chuyến không giao nhau thời gian → cả 2 gán được vào cùng cổng đó; 2 chuyến giao nhau thời gian → phải bị từ chối bởi `NoOverlap` hoặc rơi vào INFEASIBLE nếu chỉ có 1 cổng.

---

## 6. `src/optimization/simulated_annealing.py` — Bước 6

```python
import random, math
from collections import defaultdict

def soft_cost(assignment, instance, weights):
    w1, w2, w3, w4 = weights
    cost = 0.0
    gate_load = defaultdict(float)
    for f in instance.flights:
        g_id = assignment[f.flight_id]
        gate = next(g for g in instance.gates if g.gate_id == g_id)
        if f.current_gate is not None and g_id != f.current_gate:
            cost += w1 * instance.cost_params.reassignment_cost_default
        cost += w2 * f.p_delay * f.delay_est_min
        if not gate.is_contact_gate:
            cost += w4 * instance.cost_params.remote_gate_cost * f.priority_weight
        gate_load[g_id] += 1
    loads = list(gate_load.values()) or [0]
    mean_load = sum(loads) / len(loads)
    cost += w3 * sum((l - mean_load) ** 2 for l in loads)
    return cost

def is_feasible(assignment, instance) -> bool:
    """Kiểm tra lại toàn bộ ràng buộc cứng của Mục 5 trên 1 assignment ứng viên."""
    occ = defaultdict(list)
    for f in instance.flights:
        g_id = assignment[f.flight_id]
        gate = next(g for g in instance.gates if g.gate_id == g_id)
        if f.aircraft_type not in gate.compatible_types:
            return False
        start_i, end_i = occupancy_window(f, instance.cost_params.buffer_time_min)
        for (s, e) in occ[g_id]:
            if start_i < e and s < end_i:   # giao nhau
                return False
        occ[g_id].append((start_i, end_i))
    return True

def neighbor(assignment, instance, rng):
    new_assignment = dict(assignment)
    f = rng.choice(instance.flights)
    compatible = [g.gate_id for g in instance.gates if f.aircraft_type in g.compatible_types]
    new_assignment[f.flight_id] = rng.choice(compatible)
    return new_assignment

def simulated_annealing(initial_assignment, instance, weights,
                         t0: float = 100.0, alpha: float = 0.95,
                         iterations: int = 2000, seed: int = 42):
    rng = random.Random(seed)
    current = dict(initial_assignment)
    current_cost = soft_cost(current, instance, weights)
    best, best_cost = current, current_cost
    T = t0
    for _ in range(iterations):
        cand = neighbor(current, instance, rng)
        if not is_feasible(cand, instance):
            continue
        cand_cost = soft_cost(cand, instance, weights)
        delta = cand_cost - current_cost
        if delta < 0 or rng.random() < math.exp(-delta / max(T, 1e-6)):
            current, current_cost = cand, cand_cost
            if current_cost < best_cost:
                best, best_cost = current, current_cost
        T *= alpha
    return best, best_cost
```

`weights = (w1, w2, w3, w4)` đọc từ `configs/week9_simulated_annealing.yaml`. **Test bắt buộc:** `soft_cost` của lời giải SA cuối cùng phải ≤ `soft_cost` của lời giải CP-SAT ban đầu; mọi trạng thái trung gian được chấp nhận (`current`) phải `is_feasible() == True`.

---

## 7. `src/optimization/greedy_baseline.py` — Bước 7

```python
from src.optimization.cp_sat_solver import occupancy_window

def greedy_assign(instance):
    assignment = {}
    gate_free_until = {g.gate_id: 0 for g in instance.gates}
    for f in sorted(instance.flights, key=lambda fl: fl.sched_time_min):
        start_i, end_i = occupancy_window(f, instance.cost_params.buffer_time_min)
        candidates = [g for g in instance.gates
                      if f.aircraft_type in g.compatible_types and gate_free_until[g.gate_id] <= start_i]
        if not candidates:
            raise RuntimeError(f"Greedy thất bại tại chuyến {f.flight_id}: không còn cổng trống")
        chosen = min(candidates, key=lambda g: gate_free_until[g.gate_id])
        assignment[f.flight_id] = chosen.gate_id
        gate_free_until[chosen.gate_id] = end_i
    return assignment
```

---

## 8. `src/simulation/monte_carlo.py` — Bước 8

```python
import random

def sample_realized_delay(flight, rng) -> float:
    """Trễ THỰC TẾ tổng hợp (synthetic) cho 1 kịch bản — KHÔNG lấy từ 2024 Final Holdout."""
    if rng.random() < flight.p_delay:
        return max(15.0, rng.gauss(flight.delay_est_min, flight.delay_est_min * 0.3))
    return 0.0

def run_monte_carlo(instance, assignment, n_scenarios: int = 500, seed: int = 42):
    rng = random.Random(seed)
    results = []
    for s in range(n_scenarios):
        realized = {f.flight_id: sample_realized_delay(f, rng) for f in instance.flights}
        conflicts = _count_conflicts(instance, assignment, realized)  # cần cài đặt: quét theo từng cổng
        results.append({"scenario": s, "conflicts": conflicts})
    return results
```

`_count_conflicts` cần cài đặt logic: với `realized` thay cho `delay_est_min` kỳ vọng, tính lại `occupancy_window` (mode `"worst_case"`, tức không nhân `p_delay` — vì ở đây trễ đã "xảy ra thật" trong kịch bản mô phỏng) và đếm số cặp chuyến chồng lấn thời gian tại cùng cổng theo `assignment` cố định (không được đổi cổng giữa chừng — đó chính là điểm mà CP-SAT+SA cần thể hiện ưu thế so với Greedy khi so sánh ở `src/evaluation/compare_gate_strategies.py`).

---

## 9. `src/evaluation/compare_gate_strategies.py`

So sánh 3 chiến lược (Greedy / CP-SAT / CP-SAT+SA) trên cùng `ProblemInstance` và cùng bộ kịch bản Monte Carlo, xuất bảng theo đúng chỉ tiêu đề cương đã cam kết: tổng chi phí do trễ, số lần tái phân bổ, số xung đột cổng, thời gian giải. Kết quả này là input cho dashboard (ngoài phạm vi guide này).

---

## 10. Checklist hoàn thành

- [ ] Đã thực hiện Bước 0 (khảo sát API thật) và ghi lại các chỗ giả định sai/đúng
- [ ] `src/optimization/contracts.py` + test round-trip
- [ ] `src/simulation/simulate_airport.py` + log cấu hình cổng
- [ ] `src/optimization/cp_sat_solver.py` với đầy đủ ràng buộc cứng (tương thích loại tàu, khung giờ, không chồng lấn, đúng 1 cổng/chuyến) + ghép cặp qua `chain_group_id`
- [ ] `src/optimization/simulated_annealing.py` không làm xấu lời giải CP-SAT, luôn khả thi
- [ ] `src/optimization/greedy_baseline.py`
- [ ] `src/simulation/monte_carlo.py` dùng dữ liệu tổng hợp, KHÔNG đụng 2024 Final Holdout
- [ ] `src/evaluation/compare_gate_strategies.py`
- [ ] `configs/week7_*.yaml` .. `configs/week10_*.yaml`
- [ ] Toàn bộ test trong `tests/` pass
- [ ] Cập nhật `docs/thesis_notes/assumptions.md` và `limitations.md`
- [ ] Ghi 1 quyết định vào `docs/decisions/decision_gate_optimization_input_contract.md` theo khuôn `decision_registry.md`
- [ ] Nếu dùng quy trình superpowers: đã tạo spec + plan tương ứng trong `docs/superpowers/`

---

## Tài liệu tham khảo

- Google OR-Tools CP-SAT (`NewOptionalIntervalVar`, `AddNoOverlap`): https://developers.google.com/optimization/cp
- S. Kirkpatrick, C. D. Gelatt, M. P. Vecchi, "Optimization by Simulated Annealing," *Science*, 220(4598), 1983.
- A. Bolat, "Procedures for Providing Robust Gate Assignments for Arriving Aircrafts," *EJOR*, 120(1), 2000.
- A. Haghani, M.-C. Chen, "Optimizing Gate Assignments at Airport Terminals," *Transportation Research Part A*, 32(6), 1998.
- Lin Xu et al., "Aeolus: A Multi-structural Flight Delay Dataset," NeurIPS 2025 Datasets and Benchmarks Track.
- `CNTT-KLCN168_Đặng_Gia_Hào.docx`, Mục 3.4 (bản nháp đã được thay thế bởi tài liệu này).
