# UI-R01 — 06. COMPREHENSIVE RECORD OF FILES CHANGED

## 1. TỔNG HỢP DANH MỤC THAY ĐỔI

Trong Phase UI-R01 v2.0, chỉ có 10 tập tin mã nguồn giao diện/adapter/contract hiện hữu và 1 tập tin test mới được điều chỉnh hoặc khởi tạo. Tuyệt đối không thay đổi mã nguồn backend nghiên cứu thuộc `src/`.

---

## 2. CHI TIẾT CÁC THAY ĐỔI THEO TẬP TIN

### 1. `dashboard/core/contracts.py`
- **Mục đích:** Hỗ trợ giá trị khuyết thiếu trung thực, loại bỏ ép kiểu dummy.
- **Thay đổi chính:**
  - `FlightPredictionView.sched_arr_time_min`: Đổi kiểu từ `int` thành `Optional[int] = None`.
  - `FlightPredictionView.carrier`, `origin`, `destination`: Mặc định thành `"N/A"`.
  - Cập nhật hàm `__post_init__` để kiểm tra khoảng giá trị `sched_arr_time_min` khi trường này không phải `None`.
  - `RobustnessView`: Cho phép các chỉ số chi phí và xác suất nhận `Optional[float] = None`.

### 2. `dashboard/core/validation.py`
- **Mục đích:** Bổ sung validator bảo vệ chống ô nhiễm đa thuật toán trong Monte Carlo.
- **Thay đổi chính:**
  - Thêm phương thức `ScientificValidator.validate_single_solver_dataframe(cls, df, target_solver="CPSat", allow_filter=True)`.
  - Nếu phát hiện nhiều solver trong DataFrame và `allow_filter=False`, kích hoạt `IncompatibleComparisonError`.

### 3. `dashboard/adapters/prediction_adapter.py`
- **Mục đích:** Loại bỏ hoàn toàn việc bịa đặt metadata (DL, ORD, ATL, 480); sửa lỗi falsy zero; thêm cross-scenario guard.
- **Thay đổi chính:**
  - Viết lại hàm `adapt_prediction_row_to_view`.
  - Loại bỏ các chuỗi gán cứng `"DL"`, `"ORD"`, `"ATL"`, `480`. Nếu thiếu, trả về `"N/A"` và `None`.
  - Kiểm tra `is not None` để bảo toàn giá trị độ trễ thực tế `0.0`.
  - Bổ sung rào chắn so khớp kịch bản `scenario_id`.

### 4. `dashboard/adapters/monte_carlo_adapter.py`
- **Mục đích:** Loại bỏ số liệu hardcoded fallback; chuẩn hóa chú thích học thuật Mode C; hỗ trợ lọc solver trong drill-down.
- **Thay đổi chính:**
  - Trong `adapt_monte_carlo_to_views`: Xóa bỏ các fallback `1469.17`, `130.73`, `2.556`. Nếu thiếu trường trong JSON thì gán `None`.
  - Mode C: Đổi chú thích học thuật thành `Realized Greedy Oracle Baseline`, khẳng định không phải nghiệm tối ưu toán học toàn cục.
  - Trong `adapt_mc_scenario_drilldown`: Thêm tham số `solver_name: Optional[str] = "CPSat"`. Khi tìm kiếm dòng kịch bản trong DataFrame đa solver, lọc đúng dòng của solver được yêu cầu.

### 5. `dashboard/components/context_bar.py`
- **Mục đích:** Loại bỏ trạng thái mặc định sai sự thật "TỐI ƯU TUYỆT ĐỐI (CP-SAT)".
- **Thay đổi chính:**
  - Đổi default arguments: `solver_status_text="LỊCH CƠ SỞ (CANONICAL BASELINE)"`, `is_optimal=False`.

### 6. `dashboard/visualizers/robustness_charts.py`
- **Mục đích:** Ngăn chặn việc trộn dữ liệu 3 thuật toán (1.500 dòng) vào các biểu đồ phân phối và vết hội tụ.
- **Thay đổi chính:**
  - Bổ sung hàm helper `validate_single_solver_dataframe`.
  - Cập nhật cả 4 hàm biểu đồ (`create_mc_cost_distribution_figure`, `create_mc_ecdf_figure`, `create_mc_boxplot_figure`, `create_mc_convergence_figure`) với tham số `solver_name: Optional[str] = "CPSat"`.
  - Tự động lọc DataFrame đầu vào theo solver trước khi tính toán histogram, ECDF, boxplot, hoặc running mean.

### 7. `dashboard/pages/page_01_control_tower.py`
- **Mục đích:** Tính toán động xung đột danh định và slack quay vòng; hiển thị trung thực `CHƯA CHẠY [NOT_RUN]` cho nghiệm tối ưu.
- **Thay đổi chính:**
  - Kiểm tra `active_run` trong `st.session_state`. Nếu chưa chạy hoặc thuộc scenario khác, Context Bar hiển thị `LỊCH DANH ĐỊNH GỐC (NOMINAL)` và `is_optimal=False`.
  - Thẻ KPI "XUNG ĐỘT TĨNH": Tính toán động bằng cách quét va chạm giữa các chuyến bay trên cùng `nominal_gate_id`.
  - Thẻ KPI "TỐI ƯU CP-SAT" & "CỔNG ĐỖ TỪ XA": Nếu chưa chạy, hiển thị giá trị `CHƯA CHẠY [NOT_RUN]` và badge `[CHƯA CHẠY]`.
  - Thẻ "TRỄ ĐẾN DỰ BÁO": Loại bỏ fallback `18.4 min` và `38.2%`; nếu thiếu file hiển thị `N/A`.
  - Khối HTML "TURNAROUND SLACK HEALTH": Viết lại bằng mã động tính toán từ thuộc tính `turnaround_slack_min` của tập `flights`.

### 8. `dashboard/pages/page_02_flight_intelligence.py`
- **Mục đích:** Đổi Context Bar thành `DỰ BÁO HỌC MÁY (ML INFERENCE)`, `is_optimal=False`; xử lý an toàn `sched_arr_time_min=None`.
- **Thay đổi chính:**
  - Sắp xếp và định dạng giờ hạ cánh an toàn với `sched_arr_time_min` có thể là `None` (hiển thị `"N/A"`).
  - Bổ sung caption khai báo tính chất minh họa mô hình toán học của các cặp quay vòng mẫu trong Tab B.

### 9. `dashboard/pages/page_04_optimization_lab.py`
- **Mục đích:** Đổi Context Bar thành `is_optimal=False`; liên kết 4 thẻ KPI của 4 solver trực tiếp với dữ liệu benchmark thực tế.
- **Thay đổi chính:**
  - Xóa bỏ việc ghi cứng `"130.00 pts"` và các runtime giả (`1.8 ms`, `65.2 ms`, `182.4 ms`, `68.5 ms`) trên cả 4 thẻ KPI.
  - Sử dụng hàm tra cứu động `_get_solver_kpi` từ bảng aggregate `summary_rows` để hiển thị đúng chi phí thực (`323.50 pts`, `530.19 pts`, `497.56 pts`, `489.14 pts`) và runtime thực của từng solver.

### 10. `dashboard/pages/page_05_robustness_lab.py`
- **Mục đích:** Đổi Context Bar thành `is_optimal=False`; bổ sung bộ chọn solver; lọc DataFrame truyền vào biểu đồ và so sánh.
- **Thay đổi chính:**
  - Thêm `selected_solver = st.selectbox(...)` với mặc định là `"CPSat"`.
  - Lọc sạch `fixed_sub` và `recourse_sub` theo solver trước khi truyền vào 4 biểu đồ Plotly, `compute_paired_differences`, và `adapt_mc_scenario_drilldown`.
  - Xóa bỏ các fallback `1,469.2 pts`, `130.7 pts`, `500 / 500` trên các thẻ KPI; hiển thị `N/A` nếu thiếu dữ liệu.
  - Sửa nhãn sai "SỐ LƯỢT ĐỔI CỔNG TRUNG VỊ" thành nhãn đúng "SỐ LƯỢT ĐỔI CỔNG TRUNG BÌNH".

### 11. `tests/dashboard/test_ui_r01_data_integrity.py`
- **Mục đích:** Tạo bộ kiểm thử độc lập gồm 24 test cases (`R01-T01` đến `R01-T24`) để bảo vệ dữ liệu và ranh giới khoa học.
