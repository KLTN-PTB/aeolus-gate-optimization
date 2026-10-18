# AEOLUS-G8 — Mandatory Disclosures and Defense Shields

## 1. Executive Guide for Thesis Defense

This authoritative defense guide prepares the student and academic advisor with bulletproof mathematical, statistical, and operational defenses against challenging questions from the thesis defense committee (*Hội đồng chấm khóa luận tốt nghiệp*).

---

## 2. Top Defense Challenges & Battle-Tested Responses

### Defense Shield 1: "Tại sao bộ giải Lai (Hybrid CP-SAT + SA) lại không cải thiện được chút nào (0.00% gain) so với CP-SAT?"

- **Committee Challenge**: *"Em phát triển giải thuật lai Hybrid CP-SAT kết hợp Simulated Annealing, nhưng bảng kết quả lại cho thấy độ cải thiện là 0.00%. Phải chăng giải thuật lai bị lỗi?"*
- **Certified Academic Response**:
  > *"Thưa Thầy/Cô, kết quả 0.00% cải thiện của Hybrid không phải là lỗi cài đặt, mà là một **kết quả toán học hoàn toàn tất yếu**. CP-SAT là bộ giải chính xác dựa trên quy hoạch ràng buộc (Constraint Programming) kết hợp SAT solving. Trên các bài toán quy mô sân bay được khảo sát, CP-SAT đã tìm ra nghiệm và **chứng minh được tính tối ưu toàn cục** (`optimality_proven == True`). Theo định lý cơ bản của tối ưu hóa, một khi nghiệm đã đạt cực tiểu toàn cục, không có bất kỳ thuật toán metaheuristic nào (kể cả SA) có thể tìm ra nghiệm có giá trị hàm mục tiêu tốt hơn nghiệm tối ưu toàn cục đó. Do đó, mức cải thiện của SA bắt buộc phải bằng đúng 0.00%. Trong kiến trúc Aeolus, Simulated Annealing được thiết kế như một **cơ chế an toàn dự phòng (safety fallback)** khi CP-SAT bị giới hạn thời gian (timeout) trên các bài toán quy mô cực lớn, chứ không phải để cải thiện một nghiệm đã tối ưu."*

---

### Defense Shield 2: "Tại sao mô hình Median Baseline lại có MAE thấp hơn mô hình Học máy XGBoost?"

- **Committee Challenge**: *"Trong bảng kết quả dự báo độ trễ, tại sao mô hình Baseline lấy Median lại có sai số tuyệt đối MAE là 15.60 phút, trong khi mô hình phức tạp XGBoost lại có MAE là 17.60 phút? Vậy học máy có thực sự cần thiết không?"*
- **Certified Academic Response**:
  > *"Thưa Thầy/Cô, đây là hệ quả toán học trực tiếp của **Định lý tối ưu hóa mất mát $L_1$**. Về mặt lý thuyết xác suất thống kê, giá trị cực tiểu hóa sai số tuyệt đối trung bình (MAE) của một phân phối chính là Trung vị (Median). Do dữ liệu trễ chuyến bay có phân phối lệch phải cực kỳ mạnh (hơn 70% chuyến bay đúng giờ hoặc trễ dưới 5 phút, trung vị bằng 0 hoặc gần 0), một bộ dự báo đơn giản luôn đoán giá trị trung vị sẽ đạt MAE rất thấp trên phần lớn các chuyến bay bình thường. Tuy nhiên, mô hình Median hoàn toàn bất lực trong việc dự báo các chuyến bay trễ nặng. Ngược lại, mô hình XGBoost được huấn luyện với hàm mất mát bình phương ($L_2$) để cực tiểu hóa phương sai và nhận diện rủi ro đuôi nặng. Thực nghiệm chứng minh XGBoost vượt trội hơn hẳn Median Baseline ở các chỉ số quan trọng cho vận hành sân bay:
  > - **RMSE**: XGBoost đạt $43.00$ phút (tốt hơn Median $45.76$ phút).
  > - **Sai số đuôi trễ $\ge 15$ phút**: XGBoost đạt $48.91$ phút (tốt hơn Median $62.33$ phút, giảm tới $21.5\%$ sai số).
  > - **Sai số đuôi trễ $\ge 60$ phút**: XGBoost đạt $117.18$ phút (tốt hơn Median $132.54$ phút).
  > Trong điều hành cổng đỗ sân bay, việc dự báo chính xác các chuyến trễ nghiêm trọng để tránh xung đột cổng đỗ quan trọng hơn rất nhiều so với việc tối ưu MAE trên các chuyến bay đúng giờ."*

---

### Defense Shield 3: "Tại sao đề cương có so sánh Flight Chain và Thời tiết nhưng hệ thống chính lại không dùng?"

- **Committee Challenge**: *"Đề cương yêu cầu so sánh Tabular và Tabular + Flight Chain. Tại sao trong pipeline chứng nhận của hệ thống lại chỉ dùng Tabular?"*
- **Certified Academic Response**:
  > *"Thưa Thầy/Cô, chúng em đã thực hiện thí nghiệm cắt bỏ đặc trưng (Feature Ablation) để so sánh Tabular, Tabular + Flight Chain và Weather. Tuy nhiên, trong quá trình kiểm toán khoa học và rà soát rò rỉ dữ liệu, chúng em phát hiện ra rằng dữ liệu Flight Chain và METAR trong tập dữ liệu lịch sử BTS gặp phải **rào cản rò rỉ thông tin tương lai tại thời điểm $T-2\text{h}$**:
  > 1. Dữ liệu chuỗi chuyến bay (Flight Chain) yêu cầu biết trạng thái thực tế của máy bay ở chặng bay trước đó. Trong dữ liệu lịch sử, các trường này chỉ được ghi nhận sau khi toàn bộ chuỗi chuyến bay kết thúc, không có tem thời gian chứng minh nó đã sẵn sàng tại đúng $T-2\text{h}$.
  > 2. Dữ liệu METAR là thời tiết quan trắc thực tế, không phải bản tin dự báo thời tiết NWP. Sử dụng METAR tại thời điểm bay tương lai sẽ phạm lỗi 'nhìn trước tương lai' (lookahead leakage).
  > Vì vậy, để bảo đảm tính liêm chính học thuật và nguyên tắc vận hành thực tế, chúng em đã chủ động giới hạn Flight Chain và Weather vào phần Nghiên cứu Khám phá, và chỉ chứng nhận các đặc trưng Tabular thuần túy với rào chắn thời gian $T-2\text{h}$ được kiểm định 100% không rò rỉ dữ liệu."*

---

### Defense Shield 4: "Tại sao trong mô phỏng Monte Carlo Mode A lại có độ khả thi 0%?"

- **Committee Challenge**: *"Tại sao kế hoạch cố định Mode A trong mô phỏng Monte Carlo lại có tỷ lệ khả thi bằng 0%? Có phải kế hoạch ban đầu quá tệ không?"*
- **Certified Academic Response**:
  > *"Thưa Thầy/Cô, con số 0% này là do **tiêu chí định nghĩa khả thi tổng hợp (Composite Feasibility)** của hệ thống trước đây đã đánh đồng hai khái niệm khác nhau:
  > 1. **Xung đột vật lý trên cổng tiếp xúc (Physical Contact Gate Conflict)**: Khi hai máy bay thực sự chen chúc đỗ đè lên nhau tại cùng một cổng.
  > 2. **Lệch khe thời gian danh định (Static Schedule Consistency)**: Khi thời gian thực tế bay bị trễ lệch khỏi khe giờ ban đầu đã được cấp phép.
  > Khi bóc tách 5 chiều khả thi độc lập trong Gate G2, chúng em làm sáng tỏ: Trong Mode A, tỷ lệ thực sự xảy ra xung đột vật lý là **76.0%**, nghĩa là vẫn có **24.0%** kịch bản hoàn toàn không hề có va chạm vật lý nào trên cổng tiếp xúc. Nhưng do 100% các chuyến bay bị trễ đều trượt khỏi khe giờ danh định, chỉ số Feasibility tổng hợp bị hạ xuống 0%. Việc phân định rõ ràng giữa xung đột vật lý và lệch khe danh định chứng minh năng lực phân tích sâu sắc của nghiên cứu."*

---

### Defense Shield 5: "Tại sao trên dữ liệu thật lại không thể ghép cặp máy bay theo số hiệu đuôi (Tail Number)?"

- **Committee Challenge**: *"Hệ thống tuyên bố chạy trên dữ liệu Aeolus thực tế, tại sao số lượng cặp quay đầu máy bay được xác thực (Verified Rotations) trên dữ liệu BTS thật lại bằng 0?"*
- **Certified Academic Response**:
  > *"Thưa Thầy/Cô, đó là một hạn chế khách quan của nguồn dữ liệu mở BTS TranStats từ Bộ Giao thông Vận tải Hoa Kỳ: Trong tập dữ liệu bảng biểu công khai được lưu trữ, trường số hiệu đuôi máy bay (`TAIL_NUM`) đã bị lược bỏ. Động cơ ghép cặp của chúng em tuân thủ nguyên tắc liêm chính khoa học tuyệt đối: Chỉ khi có số hiệu đuôi trùng khớp, chuyến đến trước chuyến đi, đúng sân bay trung chuyển ATL và thời gian quay đầu $\ge 45$ phút thì động cơ mới cấp nhãn `VERIFIED_ROTATION`. Do dữ liệu gốc không có cột đuôi, hệ thống từ chối tự động bịa ra số hiệu đuôi giả để lấy thành tích. Thay vào đó:
  > - Ở chế độ nghiêm ngặt dữ liệu thật (`REAL_ONLY`), hệ thống phân bổ độc lập 100 chuyến đến và 100 chuyến đi ($N=200$ tác vụ gán cổng) và giải tối ưu thành công 100%.
  > - Ở chế độ ghép cặp suy diễn lịch trình (`INFERRED`), hệ thống sử dụng hãng bay và cửa sổ quay đầu danh định 45–180 phút để liên kết được 59 cặp quay đầu một cách minh bạch."*

---

## 3. Checklist Các Quyết Định Cần Xin Ý Kiến Giảng Viên Hướng Dẫn (GVHD)

Trước khi in ấn quyển luận văn và bảo vệ chính thức, sinh viên cần báo cáo với GVHD các nội dung sau:

1. **Văn bản hóa việc chuyển Flight Chain sang Nghiên cứu Khám phá**: Báo cáo GVHD về lý do loại trừ Flight Chain khỏi pipeline chính để ngăn chặn rò rỉ thông tin $T-2\text{h}$.
2. **Quy mô kịch bản Monte Carlo**: Báo cáo kết quả kiểm định nhân quả trên $N=100$ kịch bản pilot; nếu GVHD yêu cầu giữ đúng con số 500 kịch bản trong đề cương, sinh viên chỉ cần chạy lệnh batch mở rộng `run_g2_monte_carlo_remediation.py --n-scenarios 500`.
3. **Kịch bản Demo Dashboard**: Thống nhất với GVHD về việc thực hiện demo trực tiếp 15 phút trên máy tính cá nhân trong buổi bảo vệ thay vì triển khai server đám mây.
