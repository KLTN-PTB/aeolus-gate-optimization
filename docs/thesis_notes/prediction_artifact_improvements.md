# Đề Xuất Cải Thiện & Chuẩn Hóa Tệp Đầu Ra Dự Báo (Prediction Artifacts)
### Phục vụ Bài toán Tối ưu hóa Tái phân bổ Cổng đỗ Tàu bay (CP-SAT / SA)
*Dự án: Aeolus Gate Optimization — Khóa luận tốt nghiệp CNTT-KLCN168*

---

## 1. Bối cảnh & Thực trạng

Hiện tại, thư mục `src/artifacts/predictions/` chứa các tệp đầu ra dự báo máy học (ML) phục vụ bài toán xếp cổng:
- `full_turn_unified_predictions_for_cpsat.parquet` (1,000,000 dòng, 17 cột)
- `atl_gate_scheduling_input_2024.parquet` (68,009 dòng, 14 cột)
- Các tệp đơn nhiệm: `arrival_classification`, `arrival_regression`, `departure_classification`, `departure_regression`, `arrival_unified`, `departure_unified`.

Bộ điều hợp [oof_adapter.py](file:///d:/Documents/BaiTap/KhoaLuanCuNhan/aeolus-gate-optimization/src/optimization/oof_adapter.py) đã được nâng cấp để có thể tự động nhận diện và trích xuất kịch bản giải thành công bằng CP-SAT. Tuy nhiên, để bài toán tối ưu xếp cổng đạt **chất lượng vận hành thực tế cao nhất** và **chuẩn mực phương pháp luận cho báo cáo Khóa luận**, các tệp dự báo cần được hoàn thiện theo các nội dung dưới đây.

---

## 2. Các Hạng mục Cần Cải Thiện Chi Tiết

### 2.1. Nâng độ mịn thời gian từ Giờ sang Phút (Minute-level Granularity)
* **Thực trạng:** 
  Tệp hiện tại chỉ chứa `DEP_HOUR` và `ARR_HOUR` (số nguyên `0..23`). 
* **Vấn đề phát sinh:**
  Khi quy đổi sang phút (`hour * 60`), toàn bộ các chuyến bay trong cùng một giờ (ví dụ từ 08:00 đến 08:59) đều bị gán mốc giờ đến là 08:00 (phút thứ 480). Điều này tạo ra hiện tượng **quá tải ảo (artificial congestion spike)** tại đầu mỗi giờ, làm méo mó biểu đồ chiếm dụng cổng và khiến bài toán trông khó hơn thực tế.
* **Giải pháp cải thiện:**
  - Bổ sung lại cột giờ lịch trình gốc theo phút:
    - Hoặc định dạng chuỗi 4 chữ số `CRS_ARR_TIME` (vd `"0825"` = 08:25) và `CRS_DEP_TIME` (vd `"1440"` = 14:40).
    - Hoặc cột số nguyên phút kể từ 00:00: `sched_arr_min` và `sched_dep_min`.
* **Lợi ích:** Biểu đồ chiếm dụng cổng (Gate Occupancy Chart) rải đều tự nhiên, thời gian giải CP-SAT ổn định và sát thực tế sân bay.

---

### 2.2. Bổ sung mã liên kết chuỗi xoay vòng tàu bay (`chain_id` / `chain_group_id`)
* **Thực trạng:**
  Tên tệp là `full_turn` (turnaround), nhưng mỗi dòng hiện tại là một chặng bay riêng biệt (`ORIGIN` $\rightarrow$ `DEST`). Tệp thiếu thông tin định danh máy bay (`tail_number`) hoặc mã chuỗi hành trình (`chain_id`).
* **Vấn đề phát sinh:**
  Bộ giải CP-SAT buộc phải xem mỗi chuyến bay đến và đi là các đối tượng rời rạc. Solver chưa thể liên kết chuyến bay hạ cánh và chuyến bay cất cánh tiếp theo của **cùng một tàu bay** tại sân bay ATL để giữ nguyên cùng một cổng đỗ (Turnaround Coupling Constraint).
* **Giải pháp cải thiện:**
  - Khi xuất tệp dự báo, thực hiện JOIN với bảng `src/data/processed/flight_chain_reconstructed_v1/chain_members` đã được tái thiết kế ở Tuần 2 để lấy trường `chain_id` (hoặc `chain_group_id`).
* **Lợi ích:** Kích hoạt 100% các ràng buộc quay đầu máy bay trong [cp_sat_solver.py](file:///d:/Documents/BaiTap/KhoaLuanCuNhan/aeolus-gate-optimization/src/optimization/cp_sat_solver.py), nâng cao tính thực tiễn và chiều sâu học thuật của đề tài.

---

### 2.3. Giữ lại mã định danh chuẩn `flight_key` (Canonical Key)
* **Thực trạng:**
  Tệp đang dùng `flight_idx` (chỉ số số nguyên `0..999,999` phát sinh từ index phân chia tập train/test).
* **Vấn đề phát sinh:**
  Mất tính truy vết (traceability) ngược về chuyến bay thực tế trong bộ dữ liệu gốc của Cục Thống kê Vận tải Hoa Kỳ (BTS). Khó kiểm tra chéo hãng bay, số hiệu hiệu chuyến bay khi biểu diễn biểu đồ Gantt phân bổ cổng.
* **Giải pháp cải thiện:**
  - Giữ lại cột `flight_key` gốc (ví dụ: `"2024_01_01_DL_1234"`).
* **Lợi ích:** Dễ dàng kiểm toán (audit), đối soát và trực quan hóa kết quả phân bổ cổng với đầy đủ thông tin thực tế.

---

### 2.4. Đóng gói sẵn các tệp kịch bản mô phỏng theo ngày (`gate_scheduling_scenarios`)
* **Thực trạng:**
  Tệp `full_turn_unified_predictions_for_cpsat.parquet` có kích thước **1.000.000 dòng** bao gồm 156 sân bay toàn nước Mỹ suốt 12 tháng. Khi chạy thực nghiệm tối ưu, việc load 15MB với 1 triệu dòng vào bộ nhớ rồi mới lọc ra 162 chuyến của ATL là không tối ưu.
* **Giải pháp cải thiện:**
  - Tạo một thư mục kịch bản chuyên dụng: `src/artifacts/scenarios/` (hoặc `data/scenarios/`) chứa các kịch bản chuẩn cho sân bay ATL:
    1. `atl_2024_01_01_typical_day.parquet` (~162 chuyến — Ngày thông thường).
    2. `atl_2024_07_04_peak_holiday.parquet` (~250 chuyến — Ngày lễ cao điểm hè).
    3. `atl_2024_01_15_winter_disruption.parquet` (Ngày có tỷ lệ trễ dự báo cao do thời tiết).
* **Lợi ích:** Phục vụ trực tiếp cho Chương Thực nghiệm và Đánh giá (chạy so sánh hiệu năng Greedy vs CP-SAT vs CP-SAT+SA qua nhiều kịch bản điển hình).

---

### 2.5. Tích hợp loại tàu bay (`aircraft_type`) và thời gian quay đầu (`turnaround_time_min`)
* **Thực trạng:**
  Hiện tại tệp chưa có thông tin kích cỡ thân máy bay và thời gian quay đầu tối thiểu.
* **Giải pháp cải thiện:**
  - Tích hợp hàm sinh dữ liệu mô phỏng từ [src/simulation/simulate_airport.py](file:///d:/Documents/BaiTap/KhoaLuanCuNhan/aeolus-gate-optimization/src/simulation/simulate_airport.py) để gán:
    - `aircraft_type`: `"NARROWBODY"` (~85%) hoặc `"WIDEBODY"` (~15%).
    - `turnaround_time_min`: 35–45 phút đối với Narrowbody, 60–90 phút đối với Widebody.
* **Lợi ích:** Kích hoạt ràng buộc tương thích kích thước cổng (Gate Size Compatibility) — tàu bay thân rộng chỉ được đỗ ở các cổng có khả năng đón thân rộng.

---

## 3. Lược Đồ Dữ Liệu Mục Tiêu Đề Xuất (Target Schema Specification)

Một tệp kịch bản đầu vào lý tưởng cho bộ giải CP-SAT và Simulated Annealing nên có cấu trúc như sau:

| Tên Cột | Kiểu Dữ Liệu | Nguồn / Ý Nghĩa | Mô Tả |
| :--- | :---: | :---: | :--- |
| `flight_key` | `string` | Aeolus Canonical | Mã định danh chuẩn của chuyến bay (VD: `"2024_01_01_DL_1025"`) |
| `airport` | `string` | BTS / Filter | Sân bay lập lịch (VD: `"ATL"`) |
| `direction` | `string` | Xác định hướng | `"ARR"` (chiều đến) hoặc `"DEP"` (chiều đi) |
| `sched_time_min` | `int16` | Quy đổi từ CRS | Phút lịch trình tính từ 00:00 (`0..1440`) |
| `p_delay` | `float32` | **ML Model Output** | Xác suất trễ $\ge 15$ phút từ mô hình phân loại (`0.0..1.0`) |
| `delay_est_min` | `float32` | **ML Model Output** | Mức trễ kỳ vọng (phút) từ mô hình hồi quy (Dual Prediction) |
| `chain_group_id` | `string` (nullable)| Reconstructed Chain | Mã chuỗi tàu bay để ghép cặp chuyến đến và đi liên tiếp |
| `aircraft_type` | `string` | Simulation | Loại tàu bay: `"NARROWBODY"` hoặc `"WIDEBODY"` |
| `turnaround_time_min` | `int16` | Vận hành / Chuẩn | Thời gian quay đầu tối thiểu tại cổng (35–60 phút) |
| `dwell_time_min` | `int16` | Mặc định | Thời gian đỗ cổng dự kiến nếu không ghép cặp |

> **Nguyên tắc an toàn (Simulation Safety Guard):** Tuyệt đối **KHÔNG** đưa nhãn trễ thực tế `y_true_arr_delay_min` hoặc `ARR_DELAY` vào tệp kịch bản này để đảm bảo tính khách quan và chống rò rỉ dữ liệu.

---

## 4. Kế Hoạch Triển Khai (Action Plan)

1. **Bước 1 (Ưu tiên cao):** Tạo script trích xuất `scripts/export_gate_scenarios.py` đọc từ `full_turn_unified_predictions_for_cpsat.parquet` kết hợp bổ sung `flight_key` và tính đúng `sched_time_min`.
2. **Bước 2 (Ưu tiên cao):** Trích xuất tối thiểu 3 kịch bản ngày chuẩn cho sân bay ATL (Tháng 1, Tháng 7, Tháng 10/2024) lưu vào `src/artifacts/scenarios/`.
3. **Bước 3 (Ưu tiên trung bình):** Thực hiện JOIN bổ sung `chain_id` từ `chain_members` để hoàn thiện bài toán Turnaround Gate Assignment.
