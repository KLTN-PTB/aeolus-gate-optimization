# KHÓA LUẬN TỐT NGHIỆP ĐẠI HỌC
## NGÀNH CÔNG NGHỆ THÔNG TIN

---

**ĐỀ TÀI:**
# ỨNG DỤNG HỌC MÁY VÀ LẬP TRÌNH RÀNG BUỘC TRONG DỰ BÁO ĐỘ TRỄ CHUYẾN BAY VÀ TỐI ƯU TÁI PHÂN BỔ CỔNG ĐỖ TÀU BAY

**Sinh viên thực hiện:** Phùng Thế Bảo  
**Mã số sinh viên:** CNTT-KLCN168  
**Chuyên ngành:** Hệ thống Thông tin & Khoa học Dữ liệu  
**Khóa học:** 2022 – 2026  
**Thời gian thực hiện:** 10/08/2026 – 25/10/2026  
**Cán bộ hướng dẫn:** [Giảng viên Hướng dẫn Đề tài]  
**Cán bộ phản biện:** [Giảng viên Phản biện Đề tài]  

*Thành phố Hồ Chí Minh, Tháng 10 Năm 2026*

---

## LỜI CAM ĐOAN

Tôi xin cam đoan rằng khóa luận tốt nghiệp *"Ứng dụng học máy và lập trình ràng buộc trong dự báo độ trễ chuyến bay và tối ưu tái phân bổ cổng đỗ tàu bay"* là công trình nghiên cứu do chính tôi thực hiện dưới sự hướng dẫn khoa học của Cán bộ hướng dẫn.

Các số liệu thực nghiệm, kết quả đo lường và artifact được trình bày trong khóa luận là hoàn toàn trung thực, được kết xuất trực tiếp từ mã nguồn thực thi và quy trình kiểm toán tự động của hệ thống `aeolus-gate-optimization`. Các mô hình học máy, thuật toán tối ưu và mô phỏng được kế thừa từ các công trình nghiên cứu trước đây đều được dẫn nguồn tường minh và đầy đủ theo chuẩn học thuật. Mọi sự không hoàn hảo của mô hình (bao gồm nghịch lý tối ưu hàm mất mát L1/L2, giới hạn của dữ liệu BTS TranStats và tính bất biến của không gian nghiệm toàn cục) đều được phân tích công khai và trung thực, không ngụy tạo hay che giấu nhằm phục vụ mục đích thương mại hóa.

*Thành phố Hồ Chí Minh, ngày 25 tháng 10 năm 2026*  
**Sinh viên thực hiện**  
*(Ký và ghi rõ họ tên)*  
**Phùng Thế Bảo**

---

## LỜI CẢM ƠN

Để hoàn thành khóa luận tốt nghiệp này, tôi xin bày tỏ lòng biết ơn sâu sắc đến:

Quý Thầy/Cô Khoa Công nghệ Thông tin đã tận tình truyền đạt những kiến thức nền tảng vững chắc về Khoa học Máy tính, Trí tuệ Nhân tạo, Tối ưu hóa Rời rạc và Kỹ nghệ Phần mềm trong suốt 4 năm học vừa qua.

Đặc biệt, tôi xin gửi lời tri ân chân thành nhất tới **Cán bộ hướng dẫn**, người đã luôn định hướng khoa học nghiêm cẩn, hướng dẫn phương pháp nghiên cứu thực nghiệm chặt chẽ, và luôn nhắc nhở về tính trung thực học thuật trong từng kết quả thực nghiệm.

Tôi cũng xin gửi lời cảm ơn tới gia đình, bạn bè và các đồng nghiệp trong nhóm nghiên cứu đã luôn chia sẻ, đồng hành và tạo điều kiện thuận lợi nhất để tôi có thể tập trung hoàn thành công trình nghiên cứu này.

---

## TÓM TẮT ĐỀ TÀI (ABSTRACT)

### Tóm tắt tiếng Việt

Bài toán Phân bổ Cổng đỗ Tàu bay (Airport Gate Assignment Problem - AGAP) là một trong những bài toán tối ưu hóa vận hành cốt lõi và phức tạp nhất tại các sân bay trung chuyển quốc tế quy mô lớn. Trong thực tế khai thác, các yếu tố bất định từ thời tiết, tắc nghẽn không lưu và sự trễ dây chuyền thường xuyên phá vỡ lịch trình phân bổ tĩnh ban đầu, dẫn đến xung đột cổng đỗ, phát sinh chi phí kéo dắt tàu bay (towing) và suy giảm chất lượng dịch vụ hành khách.

Khóa luận này đề xuất và hiện thực hóa một hệ thống tích hợp đa tầng mang tên **Aeolus**, kết hợp mô hình Học máy Dự báo (Machine Learning Forecasting), Tối ưu hóa Rời rạc dựa trên Lập trình Ràng buộc (Constraint Programming - CP-SAT), Tối ưu hóa Cục bộ (Simulated Annealing) và Đánh giá Tính Bền vững bằng Mô phỏng Monte Carlo (Monte Carlo Simulation). 

Hệ thống được xây dựng và kiểm chứng trên tập dữ liệu vận hành thực tế quy mô lớn của Cục Thống kê Giao thông Vận tải Hoa Kỳ (BTS TranStats) tại Sân bay Quốc tế Hartsfield-Jackson Atlanta (ATL) giai đoạn 2016–2024. Tại tầng dự báo, mô hình Dual-Core ML với điểm cắt thời gian nghiêm ngặt $T-2h$ giải quyết đồng thời hai tác vụ: phân loại nhị phân xác suất trễ $P(\text{delay} \ge 15\,\text{phút})$ bằng XGBoost (đạt ROC-AUC $0.778$ cho Inbound và $0.795$ cho Outbound) và hồi quy khoảng độ trễ bằng NGBoost Student-t kết hợp XGBoost Regressor. Nghiên cứu chỉ ra nghịch lý toán học quan trọng: mặc dù giá trị trung vị lịch sử đạt MAE thấp hơn trên toàn bộ phân phối do đặc tính lệch phải cực đại của độ trễ chuyến bay (zero-delay bulk), mô hình ML vượt trội rõ rệt ở việc triệt tiêu phương sai sai số (RMSE giảm từ $45.76$ phút xuống $43.00$ phút) và giảm thiểu $21.5\%$ sai số ở đuôi trễ nghiêm trọng ($\ge 15$ phút).

Tại tầng tối ưu, mô hình CP-SAT chứng minh khả năng tìm ra nghiệm tối ưu toàn cục ($z^* = 10.0000$) trong $0.052$ giây cho bài toán 60 chuyến bay, triệt tiêu $100\%$ xung đột cổng và xóa bỏ hoàn toàn nhu cầu kéo dắt tàu bay, vượt trội so với giải thuật Tham lam ($z = 14.0000$). Nghiên cứu chứng minh rằng trên không gian ràng buộc rời rạc hữu hạn này, CP-SAT đã chứng minh tính tối ưu toàn cục tuyệt đối (Optimality Gap $0.0\%$), do đó giải thuật Hybrid kết hợp Simulated Annealing không thể cải thiện thêm chi phí ($0.00\%$ gain). 

Tại tầng đánh giá bất định, mô phỏng Monte Carlo với 500 kịch bản ngẫu nhiên có tương quan (Gaussian Copula $\rho = 0.45$) chỉ ra rằng kế hoạch tĩnh (Mode A) có tỷ lệ bất khả thi vật lý lên đến $76.0\%$, trong khi cơ chế phân bổ bù trừ cuốn chiếu nhân quả (Mode B2 - Rolling Horizon Causal Recourse) triệt tiêu hoàn toàn xung đột cổng đỗ mà không vi phạm nguyên tắc thông tin nhân quả (zero lookahead leakage). Toàn bộ hệ thống được kiểm toán độc lập qua 2.117 ca kiểm thử tự động, tích hợp trên giao diện điều hành tương tác Streamlit với 5 phân hệ chuyên sâu.

**Từ khóa:** *Phân bổ cổng đỗ tàu bay (AGAP), Học máy (Machine Learning), CP-SAT, Tối ưu hóa rời rạc, Mô phỏng Monte Carlo, Phân tách chuỗi thời gian, Dự báo độ trễ chuyến bay.*

---

### English Abstract

The Airport Gate Assignment Problem (AGAP) is one of the most critical and complex operational optimization challenges at large-scale international hub airports. In practical airport operations, operational uncertainties arising from severe weather, airspace congestion, and reactionary delay propagation frequently disrupt pre-published static gate schedules, triggering physical gate conflicts, costly aircraft towing maneuvers, and diminished passenger transfer experience.

This bachelor's thesis presents the design, mathematical formulation, and end-to-end implementation of **Aeolus**, an integrated multi-tier decision-support architecture that synergizes Machine Learning (ML) probabilistic forecasting, Constraint Programming via Satisfiability (CP-SAT), Metaheuristic Local Search (Simulated Annealing), and Uncertainty Robustness Evaluation via Copula-driven Monte Carlo Simulation.

The proposed system is empirically evaluated on large-scale real-world flight operations data from the US Bureau of Transportation Statistics (BTS TranStats) at Hartsfield-Jackson Atlanta International Airport (ATL) spanning 2016 through 2024. At the predictive layer, a Dual-Core ML framework operating under a strict $T-2\text{h}$ operational cutoff addresses dual predictive objectives: binary delay probability classification $P(\text{delay} \ge 15\text{ min})$ via XGBoost (achieving ROC-AUC of $0.778$ for Inbound and $0.795$ for Outbound) and delay magnitude regression via NGBoost Student-t and XGBoost Regressor. The study unveils an essential mathematical phenomenon: while historical median baselines minimize L1 loss on the highly right-skewed zero-delay bulk (achieving lower overall MAE), the ML models substantially outperform the baseline in error variance reduction (RMSE reduced from $45.76$ min to $43.00$ min) and reduce severe tail-delay error ($\ge 15$ min) by $21.5\%$.

At the optimization layer, the CP-SAT solver rigorously proves global optimality ($z^* = 10.0000$) within $0.052$ seconds on a 60-flight operational core dataset, completely eliminating contact gate conflicts and costly ramp towing maneuvers compared to the baseline Greedy solver ($z = 14.0000$). The research demonstrates that within this discrete flight space, CP-SAT achieves a $0.0\%$ optimality gap, proving that warm-started Simulated Annealing cannot improve upon the proven global optimum ($0.00\%$ gain).

At the robustness evaluation layer, a 500-realization Monte Carlo simulation driven by a bivariate Gaussian Copula ($\rho = 0.45$) demonstrates that static schedules (Mode A) suffer a $76.0\%$ physical conflict rate, whereas an online event-driven rolling recourse strategy (Mode B2) eliminates $100\%$ of contact conflicts while strictly respecting temporal causality without lookahead bias. The end-to-end architecture is certified via a comprehensive suite of 2,117 automated regression tests and deployed via an interactive Streamlit control tower dashboard.

**Keywords:** *Airport Gate Assignment Problem (AGAP), Machine Learning, CP-SAT, Discrete Optimization, Monte Carlo Simulation, Temporal Split, Flight Delay Forecasting.*

---

## DANH MỤC CHỮ VIẾT TẮT

| Viết tắt | Thuật ngữ Tiếng Anh | Ý nghĩa Tiếng Việt |
| :--- | :--- | :--- |
| **AGAP** | Airport Gate Assignment Problem | Bài toán Phân bổ Cổng đỗ Tàu bay |
| **ATL** | Hartsfield-Jackson Atlanta International Airport | Sân bay Quốc tế Hartsfield-Jackson Atlanta |
| **BTS** | Bureau of Transportation Statistics | Cục Thống kê Giao thông Vận tải Hoa Kỳ |
| **CP-SAT** | Constraint Programming - Boolean Satisfiability | Lập trình Ràng buộc trên nền SAT (Google OR-Tools) |
| **CRN** | Common Random Numbers | Kỹ thuật Số ngẫu nhiên dùng chung |
| **FAA** | Federal Aviation Administration | Cục Hàng không Liên bang Hoa Kỳ |
| **GAP** | Optimality Gap | Khoảng cách Tối ưu hóa |
| **HPO** | Hyperparameter Optimization | Tối ưu hóa Siêu tham số |
| **LR** | Logistic Regression | Hồi quy Logistic |
| **MAE** | Mean Absolute Error | Sai số Tuyệt đối Trung bình |
| **MILP** | Mixed-Integer Linear Programming | Quy hoạch Tuyến tính Số nguyên Hỗn hợp |
| **ML** | Machine Learning | Học máy |
| **NGBoost** | Natural Gradient Boosting | Tăng cường Gradient Tự nhiên cho Dự báo Phân phối |
| **OR** | Operations Research | Nghiên cứu Vận hành (Vận trù học) |
| **RF** | Random Forest | Rừng Ngẫu nhiên |
| **RMSE** | Root Mean Squared Error | Căn bậc hai Sai số Toàn phương Trung bình |
| **ROC-AUC**| Receiver Operating Characteristic - Area Under Curve | Diện tích dưới đường cong ROC |
| **SA** | Simulated Annealing | Giải thuật Mô phỏng Luyện kim |
| **SHAP** | SHapley Additive exPlanations | Giải thích Giá trị Cộng tính Shapley |
| **XGBoost**| eXtreme Gradient Boosting | Tăng cường Gradient Cực hạn |

---

## DANH MỤC BẢNG BIỂU

- **Bảng 3.1:** Phân tách dữ liệu theo chuỗi thời gian (BTS TranStats ATL, 2016–2024).
- **Bảng 3.2:** Bảng mã băm xác thực tính toàn vẹn Checkpoint và Artifact thực nghiệm.
- **Bảng 5.1:** Đánh giá hiệu năng dự báo trễ chuyến đến (Inbound Delay) trên tập kiểm thử 2023.
- **Bảng 5.2:** Đánh giá hiệu năng dự báo trễ chuyến đi (Outbound Delay) trên tập kiểm thử 2023.
- **Bảng 5.3:** Đánh giá so sánh hiệu năng các thuật toán tối ưu hóa phân bổ cổng (60 chuyến bay).
- **Bảng 5.4:** Kết quả mô phỏng độ bền vững Monte Carlo (500 kịch bản ngẫu nhiên).
- **Bảng 5.5:** Đánh giá thực nghiệm End-to-End trên dữ liệu thực tế Lễ Tạ ơn 2023 (ATL).
- **Bảng 5.6:** Tổng hợp kết quả kiểm thử hồi quy toàn diện hệ thống (Regression Test Suite).
- **Bảng 5.7:** Bảng đối chiếu mã băm SHA-256 các artifact và mô hình đóng băng.

---

## DANH MỤC HÌNH VẼ

- **Hình 2.1:** Khung kiến trúc bài toán Predict-then-Optimize trong vận hành sân bay.
- **Hình 3.1:** Phân phối độ trễ chuyến bay thực tế tại ATL và hiện tượng lệch phải cực đại.
- **Hình 4.1:** Sơ đồ kiến trúc tổng thể 4 tầng của hệ thống Aeolus Gate Optimization.
- **Hình 4.2:** Lưu đồ quy trình phân tách chuỗi thời gian và bảo đảm hợp đồng bất biến $T-2h$.
- **Hình 4.3:** Mô hình chu trình quay đầu tàu bay (Aircraft Turnaround) và cơ chế Turn Pairing.
- **Hình 5.1:** Biểu đồ ROC đường cong phân loại xác suất trễ Inbound và Outbound.
- **Hình 5.2:** Phân tích độ quan trọng của đặc trưng theo giá trị SHAP cho mô hình XGBoost.
- **Hình 5.3:** Biểu đồ Gantt phân bổ cổng đỗ tàu bay tối ưu tạo bởi CP-SAT solver.
- **Hình 5.4:** Phân phối hàm chi phí Monte Carlo qua 500 kịch bản giữa các chế độ A, B1, B2 và C.

---

# CHƯƠNG 1: TỔNG QUAN VÀ BỐI CẢNH ĐỀ TÀI

## 1.1. Bối cảnh Vận hành Hàng không và Bài toán Phân bổ Cổng đỗ (AGAP)

Ngành hàng không dân dụng thế giới đóng vai trò huyết mạch trong mạng lưới giao thông toàn cầu, vận chuyển hàng tỷ lượt hành khách và hàng triệu tấn hàng hóa mỗi năm. Tại các sân bay trung chuyển quốc tế quy mô cực lớn (mega-hub airports) như Sân bay Quốc tế Hartsfield-Jackson Atlanta (ATL) – sân bay bận rộn nhất thế giới với hơn 100 triệu lượt khách và hàng trăm nghìn chuyến bay cất hạ cánh mỗi năm – việc quản lý và tối ưu hóa hạ tầng mặt đất là bài toán sống còn quyết định năng lực khai thác của toàn bộ hệ thống.

Trong số các quy trình vận hành mặt đất, **Bài toán Phân bổ Cổng đỗ Tàu bay (Airport Gate Assignment Problem - AGAP)** chiếm vị trí trọng tâm. Mục tiêu của AGAP là gán mỗi chuyến bay (hoặc chu trình quay đầu tàu bay - aircraft turnaround) đến một vị trí cổng đỗ tiếp xúc hành khách (contact gate) hoặc bãi đỗ xa (remote apron) thích hợp trong một khoảng thời gian xác định, sao cho thỏa mãn hàng loạt các ràng buộc kỹ thuật khắt khe:
1. **Ràng buộc tương thích vật lý:** Kích thước sải cánh, loại tàu bay (Aircraft Category/ICAO code) phải tương thích với giới hạn chịu tải và hình học của cầu ống lồng tại cổng đỗ.
2. **Ràng buộc loại hình chuyến bay:** Chuyến bay quốc tế phải được phân bổ tại các nhà ga có phân khu kiểm soát hải quan và nhập cảnh (Customs and Border Protection - CBP, ví dụ Concourse E, F tại ATL); chuyến bay nội địa phục vụ tại các Concourse nội địa (Concourse T, A, B, C, D).
3. **Ràng buộc thời gian cách ly an toàn (Safety Buffer):** Hai tàu bay liên tiếp đỗ tại cùng một cổng phải cách nhau một khoảng thời gian tối thiểu (Separation Time Buffer, thông thường từ 15 đến 30 phút) nhằm bảo đảm an toàn đẩy lùi (push-back) và tránh va chạm mặt đất.
4. **Mục tiêu tối ưu hóa chi phí:** Tối thiểu hóa quãng đường đi bộ của hành khách chuyển tiếp, tối đa hóa việc đỗ tại cổng tiếp xúc thay vì bãi đỗ xa, hạn chế tối đa việc kéo dắt tàu bay (towing) sang vị trí khác giữa chừng, và ưu tiên phân bổ theo phân khu thương hiệu của hãng hàng không (Airline Concourse Preference).

Tuy nhiên, thách thức lớn nhất của AGAP trong môi trường vận hành thực tế không nằm ở tính toán tĩnh, mà nằm ở **tính bất định động (dynamic uncertainty)**. Các yếu tố như bão tuyết, giông lốc mùa hè, sự cố kỹ thuật của tàu bay, sự tắc nghẽn của luồng không lưu (Air Traffic Control Ground Delay Programs - GDP) và sự trễ tích lũy từ các chặng bay trước đó khiến thời gian đến thực tế (Actual Inbound Time) và thời gian khởi hành thực tế (Actual Outbound Time) thường xuyên sai lệch đáng kể so với lịch trình công bố (Scheduled Time). Khi một chuyến bay đến sớm hoặc đến trễ nghiêm trọng, kế hoạch phân bổ cổng ban đầu ngay lập tức bị phá vỡ, dẫn đến nguy cơ xung đột cổng (hai tàu bay tranh chấp cùng một vị trí), buộc đài kiểm soát phải cho máy bay chờ đợi trên đường lăn (taxiway queue) gây tiêu hao nhiên liệu khổng lồ, hoặc phải kích hoạt quy trình kéo dắt khẩn cấp với chi phí vận hành rất cao.

## 1.2. Mục tiêu Nghiên cứu của Đề tài

Xuất phát từ bối cảnh thực tiễn trên, khóa luận hướng tới các mục tiêu nghiên cứu cụ thể:
1. **Xây dựng đường ống xử lý dữ liệu chuẩn tắc (Data Engineering Pipeline):** Khai thác và chuẩn hóa dữ liệu vận hành hàng không thực tế từ Cục Thống kê Giao thông Vận tải Hoa Kỳ (BTS TranStats) cho toàn bộ các chuyến bay đến và đi tại Sân bay ATL từ năm 2016 đến 2024.
2. **Phát triển hệ thống Học máy Dự báo Đa lõi (Dual-Core ML):** Thiết lập mô hình dự báo xác suất trễ nhị phân $P(\text{delay} \ge 15\,\text{phút})$ và dự báo phân phối mức độ trễ (delay magnitude) cho cả chuyến bay đến (Inbound) và chuyến bay đi (Outbound). Đặc biệt, nghiên cứu tuân thủ nghiêm ngặt quy ước thời gian thực hành (operational cutoff $T-2h$) nhằm loại bỏ triệt để rò rỉ dữ liệu nhìn trước tương lai (lookahead data leakage).
3. **Mô hình hóa và giải quyết bài toán AGAP bằng Lập trình Ràng buộc (CP-SAT):** Xây dựng mô hình tối ưu hóa toán học đầy đủ các ràng buộc thực tế, khai thác sức mạnh của bộ giải CP-SAT (Google OR-Tools) để tìm ra phương án phân bổ cổng tối ưu toàn cục với thời gian giải đáp ứng thời gian thực.
4. **Nghiên cứu giải thuật Metaheuristic và Tiếp cận Lai ghép (Hybrid Approach):** Triển khai giải thuật Mô phỏng Luyện kim (Simulated Annealing - SA) và cơ chế lai ghép (warm-start CP-SAT với SA) để đánh giá khả năng cải tiến nghiệm và phân tích tính chất của không gian tìm kiếm.
5. **Mô phỏng Đánh giá Tính Bền vững bằng Monte Carlo:** Thiết lập khung thực nghiệm mô phỏng 500 kịch bản bất định có tương quan bằng Gaussian Copula và số ngẫu nhiên dùng chung (Common Random Numbers - CRN) để kiểm chứng độ bền vững của kế hoạch phân bổ tĩnh (Mode A), so sánh cơ chế bù trừ hồi tố (Mode B1), cơ chế bù trừ cuốn chiếu nhân quả (Mode B2) và nghiệm thấu thị lý tưởng (Mode C).
6. **Xây dựng Ứng dụng Bảng điều khiển Trực quan (Interactive Control Tower Dashboard):** Tích hợp toàn bộ chuỗi xử lý từ dự báo, tối ưu hóa đến mô phỏng vào một giao diện web trực quan phục vụ người vận hành sân bay.

## 1.3. Đối tượng và Phạm vi Nghiên cứu

- **Đối tượng nghiên cứu:** 
  - Quy trình khai thác cổng đỗ tại sân bay quốc tế quy mô lớn.
  - Các kỹ thuật học máy có giám sát (Logistic Regression, Random Forest, XGBoost, NGBoost).
  - Các phương pháp nghiên cứu vận hành và tối ưu hóa tổ hợp (Greedy Heuristics, CP-SAT, Simulated Annealing).
  - Phương pháp mô phỏng thống kê ngẫu nhiên Monte Carlo và lý thuyết Copula.
- **Phạm vi nghiên cứu (Scope Boundaries):**
  - *Không gian địa lý:* Tập trung chuyên sâu vào Sân bay Quốc tế Hartsfield-Jackson Atlanta (mã IATA: ATL), bao gồm 7 Concourse (T, A, B, C, D, E, F) với các cổng tiếp xúc và bãi đỗ xa.
  - *Thời gian dữ liệu:* Dữ liệu lịch sử giai đoạn 2016–2022 dùng cho huấn luyện và kiểm định chéo; năm 2023 dùng cho lựa chọn mô hình và benchmark thực nghiệm; năm 2024 làm tập holdout kiểm toán hậu kiểm.
  - *Quy chuẩn học vị:* Đề tài được thực hiện trong khuôn khổ **Khóa luận Tốt nghiệp Cử nhân Công nghệ Thông tin**, hướng tới việc thiết kế kiến trúc phần mềm khoa học, kiểm chứng thực nghiệm nghiêm ngặt và đánh giá độ tin cậy của hệ thống, không tuyên bố giải quyết trọn vẹn toàn bộ các khía cạnh kinh tế vĩ mô hay cơ chế điều phối không lưu cấp liên bang (FAA ATC slot allocation).

## 1.4. Đóng góp Khoa học và Thực tiễn của Khóa luận

Khóa luận mang lại các đóng góp nổi bật sau:
1. **Làm sáng tỏ bản chất toán học của phân phối trễ trong bài toán Predict-then-Optimize:** Phân tích và chứng minh hiện tượng phân phối trễ lệch phải cực đại dẫn đến việc ước lượng trung vị (Median Baseline) có MAE thấp hơn mô hình ML trên toàn bộ tập dữ liệu, nhưng mô hình ML mới là nhân tố quyết định giảm thiểu phương sai (RMSE) và bắt trúng các sự kiện trễ đuôi nghiêm trọng ($\ge 15$ phút), yếu tố then chốt gây xung đột cổng.
2. **Xác lập ranh giới phương pháp luận nghiêm ngặt về Temporal Cutoff:** Thiết lập cơ chế kiểm soát hợp đồng thời gian $T-2h$ và phân tích nguyên nhân loại bỏ đặc trưng chuỗi chuyến bay (Flight Chain Lookahead) nhằm bảo vệ tính toàn vẹn học thuật và loại bỏ rò rỉ thông tin tương lai trong thực tế vận hành.
3. **Chứng minh tính tối ưu toàn cục tuyệt đối của CP-SAT:** Cung cấp bằng chứng thực nghiệm và lý thuyết cho thấy trên bài toán AGAP với tập dữ liệu lõi 60 chuyến bay, bộ giải CP-SAT tìm ra nghiệm tối ưu toàn cục chỉ trong $0.052$ giây (khoảng cách tối ưu $0.0\%$), bác bỏ giả định phổ biến rằng các thuật toán metaheuristic như Simulated Annealing có thể cải thiện thêm chất lượng nghiệm của bộ giải chính xác.
4. **Phân định rõ ràng giữa Hồi tố Phi nhân quả (Mode B1) và Cuốn chiếu Nhân quả (Mode B2) trong Mô phỏng Bất định:** Khắc phục sai lầm phương pháp luận thường gặp trong các nghiên cứu trước khi dùng thông tin tương lai để tái phân bổ cổng trong mô phỏng Monte Carlo; đề xuất cơ chế Rolling Horizon Recourse hoàn toàn nhân quả, loại bỏ $100\%$ xung đột cổng thực tế.
5. **Hệ thống hóa bộ kiểm thử và kiểm toán độc lập:** Cung cấp một khung kiểm thử tự động với 2.117 ca kiểm thử, bảo đảm khả năng tái lập $100\%$ toàn bộ kết quả thực nghiệm.

## 1.5. Cấu trúc Khóa luận

Khóa luận được cấu trúc thành 6 chương:
- **Chương 1: Tổng quan và Bối cảnh Đề tài:** Trình bày bối cảnh hàng không, bài toán AGAP, mục tiêu, phạm vi và đóng góp của đề tài.
- **Chương 2: Cơ sở Lý thuyết và Các Công trình Liên quan:** Khảo cứu lý thuyết về học máy trong dự báo hàng không, trường phái Predict-then-Optimize, lập trình ràng buộc CP-SAT, metaheuristic SA và mô phỏng ngẫu nhiên Monte Carlo.
- **Chương 3: Dữ liệu, Phương pháp và Mô hình Toán học:** Chi tiết hóa quy trình tiền xử lý dữ liệu BTS, phân tách chuỗi thời gian, hợp đồng $T-2h$, mô hình Dual-Core ML, công thức toán học AGAP cho CP-SAT và khung mô phỏng bất định.
- **Chương 4: Thiết kế và Kiến trúc Hệ thống:** Mô tả kiến trúc tổng thể 4 tầng của hệ thống Aeolus, động cơ ghép cặp Turn Pairing, cơ chế benchmark thuật toán và ứng dụng Streamlit Control Tower.
- **Chương 5: Kết quả Thực nghiệm và Thảo luận:** Báo cáo chi tiết các kết quả định lượng, phân tích so sánh các mô hình ML, so sánh các thuật toán tối ưu, đánh giá tính bền vững Monte Carlo và thử nghiệm trên dữ liệu thực tế Thanksgiving 2023.
- **Chương 6: Kết luận và Hướng Phát triển:** Tổng kết công trình, tuyên bố minh bạch 10 giới hạn khoa học và gợi mở các hướng nghiên cứu mở rộng trong tương lai.

---

# CHƯƠNG 2: CƠ SỞ LÝ THUYẾT VÀ CÁC CÔNG TRÌNH LIÊN QUAN

## 2.1. Tiếp cận Học máy trong Dự báo Độ trễ Chuyến bay

Dự báo độ trễ chuyến bay là chủ đề được nghiên cứu sâu rộng trong ngành khoa học dữ liệu và vận trù học hàng không trong hơn hai thập kỷ qua. Độ trễ phát sinh từ sự tương tác phi tuyến tính phức tạp giữa nhiều yếu tố: điều kiện khí tượng (gió ngược, bão tuyết, trần mây thấp), tắc nghẽn hạ tầng sân bay, quy định giãn cách của cơ quan quản lý không lưu (FAA/Eurocontrol) và hiệu ứng lan truyền trễ dây chuyền (reactionary delay) qua các chặng bay liên tiếp của cùng một tàu bay.

Các nghiên cứu tiên phong của Sternberg et al. (2017) và Belcastro et al. (2016) đã chứng minh rằng các mô hình học máy phi tham số và mô hình cây quyết định dạng tập hợp (ensemble trees) như Random Forest và Gradient Boosting vượt trội hơn đáng kể so với các mô hình kinh tế lượng truyền thống (như ARIMA hoặc Hồi quy Tuyến tính Đa biến) trong việc nắm bắt các mối quan hệ phi tuyến và tương tác bậc cao giữa thời gian trong ngày, ngày trong tuần, hãng hàng không và lưu lượng không lưu.

Gần đây, Chen et al. (2016) với thuật toán XGBoost (Extreme Gradient Boosting) đã thiết lập tiêu chuẩn mới về độ chính xác và hiệu năng tính toán trong các bài toán dự báo dữ liệu bảng (tabular data). Bằng việc sử dụng xấp xỉ Taylor bậc hai cho hàm mất mát kết hợp các số hạng chuẩn hóa độ phức tạp của cây (L1 và L2 regularization), XGBoost kiểm soát tốt hiện tượng quá khớp (overfitting) ngay cả khi số lượng đặc trưng danh mục (categorical features) được mã hóa ở mức độ lớn.

Bên cạnh dự báo giá trị điểm (point forecasting), hướng nghiên cứu dự báo phân phối xác suất (probabilistic forecasting) ngày càng nhận được sự chú ý trong các bài toán ra quyết định trong điều kiện rủi ro. Duan et al. (2020) đề xuất NGBoost (Natural Gradient Boosting), một thuật toán boosting sử dụng gradient tự nhiên để ước lượng tham số của một phân phối xác suất có điều kiện định trước (ví dụ: phân phối Student-t hoặc Normal). Thay vì chỉ trả về một giá trị trễ kỳ vọng duy nhất $\hat{y}$, NGBoost cung cấp toàn bộ hàm mật độ xác suất $p(y|x)$, cho phép ước lượng độ bất định thông qua phương sai hoặc các phân vị trễ, đóng vai trò đầu vào vô cùng giá trị cho các bài toán tối ưu hóa bền vững phía sau.

## 2.2. Trường phái Tiếp cận Dự báo rồi Tối ưu (Predict-then-Optimize)

Trong quản lý vận hành truyền thống, quy trình giải quyết bài toán thường được tách rời thành hai bước độc lập: trước tiên, nhóm khoa học dữ liệu xây dựng mô hình dự báo nhằm tối thiểu hóa các hàm mất mát thống kê tiêu chuẩn như Mean Squared Error (MSE) hoặc Mean Absolute Error (MAE); sau đó, các dự báo điểm này được chuyển giao cho nhóm nghiên cứu vận hành làm tham số đầu vào cố định cho mô hình quy hoạch toán học (Mathematical Programming). Trường phái này được gọi là **Predict-then-Optimize** (Elmachtoub & Grigas, 2022).

Tuy nhiên, Elmachtoub và Grigas (2022) đã chỉ ra một hạn chế cố hữu của trường phái phân tách thuần túy: hàm mất mát thống kê không đồng nhất với hàm chi phí tối ưu hóa. Một sai số dự báo nhỏ ở một chuyến bay then chốt có thể dẫn đến việc phá vỡ hàng loạt ràng buộc thời gian đệm và gây xung đột dây chuyền tại cổng đỗ, trong khi một sai số lớn ở một chuyến bay độc lập có thể hoàn toàn không gây ảnh hưởng đến quyết định phân bổ. Do đó, việc hiểu rõ mối liên kết giữa chất lượng dự báo đuôi trễ (tail delay) và tính khả thi của phương án phân bổ là cốt lõi để thu hẹp khoảng cách giữa lý thuyết và thực tiễn vận hành.

## 2.3. Bài toán Phân bổ Cổng đỗ và Phương pháp Lập trình Ràng buộc (CP-SAT)

Về mặt phân loại độ phức tạp thuật toán, Bài toán Phân bổ Cổng đỗ Tàu bay (AGAP) thuộc lớp bài toán tối ưu hóa tổ hợp NP-khó (NP-hard), tương đương với bài toán tô màu đồ thị có trọng số (Weighted Graph Coloring Problem) hoặc bài toán đóng gói thùng có ràng buộc thời gian (Interval Bin Packing Problem) (Ding et al., 2005; Dorndorf et al., 2007).

Các công trình ban đầu thường mô hình hóa AGAP dưới dạng Quy hoạch Tuyến tính Số nguyên Hỗn hợp (Mixed-Integer Linear Programming - MILP) hoặc Quy hoạch Toàn phương Số nguyên (Quadratic Integer Programming) nhằm tối thiểu hóa khoảng cách đi bộ của hành khách hoặc số lượng cổng bị xung đột (Bihr, 1990; Mangoubi & Mathaisel, 1985). Tuy nhiên, cách tiếp cận MILP truyền thống gặp trở ngại nghiêm trọng khi kích thước bài toán tăng lên: số lượng biến nhị phân đại diện cho xung đột thời gian giữa các cặp chuyến bay tăng theo cấp số nhân $O(N^2 \cdot M)$ (với $N$ là số chuyến bay và $M$ là số cổng), dẫn đến hiện tượng bùng nổ tổ hợp và thời gian giải vượt quá giới hạn cho phép trong điều hành thời gian thực.

Nhằm khắc phục nhược điểm này, Lập trình Ràng buộc (Constraint Programming - CP) nổi lên như một công cụ đắc lực nhờ khả năng mô hình hóa tự nhiên các biến khoảng thời gian (Interval Variables) và các ràng buộc phi chồng lấn toàn cục (Global No-Overlap Constraints) (Laborie et al., 2018). Bộ giải **CP-SAT** thuộc thư viện Google OR-Tools (Perron & Furnon, 2019) tích hợp các kỹ thuật tiên tiến nhất của công nghệ giải SAT hiện đại (Conflict-Driven Clause Learning - CDCL), kết hợp với kỹ thuật lan truyền ràng buộc miền giá trị (Constraint Propagation) và phương pháp Lập trình Tuyến tính Hỗn hợp (Lazy Linearization). Nhờ đó, CP-SAT có khả năng cắt tỉa không gian tìm kiếm cực kỳ hiệu quả, nhanh chóng chứng minh tính tối ưu toàn cục hoặc tìm ra nghiệm khả thi chất lượng cao trong thời gian chỉ tính bằng phần trăm giây đối với các bài toán có quy mô vừa và lớn.

## 2.4. Thuật toán Metaheuristic và Giải thuật Mô phỏng Luyện kim (Simulated Annealing)

Khi kích thước bài toán vượt quá khả năng giải quyết chính xác trong giới hạn thời gian thực (ví dụ hàng nghìn chuyến bay trong điều kiện khẩn cấp), các thuật toán tìm kiếm cục bộ và metaheuristic thường được áp dụng. Giải thuật Mô phỏng Luyện kim (Simulated Annealing - SA), được khởi xướng bởi Kirkpatrick et al. (1983) dựa trên nguyên lý nhiệt động lực học trong quá trình làm nguội chậm kim loại, là một trong những thuật toán metaheuristic kinh điển được áp dụng thành công cho AGAP (Drexl & Nikulin, 2008).

Ưu điểm nổi bật của SA là cơ chế chấp nhận nghiệm xấu hơn với một xác suất biến thiên phụ thuộc vào nhiệt độ $T$:
$$P(\text{accept}) = \exp\left(-\frac{\Delta z}{T}\right)$$
Cơ chế này cho phép thuật toán thoát khỏi các điểm cực tiểu cục bộ (local minima) trong các giai đoạn nhiệt độ cao ban đầu, sau đó hội tụ dần về các vùng không gian nghiệm hứa hẹn khi nhiệt độ giảm dần theo lịch trình làm nguội (cooling schedule). Tuy nhiên, SA thuần túy không có khả năng bảo đảm tìm ra nghiệm tối ưu toàn cục và không cung cấp được cận dưới toán học (lower bound) để đo lường khoảng cách tới nghiệm tối ưu (optimality gap).

## 2.5. Mô phỏng Đánh giá Tính Bền vững dưới Điều kiện Bất định (Monte Carlo Simulation)

Một phương án phân bổ cổng dù đạt chi phí tối ưu trên lịch trình danh nghĩa (nominal schedule) vẫn có thể trở nên vô dụng nếu nó không có khả năng chống chịu trước các biến động ngẫu nhiên của thời gian đến và đi trong thực tế. Đánh giá tính bền vững (Robustness Evaluation) do đó trở thành một cấu phần không thể thiếu trong nghiên cứu vận trù học hiện đại (Dorndorf et al., 2008).

Phương pháp Mô phỏng Monte Carlo cho phép đánh giá hiệu năng của kế hoạch phân bổ trên một số lượng lớn các kịch bản ngẫu nhiên khả dĩ của độ trễ chuyến bay. Để mô phỏng phản ánh đúng hiện thực khai thác, hai vấn đề kỹ thuật trọng yếu cần được giải quyết:
1. **Cấu trúc phụ thuộc giữa các chuyến bay (Dependence Structure):** Độ trễ của các chuyến bay trong cùng một khung giờ thường có tương quan thuận do cùng chịu ảnh hưởng của các điều kiện thời tiết hoặc tắc nghẽn vùng trời. Việc giả định các chuyến bay độc lập độc lập thống kê sẽ dẫn đến đánh giá quá lạc quan về rủi ro xung đột cổng. Do đó, việc sử dụng hàm Copula (Nelsen, 2006) – cụ thể là Gaussian Copula – cho phép mô hình hóa chính xác hệ số tương quan đuôi giữa độ trễ đến và độ trễ đi mà không làm thay đổi các phân phối biên thực nghiệm.
2. **Kỹ thuật Số ngẫu nhiên Dùng chung (Common Random Numbers - CRN):** Khi so sánh các chính sách điều hành khác nhau (ví dụ: giữ nguyên kế hoạch tĩnh vs. tái phân bổ động), việc áp dụng CRN bảo đảm rằng các chính sách được kiểm thử trên cùng một chuỗi biến cố ngẫu nhiên đồng nhất, triệt tiêu phương sai ngoại lai và bảo đảm tính công bằng tuyệt đối trong so sánh thống kê (Law, 2015).


---

# CHƯƠNG 3: DỮ LIỆU, PHƯƠNG PHÁP VÀ MÔ HÌNH TOÁN HỌC

## 3.1. Nguồn Dữ liệu BTS TranStats và Phân tích Đặc trưng Sân bay ATL

Nghiên cứu sử dụng nguồn dữ liệu vận hành hàng không công khai từ Cục Thống kê Giao thông Vận tải Hoa Kỳ (**Bureau of Transportation Statistics - BTS TranStats**), thuộc Bộ Giao thông Vận tải Hoa Kỳ (USDOT). Tập dữ liệu gốc bao gồm toàn bộ báo cáo đúng giờ (On-Time Performance Reporting) của các hãng hàng không thương mại có chứng nhận khai thác tại Hoa Kỳ từ tháng 01/2016 đến tháng 12/2024.

Để phục vụ bài toán AGAP tại Sân bay Quốc tế Hartsfield-Jackson Atlanta (ATL), dữ liệu được trích xuất và lọc theo hai lát cắt không gian:
- **Lát cắt Chuyến bay Đến (Inbound / Arrival Dataset):** Lọc theo điều kiện sân bay đến là ATL (`DEST == 'ATL'`).
- **Lát cắt Chuyến bay Đi (Outbound / Departure Dataset):** Lọc theo điều kiện sân bay khởi hành là ATL (`ORIGIN == 'ATL'`).

Các bản ghi có trạng thái bị hủy (`CANCELLED == 1`) hoặc chuyển hướng bay (`DIVERTED == 1`) được loại bỏ khỏi tập dữ liệu phân tích độ trễ liên tục do không tham gia vào quy trình chiếm dụng cổng đỗ thông thường tại sân bay đích. Tổng số bản ghi chuyến bay đến tại ATL sau khi làm sạch đạt **4.167.269 bản ghi**, tạo nên một cơ sở dữ liệu thực nghiệm quy mô lớn phản ánh đầy đủ các chu kỳ mùa vụ, sự biến động thời tiết cực đoan và các giai đoạn biến động đặc thù (bao gồm cả giai đoạn gián đoạn giao thông trong đại dịch COVID-19 giai đoạn 2020–2021).

Một phát hiện kiểm toán dữ liệu quan trọng trong khóa luận là: Trong các bản phát hành công khai của BTS TranStats qua giao thức trích xuất tự động, trường thông tin số hiệu đuôi tàu bay (`TAIL_NUM`) bị lược bỏ hoặc khuyết thiếu trên diện rộng. Do đó, mã định danh duy nhất của mỗi chuyến bay được xác lập trên bộ khóa tổng hợp bao gồm: `(FL_DATE, OP_UNIQUE_CARRIER, OP_CARRIER_FL_NUM, ORIGIN, DEST, CRS_DEP_TIME)`.

## 3.2. Phân tách Chuỗi Thời gian (Temporal Split) và Quy ước Bất biến Cutoff T-2h

Để ngăn ngừa triệt để hiện tượng rò rỉ dữ liệu qua thời gian (Temporal Lookahead Data Leakage) – một sai sót phổ biến khi áp dụng phương pháp K-fold cross-validation ngẫu nhiên trên dữ liệu chuỗi thời gian – khóa luận áp dụng phương pháp phân tách tuần tự theo thời gian lịch sử nghiêm ngặt (Chronological Temporal Split) như được mô tả trong Bảng 3.1:

**Bảng 3.1: Phân tách dữ liệu theo chuỗi thời gian (BTS TranStats ATL, 2016–2024)**

| Tập Dữ liệu | Khung Thời gian | Số lượng Bản ghi | Tỷ lệ (%) | Mục đích Khoa học |
| :--- | :---: | :---: | :---: | :--- |
| **Train / Validation** | 2016 – 2022 | 3.365.512 | 80,76% | Huấn luyện mô hình cơ sở, điều chỉnh trọng số và Cross-Validation cuốn chiếu theo năm |
| **Model Selection (Test)**| 2023 | 399.773 | 9,59% | Đánh giá độc lập, lựa chọn mô hình chính thức, tối ưu hóa siêu tham số (Optuna HPO) |
| **Post-hoc Holdout** | 2024 | 401.984 | 9,65% | Tập kiểm toán hậu kiểm độc lập, kiểm chứng khả năng tổng quát hóa trên dữ liệu chưa thấy |
| **Tổng cộng (ATL Arrival)**| **2016 – 2024** | **4.167.269** | **100,00%** | **Toàn bộ không gian dữ liệu thực nghiệm** |

Cùng với phân tách chuỗi thời gian, hệ thống thiết lập một hợp đồng bất biến thời gian vận hành mang tên **Cutoff T-2h**:
$$\mathcal{T}_{\text{cutoff}} = \text{CRS\_DEP\_TIME} - 120\,\text{phút}$$
Tại thời điểm $T-2h$ trước giờ khởi hành dự kiến, toàn bộ các đặc trưng đầu vào phục vụ dự báo chỉ được phép khai thác các thông tin đã được công bố hoặc đã xảy ra trước thời điểm $\mathcal{T}_{\text{cutoff}}$. Mọi thông tin phát sinh sau mốc này (bao gồm thời gian lăn bánh thực tế `TAXI_OUT`, thời gian cất cánh thực tế `WHEELS_OFF`, hoặc độ trễ phát sinh trên đường bay `AIR_TIME_DELAY`) đều bị cấm tuyệt đối nhằm bảo đảm tính khả thi triển khai trong thực tế vận hành tại trung tâm điều hành bay.

## 3.3. Loại trừ Rò rỉ Thông tin Flight Chain (Flight Chain Exclusion)

Trong quá trình nghiên cứu ban đầu, một giả thuyết kỹ thuật được đặt ra là việc bổ sung đặc trưng chuỗi hành trình chuyến bay (Flight Chain Features – ví dụ: độ trễ của chặng bay trước đó của cùng một tàu bay) sẽ giúp tăng độ chính xác của mô hình dự báo. Tuy nhiên, qua quá trình kiểm toán khoa học độc lập tại Gate G1–G3, nghiên cứu đã phát hiện một rủi ro phương pháp luận nghiêm trọng:

Do tập dữ liệu BTS thiếu trường `TAIL_NUM`, việc suy diễn chuỗi bay phải dựa trên các giả định phỏng đoán. Nguy hiểm hơn, nếu một mô hình khai thác trạng thái đến của chuyến bay trước tại thời điểm $T-2h$ mà chuyến bay trước đó thực tế chưa hoàn thành hành trình, thông tin đưa vào mô hình sẽ vô tình chứa đựng tri thức nhìn trước tương lai (Lookahead Leakage). Do đó, để bảo đảm tính trung thực học thuật tuyệt đối và bảo vệ tính hợp lệ của mọi kết luận khoa học, **toàn bộ các đặc trưng Flight Chain mang tính phỏng đoán đã bị loại bỏ khỏi mô hình chính thức**. Mô hình dự báo của khóa luận thuần túy dựa trên các đặc trưng bảng độc lập (Tabular Features) tuân thủ nghiêm ngặt điểm cắt $T-2h$.

## 3.4. Kiến trúc Dự báo Đa lõi (Dual-Core Machine Learning Pipeline)

Hệ thống triển khai kiến trúc Dual-Core ML giải quyết song song hai tác vụ dự báo với các vai trò chức năng riêng biệt:

### 3.4.1. Tác vụ Phân loại Xác suất Trễ Nhị phân $P(\text{delay} \ge 15\,\text{phút})$
Theo định nghĩa của Cục Hàng không Liên bang Hoa Kỳ (FAA), một chuyến bay được coi là trễ nếu thời gian đến hoặc khởi hành thực tế chênh lệch từ 15 phút trở lên so với lịch trình danh nghĩa:
$$y_{\text{binary}} = \mathbb{I}(\text{ARR\_DELAY} \ge 15) \quad \text{hoặc} \quad y_{\text{binary}} = \mathbb{I}(\text{DEP\_DELAY} \ge 15)$$
Ba thuật toán phân loại có giám sát được huấn luyện và so sánh:
1. **Logistic Regression (LR):** Mô hình tuyến tính cơ sở có chuẩn hóa L2, cung cấp đường chuẩn hiệu năng tối thiểu và khả năng diễn giải trực tiếp thông qua hệ số hồi quy trọng số.
2. **Random Forest (RF):** Mô hình học tập hợp dạng đóng bao (Bagging) gồm 100 cây quyết định, cho phép nắm bắt các tương tác phi tuyến và giảm phương sai ước lượng.
3. **XGBoost Classifier:** Mô hình tăng cường gradient cực hạn (Chen et al., 2016), được tối ưu hóa siêu tham số tự động bằng Optuna qua 50 thử nghiệm (trials) trên tập huấn luyện 2016–2022. Đây là mô hình chính thức được tích hợp vào pipeline điều hành.

### 3.4.2. Tác vụ Hồi quy Mức độ Trễ (Delay Magnitude Regression)
Nhằm cung cấp giá trị thời gian chiếm dụng cổng ước tính cho bộ giải tối ưu, hệ thống huấn luyện các mô hình hồi quy:
1. **P4 Core Arrival (NGBoost Student-t):** Mô hình Natural Gradient Boosting (Duan et al., 2020) với phân phối mục tiêu là phân phối Student-t ba tham số (vị trí $\mu$, tỷ lệ $\sigma$, bậc tự do $\nu$). Lựa chọn Student-t giúp mô hình có khả năng chống chịu cao trước các điểm dị biệt cực đoan (heavy tails) vốn rất phổ biến trong dữ liệu trễ hàng không.
2. **P4 Core Departure (XGBoost Regressor):** Mô hình hồi quy cây gradient tăng cường chuyên biệt cho chuyến bay đi, dự báo giá trị độ lệch phút cất cánh.
3. **Mô hình Hồi quy Tuyến tính Ridge:** Mô hình hồi quy chuẩn hóa L2 đóng vai trò đường cơ sở tham chiếu.

Toàn bộ các mô hình sau khi huấn luyện được đóng băng trọng số (frozen checkpoints) và xác thực bằng mã băm SHA-256 (Bảng 3.2).

**Bảng 3.2: Bảng mã băm xác thực tính toàn vẹn Checkpoint và Artifact thực nghiệm**

| Tên Artifact / Checkpoint | Đường dẫn Tệp | Thuật toán | Mã băm SHA-256 Xác thực |
| :--- | :--- | :---: | :--- |
| **Inbound Classifier** | `models/inbound_xgb_classifier.joblib` | SHA-256 | `2c270cbaf46990263f3366c8b9d0319caef38ddaa3f8373b37803e73bfa993e3` |
| **Inbound Regressor (P4)** | `models/inbound_ngboost_student_t.joblib`| SHA-256 | `7ad6a7fc8e5bf410e30953c306e917d0577be2ba97e0bbfa1f0b093ca2dfa616` |
| **Outbound Classifier** | `models/outbound_xgb_classifier.joblib`| SHA-256 | `278456cfd74e0d37e199d79cae5a59a7a911a37c09c3eef595b16fca9c470a1e` |
| **Outbound Regressor** | `models/outbound_xgb_regressor.joblib` | SHA-256 | `868019b840e4e525166f272a276ae68e8eef3141f92e061b40283b0b5bb02fca` |
| **Core Flight Dataset** | `data/processed/p07_flights_core.csv` | SHA-256 | `5a5c689d70fa7e2a9b3488f572aeb41d3b377b78a0a9fb9cf6cf87d3e41c4115` |
| **Historical P5 Quantile**| `artifacts/p05_quantiles.csv` | SHA-256 | `e98f01b3a4a5... (frozen historical artifact)` |

## 3.5. Mô hình Toán học Bài toán Phân bổ Cổng đỗ Tàu bay (AGAP Formulation)

Mô hình AGAP trong khóa luận được công thức hóa dưới dạng bài toán Tối ưu hóa Ràng buộc Rời rạc (Constraint Optimization Problem - COP), được thiết kế tương thích trực tiếp với động cơ suy luận của Google OR-Tools CP-SAT.

### 3.5.1. Định nghĩa Tập hợp và Chỉ số
- $\mathcal{I} = \{1, 2, \dots, N\}$: Tập hợp các chuyến bay hoặc chu trình quay đầu tàu bay (turnaround flights) cần phân bổ cổng trong cửa sổ lập lịch (planning window).
- $\mathcal{K} = \{1, 2, \dots, M\}$: Tập hợp các cổng đỗ tại sân bay ATL, bao gồm cổng tiếp xúc (contact gates) tại các Concourse T, A, B, C, D, E, F và các bãi đỗ xa (remote aprons / overflow gates).
- $\mathcal{C}$: Tập hợp các nhà ga hành khách (Concourses). Mỗi cổng $k \in \mathcal{K}$ thuộc về đúng một concourse $c(k) \in \mathcal{C}$.

### 3.5.2. Tham số Đầu vào
- $s_i \in \mathbb{R}^+$: Thời điểm bắt đầu chiếm dụng cổng dự kiến của chuyến bay $i$, được tính toán từ lịch trình danh nghĩa kết hợp giá trị hiệu chỉnh trễ đến từ mô hình ML: $s_i = \text{CRS\_ARR\_TIME}_i + \hat{d}^{\text{arr}}_i$.
- $e_i \in \mathbb{R}^+$: Thời điểm kết thúc chiếm dụng cổng dự kiến: $e_i = \text{CRS\_DEP\_TIME}_i + \hat{d}^{\text{dep}}_i$.
- $\Delta_i = e_i - s_i$: Thời lượng chiếm dụng cổng (Dwell time) của chuyến bay $i$.
- $\delta_{\text{sep}}$: Khoảng thời gian đệm an toàn tối thiểu giữa hai tàu bay liên tiếp sử dụng cùng một cổng (mặc định $\delta_{\text{sep}} = 15$ phút).
- $A_i$: Phân cấp kích thước tàu bay (Aircraft Size Category: Small, Medium, Heavy, Super-Heavy).
- $C_k$: Phân cấp năng lực tiếp nhận tối đa của cổng $k$.
- $\gamma_{ik} \in \{0, 1\}$: Ma trận tương thích vật lý giữa chuyến bay $i$ và cổng $k$, với $\gamma_{ik} = 1$ nếu sải cánh và loại thân tàu bay của $i$ cho phép đỗ tại $k$, ngược lại $\gamma_{ik} = 0$.
- $\pi_{ik} \in \{0, 1\}$: Ma trận tương thích loại hình chuyến bay (International/Domestic), với $\pi_{ik} = 1$ nếu cổng $k$ có cơ sở CBP hỗ trợ chuyến bay quốc tế khi $i$ là chuyến bay quốc tế.
- $P_{ik} \ge 0$: Hệ số phạt vi phạm ưu tiên nhà ga của hãng hàng không (Airline Concourse Preference Penalty). Nếu chuyến bay của hãng hàng không được phân bổ đúng concourse căn cứ (ví dụ: Delta Air Lines ưu tiên Concourse A, B; Southwest Airlines ưu tiên Concourse C), $P_{ik} = 0$; ngược lại $P_{ik} = 1.0$.
- $W_{\text{tow}} = 1.0$: Trọng số phạt đối với hành động kéo dắt tàu bay ra bãi đỗ xa (Remote Towing Penalty).
- $W_{\text{pref}} = 1.0$: Trọng số phạt đối với vi phạm ưu tiên nhà ga.

### 3.5.3. Biến Quyết định
- $x_{ik} \in \{0, 1\}$: Biến nhị phân chỉ thị; $x_{ik} = 1$ nếu chuyến bay $i$ được phân bổ vào cổng $k$, ngược lại $x_{ik} = 0$.
- $u_i \in \{0, 1\}$: Biến nhị phân chỉ thị chuyến bay $i$ không thể phân bổ vào cổng tiếp xúc mà buộc phải chuyển ra bãi đỗ xa hoặc kéo dắt ($u_i = 1$).
- $\mathbf{Interval}_{ik}$: Biến khoảng tùy chọn (Optional Interval Variable) trong CP-SAT, kích hoạt khi $x_{ik} = 1$, có thời gian bắt đầu $s_i$, thời gian kết thúc $e_i + \delta_{\text{sep}}$, và độ dài $\Delta_i + \delta_{\text{sep}}$.

### 3.5.4. Hàm Mục tiêu
Hàm mục tiêu toàn cục tối thiểu hóa tổng chi phí vận hành có trọng số:
$$\min_{\mathbf{x}, \mathbf{u}} \quad \mathcal{Z} = \sum_{i \in \mathcal{I}} \left( W_{\text{tow}} \cdot u_i + W_{\text{pref}} \cdot \sum_{k \in \mathcal{K}} P_{ik} \cdot x_{ik} \right)$$
Trọng số được chuẩn hóa sao cho chi phí phạt cho một lần đẩy ra bãi xa hoặc kéo dắt ($W_{\text{tow}} = 1.0$) tương đương với một lần vi phạm ưu tiên nhà ga ($W_{\text{pref}} = 1.0$). Khi tất cả các chuyến bay đều được phân bổ vào đúng cổng tiếp xúc tối ưu và đúng concourse ưu tiên, giá trị hàm mục tiêu lý tưởng đạt $\mathcal{Z}^* = 0$.

### 3.5.5. Hệ thống Các Ràng buộc
1. **Ràng buộc Phân bổ Duy nhất (Exact Assignment):**
   Mỗi chuyến bay phải được gán vào đúng một cổng đỗ hợp lệ:
   $$\sum_{k \in \mathcal{K}} x_{ik} = 1, \quad \forall i \in \mathcal{I}$$
2. **Ràng buộc Tương thích Vật lý và Loại hình Chuyến bay (Physical & CBP Feasibility):**
   Chuyến bay $i$ chỉ được phép gán vào cổng $k$ nếu thỏa mãn cả điều kiện hình học và quy định biên giới:
   $$x_{ik} \le \gamma_{ik} \cdot \pi_{ik}, \quad \forall i \in \mathcal{I}, \, \forall k \in \mathcal{K}$$
3. **Ràng buộc Phi Chồng lấn Thời gian Toàn cục (Global No-Overlap Constraint):**
   Tại mỗi cổng đỗ $k$, các khoảng chiếm dụng (kèm khoảng đệm an toàn $\delta_{\text{sep}}$) của các chuyến bay được gán vào cổng đó không được phép giao nhau:
   $$\text{NoOverlap}\left( \{\mathbf{Interval}_{ik} \mid i \in \mathcal{I}\} \right), \quad \forall k \in \mathcal{K}$$
   Biểu diễn tương đương theo đại số số nguyên: Với mọi cặp chuyến bay $i, j \in \mathcal{I}$ ($i \ne j$), nếu $x_{ik} = 1$ và $x_{jk} = 1$ thì:
   $$e_i + \delta_{\text{sep}} \le s_j \quad \lor \quad e_j + \delta_{\text{sep}} \le s_i$$
4. **Ràng buộc Liên kết Biến Kéo dắt (Towing Linkage):**
   Nếu chuyến bay $i$ bị gán vào cổng thuộc tập bãi đỗ xa $\mathcal{K}_{\text{remote}}$, biến chỉ thị kéo dắt được kích hoạt:
   $$u_i \ge \sum_{k \in \mathcal{K}_{\text{remote}}} x_{ik}, \quad \forall i \in \mathcal{I}$$

## 3.6. Mô hình Mô phỏng Bất định Monte Carlo (Monte Carlo Robustness Framework)

Để kiểm chứng tính bền vững của các phương án phân bổ cổng trước các biến động thời gian thực, khóa luận xây dựng mô hình mô phỏng Monte Carlo đa kịch bản với các đặc tính toán học chuẩn mực:

### 3.6.1. Cấu trúc Mô phỏng Phụ thuộc Gaussian Copula
Độ trễ thực tế của chuyến bay đến ($\tilde{d}^{\text{arr}}_i$) và chuyến bay đi ($\tilde{d}^{\text{dep}}_i$) trong kịch bản thứ $s \in \{1, \dots, S\}$ ($S = 500$) được sinh ra bằng cách lấy mẫu ngẫu nhiên từ cấu trúc phụ thuộc song biến (Bivariate Dependence):
$$\begin{pmatrix} U_i^{\text{arr}} \\ U_i^{\text{dep}} \end{pmatrix} \sim \mathcal{C}_{\text{Gauss}}\left(\rho = 0.45\right)$$
$$\tilde{d}^{\text{arr}}_{i, s} = F_{\text{arr}}^{-1}(U_i^{\text{arr}}), \quad \tilde{d}^{\text{dep}}_{i, s} = F_{\text{dep}}^{-1}(U_i^{\text{dep}})$$
Trong đó $\mathcal{C}_{\text{Gauss}}$ là Gaussian Copula với hệ số tương quan mặc định $\rho = 0.45$, phản ánh mối tương quan thuận thực tế giữa trễ đến và trễ đi trong các chu trình quay đầu tàu bay. $F_{\text{arr}}^{-1}$ và $F_{\text{dep}}^{-1}$ là hàm phân phối tích lũy nghịch đảo thực nghiệm (Empirical Quantile Functions) trích xuất từ tập dữ liệu BTS ATL.

Kỹ thuật Số ngẫu nhiên Dùng chung (**Common Random Numbers - CRN**) được thiết lập với seed ngẫu nhiên xác định (`seed = 42`) để bảo đảm 500 kịch bản bất định hoàn toàn giống nhau khi đánh giá giữa các chế độ vận hành.

### 3.6.2. Bốn Chế độ Vận hành Đánh giá Độ bền vững
1. **Mode A (Fixed Plan):** Kế hoạch phân bổ cổng ban đầu được giữ nguyên tuyệt đối trong suốt quá trình vận hành bất kể độ trễ thực tế biến động như thế nào. Chế độ này đo lường rủi ro xung đột cổng vật lý (Physical Gate Conflicts) của kế hoạch tĩnh.
2. **Mode B1 (Retrospective Clairvoyant Recourse):** Mô hình tái phân bổ cổng hồi tố có tri thức tương lai hoàn hảo (Lookahead Clairvoyance). Toàn bộ độ trễ của 500 kịch bản được nạp đồng thời vào bộ giải tại thời điểm kết thúc ngày để tìm phương án khắc phục xung đột. Chế độ này đóng vai trò mốc tham chiếu toán học lý thuyết nhưng **không khả thi triển khai thực tế** vì vi phạm tính nhân quả thời gian.
3. **Mode B2 (Rolling Horizon Causal Recourse):** Cơ chế tái phân bổ cuốn chiếu theo dòng sự kiện thời gian thực (Event-Driven Online Recourse). Tại mỗi thời điểm $t$, bộ giải chỉ nhận biết độ trễ của các chuyến bay đã xuất hiện tại hoặc trước $t$. Khi phát hiện nguy cơ xung đột giữa hai chuyến bay, thuật toán kích hoạt hành động dời cổng (Gate Reassignment) chỉ trên các chuyến bay chưa tiếp cận vị trí đỗ, hoàn toàn tôn trọng tính nhân quả thời gian (zero lookahead leakage).
4. **Mode C (Perfect Foresight Oracle):** Kế hoạch phân bổ tối ưu toàn cục được giải từ đầu với giả định người điều hành biết trước toàn bộ độ trễ thực tế của tất cả các chuyến bay ngay từ đầu ngày. Đây là cận trên lý tưởng (Theoretical Upper Bound) về chất lượng phân bổ.

---

# CHƯƠNG 4: THIẾT KẾ VÀ KIẾN TRÚC HỆ THỐNG

## 4.1. Kiến trúc Tổng thể 4 Tầng (Four-Tier Architecture)

Hệ thống **Aeolus Gate Optimization** được thiết kế theo mô hình kiến trúc phân tầng dạng module hóa cao (Decoupled Modular Architecture), phân tách độc lập giữa xử lý dữ liệu, suy luận học máy, giải thuật tối ưu và giao diện điều hành tương tác (Hình 4.1).

```
+-----------------------------------------------------------------------------------+
|                           TẦNG 4: TRÌNH DIỄN & KIỂM TOÁN                          |
|  - Streamlit Control Tower Dashboard (5 Pages: Control Tower, Flight Intel, etc.) |
|  - Independent Audit & Verification Suite (2.117 Automated Pytest Regression Tests)|
+---------------------------------------------------------^-------------------------+
                                                          |
+---------------------------------------------------------v-------------------------+
|                           TẦNG 3: TỐI ƯU HÓA & MÔ PHỎNG                           |
|  - Solvers: Greedy Heuristic, CP-SAT (Google OR-Tools), Simulated Annealing, Hybrid|
|  - Turn Pairing Engine (Turnaround Synthesizer & Inferred Pairing Engine)         |
|  - Monte Carlo Simulator (500 Realizations, Gaussian Copula, CRN Mode A/B1/B2/C)  |
+---------------------------------------------------------^-------------------------+
                                                          |
+---------------------------------------------------------v-------------------------+
|                           TẦNG 2: HỌC MÁY DỰ BÁO ĐA LÕI                           |
|  - Cutoff Invariant T-2h Enforcement Engine (Zero Lookahead Leakage)              |
|  - Inbound Core: XGBoost Classifier + NGBoost Student-t Probabilistic Regressor   |
|  - Outbound Core: XGBoost Classifier + XGBoost Regressor                          |
|  - Model Checkpoint Integrity Verifier (SHA-256 Fingerprinting)                   |
+---------------------------------------------------------^-------------------------+
                                                          |
+---------------------------------------------------------v-------------------------+
|                           TẦNG 1: DỮ LIỆU & NGUỒN GỐC                             |
|  - BTS TranStats Clean Ingestion Engine (ATL Filter: DEST='ATL' / ORIGIN='ATL')   |
|  - Temporal Split Partitioning (2016-2022 Train, 2023 Selection, 2024 Holdout)    |
|  - Data Schema Contracts & Missing Value Sanitization                             |
+-----------------------------------------------------------------------------------+
```
*Hình 4.1: Sơ đồ kiến trúc tổng thể 4 tầng của hệ thống Aeolus Gate Optimization.*

## 4.2. Hợp đồng Toàn vẹn Dữ liệu (Data Provenance & Invariant Contracts)

Để bảo đảm tính tái lập khoa học (Scientific Reproducibility), toàn bộ luồng dữ liệu trong hệ thống được kiểm soát thông qua các hợp đồng bất biến (Invariant Contracts):
1. **Hợp đồng Lược đồ Dữ liệu (Schema Contracts):** Mọi tệp dữ liệu đầu vào và trung gian đều được kiểm tra chặt chẽ về định dạng cột, kiểu dữ liệu (`datetime64`, `float64`, `int64`) và khoảng giá trị hợp lệ trước khi được nạp vào các tầng tiếp theo.
2. **Hợp đồng Mã băm Đóng băng (Frozen Checkpoint Contracts):** Trước mỗi phiên thực thi suy luận hoặc tối ưu hóa, hệ thống tự động băm SHA-256 các tệp mô hình lưu trữ trong thư mục `models/` và đối chiếu với bảng mã băm gốc. Bất kỳ sự sai khác nào dù chỉ 1 bit đều kích hoạt cảnh báo dừng hệ thống để ngăn chặn việc sử dụng mô hình bị sửa đổi âm thầm.
3. **Hợp đồng Tính Xác định (Deterministic Seed Contract):** Mọi quá trình sinh số ngẫu nhiên (từ khởi tạo trọng số, phân chia kịch bản Monte Carlo đến bước nhảy Markov trong Simulated Annealing) đều được cố định seed xác định (`seed = 42`), bảo đảm kết quả đầu ra luôn nhất quán 100% qua các lần chạy độc lập.

## 4.3. Động cơ Ghép cặp Chu trình Tàu bay (Native Pairing Engine)

Một tàu bay trong thực tế hạ cánh tại sân bay ATL với tư cách là một chuyến bay đến (Inbound Leg), thực hiện quá trình phục vụ mặt đất (dỡ hành lý, tiếp nhiên liệu, vệ sinh, đón khách mới) tại cổng đỗ trong khoảng thời gian quay đầu (Turnaround Dwell Time), sau đó khởi hành với tư cách là một chuyến bay đi (Outbound Leg). 

Do tập dữ liệu BTS TranStats công khai không cung cấp số hiệu đuôi tàu bay (`TAIL_NUM`), hệ thống Aeolus xây dựng hai chế độ ghép cặp linh hoạt trong `src/simulation/aircraft_turn_pairing.py`:
1. **Chế độ Lịch trình Ghép cặp Chuẩn (Synthetic / Verified Turn Mode):** Sử dụng tập dữ liệu chuẩn hóa 60 chuyến bay (tương ứng 30 cặp quay đầu hoàn chỉnh) với các mốc thời gian và cổng đỗ tương thích vật lý được xác thực phục vụ kiểm chuẩn thuật toán (Benchmark Harness).
2. **Chế độ Suy diễn Chu trình Thực tế (Inferred Turnaround Mode):** Áp dụng trên tập dữ liệu vận hành thực tế không có số hiệu đuôi tàu bay (ví dụ đợt cao điểm Lễ Tạ ơn - Thanksgiving 2023 với 200 chuyến bay thực). Động cơ ghép cặp tự động quét và liên kết một chuyến bay đến và một chuyến bay đi nếu thỏa mãn đồng thời các điều kiện:
   - Cùng một hãng hàng không khai thác (`OP_UNIQUE_CARRIER`).
   - Cùng phân cấp kích thước tàu bay.
   - Thời gian cách biệt giữa giờ đến dự kiến và giờ đi dự kiến nằm trong khoảng quay đầu hợp lệ: $45\,\text{phút} \le \text{CRS\_DEP\_TIME} - \text{CRS\_ARR\_TIME} \le 180\,\text{phút}$.
   - Chuyến bay đến chưa được ghép cặp với chuyến bay nào trước đó (quy tắc gán tham lam thứ tự thời gian).
   Các chuyến bay không tìm được chặng ghép cặp hợp lệ được xử lý độc lập dưới dạng chuyến bay đơn lẻ (Singleton Flight Mode) với thời gian chiếm dụng cổng danh nghĩa, bảo đảm không loại bỏ dữ liệu thực tế và hoàn toàn không sử dụng dữ liệu nhân tạo dự phòng (No synthetic fallback).

## 4.4. Thiết kế các Bộ giải Tối ưu và Khung Benchmark (Solvers & Benchmark Harness)

Hệ thống hiện thực hóa 5 bộ giải độc lập phục vụ kiểm chuẩn đối đầu (Head-to-head Benchmark):
1. **Greedy Heuristic Solver:** Duyệt danh sách chuyến bay theo thứ tự thời gian bắt đầu chiếm dụng cổng $s_i$. Với mỗi chuyến bay, giải thuật quét danh sách cổng đỗ theo thứ tự ưu tiên concourse và gán vào cổng tương thích đầu tiên không bị xung đột thời gian. Nếu không tìm được cổng tiếp xúc khả thi, chuyến bay được gán vào bãi đỗ xa (towing penalty).
2. **CP-SAT Solver (Google OR-Tools):** Xây dựng mô hình toán học đầy đủ theo công thức tại Mục 3.5. Sử dụng các biến `IntervalVar` và ràng buộc `AddNoOverlap` toàn cục. Thời gian giới hạn tìm kiếm (Time Limit) được thiết lập mặc định 10 giây.
3. **Simulated Annealing (SA) Solver:** Khởi tạo từ một phương án khả thi ngẫu nhiên hoặc nghiệm Greedy. Tại mỗi bước lặp, giải thuật thực hiện phép biến đổi lân cận (Neighborhood Move) bằng cách chọn ngẫu nhiên một chuyến bay và gán lại vào một cổng tương thích khác, hoặc hoán đổi cổng giữa hai chuyến bay. Nhiệt độ giảm dần theo quy luật hàm mũ: $T_{k+1} = \alpha \cdot T_k$ với $\alpha = 0.995$.
4. **Hybrid Solver (CP-SAT warm-start SA):** Sử dụng phương án nghiệm tìm được từ CP-SAT làm nghiệm khởi đầu (warm-start) cho Simulated Annealing, sau đó chạy thêm 500 bước lặp tìm kiếm cục bộ nhằm kiểm tra khả năng tinh chỉnh chi phí.
5. **Exhaustive Oracle Solver:** Sử dụng tìm kiếm vét cạn nhánh cận (Branch and Bound) trên không gian nhỏ để xác lập cận tối ưu toàn cục tuyệt đối phục vụ xác thực tính đúng đắn của các bộ giải khác.

Khung kiểm chuẩn `src/optimization/benchmark_harness.py` thực hiện 10 lần chạy lặp lại trên cùng một tập dữ liệu, đo lường các chỉ số: giá trị hàm mục tiêu $z$, thời gian giải (CPU/Wall-clock time), số lượng xung đột cổng, số lượng chuyến bay kéo dắt, và trạng thái hội tụ của bộ giải.

## 4.5. Thiết kế Bảng Điều khiển Vận hành Tương tác (Streamlit Control Tower Dashboard)

Giao diện điều hành được phát triển trên nền tảng Streamlit kết hợp thư viện đồ họa tương tác Plotly, cung cấp 5 trang chức năng chuyên sâu phục vụ hai nhóm đối tượng: Cán bộ Vận hành Sân bay (Presentation Mode) và Nhà Nghiên cứu Khoa học (Research Mode):
1. **Trang 1 - Control Tower (Đài Kiểm soát Trung tâm):** Hiển thị tổng quan các chỉ số KPI vận hành thời gian thực, lưu lượng chuyến bay theo giờ (Flight Wave), tỷ lệ chiếm dụng theo từng Concourse (T, A, B, C, D, E, F) và bản đồ nhiệt trạng thái cổng đỗ.
2. **Trang 2 - Flight Intelligence (Trí tuệ Dự báo Chuyến bay):** Cho phép tra cứu chi tiết từng chuyến bay, trực quan hóa xác suất trễ nhị phân, phân phối xác suất trễ liên tục từ mô hình NGBoost Student-t và biểu đồ phân rã giá trị đóng góp đặc trưng SHAP (SHapley Additive exPlanations).
3. **Trang 3 - Gate Operations (Tác nghiệp Cổng đỗ):** Biểu diễn lịch trình phân bổ cổng dưới dạng Biểu đồ Gantt tương tác đa chiều. Người vận hành có thể lọc theo Concourse, xem chi tiết chu trình quay đầu tàu bay (Inbound $\to$ Turnaround $\to$ Outbound), và phát hiện trực quan các điểm xung đột hoặc khoảng đệm an toàn bị vi phạm.
4. **Trang 4 - Optimization Lab (Phòng Thí nghiệm Tối ưu hóa):** Cho phép người dùng tùy chọn và kích hoạt trực tiếp các bộ giải (Greedy, CP-SAT, SA, Hybrid), tùy chỉnh trọng số hàm mục tiêu ($W_{\text{tow}}, W_{\text{pref}}$), thời gian giới hạn giải và so sánh đối đầu các chỉ số hiệu năng trên cùng một màn hình.
5. **Trang 5 - Robustness Lab (Phòng Đánh giá Độ bền vững):** Môi trường thực thi mô phỏng Monte Carlo tương tác. Người dùng có thể điều chỉnh số lượng kịch bản (100–500), hệ số tương quan Copula ($\rho$), kích hoạt so sánh đồng thời giữa Mode A (Tĩnh), Mode B1 (Hồi tố), Mode B2 (Cuốn chiếu nhân quả) và Mode C (Thấu thị lý tưởng), với các biểu đồ phân phối xác suất hàm chi phí trực quan.


---

# CHƯƠNG 5: KẾT QUẢ THỰC NGHIỆM VÀ THẢO LUẬN

## 5.1. Đánh giá Thực nghiệm Hệ thống Học máy Dự báo Đa lõi

Hiệu năng của các mô hình học máy trong kiến trúc Dual-Core ML được đánh giá độc lập trên tập dữ liệu kiểm thử năm 2023 (gồm 399.773 bản ghi chuyến bay đến và tương ứng các chuyến bay đi tại Sân bay ATL), tuân thủ nghiêm ngặt hợp đồng điểm cắt thời gian $T-2h$.

### 5.1.1. Kết quả Dự báo Chuyến bay Đến (Inbound Delay Evaluation)
Bảng 5.1 tổng hợp toàn diện các chỉ số phân loại nhị phân $P(\text{delay} \ge 15\,\text{phút})$ và các chỉ số hồi quy mức độ trễ của chuyến bay đến:

**Bảng 5.1: Đánh giá hiệu năng dự báo trễ chuyến đến (Inbound Delay) trên tập kiểm thử 2023**

| Nhóm Mô hình | Thuật toán Đánh giá | Accuracy | ROC-AUC | F1-Score | Brier Score | MAE (Toàn bộ) | RMSE (Toàn bộ) | Tail MAE ($\ge 15\text{m}$) | Tail Bias |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Phân loại** | **Logistic Regression** | 0,814 | 0,741 | 0,440 | 0,126 | — | — | — | — |
| **Phân loại** | **Random Forest** | 0,825 | 0,763 | 0,485 | 0,119 | — | — | — | — |
| **Phân loại** | **XGBoost (Chính thức)** | **0,832** | **0,778** | **0,512** | **0,112** | — | — | — | — |
| **Hồi quy** | **Baseline Median (P4)** | — | — | — | — | **15,60 phút** | 45,76 phút | 62,33 phút | +61,90 phút |
| **Hồi quy** | **Ridge Regression** | — | — | — | — | 18,25 phút | 44,12 phút | 50,12 phút | +28,40 phút |
| **Hồi quy** | **NGBoost Student-t (P4)** | — | — | — | — | 17,60 phút | **43,00 phút** | **48,91 phút** | **+14,20 phút** |

### 5.1.2. Kết quả Dự báo Chuyến bay Đi (Outbound Delay Evaluation)
Bảng 5.2 trình bày hiệu năng dự báo trên tập chuyến bay khởi hành từ ATL trong năm 2023:

**Bảng 5.2: Đánh giá hiệu năng dự báo trễ chuyến đi (Outbound Delay) trên tập kiểm thử 2023**

| Nhóm Mô hình | Thuật toán Đánh giá | Accuracy | ROC-AUC | F1-Score | Brier Score | MAE (Toàn bộ) | RMSE (Toàn bộ) | Tail MAE ($\ge 15\text{m}$) | Tail Bias |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Phân loại** | **Logistic Regression** | 0,829 | 0,762 | 0,468 | 0,118 | — | — | — | — |
| **Phân loại** | **Random Forest** | 0,838 | 0,779 | 0,495 | 0,112 | — | — | — | — |
| **Phân loại** | **XGBoost (Chính thức)** | **0,845** | **0,795** | **0,528** | **0,106** | — | — | — | — |
| **Hồi quy** | **XGBoost Regressor (P4)** | — | — | — | — | **16,40 phút** | **41,80 phút** | **47,10 phút** | **+12,80 phút** |
| **Hồi quy** | **Ridge Regressor** | — | — | — | — | 17,10 phút | 42,95 phút | 49,30 phút | +24,10 phút |
| **Phân vị** | **Historical Quantile (P5)**| — | — | — | — | *Coverage: 79,8%* | *Pinball Loss: 6,12m* | — | — |

### 5.1.3. Phân tích Sâu sắc về Nghịch lý Sai số: Median Baseline so với Machine Learning
Một kết quả thực nghiệm có ý nghĩa phương pháp luận sâu sắc trong Bảng 5.1 là: **Đường cơ sở Trung vị Lịch sử (Median Baseline) đạt MAE thấp hơn mô hình NGBoost Student-t (15,60 phút so với 17,60 phút), nhưng mô hình NGBoost lại vượt trội hoàn toàn về RMSE và sai số ở đuôi trễ (Tail MAE).**

Hiện tượng này được giải thích chặt chẽ bằng cơ sở toán học và đặc tính phân phối của dữ liệu hàng không:
1. **Bản chất toán học của tối ưu hóa hàm mất mát L1:** Về mặt lý thuyết xác suất, giá trị dự báo tối thiểu hóa kỳ vọng hàm mất mát trị tuyệt đối $\mathbb{E}[|Y - \hat{y}|]$ chính là trung vị của phân phối xác suất có điều kiện: $\hat{y}^*_{\text{L1}} = \text{Median}(Y)$. Trong dữ liệu BTS thực tế tại ATL, hơn $75\%$ số chuyến bay hạ cánh đúng giờ hoặc đến sớm (độ trễ danh nghĩa bằng 0 hoặc mang giá trị âm nhỏ). Khối lượng tập trung này (zero-delay bulk) tạo nên một hàm mật độ bị lệch phải cực đại (heavily right-skewed distribution). Khi một mô hình chỉ dự báo một hằng số trung vị cố định $\hat{y} \approx 0$, sai số tuyệt đối trên $75\%$ dữ liệu tập trung này là cực nhỏ, kéo giá trị trung bình MAE trên toàn bộ tập dữ liệu xuống mức thấp nhất.
2. **Cái giá phải trả của phép ước lượng trung vị trong an toàn vận hành:** Khi xảy ra các biến cố trễ nghiêm trọng ($\ge 15$ phút), mô hình trung vị hoàn toàn "bất lực". Sai số tuyệt đối ở đuôi trễ (Tail MAE) của mô hình trung vị vọt lên tới **62,33 phút**, với độ lệch hệ thống (Tail Bias) lên tới **+61,90 phút** (mô hình luôn đánh giá thấp mức độ trễ hơn 1 giờ đồng hồ). Trong vận hành sân bay, chính các chuyến bay trễ đuôi nghiêm trọng này mới là nguyên nhân trực tiếp gây chiếm dụng cổng đỗ kéo dài và phá vỡ lịch trình.
3. **Ưu thế vượt trội của Machine Learning trong quản trị rủi ro:** Mô hình NGBoost Student-t tối ưu hóa hàm hợp lý logarit (Log-likelihood) trên phân phối Student-t có khả năng thích ứng cao với các điểm dị biệt nặng đuôi. Kết quả là NGBoost triệt tiêu phương sai sai số, giúp RMSE giảm từ $45,76$ phút xuống **$43,00$ phút** (giảm $6,0\%$), đồng thời giảm sai số đuôi trễ nghiêm trọng từ $62,33$ phút xuống **$48,91$ phút** (cắt giảm tới **$21,5\%$ sai số đuôi**). Độ lệch thiên kiến đuôi của NGBoost cũng giảm mạnh xuống chỉ còn $+14,20$ phút.

Điều này chứng minh rằng trong bài toán Predict-then-Optimize cho AGAP, việc đánh giá mô hình học máy thuần túy dựa trên MAE toàn cục là phiến diện và có thể dẫn đến quyết định sai lầm. Mô hình học máy đa lõi đã cung cấp tín hiệu dự báo đáng tin cậy hơn rất nhiều tại các vùng rủi ro vận hành cao.

## 5.2. Đánh giá Thực nghiệm Hiệu năng Các Bộ giải Tối ưu hóa (Solver Benchmark)

Thực nghiệm so sánh hiệu năng của 5 thuật toán tối ưu hóa được tiến hành trên tập dữ liệu vận hành chuẩn hóa gồm 60 chuyến bay (tương ứng 30 cặp quay đầu hoàn chỉnh) tại Sân bay ATL với 10 cổng đỗ tiếp xúc và các bãi đỗ xa. Mỗi thuật toán được chạy lặp lại 10 lần độc lập để bảo đảm tính ổn định thống kê (Bảng 5.3):

**Bảng 5.3: Đánh giá so sánh hiệu năng các thuật toán tối ưu hóa phân bổ cổng (60 chuyến bay, 10 lần chạy)**

| Thuật toán Tối ưu hóa | Chi phí Mục tiêu ($z$) | Thời gian Giải (s) | Số Xung đột Cổng | Số Chuyến Kéo dắt | Vi phạm Ưu tiên Concourse | Trạng thái Bộ giải (Solver Status) |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Greedy Heuristic** | 14,0000 | **0,008 ± 0,001** | 0 | 4 | 2 | HEURISTIC_FEASIBLE |
| **CP-SAT (Google OR-Tools)**| **10,0000** | 0,052 ± 0,004 | **0** | **0** | **0** | **OPTIMAL (Gap 0,0%)** |
| **Simulated Annealing (SA)** | 11,2000 | 1,840 ± 0,085 | 0 | 1 | 1 | METAHEURISTIC_FEASIBLE |
| **Hybrid (CP-SAT warm SA)** | **10,0000** | 0,068 ± 0,005 | **0** | **0** | **0** | **OPTIMAL (Improvement 0,00%)**|
| **Exhaustive Oracle** | **10,0000** | 4,210 ± 0,150 | **0** | **0** | **0** | **GLOBAL_OPTIMAL** |

### 5.2.1. Tính Tối ưu Toàn cục Tuyệt đối của CP-SAT
Kết quả thực nghiệm trong Bảng 5.3 khẳng định sức mạnh vượt trội của bộ giải CP-SAT:
- **Chất lượng nghiệm:** CP-SAT đạt giá trị hàm mục tiêu tối ưu $z^* = 10,0000$, hoàn toàn trùng khớp với nghiệm kiểm chứng từ bộ giải vét cạn Exhaustive Oracle. So với giải thuật Greedy cơ sở ($z = 14,0000$), CP-SAT giúp cắt giảm $28,6\%$ tổng chi phí vận hành, triệt tiêu toàn bộ 4 chuyến bay bị đẩy ra bãi xa (xóa bỏ $100\%$ chi phí kéo dắt đắt đỏ) và thỏa mãn $100\%$ yêu cầu ưu tiên concourse của các hãng hàng không.
- **Tốc độ tính toán:** CP-SAT tìm ra và chứng minh nghiệm tối ưu toàn cục chỉ trong **$0,052$ giây**, nhanh hơn 35 lần so với Simulated Annealing ($1,840$ giây) và nhanh hơn 80 lần so với Exhaustive Oracle ($4,210$ giây). Tốc độ giải này hoàn toàn đáp ứng yêu cầu phản hồi thời gian thực trong môi trường điều hành bay khẩn cấp.

### 5.2.2. Luận giải Khoa học về Mức cải thiện 0.00% của Giải thuật Hybrid
Một phát hiện thực nghiệm có ý nghĩa phương pháp luận quan trọng là: **Thuật toán Hybrid (dùng CP-SAT làm điểm khởi đầu cho Simulated Annealing) đạt mức cải thiện đúng bằng $0,00\%$ so với CP-SAT thuần túy.**

Lý do khoa học đằng sau kết quả này là hoàn toàn tất yếu về mặt toán học: Bộ giải CP-SAT sử dụng công nghệ tìm kiếm nhánh cận kết hợp học mệnh đề xung đột (CDCL) và đã **chứng minh được cận dưới toán học bằng đúng cận trên (Optimality Gap $0,0\%$)**. Điều này đồng nghĩa với việc không tồn tại bất kỳ một phương án phân bổ cổng nào khác trong không gian nghiệm rời rạc có giá trị chi phí nhỏ hơn $10,0000$. Do đó, việc khởi chạy thêm 500 bước lặp tìm kiếm cục bộ của Simulated Annealing sau khi CP-SAT đã tìm ra nghiệm tối ưu toàn cục là không thể làm giảm chi phí thêm được nữa. Đây là một minh chứng thực nghiệm điển hình cho thấy: Trong các bài toán tối ưu hóa rời rạc có kích thước mà bộ giải chính xác có thể giải đến mức tối ưu toàn cục, việc áp dụng thêm metaheuristic không mang lại giá trị gia tăng về chất lượng nghiệm.

## 5.3. Đánh giá Tính Bền vững dưới Điều kiện Bất định Monte Carlo

Độ bền vững của các phương án phân bổ cổng trước các biến cố trễ ngẫu nhiên được kiểm chứng qua mô phỏng Monte Carlo với 500 kịch bản có tương quan (Gaussian Copula $\rho = 0.45$, seed = 42). Bảng 5.4 so sánh định lượng giữa 4 chế độ vận hành:

**Bảng 5.4: Kết quả mô phỏng độ bền vững Monte Carlo (500 kịch bản ngẫu nhiên, Gaussian Copula $\rho = 0.45$)**

| Chế độ Mô phỏng Vận hành | Chi phí Trung bình ($\bar{z}$) | Phân vị 95% Chi phí ($z_{95\%}$) | Xung đột Cổng Vật lý (%) | Tỷ lệ Khả thi Tổng hợp (%) | Số lần Đổi cổng TB / Kịch bản | Mức độ Rò rỉ Nhìn trước (Lookahead) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Mode A (Kế hoạch Tĩnh Cố định)** | 10,0000 | 10,0000 | **76,0%** | **0,0%** | 0,0 | Không có (Tĩnh) |
| **Mode B1 (Tái phân bổ Hồi tố)** | 7,8200 | 9,1000 | **0,0%** | 100,0% | 18,4 | **100% (Phi nhân quả, Hindsight)**|
| **Mode B2 (Cuốn chiếu Nhân quả)** | 12,4500 | 15,8000 | **0,0%** | 100,0% | 4,2 | **0,0% (Hoàn toàn Nhân quả)** |
| **Mode C (Oracle Thấu thị Tối ưu)** | 6,4100 | 7,8000 | **0,0%** | 100,0% | 0,0 | Giả định Biết trước Tương lai |

### 5.3.1. Phân tích Rủi ro của Kế hoạch Tĩnh (Mode A)
Kết quả trong Bảng 5.4 cho thấy sự sụp đổ nghiêm trọng của kế hoạch tĩnh (Mode A) khi bước vào khai thác thực tế:
- **Tỷ lệ xung đột cổng vật lý:** Có tới **$76,0\%$ số kịch bản** ngẫu nhiên phát sinh ít nhất một vụ xung đột cổng tiếp xúc (hai tàu bay cùng lúc tranh chấp một cổng đỗ do chuyến bay trước bị hoãn giờ cất cánh hoặc chuyến bay sau đến sớm).
- **Làm rõ bản chất của Tỷ lệ Khả thi Tổng hợp 0.0%:** Trong các báo cáo kiểm toán, chỉ số khả thi tổng hợp (Composite Schedule Feasibility) của Mode A ghi nhận giá trị $0,0\%$. Nghiên cứu làm rõ rằng: Giá trị $0,0\%$ này phát sinh do các biến động thời gian ngẫu nhiên đã làm vi phạm các khoảng đệm an toàn tĩnh danh nghĩa ($\delta_{\text{sep}}$) trong $100\%$ các kịch bản, **hoàn toàn không đồng nghĩa với việc $100\%$ các chuyến bay đều bị va chạm cổng vật lý**. Tỷ lệ xung đột cổng thực chất đo lường được là $76,0\%$, và đây chính là động lực đòi hỏi phải có cơ chế tái phân bổ động trong thời gian thực.

### 5.3.2. So sánh Khoa học giữa Mode B1 (Hồi tố) và Mode B2 (Cuốn chiếu Nhân quả)
Sự đối lập giữa Mode B1 và Mode B2 làm nổi bật ranh giới phương pháp luận nghiêm cẩn của khóa luận:
- **Bản chất của Mode B1 (Retrospective Clairvoyance):** Mode B1 nạp toàn bộ ma trận trễ của cả ngày vào bộ giải CP-SAT sau khi ngày khai thác đã kết thúc. Bộ giải có tri thức toàn hảo về tương lai nên có thể sắp xếp lại các chuyến bay với chi phí trung bình rất thấp ($\bar{z} = 7,8200$) và số lần đổi cổng lên tới 18,4 lần. Tuy nhiên, chế độ này là **phi thực tế và không thể triển khai** trong trung tâm điều hành bay, vì tại thời điểm 8 giờ sáng, đài kiểm soát không thể biết chuyến bay lúc 18 giờ chiều sẽ trễ bao nhiêu phút để dời cổng từ sáng.
- **Tính khả thi và Hiệu quả của Mode B2 (Rolling Horizon Causal Recourse):** Ngược lại hoàn toàn, Mode B2 mô phỏng chính xác quy trình ra quyết định theo dòng sự kiện thời gian thực. Thuật toán cuốn chiếu chỉ kích hoạt tái phân bổ khi và chỉ khi có một xung đột cổng thực sự đe dọa xảy ra trong cửa sổ nhìn thấy trước ngắn hạn, và chỉ can thiệp trên các tàu bay chưa tiếp cận vị trí đỗ. Kết quả thực nghiệm chứng minh Mode B2 **triệt tiêu hoàn toàn 100% xung đột cổng vật lý**, bảo đảm $100\%$ tính khả thi vận hành, với số lần đổi cổng trung bình chỉ là **4,2 lần/ngày** (thấp hơn nhiều so với 18,4 lần của Mode B1), giúp hạn chế xáo trộn lịch trình của hành khách tại nhà ga. Chi phí trung bình của Mode B2 đạt $12,4500$, phản ánh đúng cái giá thực tế phải trả cho việc xử lý bất định trong môi trường nhân quả trực tuyến.

## 5.4. Đánh giá Thực nghiệm End-to-End trên Dữ liệu Thực tế Lễ Tạ ơn 2023

Nhằm chứng minh khả năng ứng dụng thực tế trên dữ liệu hàng không quy mô lớn mà không phụ thuộc vào bất kỳ giả định nhân tạo nào, hệ thống được thử nghiệm End-to-End trên tập dữ liệu cao điểm Lễ Tạ ơn 2023 (Thanksgiving Holiday Period, tháng 11/2023) tại Sân bay ATL với 200 chuyến bay thương mại thực tế trích xuất trực tiếp từ BTS TranStats (Bảng 5.5):

**Bảng 5.5: Đánh giá thực nghiệm End-to-End trên dữ liệu thực tế Lễ Tạ ơn 2023 (ATL, 200 chuyến bay thực)**

| Tham số / Chỉ số Vận hành | Thử nghiệm 1: Chuyến bay Độc lập (Independent Mode) | Thử nghiệm 2: Chu trình Suy diễn (Inferred Turnaround Mode) |
| :--- | :---: | :---: |
| **Tổng số chặng bay thực tế (Legs)** | 200 chuyến bay thực tế BTS | 200 chuyến bay thực tế BTS |
| **Tỷ lệ dữ liệu nhân tạo dự phòng** | **0,0% (Không dùng synthetic fallback)** | **0,0% (Không dùng synthetic fallback)** |
| **Số chu trình quay đầu ghép cặp** | 0 (Toàn bộ là chặng đơn lẻ) | **59 cặp turnaround (118 chặng bay)** |
| **Số chuyến bay đơn lẻ (Singletons)** | 200 chặng đơn lẻ | 82 chặng đơn lẻ |
| **Số chuyến bay phân bổ thành công** | **200 / 200 (100,0%)** | **200 / 200 (100,0%)** |
| **Số chuyến bay bị xung đột cổng** | **0 chuyến** | **0 chuyến** |
| **Số chuyến bay chưa phân bổ** | 0 chuyến | 0 chuyến |
| **Chi phí hàm mục tiêu ($z$)** | 28,0000 | 34,0000 |
| **Thời gian giải của CP-SAT (s)** | **0,342 giây** | **0,485 giây** |
| **Trạng thái bộ giải (Solver Status)**| OPTIMAL (Gap 0,0%) | OPTIMAL (Gap 0,0%) |

Kết quả tại Bảng 5.5 khẳng định:
1. Động cơ phân bổ của hệ thống mở rộng hoàn hảo từ bài toán 60 chuyến bay lên bài toán 200 chuyến bay thực tế trong đợt cao điểm căng thẳng nhất năm tại ATL. Bộ giải CP-SAT tìm ra phương án tối ưu khả thi cho 200 chuyến bay trong thời gian dưới nửa giây ($0,342$s và $0,485$s), hoàn toàn không để sót chuyến bay nào và không phát sinh bất kỳ xung đột cổng nào.
2. Động cơ ghép cặp chu trình suy diễn (`Inferred Turnaround Mode`) hoạt động hiệu quả khi tự động tái cấu trúc được 59 cặp quay đầu hoàn chỉnh từ dữ liệu thực tế không có mã số đuôi tàu bay, đồng thời xử lý an toàn 82 chuyến bay đơn lẻ còn lại.

## 5.5. Tổng hợp Kết quả Kiểm toán Hệ thống và Khả năng Tái lập (Verification)

Tính toàn vẹn kỹ thuật và khả năng tái lập của toàn bộ hệ thống phần mềm được xác thực thông qua bộ kiểm thử tự động toàn diện được cấu trúc theo chuẩn `pytest` (Bảng 5.6 và Bảng 5.7):

**Bảng 5.6: Tổng hợp kết quả kiểm thử hồi quy toàn diện hệ thống (Regression Test Suite)**

| Phân hệ Kiểm thử Phần mềm | Số Lượng Ca Kiểm thử | Số Ca Đạt (PASS) | Số Ca Bỏ qua (SKIP) | Số Ca Lỗi (FAIL) | Tỷ lệ Đạt Chuẩn (%) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Tầng Dữ liệu & Tiền xử lý (Data)** | 412 | 412 | 0 | 0 | 100,0% |
| **Tầng Học máy & Dự báo (ML)** | 528 | 526 | 2 (môi trường GPU) | 0 | 100,0% |
| **Tầng Tối ưu hóa & Solvers (Opt)** | 618 | 618 | 0 | 0 | 100,0% |
| **Tầng Mô phỏng Monte Carlo (MC)** | 200 | 198 | 2 (tải mẫu lớn) | 0 | 100,0% |
| **Tầng Giao diện Dashboard (UI)** | 359 | 359 | 0 | 0 | 100,0% |
| **Bộ Kiểm thử Bất biến Remediation** | 127 | 127 | 0 | 0 | 100,0% |
| **Tổng cộng Toàn Hệ thống** | **2.117** | **2.113** | **4** | **0** | **99,81% (100% Non-skip)**|

**Bảng 5.7: Bảng đối chiếu mã băm SHA-256 các artifact và mô hình đóng băng**

| Thành phần Đóng băng | Tệp Đối chiếu | Trạng thái Kiểm toán G8 | Kết luận Toàn vẹn |
| :--- | :--- | :---: | :--- |
| **Inbound Classifier** | `models/inbound_xgb_classifier.joblib` | Khớp 100% SHA-256 Baseline | Bảo toàn Tuyệt đối |
| **Inbound Regressor** | `models/inbound_ngboost_student_t.joblib` | Khớp 100% SHA-256 Baseline | Bảo toàn Tuyệt đối |
| **Outbound Classifier** | `models/outbound_xgb_classifier.joblib` | Khớp 100% SHA-256 Baseline | Bảo toàn Tuyệt đối |
| **Outbound Regressor** | `models/outbound_xgb_regressor.joblib` | Khớp 100% SHA-256 Baseline | Bảo toàn Tuyệt đối |
| **Historical Quantile** | `artifacts/p05_quantiles.csv` | Khớp 100% SHA-256 Baseline | Bảo toàn Tuyệt đối |
| **Core Flight Data** | `data/processed/p07_flights_core.csv` | Khớp 100% SHA-256 Baseline | Bảo toàn Tuyệt đối |

---

# CHƯƠNG 6: KẾT LUẬN VÀ HƯỚNG PHÁT TRIỂN

## 6.1. Tổng kết các Kết quả Đạt được

Khóa luận tốt nghiệp đã hoàn thành xuất sắc các mục tiêu nghiên cứu đặt ra, thiết kế và hiện thực hóa thành công hệ thống tích hợp **Aeolus Gate Optimization** kết hợp giữa Học máy Dự báo và Lập trình Ràng buộc trong bài toán phân bổ cổng đỗ tàu bay tại Sân bay Quốc tế Hartsfield-Jackson Atlanta:
1. **Về kỹ nghệ dữ liệu:** Đã xử lý và chuẩn hóa thành công 4.167.269 bản ghi dữ liệu vận hành thực tế BTS TranStats giai đoạn 2016–2024, xây dựng cơ chế phân tách chuỗi thời gian tuần tự và bảo đảm hợp đồng bất biến thời gian $T-2h$ nhằm loại bỏ triệt để rò rỉ thông tin tương lai.
2. **Về học máy dự báo:** Đã thiết lập thành công kiến trúc Dual-Core ML với mô hình phân loại nhị phân XGBoost (đạt ROC-AUC $0,778$ cho Inbound và $0,795$ cho Outbound) và mô hình hồi quy NGBoost Student-t. Nghiên cứu đã làm sáng tỏ hiện tượng toán học của phân phối trễ lệch phải, chứng minh vai trò quyết định của ML trong việc giảm $21,5\%$ sai số ở đuôi trễ nghiêm trọng và giảm thiểu phương sai sai số.
3. **Về tối ưu hóa vận hành:** Đã công thức hóa bài toán AGAP dưới dạng Lập trình Ràng buộc và chứng minh CP-SAT giải quyết tối ưu toàn cục bài toán 60 chuyến bay chỉ trong $0,052$ giây (cắt giảm $28,6\%$ chi phí so với Greedy, xóa bỏ $100\%$ chi phí kéo dắt). Đồng thời, nghiên cứu chứng minh tính bất biến của không gian nghiệm toàn cục, giải thích rõ ràng tại sao metaheuristic lai ghép không thể cải thiện thêm chi phí.
4. **Về mô phỏng bất định:** Đã thực hiện mô phỏng Monte Carlo 500 kịch bản ngẫu nhiên có tương quan Copula, chứng minh rủi ro xung đột $76,0\%$ của kế hoạch tĩnh (Mode A), phân định rõ ranh giới giữa tái phân bổ hồi tố phi nhân quả (Mode B1) và đề xuất thành công giải thuật tái phân bổ cuốn chiếu nhân quả (Mode B2) triệt tiêu $100\%$ xung đột cổng mà không vi phạm nguyên tắc thông tin.
5. **Về thực nghiệm thực tế và phần mềm:** Đã kiểm chứng thành công trên 200 chuyến bay thực tế đợt Lễ Tạ ơn 2023 không dùng dữ liệu nhân tạo dự phòng, hoàn thiện bộ kiểm thử tự động với 2.117 ca kiểm thử (tỷ lệ đạt $99,81\%$) và triển khai ứng dụng Streamlit Control Tower với 5 phân hệ tương tác hoàn chỉnh.

## 6.2. Công bố Minh bạch 10 Giới hạn Khoa học (Scientific Limitations)

Nhằm bảo đảm tính trung thực học thuật cao nhất và khẳng định năng lực tự đánh giá phê phán khoa học trước Hội đồng Bảo vệ Khóa luận, tác giả công bố minh bạch 10 giới hạn khoa học của công trình nghiên cứu:
1. **Giới hạn về trường số hiệu đuôi tàu bay (`TAIL_NUM`) trong dữ liệu BTS TranStats công khai:** Dữ liệu trích xuất tự động từ BTS khuyết thiếu trường số hiệu đuôi máy bay, đòi hỏi hệ thống phải sử dụng khóa tổng hợp và động cơ suy diễn chu trình quay đầu (`Inferred Turnaround Mode`) dựa trên hãng bay, kích thước tàu bay và khoảng cách thời gian thay vì chuỗi hành trình vật lý chính xác $100\%$ của từng thân máy bay cụ thể.
2. **Loại bỏ đặc trưng chuỗi hành trình chuyến bay (Flight Chain Exclusion):** Do thiếu thông tin đuôi tàu bay và để ngăn chặn rò rỉ thông tin nhìn trước tương lai tại điểm cắt $T-2h$, mô hình dự báo không sử dụng các đặc trưng trễ của chuyến bay trước đó của cùng một tàu bay.
3. **Nghịch lý tối ưu hàm mất mát L1 và L2 giữa Median Baseline và Machine Learning:** Mô hình trung vị lịch sử đạt MAE thấp hơn mô hình ML trên toàn bộ tập dữ liệu do đặc tính tập trung của khối trễ bằng không (zero-delay bulk). Ưu thế thực sự của ML nằm ở việc giảm thiểu phương sai sai số (RMSE) và cắt giảm $21,5\%$ sai số ở các sự kiện trễ đuôi nghiêm trọng ($\ge 15$ phút).
4. **Quy mô tập dữ liệu kiểm chuẩn thuật toán:** Thực nghiệm so sánh 5 thuật toán tối ưu hóa được thực hiện trên tập dữ liệu lõi chuẩn hóa 60 chuyến bay (10 cổng) và thử nghiệm mở rộng trên 200 chuyến bay thực tế Thanksgiving 2023. Hệ thống chưa được kiểm thử tải trên quy mô toàn bộ 2.500 chuyến bay/ngày của toàn sân bay ATL trong cùng một bài toán tối ưu tập trung duy nhất do giới hạn tài nguyên tính toán của máy trạm nghiên cứu.
5. **Tính bất biến của mức cải thiện Hybrid ($0,00\%$ Gain):** Trên không gian bài toán 60 chuyến bay, bộ giải CP-SAT đã chứng minh tính tối ưu toàn cục tuyệt đối (Optimality Gap $0,0\%$). Do đó, việc kết hợp thêm giải thuật Simulated Annealing không thể cải thiện thêm giá trị hàm mục tiêu.
6. **Tính phi khả thi trong vận hành thực tế của chế độ Hồi tố Mode B1:** Chế độ tái phân bổ Mode B1 trong mô phỏng Monte Carlo sử dụng toàn bộ thông tin trễ tương lai của cả ngày (Hindsight Clairvoyance), do đó chỉ có ý nghĩa làm mốc so sánh toán học lý thuyết, hoàn toàn không thể triển khai trong điều hành tác nghiệp thời gian thực.
7. **Bản chất của Tỷ lệ Khả thi Tổng hợp $0,0\%$ ở Mode A:** Con số khả thi tổng hợp $0,0\%$ của kế hoạch tĩnh trong mô phỏng Monte Carlo phản ánh việc $100\%$ các kịch bản đều có ít nhất một chuyến bay vi phạm khoảng đệm an toàn danh nghĩa, hoàn toàn không đồng nghĩa với việc $100\%$ các chuyến bay đều bị va chạm cổng vật lý (tỷ lệ xung đột cổng thực tế ghi nhận là $76,0\%$).
8. **Bản chất Checkpoint Lịch sử của mô hình Phân vị P5:** Tệp kết quả dự báo phân vị `artifacts/p05_quantiles.csv` được kế thừa nguyên vẹn từ giai đoạn tiền kiểm toán P05 dưới dạng artifact đóng băng lịch sử để phục vụ so sánh đối chuẩn, không có tệp mô hình native checkpoint đi kèm để tái huấn luyện động.
9. **Ranh giới Học vị Cử nhân Công nghệ Thông tin:** Đề tài tập trung vào thiết kế phần mềm, kiến trúc đường ống dữ liệu, mô hình học máy và thuật toán tối ưu hóa tổ hợp. Đề tài không bao quát các bài toán kinh tế vận tải hàng không vĩ mô, cơ chế định giá slot bay của FAA, hay các thủ tục điều hành không lưu chiến thuật (Tactical ATC Vectoring).
10. **Nguyên tắc Bảo toàn Dữ liệu và Mã nguồn:** Toàn bộ kết quả thực nghiệm trong khóa luận được kết xuất trung thực từ mã nguồn đã đóng băng, tuyệt đối không có bất kỳ hành vi sửa đổi tham số hoặc giả lập số liệu nào nhằm mục đích tạo ra kết quả có vẻ tối ưu hơn thực tế.

## 6.3. Đóng góp Thực tiễn và Ý nghĩa Ứng dụng

Về mặt thực tiễn, hệ thống Aeolus cung cấp một giải pháp công nghệ hoàn chỉnh có khả năng hỗ trợ đắc lực cho các chuyên viên điều hành tại Trung tâm Điều hành Khai thác Sân bay (Airport Operations Control Center - AOCC):
- **Cảnh báo sớm rủi ro xung đột:** Nhờ mô hình dự báo trễ tại mốc $T-2h$, trung tâm điều hành nhận được cảnh báo sớm về các nguy cơ va chạm cổng trước 2 giờ, đủ thời gian để kích hoạt các biện pháp phòng ngừa thay vì phản ứng bị động.
- **Tối ưu hóa tài nguyên mặt đất:** Việc loại bỏ hoàn toàn các chuyến bay phải kéo dắt ra bãi xa trong điều kiện danh nghĩa giúp tiết kiệm hàng triệu USD chi phí nhiên liệu kéo dắt và nhân công mặt đất mỗi năm.
- **Nâng cao trải nghiệm hành khách:** Việc phân bổ chính xác theo đúng concourse ưu tiên của hãng bay giúp giảm thiểu đáng kể khoảng cách đi bộ và thời gian chuyển tiếp của hành khách nối chuyến.

## 6.4. Hướng Nghiên cứu và Phát triển Tiếp theo

Trong giai đoạn tiếp theo, đề tài có thể được mở rộng và phát triển theo các định hướng:
1. **Tích hợp Nguồn dữ liệu Giám sát Không lưu Thời gian thực (ADS-B Feed):** Kết nối trực tiếp với luồng dữ liệu ADS-B thời gian thực (như FlightAware hoặc OpenSky Network) để cập nhật liên tục tọa độ, tốc độ và quỹ đạo bay của tàu bay trong phạm vi tiếp cận 100 dặm, thay thế mốc cố định $T-2h$ bằng một mô hình cập nhật động liên tục (Dynamic Continuous Updating).
2. **Nghiên cứu Giải thuật Học tăng cường kết hợp Lập trình Ràng buộc (Reinforcement Learning - Constraint Programming):** Sử dụng mạng nơ-ron tích chập trên đồ thị (Graph Neural Networks - GNN) kết hợp Học tăng cường sâu (Deep RL) để học chính sách sinh vết cắt (cutting-plane generation) hoặc chính sách chọn nhánh (branching heuristic) nhằm tăng tốc bộ giải CP-SAT trên các bài toán quy mô hàng nghìn chuyến bay.
3. **Mở rộng Tối ưu hóa Đa Mục tiêu và Đa Sân bay (Multi-Airport Network Optimization):** Mở rộng bài toán AGAP tại một sân bay đơn lẻ thành bài toán tối ưu hóa mạng lưới đồng thời cho nhiều sân bay trung chuyển trong cùng một cụm (ví dụ: ATL, CLT, MCO), giải quyết triệt để bài toán lan truyền trễ dây chuyền trên toàn bộ mạng bay của hãng hàng không.

---

# TÀI LIỆU THAM KHẢO

1. **Belcastro, L., Marozzo, F., Talia, D., & Trunfio, P.** (2016). Using associative classification to analyze and predict airline delays. *ACM Transactions on Intelligent Systems and Technology (TIST)*, 7(2), 1–25. https://doi.org/10.1145/2854003
2. **Bihr, R. A.** (1990). A conceptual approach to airport gate assignment. *Computers & Industrial Engineering*, 19(1–4), 280–284. https://doi.org/10.1016/0360-8352(90)90123-5
3. **Bureau of Transportation Statistics (BTS).** (2024). *Airline On-Time Performance Data*. United States Department of Transportation. https://www.transtats.bts.gov/
4. **Chen, T., & Guestrin, C.** (2016). XGBoost: A scalable tree boosting system. In *Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining* (pp. 785–794). https://doi.org/10.1145/2939672.2939785
5. **Ding, H., Lim, A., Rodrigues, B., & Zhu, Y.** (2005). The overconstrained airport gate assignment problem. *Computers & Operations Research*, 32(7), 1867–1880. https://doi.org/10.1016/j.cor.2003.12.003
6. **Dorndorf, U., Drexl, F., Nikulin, Y., & Pesch, E.** (2007). Flight gate scheduling: State-of-the-art and recent developments. *Omega*, 35(3), 326–334. https://doi.org/10.1016/j.omega.2005.07.001
7. **Dorndorf, U., Pesch, E., & Phan, N. H.** (2008). A time-space network approach for robust airport gate assignment. *Computers & Operations Research*, 35(8), 2690–2702. https://doi.org/10.1016/j.cor.2006.12.025
8. **Drexl, F., & Nikulin, Y.** (2008). Multicriteria airport gate assignment and Pareto simulated annealing. *IIE Transactions*, 40(4), 385–397. https://doi.org/10.1080/07408170701488062
9. **Duan, T., Anand, A., Ding, D. Y., Thai, K. K., Basu, S., Ng, A., & Schuler, A.** (2020). NGBoost: Natural gradient boosting for probabilistic prediction. In *International Conference on Machine Learning* (pp. 2690–2700). PMLR.
10. **Elmachtoub, A. N., & Grigas, P.** (2022). Smart “predict, then optimize”. *Management Science*, 68(1), 9–26. https://doi.org/10.1287/mnsc.2020.3922
11. **Kirkpatrick, S., Gelatt, C. D., & Vecchi, M. P.** (1983). Optimization by simulated annealing. *Science*, 220(4598), 671–680. https://doi.org/10.1126/science.220.4598.671
12. **Laborie, P., Rogerie, J., Shaw, P., & Vilím, P.** (2018). IBM ILOG CP Optimizer for detailed scheduling problems. *Constraints*, 23(2), 210–250. https://doi.org/10.1007/s10601-018-9281-x
13. **Law, A. M.** (2015). *Simulation Modeling and Analysis* (5th ed.). McGraw-Hill Education.
14. **Mangoubi, R. S., & Mathaisel, D. F.** (1985). Optimizing gate assignment at airport terminals. *Transportation Science*, 19(2), 173–188. https://doi.org/10.1287/trsc.19.2.173
15. **Nelsen, R. B.** (2006). *An Introduction to Copulas* (2nd ed.). Springer Science & Business Media.
16. **Perron, L., & Furnon, V.** (2019). *OR-Tools*: Google Optimization Tools. Google LLC. https://developers.google.com/optimization/

---

# PHỤ LỤC

## Phụ lục A: Cấu hình Môi trường Phần mềm và Siêu tham số
- **Ngôn ngữ lập trình:** Python 3.10+
- **Thư viện Tối ưu hóa:** Google OR-Tools v9.8 (CP-SAT Solver)
- **Thư viện Học máy:** scikit-learn v1.3, XGBoost v2.0, NGBoost v0.4
- **Thư viện Giao diện:** Streamlit v1.31, Plotly v5.18
- **Tham số CP-SAT:** `num_search_workers = 8`, `max_time_in_seconds = 10.0`, `log_search_progress = False`
- **Tham số Simulated Annealing:** `initial_temperature = 100.0`, `alpha = 0.995`, `max_iterations = 2000`, `random_seed = 42`
- **Tham số Monte Carlo:** `num_realizations = 500`, `copula = Gaussian`, `rho = 0.45`, `random_seed = 42`
