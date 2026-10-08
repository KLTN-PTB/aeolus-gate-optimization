# P0 — Aeolus Dual Core: Preflight Inventory, Baseline & Repository Protection

**Protocol Phase**: P0 Preflight & Baseline Protection  
**Auditor**: Senior ML Engineer / Research Software Engineer / Software Auditor  
**Date**: 2026-10-08  
**Repository**: `Aeolus Gate Optimization`  
**Execution Context**: Python 3.11.15 AMD64 (Windows 10)  
**Quality Gate Verdict**: **`PASS`**  

---

## 1. Executive Summary & Purpose

Tài liệu này xác lập kiểm toán độc lập **Phase P0: Preflight, Baseline & Repository Protection** cho sáng kiến nâng cấp **Aeolus Dual Core**.
Dự án Aeolus hiện vận hành trên kiến trúc cốt lõi **Core Arrival** kết hợp chu kỳ quay đầu tổng hợp (**Synthetic Turn**) để điều phối và tối ưu hóa cổng đỗ máy bay tại sân bay ATL.

Mục tiêu dài hạn của nhánh **Dual Core** là:
1. Phát triển độc lập mô hình **`CORE_DEPARTURE`** dự báo độ trễ khởi hành có dấu (`DEP_DELAY` signed minutes) tại điểm cắt $T_{\text{cutoff}} = \text{CRS\_DEP\_TIME} - 2\text{h}$ trên tập chuyến bay rời ATL (`ORIGIN = ATL`).
2. Ghép nối dự báo Arrival và Departure vào tầng mô phỏng quay đầu (**Aircraft Turn Synthesis**) và giải bài toán tối ưu hóa phân bổ cổng (**Gate Optimization**).
3. Bảo toàn tuyệt đối mọi artifact đã đóng băng (Arrival models, kết quả P4 NGBoost Student-T, các bài test certification và kết quả nghiên cứu lịch sử).

---

## 2. Kiểm toán Trạng thái Repository & Git Topology

### 2.1. Trạng thái Git hiện tại
* **Nhánh làm việc (Current Branch)**: `development/scalability-1500x50`
* **HEAD Commit**: `18962df` (*"docs(sync): update handover documentation, system state, and project structure"*)
* **Trạng thái Working Tree**:
  - Không có file bị xóa hoặc bị modified chưa stage.
  - Có 5 file đang ở trạng thái **Staged (Changes to be committed)** được kéo về từ nhánh `NTD` theo yêu cầu thao tác của người dùng trước đó trong thư mục `src/artifacts/predictions/`:
    1. `src/artifacts/predictions/atl_1500_flights_cpsat_turnaround_schedule.csv` (474 KB)
    2. `src/artifacts/predictions/atl_1500_flights_reassigned_schedule.csv` (265 KB)
    3. `src/artifacts/predictions/atl_cpsat_turnaround_flights_schedule.csv` (26.5 KB)
    4. `src/artifacts/predictions/atl_cpsat_turnaround_sessions_schedule.csv` (231 KB)
    5. `src/artifacts/predictions/greedy_160_flights_10_gates_schedule.csv` (23.0 KB)
  - **Chính sách bảo toàn**: Các file trên được giữ nguyên vẹn trạng thái staged, **không reset, không stash, không clean và không ghi đè**.
* **Nhánh mới phục vụ Dual Core**: Nhánh `feature/dual-core-departure-v1` đã được khởi tạo an toàn trỏ vào commit `18962df` mà không làm thay đổi trạng thái working tree hiện tại.

### 2.2. Thống kê Cấu trúc Thư mục

| Thư mục | Số lượng File | Dung lượng | Vai trò trong hệ thống |
| :--- | :---: | :---: | :--- |
| `src/` | 341 files | 6.53 MB | Mã nguồn lõi (audit, data, features, models, simulation, optimization, evaluation) |
| `tests/` | 482 files | 6.70 MB | Bộ kiểm thử toàn diện (contract, benchmark, stability, downstream, forensics) |
| `configs/` | 19 files | 0.07 MB | Cấu hình tham số, catalog mô hình, seed, protocol YAML |
| `scripts/` | 192 files | 3.34 MB | Các kịch bản chạy benchmark, audit, report generation |
| `data/` | 527 files | 41.12 GB | Dữ liệu raw CSV, chain .pt và parquet processed theo năm (Git-ignored) |
| `artifacts/` | 1,188 files | 536.76 MB | Checkpoint mô hình, OOF predictions, manifests, báo cáo kết quả |
| `docs/` | 98 files | 1.27 MB | Tài liệu kiến trúc, giao thức nghiên cứu, audit report và handbook |

### 2.3. Định vị chính xác Đường dẫn Hệ thống

| Thành phần chức năng | Đường dẫn mã nguồn chính | Mô tả vai trò |
| :--- | :--- | :--- |
| **Model Registry** | `src/models/registry.py` | Catalog quản lý định danh mô hình, fail-closed metadata, quyền downstream |
| **Model Interfaces** | `src/models/interfaces.py` | Định nghĩa abstract class, capability flags, ModelTask, ModelTarget |
| **Leakage Guard** | `src/data/leakage_rules.py`<br>`src/data/access_guard.py` | Tường lửa chặn rò rỉ dữ liệu sau điểm cắt T-2h và niêm phong holdout 2024 |
| **Protocol Guards** | `src/audit/protocol_guards.py` | Kiểm soát tính toàn vẹn tham số và seed ngẫu nhiên |
| **Feature Builder** | `src/features/arrival_features.py`<br>`src/features/core_arrival.py` | Trích xuất 11 đặc trưng an toàn (Schedule/Calendar/Carrier/Route) |
| **Preprocessing** | `src/data/preprocessing.py`<br>`src/data/canonicalize.py` | Tiền xử lý chuẩn hóa schema, xử lý dữ liệu thiếu, fit trên train fold duy nhất |
| **Simulation** | `src/simulation/turn_synthesis.py`<br>`src/simulation/gate_allocation.py` | Mô hình quay đầu tổng hợp (Synthetic Turn) và tính toán thời gian đỗ cổng |
| **Optimization Solvers** | `src/optimization/solvers/`<br>`src/optimization/sa/` | Các thuật toán điều phối cổng (Greedy, CP-SAT, SA, Hybrid) |
| **Evaluation Engine** | `src/evaluation/native_downstream_p4.py`<br>`src/evaluation/week10_robustness_recourse.py` | Đánh giá vận hành downstream, Monte Carlo robustness và phân tích recourse |

---

## 3. Kiểm toán Hiện trạng Mô hình & Ranh giới Vận hành

### 3.1. Các mô hình Core Arrival
* **Dữ liệu huấn luyện**: 100% là chuyến bay đến Atlanta (`DEST = ATL`).
* **Thời điểm dự báo**: $T_{\text{cutoff}} = \text{CRS\_DEP\_TIME} - 2\text{h}$ trước khi khởi hành tại sân bay gốc.
* **Tập đặc trưng được phê duyệt (11 features)**:
  `CRS_ELAPSED_TIME`, `calendar_year`, `calendar_month`, `calendar_day_of_month`, `calendar_day_of_week`, `is_weekend`, `scheduled_departure_hour`, `scheduled_departure_minute`, `OP_CARRIER`, `ORIGIN`, `OP_CARRIER_FL_NUM`.
* **5 họ mô hình điểm chính (Core Point)**:
  1. `arrival_linear_baseline_v1` (Ridge Regressor / Logistic Classifier)
  2. `arrival_random_forest_baseline_v1` & `arrival_random_forest_tuned_v1_1`
  3. `arrival_hist_gradient_boosting_baseline_v1` & `arrival_hist_gradient_boosting_tuned_v1_1`
  4. `arrival_xgboost_baseline_v1` & `arrival_xgboost_tuned_v1_1`
  5. `arrival_weighted_ensemble_v1`
* **Nguyên tắc bất biến**: Không sử dụng Weather, không sử dụng biến vận hành thực tế (`DEP_DELAY`, `TAXI_OUT`, `WHEELS_OFF`).

### 3.2. Mô hình P4 và Quyền Downstream
* **Định danh mô hình**: `P4_ngboost_student_t` (triển khai qua `B5NGBoostStudentT` / `P4NGBoostStudentTCandidate`).
* **Checkpoint vật lý**: `artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib`
  - Dung lượng: **243,595 bytes**
  - Khóa băm SHA-256: **`e7e7462f17b65b276ebdee9c7beced15e090f69b088a18896d5a91aaa8cb062f`** (Khớp 100% với hằng số `P4_CERTIFIED_SHA256`).
* **Vai trò trong hệ thống**: Được cấp quyền **Role C: Downstream Simulation Champion** trong mô phỏng downstream nhờ khả năng sinh mẫu liên tục (heteroscedastic Student-T: $\mu(x), \sigma(x), \nu(x)$).

### 3.3. Mô hình Auxiliary Departure & Cơ chế Cô lập
* **Định danh**: `departure_auxiliary_baseline_v1` (`LogisticRegressionDepartureModel`).
* **Tác vụ**: `ModelTask.AUXILIARY_DEPARTURE` trên các chuyến bay cất cánh từ ATL (`ORIGIN = ATL`).
* **Target**: Chỉ phân loại nhị phân `DEPARTURE_DELAY_BINARY_15` ($\ge 15$ phút), không dự đoán số phút trễ liên tục.
* **Cơ chế cô lập**:
  - `downstream_eligible = False`.
  - Hàm `is_downstream_eligible(model_id)` trả về `False` ngay lập tức nếu tác vụ khác `CORE_ARRIVAL`.
  - Hàm `assert_downstream_eligible(model_id)` tung ngoại lệ fail-closed nếu có bất kỳ nỗ lực nào đưa model này vào xếp cổng.

### 3.4. Hiện trạng Triển khai Bộ giải Tối ưu (Optimization Solvers)

Bốn thuật toán tối ưu xếp cổng được triển khai và kiểm toán như sau:
1. **Deterministic Greedy (`greedy_solver.py`)**:
   - Thuật toán tham lam đơn vòng, độ phức tạp $O(N \cdot M)$.
   - Thời gian thực thi cực nhanh (~1.1 ms). Đóng vai trò baseline tối thiểu.
2. **CP-SAT Solver (`cp_sat_solver.py`)**:
   - Bộ giải quy hoạch nguyên Constraint Programming của Google OR-Tools.
   - Cơ chế: Tìm kiếm nhánh và cận (Branch-and-Bound), tối ưu toàn cục.
   - Chứng minh đạt nghiệm tối ưu tuyệt đối (Optimality Gap = 0.00%) trên 100% các bài toán kiểm toán (28/28 instances).
3. **Simulated Annealing (`src/optimization/sa/`)**:
   - Thuật toán tìm kiếm cục bộ ngẫu nhiên đa bước, làm nguội theo hàm mũ.
   - Chạy đủ trần thời gian ngân sách (2.0s).
4. **Hybrid CP-SAT + SA (`native_downstream_p4.py` / `scalability_benchmark.py`)**:
   - Phân bổ ngân sách công bằng: CP-SAT chạy 1.0s tìm nghiệm sơ bộ, SA nhận nghiệm đó làm `initial_assignments` (warm-start) và tinh chỉnh tiếp trong 1.0s còn lại.
   - Tổng ngân sách tường đồng nhất: $T = 2.0$ giây.

### 3.5. Ràng buộc cứng, Vùng đệm và Hàm mục tiêu
* **Ràng buộc cứng (Hard Constraints)**:
  - Cấm trùng lịch đỗ (Zero Overlap): Hai máy bay trên cùng một cổng phải cách nhau ít nhất vùng đệm quy định.
  - Tương thích hãng bay - cổng đỗ (Carrier Compatibility).
  - Tương thích kích thước máy bay - kích thước cổng (Aircraft Size Compatibility).
* **Vùng đệm thời gian (Time Buffers)**:
  - Thời gian quay đầu tối thiểu: $T_{\text{turnaround}} = 45$ phút.
  - Thời gian dừng đỗ mặc định: $T_{\text{dwell}} = 60$ phút (cho chuyến chưa ghép đôi).
  - Vùng đệm phân tách an toàn giữa 2 chuyến tại cổng: $B_{\text{sep}} = 15$ phút.
* **Trọng số hàm mục tiêu mềm (Soft Objectives in `GateOptimizationConfig`)**:
  - Phạt đổi cổng danh định (Reassignment): $w_{\text{reassign}} = 10.0$
  - Phạt đỗ bãi xa / tràn cổng (Overflow): $w_{\text{overflow}} = 200.0$
  - Phạt chậm trễ (Delay): $w_{\text{delay}} = 1.0$
  - Phạt xung đột kế hoạch (Conflict): $w_{\text{conflict}} = 1000.0$
  - Hệ số an toàn rủi ro (Risk): $w_{\text{risk}} = 2.0$

---

## 4. Kiểm toán Môi trường & Bảng Dữ liệu / Checkpoint

### 4.1. Môi trường Thực thi (Runtime Environment)
* **Python Runtime**: `Python 3.11.15 AMD64` (`MSC v.1944 64 bit`)
* **Thư viện phụ thuộc**:
  - `ortools`: **9.15.6755** (Hoạt động tốt, hỗ trợ CP-SAT)
  - `ngboost`: **0.5.11** (Hỗ trợ phân phối Student-T P4)
  - `xgboost`: **3.2.0**
  - `pyarrow`: **25.0.1** (Đọc ghi Parquet streaming)
  - `pytest`: **9.1.1**
  - `lightgbm`: **4.7.0**
  - `scikit-learn`: **1.9.0**
  - `scipy`: **1.17.1**
  - `numpy`: **2.2.6**
  - `pandas`: **2.3.3**
  - `optuna`: **5.0.0**
* **Kết luận môi trường**: Mọi thư viện bắt buộc đều được cài đặt đầy đủ với phiên bản tương thích cao nhất.

### 4.2. Bảng Kiểm kê Dữ liệu, Checkpoint và Manifest

| Đường dẫn tài nguyên | Trạng thái | Số lượng file / kích thước | Đánh giá kiểm toán |
| :--- | :---: | :---: | :--- |
| `data/raw/tabular/` | **`PRESENT`** | 9 CSVs (2016–2024, ~15.2 GB) | Toàn vẹn, đầy đủ dữ liệu thô BTS |
| `data/raw/chain/` | **`PRESENT`** | 27 files `.pt` (2016–2024) | Dữ liệu chain gốc (đã khóa NO-GO) |
| `data/processed/tabular_by_year/` | **`PRESENT`** | 224 files Parquet (9 năm) | Dữ liệu canonical 54.674.003 dòng |
| `data/processed/inbound_atl/` | **`PRESENT`** | 20 files Parquet | Tập Inbound 3.022.433 dòng (`DEST=ATL`) |
| `data/processed/outbound_atl/` | **`PRESENT`** | 209 files Parquet | Tập Outbound 3.022.670 dòng (`ORIGIN=ATL`) |
| `data/processed/flight_chain_reconstructed_v1/` | **`PRESENT`** | 25 files | Reconstructed schedule chain |
| `artifacts/models/refactored/` | **`PRESENT`** | 5 checkpoints (XGB, HGB, Hurdle) | Checkpoints huấn luyện baseline |
| `artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib` | **`PRESENT`** | 243.6 KB, SHA-256 xác thực | Checkpoint P4 NGBoost Student-T chuẩn |
| `artifacts/predictions/` | **`PRESENT`** | 32 files Parquet OOF | Kết quả dự báo OOF các fold |
| `artifacts/manifests/` | **`PRESENT`** | 141 manifests JSON/SHA256 | Các bản kê đóng băng hệ thống |
| `artifacts/audit/` | **`PRESENT`** | 198 báo cáo & manifests | Dữ liệu kiểm toán pháp y R25–R39, P10–P14 |
| `artifacts/stress_1500x50/` | **`PRESENT`** | 15 files | Dữ liệu benchmark nghiệm thu 1500x50 |
| `artifacts/week10_robustness/` | **`PRESENT`** | 9 files | Kết quả nghiệm thu robustness Week 10 |

> [!NOTE]
> Khác với dự kiến trong trường hợp chia sẻ kho lưu trữ tối giản, trên máy trạm thực tế hiện tại **TOÀN BỘ DỮ LIỆU PARQUET VÀ CHECKPOINT P4 ĐỀU HIỆN DIỆN ĐẦY ĐỦ VÀ TRUY CẬP ĐƯỢC 100%**.

---

## 5. Kết quả Kiểm thử Baseline Độc lập

Đã thực hiện 2 phiên kiểm thử nghiệm thu baseline với kết quả:

### 5.1. Bộ kiểm thử thu hẹp (Certification, Downstream & Scalability)
* **Lệnh chạy**:
  ```powershell
  python -m pytest tests/test_r37_final_certification.py tests/test_phase10_system_freeze.py tests/downstream/ tests/test_scalability_benchmark.py tests/test_scalability_scenario.py -v
  ```
* **Kết quả**: **85 / 85 tests PASSED (100%)** trong **11.89s**.
* **Exit code**: `0`

### 5.2. Toàn bộ Test Suite của Repository
* **Lệnh chạy**:
  ```powershell
  python -m pytest -q
  ```
* **Kết quả**: **1,231 / 1,231 tests PASSED (100%)** trong **86.59s**.
* **Exit code**: `0`
* **Phân loại lỗi**:
  - Lỗi môi trường (Environment Errors): **0**
  - Lỗi thiếu dữ liệu (Missing Data Errors): **0**
  - Lỗi dự án (Project Defects): **0**
  - Cảnh báo (Warnings): Duy nhất 1 warning về tỷ lệ thu hẹp ngoại lai (shrinkage ratio) trong `test_phase3_pipeline.py`.

Báo cáo JSON độc lập đã được xuất tự động tại:
[`artifacts/dual_core/preflight/baseline_test_report.json`](file:///D:/Study/Code/Python/Aelous/artifacts/dual_core/preflight/baseline_test_report.json)

---

## 6. Bảng băm Cryptographic Hash Inventory các Artifact Đóng băng

Để đảm bảo quy tắc "Không làm thay đổi artifact lịch sử", toàn bộ mã băm SHA-256 của các cấu hình và checkpoint quan trọng đã được niêm phong tại:
[`artifacts/dual_core/preflight/frozen_artifact_hashes.json`](file:///D:/Study/Code/Python/Aelous/artifacts/dual_core/preflight/frozen_artifact_hashes.json)

### Bảng tóm tắt các Hash chủ chốt:

| Tên Artifact | Kích thước | SHA-256 Checksum |
| :--- | :---: | :--- |
| `artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib` | 243,595 B | `e7e7462f17b65b276ebdee9c7beced15e090f69b088a18896d5a91aaa8cb062f` |
| `system_freeze_manifest.json` | 13,039 B | `9ba6e3a65239c894ce05cf8c3961239c4d9e03d7cfec2793108baae4d03e226a` |
| `artifacts/manifests/processed_data_manifest_v1.json` | 5,317 B | `8e0856fea4697c8e42e79d31beb0eac85207ae5ca6c404806f38d06f852d2933` |
| `artifacts/manifests/feature_manifest_arrival_v1.json` | 2,752 B | `cb352a56d194e9f39ee9477fdbc5da7929ba03b5ba089100cbd88b01dec09e85` |
| `artifacts/manifests/temporal_folds_manifest.json` | 2,829 B | `8c5bfbd400e0f0c8591ff0bdcf37759e7e4eaead00697f5e5d92c2a9fcea0f31` |
| `configs/model_catalog_v2.yaml` | 14,188 B | `e612ea99d5cae923e10fa841b8979313ea595d2c0b89b4fce23d5d78fa1b98ee` |
| `configs/base.yaml` | 6,345 B | `335e3fb242409aeafc3fa9db5928dff123f130b91d904724a2c1613b5bf5c4fb` |

---

## 7. Phân tích Rủi ro & Đề xuất ADR cho Nhánh Dual Core

### 7.1. Phân tích Rủi ro Kiến trúc (Risk Matrix)

| Rủi ro | Mức độ | Nguyên nhân tiềm ẩn | Biện pháp kiểm soát & Giảm thiểu |
| :--- | :---: | :--- | :--- |
| **Data Leakage trên Outbound** | **CAO** | Các trường `CRS_ARR_TIME`, `ARR_DELAY`, `TAXI_IN` của chuyến outbound xuất hiện trước thời điểm bay | Áp dụng nghiêm ngặt điểm cắt $T_{\text{cutoff}} = \text{CRS\_DEP\_TIME} - 2\text{h}$ trên dữ liệu `outbound_atl`; kích hoạt bộ lọc loại trừ triệt để trong `src/data/leakage_rules.py`. |
| **Phá vỡ tính tương thích ngược của Optimizer** | **TRUNG BÌNH** | Hàm xếp cổng hiện tại chỉ nhận đầu vào từ chuyến đến ($A_{\text{pred}}$), nếu ép buộc nhận thêm $D_{\text{pred}}$ sẽ làm sập các bài test cũ | Thiết kế cờ `dual_core_gate_enabled = False` theo mặc định. Khi tắt, bộ giải hoạt động 100% như hệ thống cũ. |
| **Bùng nổ thời gian giải CP-SAT** | **TRUNG BÌNH** | Khoảng đỗ cổng $[A_{\text{pred}}, D_{\text{pred}}]$ thay đổi độ dài động cho từng chuyến, làm tăng mật độ giao cắt khoảng thời gian (Interval overlaps) | Giữ nguyên quy định ngân sách trần thời gian tường ($T = 2.0$s) và cơ chế warm-start sang Simulated Annealing khi CP-SAT chạm ngưỡng giới hạn. |
| **Xung đột định danh Model Registry** | **THẤP** | Trùng lặp mã định danh giữa mô hình Arrival và Departure | Đặt prefix bắt buộc: `departure_linear_*`, `departure_xgboost_*`, `departure_p4_*`. |

### 7.2. Đề xuất Kiến trúc ADR (Architectural Decision Record)

#### **ADR-001: Kiến trúc Dual Core Gate Optimization Decoupling**
* **Trạng thái**: Đề xuất (Proposed)
* **Quyết định thiết kế**:
  1. Tách biệt hai tác vụ máy học:
     - `ModelTask.CORE_ARRIVAL`: $X_{\text{arr}} \rightarrow \Delta T_{\text{arr}}$ (`ARR_DELAY` signed minutes).
     - `ModelTask.CORE_DEPARTURE`: $X_{\text{dep}} \rightarrow \Delta T_{\text{dep}}$ (`DEP_DELAY` signed minutes).
  2. Cơ chế ghép nối chu kỳ quay đầu máy bay:
     $$\text{Gate Interval} = [A_{\text{pred}}, D_{\text{realized}} + B_{\text{risk}}]$$
     Trong đó:
     $$A_{\text{pred}} = A_{\text{sched}} + \Delta T_{\text{arr}}$$
     $$D_{\text{target}} = D_{\text{sched}} + \Delta T_{\text{dep}}$$
     $$D_{\text{realized}} = \max(D_{\text{target}}, A_{\text{pred}} + T_{\text{turnaround}})$$
  3. Cơ chế kích hoạt tính năng an toàn (Feature Flag):
     - Biến cờ `dual_core_gate_enabled: bool = False` trong `GateOptimizationConfig`.
     - Nếu `False`: Sử dụng cơ chế Synthetic Turn truyền thống ($D_{\text{sched}} = A_{\text{sched}} + T_{\text{dwell}}$).
     - Nếu `True`: Đọc cặp dự báo thực tế từ cả hai mô hình Core.
  4. Quyền Downstream: Mô hình `CORE_DEPARTURE` chỉ được cấp `downstream_eligible = True` sau khi vượt qua bài kiểm toán phân phối và kiểm định không rò rỉ dữ liệu.

---

## 8. Kết luận Kiểm toán Quality Gate P0

* **Trạng thái Phase P0**: **`PASS`**
* **Điều kiện bắt đầu Phase P1**: **ĐỦ ĐIỀU KIỆN (ELIGIBLE)**
* **Hành động tiếp theo**: Dừng lại theo đúng yêu cầu. Sẵn sàng nhận chỉ thị bước vào Phase P1 khi người dùng yêu cầu.
