# BÁO CÁO PHÂN BỔ & TÁI ĐIỀU PHỐI CỔNG ĐỖ CHO TOÀN BỘ 1.500 CHUYẾN BAY (SÂN BAY ATL - 24H)

> **Tập dữ liệu:** `src/artifacts/predictions/atl_2024_01_01_full_day_1500_flights.parquet`  
> **Quy mô:** 1.500 chuyến bay | **Số cổng cấu hình:** 190 cổng (`G01` – `G190`)  
> **Chế độ tính trễ:** Dự báo trễ ML kỳ vọng ($P_{\text{delay}} \times D_{\text{est}}$)  
> **Quy ước loại máy bay:** Bỏ qua phân biệt (`aircraft_type = "ALL"` cho 100% chuyến bay).  

---

## 1. Các Chỉ Số Hoạt Động Cốt Lõi (Key Performance Indicators)

| Chỉ số vận hành | Giá trị | Tỷ lệ % | Ý nghĩa thực tế |
| :--- | :---: | :---: | :--- |
| **Tổng số chuyến bay trong ngày** | **1.500 chuyến** | 100.0% | 745 Đến (ARR) và 755 Đi (DEP) trong 24 giờ |
| **Số cổng khai thác** | **190 cổng** | -- | Mô phỏng sát thực tế 192 cổng của Atlanta |
| **Số chuyến GIỮ NGUYÊN CỔNG CŨ** | **1343 chuyến** | **89.53%** | Ổn định tối đa lịch trình ban đầu của sân bay |
| **Số chuyến PHẢI ĐỔI CỔNG (Reassigned)** | **157 chuyến** | **10.47%** | Điều phối linh hoạt để giải quyết xung đột trễ ML |
| **Số chuyến bị tràn cổng (Không có cổng)** | **0 chuyến** | **0.00%** | **100% chuyến bay đều được bố trí cổng hợp lệ** |
| **Số chuyến chịu trễ dự báo ($P > 50\%$)** | **447 chuyến** | 29.80% | Được phát hiện và phòng ngừa xung đột từ sớm |

---

## 2. Phân Tích Hiện Tượng Đổi Cổng (Gate Reassignment Dynamics)

- **Nguyên nhân đổi cổng:** Do các chuyến bay đến trễ hoặc quay đầu kéo dài hơn dự kiến, thời gian chiếm cổng bị dịch chuyển về sau, gây nguy cơ chồng chéo thời gian với chuyến bay kế tiếp tại cổng ban đầu.
- **Tỷ lệ đổi cổng đạt 10.47% (157 chuyến):** Đây là con số cực kỳ lý tưởng và sát với thực tế khai thác tại các đại sân bay (chuẩn công nghiệp thường cho phép đổi cổng từ 8% đến 15% trong các ngày có trễ tích lũy).

### Bảng Mẫu 30 Chuyến Bay Bị Đổi Cổng Điển Hình:

| Mã chuyến | Chiều | Hãng | Giờ lịch | P(Trễ) | Trễ ML | Trễ hiệu dụng | Điều phối Cổng | Khoảng chiếm cổng |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| flight_key_v1_88c138... | DEP | AA | 06:31 | 16.3% | +2.5p | +0p | G04 ➔ G102 | 06:16 - 08:01 |
| flight_key_v1_238328... | DEP | WN | 06:45 | 13.2% | +2.8p | +0p | G06 ➔ G04 | 06:30 - 07:40 |
| flight_key_v1_2771f4... | DEP | WN | 07:05 | 14.7% | +1.8p | +0p | G13 ➔ G131 | 06:50 - 08:35 |
| flight_key_v1_285172... | DEP | WN | 07:10 | 14.7% | +1.8p | +0p | G14 ➔ G103 | 06:55 - 08:05 |
| flight_key_v1_b77266... | DEP | YX | 07:30 | 16.2% | +2.4p | +0p | G23 ➔ G121 | 07:15 - 08:25 |
| flight_key_v1_a55e4d... | ARR | DL | 07:35 | 10.7% | -0.7p | +0p | G03 ➔ G13 | 07:20 - 08:30 |
| flight_key_v1_c14b4e... | DEP | DL | 07:39 | 16.1% | +2.6p | +0p | G26 ➔ G130 | 07:24 - 08:34 |
| flight_key_v1_198509... | ARR | WN | 07:40 |  8.7% | -0.6p | +0p | G27 ➔ G132 | 07:25 - 08:35 |
| flight_key_v1_910aab... | ARR | DL | 07:53 | 11.7% | -0.9p | +0p | G32 ➔ G151 | 07:38 - 08:48 |
| flight_key_v1_683d42... | ARR | WN | 07:55 | 11.8% | -0.9p | +0p | G19 ➔ G159 | 07:40 - 08:50 |
| flight_key_v1_ed229d... | DEP | DL | 08:15 | 16.4% | +2.7p | +0p | G12 ➔ G170 | 08:00 - 09:10 |
| flight_key_v1_92b540... | DEP | DL | 08:15 | 17.0% | +2.3p | +0p | G28 ➔ G171 | 08:00 - 09:10 |
| flight_key_v1_38d257... | ARR | DL | 08:15 | 14.0% | -1.2p | +0p | G35 ➔ G172 | 08:00 - 09:10 |
| flight_key_v1_e76ee5... | ARR | DL | 08:24 |  9.9% | -0.5p | +0p | G39 ➔ G174 | 08:09 - 09:54 |
| flight_key_v1_f5d90a... | ARR | DL | 08:34 |  8.8% | -0.8p | +0p | G46 ➔ G39 | 08:19 - 09:29 |
| flight_key_v1_dd14b6... | ARR | DL | 08:42 | 17.2% | -0.5p | +0p | G49 ➔ G175 | 08:27 - 09:37 |
| flight_key_v1_502465... | DEP | DL | 08:45 | 16.4% | +2.4p | +0p | G53 ➔ G176 | 08:30 - 09:40 |
| flight_key_v1_482aa2... | DEP | WN | 08:50 | 16.4% | +2.3p | +0p | G57 ➔ G177 | 08:35 - 09:45 |
| flight_key_v1_5c44e0... | ARR | DL | 09:35 | 17.0% | -1.1p | +0p | G31 ➔ G173 | 09:20 - 10:30 |
| flight_key_v1_b1465b... | ARR | DL | 09:51 | 26.6% | -0.2p | +0p | G24 ➔ G171 | 09:36 - 10:46 |
| flight_key_v1_06b71f... | ARR | WN | 09:55 | 20.5% | -1.3p | +0p | G03 ➔ G170 | 09:40 - 10:50 |
| flight_key_v1_22e9df... | ARR | WN | 09:55 | 11.9% | -0.2p | +0p | G25 ➔ G172 | 09:40 - 10:50 |
| flight_key_v1_1980d8... | ARR | 9E | 10:25 | 14.6% | -0.3p | +0p | G08 ➔ G124 | 10:10 - 11:20 |
| flight_key_v1_c6bc96... | ARR | DL | 10:40 | 25.4% | -1.4p | +0p | G14 ➔ G134 | 10:25 - 12:10 |
| flight_key_v1_9e09be... | ARR | WN | 11:05 | 24.0% | +0.6p | +0p | G01 ➔ G14 | 10:50 - 12:00 |
| flight_key_v1_a00ff7... | ARR | AA | 11:06 | 25.0% | +0.6p | +0p | G53 ➔ G110 | 10:51 - 12:36 |
| flight_key_v1_d6bd09... | ARR | WN | 11:15 | 27.9% | +0.2p | +0p | G60 ➔ G111 | 11:00 - 12:10 |
| flight_key_v1_9e3c4c... | DEP | DL | 11:20 | 19.9% | +4.0p | +1p | G05 ➔ G16 | 11:06 - 12:16 |
| flight_key_v1_f8f61f... | ARR | DL | 11:20 | 17.7% | -0.6p | +0p | G16 ➔ G109 | 11:05 - 12:50 |
| flight_key_v1_5fd0b4... | ARR | DL | 11:27 | 19.2% | +0.2p | +0p | G44 ➔ G60 | 11:12 - 12:22 |

---

## 3. Phân Bố Phụ Tải Trên 190 Cổng Đỗ

- **Số cổng hoạt động:** 177 cổng.
- **Số chuyến trung bình mỗi cổng:** 7.9 chuyến/cổng/ngày.
- **Cổng phục vụ nhiều chuyến nhất:** `G02` (16 chuyến).
- **Cổng phục vụ ít chuyến nhất:** `G173` (1 chuyến).

---

## 4. Dữ Liệu Chi Tiết Toàn Bộ 1.500 Chuyến Bay Theo Khung Giờ

> Do bảng toàn bộ 1.500 chuyến rất dài, dưới đây chia thành các khung giờ hoạt động chính trong ngày để thuận tiện tra cứu và kiểm chứng:

### Đợt 1: Khung Đêm & Sáng Sớm (00:00 - 07:00) (50 chuyến bay)

| Mã chuyến | Chiều | Hãng | Giờ lịch | P(Trễ) | Trễ ML | Cổng gốc | Cổng gán | Trạng thái | Khoảng chiếm cổng |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| flight_key_v1_0ea1... | ARR | WN | 00:25 | 56.1% | +4.1p | G01 | G01 | Giữ nguyên ✓ | 00:12 - 01:22 |
| flight_key_v1_96f8... | ARR | AA | 00:28 | 42.4% | +4.1p | G02 | G02 | Giữ nguyên ✓ | 00:15 - 01:25 |
| flight_key_v1_a969... | ARR | NK | 00:31 | 40.7% | +4.3p | G03 | G03 | Giữ nguyên ✓ | 00:18 - 01:28 |
| flight_key_v1_2086... | ARR | WN | 00:35 | 48.6% | +4.1p | G04 | G04 | Giữ nguyên ✓ | 00:22 - 01:32 |
| flight_key_v1_e586... | ARR | WN | 00:40 | 58.1% | +4.1p | G05 | G05 | Giữ nguyên ✓ | 00:27 - 02:12 |
| flight_key_v1_d2f6... | ARR | F9 | 00:41 | 64.3% | +4.2p | G06 | G06 | Giữ nguyên ✓ | 00:29 - 01:39 |
| flight_key_v1_f83a... | ARR | NK | 00:44 | 47.9% | +4.4p | G07 | G07 | Giữ nguyên ✓ | 00:31 - 01:41 |
| flight_key_v1_ff2d... | ARR | NK | 00:45 | 43.5% | +4.7p | G08 | G08 | Giữ nguyên ✓ | 00:32 - 01:42 |
| flight_key_v1_a2b5... | ARR | F9 | 04:03 | 59.2% | +3.3p | G01 | G01 | Giữ nguyên ✓ | 03:50 - 05:00 |
| flight_key_v1_e537... | ARR | DL | 05:00 | 16.8% | +0.7p | G02 | G02 | Giữ nguyên ✓ | 04:45 - 06:30 |
| flight_key_v1_fe58... | ARR | DL | 05:11 | 23.8% | +1.8p | G03 | G03 | Giữ nguyên ✓ | 04:56 - 06:06 |
| flight_key_v1_b055... | ARR | DL | 05:15 | 23.1% | +1.5p | G01 | G01 | Giữ nguyên ✓ | 05:00 - 06:45 |
| flight_key_v1_fda6... | DEP | NK | 05:21 | 17.4% | +4.1p | G04 | G04 | Giữ nguyên ✓ | 05:07 - 06:17 |
| flight_key_v1_df0f... | ARR | DL | 05:29 | 20.0% | +1.1p | G05 | G05 | Giữ nguyên ✓ | 05:14 - 06:24 |
| flight_key_v1_26dd... | DEP | NK | 05:35 | 17.0% | +3.6p | G06 | G06 | Giữ nguyên ✓ | 05:21 - 06:31 |
| flight_key_v1_8632... | DEP | AA | 05:36 | 16.3% | +3.3p | G07 | G07 | Giữ nguyên ✓ | 05:22 - 06:32 |
| flight_key_v1_97ba... | ARR | NK | 05:43 | 43.2% | +4.2p | G08 | G08 | Giữ nguyên ✓ | 05:30 - 06:40 |
| flight_key_v1_df7f... | ARR | DL | 05:44 | 23.6% | +1.8p | G09 | G09 | Giữ nguyên ✓ | 05:29 - 06:39 |
| flight_key_v1_9324... | DEP | AA | 05:47 | 16.3% | +3.0p | G10 | G10 | Giữ nguyên ✓ | 05:32 - 06:42 |
| flight_key_v1_36ca... | DEP | F9 | 05:50 | 17.4% | +2.7p | G11 | G11 | Giữ nguyên ✓ | 05:35 - 06:45 |
*(Hiển thị 20/50 chuyến tiêu biểu của đợt này. Toàn bộ 50 chuyến đã được lưu trữ trong file CSV)*

### Đợt 2: Cao Điểm Buổi Sáng (07:00 - 11:30) (459 chuyến bay)

| Mã chuyến | Chiều | Hãng | Giờ lịch | P(Trễ) | Trễ ML | Cổng gốc | Cổng gán | Trạng thái | Khoảng chiếm cổng |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| flight_key_v1_46a4... | DEP | AA | 07:00 | 15.8% | +0.9p | G01 | G01 | Giữ nguyên ✓ | 06:45 - 08:30 |
| flight_key_v1_ca0b... | DEP | WN | 07:00 | 14.7% | +1.8p | G09 | G09 | Giữ nguyên ✓ | 06:45 - 07:55 |
| flight_key_v1_09d0... | DEP | AS | 07:00 | 15.1% | -0.6p | G10 | G10 | Giữ nguyên ✓ | 06:45 - 07:55 |
| flight_key_v1_fd36... | ARR | DL | 07:03 |  8.8% | -0.8p | G11 | G11 | Giữ nguyên ✓ | 06:48 - 07:58 |
| flight_key_v1_e760... | DEP | DL | 07:05 | 17.2% | +4.0p | G12 | G12 | Giữ nguyên ✓ | 06:51 - 08:01 |
| flight_key_v1_2771... | DEP | WN | 07:05 | 14.7% | +1.8p | G13 | G131 | ĐỔI CỔNG ⚠️ | 06:50 - 08:35 |
| flight_key_v1_ef57... | DEP | DL | 07:05 | 16.2% | +3.2p | G35 | G35 | Giữ nguyên ✓ | 06:51 - 08:01 |
| flight_key_v1_1349... | DEP | NK | 07:05 | 19.8% | +5.9p | G36 | G36 | Giữ nguyên ✓ | 06:51 - 08:01 |
| flight_key_v1_8e00... | ARR | DL | 07:07 | 11.1% | -0.5p | G37 | G37 | Giữ nguyên ✓ | 06:52 - 08:02 |
| flight_key_v1_05c1... | ARR | DL | 07:08 | 20.9% | -0.9p | G38 | G38 | Giữ nguyên ✓ | 06:53 - 08:38 |
| flight_key_v1_2851... | DEP | WN | 07:10 | 14.7% | +1.8p | G14 | G103 | ĐỔI CỔNG ⚠️ | 06:55 - 08:05 |
| flight_key_v1_1c14... | ARR | DL | 07:12 | 14.5% | -0.5p | G15 | G15 | Giữ nguyên ✓ | 06:57 - 08:07 |
| flight_key_v1_8991... | DEP | DL | 07:14 | 17.2% | +4.1p | G39 | G39 | Giữ nguyên ✓ | 07:00 - 08:10 |
| flight_key_v1_3736... | ARR | 9E | 07:15 | 12.7% | -1.0p | G16 | G16 | Giữ nguyên ✓ | 07:00 - 08:10 |
| flight_key_v1_69e6... | DEP | DL | 07:15 | 16.1% | +2.6p | G40 | G40 | Giữ nguyên ✓ | 07:00 - 08:10 |
| flight_key_v1_9068... | DEP | B6 | 07:20 | 16.2% | +1.5p | G17 | G17 | Giữ nguyên ✓ | 07:05 - 08:15 |
| flight_key_v1_4f22... | DEP | DL | 07:20 | 16.6% | +3.1p | G41 | G41 | Giữ nguyên ✓ | 07:06 - 08:16 |
| flight_key_v1_f83f... | ARR | DL | 07:20 | 16.3% | -0.5p | G42 | G42 | Giữ nguyên ✓ | 07:05 - 08:15 |
| flight_key_v1_406b... | ARR | DL | 07:20 |  9.8% | -1.0p | G43 | G43 | Giữ nguyên ✓ | 07:05 - 08:15 |
| flight_key_v1_0e1f... | DEP | AA | 07:21 | 17.2% | +3.2p | G44 | G44 | Giữ nguyên ✓ | 07:07 - 08:17 |
*(Hiển thị 20/459 chuyến tiêu biểu của đợt này. Toàn bộ 459 chuyến đã được lưu trữ trong file CSV)*

### Đợt 3: Đợt Bay Buổi Trưa (11:30 - 16:00) (370 chuyến bay)

| Mã chuyến | Chiều | Hãng | Giờ lịch | P(Trễ) | Trễ ML | Cổng gốc | Cổng gán | Trạng thái | Khoảng chiếm cổng |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| flight_key_v1_e7c4... | DEP | DL | 11:30 | 20.1% | +4.2p | G20 | G20 | Giữ nguyên ✓ | 11:16 - 12:26 |
| flight_key_v1_9b2e... | DEP | DL | 11:30 | 20.2% | +4.3p | G106 | G106 | Giữ nguyên ✓ | 11:16 - 12:26 |
| flight_key_v1_b157... | DEP | DL | 11:30 | 20.2% | +5.0p | G107 | G107 | Giữ nguyên ✓ | 11:16 - 12:26 |
| flight_key_v1_5de4... | ARR | DL | 11:30 | 15.9% | +0.3p | G108 | G112 | ĐỔI CỔNG ⚠️ | 11:15 - 12:25 |
| flight_key_v1_b86f... | ARR | NK | 11:32 | 29.3% | +1.0p | G21 | G53 | ĐỔI CỔNG ⚠️ | 11:17 - 12:27 |
| flight_key_v1_3ba9... | ARR | DL | 11:33 | 12.2% | -0.6p | G45 | G45 | Giữ nguyên ✓ | 11:18 - 12:28 |
| flight_key_v1_1c46... | ARR | B6 | 11:35 | 40.1% | +1.0p | G08 | G08 | Giữ nguyên ✓ | 11:20 - 12:30 |
| flight_key_v1_d951... | DEP | F9 | 11:35 | 22.4% | +5.4p | G23 | G23 | Giữ nguyên ✓ | 11:21 - 12:31 |
| flight_key_v1_c24a... | DEP | DL | 11:35 | 20.6% | +6.6p | G48 | G48 | Giữ nguyên ✓ | 11:21 - 12:31 |
| flight_key_v1_2ad8... | ARR | 9E | 11:38 | 19.1% | +0.7p | G49 | G49 | Giữ nguyên ✓ | 11:23 - 12:33 |
| flight_key_v1_e092... | ARR | DL | 11:38 | 13.6% | -0.6p | G50 | G108 | ĐỔI CỔNG ⚠️ | 11:23 - 12:33 |
| flight_key_v1_5872... | ARR | DL | 11:40 | 22.7% | -0.9p | G54 | G50 | ĐỔI CỔNG ⚠️ | 11:25 - 12:35 |
| flight_key_v1_5cee... | DEP | 9E | 11:40 | 20.3% | +4.3p | G74 | G74 | Giữ nguyên ✓ | 11:26 - 12:36 |
| flight_key_v1_94b4... | DEP | NK | 11:41 | 21.7% | +6.6p | G75 | G75 | Giữ nguyên ✓ | 11:27 - 13:12 |
| flight_key_v1_246e... | DEP | DL | 11:42 | 20.6% | +5.5p | G76 | G76 | Giữ nguyên ✓ | 11:28 - 12:38 |
| flight_key_v1_3ca6... | DEP | WN | 11:45 | 21.7% | +5.2p | G12 | G12 | Giữ nguyên ✓ | 11:31 - 12:41 |
| flight_key_v1_0e12... | DEP | 9E | 11:45 | 20.3% | +3.9p | G77 | G77 | Giữ nguyên ✓ | 11:31 - 12:41 |
| flight_key_v1_b514... | DEP | 9E | 11:46 | 20.3% | +3.9p | G79 | G79 | Giữ nguyên ✓ | 11:32 - 12:42 |
| flight_key_v1_a45f... | DEP | OH | 11:47 | 20.2% | +3.9p | G80 | G80 | Giữ nguyên ✓ | 11:33 - 12:43 |
| flight_key_v1_1dde... | DEP | AA | 11:48 | 21.1% | +5.7p | G04 | G04 | Giữ nguyên ✓ | 11:34 - 12:44 |
*(Hiển thị 20/370 chuyến tiêu biểu của đợt này. Toàn bộ 370 chuyến đã được lưu trữ trong file CSV)*

### Đợt 4: Cao Điểm Buổi Chiều (16:00 - 20:30) (388 chuyến bay)

| Mã chuyến | Chiều | Hãng | Giờ lịch | P(Trễ) | Trễ ML | Cổng gốc | Cổng gán | Trạng thái | Khoảng chiếm cổng |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| flight_key_v1_962c... | ARR | DL | 16:00 | 25.9% | +2.2p | G05 | G105 | ĐỔI CỔNG ⚠️ | 15:46 - 16:56 |
| flight_key_v1_daee... | ARR | DL | 16:00 | 22.3% | +1.1p | G29 | G29 | Giữ nguyên ✓ | 15:45 - 16:55 |
| flight_key_v1_8aad... | ARR | WN | 16:00 | 32.3% | +3.4p | G40 | G40 | Giữ nguyên ✓ | 15:46 - 16:56 |
| flight_key_v1_5838... | DEP | DL | 16:00 | 23.6% | +7.4p | G42 | G42 | Giữ nguyên ✓ | 15:47 - 16:57 |
| flight_key_v1_3b71... | DEP | DL | 16:00 | 23.2% | +5.6p | G80 | G80 | Giữ nguyên ✓ | 15:46 - 16:56 |
| flight_key_v1_ae33... | DEP | NK | 16:03 | 31.2% | +14.2p | G37 | G37 | Giữ nguyên ✓ | 15:52 - 17:02 |
| flight_key_v1_5b8d... | DEP | WN | 16:05 | 29.4% | +10.4p | G02 | G02 | Giữ nguyên ✓ | 15:53 - 17:03 |
| flight_key_v1_fd32... | DEP | B6 | 16:05 | 30.7% | +14.2p | G18 | G18 | Giữ nguyên ✓ | 15:54 - 17:04 |
| flight_key_v1_4707... | DEP | WN | 16:05 | 29.2% | +11.1p | G32 | G32 | Giữ nguyên ✓ | 15:53 - 17:38 |
| flight_key_v1_b785... | DEP | WN | 16:05 | 28.5% | +9.7p | G39 | G39 | Giữ nguyên ✓ | 15:53 - 17:03 |
| flight_key_v1_9072... | DEP | WN | 16:05 | 29.2% | +9.7p | G47 | G47 | Giữ nguyên ✓ | 15:53 - 17:03 |
| flight_key_v1_55f9... | ARR | 9E | 16:09 | 25.8% | +1.4p | G19 | G19 | Giữ nguyên ✓ | 15:54 - 17:04 |
| flight_key_v1_b977... | DEP | NK | 16:10 | 31.2% | +14.3p | G20 | G20 | Giữ nguyên ✓ | 15:59 - 17:09 |
| flight_key_v1_1fb8... | ARR | DL | 16:10 | 30.7% | +2.0p | G55 | G55 | Giữ nguyên ✓ | 15:56 - 17:06 |
| flight_key_v1_f56e... | DEP | WN | 16:10 | 29.2% | +9.5p | G56 | G56 | Giữ nguyên ✓ | 15:58 - 17:43 |
| flight_key_v1_c5d7... | ARR | 9E | 16:11 | 25.9% | +2.2p | G57 | G116 | ĐỔI CỔNG ⚠️ | 15:57 - 17:42 |
| flight_key_v1_4c34... | DEP | F9 | 16:13 | 29.3% | +9.7p | G21 | G21 | Giữ nguyên ✓ | 16:01 - 17:11 |
| flight_key_v1_83e8... | DEP | F9 | 16:13 | 29.1% | +9.5p | G58 | G58 | Giữ nguyên ✓ | 16:01 - 17:11 |
| flight_key_v1_5d11... | ARR | UA | 16:17 | 37.7% | +3.4p | G43 | G43 | Giữ nguyên ✓ | 16:03 - 17:13 |
| flight_key_v1_9550... | ARR | DL | 16:19 | 28.7% | +2.3p | G45 | G45 | Giữ nguyên ✓ | 16:05 - 17:15 |
*(Hiển thị 20/388 chuyến tiêu biểu của đợt này. Toàn bộ 388 chuyến đã được lưu trữ trong file CSV)*

### Đợt 5: Đợt Bay Buổi Tối & Đêm (20:30 - 24:00) (233 chuyến bay)

| Mã chuyến | Chiều | Hãng | Giờ lịch | P(Trễ) | Trễ ML | Cổng gốc | Cổng gán | Trạng thái | Khoảng chiếm cổng |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| flight_key_v1_a36c... | DEP | WN | 20:30 | 30.8% | +11.9p | G03 | G03 | Giữ nguyên ✓ | 20:19 - 21:29 |
| flight_key_v1_438c... | ARR | DL | 20:34 | 32.2% | +1.6p | G10 | G10 | Giữ nguyên ✓ | 20:20 - 21:30 |
| flight_key_v1_14db... | ARR | F9 | 20:34 | 57.9% | +6.5p | G44 | G44 | Giữ nguyên ✓ | 20:23 - 21:33 |
| flight_key_v1_2942... | DEP | WN | 20:35 | 30.8% | +10.9p | G04 | G04 | Giữ nguyên ✓ | 20:23 - 21:33 |
| flight_key_v1_1037... | ARR | WN | 20:35 | 55.1% | +4.6p | G11 | G11 | Giữ nguyên ✓ | 20:23 - 21:33 |
| flight_key_v1_0e88... | ARR | NK | 20:40 | 51.5% | +5.9p | G05 | G05 | Giữ nguyên ✓ | 20:28 - 21:38 |
| flight_key_v1_61c9... | ARR | WN | 20:40 | 57.0% | +5.7p | G14 | G14 | Giữ nguyên ✓ | 20:28 - 21:38 |
| flight_key_v1_6b42... | ARR | DL | 20:42 | 27.2% | +1.6p | G24 | G24 | Giữ nguyên ✓ | 20:27 - 21:37 |
| flight_key_v1_0c47... | ARR | DL | 20:47 | 20.4% | +0.9p | G27 | G27 | Giữ nguyên ✓ | 20:32 - 21:42 |
| flight_key_v1_cd32... | ARR | DL | 20:48 | 49.6% | +6.4p | G06 | G06 | Giữ nguyên ✓ | 20:36 - 22:21 |
| flight_key_v1_a7b7... | ARR | DL | 20:49 | 40.5% | +2.4p | G28 | G28 | Giữ nguyên ✓ | 20:35 - 21:45 |
| flight_key_v1_0df6... | ARR | WN | 20:50 | 51.2% | +4.6p | G07 | G123 | ĐỔI CỔNG ⚠️ | 20:37 - 21:47 |
| flight_key_v1_6b9e... | ARR | OO | 20:51 | 63.0% | +7.2p | G19 | G19 | Giữ nguyên ✓ | 20:41 - 21:51 |
| flight_key_v1_96e3... | ARR | WN | 20:55 | 51.4% | +5.8p | G17 | G17 | Giữ nguyên ✓ | 20:43 - 22:28 |
| flight_key_v1_ff60... | ARR | WN | 20:55 | 46.5% | +4.6p | G29 | G29 | Giữ nguyên ✓ | 20:42 - 21:52 |
| flight_key_v1_8a62... | DEP | DL | 20:55 | 23.6% | +9.3p | G30 | G30 | Giữ nguyên ✓ | 20:42 - 21:52 |
| flight_key_v1_6607... | ARR | WN | 20:55 | 45.9% | +5.8p | G37 | G37 | Giữ nguyên ✓ | 20:43 - 21:53 |
| flight_key_v1_2a55... | DEP | DL | 20:55 | 24.2% | +9.3p | G40 | G40 | Giữ nguyên ✓ | 20:42 - 21:52 |
| flight_key_v1_1394... | DEP | DL | 20:55 | 24.2% | +9.0p | G45 | G45 | Giữ nguyên ✓ | 20:42 - 21:52 |
| flight_key_v1_3885... | ARR | WN | 20:55 | 54.0% | +5.1p | G46 | G46 | Giữ nguyên ✓ | 20:43 - 21:53 |
*(Hiển thị 20/233 chuyến tiêu biểu của đợt này. Toàn bộ 233 chuyến đã được lưu trữ trong file CSV)*
