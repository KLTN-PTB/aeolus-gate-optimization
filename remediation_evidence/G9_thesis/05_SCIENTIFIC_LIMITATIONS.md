# AEOLUS-G9 — Thuyết Minh 10 Giới Hạn Khoa Học và Ranh Giới Nghiên Cứu

Tài liệu này cung cấp diễn giải khoa học, cơ sở toán học và ranh giới nghiên cứu chính thức cho 10 vấn đề trọng tâm của khóa luận. Đây là cơ sở cốt lõi để sinh viên bảo vệ tính trung thực và liêm chính học thuật trước Hội đồng chấm khóa luận tốt nghiệp.

---

## 1. VÌ SAO MÔ HÌNH HỌC MÁY KHÔNG NHẤT THIẾT CÓ MAE TỐT HƠN MEDIAN BASELINE?

### Cơ sở Toán học: Định lý Tối ưu hóa Mất mát Tuyệt đối $L_1$
Cho biến ngẫu nhiên độ trễ chuyến bay $Y$ có hàm phân phối xác suất tích lũy $F_Y(y)$. Giá trị hằng số $c^*$ cực tiểu hóa hàm mất mát sai số tuyệt đối trung bình (Mean Absolute Error - MAE):
$$c^* = \arg\min_c \mathbb{E}[|Y - c|]$$
chính là **Trung vị (Median)** của phân phối: $F_Y(c^*) = 0.5$.

### Thực tế Dữ liệu Hàng không
- Trong CSDL Aeolus/BTS TranStats tại ATL, hơn $70\%$ số chuyến bay khởi hành đúng giờ hoặc trễ không đáng kể ($< 5$ phút). Trung vị của tập dữ liệu là $c^* = 0$ (hoặc $-2$ phút đối với chuyến bay sớm).
- Bộ dự báo ngây thơ (Naive Baseline) luôn dự đoán $c = 0$ sẽ đạt sai số tuyệt đối cực tiểu trên hơn $70\%$ các chuyến bay đúng giờ này, kéo chỉ số MAE toàn tập xuống mức rất thấp (**$15.60$ phút**).
- Mô hình Machine Learning (XGBoost) được tối ưu hóa theo hàm mất mát $L_2$ (bình phương sai số) để giảm phương sai và nắm bắt các chuyến bay trễ đột biến. Khi dự báo một chuyến bay trễ 45 phút, nếu thực tế chỉ trễ 10 phút, sai số tuyệt đối là 35 phút, làm tăng MAE trung bình toàn tập lên **$17.60$ phút**.

### Giá trị Vận hành của Mô hình Học máy
Trong điều hành sân bay, các chuyến bay đúng giờ không gây ra tắc nghẽn cổng đỗ. Yếu tố cốt lõi gây phá vỡ kế hoạch là **các chuyến bay trễ nghiêm trọng (đuôi nặng)**.
- **Về RMSE toàn tập**: XGBoost ($43.00$ phút) vượt trội hơn Median ($45.76$ phút).
- **Về sai số đuôi trễ $\ge 15$ phút**: XGBoost đạt $48.91$ phút (vượt trội hơn Median $62.33$ phút, giảm tới **$21.5\%$** sai số).
- **Về sai số đuôi trễ $\ge 60$ phút**: XGBoost đạt $117.18$ phút (tốt hơn Median $132.54$ phút).
Do đó, mô hình học máy mang lại giá trị vận hành thực tế vượt trội so với Median Baseline dù MAE toàn tập cao hơn.

---

## 2. VÌ SAO LỰA CHỌN MÔ HÌNH P4 CHO DOWNSTREAM SAMPLING DÙ P5/P1 CÓ CHỈ SỐ TỐT HƠN Ở MỘT TIÊU CHÍ?

- **Mô hình P1 (Hồi quy Điểm XGBoost)** chỉ cung cấp một giá trị trễ kỳ vọng duy nhất $\hat{y}$, hoàn toàn không có thông tin về độ biến động hoặc rủi ro đuôi để thực hiện mô phỏng Monte Carlo.
- **Mô hình P5 (Hồi quy Phân vị Gradient Boosting)** cung cấp 5 giá trị phân vị rời rạc ($\tau \in \{0.1, 0.25, 0.5, 0.75, 0.9\}$) có thể đạt điểm mất mát Pinball Loss tốt hơn trên tập kiểm tra lịch sử. Tuy nhiên, P5 **không có checkpoint nhị phân được lưu trữ (No native serialized checkpoint)**, không thể tạo ra hàm mật độ xác suất liên tục $f(t)$ và không thể lấy mẫu bất kỳ phân vị nào cho động cơ mô phỏng ngẫu nhiên trực tuyến.
- **Mô hình P4 (NGBoost Student-t)**: Cung cấp đầy đủ tham số phân phối tham số liên tục $(\mu, \sigma, \nu)$ với checkpoint đã đóng băng (`model_weights_frozen_v1.joblib`). Tham số bậc tự do $\nu = 4.5$ nắm bắt chính xác hiện tượng đuôi nặng (fat-tailed dispersion) của độ trễ sân bay, cho phép lấy mẫu ngẫu nhiên trơn tru qua hàm Copula trong mô phỏng Monte Carlo. Do đó, P4 là lựa chọn kiến trúc tối ưu duy nhất cho downstream sampling.

---

## 3. VÌ SAO LOẠI BỎ ĐẶC TRƯNG THỜI TIẾT (METAR) VÀ CHUỖI CHUYẾN BAY (FLIGHT CHAIN)?

- **Nguyên tắc Chống Rò rỉ Thông tin tại $T-2\text{h}$**: Mọi quyết định gán cổng và điều hành sân bay phải được chốt trước giờ bay ít nhất 2 giờ. Mọi đặc trưng đưa vào mô hình phải được chứng minh sẵn sàng tại $T_{\text{cutoff}} = T_{\text{sched}} - 120$ phút.
- **Rủi ro của Dữ liệu Chuỗi Chuyến bay (Flight Chain)**: Dữ liệu lịch trình BTS được đóng gói sau khi chuyến bay kết thúc. Thông tin về việc máy bay ở chặng trước có bị trễ hay không không có tem thời gian chứng minh đã được truyền về hệ thống điều hành tại ATL đúng lúc $T-2\text{h}$.
- **Rủi ro của Dữ liệu Thời tiết METAR**: Dữ liệu METAR trong các CSDL lịch sử là dữ liệu quan trắc thực tế tại thời điểm bay, không phải là bản tin dự báo thời tiết số (NWP Forecast). Sử dụng METAR tại thời điểm bay tương lai sẽ phạm lỗi "nhìn trước tương lai" (Lookahead Leakage).
- **Kết luận**: Mặc dù loại bỏ hai nhóm đặc trưng này làm giảm nhẹ mức cải thiện cận biên (khoảng $0.68\%$ MAE), việc phong tỏa chúng bảo đảm hệ thống đạt chuẩn liêm chính học thuật 100%, không bị rò rỉ dữ liệu.

---

## 4. VÌ SAO SIMULATED ANNEALING KHÔNG CẢI THIỆN ĐƯỢC NGHIỆM TỐI ƯU CỦA CP-SAT (0.00% GAIN)?

- **Bản chất Toán học của Tối ưu Toàn cục**: Bộ giải CP-SAT là một solver chính xác (Exact Solver) dựa trên SAT-based Constraint Programming. Trên các bài toán quy mô sân bay được khảo sát ($N \le 300$ chuyến bay), CP-SAT đã tìm ra nghiệm và **chứng minh được tính tối ưu toàn cục** (`optimality_proven == True`).
- **Định lý**: Với bài toán cực tiểu hóa hàm mục tiêu $J(x)$, nếu nghiệm $x^*$ đã được chứng minh là nghiệm tối ưu toàn cục, nghĩa là $\forall x \in \mathcal{X}, J(x) \ge J(x^*)$. Khi đó, bất kỳ thuật toán metaheuristic tìm kiếm lân cận nào (kể cả Simulated Annealing) cũng chỉ có thể tìm thấy các nghiệm có $J(x) \ge J(x^*)$.
- **Kết luận**: Mức cải thiện của Hybrid so với CP-SAT bằng đúng **$0.00\%$** là bằng chứng xác nhận tính tối ưu toàn cục của CP-SAT, không phải là lỗi cài đặt của Simulated Annealing. Trong hệ thống, SA đóng vai trò là cơ chế an toàn dự phòng (Safety Fallback) khi CP-SAT bị giới hạn thời gian chạy trên các bài toán quy mô lớn.

---

## 5. VÌ SAO PHẢI PHÂN BIỆT RẠCH RÒI GIỮA RETROSPECTIVE VÀ ONLINE TRONG MODE B?

- **Hạn chế của Mode B Lịch sử (Retrospective Recourse - Mode B1)**: Trong phiên bản P09 cũ, bộ giải nhận toàn bộ lịch bay thực tế đã xảy ra trong cả ngày và tối ưu hóa lại. Đây là bài toán "nhìn lại quá khứ" (Hindsight / Retrospective), cho phép bộ giải sử dụng thông tin trễ của các chuyến bay buổi chiều để điều chỉnh cổng cho chuyến bay buổi sáng. Điều này hoàn toàn bất khả thi trong vận hành thực tế.
- **Động cơ Mode B2 (Rolling-Horizon Online Recourse)**: Thuật toán quét sự kiện theo dòng thời gian thực ($t$). Tại mỗi thời điểm $t$, bộ giải chỉ biết độ trễ của các chuyến bay đã hạ cánh trước $t$. Các chuyến bay đang đỗ tại cổng bị khóa cứng vật lý (`Locked Flights`); chỉ những chuyến bay trong tương lai chưa cập cổng mới được phép đổi cổng.
- **Kết luận**: Phân định rạch ròi giữa Mode B1 (cận tham chiếu phi vận hành) và Mode B2 (chính sách vận hành trực tuyến nhân quả) loại bỏ hoàn toàn sự lạc quan nhân tạo (artificial algorithmic optimism) trong nghiên cứu.

---

## 6. VÌ SAO MODE C GREEDY FORESIGHT KHÔNG PHẢI LÀ OPTIMAL LOWER BOUND?

- Trong lý thuyết Vận trù học, **Cận dưới Hoàn hảo (Perfect Foresight Oracle)** là nghiệm tối ưu toàn cục tốt nhất có thể đạt được nếu người điều hành có năng lực ngoại cảm biết trước 100% độ trễ tương lai. Nghiệm này phải được giải bằng bộ giải quy hoạch tối ưu toàn cục (CP-SAT hoặc MIP).
- Phiên bản P09 cũ sử dụng thuật toán Tham lam (`DeterministicGreedyGateSolver`) để tính Mode C. Do thuật toán Tham lam đưa ra quyết định cục bộ thiển cận (myopic local decision), nghiệm của nó kém hơn nghiệm tối ưu toàn cục của CP-SAT tới **$12.40$ điểm chi phí** ($p = 1.72 \times 10^{-14}$).
- Đề tài đã phân tách rạch ròi: **Mode C1** là Heuristic tham lam biết trước tương lai; **Mode C2** mới là Cận dưới Hoàn hảo Lý thuyết được giải bằng CP-SAT tối ưu toàn cục.

---

## 7. VÌ SAO PHẢI TÁCH BẠCH XUNG ĐỘT VẬT LÝ VÀ TÍNH KHẢ THI LỊCH TĨNH?

- Chỉ số khả thi tổng hợp cũ (Composite Feasibility) của Mode A ghi nhận **$0\%$**, tạo cảm giác sai lệch rằng 100% các kịch bản đều xảy ra va chạm máy bay đè cổng.
- Thực tế, khi một chuyến bay bị trễ, nó tự động vi phạm cửa sổ giờ danh định được cấp phép ban đầu (Static Schedule Slot Mismatch). Tuy nhiên, nếu cổng đỗ tiếp xúc lúc đó đang trống, máy bay vẫn đỗ an toàn mà **không xảy ra bất kỳ xung đột vật lý nào**.
- Bóc tách 5 chiều khả thi trong Gate G2 chỉ ra rằng: Tỷ lệ thực sự xảy ra xung đột vật lý trên cổng tiếp xúc trong Mode A là **$76.0\%$**; vẫn có **$24.0\%$** kịch bản hoàn toàn an toàn về mặt vật lý. Việc phân tách này chứng minh năng lực phân tích khoa học sâu sắc, khách quan của đề tài.

---

## 8. VÌ SAO MÔ PHỎNG SÂN BAY KHÔNG TƯƠNG ĐƯƠNG TRIỂN KHAI VẬN HÀNH THỰC TẾ?

- Mô hình toán học và mô phỏng Monte Carlo trong khóa luận giả định các thông số vận hành tiêu chuẩn: thời gian đẩy lùi cố định, tốc độ lăn bánh đồng nhất, và thời gian phục vụ mặt đất không bị gián đoạn bất ngờ.
- Trong thực tế sân bay, các yếu tố ngoại cảnh như xe thang hỏng, tiếp nhiên liệu chậm, đình công mặt đất, hoặc cảnh báo an ninh sẽ tạo ra các biến động phi cấu trúc mà mô hình chưa bao quát hết.
- Đề tài khẳng định: Khóa luận xây dựng **Mô hình Hỗ trợ Ra Quyết định (Decision Support System)** cho nhân viên điều độ AOCC, không thay thế hoàn toàn con người trong việc xử lý các tình huống bất khả kháng.

---

## 9. GIỚI HẠN VỀ DỮ LIỆU SỐ HIỆU ĐUÔI TÀU BAY (TAIL NUMBER) TRONG CSDL BTS

- CSDL mở BTS TranStats của Bộ Giao thông Vận tải Hoa Kỳ là nguồn dữ liệu chuẩn trong nghiên cứu hàng không, nhưng bảng dữ liệu phân phối công khai đã bị lược bỏ cột số hiệu đăng ký máy bay (`TAIL_NUM`).
- Động cơ ghép cặp của đề tài tuân thủ nguyên tắc liêm chính học thuật: Không tự động tạo ra số hiệu đuôi giả để lấy thành tích.
- Thay vào đó, đề tài xử lý minh bạch: Ở chế độ dữ liệu thật, hệ thống giải tối ưu 200 tác vụ bay độc lập; ở chế độ suy diễn, hệ thống liên kết được 59 cặp quay đầu dựa trên hãng bay và khoảng cách thời gian danh định 45–180 phút.

---

## 10. GIỚI HẠN CỦA VIỆC SỬ DỤNG TẬP DỮ LIỆU NĂM 2024

- Trong lịch sử nghiên cứu ban đầu, tập dữ liệu năm 2024 đã được sử dụng trong một số bài kiểm tra hậu nghiệm (post-hoc leakage checks).
- Theo chuẩn mực khoa học quốc tế, một khi tập kiểm thử đã được quan sát và phân tích trong quá trình phát triển, nó không còn giữ được tính chất "hoàn toàn chưa chạm tới" (Untouched Holdout).
- Đề tài trung thực công bố: Tập năm 2023 là tập benchmark chuẩn duy nhất để đánh giá và lựa chọn mô hình; tập 2024 được giữ nguyên làm vùng cấm bảo lưu, không được tuyên bố là tập holdout nguyên sơ mới.
