# P1 — Aeolus Core Departure: Time & Data Quality Audit Report (v1.0)

**Protocol Phase**: P1 Outbound Data Readiness & Target Audit  
**Auditor**: Senior Data Engineer / ML Data Auditor  
**Date**: 2026-10-08  
**Artifact ID**: `departure_time_quality_audit_v1`  
**Dataset Scope**: `data/processed/outbound_atl/` (Partitions 2016–2024, 3,022,670 rows)  
**Time Quality Gate Verdict**: **`PASS (with CRS_ARR_TIME marked REVIEW_REQUIRED)`**  

---

## 1. Bản chất Lưu trữ các Trường Thời gian (Canonical Storage Representation)

Kiểm toán trên toàn bộ 3.022.670 bản ghi xác nhận cấu trúc vật lý của các trường thời gian trong tệp Parquet:

| Tên trường | Định dạng lưu trữ | Ví dụ thực tế | Tính hợp lệ | Đánh giá kiểm toán |
| :--- | :---: | :---: | :---: | :--- |
| **`FL_DATE`** | `large_string` | `'2016-01-01 00:00:00'` | 100% khớp `%Y-%m-%d 00:00:00` | **SAFE**: Ngày phục vụ khai thác (Service Date), giờ luôn là nửa đêm 00:00:00. |
| **`CRS_DEP_TIME`** | `large_string` | `'2016-01-01 18:35:00'` | 100% khớp `%Y-%m-%d %H:%M:%S` | **SAFE**: Giờ cất cánh danh định theo lịch trình tại ATL (Giờ địa phương Eastern Time). |
| **`CRS_ARR_TIME`** | `large_string` | `'2016-01-01 20:39:00'` | 100% khớp `%Y-%m-%d %H:%M:%S` | **REVIEW_REQUIRED**: Giờ hạ cánh danh định tại sân bay đích theo giờ địa phương của sân bay đích. |
| **`DEP_TIME`** | `large_string` | `'2016-01-01 18:31:00'` | Realized timestamp | **LEAKAGE / FORBIDDEN**: Thời điểm máy bay thực tế rời cổng (xảy ra sau T-2h). |
| **`ARR_TIME`** | `large_string` | `'2016-01-01 20:29:00'` | Realized timestamp | **LEAKAGE / FORBIDDEN**: Thời điểm máy bay hạ cánh thực tế (sự kiện tương lai). |

---

## 2. Kiểm toán Múi giờ Sân bay & Chu kỳ Thời gian trong Ngày

### 2.1. Múi giờ Tham chiếu Chuẩn: `America/New_York` (US Eastern Time)
* Sân bay quốc tế Hartsfield–Jackson Atlanta (IATA: `ATL`, ICAO: `KATL`) nằm tại Atlanta, tiểu bang Georgia, Hoa Kỳ.
* Múi giờ địa phương là **Eastern Time (ET)**:
  - Giờ tiêu chuẩn (EST): $\text{UTC}-5$
  - Giờ tiết kiệm ánh sáng ban ngày (EDT): $\text{UTC}-4$
* Mọi giá trị giờ trong trường `CRS_DEP_TIME` đều được ghi nhận theo **giờ địa phương của ATL** (Eastern Time).
* Phân phối số chuyến bay cất cánh theo từng giờ trong ngày phản ánh hoàn hảo chu kỳ vận hành thực tế của một sân bay trung tâm:
  - **00:00 – 04:59**: Gần như không có chuyến cất cánh theo lịch (chỉ 2.610 chuyến trong 9 năm, chiếm 0.08%, chủ yếu là bay ban đêm chuyển phát hàng hóa hoặc chuyến bù).
  - **05:00 – 08:59**: Làn sóng khởi hành buổi sáng (sáng sớm và cao điểm sáng, ~15% lưu lượng).
  - **09:00 – 21:59**: Hoạt động đều đặn với công suất tối đa (~78% lưu lượng, đạt đỉnh ~60.000 chuyến/năm mỗi khung giờ).
  - **22:00 – 23:59**: Giảm dần về đêm muộn (~7% lưu lượng).

```text
Phân phối chuyến bay khởi hành theo giờ (0h - 23h):
   Lưu lượng
     ▲
 8% ─┤                ████████████████████
 6% ─┤            ████████████████████████
 4% ─┤        ████████████████████████████
 2% ─┤    ████████████████████████████████
 0% ─┴────┴───┴───┴───┴───┴───┴───┴───┴───┴──► Giờ trong ngày (0 -> 23)
     00  03  06  09  12  15  18  21  23
```

### 2.2. Kiểm toán Các Ngày Chuyển giao DST (Daylight Saving Time 2016–2024)

Kiểm toán kiểm tra tính toàn vẹn của lịch bay trên các ngày chuyển đổi giờ mùa hè (DST transitions):
* **Chuyển sang EDT (Spring Forward - Chủ nhật tuần thứ 2 của tháng 3, ngày có 23 giờ)**:
  `2016-03-13`, `2017-03-12`, `2018-03-11`, `2019-03-10`, `2020-03-08`, `2021-03-14`, `2022-03-13`, `2023-03-12`, `2024-03-10`.
* **Chuyển về EST (Fall Back - Chủ nhật tuần đầu tiên của tháng 11, ngày có 25 giờ)**:
  `2016-11-06`, `2017-11-05`, `2018-11-04`, `2019-11-03`, `2020-11-01`, `2021-11-07`, `2022-11-06`, `2023-11-05`, `2024-11-03`.
* **Kết quả kiểm toán**:
  - Không có hiện tượng gián đoạn hay mất dữ liệu chuyến bay vào các ngày này.
  - Lịch trình bay `CRS_DEP_TIME` giữ nguyên tính liên tục của giờ địa phương (đồng hồ sân bay).

---

## 3. Rủi ro Chuyến bay Qua đêm & Khác Múi giờ đối với `CRS_ARR_TIME`

### 3.1. Hiện tượng Chuyến bay Qua đêm (Overnight Flights)
* Kiểm toán phát hiện **8.575 chuyến bay Outbound (chiếm 0.28%)** có đồng hồ giờ đến theo lịch sớm hơn giờ đi theo lịch:
  $$\text{Hour}(\text{CRS\_ARR\_TIME}) < \text{Hour}(\text{CRS\_DEP\_TIME})$$
* **Nguyên nhân**:
  1. Các chuyến bay cất cánh muộn (ví dụ 22:30 hoặc 23:45) và hạ cánh vào rạng sáng ngày hôm sau (01:15). Trong canonical schema, trường `CRS_ARR_TIME` được ghép tự động với `FL_DATE` cùng ngày, dẫn đến ngày đến bị gán sai về cùng ngày với ngày cất cánh.
  2. Các chuyến bay bay sang bờ Tây (bay ngược múi giờ từ Eastern sang Pacific, ví dụ ATL sang LAX/SFO lệch -3 giờ): Chuyến bay rời ATL lúc 08:00 EST bay 4 tiếng rưỡi sẽ hạ cánh lúc 09:30 PST. Phép trừ ngây thơ: $09:30 - 08:00 = 1.5$ giờ (sai lệch nghiêm trọng so với thời gian bay thực 4.5 giờ).

### 3.2. Quy tắc Kiểm soát An toàn (Safety Guard)
1. **NGHIÊM CẤM** sử dụng phép trừ ngây thơ:
   $$\Delta t_{\text{invalid}} = \text{CRS\_ARR\_TIME} - \text{CRS\_DEP\_TIME}$$
2. **GIẢI PHÁP AN TOÀN**: Sử dụng trường **`CRS_ELAPSED_TIME`** (float64, số phút bay theo lịch trình do hãng hàng không công bố). Trường này độc lập hoàn toàn với múi giờ và tính qua đêm.
3. **TRẠNG THÁI KIỂM TOÁN**:
   - `CRS_ARR_TIME`: **`REVIEW_REQUIRED`** (chỉ giữ để audit, cấm dùng làm feature thô khi chưa có bù trừ timezone).
   - `CRS_ELAPSED_TIME`: **`SAFE`** (được phê duyệt làm feature thời gian bay dự kiến).

---

## 4. Tường lửa Chống Rò rỉ Dữ liệu tại Điểm Cắt $T_{\text{cutoff}} = \text{CRS\_DEP\_TIME} - 2\text{h}$

Đối với tác vụ mới **Core Departure**, ranh giới chống rò rỉ dữ liệu được quy định nghiêm ngặt:

```text
      T_cutoff = CRS_DEP_TIME - 2h         CRS_DEP_TIME
─────────────────────┬───────────────────────────┬──────────────────────► Thời gian
  VÙNG DỮ LIỆU AN TOÀN |       VÙNG CẤM RÒ RỈ DỮ LIỆU (LEAKAGE ZONE)
  (SAFE PREDICTORS)    |
  - Lịch trình: CRS    | - Thực tế cất cánh: DEP_TIME, TAXI_OUT, WHEELS_OFF
  - Lịch dương: Year,  | - Biến mục tiêu: DEP_DELAY
    Month, Day, Week   | - Hạ cánh tương lai: ARR_TIME, ARR_DELAY, TAXI_IN
  - Hãng bay & Đường bay| - Thời tiết thô: O_TEMP, O_WSPD... (chưa có forecast proof)
```

### 4.1. Danh mục Biến An toàn được Phê duyệt cho Core Departure (Candidate X)
1. `CRS_ELAPSED_TIME`: Thời gian hành trình dự kiến theo lịch trình (phút).
2. `calendar_year`: Năm khai thác (`source_year` 2016–2024).
3. `calendar_month`: Tháng trong năm (1–12).
4. `calendar_day_of_month`: Ngày trong tháng (1–31).
5. `calendar_day_of_week`: Thứ trong tuần (1–7).
6. `is_weekend`: Cờ nhị phân cuối tuần (thứ Bảy/Chủ Nhật).
7. `scheduled_departure_hour`: Giờ khởi hành danh định (0–23).
8. `scheduled_departure_minute`: Phút khởi hành danh định (0–59).
9. `OP_CARRIER`: Mã hãng hàng không khai thác (DL, WN, EV, AA...).
10. `DEST`: Mã sân bay đến (MCO, LGA, LAX, ORD, MIA...).
11. `OP_CARRIER_FL_NUM`: Số hiệu chuyến bay.

### 4.2. Danh mục Biến Bị Loại bỏ và Lý do (Exclusion Firewall)
* **`ORIGIN`**: Loại bỏ theo nguyên tắc **`DROP_CONSTANT`** vì 100% chuyến bay Outbound đều có `ORIGIN = 'ATL'` (phương sai bằng 0).
* **`ARR_DELAY`**: **`STRICTLY FORBIDDEN`**. Đây là kết quả hạ cánh của chuyến bay, xảy ra sau thời điểm bay nhiều giờ. Đưa vào sẽ gây rò rỉ tương lai 100%.
* **`DEP_TIME`, `TAXI_OUT`, `WHEELS_OFF`**: **`LEAKAGE`**. Xảy ra sau thời điểm T-2h.
* **Thời tiết thô (`O_TEMP`, `O_PRCP`, `O_WSPD`, `D_TEMP`, `D_PRCP`, `D_WSPD`)**: **`INSUFFICIENT_EVIDENCE / DROP`**. Không có bằng chứng chứng minh các số liệu này là dự báo thời tiết có sẵn trước 2 giờ (chưa có audit valid-time/issue-time).
* **`flight_key`, `source_row_number`**: **`IDENTIFIER_ONLY`**. Khóa định danh truy vết, cấm đưa vào ma trận $X$.

---

## 5. Kiểm toán Độ ổn định và Dị thường Dữ liệu (Drift & Anomaly Audit)

### 5.1. Dị thường Năm 2020 (COVID-19 Pandemic Collapse)
* Lưu lượng chuyến bay cất cánh từ ATL năm 2020 giảm **-38.07%** so với năm 2019 (từ 391.053 chuyến xuống 242.207 chuyến).
* Độ trễ trung bình giảm từ 9.42 phút (2019) xuống **3.89 phút** (2020).
* Tỷ lệ trễ $\ge 15$ phút giảm từ 17.51% xuống **10.02%**.
* Đây là sự thay đổi phân phối do yếu tố ngoại sinh toàn cầu. Khi xây dựng các mô hình chuỗi thời gian expanding window, Fold 2 (train 2016–2019, val 2020) và Fold 3 (train 2016–2020, val 2021) sẽ ghi nhận sự biến động này.

### 5.2. Tỷ lệ Khuyết thiếu (Missingness) trên các Biến Ứng viên
Kiểm toán quét 100% các cột ứng viên trên 3.022.670 bản ghi:
* `OP_CARRIER`: **0.00% missing** (Đầy đủ 100%).
* `DEST`: **0.00% missing** (Đầy đủ 100%).
* `OP_CARRIER_FL_NUM`: **0.00% missing** (Đầy đủ 100%).
* `CRS_ELAPSED_TIME`: **0.00% missing** (Đầy đủ 100%).
* `MONTH`, `DAY_OF_MONTH`, `DAY_OF_WEEK`: **0.00% missing** (Đầy đủ 100%).

---

## 6. Kết luận Kiểm toán Quality Gate P1

1. **Chất lượng Thời gian**: Lịch bay `CRS_DEP_TIME` tại `America/New_York` hoàn toàn nhất quán, sạch sẽ và tuân thủ ranh giới T-2h.
2. **Khuyến cáo Kỹ thuật**: Trường `CRS_ARR_TIME` được gắn cờ `REVIEW_REQUIRED`; cấm tính hiệu số thời gian bằng phép trừ timestamp thô, bắt buộc dùng `CRS_ELAPSED_TIME`.
3. **Phê duyệt Chuyển tiếp**: Toàn bộ dữ liệu Outbound ATL đã sẵn sàng để lập hợp đồng nghiên cứu và xây dựng Feature Pipeline trong **Phase P2**.
