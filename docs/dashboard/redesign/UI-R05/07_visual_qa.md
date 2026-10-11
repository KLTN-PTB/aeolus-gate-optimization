# UI-R05: Visual Quality Assurance & Manual Inspection Checklist

## 1. Tuyên Bố Liêm Chính Trực Quan (Honest Visual QA Disclosure)

> [!IMPORTANT]
> **Trạng thái Thẩm định Trực quan:** `VISUAL_QA_PENDING` (Chờ người dùng/Hội đồng thẩm duyệt trực tiếp trên trình duyệt).
> Hệ thống tuân thủ nguyên tắc liêm chính khoa học: **Tuyệt đối không tạo screenshot giả mạo hoặc báo cáo kết quả kiểm tra giao diện không có thật**.

Do môi trường dòng lệnh không có visual display server để chụp ảnh màn hình trình duyệt thực tế, tài liệu này cung cấp **Checklist Kiểm Tra Thủ Công (Manual Inspection Checklist)** chi tiết để người dùng hoặc giảng viên hướng dẫn có thể khởi chạy `streamlit run` và thẩm duyệt trực tiếp.

## 2. Hướng Dẫn Khởi Chạy Thẩm Duyệt
Chạy lệnh sau trong terminal để khởi động dashboard:
```bash
.venv\Scripts\activate
streamlit run dashboard/app.py
```
Sau đó mở trình duyệt tại địa chỉ `http://localhost:8501` và chuyển đến trang **"03. Gate Operations (Phân cổng & Gantt)"**.

## 3. Danh Mục Kiểm Tra Trực Quan Thủ Công (Checklist)

### A. Bố Cục Không Gian & Độ Rộng Biểu Đồ Gantt
- [ ] **Toàn màn hình ngang:** Biểu đồ Master Interactive Gantt chiếm trọn vẹn 100% chiều rộng khu vực làm việc chính (không bị bóp méo vào cột 8.5/12 như trước).
- [ ] **Thứ tự trục tung:** Cổng đầu tiên ($G\_01$) hiển thị ở hàng trên cùng của trục Y.
- [ ] **Tiêu đề sạch:** Tiêu đề biểu đồ hiển thị `BIỂU ĐỒ GANTT TƯƠNG TÁC PHÂN BỔ CỔNG — ...`, không còn mã kỹ thuật `(CHART-07)`.

### B. Thanh Công Cụ Bộ Lọc & Số Lượng Cổng Động (ISSUE-R00-11)
- [ ] **Kịch bản Canonical 120:** Nhãn checkbox hiển thị `Concourse T (10)`, `Concourse A (15)`, `Bãi đỗ từ xa (1)`.
- [ ] **Kịch bản P07 Dual-Core:** Chuyển sang kịch bản P07 trong thanh bên; nhãn checkbox phải cập nhật động thành `Concourse T (10)`, `Concourse A (5)`, `Bãi đỗ từ xa (1)`.
- [ ] **Ngữ nghĩa bỏ chọn:** Khi bỏ chọn tất cả các checkbox concourse, biểu đồ hiển thị trạng thái trống và không vẽ chuyến bay nào.

### C. Phân Loại Tài Nguyên & Cách Ly Apron (ISSUE-R00-07)
- [ ] Khi chọn lọc riêng `Concourse A`, các vị trí bãi tràn `APRON_*` **tuyệt đối không xuất hiện** trong danh sách cổng hoặc trên biểu đồ.
- [ ] Vị trí đỗ từ xa và bãi tràn hiển thị đúng nhóm màu đặc trưng (`#A78BFA` và `#64748B`).

### D. An Toàn Thực Thi Bộ Giải (Execution Safety)
- [ ] Khi mới vào trang với kịch bản chưa chạy, hệ thống hiển thị Kế hoạch Danh định Gốc (Nominal Plan) và trạng thái `CHƯA PHÂN BỔ (IDLE)`. CP-SAT không được tự ý chạy ngầm.
- [ ] Bảng điều khiển bộ giải mở rộng (`expanded=True`) khi chưa có kết quả và tự động thu gọn (`expanded=False`) khi đã có kết quả.
- [ ] Đổi bộ lọc, zoom thời gian hoặc chọn chuyến bay **không gây kích hoạt lại solver**.

### E. Flight Inspector & Định Dạng Vượt Nửa Đêm
- [ ] Chọn chuyến bay hạ cánh hoặc rời cổng sau 24:00 (ví dụ `FL_CROSS` hoặc các chuyến đêm muộn): Thời gian hiển thị chuẩn `+1d HH:MM`.
- [ ] Các huy hiệu `TÁI PHÂN BỔ`, `XUNG ĐỘT`, `CỔNG TIẾP XÚC` / `BÃI ĐỖ TỪ XA` hiển thị rõ ràng và tương phản.

### F. Thẻ Kiểm Chứng Độc Lập (Independent Verification Card)
- [ ] Khi xem kế hoạch danh định có xung đột: Thẻ màu đỏ cảnh báo số chuyến bay xung đột thời gian trên cổng tiếp xúc.
- [ ] Khi chạy bộ giải Greedy hoặc CP-SAT thành công: Thẻ màu xanh chứng nhận 0 vi phạm ràng buộc cứng.
- [ ] Lời giải Greedy hiển thị trạng thái `KHẢ THI (GREEDY)`, **không bao giờ hiển thị nhãn TỐI ƯU TUYỆT ĐỐI**.
