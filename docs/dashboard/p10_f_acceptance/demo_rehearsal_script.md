# KỊCH BẢN THUYẾT TRÌNH BẢO VỆ KHÓA LUẬN (10–12 PHÚT)
## Thesis Defense Live Demonstration Rehearsal Script

**Khóa luận:** Ứng dụng học máy và lập trình ràng buộc trong dự báo độ trễ chuyến bay và tối ưu tái phân bổ cổng đỗ tàu bay  
**Hệ thống trình diễn:** Aeolus Flight Operations Intelligence Dashboard  
**Thời lượng chuẩn:** 10 – 12 phút

---

## 1. PHÂN BỔ THỜI LƯỢNG & CẤU TRÚC KỊCH BẢN

```
00:00 - 01:30 | 1. Giới thiệu Tổng quan & Trung tâm Điều hành (Control Tower)
01:30 - 03:30 | 2. Trí tuệ Dự báo Trễ & Giải thích Mô hình ML (Flight Intelligence)
03:30 - 06:00 | 3. Điều hành Cổng đỗ & Demo Giải thuật Trực tiếp (Gate Operations)
06:00 - 08:30 | 4. Đối chuẩn 4 Thuật toán & Khả năng Mở rộng (Optimization Lab)
08:30 - 10:30 | 5. Kiểm chứng Độ vững chắc Monte Carlo 500 Kịch bản (Robustness Lab)
10:30 - 11:30 | 6. Khu vực Kiểm toán Khoa học & Hỏi đáp (Research Inspector & Q&A)
```

---

## 2. NỘI DUNG THUYẾT TRÌNH CHI TIẾT THEO TỪNG TRANG

### Phút 00:00 – 01:30: Trang 01 — Control Tower (Trung tâm Chỉ huy)
- **Hành động:** Mở trang chủ `01_control_tower`. Mặc định ở chế độ **Presentation Mode**.
- **Lời thoại:**
  > "Kính thưa Hội đồng, đây là giao diện Control Tower của hệ thống Aeolus, tái hiện hoạt động trong 24 giờ của 120 chuyến bay tại sân bay Atlanta (ATL).
  > Hệ thống theo dõi 4 chỉ số vận hành cốt lõi: Tổng số chuyến bay, Tỷ lệ đúng giờ dự báo (82.5%), Số lượng xung đột cổng đỗ tiềm tàng nếu không can thiệp (12 xung đột), và Thời gian trễ trung bình (+18.4 phút).
  > Biểu đồ hoạt động theo giờ cho thấy đỉnh lưu lượng tập trung vào khung giờ chiều (14:00 - 18:00), dẫn đến nguy cơ ùn tắc cục bộ tại các Concourse A và T."

### Phút 01:30 – 03:30: Trang 02 — Flight Intelligence (Trí tuệ Dự báo Chuyến bay)
- **Hành động:** Chuyển sang trang `02_flight_intelligence`.
- **Lời thoại:**
  > "Giai đoạn đầu tiên trong mô hình Predict-then-Optimize là dự báo độ trễ chính xác bằng Machine Learning.
  > Đồ thị phân phối trễ thể hiện tính toán bảo lưu dấu trễ: các chuyến đến sớm được ghi nhận trễ âm (ví dụ: -14.5 phút) thay vì bị gán bằng 0, giúp bảo toàn chính xác thời gian chiếm dụng cổng.
  > Đặc biệt, qua công cụ SHAP Waterfall bên dưới, chúng ta có thể giải thích minh bạch nguyên nhân gây trễ cho từng chuyến bay: ví dụ chuyến bay mang mã DL123 bị trễ +28 phút chủ yếu do sức gió giật tại sân bay khởi hành (+14 phút) và hiện tượng nghẽn đường lăn (+9 phút)."

### Phút 03:30 – 06:00: Trang 03 — Gate Operations & Live Demo Giải toán
- **Hành động:** Chuyển sang trang `03_gate_operations`. Phóng to khung giờ trưa trên biểu đồ Gantt. Sau đó chọn thuật toán **Deterministic Greedy** và bấm **🚀 THỰC THI TỐI ƯU CỔNG**.
- **Lời thoại:**
  > "Đây là không gian điều hành cổng đỗ với biểu đồ Gantt tương tác. Các vệt màu đại diện cho thời gian chiếm dụng cổng của tàu bay, bao gồm 15 phút đệm an toàn buffer.
  > Khi chưa tối ưu (Nominal Plan), các chuyến bay trễ đỗ đè lên nhau gây ra 12 va chạm không gian - thời gian (được đánh dấu cảnh báo màu đỏ).
  > Bây giờ tôi sẽ thực hiện giải trực tiếp bằng thuật toán **Deterministic Greedy** trên hệ thống..."
  *(Bấm nút Chạy - kết quả trả về tức thì sau 7.4 ms)*
  > "Chỉ sau chưa đầy 10 mili-giây, toàn bộ 12 xung đột đã được triệt tiêu hoàn toàn. Hệ thống đã tự động thực hiện 4 lần đổi cổng (Reassignments) sang các cổng lân cận và đưa 1 chuyến vào bãi đỗ xa, bảo đảm an toàn tuyệt đối."

### Phút 06:00 – 08:30: Trang 04 — Optimization Lab (Phòng thí nghiệm Tối ưu)
- **Hành động:** Chuyển sang trang `04_optimization_lab`. Chỉ vào biểu đồ Pareto Frontier (CHART-09) và Scalability (CHART-11).
- **Lời thoại:**
  > "Tại Optimization Lab, chúng tôi đối chuẩn độc lập giữa 4 họ giải thuật: Deterministic Greedy, CP-SAT (Sparse Interval), Simulated Annealing, và Two-stage Hybrid.
  > Biểu đồ Pareto Frontier cho thấy: CP-SAT đạt điểm cân bằng lý tưởng nhất, tìm ra nghiệm tối ưu toàn cục đã được chứng minh toán học (Gap 0.0%) chỉ trong 65 mili-giây.
  > Về khả năng mở rộng quy mô (CHART-11): Với mô hình Sparse Interval NoOverlap2D, CP-SAT giải mượt mà từ 100 đến 1,000 chuyến bay.
  > Tuy nhiên, với tinh thần trung thực khoa học, tại quy mô cực đại 1,500 chuyến bay × 50 cổng, CP-SAT vượt quá giới hạn 10 giây mà chưa tìm thấy nghiệm hợp lệ, hệ thống đánh dấu minh bạch trạng thái **UNKNOWN** (chữ X đỏ) chứ tuyệt đối không ngụy tạo kết quả."

### Phút 08:30 – 10:30: Trang 05 — Robustness Lab (Phòng thí nghiệm Độ vững Monte Carlo)
- **Hành động:** Chuyển sang trang `05_robustness_lab`.
- **Lời thoại:**
  > "Để chứng minh phương án phân cổng có thể trụ vững trước biến động thời tiết thực tế, chúng tôi thực hiện mô phỏng Monte Carlo qua 500 kịch bản độc lập theo 3 giao thức:
  > Mode A (Kế hoạch tĩnh): Nếu không điều chỉnh, 74.8% số kịch bản sẽ xảy ra va chạm vật lý trực tiếp, chi phí phạt kỳ vọng lên tới 1,469 điểm.
  > Mode B (Ứng phó tức thời Recourse): Điều chỉnh linh hoạt trong ngày bay giúp hấp thụ 100% va chạm, chi phí giảm xuống chỉ còn 130.7 điểm với trung vị chỉ 2 lần đổi cổng.
  > Mode C (Oracle): Mốc tham chiếu lý thuyết giả định biết trước tương lai, được gắn nhãn đỏ cảnh báo **NON-DEPLOYABLE**.
  > Biểu đồ vết hội tụ Monte Carlo bên dưới khẳng định với n = 500 mẫu, sai số chuẩn đã thu hẹp xuống còn 1.13 điểm, chứng minh kết quả hoàn toàn ổn định và đáng tin cậy."

### Phút 10:30 – 11:30: Research Inspector & Kết luận
- **Hành động:** Bật công tắc **🔬 Research Mode** trên thanh điều hướng bên trái. Cuộn xuống mở ngăn **RESEARCH INSPECTOR**.
- **Lời thoại:**
  > "Khi chuyển sang Research Mode, các chuyên gia và hội đồng có thể kiểm tra toàn bộ nguồn gốc dữ liệu (Provenance), mã băm SHA256 của kịch bản, và tải xuống toàn bộ dữ liệu kiểm toán định dạng CSV/JSON đã được khử sạch thông tin nhạy cảm.
  > Xin cảm ơn quý Thầy Cô trong Hội đồng đã chú ý lắng nghe, tôi xin phép sẵn sàng nhận các câu hỏi phản biện."
