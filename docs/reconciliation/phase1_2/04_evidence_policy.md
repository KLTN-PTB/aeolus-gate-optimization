# Quy tắc sử dụng và đối soát bằng chứng

## Quyền hạn của nguồn

Đề gốc xác định yêu cầu học thuật; mã nguồn và cấu hình cho biết chương trình thực sự thực hiện gì. Checkpoint, prediction-level data, ledger và nguồn chạy giải thích từng kết quả. Văn bản GVHD xác nhận việc điều chỉnh phạm vi. Bốn loại nguồn có vai trò riêng và không thay thế lẫn nhau.

Trình tự kiểm tra một con số: tìm đúng task/split/population → xác định model/checkpoint và cột dự báo → tính lại bằng công thức công bố → đối chiếu bảng tổng hợp → sửa văn bản đang sử dụng. Một báo cáo ghi VERIFIED hoặc có ngày mới hơn chưa đủ kết luận con số đúng.

## Trạng thái bằng chứng

- RECOMPUTED_FROM_STORED_PREDICTIONS: phép tính được kiểm tra trên dự báo đã lưu; chưa phải tái huấn luyện độc lập hay xác minh prospective validity.
- RECOMPUTED_TREESHAP: TreeSHAP được tính lại bằng checkpoint/preprocessor và mẫu xác định.
- HEURISTIC_DERIVED: đại lượng tạo bởi phép biến đổi heuristic, ví dụ sigmoid từ mức trễ hồi quy.
- HISTORICAL_REPORTED: giữ nguyên kết quả lịch sử với phạm vi và thời điểm của nó; chưa tính lại trong đợt này.
- HARDCODED_SUMMARY / NOT_REPRODUCIBLE: thiếu mảng dự báo hoặc quy trình thực nghiệm để chứng minh giá trị.
- ILLUSTRATIVE: ví dụ phục vụ giải thích; không đưa vào kết luận dữ liệu thực tế.

advisor_status độc lập với evidence_status và fulfillment. PENDING chỉ thay bằng kết quả quyết định khi có căn cứ xác nhận; NONE nghĩa không có kiến nghị điều chỉnh riêng, không phải đã được GVHD duyệt.

## Hợp đồng chỉ số

Classification dùng nhãn I(delay ≥15 phút), ngưỡng dự báo 0,5 nếu bảng không chỉ ra ngưỡng khác. PR-AUC ở đây là average precision của scikit-learn. ECE dùng 10 bin đều [0,0.1), …, [0.9,1], bin cuối chứa 1. Confusion matrix dùng thứ tự TN, FP, FN, TP.

Hồi quy dùng độ trễ có dấu, đơn vị phút; không cắt dự báo âm. MAE/RMSE và MAE nhóm đuôi tính đúng tập nhãn được công bố. Ngưỡng phát hiện 15 phút từ đầu ra hồi quy không tạo thành bộ phân loại đã huấn luyện hoặc một density hợp lệ.

Macro là trung bình metric của từng fold, pooled tính metric trên toàn bộ dòng gộp. Hai cách có thể khác nhau ngay cả khi mỗi fold có số dòng bằng nhau. Giữ nguyên cỡ mẫu từng fold và không đối chiếu trực tiếp 16.000 dòng với 1.254.518 dòng như cùng thí nghiệm.

Kết quả trong JSON giữ số thực đầy đủ; bảng hiển thị 5 chữ số. Khi so với CSV lịch sử có 4/5 chữ số, dung sai bằng nửa đơn vị làm tròn tương ứng. Sai lệch nhỏ ở chữ số cuối được công bố, không sửa file gốc. CVaR lịch sử MC500 dùng trung bình các giá trị ≥ phân vị, kể cả các quan sát bằng ngưỡng; CVaR web theo số mẫu đuôi làm tròn lên là quy ước khác.

Khoảng tin cậy ghép cặp MC500 mới dùng Student t với df=N−1, delta = trái−phải và cùng realization hash. Không mô tả policy-to-foresight gap là EVPI lý thuyết. Bảng paired_comparison.csv cũ dùng xấp xỉ 1,96 nên có endpoint hơi khác; đây là hiệu đính phương pháp trình bày, không chạy lại mô phỏng.

## Những nguồn được giữ nguyên

Đề DOCX, checkpoint, prediction/ledger gốc, manifest đóng băng và bản G9/G12C được đọc và băm SHA-256. Công cụ không import script tạo artifact cũ, không train, không chạy solver và không truy cập dòng dữ liệu raw/processed năm 2024. Kết quả hậu kiểm 2024 đã lưu chỉ được đề cập như lịch sử; không gọi là untouched holdout cho toàn bộ dự án.

Thiếu file hoặc cấu trúc đầu vào sai phải báo lỗi hoặc giữ trạng thái thiếu bằng chứng. Không tự điền 0, tạo cột dự báo giả hoặc chọn nguồn có kết quả thuận lợi hơn.

Các kết luận số học không phải chứng nhận vận hành tại sân bay thật, chấm điểm đề cương, full regression hoặc G13.
