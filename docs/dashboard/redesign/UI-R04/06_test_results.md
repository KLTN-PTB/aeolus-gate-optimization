# AEOLUS DASHBOARD — UI-R04
# COMPREHENSIVE TEST SUITE EXECUTION & REGRESSION REPORT

**Tài liệu:** `docs/dashboard/redesign/UI-R04/06_test_results.md`  
**Giai đoạn:** Phase UI-R04 v2.0  
**Tác giả:** QA Automation Lead, Software Testing Specialist  
**Ngày phê duyệt:** 2026-10-11  
**Trạng thái:** 100% PASSED (368/368 TESTS PASSING)  

---

## 1. TỔNG QUAN KẾT QUẢ KIỂM THỬ

Toàn bộ các yêu cầu kỹ thuật và nguyên tắc bảo toàn khoa học của giai đoạn UI-R04 đã được kiểm chứng thông qua bộ kiểm thử tự động toàn diện:
- **Bộ kiểm thử UI-R04 mới (`R04-T01` đến `R04-T25`):** 25/25 tests PASSED (100%).
- **Toàn bộ kiểm thử Dashboard (`tests/dashboard/`):** 221/221 tests PASSED (100%).
- **Bộ kiểm thử Regression Pipeline Backend (`tests/test_*_p0*.py`):** 147/147 tests PASSED (100%).
- **Tổng số tests thực thi:** 368 tests PASSED, 0 failures, 0 errors.

---

## 2. MA TRẬN TEST CHI TIẾT PHASE UI-R04

| Mã Test | Mô tả Mục tiêu Kiểm định | File Thực thi | Kết quả |
| :--- | :--- | :--- | :---: |
| `R04-T01` | Scenario launcher metadata chứa hub ATL, số chuyến, số cổng, digest | `test_ui_r04_*.py` | **PASSED** |
| `R04-T02` | Loại bỏ lối tắt `len(flights)//2`; kịch bản chưa ghép cặp trả về `[]` | `test_ui_r04_*.py` | **PASSED** |
| `R04-T03` | Kịch bản `SCEN_P07_DUAL_CORE_30` tải đủ 30 cặp quay vòng thực tế | `test_ui_r04_*.py` | **PASSED** |
| `R04-T04` | Phân tách trung thực cổng ống lồng, bãi đỗ xa và bãi đỗ tràn | `test_ui_r04_*.py` | **PASSED** |
| `R04-T05` | Bảo toàn dấu âm độ trễ dự báo (vd: $-9.1$ min) không bị ép về 0 | `test_ui_r04_*.py` | **PASSED** |
| `R04-T06` | Trạng thái tối ưu hiển thị `CHƯA CHẠY [NOT_RUN]` khi chưa giải | `test_ui_r04_*.py` | **PASSED** |
| `R04-T07` | Solver name, trạng thái và số xung đột báo đúng khi solver đã chạy | `test_ui_r04_*.py` | **PASSED** |
| `R04-T08` | Concourse utilization mặc định `occupied = 0` (chấm dứt bịa đặt 8 và 15) | `test_ui_r04_*.py` | **PASSED** |
| `R04-T09` | Concourse utilization tính động từ gates với 0 occupied | `test_ui_r04_*.py` | **PASSED** |
| `R04-T10` | Tiêu đề timeline được làm sạch (không chứa mã thô `(CHART-01)`) | `test_ui_r04_*.py` | **PASSED** |
| `R04-T11` | Bảng dự báo Dual-Core Tab A chứa đầy đủ cả 2 chiều `ARR` và `DEP` | `test_ui_r04_*.py` | **PASSED** |
| `R04-T12` | Bộ lọc chiều bay lọc chính xác độc lập `ARR` hoặc `DEP` | `test_ui_r04_*.py` | **PASSED** |
| `R04-T13` | `FlightPredictionView` giữ nguyên dấu âm và phân loại rủi ro | `test_ui_r04_*.py` | **PASSED** |
| `R04-T14` | Nạp đúng xác suất trễ $\ge 15$m và quantiles ($q_{10}, q_{50}, q_{90}$) | `test_ui_r04_*.py` | **PASSED** |
| `R04-T15` | Báo cáo trung thực nguồn gốc mô hình (`ngboost` / `xgboost`) | `test_ui_r04_*.py` | **PASSED** |
| `R04-T16` | Kiểm định Zero-Leakage: ném ngoại lệ khi có cột nhãn trễ thực tế | `test_ui_r04_*.py` | **PASSED** |
| `R04-T17` | Kịch bản chưa ghép cặp hiển thị Empty State thay vì bịa đặt cặp giả | `test_ui_r04_*.py` | **PASSED** |
| `R04-T18` | Xóa bỏ hoàn toàn biến `sample_turns` hardcoded khỏi mã nguồn | `test_ui_r04_*.py` | **PASSED** |
| `R04-T19` | $D_{gate\_out} = \max(D_{pred}, A_{pred} + T_{min})$ và $T_{release} = D_{gate\_out} + \text{buffer}$ | `test_ui_r04_*.py` | **PASSED** |
| `R04-T20` | Buffer an toàn 15 phút chỉ được cộng đúng 1 lần duy nhất | `test_ui_r04_*.py` | **PASSED** |
| `R04-T21` | Tính toán chính xác đệm slack hấp thụ và trễ lan truyền | `test_ui_r04_*.py` | **PASSED** |
| `R04-T22` | Tiêu đề turn dynamics figure sạch, không chứa mã thô `(CHART-03)` | `test_ui_r04_*.py` | **PASSED** |
| `R04-T23` | TreeSHAP global importance và local case studies tải thành công | `test_ui_r04_*.py` | **PASSED** |
| `R04-T24` | Bảng đánh giá OOF validation metrics tải đầy đủ trong Research Mode | `test_ui_r04_*.py` | **PASSED** |
| `R04-T25` | Khế ước `render_page` tồn tại và hợp lệ trên cả Page 01 và Page 02 | `test_ui_r04_*.py` | **PASSED** |

---

## 3. LOG THỰC THI PYTEST CHÍNH THỨC

```text
============================= test session starts =============================
platform win32 -- Python 3.11.15, pytest-9.1.1, pluggy-1.6.0
rootdir: D:\Study\Code\Python\Aelous
configfile: pytest.ini
plugins: anyio-4.15.1
collected 25 items

tests/dashboard/test_ui_r04_control_tower_flight_intelligence.py ......................... [100%]

============================= 25 passed in 1.69s ==============================

tests/dashboard/ (Full Dashboard Suite):
221 passed, 3 warnings in 7.08s

tests/test_*_p0*.py (Core Research Backend Regression Suite):
147 passed, 3 warnings in 13.18s
```
