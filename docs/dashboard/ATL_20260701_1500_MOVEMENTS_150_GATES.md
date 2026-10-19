# Kịch bản ATL 01/07/2026: 1.500 lượt đến–đi, 150 cổng

Chọn `SCEN_2026_07_01_1500_MOVEMENTS_150_GATES` trên thanh bên dashboard.
Vào **Gate Operations**, chọn Greedy, CP-SAT hoặc Hybrid và nhấn **RUN SOLVER**.
CP-SAT và giai đoạn CP-SAT của Hybrid dùng nghiệm Greedy làm gợi ý khởi tạo;
đây là cấu hình riêng cho kịch bản lớn này. Trạng thái FEASIBLE không đồng nghĩa OPTIMAL.

## Dữ liệu và đơn vị đếm

- Nguồn: `data/raw/ontime.td.202607.asc`, BTS ASQP tháng 7/2026.
- Ngày hoạt động: **01/07/2026 theo America/New_York**.
- **750 lượt đến + 750 lượt đi = 1.500 lượt di chuyển**.
- Các lượt này tạo **750 khoảng chiếm dụng cổng**, mỗi khoảng gồm một lượt đến
  và lượt đi kế tiếp của cùng đăng ký tàu bay, cùng hãng khai thác.
- Chọn không hoàn lại 750 trong 769 cặp đủ điều kiện, phân tầng theo hãng và
  giờ đến; seed `202601`. Không tạo chuyến bay giả để đủ số lượng.
- Chỉ chọn lượt quay đầu hoàn chỉnh trong ngày: thời gian ở sân bay 30–720 phút.
  Loại chuyến hủy, chuyển hướng, thiếu đăng ký, múi giờ chưa có trong bảng tra
  hoặc giờ thực tế không khớp bản ghi. Không bổ sung giả các lượt đỗ qua đêm.
- Thời điểm đến được chuẩn hóa từ ngày/giờ khởi hành tại sân bay gốc, múi giờ,
  thời gian bay dự kiến và độ trễ có dấu; không mặc định ngày khởi hành là ngày đến.

## Giả định tài nguyên

- Đúng **150 cổng tiếp xúc, sức chứa mỗi cổng bằng 1**, không có bãi tràn vô hạn.
- Phân khu mô phỏng: T=21, A=29, B=32, C=34, D=34. Đây là cấu hình thử nghiệm,
  không phải xác nhận sơ đồ cổng ATL trong ngày nguồn.
- Cổng danh định được dựng từ lịch dự kiến; BTS không cung cấp mã cổng thực tế.
- Dùng thời gian rời cổng thực tế của lượt đi, không áp mặc định 60 phút cho mọi tàu bay.
- Đệm giãn cách 15 phút; ngưỡng 30 phút là giả định sàng lọc quay đầu, không phải
  tiêu chuẩn phục vụ đã được xác nhận cho mọi loại tàu bay.
- Nhu cầu đồng thời lớn nhất của mẫu: **115 tàu bay, đã bao gồm đệm**.
- Chưa mô phỏng hạn chế thuê cổng theo hãng, tương thích loại tàu bay, kéo tàu bay,
  xe buýt, nhân lực phục vụ hoặc toàn bộ nhu cầu đỗ qua đêm của sân bay.

## Diễn giải thực nghiệm

Đây là **tái hiện lịch sử (historical replay)** với thời gian vào/rời vị trí đỗ
đã quan sát. Bộ giải dùng thông tin hậu nghiệm để phân cổng. Không diễn giải
kết quả thành chất lượng dự báo ML, hiệu quả điều hành nhân quả hay lịch cổng thực tế.
Các sự kiện là giờ vào/rời vị trí đỗ, không phải giờ chạm đất/cất cánh trên đường băng.

Trong Control Tower, tổng lượt là 1.500; Gantt và CSV phân cổng có 750 dòng chiếm dụng.
Flight Intelligence hiển thị các bản ghi quan sát; Robustness Lab không gán kết quả
Monte Carlo của kịch bản cũ cho kịch bản mới.

## Tái tạo

```powershell
.\.venv\Scripts\python.exe scripts/build_atl_20260701_scenario.py
```

Nếu chủ động dựng lại các tệp của riêng kịch bản này, thêm `--overwrite`.
Manifest cùng tên trong `data/simulation` ghi hash nguồn, hash các tệp đầu ra,
tiêu chí chọn mẫu và các giới hạn. Tệp raw chỉ được đọc.
