# UI-R05: Golden Test Suite & Verification Results

## 1. Tổng Quan Bộ Kiểm Thử
Bộ kiểm thử vàng `tests/dashboard/test_ui_r05_gate_operations_gantt.py` bao gồm **35 ca kiểm thử đơn vị và tích hợp** (vượt chỉ tiêu tối thiểu 28 test theo yêu cầu của phase UI-R05).

Toàn bộ 35 tests được thiết kế để bảo vệ nghiêm ngặt các sửa đổi liên quan đến phân loại vị trí đỗ, ngữ nghĩa lọc, toán học khoảng thời gian nửa mở, và kiểm chứng độc lập.

## 2. Danh Mục Chi Tiết 35 Ca Kiểm Thử

| Mã Test | Tên Hàm Kiểm Thử | Mục Tiêu & Tiêu Chí Kiểm Tra | Kết Quả |
| :--- | :--- | :--- | :---: |
| **R05-T01** | `test_r05_t01_issue_r00_07_apron_never_classified_as_concourse_a` | Khắc phục ISSUE-R00-07: `APRON_*` luôn được xếp vào `OVERFLOW`, không bao giờ là Concourse A. | **PASSED** |
| **R05-T02** | `test_r05_t02_issue_r00_07_remote_distinct_from_concourse_a_and_overflow` | Khắc phục ISSUE-R00-07: `REMOTE_*` thuộc concourse `REMOTE`, tách biệt khỏi A và OVERFLOW. | **PASSED** |
| **R05-T03** | `test_r05_t03_issue_r00_11_dynamic_gate_counts_canonical_scenario` | Khắc phục ISSUE-R00-11: Số lượng cổng đếm động khớp chính xác kịch bản canonical 120. | **PASSED** |
| **R05-T04** | `test_r05_t04_issue_r00_11_dynamic_gate_counts_p07_dual_core_scenario` | Khắc phục ISSUE-R00-11: Kịch bản P07 hiển thị Concourse A = 5 cổng (loại bỏ hardcode 15). | **PASSED** |
| **R05-T05** | `test_r05_t05_concourse_helper_contact_gates_t_and_a` | Helper `_get_gate_concourse` nhận diện chính xác các cổng tiếp xúc T và A. | **PASSED** |
| **R05-T06** | `test_r05_t06_concourse_helper_remote_and_apron` | Helper `_get_gate_concourse` tách bạch chính xác bãi từ xa và bãi tràn apron. | **PASSED** |
| **R05-T07** | `test_r05_t07_concourse_helper_unrecognized_gates_graceful` | Xử lý an toàn khi gặp mã cổng không thuộc các quy chuẩn thông thường (`UNKNOWN_GROUP`). | **PASSED** |
| **R05-T08** | `test_r05_t08_filter_concourse_none_returns_all` | Ngữ nghĩa bộ lọc: `concourse_filter=None` giữ lại tất cả các chuyến bay. | **PASSED** |
| **R05-T09** | `test_r05_t09_filter_concourse_empty_list_returns_none` | Ngữ nghĩa bộ lọc: `concourse_filter=[]` trả về danh sách rỗng (chọn rỗng = không hiển thị). | **PASSED** |
| **R05-T10** | `test_r05_t10_filter_concourse_single_selection` | Ngữ nghĩa bộ lọc: Chọn concourse cụ thể chỉ trả về chuyến bay trong concourse đó. | **PASSED** |
| **R05-T11** | `test_r05_t11_filter_carrier_all_and_specific` | Lọc theo hãng hàng không: `ALL` trả về tất cả, hãng cụ thể chỉ trả về chuyến bay của hãng đó. | **PASSED** |
| **R05-T12** | `test_r05_t12_filter_resource_type_contact` | Lọc loại tài nguyên `CONTACT_GATE` chỉ giữ lại các cổng tiếp xúc. | **PASSED** |
| **R05-T13** | `test_r05_t13_filter_resource_type_remote` | Lọc loại tài nguyên `FINITE_REMOTE_STAND` chỉ giữ lại các bãi đỗ từ xa. | **PASSED** |
| **R05-T14** | `test_r05_t14_filter_resource_type_overflow` | Lọc loại tài nguyên `UNBOUNDED_OVERFLOW_APRON` chỉ giữ lại bãi đỗ tràn. | **PASSED** |
| **R05-T15** | `test_r05_t15_filter_search_query_substring_match` | Tìm kiếm chuỗi con khớp chính xác mã chuyến bay hoặc số hiệu chuyến bay. | **PASSED** |
| **R05-T16** | `test_r05_t16_filter_strict_intersection_and_logic` | Phép giao nghiêm ngặt: Kết hợp nhiều bộ lọc đồng thời tuân thủ logic AND. | **PASSED** |
| **R05-T17** | `test_r05_t17_time_window_half_open_intersection` | Giao nửa mở: Chuyến bay xuất hiện nếu $[start, release) \cap [W_{start}, W_{end}) > 0$. | **PASSED** |
| **R05-T18** | `test_r05_t18_time_window_flight_arriving_before_window_included` | Chuyến bay đến trước cửa sổ nhưng đang đỗ tại cổng vẫn được hiển thị trong cửa sổ. | **PASSED** |
| **R05-T19** | `test_r05_t19_time_window_flight_departing_before_window_excluded` | Chuyến bay rời cổng trước khi cửa sổ bắt đầu bị loại trừ tuyệt đối. | **PASSED** |
| **R05-T20** | `test_r05_t20_time_window_flight_arriving_at_or_after_window_excluded` | Chuyến bay đến tại hoặc sau biên kết thúc của cửa sổ bị loại trừ đúng quy tắc nửa mở. | **PASSED** |
| **R05-T21** | `test_r05_t21_single_buffer_present_never_double_counted` | Đệm an toàn xuất hiện đúng 1 lần trong thời điểm giải phóng: $release = gate\_out + buffer$. | **PASSED** |
| **R05-T22** | `test_r05_t22_adjacent_intervals_do_not_conflict` | Hai khoảng nửa mở tiếp giáp $[a, b)$ và $[b, c)$ không xảy ra xung đột. | **PASSED** |
| **R05-T23** | `test_r05_t23_overlapping_intervals_do_conflict` | Hai khoảng giao nhau với $\max(s_1, s_2) < \min(e_1, e_2)$ kích hoạt xung đột. | **PASSED** |
| **R05-T24** | `test_r05_t24_pooled_remote_capacity_k_allows_k_concurrent` | Bãi đỗ từ xa sức chứa $K$ cho phép tối đa $K$ chuyến bay đồng thời không xung đột. | **PASSED** |
| **R05-T25** | `test_r05_t25_pooled_remote_capacity_k_detects_k_plus_1_conflict` | Bãi đỗ từ xa sức chứa $K$ phát hiện vi phạm khi có $K+1$ chuyến bay đồng thời. | **PASSED** |
| **R05-T26** | `test_r05_t26_master_gantt_clean_title_no_raw_chart_id` | Tiêu đề biểu đồ Master Gantt không chứa mã kỹ thuật `(CHART-07)`. | **PASSED** |
| **R05-T27** | `test_r05_t27_master_gantt_reversed_gate_order` | Trục Y đảo ngược danh mục để cổng $G\_01$ nằm ở dòng đầu tiên trên cùng. | **PASSED** |
| **R05-T28** | `test_r05_t28_nominal_plan_detects_contact_conflicts` | Kế hoạch danh định gốc phát hiện chính xác các xung đột lịch trình trên cổng tiếp xúc. | **PASSED** |
| **R05-T29** | `test_r05_t29_nominal_plan_provenance_is_schedule_baseline` | Kế hoạch danh định mang provenance `SCHEDULE_BASELINE`. | **PASSED** |
| **R05-T30** | `test_r05_t30_unrun_scenario_does_not_implicitly_solve` | Kịch bản chưa chạy không kích hoạt giải ngầm; giữ nguyên kế hoạch danh định. | **PASSED** |
| **R05-T31** | `test_r05_t31_safe_live_optimization_size_guard` | Bộ giải trực tiếp chặn thực thi và báo lỗi khi kịch bản vượt quá ngưỡng quy mô (150). | **PASSED** |
| **R05-T32** | `test_r05_t32_independent_verifier_valid_cpsat_run` | Trình kiểm chứng độc lập xác nhận lời giải hợp lệ với 0 vi phạm ràng buộc cứng. | **PASSED** |
| **R05-T33** | `test_r05_t33_greedy_heuristic_never_claims_optimal` | Lời giải Greedy không bao giờ tự nhận là tối ưu toàn cục (`is_optimal_proven=False`). | **PASSED** |
| **R05-T34** | `test_r05_t34_cross_midnight_clock_formatting` | Định dạng thời gian liên tục vượt nửa đêm hiển thị `+1d HH:MM` rõ ràng. | **PASSED** |
| **R05-T35** | `test_r05_t35_flight_inspector_views_contain_operational_attributes` | `GateTimelineView` chứa đầy đủ các thuộc tính tác nghiệp phục vụ Flight Inspector. | **PASSED** |

## 3. Thống Kê Thực Thi Kiểm Thử
- **Tổng số tests UI-R05:** 35 / 35 Passed (100%).
- **Thời gian chạy kiểm thử:** 1.64 giây.
- **Tương thích hồi quy:**
  - `tests/dashboard/`: 256 / 256 Passed (100%).
  - Backend regression `tests/test_*p0*.py`: 235 / 235 Passed (100%).
  - **Toàn hệ thống:** 491 / 491 Passed (100%).
