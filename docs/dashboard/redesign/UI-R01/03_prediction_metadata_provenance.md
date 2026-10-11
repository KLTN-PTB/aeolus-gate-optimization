# UI-R01 — 03. PREDICTION METADATA PROVENANCE & ZERO-FABRICATION REPORT

## 1. PHÁT HIỆN GỐC RỄ (ROOT CAUSE DISCOVERY)

Cuộc kiểm toán UI-R00 và Task R01-C đã xác định nguyên nhân kỹ thuật trực tiếp dẫn đến việc tạo dữ liệu giả trong Page 02 (Flight Intelligence):

1. **Lệch định danh kịch bản (ID Schema Incompatibility):**
   - Tập tin dự báo ML mẫu `artifacts/remediation/native_dual_core/predictions_sample.csv` được sinh ra từ pipeline nghiên cứu native dual-core với các mã định danh chuyến bay là `LEG_ARR_0001` đến `LEG_ARR_0060`.
   - Trong khi đó, kịch bản lịch trình phân cổng chuẩn 120 chuyến (`SCEN_P09_CANONICAL_120`) lại sử dụng không gian mã chuyến bay là `S1500-0001` đến `S1500-0120`.
   - Kết quả: Khi hàm `adapt_prediction_row_to_view` cố gắng ánh xạ thông tin chuyến bay từ `flight_manifest` bằng key `flight_id`, không có bản ghi nào khớp được (`manifest_match is None`).

2. **Cơ chế Silent Dummy Fallback sai lầm:**
   - Để "tránh crash giao diện" và "hiển thị bảng biểu cho đẹp", code cũ trong `dashboard/adapters/prediction_adapter.py` đã tự động điền các giá trị mặc định:
     ```python
     # CODE CŨ (NGUY HẠI):
     carrier = row.get("carrier") or "DL"
     origin = row.get("origin") or "ORD"
     dest = row.get("destination") or "ATL"
     sched_time = int(row.get("sched_arr_time_min") or 480) # 08:00 AM
     ```
   - Hậu quả nghiêm trọng: Toàn bộ 60 chuyến bay trong `predictions_sample.csv` đều bị biến thành hãng hàng không **Delta Air Lines (DL)**, bay từ Chicago O'Hare (**ORD**) đến Atlanta (**ATL**) và đều hạ cánh đúng vào lúc **08:00 AM (phút 480)**! Đây là hành vi chế tác dữ liệu hiển thị (data fabrication) hoàn toàn vi phạm đạo đức nghiên cứu phần mềm khoa học.

3. **Lỗi logic Falsy Zero trong Python:**
   - Cú pháp `pred_delay = float(row.get("predicted_delay_min") or 0.0)` vô tình coi giá trị `0.0` là *falsy*. Nếu trường này có nhiều tên gọi fallback liên tiếp, giá trị dự báo đúng bằng 0 phút trễ có thể bị nhảy sang nhánh fallback ngoài ý muốn.

---

## 2. BIỆN PHÁP KHẮC PHỤC TRIỆT ĐỂ (UI-R01 REMEDIATION)

### 2.1. Tái cấu trúc View Contract & Adapter
1. Trong [`dashboard/core/contracts.py`](file:///D:/Study/Code/Python/Aelous/dashboard/core/contracts.py):
   - Chuyển `sched_arr_time_min: Optional[int] = None` (cho phép nhận `None`).
   - Các trường `carrier`, `origin`, `destination` có giá trị mặc định là `"N/A"`.
   - Ràng buộc kiểm tra tính hợp lệ `0 <= sched_arr_time_min <= 2880` chỉ kích hoạt khi `sched_arr_time_min is not None`.

2. Trong [`dashboard/adapters/prediction_adapter.py`](file:///D:/Study/Code/Python/Aelous/dashboard/adapters/prediction_adapter.py):
   - Loại bỏ hoàn toàn mọi chuỗi `"DL"`, `"ORD"`, `"ATL"`, `480`.
   - Nếu không có trường trong raw row và không tìm thấy trong `flight_manifest`, trường thông tin bắt buộc phải là `"N/A"`, và `sched_arr_time_min` là `None`.
   - Xử lý giá trị số thực chính xác với `val is not None`, bảo toàn tuyệt đối giá trị `0.0`.
   - Bổ sung rào chắn cách ly liên kịch bản (Cross-scenario Guard):
     ```python
     row_scenario = row.get("scenario_id")
     if scenario_id and row_scenario and row_scenario != scenario_id:
         raise ValueError(
             f"Cross-scenario mismatch: row scenario '{row_scenario}' does not match active scenario '{scenario_id}'"
         )
     ```

### 2.2. Xử lý An toàn trên Giao diện Streamlit
Trong [`dashboard/pages/page_02_flight_intelligence.py`](file:///D:/Study/Code/Python/Aelous/dashboard/pages/page_02_flight_intelligence.py):
- Xử lý phân loại và sắp xếp an toàn khi `sched_arr_time_min` là `None`:
  ```python
  elif sort_order == "Giờ hạ cánh":
      filtered_views.sort(key=lambda x: x.sched_arr_time_min if x.sched_arr_time_min is not None else -1)
  ```
- Hiển thị bảng biểu trung thực:
  ```python
  if v.sched_arr_time_min is not None:
      h = v.sched_arr_time_min // 60
      m = v.sched_arr_time_min % 60
      time_str = f"{h:02d}:{m:02d}"
  else:
      time_str = "N/A"
  ```
- Không còn bất kỳ chuyến bay nào bị gán ép thành "DL", "ORD➔ATL", hay "08:00". Dữ liệu hiển thị thể hiện chính xác 100% bản chất của artifact nguồn.

---

## 3. BẰNG CHỨNG KIỂM CHỨNG TỰ ĐỘNG

Bộ test tự động `tests/dashboard/test_ui_r01_data_integrity.py` đã xác nhận:
- `test_r01_t01_prediction_missing_metadata_defaults_to_na`: PASS.
- `test_r01_t02_prediction_missing_sched_arr_time_is_none`: PASS.
- `test_r01_t03_prediction_unmatched_flight_id_gives_na_metadata`: PASS.
- `test_r01_t04_prediction_exact_zero_delay_preserved`: PASS.
- `test_r01_t05_prediction_cross_scenario_guard`: PASS.
- `test_r01_t21_flight_intelligence_handles_none_sched_arr_time`: PASS.
- `test_r01_t22_flight_prediction_view_immutability`: PASS.
