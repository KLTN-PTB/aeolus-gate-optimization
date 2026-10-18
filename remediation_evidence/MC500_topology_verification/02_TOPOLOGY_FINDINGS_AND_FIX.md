# 02. TOPOLOGY DEFECT ROOT CAUSE ANALYSIS & CONTROLLED CORRECTION

**Protocol Reference:** AEOLUS-MC500-TOPOLOGY-GATE  
**Component:** `src/simulation/scalability_scenario.py`, `scripts/run_g2_monte_carlo_remediation.py`  
**Author:** Operations Research & Scientific Software Verification Engineer  

---

## 1. Phân tích Nguyên nhân Gốc rễ (Root Cause Analysis)

### 1.1. Hiện tượng ghi nhận từ Pilot MC500-P1
Trong đợt chạy Pilot $N=20$ của MC500-P1:
1. Toàn bộ $220$ evaluation slots (bao gồm $60$ evaluations của Mode B2) đều ghi nhận `remote_count = 0`.
2. Riêng kịch bản `MC_REM_S0009` (scenario index 9), cả 3 solver ban đầu (Greedy, CP-SAT, Hybrid) đều thất bại ở Mode B2 với trạng thái:
   `ONLINE_INFEASIBLE_NO_CAPACITY`, để lại đúng 1 chuyến bay không thể gán cổng, đẩy chi phí mục tiêu lên $574.63$.
3. Tổng số lượt khả thi của $N=20$ bị dừng ở $166/220$ thay vì đạt mức tối ưu.

### 1.2. Phân tích Luồng Dữ liệu & Sai lệch Mã nguồn
Khi truy vết mã nguồn:
1. **Khởi tạo kịch bản (`scripts/run_g2_monte_carlo_remediation.py`):**
   ```python
   N_CONTACT_GATES = 25
   N_REMOTE_STANDS = 5

   contact_gates, overflow_gate = scenario_to_gates(scen)
   all_gates = contact_gates + [overflow_gate]
   ```
2. **Hàm phát sinh cổng (`src/evaluation/downstream_comparison_v2.py:build_scenario_gates`):**
   ```python
   overflow_gate = Gate(
       gate_id="REMOTE_APRON_01",
       gate_index=n_contact_gates,
       is_overflow=True,
   )
   ```
3. **Cơ chế tự động phân loại của Domain Entity (`src/optimization/domain.py:Gate.__post_init__`):**
   ```python
   if any(token in upper_id for token in ("APRON", "OVF", "OVERFLOW")):
       resolved_res = GateResourceType.UNBOUNDED_OVERFLOW_APRON
       object.__setattr__(self, "capacity", math.inf)
   ```
   Do ID chứa chuỗi `"APRON"`, cổng này bị gán thành bãi tràn vô hạn (`math.inf`).
4. **Cấu hình thí nghiệm nghiêm ngặt:**
   ```python
   allow_unbounded_overflow = False
   finite_remote_capacity = 5
   ```
5. **Cơ chế chọn cổng của Mode B2 (`src/simulation/monte_carlo_engine_v2.py`):**
   ```python
   remote_gate = next(
       (g for g in gates if g.resource_type == GateResourceType.FINITE_REMOTE_STAND),
       None,
   )
   # remote_gate trả về None vì không có cổng nào có kiểu FINITE_REMOTE_STAND!
   if remote_gate is None and config.allow_unbounded_overflow:
       remote_gate = next((g for g in gates if g.is_overflow), None)
   # Do allow_unbounded_overflow = False, điều kiện này KHÔNG chạy!
   # remote_gate HOÀN TOÀN LÀ None!
   ```
6. **Hậu quả vận hành:**
   Khi xung đột trễ diễn ra khiến 25 cổng tiếp xúc bị chiếm dụng, thuật toán online recourse tìm kiếm `remote_gate`. Vì `remote_gate is None` và bãi tràn vô hạn bị khóa, thuật toán buộc phải trả về `None, "NO_CAPACITY_EXHAUSTED"`.

---

## 2. Giải pháp Sửa đổi Tối thiểu Có kiểm soát (Controlled Minimal Fix)

### 2.1. Thiết kế Kiến trúc
Để không làm hỏng các bài kiểm tra kế thừa (legacy tests) và các caller khác:
1. Mở rộng tham số hàm `scenario_to_gates()` trong `src/simulation/scalability_scenario.py` với 2 tham số tùy chọn:
   - `finite_remote_capacity: int | None = None`
   - `remote_gate_id: str = "REMOTE_STAND_01"`
2. Nếu `finite_remote_capacity` được truyền vào giá trị dương:
   - Tạo rõ ràng 25 cổng với `resource_type = GateResourceType.CONTACT_GATE`, `capacity = 1`, `is_overflow = False`.
   - Tạo rõ ràng 1 vị trí đỗ tập trung với `resource_type = GateResourceType.FINITE_REMOTE_STAND`, `capacity = finite_remote_capacity`, `is_overflow = True`.
3. Nếu không truyền (hoặc truyền `None`), gọi `build_scenario_gates()` để bảo toàn nguyên vẹn hành vi legacy.

### 2.2. Đồng bộ Production Runner
Trong `scripts/run_g2_monte_carlo_remediation.py`:
1. Gọi `scenario_to_gates(scen, finite_remote_capacity=N_REMOTE_STANDS, remote_gate_id="REMOTE_STAND_01")`.
2. Tạo và xuất tự động `gate_inventory.json` vào thư mục đầu ra của lượt chạy.
3. Thêm `"gate_inventory.json"` vào danh sách `artifacts_generated` trong `simulation_manifest.json`.

---

## 3. Bản Dịch Thay đổi Mã Nguồn Thực tế (Git Diff Patch)

```diff
diff --git a/scripts/run_g2_monte_carlo_remediation.py b/scripts/run_g2_monte_carlo_remediation.py
index d2b6d2e..c1ca2bd 100644
--- a/scripts/run_g2_monte_carlo_remediation.py
+++ b/scripts/run_g2_monte_carlo_remediation.py
@@ -24,6 +24,7 @@ from dataclasses import asdict
 from datetime import datetime, timezone
 import hashlib
 import json
+import math
 import os
 from pathlib import Path
 import sys
@@ -46,7 +47,7 @@ from src.contracts.provenance import (
     ScenarioGeneration,
 )
 from src.optimization.config import GateOptimizationConfig
-from src.optimization.domain import Gate, Flight, GateAssignment
+from src.optimization.domain import Gate, Flight, GateAssignment, GateResourceType
 from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
 from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver
 from src.optimization.solvers.hybrid_solver import HybridGateSolver
@@ -125,8 +126,35 @@ def run_g2_remediation_pipeline(
         scenario_id="SCEN_P09_CANONICAL_120",
     )
     base_flights = scenario_to_flights(scen)
-    contact_gates, overflow_gate = scenario_to_gates(scen)
-    all_gates = contact_gates + [overflow_gate]
+    contact_gates, remote_gate = scenario_to_gates(
+        scen, finite_remote_capacity=N_REMOTE_STANDS, remote_gate_id="REMOTE_STAND_01"
+    )
+    all_gates = contact_gates + [remote_gate]
+
+    # Export certified gate inventory artifact
+    gate_inventory = {
+        "n_contact_gates": len(contact_gates),
+        "total_finite_remote_capacity": sum(
+            g.capacity for g in all_gates if g.resource_type == GateResourceType.FINITE_REMOTE_STAND
+        ),
+        "n_unbounded_overflow_aprons": sum(
+            1 for g in all_gates if g.resource_type == GateResourceType.UNBOUNDED_OVERFLOW_APRON
+        ),
+        "allow_unbounded_overflow": config.allow_unbounded_overflow,
+        "gates": [
+            {
+                "gate_id": g.gate_id,
+                "gate_index": g.gate_index,
+                "resource_type": g.resource_type.value if hasattr(g.resource_type, "value") else str(g.resource_type),
+                "capacity": float(g.capacity) if math.isfinite(g.capacity) else "unbounded",
+                "is_overflow": g.is_overflow,
+                "allowed_carriers": sorted(list(g.allowed_carriers)) if g.allowed_carriers is not None else None,
+                "allowed_aircraft_types": sorted(list(g.allowed_aircraft_types)) if g.allowed_aircraft_types is not None else None,
+                "available_windows": list(g.available_windows) if g.available_windows is not None else None,
+            }
+            for g in all_gates
+        ],
+    }
+    with open(out_path / "gate_inventory.json", "w", encoding="utf-8") as f:
+        json.dump(gate_inventory, f, indent=2)

diff --git a/src/simulation/scalability_scenario.py b/src/simulation/scalability_scenario.py
index eba1e12..4654a04 100644
--- a/src/simulation/scalability_scenario.py
+++ b/src/simulation/scalability_scenario.py
@@ -30,7 +30,7 @@ from src.features.tabular_features import (
     APPROVED_PREDICTOR_COLUMNS,
     APPROVED_PREDICTOR_COLUMNS_V1_1,
 )
-from src.optimization.domain import Flight, Gate
+from src.optimization.domain import Flight, Gate, GateResourceType
 from src.simulation.aircraft_turn import AircraftTurn, AircraftTurnModel
 from src.evaluation.downstream_comparison_v2 import (
     DownstreamScenario,
@@ -472,8 +472,35 @@ def scenario_to_flights(
 
 def scenario_to_gates(
     scenario: DownstreamScenario,
+    finite_remote_capacity: int | None = None,
+    remote_gate_id: str = "REMOTE_STAND_01",
 ) -> tuple[list[Gate], Gate]:
-    """Return contact gates and remote overflow apron for the scenario."""
+    """Return contact gates and remote stand/overflow apron for the scenario.
+
+    If finite_remote_capacity is provided (> 0), constructs explicit GateResourceType.CONTACT_GATE
+    for all contact gates and an explicit GateResourceType.FINITE_REMOTE_STAND with the requested
+    finite capacity.
+    Otherwise, falls back to legacy build_scenario_gates() returning REMOTE_APRON_01.
+    """
+    if finite_remote_capacity is not None and finite_remote_capacity > 0:
+        contact_gates = [
+            Gate(
+                gate_id=f"G_{i+1:02d}",
+                gate_index=i,
+                resource_type=GateResourceType.CONTACT_GATE,
+                capacity=1,
+                is_overflow=False,
+            )
+            for i in range(scenario.n_contact_gates)
+        ]
+        remote_gate = Gate(
+            gate_id=remote_gate_id,
+            gate_index=scenario.n_contact_gates,
+            resource_type=GateResourceType.FINITE_REMOTE_STAND,
+            capacity=finite_remote_capacity,
+            is_overflow=True,
+        )
+        return contact_gates, remote_gate
     return build_scenario_gates(scenario.n_contact_gates)
```
