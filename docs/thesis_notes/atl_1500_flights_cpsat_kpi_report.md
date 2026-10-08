# Báo Cáo Phân Bổ Cổng Đỗ Toàn Bộ 1.500 Chuyến Bay Bằng CP-SAT (Turnaround Sessions)
### Đề tài: Tối ưu hóa phân bổ cổng đỗ tàu bay — Aeolus Gate Optimization
**Ngày thực nghiệm:** 2026-10-05 15:37:58  
**Cảng hàng không:** Hartsfield-Jackson Atlanta International Airport (KATL)  
**Tệp dữ liệu đầu vào:** `atl_2024_01_01_full_day_1500_flights_turnaround_sessions.parquet` (851 phiên = 1.500 chuyến bay)  
**Tệp kết quả CSV xuất khẩu:** [`atl_1500_flights_cpsat_turnaround_schedule.csv`](file:///D:/Documents/BaiTap/KhoaLuanCuNhan/aeolus-gate-optimization/src/artifacts/predictions/atl_1500_flights_cpsat_turnaround_schedule.csv)  
**Bộ giải toán:** Google OR-Tools CP-SAT (Constraint Programming - Satisfiability)  

---

## 1. Bảng Chỉ Số Hiệu Quả Vận Hành Tổng Thể (Airport Operational KPIs)

| Chỉ Số Vận Hành (KPI) | Giá Trị Thực Nghiệm | Ý Nghĩa / Mục Tiêu Đạt Được |
| :--- | :---: | :--- |
| **Trạng Thái Tối Ưu Bộ Giải** | **`OPTIMAL`** | Đạt nghiệm tối ưu toàn cục (Global Optimum) |
| **Thời Gian Giải Toán (Wall Time)** | **`27.15 giây`** | Xử lý thành công toàn bộ 1.500 chuyến trong chưa đầy 30 giây |
| **Tổng Số Chuyến Bay Được Phân Cổng** | **1.500 / 1.500 (100.0%)** | 0 chuyến bay bị bỏ sót hoặc tràn bãi đỗ |
| **Tổng Số Phiên Quay Đầu (Sessions)** | **851 / 851 (100.0%)** | 649 phiên ghép cặp (PAIRED) + 202 phiên đơn |
| **Số Cổng Đỗ Kích Hoạt / Tổng Cổng** | **175 / 175 cổng** | Đạt cực đại ở 140 cổng đồng thời vào giờ cao điểm |
| **Phụ Tải Cổng Trung Bình** | **4.86 phiên / cổng** | Độ lệch chuẩn: $\pm 1.07$ phiên |
| **Phụ Tải Lớn Nhất / Nhỏ Nhất** | **9 phiên / 2 phiên** | Cân bằng tải tối ưu giữa các concourse |
| **Tỷ Lệ Chuyến Bay Nằm Trọn Trong Đệm Khóa Cổng** | **71.3%** (1070/1500 chuyến) | Vùng đệm 15m + Dự báo ML bảo vệ máy bay an toàn |
| **Điểm Xung Đột Thực Tế Phát Hiện (Stress Test)** | **38 điểm** (95.5% kháng nhiễu) | Chỉ có 38 trường hợp vượt đệm khi trễ cực đoan |
| **Xác Suất Trễ (P $\ge$ 15m) Trung Bình** | **27.8%** | Dự báo từ mô hình phân loại Gradient Boosting |
| **Mức Trễ Dự Báo Trung Bình (ML)** | **+3.8 phút** | Dự báo từ mô hình hồi quy độ trễ |
| **Mức Trễ Thực Tế Trung Bình** | **-2.9 phút** | Đối chứng từ dữ liệu khai thác thực tế BTS |

---

## 2. Thống Kê Phân Bổ Theo Hãng Hàng Không (Carriers Breakdown)

| Hãng Bay | Tổng Chuyến | Đến (ARR) | Đi (DEP) | Trễ Thực Tế TB (phút) | Tỷ Trọng Sản Lượng |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **DL** | 857 | 426 | 431 | -5.8m | 57.1% |
| **WN** | 239 | 119 | 120 | -0.1m | 15.9% |
| **9E** | 136 | 67 | 69 | -9.5m | 9.1% |
| **NK** | 62 | 31 | 31 | +8.4m | 4.1% |
| **F9** | 53 | 26 | 27 | +38.6m | 3.5% |
| **OO** | 42 | 21 | 21 | -13.8m | 2.8% |
| **AA** | 41 | 20 | 21 | +0.6m | 2.7% |
| **UA** | 26 | 13 | 13 | +0.5m | 1.7% |
| **B6** | 16 | 8 | 8 | +7.6m | 1.1% |
| **OH** | 12 | 6 | 6 | -12.1m | 0.8% |
| **YX** | 8 | 4 | 4 | -20.1m | 0.5% |
| **AS** | 6 | 3 | 3 | +4.3m | 0.4% |
| **MQ** | 2 | 1 | 1 | +3.5m | 0.1% |

---

## 3. Mẫu 30 Chuyến Bay Tiêu Biểu Trong File CSV (Audit Sample)

Trích xuất 30 chuyến bay đầu tiên theo trình tự thời gian với đầy đủ các cột đối chứng:

| Số Hiệu | Hướng | Cổng Gán | Giờ Lịch | Giờ Dự Báo | Giờ Thực Tế | Lệch Thực Tế | Khung Giờ Khóa Cổng | Khóa Cổng | Đánh Giá Vận Hành |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `WN 1579` | ARR | **`G161`** | 00:25 | 00:29 | 00:35 | Trễ 10p ⏳ | `[00:12 ➔ 01:22]` | 70m | An toàn tuyệt đối (Được bảo vệ) |
| `AA 659` | ARR | **`G33`** | 00:28 | 00:32 | 00:19 | Sớm 9p ⚡ | `[00:14 ➔ 01:24]` | 70m | An toàn tuyệt đối (Được bảo vệ) |
| `NK 1600` | ARR | **`G48`** | 00:31 | 00:35 | 00:20 | Sớm 11p ⚡ | `[00:17 ➔ 01:27]` | 70m | An toàn tuyệt đối (Được bảo vệ) |
| `WN 643` | ARR | **`G98`** | 00:35 | 00:39 | 00:18 | Sớm 17p ⚡ | `[00:21 ➔ 01:31]` | 70m | Hạ cánh sớm hơn đệm (3p) |
| `WN 2675` | ARR | **`G10`** | 00:40 | 00:44 | 01:08 | Trễ 28p ⏳ | `[00:27 ➔ 02:12]` | 105m | An toàn tuyệt đối (Được bảo vệ) |
| `F9 4027` | ARR | **`G88`** | 00:41 | 00:45 | 00:39 | Sớm 2p ⚡ | `[00:28 ➔ 01:38]` | 70m | An toàn tuyệt đối (Được bảo vệ) |
| `NK 1594` | ARR | **`G04`** | 00:44 | 00:48 | 00:10 | Sớm 34p ⚡ | `[00:31 ➔ 01:41]` | 70m | Hạ cánh sớm hơn đệm (21p) |
| `NK 3065` | ARR | **`G87`** | 00:45 | 00:49 | 01:02 | Trễ 17p ⏳ | `[00:32 ➔ 01:42]` | 70m | An toàn tuyệt đối (Được bảo vệ) |
| `F9 4917` | ARR | **`G49`** | 04:03 | 04:06 | 04:27 | Trễ 24p ⏳ | `[03:49 ➔ 06:06]` | 137m | An toàn tuyệt đối (Được bảo vệ) |
| `DL 730` | ARR | **`G64`** | 05:00 | 05:00 | 04:43 | Sớm 17p ⚡ | `[04:45 ➔ 08:15]` | 210m | Hạ cánh sớm hơn đệm (2p) |
| `DL 2796` | ARR | **`G127`** | 05:11 | 05:12 | 04:55 | Sớm 16p ⚡ | `[04:56 ➔ 06:15]` | 79m | Hạ cánh sớm hơn đệm (1p) |
| `DL 823` | ARR | **`G45`** | 05:15 | 05:16 | 05:12 | Sớm 3p ⚡ | `[05:00 ➔ 08:19]` | 199m | An toàn tuyệt đối (Được bảo vệ) |
| `NK 403` | DEP | **`G28`** | 05:21 | 05:28 | 05:36 | Trễ 15p ⏳ | `[04:21 ➔ 05:36]` | 75m | An toàn tuyệt đối (Được bảo vệ) |
| `DL 414` | ARR | **`G11`** | 05:29 | 05:30 | 05:04 | Sớm 25p ⚡ | `[05:14 ➔ 07:20]` | 126m | Hạ cánh sớm hơn đệm (10p) |
| `NK 3389` | DEP | **`G07`** | 05:35 | 05:41 | 05:41 | Trễ 6p ⏳ | `[04:35 ➔ 05:50]` | 75m | An toàn tuyệt đối (Được bảo vệ) |
| `AA 1151` | DEP | **`G164`** | 05:36 | 05:41 | 05:27 | Sớm 9p ⚡ | `[04:36 ➔ 05:51]` | 75m | An toàn tuyệt đối (Được bảo vệ) |
| `NK 1828` | ARR | **`G58`** | 05:43 | 05:47 | 05:30 | Sớm 13p ⚡ | `[05:29 ➔ 06:58]` | 89m | An toàn tuyệt đối (Được bảo vệ) |
| `DL 738` | ARR | **`G44`** | 05:44 | 05:45 | 05:42 | Sớm 2p ⚡ | `[05:29 ➔ 07:20]` | 111m | An toàn tuyệt đối (Được bảo vệ) |
| `AA 2770` | DEP | **`G74`** | 05:47 | 05:51 | 05:37 | Sớm 10p ⚡ | `[04:47 ➔ 06:02]` | 75m | An toàn tuyệt đối (Được bảo vệ) |
| `F9 4026` | DEP | **`G49`** | 05:50 | 06:01 | 05:40 | Sớm 10p ⚡ | `[03:49 ➔ 06:06]` | 137m | An toàn tuyệt đối (Được bảo vệ) |
| `F9 4754` | ARR | **`G156`** | 05:50 | 05:53 | 04:57 | Sớm 53p ⚡ | `[05:36 ➔ 07:01]` | 85m | Hạ cánh sớm hơn đệm (39p) |
| `F9 1450` | ARR | **`G82`** | 05:54 | 05:57 | 09:08 | Trễ 194p ⏳ | `[05:40 ➔ 08:40]` | 180m | Trễ vượt đệm an toàn (+28p) |
| `B6 467` | DEP | **`G29`** | 06:00 | 06:03 | 05:53 | Sớm 7p ⚡ | `[05:00 ➔ 06:15]` | 75m | An toàn tuyệt đối (Được bảo vệ) |
| `DL 8783` | DEP | **`G127`** | 06:00 | 06:07 | 05:56 | Sớm 4p ⚡ | `[04:56 ➔ 06:15]` | 79m | An toàn tuyệt đối (Được bảo vệ) |
| `WN 1221` | DEP | **`G59`** | 06:05 | 06:08 | 06:03 | Sớm 2p ⚡ | `[05:05 ➔ 06:20]` | 75m | An toàn tuyệt đối (Được bảo vệ) |
| `DL 899` | ARR | **`G78`** | 06:06 | 06:07 | 05:39 | Sớm 27p ⚡ | `[05:51 ➔ 07:29]` | 98m | Hạ cánh sớm hơn đệm (12p) |
| `NK 768` | DEP | **`G105`** | 06:10 | 06:16 | 06:05 | Sớm 5p ⚡ | `[04:55 ➔ 06:25]` | 90m | An toàn tuyệt đối (Được bảo vệ) |
| `WN 3089` | DEP | **`G110`** | 06:10 | 06:13 | 06:13 | Trễ 3p ⏳ | `[04:55 ➔ 06:25]` | 90m | An toàn tuyệt đối (Được bảo vệ) |
| `F9 1595` | DEP | **`G117`** | 06:15 | 06:20 | 06:59 | Trễ 44p ⏳ | `[05:15 ➔ 06:30]` | 75m | Trễ vượt đệm an toàn (+29p) |
| `WN 3741` | DEP | **`G148`** | 06:15 | 06:18 | 06:14 | Sớm 1p ⚡ | `[05:15 ➔ 06:30]` | 75m | An toàn tuyệt đối (Được bảo vệ) |

---

## 4. Hướng Dẫn Truy Xuất File CSV

Toàn bộ dữ liệu 1.500 chuyến bay đã được xuất đầy đủ ra tệp CSV:

- Đường dẫn: [`src/artifacts/predictions/atl_1500_flights_cpsat_turnaround_schedule.csv`](file:///D:/Documents/BaiTap/KhoaLuanCuNhan/aeolus-gate-optimization/src/artifacts/predictions/atl_1500_flights_cpsat_turnaround_schedule.csv)

- Cấu trúc 31 cột bao gồm: các mốc phút (`*_min`), các mốc giờ định dạng chuẩn (`*_hhmm`), phân loại tàu bay, cửa sổ chiếm dụng cổng, độ trễ và nhãn đánh giá an toàn vận hành.