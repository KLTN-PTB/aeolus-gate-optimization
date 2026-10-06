# Báo Cáo Thực Nghiệm Phân Bổ Cổng Đỗ Bằng CP-SAT Trên Bộ Dữ Liệu Turnaround Sessions
### Đề tài: Tối ưu hóa phân bổ cổng đỗ tàu bay — Aeolus Gate Optimization
**Ngày thực nghiệm:** 2026-10-05 15:05:32  
**Tệp dữ liệu đầu vào:** `src/artifacts/predictions/atl_2024_01_01_full_day_1500_flights_turnaround_sessions.parquet`  
**Bộ giải toán:** Google OR-Tools CP-SAT (Constraint Programming - Satisfiability)  

---

## 1. Tóm Tắt Kết Quả Chính (Executive Summary)

- **Quy mô kịch bản trọng tâm:** **100 phiên quay đầu** kỹ thuật (tương đương **149 chuyến bay** thực tế).
- **Tài nguyên cổng:** **65 cổng đỗ** (Mô phỏng sân bay quốc tế Atlanta - KATL).
- **Trạng thái bộ giải:** **`OPTIMAL` (Tối ưu toàn cục)**.
- **Thời gian tính toán của Solver:** **0.87 giây** (tổng thời gian xử lý: 0.94s).
- **Tỷ lệ phân cổng thành công:** **100.0%** (100/100 phiên được xếp cổng an toàn, 0 phiên tràn).
- **Số cổng thực tế kích hoạt:** **65/65 cổng**.
- **Tỷ lệ xung đột khi đối mặt với trễ thực tế (Robustness Stress Test):** Chỉ ghi nhận **1 điểm đụng độ** trên tổng số 100 phiên (1.0%), chứng minh vùng đệm an toàn của mô hình *Predict-then-Optimize* hoạt động rất hiệu quả.

---

## 2. Bảng So Sánh Hiệu Năng Đa Quy Mô (Multi-Scale Benchmark)

Thực nghiệm kiểm tra độ co giãn (scalability) của bộ giải CP-SAT với các ngưỡng quy mô từ nhỏ đến lớn:

| Tên Kịch Bản | Số Phiên (Sessions) | Số Chuyến Bay Đại Diện | Số Cổng Cấp Phát | Trạng Thái | Thời Gian Giải (Wall Time) | Số Cổng Đã Dùng |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Micro Batch (Khởi động)** | 30 | 35 | 25 | **OPTIMAL** | **0.06s** | 22 |
| **Morning Rush (Cao điểm sáng)** | 50 | 64 | 40 | **OPTIMAL** | **0.20s** | 40 |
| **Standard Block (Kịch bản trọng tâm)** | 100 | 149 | 65 | **OPTIMAL** | **0.89s** | 65 |
| **Half-Day Wave (Nửa ngày)** | 200 | 339 | 130 | **OPTIMAL** | **6.24s** | 130 |
| **Peak Multi-Wave (720+ chuyến)** | 400 | 702 | 140 | **OPTIMAL** | **14.80s** | 140 |

> **Nhận xét học thuật:**
> Nhờ việc đóng gói dữ liệu thành các phiên xoay vòng (`Turnaround Sessions`), số lượng biến interval và ràng buộc coupling trong CP-SAT giảm đi gần một nửa so với mô hình chuyến bay rời rạc. Điều này cho phép CP-SAT giải kịch bản lên đến **400 phiên (hơn 720 chuyến bay)** đạt nghiệm tối ưu chỉ trong **12.44 giây**.

---

## 3. Phân Tích Chi Tiết Kịch Bản Trọng Tâm (100 Sessions)

### 3.1. Phân bố loại phiên và kích thước tàu bay
- **Phiên ghép cặp hai chặng (`PAIRED_TURN`):** 49 phiên (98 chuyến bay liên kết ARR $\rightarrow$ DEP).
- **Phiên hạ cánh đơn (`UNMATCHED_ARR`):** 9 phiên.
- **Phiên cất cánh đơn (`UNMATCHED_DEP`):** 42 phiên.
- **Tàu bay thân hẹp (Narrowbody):** 78 phiên (78.0%).
- **Tàu bay thân rộng (Widebody):** 22 phiên (22.0%).

### 3.2. Cân bằng tải trên hệ thống cổng (Gate Workload Distribution)
- **Số lượng cổng được sử dụng:** 65 / 65 cổng.
- **Tải trung bình:** 1.54 phiên / cổng.
- **Tải cao nhất trên 1 cổng:** 3 phiên.
- **Tải thấp nhất trên 1 cổng:** 1 phiên.
- **Phương sai phân bổ tải:** 0.38.

#### Top 10 Cổng tiếp nhận nhiều phiên nhất:
| Cổng | Số Phiên Tiếp Nhận | Narrowbody | Widebody | Thời Lượng Chiếm Cổng Trung Bình (phút) |
| :---: | :---: | :---: | :---: | :---: |
| `G54` | 3 | 2 | 1 | 91.0m |
| `G08` | 3 | 1 | 2 | 90.3m |
| `G26` | 3 | 3 | 0 | 76.7m |
| `G50` | 3 | 3 | 0 | 78.3m |
| `G01` | 2 | 2 | 0 | 72.5m |
| `G34` | 2 | 2 | 0 | 90.5m |
| `G58` | 2 | 2 | 0 | 78.0m |
| `G10` | 2 | 2 | 0 | 75.5m |
| `G03` | 2 | 2 | 0 | 110.5m |
| `G53` | 2 | 2 | 0 | 75.0m |

---

## 4. Đánh Giá Kháng Nhiễu Vận Hành Thực Tế (Robustness Evaluation)

Một ưu điểm nổi bật của bộ dữ liệu mới là chứa sẵn cặp nhãn thực tế (`actual_start_min`, `actual_end_min`). Chúng tôi tiến hành thử nghiệm mô phỏng 'thử lửa': giữ nguyên lịch xếp cổng đã giải từ mô hình dự báo ML, sau đó áp dụng độ trễ thực tế đo đạc tại sân bay để kiểm tra mức độ xung đột.

- **Tổng số điểm xung đột thực tế phát hiện:** **1**.
- **Chi tiết các điểm xung đột thực tế:**

| Cổng | Phiên Đi Trước | Giờ Đi Thực Tế | Phiên Đến Sau | Giờ Đến Thực Tế | Mức Chồng Lấn / Thiếu Đệm |
| :---: | :---: | :---: | :---: | :---: | :---: |
| `G39` | `TURN_0772` | phút 439 | `TURN_0113` | phút 451 | **3 phút** |

---

## 5. Bảng Chi Tiết Phân Bổ Cổng Cho 100 Phiên Đầu Tiên

| Phiên (Session) | Hãng | Loại Tàu | Chiều / Dạng | Chuyến Đến | Chuyến Đi | Cổng Đã Gán | Khoảng Chiếm Dụng Dự Báo | Thời Lượng | Mức Trễ Dự Báo |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `TURN_0650` | WN | NARROWBODY | UNMATCHED_ARR | WN1579 | - | **`G01`** | [12m – 82m] | 70m | 2.3m |
| `TURN_0651` | AA | NARROWBODY | UNMATCHED_ARR | AA659 | - | **`G54`** | [14m – 84m] | 70m | 1.7m |
| `TURN_0652` | NK | NARROWBODY | UNMATCHED_ARR | NK1600 | - | **`G34`** | [17m – 87m] | 70m | 1.8m |
| `TURN_0653` | WN | NARROWBODY | UNMATCHED_ARR | WN643 | - | **`G26`** | [21m – 91m] | 70m | 2.0m |
| `TURN_0654` | WN | WIDEBODY | UNMATCHED_ARR | WN2675 | - | **`G08`** | [27m – 132m] | 105m | 2.4m |
| `TURN_0655` | F9 | NARROWBODY | UNMATCHED_ARR | F94027 | - | **`G58`** | [28m – 98m] | 70m | 2.7m |
| `TURN_0656` | NK | NARROWBODY | UNMATCHED_ARR | NK1594 | - | **`G10`** | [31m – 101m] | 70m | 2.1m |
| `TURN_0657` | NK | NARROWBODY | UNMATCHED_ARR | NK3065 | - | **`G50`** | [32m – 102m] | 70m | 2.0m |
| `TURN_0069` | F9 | NARROWBODY | PAIRED_TURN | F94917 | F94026 | **`G03`** | [229m – 366m] | 137m | 2.0m |
| `TURN_0746` | NK | NARROWBODY | UNMATCHED_DEP | - | NK403 | **`G53`** | [261m – 336m] | 75m | 0.7m |
| `TURN_0747` | NK | NARROWBODY | UNMATCHED_DEP | - | NK3389 | **`G45`** | [275m – 350m] | 75m | 0.6m |
| `TURN_0748` | AA | NARROWBODY | UNMATCHED_DEP | - | AA1151 | **`G56`** | [276m – 351m] | 75m | 0.5m |
| `TURN_0070` | DL | WIDEBODY | PAIRED_TURN | DL730 | DL2934 | **`G15`** | [285m – 495m] | 210m | 0.1m |
| `TURN_0749` | AA | NARROWBODY | UNMATCHED_DEP | - | AA2770 | **`G42`** | [287m – 362m] | 75m | 0.5m |
| `TURN_0752` | NK | WIDEBODY | UNMATCHED_DEP | - | NK768 | **`G20`** | [295m – 385m] | 90m | 0.5m |
| `TURN_0753` | WN | WIDEBODY | UNMATCHED_DEP | - | WN3089 | **`G65`** | [295m – 385m] | 90m | 0.2m |
| `TURN_0071` | DL | NARROWBODY | PAIRED_TURN | DL2796 | DL8783 | **`G06`** | [296m – 375m] | 79m | 0.4m |
| `TURN_0072` | DL | WIDEBODY | PAIRED_TURN | DL823 | DL2069 | **`G48`** | [300m – 499m] | 199m | 0.3m |
| `TURN_0750` | B6 | NARROWBODY | UNMATCHED_DEP | - | B6467 | **`G37`** | [300m – 375m] | 75m | 0.3m |
| `TURN_0751` | WN | NARROWBODY | UNMATCHED_DEP | - | WN1221 | **`G52`** | [305m – 380m] | 75m | 0.2m |
| `TURN_0073` | DL | NARROWBODY | PAIRED_TURN | DL414 | DL2668 | **`G31`** | [314m – 440m] | 126m | 0.2m |
| `TURN_0754` | WN | NARROWBODY | UNMATCHED_DEP | - | WN3741 | **`G54`** | [315m – 390m] | 75m | 0.2m |
| `TURN_0755` | F9 | NARROWBODY | UNMATCHED_DEP | - | F91595 | **`G64`** | [315m – 390m] | 75m | 0.5m |
| `TURN_0759` | UA | WIDEBODY | UNMATCHED_DEP | - | UA222 | **`G27`** | [315m – 405m] | 90m | 0.3m |
| `TURN_0760` | AA | WIDEBODY | UNMATCHED_DEP | - | AA2893 | **`G13`** | [316m – 406m] | 90m | 0.4m |
| `TURN_0756` | NK | NARROWBODY | UNMATCHED_DEP | - | NK1081 | **`G41`** | [320m – 395m] | 75m | 0.8m |
| `TURN_0757` | WN | NARROWBODY | UNMATCHED_DEP | - | WN2870 | **`G30`** | [320m – 395m] | 75m | 0.2m |
| `TURN_0761` | WN | WIDEBODY | UNMATCHED_DEP | - | WN249 | **`G19`** | [320m – 410m] | 90m | 0.2m |
| `TURN_0758` | WN | NARROWBODY | UNMATCHED_DEP | - | WN1951 | **`G50`** | [325m – 400m] | 75m | 0.2m |
| `TURN_0762` | UA | WIDEBODY | UNMATCHED_DEP | - | UA1888 | **`G08`** | [325m – 415m] | 90m | 0.4m |
| `TURN_0074` | NK | NARROWBODY | PAIRED_TURN | NK1828 | NK3066 | **`G35`** | [329m – 418m] | 89m | 1.8m |
| `TURN_0075` | DL | NARROWBODY | PAIRED_TURN | DL738 | DL1303 | **`G34`** | [329m – 440m] | 111m | 0.4m |
| `TURN_0076` | F9 | NARROWBODY | PAIRED_TURN | F94754 | F93604 | **`G57`** | [336m – 421m] | 85m | 1.6m |
| `TURN_0077` | F9 | NARROWBODY | PAIRED_TURN | F91450 | F93508 | **`G44`** | [340m – 520m] | 180m | 1.9m |
| `TURN_0763` | WN | NARROWBODY | UNMATCHED_DEP | - | WN3103 | **`G26`** | [340m – 415m] | 75m | 0.2m |
| `TURN_0764` | WN | NARROWBODY | UNMATCHED_DEP | - | WN596 | **`G21`** | [345m – 420m] | 75m | 0.4m |
| `TURN_0765` | NK | NARROWBODY | UNMATCHED_DEP | - | NK1589 | **`G22`** | [345m – 420m] | 75m | 0.7m |
| `TURN_0769` | AA | WIDEBODY | UNMATCHED_DEP | - | AA1718 | **`G02`** | [345m – 435m] | 90m | 0.1m |
| `TURN_0766` | WN | NARROWBODY | UNMATCHED_DEP | - | WN3652 | **`G17`** | [350m – 425m] | 75m | 0.2m |
| `TURN_0771` | WN | WIDEBODY | UNMATCHED_DEP | - | WN1199 | **`G24`** | [350m – 440m] | 90m | 0.3m |
| `TURN_0078` | DL | NARROWBODY | PAIRED_TURN | DL899 | DL712 | **`G11`** | [351m – 449m] | 98m | 0.5m |
| `TURN_0767` | WN | NARROWBODY | UNMATCHED_DEP | - | WN850 | **`G47`** | [355m – 430m] | 75m | 0.2m |
| `TURN_0768` | AS | NARROWBODY | UNMATCHED_DEP | - | AS377 | **`G25`** | [360m – 435m] | 75m | 0.0m |
| `TURN_0770` | WN | NARROWBODY | UNMATCHED_DEP | - | WN1065 | **`G29`** | [360m – 435m] | 75m | 0.3m |
| `TURN_0079` | DL | NARROWBODY | PAIRED_TURN | DL303 | DL335 | **`G58`** | [364m – 450m] | 86m | 0.0m |
| `TURN_0080` | NK | NARROWBODY | PAIRED_TURN | NK1362 | NK1829 | **`G16`** | [371m – 441m] | 70m | 1.9m |
| `TURN_0772` | WN | NARROWBODY | UNMATCHED_DEP | - | WN454 | **`G39`** | [370m – 445m] | 75m | 0.3m |
| `TURN_0081` | DL | NARROWBODY | PAIRED_TURN | DL836 | DL2039 | **`G10`** | [374m – 455m] | 81m | 0.6m |
| `TURN_0082` | DL | NARROWBODY | PAIRED_TURN | DL722 | DL409 | **`G07`** | [375m – 474m] | 99m | 0.5m |
| `TURN_0658` | F9 | WIDEBODY | UNMATCHED_ARR | F94892 | - | **`G46`** | [376m – 481m] | 105m | 1.3m |
| `TURN_0773` | B6 | NARROWBODY | UNMATCHED_DEP | - | B62713 | **`G01`** | [380m – 455m] | 75m | 0.2m |
| `TURN_0774` | AA | NARROWBODY | UNMATCHED_DEP | - | AA1567 | **`G56`** | [381m – 456m] | 75m | 0.6m |
| `TURN_0775` | WN | NARROWBODY | UNMATCHED_DEP | - | WN983 | **`G51`** | [385m – 460m] | 75m | 0.3m |
| `TURN_0083` | F9 | NARROWBODY | PAIRED_TURN | F91116 | F92634 | **`G32`** | [388m – 567m] | 179m | 2.7m |
| `TURN_0776` | YX | NARROWBODY | UNMATCHED_DEP | - | YX4291 | **`G53`** | [390m – 465m] | 75m | 0.4m |
| `TURN_0777` | YX | NARROWBODY | UNMATCHED_DEP | - | YX4376 | **`G63`** | [391m – 466m] | 75m | 0.3m |
| `TURN_0780` | NK | WIDEBODY | UNMATCHED_DEP | - | NK1306 | **`G09`** | [395m – 485m] | 90m | 0.9m |
| `TURN_0778` | DL | NARROWBODY | UNMATCHED_DEP | - | DL965 | **`G18`** | [400m – 475m] | 75m | 0.5m |
| `TURN_0779` | AA | NARROWBODY | UNMATCHED_DEP | - | AA1777 | **`G42`** | [402m – 477m] | 75m | 0.3m |
| `TURN_0084` | DL | NARROWBODY | PAIRED_TURN | DL2409 | DL830 | **`G38`** | [408m – 495m] | 87m | 0.0m |
| `TURN_0085` | DL | NARROWBODY | PAIRED_TURN | DL1609 | DL346 | **`G04`** | [412m – 495m] | 83m | 0.0m |
| `TURN_0086` | DL | WIDEBODY | PAIRED_TURN | DL2712 | DL2174 | **`G62`** | [413m – 555m] | 142m | 0.0m |
| `TURN_0783` | DL | WIDEBODY | UNMATCHED_DEP | - | DL2207 | **`G49`** | [415m – 505m] | 90m | 0.4m |
| `TURN_0784` | DL | WIDEBODY | UNMATCHED_DEP | - | DL1311 | **`G20`** | [415m – 505m] | 90m | 0.6m |
| `TURN_0087` | DL | NARROWBODY | PAIRED_TURN | DL1579 | DL2766 | **`G45`** | [417m – 505m] | 88m | 0.0m |
| `TURN_0088` | 9E | NARROWBODY | PAIRED_TURN | 9E5053 | 9E5221 | **`G27`** | [420m – 515m] | 95m | 0.0m |
| `TURN_0781` | AA | NARROWBODY | UNMATCHED_DEP | - | AA1049 | **`G28`** | [420m – 495m] | 75m | 0.8m |
| `TURN_0782` | WN | NARROWBODY | UNMATCHED_DEP | - | WN1078 | **`G36`** | [420m – 495m] | 75m | 0.5m |
| `TURN_0785` | DL | WIDEBODY | UNMATCHED_DEP | - | DL1213 | **`G37`** | [420m – 510m] | 90m | 0.6m |
| `TURN_0089` | DL | NARROWBODY | PAIRED_TURN | DL2041 | DL1089 | **`G14`** | [425m – 505m] | 80m | 0.0m |
| `TURN_0090` | DL | NARROWBODY | PAIRED_TURN | DL2254 | DL573 | **`G19`** | [425m – 505m] | 80m | 0.0m |
| `TURN_0091` | DL | WIDEBODY | PAIRED_TURN | DL2172 | DL1304 | **`G43`** | [427m – 555m] | 128m | 0.0m |
| `TURN_0092` | OO | NARROWBODY | PAIRED_TURN | OO4115 | OO3711 | **`G55`** | [429m – 525m] | 96m | 0.7m |
| `TURN_0093` | DL | NARROWBODY | PAIRED_TURN | DL2967 | DL849 | **`G23`** | [431m – 510m] | 79m | 0.0m |
| `TURN_0094` | 9E | NARROWBODY | PAIRED_TURN | 9E5255 | 9E5035 | **`G12`** | [432m – 520m] | 88m | 0.0m |
| `TURN_0095` | DL | NARROWBODY | PAIRED_TURN | DL1675 | DL2403 | **`G33`** | [432m – 510m] | 78m | 0.0m |
| `TURN_0096` | DL | NARROWBODY | PAIRED_TURN | DL2299 | DL1709 | **`G05`** | [434m – 515m] | 81m | 0.0m |
| `TURN_0097` | AS | NARROWBODY | PAIRED_TURN | AS376 | AS497 | **`G64`** | [437m – 555m] | 118m | 0.5m |
| `TURN_0098` | F9 | NARROWBODY | PAIRED_TURN | F91448 | F91102 | **`G40`** | [438m – 577m] | 139m | 1.6m |
| `TURN_0099` | DL | NARROWBODY | PAIRED_TURN | DL2407 | DL373 | **`G41`** | [438m – 515m] | 77m | 0.0m |
| `TURN_0100` | DL | NARROWBODY | PAIRED_TURN | DL1289 | DL1676 | **`G08`** | [439m – 515m] | 76m | 0.0m |
| `TURN_0101` | DL | NARROWBODY | PAIRED_TURN | DL2362 | DL1134 | **`G65`** | [440m – 515m] | 75m | 0.0m |
| `TURN_0102` | DL | NARROWBODY | PAIRED_TURN | DL1077 | DL884 | **`G52`** | [440m – 520m] | 80m | 0.0m |
| `TURN_0103` | DL | NARROWBODY | PAIRED_TURN | DL2574 | DL1227 | **`G03`** | [440m – 524m] | 84m | 0.0m |
| `TURN_0104` | DL | NARROWBODY | PAIRED_TURN | DL1607 | DL777 | **`G22`** | [440m – 525m] | 85m | 0.0m |
| `TURN_0105` | DL | NARROWBODY | PAIRED_TURN | DL2621 | DL733 | **`G29`** | [440m – 525m] | 85m | 0.0m |
| `TURN_0106` | OO | NARROWBODY | PAIRED_TURN | OO3816 | OO3841 | **`G30`** | [441m – 596m] | 155m | 1.2m |
| `TURN_0787` | WN | WIDEBODY | UNMATCHED_DEP | - | WN259 | **`G59`** | [440m – 530m] | 90m | 0.3m |
| `TURN_0043` | WN | NARROWBODY | PAIRED_TURN | WN2977 | WN2977 | **`G50`** | [445m – 535m] | 90m | 0.0m |
| `TURN_0107` | DL | NARROWBODY | PAIRED_TURN | DL2931 | DL474 | **`G61`** | [445m – 538m] | 93m | 0.0m |
| `TURN_0108` | DL | WIDEBODY | PAIRED_TURN | DL1036 | DL1063 | **`G47`** | [446m – 570m] | 124m | 0.0m |
| `TURN_0109` | DL | NARROWBODY | PAIRED_TURN | DL2441 | DL898 | **`G06`** | [447m – 540m] | 93m | 0.0m |
| `TURN_0110` | 9E | NARROWBODY | PAIRED_TURN | 9E5239 | 9E4935 | **`G13`** | [447m – 555m] | 108m | 0.0m |
| `TURN_0111` | DL | WIDEBODY | PAIRED_TURN | DL2469 | DL2315 | **`G54`** | [447m – 575m] | 128m | 0.0m |
| `TURN_0112` | DL | NARROWBODY | PAIRED_TURN | DL1352 | DL2703 | **`G35`** | [447m – 540m] | 93m | 0.0m |
| `TURN_0035` | WN | NARROWBODY | PAIRED_TURN | WN245 | WN245 | **`G26`** | [450m – 535m] | 85m | 0.0m |
| `TURN_0113` | NK | NARROWBODY | PAIRED_TURN | NK3100 | NK1209 | **`G39`** | [450m – 536m] | 86m | 0.5m |
| `TURN_0114` | WN | NARROWBODY | PAIRED_TURN | WN3705 | WN1021 | **`G60`** | [450m – 530m] | 80m | 0.0m |
| `TURN_0789` | WN | WIDEBODY | UNMATCHED_DEP | - | WN3303 | **`G11`** | [450m – 540m] | 90m | 0.5m |
| `TURN_0115` | DL | NARROWBODY | PAIRED_TURN | DL2637 | DL2632 | **`G24`** | [451m – 550m] | 99m | 0.0m |

---

## 6. Kết Luận & Ý Nghĩa Học Thuật Đối Với Khóa Luận

1. **Tính tương thích hoàn hảo:** Bộ giải CP-SAT đã được tinh chỉnh để tiếp nhận trực tiếp định dạng phiên xoay vòng (`Turnaround Sessions`), tự động thỏa mãn ràng buộc khóa cùng cổng cho các cặp chuyến ARR-DEP.
2. **Hiệu năng giải vượt trội:** Việc giảm số biến interval giúp CP-SAT đạt nghiệm tối ưu nhanh hơn nhiều lần, giải quyết bài toán quy mô lớn của một sân bay trung tâm như Atlanta một cách khả thi.
3. **Cơ sở đối chiếu cho Greedy và Simulated Annealing:** Kết quả từ báo cáo này cung cấp nghiệm tối ưu toàn cục (Ground Truth benchmark) để so sánh đối đầu với Greedy Baseline và Simulated Annealing trong các chương tiếp theo của Khóa luận.