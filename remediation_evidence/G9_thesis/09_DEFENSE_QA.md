# AEOLUS-G9 — Ngân Hàng 20 Câu Hỏi và Đáp Án Phản Biện Bảo Vệ Khóa Luận (Defense Q&A Bank)

Tài liệu này chuẩn bị 20 câu hỏi phản biện chuyên sâu được chia đều thành 10 nhóm chủ đề trọng tâm. Mỗi câu trả lời đều được xây dựng trên cơ sở toán học, nguyên lý kỹ thuật phần mềm và bằng chứng thực nghiệm đã thẩm định tại Gate G8, giúp sinh viên tự tin đối đáp trước Hội đồng chấm khóa luận tốt nghiệp.

---

## NHÓM 1: DỮ LIỆU VÀ RÒ RỈ THÔNG TIN (DATASET & LEAKAGE)

### Câu 1: Tại sao em lại chọn điểm rào chắn thời gian là $T-2\text{h}$ mà không phải $T-30$ phút hoặc $T-4\text{h}$?
- **Trả lời**:
  > *"Thưa Thầy/Cô, mốc $T-2\text{h}$ được lựa chọn dựa trên quy chuẩn vận hành thực tế tại các trung tâm điều phối sân bay lớn (AOCC):
  > 1. Trước giờ bay 2 tiếng là thời điểm bắt đầu thủ tục làm thủ tục lên máy bay (check-in) và chuẩn bị nhân sự phục vụ mặt đất (ground handling, tra nạp nhiên liệu, hành lý). Việc chốt cổng đỗ trước 2 giờ là bắt buộc để phát loa thông báo và in thẻ lên tàu bay (boarding pass) cho hành khách.
  > 2. Nếu chọn $T-30$ phút, việc đổi cổng sẽ gây hỗn loạn tại nhà ga vì hành khách đã tập trung tại cổng cũ.
  > 3. Nếu chọn $T-4\text{h}$, độ bất định của thời tiết và luồng không lưu còn quá lớn, làm giảm độ chính xác của mô hình học máy. Vì vậy, $T-2\text{h}$ là điểm cân bằng tối ưu giữa độ chính xác dự báo và tính khả thi vận hành."*

### Câu 2: Tại sao em không dùng toàn bộ dữ liệu từ 2016 đến 2024 để train model cho nhiều dữ liệu hơn mà lại chia nhỏ theo năm?
- **Trả lời**:
  > *"Thưa Thầy/Cô, trong dữ liệu chuỗi thời gian vận tải, việc gộp chung các năm để chia ngẫu nhiên (K-fold Cross Validation) sẽ phạm phải lỗi rò rỉ dữ liệu nghiêm trọng (Data Leakage): mô hình sẽ học trước xu hướng của tương lai để dự báo cho quá khứ.
  > Để đảm bảo tính liêm chính khoa học, chúng em áp dụng nguyên tắc **Temporal Split (Phân chia thời gian một chiều)**:
  > - Dùng 2016–2022 để huấn luyện và tối ưu siêu tham số.
  > - Dùng năm 2023 độc lập hoàn toàn để đánh giá và chọn mô hình.
  > - Năm 2024 được giữ nguyên làm vùng cấm bảo lưu. Cách tiếp cận này mô phỏng chính xác bài toán thực tế: một mô hình được huấn luyện từ dữ liệu quá khứ và triển khai vào vận hành của năm sau."*

---

## NHÓM 2: HỌC MÁY VÀ DỰ BÁO XÁC SUẤT (ML & PROBABILISTIC FORECASTING)

### Câu 3: Tại sao mô hình Median Baseline lại có chỉ số MAE thấp hơn mô hình học máy XGBoost?
- **Trả lời**:
  > *"Thưa Thầy/Cô, đây là hệ quả toán học trực tiếp của **Định lý tối ưu hóa mất mát $L_1$**: Giá trị cực tiểu hóa sai số tuyệt đối MAE của một phân phối chính là giá trị Trung vị (Median). Do hơn $70\%$ chuyến bay đúng giờ hoặc trễ không đáng kể, trung vị độ trễ xấp xỉ bằng 0. Một bộ dự báo luôn đoán bằng 0 sẽ đạt MAE rất thấp ($15.60$ phút) trên các chuyến bay đúng giờ này.
  > Tuy nhiên, mô hình Median hoàn toàn bất lực trong việc phát hiện các chuyến bay trễ nặng. Ngược lại, XGBoost được tối ưu hóa theo hàm mất mát $L_2$ để nắm bắt rủi ro đuôi nặng. Thực nghiệm chứng minh XGBoost vượt trội hơn Median Baseline ở các chỉ số quyết định vận hành:
  > - **RMSE**: XGBoost đạt $43.00$ phút (tốt hơn Median $45.76$ phút).
  > - **Sai số đuôi trễ $\ge 15$ phút**: XGBoost đạt $48.91$ phút (giảm tới $21.5\%$ sai số so với Median $62.33$ phút).
  > - **Sai số đuôi trễ $\ge 60$ phút**: XGBoost đạt $117.18$ phút (tốt hơn Median $132.54$ phút)."*

### Câu 4: Vì sao em lại dùng mô hình NGBoost Student-t thay vì phân phối chuẩn Gaussian?
- **Trả lời**:
  > *"Thưa Thầy/Cô, độ trễ hàng không có tính chất 'đuôi nặng' (Fat-tailed / Leptokurtic): phần lớn chuyến bay trễ ít, nhưng khi có sự cố thời tiết hoặc kỹ thuật thì độ trễ có thể vọt lên 2–3 tiếng. Phân phối chuẩn Gaussian giả định xác suất xảy ra các sự kiện cực đoan này suy giảm theo hàm mũ $\exp(-x^2)$, dẫn đến việc đánh giá thấp nghiêm trọng rủi ro trễ nặng.
  > Phân phối Student-t với bậc tự do được học $\nu = 4.5$ có phần đuôi suy giảm theo luật lũy thừa (Power law), phản ánh chính xác các đỉnh trễ đột biến, giúp các mẫu ngẫu nhiên sinh ra trong mô phỏng Monte Carlo sát với thực tế vận hành sân bay."*

---

## NHÓM 3: TỐI ƯU HÓA PHÂN BỔ CỔNG ĐỖ (GATE OPTIMIZATION)

### Câu 5: Tại sao em lại dùng Google OR-Tools CP-SAT thay vì giải bằng Quy hoạch Tuyến tính Nguyên (MIP)?
- **Trả lời**:
  > *"Thưa Thầy/Cô, bài toán phân bổ cổng đỗ với ràng buộc thời gian (AGAP) nếu giải bằng MIP truyền thống thường phải rời rạc hóa trục thời gian thành các khoảng nhỏ (Time-indexed formulation), dẫn đến việc phát sinh hàng triệu biến nhị phân $x_{i,g,t}$ và ma trận ràng buộc bùng nổ bậc hai $O(N^2)$.
  > Bộ giải CP-SAT của Google sử dụng mô hình hóa dựa trên biến khoảng (`IntervalVar`) và thuật toán lọc lan truyền ràng buộc không đè chồng (`AddNoOverlap`). Cách tiếp cận này duy trì miền biến liên tục, giảm độ phức tạp không gian xuống bậc tuyến tính $O(N \cdot M)$, cho phép giải tối ưu bài toán 300 chuyến bay trong chưa đầy 9 giây."*

### Câu 6: Trong hàm mục tiêu, tại sao em lại phải phân tách giữa Decision Cost và Reporting Cost?
- **Trả lời**:
  > *"Thưa Thầy/Cô, việc phân tách này là bắt buộc để đảm bảo tính công bằng học thuật:
  > 1. **Decision Cost ($J_{\text{decision}}$)**: Là các chi phí trực tiếp phụ thuộc vào quyết định của thuật toán, gồm: phạt đổi cổng danh định, phạt kéo tàu bay ra bãi đỗ xa, và phạt vi phạm đệm mềm. Đây là thước đo thực sự để so sánh năng lực giữa các bộ giải.
  > 2. **Reporting Cost ($J_{\text{reporting}}$)**: Là các hình phạt ngoại sinh do chính độ trễ ban đầu của chuyến bay gây ra, không phụ thuộc vào việc chuyến bay đó đỗ ở cổng nào. Nếu gộp chung, chi phí ngoại sinh quá lớn sẽ che lấp sự khác biệt tinh tế giữa các giải thuật tối ưu."*

---

## NHÓM 4: THUẬT TOÁN SA VÀ HYBRID (SIMULATED ANNEALING & HYBRID)

### Câu 7: Tại sao giải thuật lai Hybrid CP-SAT + SA lại có độ cải thiện đúng bằng 0.00% so với CP-SAT thuần túy?
- **Trả lời**:
  > *"Thưa Thầy/Cô, con số 0.00% này không phải là lỗi lập trình, mà là một **kết quả toán học tất yếu**. CP-SAT là bộ giải chính xác. Trên các bài toán quy mô sân bay khảo sát, CP-SAT đã tìm ra nghiệm và chứng minh được tính tối ưu toàn cục (`optimality_proven == True`).
  > Theo định lý tối ưu hóa, một khi nghiệm đã đạt cực tiểu toàn cục, không có bất kỳ thuật toán metaheuristic nào (kể cả SA) có thể tìm ra nghiệm tốt hơn nghiệm tối ưu đó. Do đó, mức cải thiện của SA bắt buộc bằng 0.00%. Trong kiến trúc hệ thống, SA đóng vai trò là giải pháp an toàn dự phòng (Safety Fallback) khi CP-SAT bị giới hạn thời gian chạy trên các bài toán quy mô khổng lồ, chứ không phải để cải thiện nghiệm đã tối ưu."*

### Câu 8: Thuật toán Simulated Annealing của em sử dụng toán tử biến đổi lân cận (Neighborhood Move) nào?
- **Trả lời**:
  > *"Thưa Thầy/Cô, bộ giải SA sử dụng 2 toán tử lân cận chính bảo toàn tính khả thi:
  > 1. **Reassign Move**: Chọn ngẫu nhiên 1 chuyến bay và thử gán sang một cổng đỗ hợp lệ khác đang trống.
  > 2. **Swap Move**: Chọn 2 chuyến bay đang đỗ ở 2 cổng khác nhau và tráo đổi cổng đỗ cho nhau nếu kích thước tàu bay tương thích và không bị trùng lịch.
  > Mọi bước nhảy nghiệm đều được kiểm tra tính khả thi ràng buộc cứng trước khi áp dụng quy tắc chấp nhận xác suất Metropolis $P = \exp(-\Delta / T)$."*

---

## NHÓM 5: MÔ PHỎNG MONTE CARLO (MONTE CARLO SIMULATION)

### Câu 9: Tại sao Mode A trong mô phỏng Monte Carlo lại có tỷ lệ khả thi tổng hợp là 0%?
- **Trả lời**:
  > *"Thưa Thầy/Cô, con số 0% này là do tiêu chí định nghĩa khả thi cũ đã đánh đồng giữa xung đột vật lý và lệch khe giờ tĩnh. Khi trễ xảy ra, 100% các chuyến bay trễ đều bị lệch khỏi khe giờ danh định ban đầu (Static slot mismatch).
  > Khi bóc tách 5 chiều khả thi trong Gate G2, chúng em làm sáng tỏ: Tỷ lệ thực sự xảy ra va chạm vật lý đè cổng trong Mode A là **$76.0\%$**, nghĩa là vẫn có **$24.0\%$** kịch bản hoàn toàn an toàn về mặt vật lý vì cổng lúc đó đang trống. Việc bóc tách này chứng minh năng lực phân tích khoa học sâu sắc, khách quan của đề tài."*

### Câu 10: Mode B2 của em khác gì so với Mode B1 và tại sao Mode B2 mới là giải thuật nhân quả?
- **Trả lời**:
  > *"Thưa Thầy/Cô:
  > - **Mode B1 (Retrospective Recourse)**: Nhận toàn bộ lịch bay thực tế cả ngày rồi tối ưu lại. Đây là bài toán nhìn lại quá khứ (Hindsight), phi thực tế vì người điều hành không thể biết trước các chuyến bay buổi chiều để điều chỉnh cổng cho buổi sáng.
  > - **Mode B2 (Rolling-Horizon Online Recourse)**: Thuật toán quét sự kiện theo thời gian thực. Tại thời điểm $t$, chỉ những chuyến bay đã hạ cánh trước $t$ mới biết độ trễ; các tàu bay đang đỗ tại cổng bị khóa cứng không được di dời; chỉ những chuyến bay trong tương lai chưa cập cổng mới được gán lại để giải tỏa xung đột. Đây là giải thuật duy nhất tuân thủ nguyên lý nhân quả thời gian thực."*

---

## NHÓM 6: TÍNH GIÁ TRỊ THỐNG KÊ (STATISTICAL VALIDITY)

### Câu 11: Em sử dụng phương pháp thống kê nào để chứng minh Mode B2 thực sự tốt hơn Mode A?
- **Trả lời**:
  > *"Thưa Thầy/Cô, chúng em áp dụng kỹ thuật **Biến ngẫu nhiên chung (Common Random Numbers - CRN)**: Cả Mode A và Mode B2 đều được thử nghiệm trên cùng một tập $N=100$ kịch bản ngẫu nhiên có seed cố định.
  > Sau đó, chúng em tính hiệu chênh lệch bắt cặp (Paired Difference) $\Delta_i = \text{Cost}_{A,i} - \text{Cost}_{B2,i}$ cho từng kịch bản và thực hiện kiểm định t-test bắt cặp. Kết quả cho thấy Mode B2 tiết kiệm trung bình $1,459.0$ điểm chi phí với giá trị $p = 7.03 \times 10^{-21}$ (nhỏ hơn rất nhiều so với ngưỡng $0.05$), chứng minh sự cải thiện là có ý nghĩa thống kê vượt trội, không phải do ngẫu nhiên."*

### Câu 12: Chỉ số CVaR trong nghiên cứu của em đo lường điều gì?
- **Trả lời**:
  > *"Thưa Thầy/Cô, CVaR (Conditional Value-at-Risk ở mức tin cậy $95\%$) đo lường giá trị thiệt hại kỳ vọng trung bình trong $5\%$ kịch bản tồi tệ nhất.
  > Trong điều hành sân bay, nếu chỉ nhìn vào chi phí trung bình thì người quản lý sẽ bị bất ngờ khi xảy ra bão tuyết hoặc giông lốc diện rộng. Chỉ số CVaR giúp sân bay chuẩn bị sẵn phương án dự phòng (như số lượng xe buýt đón tại bãi đỗ xa) cho các tình huống xấu nhất."*

---

## NHÓM 7: DỮ LIỆU THẬT VÀ DỮ LIỆU MÔ PHỎNG (REAL VS SYNTHETIC DATA)

### Câu 13: Tại sao trong lượt chạy dữ liệu thật ngày Lễ Tạ ơn 2023, số cặp quay đầu xác thực lại bằng 0?
- **Trả lời**:
  > *"Thưa Thầy/Cô, đó là hạn chế khách quan của CSDL mở BTS TranStats: CSDL công khai này đã lược bỏ cột số hiệu đăng ký máy bay (`TAIL_NUM`).
  > Động cơ ghép cặp của chúng em tuân thủ liêm chính học thuật: Chỉ khi có số hiệu đuôi trùng khớp thì mới gắn nhãn `VERIFIED_ROTATION`, không tự động bịa ra số đuôi giả.
  > Thay vào đó, hệ thống chứng minh tính khả thi thực tế bằng 2 cách:
  > 1. Ở chế độ dữ liệu thật nghiêm ngặt: Phân bổ tối ưu 200 chuyến bay độc lập trong $1.31$s (0 vi phạm).
  > 2. Ở chế độ suy diễn lịch trình: Ghép cặp được 59 chuyến bay quay đầu dựa trên cùng hãng bay và cửa sổ danh định 45–180 phút, giải tối ưu trong $0.94$s."*

### Câu 14: Dữ liệu mô phỏng synthetic trong đề tài được tạo ra như thế nào?
- **Trả lời**:
  > *"Thưa Thầy/Cô, các kịch bản synthetic (100–300 chuyến bay) được sinh ra dựa trên phân phối lịch trình và tham số đội tàu bay thực tế của sân bay ATL. Các chuyến bay được cấu hình thời gian đến, thời gian đi, loại tàu bay thân hẹp/thân rộng, và tỷ lệ phân bổ theo concourse mô phỏng cấu trúc 7 nhà ga của sân bay ATL."*

---

## NHÓM 8: THỜI GIAN CHẠY VÀ KHẢ NĂNG MỞ RỘNG (RUNTIME & SCALABILITY)

### Câu 15: Bộ giải CP-SAT mất bao lâu để giải bài toán 300 chuyến bay và có đáp ứng thời gian thực không?
- **Trả lời**:
  > *"Thưa Thầy/Cô, trên bài toán quy mô áp lực 300 chuyến bay và 51 cổng đỗ, CP-SAT tìm ra nghiệm tối ưu trong **$8.42$ giây** (hoàn toàn nằm dưới giới hạn thời gian cho phép $30$ giây).
  > Trong chu kỳ điều hành sân bay, việc chạy lại bài toán tái phân bổ cổng mỗi 5 đến 15 phút một lần với thời gian tính toán dưới 10 giây là hoàn toàn đáp ứng yêu cầu vận hành thời gian thực."*

### Câu 16: Nếu quy mô tăng lên 1.000 chuyến bay/ngày thì giải thuật có bị treo (timeout) không?
- **Trả lời**:
  > *"Thưa Thầy/Cô, nếu giải đồng thời 1.000 chuyến trong cả ngày trên một mô hình duy nhất, CP-SAT có thể gặp giới hạn thời gian.
  > Tuy nhiên, trong thực tế hàng không, bài toán được giải quyết bằng kỹ thuật **Khung thời gian trượt (Rolling Horizon Framework)**: Tại mỗi thời điểm, hệ thống chỉ giải cho các chuyến bay trong cửa sổ 4 đến 6 giờ tới (khoảng 200–300 chuyến). Do đó, quy mô bài toán luôn được giới hạn trong ngưỡng tối ưu của CP-SAT."*

---

## NHÓM 9: GIỚI HẠN KHOA HỌC (LIMITATIONS)

### Câu 17: Giới hạn lớn nhất của đề tài này là gì?
- **Trả lời**:
  > *"Thưa Thầy/Cô, giới hạn lớn nhất của đề tài là **chưa tích hợp dữ liệu radar giám sát ADS-B thời gian thực** để cập nhật vị trí máy bay đang bay trên không phận. Hiện tại, hệ thống sử dụng rào chắn thông tin $T-2\text{h}$ dựa trên lịch trình và thống kê. Nếu có thêm dữ liệu vị trí radar trực tiếp khi máy bay chuẩn bị hạ cánh, độ chính xác dự báo độ trễ ở chặng cuối sẽ còn cao hơn nữa."*

### Câu 18: Tại sao em không dùng mô hình Deep Learning (LSTM hoặc Transformer) để dự báo trễ?
- **Trả lời**:
  > *"Thưa Thầy/Cô, chúng em đã khảo sát và nhận thấy: Dữ liệu vận hành bay có cấu trúc dạng bảng (Tabular data) với các biến phân loại mạnh (hãng, tuyến bay, sân bay). Các nghiên cứu thực nghiệm quốc tế uy tín (như Grinsztajn et al., NeurIPS 2022) đã chứng minh các mô hình Gradient Boosting (XGBoost) luôn vượt trội hơn Deep Learning trên dữ liệu dạng bảng cả về độ chính xác, tốc độ huấn luyện lẫn khả năng giải thích đặc trưng thông qua giá trị SHAP."*

---

## NHÓM 10: HƯỚNG PHÁT TRIỂN VÀ ỨNG DỤNG THỰC TẾ (FUTURE WORK)

### Câu 19: Kết quả nghiên cứu của em có thể áp dụng cho các sân bay tại Việt Nam như Nội Bài hay Tân Sơn Nhất không?
- **Trả lời**:
  > *"Thưa Thầy/Cô, hoàn toàn có thể áp dụng được. Các sân bay lớn của Việt Nam như Tân Sơn Nhất (khoảng 800 chuyến/ngày) và Nội Bài đang gặp áp lực quá tải cổng đỗ và sân đỗ rất lớn.
  > Hệ thống của chúng em được thiết kế theo kiến trúc module hóa: Chỉ cần thay đổi cấu hình sơ đồ cổng đỗ (Concourse topology) và nạp dữ liệu lịch bay của Cục Hàng không Việt Nam (CAAV), hệ thống có thể vận hành ngay như một công cụ hỗ trợ ra quyết định (Decision Support System) cho trung tâm điều hành sân bay AOCC."*

### Câu 20: Nếu có thêm thời gian phát triển tiếp, em sẽ cải tiến điều gì?
- **Trả lời**:
  > *"Thưa Thầy/Cô, em sẽ tập trung vào 2 hướng phát triển chính:
  > 1. Mở rộng bài toán tối ưu đa mục tiêu kết hợp giữa cổng đỗ và **Quy hoạch đường lăn (Taxiway Routing)** để cực tiểu hóa thời gian lăn bánh và giảm phát thải nhiên liệu/CO2 của tàu bay.
  > 2. Xây dựng cơ chế học tăng cường (Reinforcement Learning) để tự động điều chỉnh trọng số hàm mục tiêu dựa trên phản hồi thực tế của nhân viên điều độ sân bay."*
