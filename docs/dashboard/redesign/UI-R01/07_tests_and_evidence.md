# UI-R01 — 07. TEST SPECIFICATIONS, EXECUTION EVIDENCE & REGRESSION AUDIT

## 1. MỤC TIÊU KIỂM THỬ

Mọi thay đổi trong Phase UI-R01 v2.0 đều phải được bảo vệ bằng test tự động độc lập, không dựa trên niềm tin hay kiểm tra bằng mắt thường. Báo cáo này ghi lại chi tiết:
1. Đặc tả 24 ca kiểm thử mới (`R01-T01` đến `R01-T24`).
2. Kết quả thực thi bộ test mới.
3. Kết quả chạy toàn bộ test suite dashboard (147 tests).
4. Kết quả chạy bộ hồi quy pipeline P07–P09 (89 tests).

---

## 2. ĐẶC TẢ 24 CA KIỂM THỬ MỚI (TEST MATRIX)

| Test ID | Tên hàm kiểm thử | Mục tiêu xác minh & Tiêu chí PASS | Kết quả |
| :--- | :--- | :--- | :--- |
| **R01-T01** | `test_r01_t01_prediction_missing_metadata_defaults_to_na` | Thiếu carrier/origin/dest phải trả về `"N/A"`, không được điền `"DL"`, `"ORD"`, `"ATL"`. | **PASS** |
| **R01-T02** | `test_r01_t02_prediction_missing_sched_arr_time_is_none` | Thiếu giờ hạ cánh phải trả về `None`, không được điền phút `480` (08:00). | **PASS** |
| **R01-T03** | `test_r01_t03_prediction_unmatched_flight_id_gives_na_metadata` | Flight ID không có trong schedule manifest phải cho metadata `"N/A"` và `None`. | **PASS** |
| **R01-T04** | `test_r01_t04_prediction_exact_zero_delay_preserved` | Giá trị dự báo `0.0` phút trễ phải được bảo toàn chính xác, không bị falsy drop. | **PASS** |
| **R01-T05** | `test_r01_t05_prediction_cross_scenario_guard` | Khi `scenario_id` bị lệch giữa dòng dữ liệu và active scenario, phải raise `ValueError`. | **PASS** |
| **R01-T06** | `test_r01_t06_monte_carlo_mode_a_missing_metrics_are_none` | Mode A thiếu trường trong dict phải trả về `None`, không được fallback số giả `1469.17`. | **PASS** |
| **R01-T07** | `test_r01_t07_monte_carlo_mode_b_missing_metrics_are_none` | Mode B thiếu trường trong dict phải trả về `None`, không được fallback số giả `130.73` / `2.556`. | **PASS** |
| **R01-T08** | `test_r01_t08_monte_carlo_mode_c_oracle_academic_notes` | Mode C phải ghi rõ là Realized Greedy Oracle Baseline, không phải nghiệm toàn cục. | **PASS** |
| **R01-T09** | `test_r01_t09_monte_carlo_mode_c_is_not_deployable` | Thuộc tính `is_deployable` của Mode C bắt buộc phải là `False`. | **PASS** |
| **R01-T10** | `test_r01_t10_validate_single_solver_dataframe_filters_to_target` | Lọc sạch 1.500 dòng đa solver về đúng 500 dòng của solver được yêu cầu. | **PASS** |
| **R01-T11** | `test_r01_t11_validate_single_solver_dataframe_single_solver_unchanged` | Dữ liệu đơn solver đi qua hàm lọc mà không bị biến dạng. | **PASS** |
| **R01-T12** | `test_r01_t12_cost_distribution_figure_guards_against_mixing` | CHART-12 Plotly histogram tự động lọc solver, ngăn ngừa trộn đa phân phối. | **PASS** |
| **R01-T13** | `test_r01_t13_ecdf_figure_guards_against_mixing` | CHART-13 Plotly ECDF tự động lọc solver, bảo toàn xác suất rủi ro đuôi. | **PASS** |
| **R01-T14** | `test_r01_t14_boxplot_and_convergence_guard_against_mixing` | CHART-14 và CHART-15 chạy đúng trên 500 mẫu, không bị kéo dài thành 1.500 mẫu. | **PASS** |
| **R01-T15** | `test_r01_t15_mc_drilldown_respects_solver_name` | Drill-down kịch bản trả về đúng kết quả của solver được yêu cầu (CPSat). | **PASS** |
| **R01-T16** | `test_r01_t16_scientific_validator_strict_contamination_rejection` | `ScientificValidator` kích hoạt `IncompatibleComparisonError` khi cấm trộn dữ liệu. | **PASS** |
| **R01-T17** | `test_r01_t17_control_tower_nominal_conflicts_dynamic` | Xung đột danh định được tính toán động (kịch bản chuẩn 120 chuyến có đúng 0 va chạm). | **PASS** |
| **R01-T18** | `test_r01_t18_control_tower_turnaround_slack_dynamic` | Phân phối slack quay vòng được tính động từ thuộc tính `turnaround_slack_min`. | **PASS** |
| **R01-T19** | `test_r01_t19_active_run_mismatch_or_none_defaults_to_not_run` | Khi chưa có run hoặc run lệch kịch bản, kết quả trả về `NOT_RUN` an toàn. | **PASS** |
| **R01-T20** | `test_r01_t20_context_bar_defaults_are_honest` | Giá trị mặc định của `render_context_bar` là CANONICAL BASELINE và `is_optimal=False`. | **PASS** |
| **R01-T21** | `test_r01_t21_flight_intelligence_handles_none_sched_arr_time` | Sắp xếp và format bảng Flight Intelligence không crash khi `sched_arr_time_min=None`. | **PASS** |
| **R01-T22** | `test_r01_t22_flight_prediction_view_immutability` | `FlightPredictionView` là frozen dataclass, ngăn chặn chỉnh sửa sau khi tạo. | **PASS** |
| **R01-T23** | `test_r01_t23_robustness_view_immutability_and_none_support` | `RobustnessView` hỗ trợ `None` cho các metrics khuyết thiếu và bất biến. | **PASS** |
| **R01-T24** | `test_r01_t24_optimization_lab_benchmark_summary_rows` | Tổng hợp benchmark trên Optimization Lab tính trung bình thực tế, không hardcode. | **PASS** |

---

## 3. BẰNG CHỨNG THỰC THI PYTEST (LOGS & EVIDENCE)

### 3.1. Thực thi Bộ Kiểm thử Mới (test_ui_r01_data_integrity.py)
```text
D:\Study\Code\Python\Aelous\.venv\Scripts\python -m pytest tests/dashboard/test_ui_r01_data_integrity.py -v
============================= test session starts =============================
platform win32 -- Python 3.11.15, pytest-9.1.1, pluggy-1.6.0
rootdir: D:\Study\Code\Python\Aelous
configfile: pytest.ini
plugins: anyio-4.15.1
collected 24 items

tests/dashboard/test_ui_r01_data_integrity.py::test_r01_t01_prediction_missing_metadata_defaults_to_na PASSED [  4%]
tests/dashboard/test_ui_r01_data_integrity.py::test_r01_t02_prediction_missing_sched_arr_time_is_none PASSED [  8%]
tests/dashboard/test_ui_r01_data_integrity.py::test_r01_t03_prediction_unmatched_flight_id_gives_na_metadata PASSED [ 12%]
tests/dashboard/test_ui_r01_data_integrity.py::test_r01_t04_prediction_exact_zero_delay_preserved PASSED [ 16%]
tests/dashboard/test_ui_r01_data_integrity.py::test_r01_t05_prediction_cross_scenario_guard PASSED [ 20%]
tests/dashboard/test_ui_r01_data_integrity.py::test_r01_t06_monte_carlo_mode_a_missing_metrics_are_none PASSED [ 25%]
tests/dashboard/test_ui_r01_data_integrity.py::test_r01_t07_monte_carlo_mode_b_missing_metrics_are_none PASSED [ 29%]
tests/dashboard/test_ui_r01_data_integrity.py::test_r01_t08_monte_carlo_mode_c_oracle_academic_notes PASSED [ 33%]
tests/dashboard/test_ui_r01_data_integrity.py::test_r01_t09_monte_carlo_mode_c_is_not_deployable PASSED [ 37%]
tests/dashboard/test_ui_r01_data_integrity.py::test_r01_t10_validate_single_solver_dataframe_filters_to_target PASSED [ 41%]
tests/dashboard/test_ui_r01_data_integrity.py::test_r01_t11_validate_single_solver_dataframe_single_solver_unchanged PASSED [ 45%]
tests/dashboard/test_ui_r01_data_integrity.py::test_r01_t12_cost_distribution_figure_guards_against_mixing PASSED [ 50%]
tests/dashboard/test_ui_r01_data_integrity.py::test_r01_t13_ecdf_figure_guards_against_mixing PASSED [ 54%]
tests/dashboard/test_ui_r01_data_integrity.py::test_r01_t14_boxplot_and_convergence_guard_against_mixing PASSED [ 58%]
tests/dashboard/test_ui_r01_data_integrity.py::test_r01_t15_mc_drilldown_respects_solver_name PASSED [ 62%]
tests/dashboard/test_ui_r01_data_integrity.py::test_r01_t16_scientific_validator_strict_contamination_rejection PASSED [ 66%]
tests/dashboard/test_ui_r01_data_integrity.py::test_r01_t17_control_tower_nominal_conflicts_dynamic PASSED [ 70%]
tests/dashboard/test_ui_r01_data_integrity.py::test_r01_t18_control_tower_turnaround_slack_dynamic PASSED [ 75%]
tests/dashboard/test_ui_r01_data_integrity.py::test_r01_t19_active_run_mismatch_or_none_defaults_to_not_run PASSED [ 79%]
tests/dashboard/test_ui_r01_data_integrity.py::test_r01_t20_context_bar_defaults_are_honest PASSED [ 83%]
tests/dashboard/test_ui_r01_data_integrity.py::test_r01_t21_flight_intelligence_handles_none_sched_arr_time PASSED [ 87%]
tests/dashboard/test_ui_r01_data_integrity.py::test_r01_t22_flight_prediction_view_immutability PASSED [ 91%]
tests/dashboard/test_ui_r01_data_integrity.py::test_r01_t23_robustness_view_immutability_and_none_support PASSED [ 95%]
tests/dashboard/test_ui_r01_data_integrity.py::test_r01_t24_optimization_lab_benchmark_summary_rows PASSED [100%]

============================= 24 passed in 1.92s ==============================
```

### 3.2. Thực thi Toàn bộ Dashboard Pytest Suite (147 Tests)
```text
D:\Study\Code\Python\Aelous\.venv\Scripts\python -m pytest tests/dashboard/ -v
============================= test session starts =============================
platform win32 -- Python 3.11.15, pytest-9.1.1, pluggy-1.6.0
rootdir: D:\Study\Code\Python\Aelous
configfile: pytest.ini
plugins: anyio-4.15.1
collected 147 items

tests/dashboard/test_final_acceptance.py .........................       [ 17%]
tests/dashboard/test_foundation.py ..................                    [ 29%]
tests/dashboard/test_gate_operations.py ............................     [ 48%]
tests/dashboard/test_lab_and_robustness.py ..........................    [ 65%]
tests/dashboard/test_services.py ......                                  [ 70%]
tests/dashboard/test_ui_components.py ....................               [ 83%]
tests/dashboard/test_ui_r01_data_integrity.py ........................   [100%]

====================== 147 passed, 3 warnings in 10.70s =======================
```

### 3.3. Thực thi Bộ Kiểm thử Hồi quy Pipeline P07–P09 (89 Tests)
```text
D:\Study\Code\Python\Aelous\.venv\Scripts\python -m pytest tests/test_native_dual_core_pipeline_p07.py tests/test_ml_research_validation_p08.py tests/test_monte_carlo_robustness_p09.py -v
============================= test session starts =============================
platform win32 -- Python 3.11.15, pytest-9.1.1, pluggy-1.6.0
rootdir: D:\Study\Code\Python\Aelous
configfile: pytest.ini
plugins: anyio-4.15.1
collected 89 items

tests/test_native_dual_core_pipeline_p07.py ................................... [ 39%]
tests/test_ml_research_validation_p08.py ..........................             [ 68%]
tests/test_monte_carlo_robustness_p09.py ............................           [100%]

======================= 89 passed, 3 warnings in 7.46s ========================
```

---

## 4. KẾT LUẬN KIỂM ĐỊNH KỸ THUẬT

1. **Tỷ lệ vượt qua kiểm thử:** **100%** (147/147 dashboard tests PASS, 89/89 backend regression tests PASS).
2. **Tổng số ca kiểm thử hợp lệ:** **236 tests**.
3. **Số ca kiểm thử thất bại:** **0**.
4. **Hồi quy (Regression):** Không có bất kỳ hồi quy nào trên toàn bộ hệ thống pipeline ML hay optimization.
