# Nội dung slide bảo vệ dùng bộ số liệu đã đối soát

Nội dung Markdown để dựng slide ở giai đoạn tài liệu cuối. Chưa có PPTX hoặc nghiệm thu hình thức. Các đề nghị khác phạm vi còn chờ GVHD. Bảng số liệu lấy từ 05_results.md; không tái dùng số của G9 cũ.

## Slide 1 Đề tài và nhóm thực hiện

Tên đề CNTT-KLCN168 theo đề gốc. Nhóm tự kiểm tra tên, MSSV, GVHD và phân công thực tế khi dựng slide.

## Slide 2 Bài toán

Chuyến bay trễ có thể làm thay đổi khoảng chiếm dụng cổng. Mục tiêu là hỗ trợ quyết định trên sân bay mô phỏng, đánh giá xung đột và điểm chi phí.

## Slide 3 Yêu cầu và phạm vi

Đề yêu cầu ML, Optuna, CP-SAT, SA, so sánh solver, MC500 và dashboard. Quy mô nghiệm thu 20–50 cổng/100–300 chuyến; demo lớn là phần mở rộng.

## Slide 4 Kiến trúc

Predict → Simulate → Optimize → Evaluate. Streamlit giữ kịch bản; web hỗ trợ upload. Historical replay và native inference được ghi nhãn riêng.

## Slide 5 Dữ liệu và thời gian

Cutoff CRS_DEP_TIME − 2h; delay ≥15 phút cho classification, phút có dấu cho regression. Tách rolling OOF, selection 2023 và hậu kiểm 2024 lịch sử.

## Slide 6 Mô hình và các khác biệt với đề

LR, RF, XGBoost có các bằng chứng theo task. Weighted Ensemble hiện có chưa được gọi là Stacking. Weather/Chain và vai trò NGBoost arrival đang trình GVHD.

## Slide 7 Phân loại departure

N=332.734, threshold=0,5. Calibrated XGBoost: ROC-AUC 0,64289; PR-AUC 0,32915; Brier 0,15637. Precision 0,49262; Recall 0,04862; F1 0,08851. Công bố rõ Recall thấp.

## Slide 8 Hồi quy departure và OOF arrival

Departure XGBoost: MAE 17,60169 phút; RMSE 43,00055 phút. Arrival baseline subset N=16.000 khác full tuned OOF N=1.254.518. Dùng bảng riêng pooled/macro, không vẽ biểu đồ gain giữa hai population khác nhau.

## Slide 9 Optuna và SHAP

Hai study XGBoost arrival có 10 COMPLETE trials/study, best trials số 1 và 6 theo quy ước zero-based. TreeSHAP departure trên 1.000 mẫu có kiểm tra tính cộng, không giải thích nhân quả hoặc flight upload mới.

## Slide 10 Mô hình tối ưu

Trình bày assignment, tài nguyên hữu hạn và khoảng chiếm dụng có buffer. Điểm chi phí phải gắn đúng trọng số. Phân biệt FEASIBLE, OPTIMAL, UNKNOWN và INFEASIBLE.

## Slide 11 So sánh thuật toán

Dùng bảng G5 được tổng hợp lại trong 05_results.md. Công bố runtime và giới hạn ngân sách. Không tuyên bố Hybrid luôn tốt hơn CP-SAT hoặc tất cả run là optimum.

## Slide 12 Thiết kế Monte Carlo

Official MC500: 500 realizations, 5.500 slots; 25 contact gates và remote theo manifest nguồn. Marginals/copula là cấu hình mô phỏng. Tách A, B1 hồi cứu, B2 online causal, C1 heuristic foresight và C2 CP-SAT foresight.

## Slide 13 Kết quả Monte Carlo

Mode A khả thi 25,2% với mỗi initial solver, B2 500/500. C2: 499 OPTIMAL và 1 FEASIBLE. A−B2 trung bình 1.329,68 điểm; B2−C2 là khoảng cách chính sách–foresight 19,10 điểm, không phải EVPI lý thuyết.

## Slide 14 Dữ liệu thật và đơn vị đếm

G4 strict native: 200 legs, không có verified rotations trong run đó. Replay 2026: 1.500 movements, 750 occupancies, 150 contact gates mô phỏng. Đơn vị không hoán đổi.

## Slide 15 Demo

Upload raw có sẵn → chọn ngày/cấu hình → inference → phân cổng → Gantt → xuất kết quả. Hiển thị nguồn, model, trạng thái và assumptions. Chuẩn bị snapshot/ZIP dự phòng.

## Slide 16 Giới hạn

Chưa chứng nhận tại sân bay thật; giới hạn tail/rotation, tồn đầu ngày và sức chứa. MC web recourse là hồi cứu, khác B2 chính thức. UI QA và các quyết định GVHD còn phải hoàn tất.

## Slide 17 Kết luận

Có pipeline mô phỏng và nhiều bằng chứng tính lại được. Kết luận trong đúng phạm vi dữ liệu và cấu hình. Trình bày các quyết định phạm vi đã thực sự được xác nhận khi có biên bản; không tự ghi đã nghiệm thu toàn bộ đề.
