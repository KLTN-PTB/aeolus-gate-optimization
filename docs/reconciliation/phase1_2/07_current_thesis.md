# Nội dung hợp nhất cho báo cáo Aeolus

Nội dung này dùng để tiếp tục biên tập khóa luận CNTT-KLCN168 theo kết quả đối soát ngày 19/10/2026. Các bảng chi tiết và nguồn nằm trong [kết quả hiện hành](05_results.md). Các đề nghị thay đổi phạm vi chưa được GVHD phê duyệt; đây chưa phải quyển Word/PDF cuối theo mẫu trường.

## Tóm tắt tiếng Việt

Đề tài xây dựng hệ thống hỗ trợ quyết định phân và tái phân bổ cổng trên môi trường sân bay mô phỏng ATL, theo chu trình dự báo, mô phỏng khoảng chiếm dụng, tối ưu hóa và đánh giá. Dự báo được xây dựng từ các đặc trưng lịch bay, lịch, hãng và tuyến được cho phép trong hợp đồng thời gian. Cấu hình hiện hành dùng CRS_DEP_TIME trừ hai giờ làm cutoff; nhãn trễ là delay từ 15 phút, hồi quy giữ độ trễ có dấu.

Bằng chứng ML được báo cáo theo từng tác vụ và tập đánh giá. Trên 332.734 lượt departure thuộc selection 2023, calibrated XGBoost classifier đạt ROC-AUC 0,64289, PR-AUC 0,32915 và Brier 0,15637; tại threshold 0,5, Precision 0,49262, Recall 0,04862 và F1 0,08851. Recall thấp ở ngưỡng này là giới hạn cần công bố, không thể thay bằng AUC để mô tả khả năng phát hiện trễ nặng. XGBoost regressor cùng population có MAE 17,60169 phút và RMSE 43,00055 phút. Arrival có các bộ OOF riêng; không thay kết quả departure cho arrival.

Hệ thống có Greedy, CP-SAT, SA và Hybrid, cùng kiểm tra ràng buộc độc lập. Official MC500 bao gồm 500 kịch bản và 5.500 lượt đánh giá, sử dụng các marginal và copula được cấu hình cho mô phỏng. Mode A có 25,2% lượt khả thi theo từng initial solver; B2 có 500/500 khả thi trong tập khảo sát. Foresight C2 có 499 nghiệm được chứng minh tối ưu và một nghiệm khả thi. Đây là bằng chứng trên mô phỏng, không đo hiệu quả tại sân bay thật.

Các phần mở rộng gồm NGBoost Student-t arrival và dashboard React/FastAPI bên cạnh Streamlit. Khác biệt với đề, đặc biệt Flight Chain, Weather, Stacking và vai trò XGBoost, được trình GVHD để xác nhận. Các bảng ablation chưa có prediction-level evidence không được dùng làm kết luận thực nghiệm.

## Abstract

This thesis implements a predict–simulate–optimize–evaluate system for gate assignment in a controlled ATL airport simulation. Forecasting results are reported separately by prediction task, temporal split, sample population and aggregation method. On 332,734 departure observations from the 2023 selection partition, the calibrated XGBoost classifier has ROC-AUC 0.64289, average precision 0.32915 and Brier score 0.15637. At threshold 0.5 its recall is 0.04862. These figures describe the stored evaluation population and do not establish prospective operational performance.

The native application combines a stored NGBoost Student-t arrival checkpoint with a departure XGBoost regressor, then synthesizes occupancy intervals and applies finite-capacity optimization. The official 500-scenario experiment contains 5,500 evaluation slots with configured marginal distributions and a Gaussian copula. It is distinct from the uploaded-data web experiment, whose recourse is retrospective. Scope changes remain subject to advisor review. No real-airport deployment certification or universal algorithmic superiority is claimed.

## Chương 1 Bài toán và phạm vi

Mục tiêu gốc là kết hợp ML và lập trình ràng buộc để hạn chế xung đột cổng, đánh giá chi phí quyết định và minh họa trên dashboard. Đối tượng nghiệm thu là hệ thống mô phỏng trên tập con Aeolus theo sân bay/thời gian, với quy mô nêu trong đề là 20–50 cổng và 100–300 chuyến/ngày.

Phạm vi thực tế phải phân biệt dữ liệu nghiên cứu Aeolus, các bộ kịch bản tổng hợp, native pilot và dữ liệu BTS 2026 phục vụ replay/upload. Có thêm demo quy mô lớn không tự chứng minh mọi yêu cầu trong đề đã hoàn tất. Ma trận 35 hạng mục bao gồm cả các yêu cầu quy trình và sản phẩm báo cáo.

## Chương 2 Cơ sở phương pháp và nghiên cứu liên quan

Các thành phần gồm Logistic Regression và Random Forest làm baseline, XGBoost classification/regression, tối ưu siêu tham số bằng Optuna, CP-SAT, SA, Hybrid và mô phỏng Monte Carlo. Weighted Ensemble hiện có được mô tả theo cơ chế trọng số; Stacking cần meta learner trên dự báo ngoài mẫu và chưa có bằng chứng tương đương trong repo.

Các nguồn tham khảo gốc được giữ trong 12_references.md. Phần tổng quan cuối phải gắn mỗi nhận định với bài thực sự được đọc; đợt này chưa xác minh trực tuyến toàn bộ thông tin thư mục. Kết quả nội bộ của dự án không được gán thành kết luận của tài liệu trích dẫn.

## Chương 3 Dữ liệu và mô hình dự báo

Các tác vụ arrival/departure có target và feature contract riêng. Chỉ dùng predictors được cho phép tại cutoff; actual delay dùng để đánh giá, không đi vào inference. Tiền xử lý phải fit trong train tương ứng.

Rolling development có các validation year 2019–2022. Selection 2023 phục vụ chọn/đánh giá theo giao thức được lưu. Một số kết quả 2024 đã được truy cập trong các đợt hậu kiểm lịch sử; không gọi 2024 là untouched holdout của toàn dự án. Đợt đối soát hiện tại không đọc dòng raw/processed 2024 và không điều chỉnh mô hình theo kết quả năm đó.

Các nhánh arrival baseline trong bảng P08 dùng 16.000 dòng từ bốn fold. Script cũ gộp các dòng rồi tính metric nhưng ghi nhãn macro. Bản hiện tại giữ riêng pooled và trung bình metric từng fold. XGBoost tuned có 1.254.518 dòng OOF; pooled ROC-AUC là 0,61768 và macro ROC-AUC là 0,61933. Pooled MAE là 19,40800 phút và macro MAE là 19,19011 phút. Chưa có đối chiếu cùng population thì không phát biểu phần trăm tăng so với baseline subset.

Hai study Optuna XGBoost arrival có 10 trial COMPLETE mỗi study; best classification trial số 1 tối đa hóa macro PR-AUC, best regression trial số 6 tối thiểu hóa macro MAE. Số trial dùng quy ước zero-based trong SQLite. Bằng chứng này chưa xác nhận departure checkpoint đang phục vụ được huấn luyện bằng cùng study.

Departure classifier XGBoost được calibration sigmoid; LR dùng isotonic. Phép sigmoid((predicted_delay−15)/10) áp lên regressor trong P08 là heuristic, không phải đầu ra của classifier hoặc xác suất đã được hiệu chuẩn. ROC-AUC 0,67219 của heuristic này không thay thế ROC-AUC classifier 0,64289.

Flight Chain và Weather còn thiếu bằng chứng point-in-time cho các feature dự kiến. Các bảng B/C ghi cứng không chứng minh độ cải thiện hoặc ablation đã hoàn tất. Báo cáo giữ kết quả kiểm toán khả dụng và đề nghị GVHD xác nhận cách đáp ứng yêu cầu gốc. Không suy diễn mọi nguồn weather là một loại METAR hoặc tự tạo lags để hợp thức hóa dữ liệu.

## Chương 4 Mô phỏng tối ưu và ứng dụng

Native pipeline kiểm tra hash checkpoint và quyền model trong registry, dự báo hai chiều, ghép cặp và dựng các khoảng chiếm dụng cổng. Với turnaround có hai chặng, thời điểm rời cổng được bảo vệ bởi giá trị lớn hơn giữa departure dự báo và arrival mô phỏng cộng thời gian quay đầu tối thiểu; buffer được cộng một lần.

Checkpoint arrival hiện deserialize thành B5NGBoostStudentT, ID b5_ngboost_student_t có trạng thái legacy_frozen và quyền downstream. ID P4_ngboost_student_t trong registry là research_candidate, downstream_eligible=false. Tên khoa học P4 trong báo cáo cũ phải được đối chiếu với lineage checkpoint; không nâng quyền hoặc đổi nhãn để khớp văn bản.

CP-SAT, SA và Hybrid giải bài toán theo objective và giới hạn của cấu hình cụ thể. Khi CP-SAT đã chứng minh optimum của cùng bài toán, SA không tìm được giá trị thấp hơn optimum đó; điều này không chứng minh Hybrid luôn bằng CP-SAT trong mọi run có ngân sách hữu hạn. Bảng G5 giữ kết quả thật theo từng solver và không suy ra equal wall-clock chỉ từ việc dùng cùng scenario hash.

Web dùng objective 10 × số tái phân bổ + 200 × lượt bãi xa trong snapshot thí nghiệm. Cổng danh định được dựng bằng Greedy trên lịch mô phỏng; không phải mã cổng thực tế. Chi phí là điểm mô hình, không phải tiền; phân cổng không tự làm thay đổi ML delay đã dự báo.

Streamlit là giao diện nằm trong lựa chọn công nghệ của đề; React/FastAPI là mở rộng. Historical replay dùng actual timestamps để nghiên cứu phân cổng hồi cứu. Có TAIL_NUM trong raw không tự xác thực rotation trước cutoff hoặc xác nhận lịch điều hành của hãng. Native pilot strict 200 legs không được mô tả là 200 vòng quay đầu đã xác thực.

## Chương 5 Kết quả và đánh giá

Các bảng ở 05_results.md được sinh từ prediction-level data và ledger, có nguồn và hash đi kèm. Classifier departure được đánh giá bằng ROC-AUC, average precision, Brier, ECE, Precision, Recall và F1 trên cùng 332.734 dòng. Báo cáo cả threshold và class prevalence để người đọc hiểu khả năng phát hiện thực tế.

Hồi quy departure XGBoost có RMSE thấp hơn median đã lưu trong cùng tập, nhưng MAE cao hơn. Đây là mô tả thực nghiệm cụ thể. Median là nghiệm tối ưu L1 trong một bài toán xác định không có nghĩa mọi median baseline hợp lệ phải thắng mọi conditional model; baseline median lấy từ nhãn đánh giá còn có giới hạn fit trên eval. Bản hiện tại không dùng median P08 arrival làm đối chứng triển khai hợp lệ.

TreeSHAP được tính lại trên 1.000 mẫu departure 2023, đúng checkpoint và preprocessor. Sai số cộng tối đa khoảng 0,0000062 phút; importance khớp mức làm tròn của bảng đã lưu. Đây là attribution trong không gian hồi quy phút, không phải tác động nhân quả hoặc giải thích cho flight upload mới.

Official MC500 dùng Gaussian copula rho=0,45, arrival Student-t df=4,5/loc=5/scale=18 và departure Student-t df=4/loc=8/scale=22 theo manifest. Chúng là phân phối cấu hình cho mô phỏng; không gán thành tham số native ML đã dự báo cho từng chuyến.

Với mỗi initial solver của Mode A, 126/500 kịch bản khả thi, tổng 682 contact overlaps và không có buffer violation theo các cột raw. B1, B2, C1, C2 có 500/500 khả thi trong tập tương ứng. C2 gồm 499 OPTIMAL và 1 FEASIBLE. Không coi mọi lượt khả thi là đã được chứng minh tối ưu.

Trên initial plan Greedy và cùng realization hash, chi phí A−B2 trung bình 1.329,68 điểm, khoảng tin cậy Student t 95% [1.229,91249; 1.429,44751]. B2−C2 trung bình 19,10 điểm, CI [15,93198; 22,26802]. Khoảng cách thứ hai là policy-to-foresight gap thực nghiệm, không được gắn nhãn formal EVPI.

Monte Carlo trên web lấy mẫu arrival độc lập, giữ departure point prediction và phân cổng lại khi biết toàn bộ kịch bản ngày. Đây là recourse hồi cứu; kết quả không thay thế hoặc nhân rộng kết luận causal B2 chính thức.

## Chương 6 Kết luận và việc cần hoàn tất

Dự án đã có các thành phần ML, tối ưu, mô phỏng, lưu trữ và trình diễn, cùng bằng chứng có thể tính lại cho nhiều chỉ số. Hai giai đoạn hiện tại tạo hồ sơ đối chiếu và nội dung khoa học thống nhất hơn; không tự chứng nhận đề đã hoàn thành.

Các hạng mục còn chờ gồm quyết định GVHD cho các khác biệt phương pháp, bằng chứng Stacking/ablation hoặc điều chỉnh phạm vi được chấp nhận, truy vết model identity/HPO deployment, UI QA, G13, tài liệu cuối và diễn tập. Giới hạn về tài nguyên, vận hành thật và dữ liệu phải được giữ trong phần phương pháp và khi trả lời phản biện.
