# AEOLUS-G12A — DELIVERABLE 05: CAUSAL REGRESSION TEST SUITE RESULTS

---

**Task Identifier:** `AEOLUS-G12A` — Causal Online Recourse Remediation  
**Auditor & Verification Role:** Senior Operations Research Engineer, Verification Test Lead  
**Date:** 2026-10-12  
**Test Suite File:** `tests/test_g12a_causal_online_recourse.py`  
**Classification:** SCIENTIFIC INVARIANT & REGRESSION TEST RESULTS  

---

## 1. MỤC TIÊU VÀ DANH MỤC 14 BẤT BIẾN NHÂN QUẢ (CAUSAL-01 ĐẾN CAUSAL-14)

Để xác nhận tính đúng đắn khoa học tuyệt đối của Mode B2 sau remediation, bộ kiểm thử `test_g12a_causal_online_recourse.py` được thiết kế với đầy đủ 14 bất biến bắt buộc:

| Mã Kiểm thử | Tên Bất biến Khoa học | Mục tiêu Kiểm chứng | Kết quả |
| :---: | :--- | :--- | :---: |
| **CAUSAL-01** | Lịch sử đồng nhất $\rightarrow$ Quyết định đồng nhất | Hai kịch bản có cùng lịch sử quan sát $\le t$ phải đưa ra quyết định tại $t$ giống nhau. | **PASS** |
| **CAUSAL-02** | Rời cổng tương lai nghiêm ngặt ($> t$) | Cả hai mốc rời cổng thực tế đều diễn ra sau $t$, khắc phục nhược điểm của test G11. | **PASS** |
| **CAUSAL-03** | Bảo tồn đầu vào cơ sở | Giữ nguyên danh sách chuyến bay, lịch trình và forecast; chỉ đột biến world future. | **PASS** |
| **CAUSAL-04** | Đột biến trễ đi tương lai của chính chuyến bay | Đổi thời gian rời cổng tương lai của chuyến đang xét không làm đổi quyết định tại lúc đến. | **PASS** |
| **CAUSAL-05** | Biến cố quá khứ $\le t$ làm đổi quyết định | Tàu bay đã rời cổng thực tế trước $t$ được ghi nhận giải phóng cổng, cho phép quyết định khác. | **PASS** |
| **CAUSAL-06** | Fallback khi thiếu dự báo | Xử lý tất định và nhân quả theo công thức $\max(T_{\text{dep}}^{\text{sched}}, T_{\text{arr}} + \text{turnaround}, t)$. | **PASS** |
| **CAUSAL-07** | Từ chối truy cập qua ranh giới dữ liệu | Truy cập `precomputed_gate_out_min` trên `ObservableFlightSnapshot` bị chặn bằng `AttributeError`. | **PASS** |
| **CAUSAL-08** | Thực thi hợp đồng `lock_horizon_minutes` | Thay đổi $H_{\text{lock}}$ (45 vs 15) chứng minh tác động trực tiếp lên quyết định chọn cổng ứng viên. | **PASS** |
| **CAUSAL-09** | Tàu bay đã đỗ là bất biến | Tàu bay cập cổng tại $t_1 < t$ tuyệt đối không bao giờ bị điều chuyển hồi tố ở các vòng sau. | **PASS** |
| **CAUSAL-10** | Giới hạn sức chứa bãi đỗ xa | Theo dõi số lượng đỗ tức thời và không vượt quá `finite_remote_capacity`. | **PASS** |
| **CAUSAL-11** | Tương thích loại tàu bay và đệm 15 phút | Cổng hẹp không nhận tàu bay thân rộng; khoảng cách an toàn 15 phút được bảo toàn. | **PASS** |
| **CAUSAL-12** | Biên thời gian qua nửa đêm ($> 1440$ phút) | Số phút luỹ kế bảo toàn thứ tự biến cố thời gian đơn điệu qua ranh giới ngày. | **PASS** |
| **CAUSAL-13** | Tái lập tất định (Deterministic Replay) | 5 lần chạy lặp lại với cùng input cho kết quả và vết quyết định trùng khớp 100%. | **PASS** |
| **CAUSAL-14** | Độc lập giữa ra quyết định và đánh giá sau | Quá trình quyết định hoàn tất trước khi đối chiếu ex-post với ground truth. | **PASS** |

---

## 2. NHẬT KÝ THỰC THI PYTEST CHÍNH THỨC (RAW EXECUTION TRACE)

### Lệnh chạy:
```powershell
.venv\Scripts\python.exe -m pytest tests/test_g12a_causal_online_recourse.py -v
```

### Kết quả đầu ra:
```text
============================= test session starts =============================
platform win32 -- Python 3.11.15, pytest-9.1.1, pluggy-1.6.0 -- D:\Study\Code\Python\Aelous\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: D:\Study\Code\Python\Aelous
configfile: pytest.ini
plugins: anyio-4.15.1
collecting ... collected 12 items

tests/test_g12a_causal_online_recourse.py::test_causal_01_02_03_identical_history_different_future_gate_out PASSED [  8%]
tests/test_g12a_causal_online_recourse.py::test_causal_04_own_future_gate_out_mutation_invariance PASSED [ 16%]
tests/test_g12a_causal_online_recourse.py::test_causal_05_observed_departure_alters_decision PASSED [ 25%]
tests/test_g12a_causal_online_recourse.py::test_causal_06_missing_forecast_deterministic_fallback PASSED [ 33%]
tests/test_g12a_causal_online_recourse.py::test_causal_07_future_data_access_across_boundary_rejected PASSED [ 41%]
tests/test_g12a_causal_online_recourse.py::test_causal_08_lock_horizon_demonstrable_impact PASSED [ 50%]
tests/test_g12a_causal_online_recourse.py::test_causal_09_docked_aircraft_immutability PASSED [ 58%]
tests/test_g12a_causal_online_recourse.py::test_causal_10_finite_remote_stand_capacity PASSED [ 66%]
tests/test_g12a_causal_online_recourse.py::test_causal_11_gate_compatibility_and_buffer PASSED [ 75%]
tests/test_g12a_causal_online_recourse.py::test_causal_12_midnight_boundary_crossover PASSED [ 83%]
tests/test_g12a_causal_online_recourse.py::test_causal_13_deterministic_replay PASSED [ 91%]
tests/test_g12a_causal_online_recourse.py::test_causal_14_ex_post_evaluation_independence PASSED [100%]

============================= 12 passed in 1.17s ==============================
```

---

## 3. KẾT QUẢ KIỂM THỬ KHÔNG SUY GIẢM (NON-REGRESSION SUITE)

```powershell
.venv\Scripts\python.exe -m pytest tests/test_g2_monte_carlo_causality.py -v
```

```text
============================= 14 passed in 1.19s ==============================
```

**Tổng cộng:** **26/26 unit tests PASS 100%**, xác nhận toàn bộ các bất biến nhân quả, tính toàn vẹn cấu trúc và độ ổn định của hệ thống.
