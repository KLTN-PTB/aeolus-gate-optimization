# Báo Cáo Kiểm Thử Ứng Suất Tái Phân Bổ Cổng Đỗ (Gate Reassignment Stress-Test)

**Mô phỏng tình huống sự cố kép:** Bão thời tiết dồn toa (+75p) & Hỏng cầu dẫn đóng cổng G04

*Bộ giải:* Google OR-Tools CP-SAT | *Thời gian giải:* 0.035s | *Trạng thái:* OPTIMAL

## 1. Tổng Hợp Chỉ Số Kiểm Thử (Stress-Test KPIs)

| Chỉ số | Giá trị |
| --- | --- |
| Tổng số chuyến bay cần phục vụ | 30 chuyến (Khung giờ cao điểm 10:00 - 18:00) |
| Số cổng ban đầu | 8 cổng (G01 đến G08) |
| Sự cố cổng khẩn cấp | Cổng G04 bị đóng hoàn toàn (Hỏng cầu dẫn) |
| Số chuyến bị đè giờ hoặc mất cổng ban đầu | 3 chuyến |
| Trạng thái nghiệm toán học | OPTIMAL (Nghiệm tốt nhất toàn cục) |
| Thời gian giải thuật toán | 0.035 giây |
| Số chuyến bay được CP-SAT đổi cổng | 3/30 chuyến (10.0%) |
| Số chuyến bay được bảo toàn cổng gốc | 27/30 chuyến (90.0%) |
| Xung đột thời gian tại các cổng còn lại | 0 xung đột (Bảo đảm an toàn 100%) |

## 2. Danh Sách Các Chuyến Bay Được CP-SAT Điều Phối Đổi Cổng

> CP-SAT tự động tìm các 'khe trống' (slack time) tại các cổng khác để dời máy bay vào, tránh hoàn toàn va chạm:

| Mã | Chiều | Giờ Lịch | Giờ Bay Mới | Mức Trễ | Cổng Gốc->Mới | Khung Giờ Cổng | Nguyên nhân sự cố kích hoạt đổi cổng |
| --- | --- | --- | --- | --- | --- | --- | --- |
| FL_03 | DEP | 13:00 | 13:45 | 45.0 | G05->G02 | 12:45->14:00 | Trễ bão +45p (Xung đột cổng cũ) |
| FL_05 | DEP | 15:00 | 15:00 | 0.0 | G04->G02 | 14:00->15:15 | Mất cổng do G04 hỏng khẩn cấp (Đóng cửa sửa chữa) |
| FL_14 | ARR | 18:00 | 18:00 | 0.0 | G04->G02 | 17:45->18:30 | Mất cổng do G04 hỏng khẩn cấp (Đóng cửa sửa chữa) |

## 3. Bảng Chi Tiết Toàn Bộ 32 Chuyến Bay Trong Kịch Bản

| Mã | Chiều | Lịch | Dự Báo | Trễ | Cổng Gốc->Mới | Khung Cổng | Điều Phối | Tình Trạng |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FL_01 | DEP | 11:00 | 11:00 | 0.0 | G01->G01 | 10:00->11:15 | Giữ nguyên ✓ | Đúng giờ (Lịch trình giữ nguyên) |
| FL_02 | ARR | 12:00 | 12:00 | 0.0 | G10->G10 | 11:45->12:30 | Giữ nguyên ✓ | Đúng giờ (Lịch trình giữ nguyên) |
| FL_03 | DEP | 13:00 | 13:45 | 45.0 | G05->G02 | 12:45->14:00 | ĐỔI CỔNG ⚠️ | Trễ bão +45p (Xung đột cổng cũ) |
| FL_04 | ARR | 14:00 | 14:00 | 0.0 | G08->G08 | 13:45->14:30 | Giữ nguyên ✓ | Đúng giờ (Lịch trình giữ nguyên) |
| FL_05 | DEP | 15:00 | 15:00 | 0.0 | G04->G02 | 14:00->15:15 | ĐỔI CỔNG ⚠️ | Mất cổng do G04 hỏng khẩn cấp (Đóng cửa sửa chữa) |
| FL_06 | ARR | 16:00 | 16:00 | 0.0 | G06->G06 | 15:45->16:30 | Giữ nguyên ✓ | Đúng giờ (Lịch trình giữ nguyên) |
| FL_07 | DEP | 17:00 | 17:50 | 50.0 | G07->G07 | 16:50->18:05 | Giữ nguyên ✓ | Trễ kỹ thuật +50p (Xung đột cổng cũ) |
| FL_08 | ARR | 12:00 | 12:00 | 0.0 | G02->G02 | 11:45->12:30 | Giữ nguyên ✓ | Đúng giờ (Lịch trình giữ nguyên) |
| FL_09 | DEP | 13:00 | 13:00 | 0.0 | G01->G01 | 12:00->13:15 | Giữ nguyên ✓ | Đúng giờ (Lịch trình giữ nguyên) |
| FL_10 | ARR | 14:00 | 14:00 | 0.0 | G05->G05 | 13:45->14:30 | Giữ nguyên ✓ | Đúng giờ (Lịch trình giữ nguyên) |
| FL_11 | DEP | 15:00 | 15:00 | 0.0 | G07->G07 | 14:00->15:15 | Giữ nguyên ✓ | Đúng giờ (Lịch trình giữ nguyên) |
| FL_12 | ARR | 16:00 | 17:00 | 60.0 | G01->G01 | 16:45->17:30 | Giữ nguyên ✓ | Trễ dây chuyền +60p (Xung đột cổng cũ) |
| FL_13 | DEP | 17:00 | 17:00 | 0.0 | G05->G05 | 16:00->17:15 | Giữ nguyên ✓ | Đúng giờ (Lịch trình giữ nguyên) |
| FL_14 | ARR | 18:00 | 18:00 | 0.0 | G04->G02 | 17:45->18:30 | ĐỔI CỔNG ⚠️ | Mất cổng do G04 hỏng khẩn cấp (Đóng cửa sửa chữa) |
| FL_15 | DEP | 19:00 | 19:00 | 0.0 | G10->G10 | 18:00->19:15 | Giữ nguyên ✓ | Đúng giờ (Lịch trình giữ nguyên) |
| FL_16 | ARR | 14:00 | 14:00 | 0.0 | G10->G10 | 13:45->14:30 | Giữ nguyên ✓ | Đúng giờ (Lịch trình giữ nguyên) |
| FL_17 | DEP | 15:00 | 15:00 | 0.0 | G01->G01 | 14:00->15:15 | Giữ nguyên ✓ | Đúng giờ (Lịch trình giữ nguyên) |
| FL_18 | ARR | 16:00 | 16:45 | 45.0 | G02->G02 | 16:30->17:15 | Giữ nguyên ✓ | Trễ thời tiết +45p (Xung đột cổng cũ) |
| FL_19 | DEP | 17:00 | 17:00 | 0.0 | G03->G03 | 16:00->17:15 | Giữ nguyên ✓ | Đúng giờ (Lịch trình giữ nguyên) |
| FL_20 | ARR | 18:00 | 18:00 | 0.0 | G06->G06 | 17:45->18:30 | Giữ nguyên ✓ | Đúng giờ (Lịch trình giữ nguyên) |
| FL_21 | DEP | 19:00 | 19:00 | 0.0 | G01->G01 | 18:00->19:15 | Giữ nguyên ✓ | Đúng giờ (Lịch trình giữ nguyên) |
| FL_22 | ARR | 20:00 | 20:00 | 0.0 | G06->G06 | 19:45->20:30 | Giữ nguyên ✓ | Đúng giờ (Lịch trình giữ nguyên) |
| FL_23 | DEP | 21:00 | 21:00 | 0.0 | G03->G03 | 20:00->21:15 | Giữ nguyên ✓ | Đúng giờ (Lịch trình giữ nguyên) |
| FL_24 | ARR | 16:00 | 16:00 | 0.0 | G10->G10 | 15:45->16:30 | Giữ nguyên ✓ | Đúng giờ (Lịch trình giữ nguyên) |
| FL_25 | DEP | 17:00 | 17:00 | 0.0 | G09->G09 | 16:00->17:15 | Giữ nguyên ✓ | Đúng giờ (Lịch trình giữ nguyên) |
| FL_26 | ARR | 18:00 | 18:00 | 0.0 | G05->G05 | 17:45->18:30 | Giữ nguyên ✓ | Đúng giờ (Lịch trình giữ nguyên) |
| FL_27 | DEP | 19:00 | 19:00 | 0.0 | G08->G08 | 18:00->19:15 | Giữ nguyên ✓ | Đúng giờ (Lịch trình giữ nguyên) |
| FL_28 | ARR | 20:00 | 20:00 | 0.0 | G09->G09 | 19:45->20:30 | Giữ nguyên ✓ | Đúng giờ (Lịch trình giữ nguyên) |
| FL_29 | DEP | 21:00 | 21:00 | 0.0 | G05->G05 | 20:00->21:15 | Giữ nguyên ✓ | Đúng giờ (Lịch trình giữ nguyên) |
| FL_30 | ARR | 22:00 | 22:00 | 0.0 | G01->G01 | 21:45->22:30 | Giữ nguyên ✓ | Đúng giờ (Lịch trình giữ nguyên) |

## 4. Phụ Tải Các Cổng Sau Khi Tái Phân Bổ (G04 đã đóng)

| Cổng | Số chuyến phục vụ | Phụ tải |
| --- | --- | --- |
| G01 | 6 | ██████ |
| G02 | 5 | █████ |
| G03 | 2 | ██ |
| G05 | 4 | ████ |
| G06 | 3 | ███ |
| G07 | 2 | ██ |
| G08 | 2 | ██ |
| G09 | 2 | ██ |
| G10 | 4 | ████ |
| G04 (Hỏng) | 0 | [ĐÓNG CỬA SỬA CHỮA] |
