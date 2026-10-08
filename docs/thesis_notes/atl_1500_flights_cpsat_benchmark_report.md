# Báo Cáo Đánh Giá & Thử Nghiệm Bộ Giải CP-SAT Trên Tập Dữ Liệu 1.500 Chuyến Bay (ATL Full-Day)

> **Tệp dữ liệu thử nghiệm:** `src/artifacts/predictions/atl_2024_01_01_full_day_1500_flights.parquet`  
> **Thời điểm đánh giá:** 2026-10-04  
> **Cấu hình loại máy bay:** Bỏ qua phân biệt kích thước (`aircraft_type = "ALL"`, mọi cổng chấp nhận mọi loại máy bay theo yêu cầu).  
> **Mục tiêu:** Kiểm chứng tính khả thi khi đưa toàn bộ 1.500 chuyến bay trong 1 ngày vào mô hình tối ưu hóa phân bổ cổng đỗ CP-SAT (Google OR-Tools).

---

## 1. Tóm Tắt Kết Quả Thử Nghiệm (Executive Summary)

1. **Khả năng sử dụng dữ liệu:**
   - Tập dữ liệu **`atl_2024_01_01_full_day_1500_flights.parquet`** hoàn toàn hợp lệ, đầy đủ 100% trường thông tin cần thiết và không có giá trị rỗng (`0 null`).
   - Thiết lập **`aircraft_type = "ALL"`** được tuân thủ nghiêm ngặt theo đúng định hướng của nhóm, không phát sinh bất kỳ ràng buộc loại trừ nào liên quan đến thân hẹp (Narrowbody) hay thân rộng (Widebody).

2. **Khả năng giải của CP-SAT trên quy mô 1.500 chuyến:**
   - **Theo lát cắt vận hành (Operational Banks / Time Windows):** Bộ giải CP-SAT hoạt động **cực kỳ xuất sắc**:
     - Lát cắt **100 chuyến đầu ngày**: Đạt trạng thái **OPTIMAL** trong **0.74 giây** (với 50 cổng).
     - Đợt **cao điểm sáng (359 chuyến từ 06:00 đến 10:00)**: Đạt trạng thái **OPTIMAL** trong **20.46 giây** (với 195 cổng).
   - **Theo mô hình nguyên khối cả ngày 24h (Monolithic 1.500 chuyến):**
     - Đòi hỏi tối thiểu **192–195 cổng** vì phụ tải đồng thời tại ATL đạt đỉnh **143 máy bay** lúc 09:10.
     - Nếu giải nguyên khối cả 1.500 chuyến một lúc với 200 cổng, mô hình sinh ra hơn **300.000 biến nhị phân** và **300.000 biến khoảng (IntervalVar)**, dẫn đến tình trạng quá thời gian giải (timeout ở 30s–60s) hoặc không tìm ra nghiệm khả thi nếu giữ nguyên 43 chuỗi khứ hồi out-and-back.

---

## 2. Đặc Tính Kỹ Thuật Tập Dữ Liệu 1.500 Chuyến Bay

| Đặc tính | Giá trị thống kê | Nhận xét kỹ thuật |
| :--- | :--- | :--- |
| **Tổng số chuyến bay** | 1.500 chuyến (745 Đến - ARR, 755 Đi - DEP) | Tỷ lệ ARR/DEP cân bằng hoàn hảo (1:1.01) |
| **Phạm vi thời gian** | Phút 25 (00:25) đến Phút 1439 (23:59) | Phủ trọn vẹn 24 giờ của ngày 01/01/2024 |
| **Phụ tải đồng thời cực đại** | **143 máy bay** tại phút 550 (09:10) | Trùng khớp với quy mô vật lý thực tế của ATL (~192–196 cổng tiếp xúc) |
| **Xác suất trễ ($P_{\text{delay}}$)** | Trung bình: 31.4% (Min: 5.2%, Max: 88.6%) | Dữ liệu đầu ra từ mô hình phân loại ML Classifier |
| **Phút trễ dự báo ($D_{\text{est}}$)** | Trung bình: 12.8 phút (Min: 0.0, Max: 78.4) | Dữ liệu đầu ra từ mô hình hồi quy ML Regressor |
| **Thời gian quay đầu ($T_{\text{turn}}$)**| 40 phút và 75 phút | Phục vụ tính toán thời gian chiếm cổng theo chuỗi xoay vòng |
| **Cấu hình loại tàu bay** | 100% gán `ALL` | Đáp ứng yêu cầu bỏ qua hạn chế loại máy bay |

---

## 3. Bảng Kết Quả Benchmark Hiệu Năng Bộ Giải CP-SAT

| Kịch bản thử nghiệm | Số chuyến | Số cổng | Ràng buộc áp dụng | Trạng thái CP-SAT | Thời gian giải |
| :--- | :---: | :---: | :--- | :---: | :---: |
| **1. Lát cắt sáng sớm** | 100 chuyến | 50 cổng | Không chồng chéo + Dwell + Quay đầu | **OPTIMAL** | **0.74s** |
| **2. Đợt cao điểm sáng (06h - 10h)** | 359 chuyến | 195 cổng | Không chồng chéo + Chuỗi quay đầu mặt đất | **OPTIMAL** | **20.46s** |
| **3. Toàn bộ 1.500 chuyến (24h)** | 1.500 chuyến | 200 cổng | Nguyên khối 24h (300.000 biến) | `UNKNOWN` (Timeout) / `INFEASIBLE`* | > 60.00s |

> *( \* ) Ghi chú:* Kịch bản 3 bị `INFEASIBLE` khi kích hoạt ghép cặp tự động trên 43 chuỗi khứ hồi (*out-and-back* - máy bay cất cánh từ ATL đi nơi khác vào buổi sáng và đến chiều tối mới quay về ATL). Trong khoảng giữa 8-9 tiếng đó, máy bay không có mặt tại ATL nên việc ép chiếm cổng liên tục là không thực tế.

---

## 4. Chi Tiết Phân Bổ Cổng Cho Mẫu 25 Chuyến Bay Đầu Tiên (Trích Xuất Kết Quả CP-SAT)

| Mã chuyến | Chiều | Giờ lịch | P(Trễ) | Trễ ML (phút) | Giờ cất cánh tính | Khoảng chiếm cổng | Cổng được gán |
| --- | --- | --- | --- | --- | --- | --- | --- |
| flight_key_v1_0ea1de... | ARR | 00:25 | 56.1% | +4.1 | 01:07 | 00:12 -> 01:22 | G43 |
| flight_key_v1_96f840... | ARR | 00:28 | 42.4% | +4.1 | 01:09 | 00:14 -> 01:24 | G01 |
| flight_key_v1_a9694e... | ARR | 00:31 | 40.7% | +4.3 | 01:12 | 00:17 -> 01:27 | G48 |
| flight_key_v1_20869c... | ARR | 00:35 | 48.6% | +4.1 | 01:16 | 00:21 -> 01:31 | G23 |
| flight_key_v1_e58642... | ARR | 00:40 | 58.1% | +4.1 | 01:57 | 00:27 -> 02:12 | G41 |
| flight_key_v1_d2f6b6... | ARR | 00:41 | 64.3% | +4.2 | 01:23 | 00:28 -> 01:38 | G03 |
| flight_key_v1_f83afb... | ARR | 00:44 | 47.9% | +4.4 | 01:26 | 00:31 -> 01:41 | G44 |
| flight_key_v1_ff2d15... | ARR | 00:45 | 43.5% | +4.7 | 01:27 | 00:32 -> 01:42 | G29 |
| flight_key_v1_a2b5b1... | ARR | 04:03 | 59.2% | +3.3 | 04:44 | 03:49 -> 04:59 | G43 |
| flight_key_v1_e53740... | ARR | 05:00 | 16.8% | +0.7 | 06:15 | 04:45 -> 06:30 | G44 |
| flight_key_v1_fe5804... | ARR | 05:11 | 23.8% | +1.8 | 05:51 | 04:56 -> 06:06 | G26 |
| flight_key_v1_b0555a... | ARR | 05:15 | 23.1% | +1.5 | 06:30 | 05:00 -> 06:45 | G27 |
| flight_key_v1_fda60f... | DEP | 05:21 | 17.4% | +4.1 | 05:21 | 04:21 -> 05:36 | G38 |
| flight_key_v1_df0fd8... | ARR | 05:29 | 20.0% | +1.1 | 06:09 | 05:14 -> 06:24 | G09 |
| flight_key_v1_26dd8b... | DEP | 05:35 | 17.0% | +3.6 | 05:35 | 04:35 -> 05:50 | G46 |
| flight_key_v1_8632b1... | DEP | 05:36 | 16.3% | +3.3 | 05:36 | 04:36 -> 05:51 | G08 |
| flight_key_v1_97bab9... | ARR | 05:43 | 43.2% | +4.2 | 06:24 | 05:29 -> 06:39 | G14 |
| flight_key_v1_df7f38... | ARR | 05:44 | 23.6% | +1.8 | 06:24 | 05:29 -> 06:39 | G16 |
| flight_key_v1_9324db... | DEP | 05:47 | 16.3% | +3.0 | 05:47 | 04:47 -> 06:02 | G50 |
| flight_key_v1_36ca44... | DEP | 05:50 | 17.4% | +2.7 | 05:50 | 04:50 -> 06:05 | G15 |
| flight_key_v1_f1bb81... | ARR | 05:50 | 46.6% | +3.3 | 06:31 | 05:36 -> 06:46 | G19 |
| flight_key_v1_2077b6... | ARR | 05:54 | 55.0% | +3.4 | 06:35 | 05:40 -> 06:50 | G21 |
| flight_key_v1_239ce8... | DEP | 06:00 | 16.3% | +1.6 | 06:00 | 05:00 -> 06:15 | G07 |
| flight_key_v1_62646d... | DEP | 06:00 | 16.3% | +3.4 | 06:00 | 05:00 -> 06:15 | G35 |
| flight_key_v1_a49be6... | DEP | 06:05 | 13.2% | +1.5 | 06:05 | 05:05 -> 06:20 | G18 |

---

## 5. Phân Bố Phụ Tải Trên Các Cổng Đỗ (Mẫu 20 Cổng Đầu)

| Cổng đỗ | Số chuyến phục vụ | Biểu đồ phụ tải |
| --- | --- | --- |
| G01 | 2 | ██ |
| G02 | 2 | ██ |
| G03 | 3 | ███ |
| G04 | 2 | ██ |
| G05 | 1 | █ |
| G06 | 1 | █ |
| G07 | 2 | ██ |
| G08 | 2 | ██ |
| G09 | 2 | ██ |
| G10 | 2 | ██ |
| G11 | 1 | █ |
| G12 | 2 | ██ |
| G13 | 1 | █ |
| G14 | 2 | ██ |
| G15 | 2 | ██ |
| G16 | 2 | ██ |
| G17 | 2 | ██ |
| G18 | 2 | ██ |
| G19 | 2 | ██ |
| G20 | 2 | ██ |

---

## 6. Đánh Giá & Kiến Nghị Cho Khóa Luận

1. **Về dữ liệu:** Tập dữ liệu 1.500 chuyến là tài nguyên thực nghiệm rất giá trị, có độ chân thực cao, thể hiện được các làn sóng hạ cánh/cất cánh dồn dập (peak banks) đặc trưng của các siêu sân bay trung chuyển như Atlanta.
2. **Về chiến lược phân cổng thực tế:**
   - Trong vận hành sân bay thực tế, không có trung tâm điều hành nào (AOC) giải phân cổng tĩnh một lần cho cả 1.500 chuyến 24h trong một mô hình toán nguyên khối vì tính bất định của thời tiết và trễ tích lũy.
   - Thay vào đó, mô hình giải theo **khung giờ cao điểm (Bank-based / Time-window: 300–400 chuyến)** hoặc **cửa sổ trượt (Rolling-horizon: 2–4 giờ)** với thời gian giải dưới **20 giây** là giải pháp chuẩn công nghiệp, vừa đảm bảo tính tối ưu toàn cục theo đợt bay, vừa có khả năng phản ứng theo thời gian thực (Real-time Dynamic Reassignment).
