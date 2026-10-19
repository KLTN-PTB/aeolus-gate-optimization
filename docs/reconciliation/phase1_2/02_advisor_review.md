# Bản đối chiếu phạm vi trình giảng viên hướng dẫn

Kính gửi Thầy Phùng Thế Bảo và Thầy Nguyễn Huy Liêm,

Nhóm thực hiện đề CNTT-KLCN168 đã xây dựng pipeline dự báo và tối ưu phân cổng trên môi trường mô phỏng, lưu mô hình, thí nghiệm và dashboard. Bản đối chiếu này trình bày những khác biệt cần xin ý kiến trước khi chốt nội dung khóa luận. **Các kiến nghị dưới đây đang chờ xác nhận, chưa phải quyết định của GVHD.**

## Các nội dung đề nghị xác nhận

| Mã | Yêu cầu và hiện trạng | Kiến nghị của nhóm | Căn cứ và điều kiện xử lý |
|---|---|---|---|
| DEV-01 | Đề có Weather và so sánh Tabular + Flight Chain. Pipeline chính chỉ dùng đặc trưng đã được cho phép; thiếu chứng cứ khả dụng cho Chain/Weather tại cutoff. Bảng ablation B/C hiện là hằng số trong script. | Chấp nhận báo cáo kiểm toán tính khả dụng và giới hạn dữ liệu; chưa coi là hoàn tất thực nghiệm ablation định lượng. | R10, R11; nếu GVHD yêu cầu ablation, lập thực nghiệm mới chỉ sau khi có dữ liệu/đặc trưng hợp lệ. Không dùng số ghi cứng làm kết quả. |
| DEV-02 | Đề nêu Stacking Ensemble; registry hiện có Weighted Ensemble theo trọng số. | Xin xác nhận mô hình ensemble hiện có đủ làm đối chứng hay phải bổ sung Stacking. | R05; hai phương pháp có cơ chế khác nhau. Nếu yêu cầu bổ sung, dùng OOF temporal để huấn luyện meta learner, ngoài hai giai đoạn hiện tại. |
| DEV-03 | Đề mô tả pipeline XGBoost → CP-SAT/SA. Luồng native hiện dùng arrival b5_ngboost_student_t và departure XGBoost Regressor. Tên P4 trong báo cáo lịch sử không trùng trạng thái registry hiện hành. | Chấp nhận NGBoost như phần mở rộng dự báo arrival, giữ bằng chứng XGBoost theo đúng tác vụ và lập bản đối chiếu model rõ ràng. | R04, R19; nếu không chấp nhận, thiết kế pipeline đối chứng XGBoost riêng, không thay checkpoint đóng băng. |
| DEV-04 | Đề yêu cầu SA cải thiện tiêu chí mềm. Benchmark hiện không chứng minh Hybrid luôn tốt hơn CP-SAT; một số trường hợp CP-SAT đã tối ưu. | Nghiệm thu việc cài đặt và đánh giá trung thực, không đặt yêu cầu tăng dương ở mọi trường hợp. | R14; so sánh cùng mục tiêu và ngân sách được công bố. Tính tối ưu chỉ áp dụng đúng model/objective đã giải. |
| DEV-05 | Đề chỉ ra tổng chi phí do trễ và tái phân bổ. Web hiện tối ưu điểm tái phân bổ/bãi xa; delay_weight bằng 0 trong cấu hình web. | Xác nhận cách trình bày mục tiêu là giảm xung đột và chi phí quyết định mô phỏng. | R16; không quy đổi thành tiền hoặc tuyên bố bộ giải giảm độ trễ đã dự báo. Nếu cần delay-aware decision, lập bài toán thay đổi riêng. |
| DEV-06 | Đề chọn Streamlit/Plotly Dash. Repo giữ Streamlit và bổ sung React/FastAPI. | Giữ Streamlit trong hồ sơ đáp ứng đề; web là giao diện mở rộng và có thể dùng trình diễn nếu được chấp nhận. | R20; nghiệm thu trực quan trên trình duyệt và máy chiếu vẫn thuộc giai đoạn tiếp theo. |
| DEV-07 | Đề yêu cầu 20–50 cổng, 100–300 chuyến/ngày. Tệp benchmark đếm cả tài nguyên remote; demo lớn đếm movements và occupancies khác nhau. | Thống nhất báo cáo theo contact gates, remote capacity, legs và occupancies riêng; dùng bài toán đúng quy mô đề làm kết quả chính. | R18; 1.500 movements/750 occupancies không được mô tả là 1.500 turn. Kịch bản 150 cổng là mở rộng. |

## Những việc đã có thể kiểm tra

Có prediction-level evidence cho LR/XGBoost classification departure và hồi quy departure; có OOF baseline và OOF tuned arrival; hai study HPO XGBoost arrival có SQLite để đối chiếu; MC500 có 500 kịch bản, 5.500 lượt; SHAP departure có thể tính lại trên đúng 1.000 mẫu.

Các bằng chứng này được tính lại trong bộ reconciliation. Chúng chưa tự động chứng minh pipeline hiện tại đáp ứng toàn bộ đề, chất lượng triển khai tại sân bay thật hoặc đã được GVHD chấp thuận.

## Nội dung nhóm cần bổ sung khi làm việc với GVHD

- Ý kiến cụ thể cho DEV-01 đến DEV-07, ngày và hình thức xác nhận.
- Phân công và nhật ký làm việc thực tế của ba thành viên; lịch trao đổi với GVHD.
- Xác nhận yêu cầu nộp, mẫu báo cáo, thời điểm bảo vệ và việc thay đổi lịch nếu có.
- Danh sách thực nghiệm phải bổ sung trước G13; các mục chấp nhận có giới hạn phải thể hiện rõ trong luận văn.

[Nhật ký quyết định](advisor_decisions.json) giữ trạng thái PENDING đến khi có bằng chứng xác nhận. Nhóm có thể ghi nội dung trả lời vào nhật ký; không suy diễn im lặng thành chấp thuận.
