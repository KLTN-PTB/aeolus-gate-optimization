# Presentation Rehearsal Script & Defense Walkthrough (15-Minute Protocol)

**Document ID:** `AEOLUS-P10-A-SCRIPT-12`  
**Phase:** P10-A (UI/UX Design Specification & Design Freeze)  
**Status:** DESIGN FROZEN  
**Target Event:** Thesis Defense & Demonstration Evaluation (Hội đồng Chấm Khóa luận Tốt nghiệp)  
**Target Duration:** Exactly 15 minutes (with 5-10 minutes reserved for Q&A)  

---

## 1. Executive Summary & Presentation Philosophy

This document provides a minute-by-minute verbal and interactive demonstration protocol for presenting the Aeolus Gate Optimization project. The presentation leverages the **Presentation Mode** of the dashboard to convey a logical, compelling scientific narrative:

$$\text{Practical Operational Crisis} \longrightarrow \text{ML Delay Prediction} \longrightarrow \text{Constraint Optimization} \longrightarrow \text{Stochastic Robustness Validation}$$

---

## 2. Minute-by-Minute Rehearsal Script

### [00:00 – 02:00] Phần 1: Giới thiệu Bài toán & Bối cảnh Thực tiễn
- **Thao tác màn hình:** Đứng tại trang **01. Control Tower**, chế độ *Presentation Mode*.
- **Lời thoại thuyết trình:**
  > *"Kính thưa Thầy Cô trong Hội đồng và các bạn!  
  > Tại các siêu cảng hàng không như Hartsfield-Jackson Atlanta (ATL), mỗi ngày có hơn 2.000 chuyến bay cất hạ cánh. Tuy nhiên, tình trạng trễ chuyến do thời tiết và không lưu thường xuyên phá vỡ lịch trình cổng đỗ cố định. Khi máy bay hạ cánh trễ, chúng chiếm dụng cổng ngoài kế hoạch, gây ra va chạm không gian - thời gian, buộc các máy bay kế tiếp phải dừng chờ trên đường lăn, tiêu tốn nhiên liệu và làm trễ dây chuyền hành khách.  
  > Khóa luận của em giải quyết bài toán này thông qua phương pháp tiếp cận hai giai đoạn: Sử dụng **Học máy (Machine Learning)** để dự báo độ trễ đến/đi và lượng đệm quay vòng, sau đó ứng dụng **Lập trình Ràng buộc (Constraint Programming / CP-SAT)** để tái phân bổ cổng đỗ tự động, loại bỏ 100% xung đột với chi phí điều hành tối thiểu."*

---

### [02:00 – 04:30] Phần 2: Control Tower — Bức tranh Toàn cảnh Đợt Cao điểm
- **Thao tác màn hình:** Chỉ vào 5 Thẻ Điểm KPI và Biểu đồ Hoạt động Khai thác.
- **Lời thoại thuyết trình:**
  > *"Trước mắt Thầy Cô là Trung tâm Điều hành Aeolus cho kịch bản sáng cao điểm gồm **120 chuyến bay** và **25 cổng tiếp xúc** tại nhà ga T và A của sân bay Atlanta.  
  > Mô hình Machine Learning của chúng em dự báo độ trễ trung bình đợt này là **+18.4 phút**, với hơn 38% số chuyến trễ trên 15 phút. Nếu giữ nguyên lịch bay danh định ban đầu, sự biến động này sẽ tạo ra **13 cặp xung đột trực tiếp** trên các cổng đỗ.  
  > Nhìn vào biểu đồ hoạt động khai thác bên dưới, đỉnh điểm ùn tắc diễn ra từ 07:30 đến 08:30 với hơn 20 lượt cất hạ cánh mỗi 15 phút, khiến Concourse A chạm trần 100% công suất."*

---

### [04:30 – 07:00] Phần 3: Flight Intelligence — Dự báo Trễ Hai Lõi & Giải thích SHAP
- **Thao tác màn hình:** Chuyển sang trang **02. Flight Intelligence**. Mở Tab A, chọn chuyến bay `DL1024`, chuyển sang Tab B (Turn Dynamics) và Tab C (SHAP).
- **Lời thoại thuyết trình:**
  > *"Điểm cốt lõi đầu tiên của hệ thống nằm ở trang Flight Intelligence. Thay vì chỉ dự báo trễ chuyến đơn lẻ, Aeolus xây dựng kiến trúc **Hai Lõi (Dual-Core)**: kết hợp dự báo trễ đến inbound và trễ đi outbound thông qua cặp quay vòng tàu bay (aircraft turnaround).  
  > Em xin lấy ví dụ chuyến bay `DL1024` từ Chicago về Atlanta: mô hình XGBoost dự báo trễ **+24.5 phút**. Tại Tab B, hệ thống tự động tính toán: thời gian quay vòng theo lịch là 75 phút, dịch vụ kỹ thuật tối thiểu cần 45 phút, do đó có 30 phút slack đệm. Độ trễ 24.5 phút được hấp thụ an toàn vào slack, giúp chuyến bay cất cánh tiếp theo không bị trễ lan truyền.  
  > Tại Tab C, thông qua kỹ thuật **TreeSHAP**, Thầy Cô có thể thấy rõ các yếu tố chi phối dự báo: độ trễ lan truyền từ mạng bay trước đó đóng góp +8.45 phút, và giờ khởi hành cao điểm đóng góp +5.12 phút. Mô hình hoàn toàn minh bạch và có thể giải thích được."*

---

### [07:00 – 10:30] Phần 4: Gate Operations — Trọng tâm Phân bổ Cổng CP-SAT [CLIMAX]
- **Thao tác màn hình:** Chuyển sang trang **03. Gate Operations**.
  1. Bật radio chọn `Kế hoạch Danh định (Nominal)` $\to$ Chỉ ra các vạch màu đỏ cảnh báo xung đột.
  2. Bật radio chọn `Kế hoạch Tối ưu CP-SAT` $\to$ Các vạch đỏ biến mất hoàn toàn, lịch bay sạch sẽ.
  3. Thử nghiệm kéo slider `buffer_time_min` lên 20 phút và bấm `[⚡ TỐI ƯU HÓA NGAY]`.
  4. Chỉ vào Thẻ Kiểm chứng Toán học Độc lập `[🛡️ HỢP LỆ — 0 VI PHẠM]`.
- **Lời thoại thuyết trình:**
  > *"Đây là trang trọng tâm của hệ thống: Biểu đồ Gantt tương tác phân bổ cổng đỗ.  
  > Khi bật chế độ 'Kế hoạch Danh định', dưới tác động của trễ chuyến dự báo, Thầy Cô sẽ thấy các vạch đỏ chớp sáng tại cổng T02 và A04 — đây là các vị trí hai tàu bay cùng chiếm dụng cổng trong một khung giờ, vi phạm khoảng cách an toàn 15 phút.  
  > Nhưng khi chuyển sang 'Kế hoạch Tối ưu CP-SAT', bộ giải dựa trên thuật toán lập trình ràng buộc của Google OR-Tools đã tự động điều chỉnh lịch bay, bảo đảm 100% chuyến bay được phân cổng tiếp xúc mà không cần đưa tàu bay ra bãi đỗ từ xa, với chi phí đổi cổng tối thiểu.  
  > Đặc biệt, hệ thống tích hợp mô đun **Kiểm chứng Độc lập độc lập (Independent Verifier)**. Mọi kết quả sau khi giải đều được quét lại qua thuật toán kiểm tra va chạm không gian - thời gian nghiêm ngặt, bảo đảm tính an toàn tuyệt đối trước khi gửi tới điều phối viên."*

---

### [10:30 – 12:30] Phần 5: Optimization Lab — Khảo sát Hiệu năng & Quy mô Mega-Hub
- **Thao tác màn hình:** Chuyển sang trang **04. Optimization Lab**. Chỉ vào Bảng So sánh 4 Thuật toán và Biểu đồ Khả năng Mở rộng 1.500 chuyến bay.
- **Lời thoại thuyết trình:**
  > *"Tại Optimization Lab, chúng em đặt 4 thuật toán lên cùng một bàn cân thực nghiệm.  
  > Thuật toán CP-SAT với mô hình hóa biến khoảng rời rạc (Sparse Interval) giải quyết kịch bản 120 chuyến chỉ trong **65 mili-giây**, đạt cận tối ưu tuyệt đối (Optimality Gap = 0.0%), nhanh hơn 21 lần so với mô hình lưới thời gian truyền thống (Dense Grid).  
  > Về khả năng mở rộng quy mô (Scalability), trên tập dữ liệu thử nghiệm stress 24 giờ với **1.500 chuyến bay** và **50 cổng**, CP-SAT hoàn thành tìm kiếm trong **34.2 giây** với gap dưới 1.5%, chứng minh thuật toán hoàn toàn đủ khả năng triển khai thực tế tại các sân bay lớn nhất thế giới."*

---

### [12:30 – 14:30] Phần 6: Robustness Lab — Kiểm thử Bền vững 500 Kịch bản Monte Carlo
- **Thao tác màn hình:** Chuyển sang trang **05. Robustness Lab**. Chỉ vào Đồ thị Hàm Phân bố Tích lũy (CDF) và Kéo Slider Chọn Kịch bản `#042`.
- **Lời thoại thuyết trình:**
  > *"Cuối cùng, trong thực tế hàng không, dự báo thời tiết luôn có độ bất định. Để kiểm chứng độ bền vững, chúng em đã thực hiện mô phỏng **Monte Carlo trên 500 kịch bản ngẫu nhiên**.  
  > Kết quả cho thấy: Kế hoạch cố định (Mode A) có tới **74.8% xác suất xảy ra va chạm thực tế** do máy bay bị trễ. Trong khi đó, chiến lược Phân bổ Tức thời (Mode B - Recourse) của chúng em giúp hấp thụ toàn bộ biến động: trung bình chỉ cần đổi **2.556 cổng** cho mỗi đợt 120 chuyến là đã giải tỏa hoàn toàn xung đột, đưa chi phí trung bình từ 22.000 xuống còn 130 điểm.  
  > Đường cong CDF minh chứng rằng 100% kịch bản trong Mode B đều có chi phí dưới 250, loại bỏ hoàn toàn các rủi ro thảm họa ở đuôi phân phối."*

---

### [14:30 – 15:00] Phần 7: Kết luận & Bàn giao
- **Lời thoại thuyết trình:**
  > *"Tóm lại, Aeolus đã chứng minh thành công sự kết hợp giữa Machine Learning giải thích được và Lập trình Ràng buộc CP-SAT mang lại giải pháp phân cổng thông minh, thời gian thực, có khả năng chống chịu biến động cao và hoàn toàn khả thi trong thực tế vận hành hàng không.  
  > Em xin chân thành cảm ơn Quý Thầy Cô và kính mời Hội đồng đặt câu hỏi!"*

---

## 3. Anticipated Jury Questions & Defense Answers (Hỏi - Đáp Học thuật)

### Q1: "Tại sao trong Robustness Lab, tỷ lệ khả thi của Mode A là 0.0% nhưng tỷ lệ va chạm lại là 74.8%?"
- **Câu trả lời chuẩn:**
  > *"Dạ thưa Thầy Cô, đây là phát hiện quan trọng được ghi nhận trong báo cáo kiểm toán P10-00 (Mã phát hiện D1). Hàm kiểm chứng độc lập của hệ thống định nghĩa 'khả thi tĩnh' là chuyến bay phải khớp chính xác với khung giờ slot đã đăng ký (`assign.start == flight.start`). Khi có trễ ngẫu nhiên, 100% chuyến bay đều bị dịch chuyển thời gian, do đó tỷ lệ tuân thủ lịch tĩnh là 0.0%.  
  > Tuy nhiên, khi xét về an toàn va chạm vật lý trên cùng một cổng đỗ, chỉ có **74.8% kịch bản** xảy ra việc máy bay đến sau đè lên máy bay đến trước; còn trong 25.2% kịch bản, các máy bay dù bị trễ nhưng giãn cách tự nhiên vẫn không trùng nhau trên cổng tiếp xúc."*

### Q2: "Tại sao Mode B (Recourse) và Mode C (Oracle) lại có chi phí trung bình bằng nhau chính xác là 130.73?"
- **Câu trả lời chuẩn:**
  > *"Dạ thưa Thầy Cô, đây là mã phát hiện D2 trong hồ sơ kiểm toán. Trên kịch bản chuẩn 120 chuyến bay, kế hoạch danh định ban đầu có 0 lần đổi cổng (tất cả chuyến bay đều ở cổng mong muốn). Trong Phase P09, cả Mode B và Mode C đều sử dụng thuật toán Deterministic Greedy để tái phân bổ theo thứ tự thời gian thực tế.  
  > Do kế hoạch ban đầu không có độ lệch và cùng dùng giải thuật tham lam có thứ tự như nhau, hai chế độ nhận cùng dữ liệu đầu vào nên cho kết quả tương đương hoàn hảo ($p = 1.0$). Chúng em xin nhấn mạnh: Mode C ở đây là **Chuẩn Heuristic Tham lam Thực tế (Realized Greedy Oracle Baseline)** chứ không phải cận dưới tối ưu toàn cục từ CP-SAT."*
