# MA TRẬN KIỂM THỬ TỔNG THỂ & NGHIỆM THU HỆ THỐNG — PHASE P10-F
## Final Test Matrix & Verification Coverage

**Dự án:** Aeolus Gate Optimization  
**Khóa luận:** Ứng dụng học máy và lập trình ràng buộc trong dự báo độ trễ chuyến bay và tối ưu tái phân bổ cổng đỗ tàu bay  
**Giai đoạn:** P10-F — Final System QA, Offline Packaging & Acceptance  
**Tổng số test:** 212 tests (123 Dashboard tests + 89 Core Regression tests)  
**Tỷ lệ đạt:** **100% PASS (0 failures, 0 skipped, 0 errors)**

---

## 1. MA TRẬN PHÂN BỔ NHÓM KIỂM THỬ P10-F

| Nhóm Kiểm Thử | Tên Phân Hệ | File Kiểm Thử | Số lượng | Kết quả | Ghi chú Trọng yếu |
| :--- | :--- | :--- | :---: | :---: | :--- |
| **Group A** | Application Smoke & Streamlit AppTest | `test_final_acceptance.py` | 11 | **PASS** | Kiểm chứng cả 5 trang ở Presentation và Research Mode (0 exceptions) |
| **Group B** | Data & Provenance Integrity | `test_final_acceptance.py`, `test_foundation.py` | 15 | **PASS** | Cách ly dữ liệu 2024, xác thực schema JSON/CSV/Parquet, hash kịch bản |
| **Group C** | ML Scientific Correctness | `test_final_acceptance.py`, `test_ui_components.py` | 12 | **PASS** | Bảo lưu dấu trễ (âm/dương), SHAP waterfall, zero target data leakage |
| **Group D** | Gate Domain Correctness | `test_final_acceptance.py`, `test_gate_operations.py` | 30 | **PASS** | One-to-one, buffer 15m duy nhất, no-overlap, pooled capacity, verifier |
| **Group E** | Solver Status & Fallback | `test_final_acceptance.py`, `test_gate_operations.py` | 16 | **PASS** | Heuristic không dán nhãn OPTIMAL, UNKNOWN không bịa nghiệm, stale flag |
| **Group F** | Monte Carlo & Robustness | `test_final_acceptance.py`, `test_lab_and_robustness.py` | 20 | **PASS** | Tách bạch Mode A/B/C, Mode C NON-DEPLOYABLE, t-test CRN, CVaR |
| **Group G** | Streamlit Lifecycle & Session | `test_final_acceptance.py`, `test_foundation.py` | 8 | **PASS** | Chuỗi tương tác 12 bước, không rò rỉ session/cache giữa các kịch bản |
| **Group H** | Security & Resilience | `test_final_acceptance.py`, `test_services.py` | 8 | **PASS** | Chặn Path traversal, khử sạch đường dẫn tuyệt đối, tiếng Việt Unicode |
| **Group I** | Performance Bounds | `test_final_acceptance.py` | 3 | **PASS** | Load artifact < 50ms, render UI < 300ms, peak memory < 150MB |
| **Reg P07** | Native Dual Core Pipeline | `test_native_dual_core_pipeline_p07.py` | 35 | **PASS** | Mô hình trễ đến/đi, tổng hợp turn, ràng buộc an toàn |
| **Reg P08** | ML Research Validation | `test_ml_research_validation_p08.py` | 26 | **PASS** | MAE, RMSE, SHAP TreeExplainer, Temporal Holdout |
| **Reg P09** | Monte Carlo Engine 500 | `test_monte_carlo_robustness_p09.py` | 28 | **PASS** | 500 realizations, Copula phi tuyến, Recourse engine |
| **TỔNG CỘNG**| **HỆ THỐNG TOÀN DIỆN** | **9 file tests** | **212** | **PASS** | **Tuyệt đối không bỏ qua test nào** |

---

## 2. CHI TIẾT CÁC TEST CASES ĐẶC THÙ TRÊN GIAO DIỆN

### Test Group A: Application Smoke & AppTest
- `test_group_a_01_app_import_and_startup`: Khởi chạy `dashboard/app.py` qua `streamlit.testing.v1.AppTest`, kiểm tra không sinh ngoại lệ.
- `test_group_a_02_all_pages_presentation_mode`: Duyệt qua 5 trang (`01_control_tower`, `02_flight_intelligence`, `03_gate_operations`, `04_optimization_lab`, `05_robustness_lab`) ở Presentation Mode, xác nhận số exceptions = 0.
- `test_group_a_03_all_pages_research_mode`: Duyệt qua 5 trang ở Research Mode, xác nhận số exceptions = 0 và Research Inspector hiển thị.

### Test Group B: Data Contracts & Provenance
- `test_group_b_01_scenario_loading_and_quarantine`: Xác nhận danh sách kịch bản đăng ký hợp lệ; kịch bản chứa năm 2024 bị chặn bởi `PermissionError`.
- `test_group_b_02_artifact_loader_schema_validation`: Bắt lỗi `ArtifactValidationError` khi bảng dữ liệu thiếu cột bắt buộc.

### Test Group C: ML Scientific Integrity
- `test_group_c_01_signed_delays_preserved`: Chuyến bay hạ cánh sớm mang giá trị âm (ví dụ: -14.5 phút) không bị làm tròn về 0.
- `test_group_c_02_zero_leakage_in_planning_views`: Bắt lỗi `DataLeakageError` ngay lập tức khi xuất hiện cột trễ thực tế (`arr_delay`, `actual_arr_delay_min`).

### Test Group D: Gate Scheduling & Hard Constraints
- `test_group_d_01_release_buffer_present_exactly_once`: Khoảng đệm giải tỏa 15 phút chỉ xuất hiện đúng một lần trong View Model.
- `test_group_d_02_independent_verifier_validates_clean_schedule`: Hậu kiểm độc lập (`verify_hard_constraints_independently`) xác thực phương án gán cổng không có va chạm.

### Test Group E: Solver Status & Fallback
- `test_group_e_01_greedy_never_claims_optimal`: Greedy luôn trả về trạng thái `FEASIBLE`, cờ `is_optimal_proven = False`.
- `test_group_e_02_config_modification_marks_stale`: Khi người dùng thay đổi tham số điều khiển nhưng chưa bấm Run, nghiệm cũ được đánh dấu stale.

### Test Group F: Monte Carlo & Statistical Methods
- `test_group_f_01_mode_c_labeled_non_deployable`: Mode C Oracle mang nhãn cố định `NON-DEPLOYABLE (THEORETICAL BENCHMARK)`.
- `test_group_f_02_paired_analysis_alignment`: Kiểm định ghép cặp $n=500$ kịch bản thành công ($\Delta \text{Cost} = 1338.44$ pts, $p < 10^{-15}$).

### Test Group G: Lifecycle & Session State
- `test_group_g_01_twelve_step_interaction_lifecycle`: Mô phỏng đầy đủ chuỗi tương tác 12 bước của người điều hành mà không phát sinh stale cache hay xung đột kịch bản.

### Test Group H: Security & Resilience
- `test_group_h_01_path_traversal_blocked`: Chặn đứng tấn công duyệt thư mục (`../../../`).
- `test_group_h_02_path_and_secrets_sanitization`: Làm sạch toàn bộ đường dẫn cục bộ và từ khóa bí mật.

### Test Group I: Performance Bounds
- `test_group_i_01_artifact_load_latency_bound`: Thời gian tải tất cả các artifact cốt lõi đạt dưới 500 ms (thực tế 39.3 ms).
