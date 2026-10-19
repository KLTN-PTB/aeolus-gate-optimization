# Khoảng thiếu và tiêu chí xử lý tiếp theo

Danh sách này tách công việc chuẩn hóa đã thực hiện khỏi việc cần thực nghiệm, nghiệm thu hoặc ý kiến bên ngoài. Thứ tự ưu tiên phục vụ việc chốt khóa luận, không phải mức độ lỗi vận hành sân bay.

| Mã | Ưu tiên | Khoảng thiếu | Người/điều kiện cần có | Tiêu chí hoàn thành |
|---|---|---|---|---|
| GAP-01 | Cao | Chưa có xác nhận GVHD cho các khác biệt đề–triển khai | Nhóm và GVHD | DEV-01…07 có quyết định, ngày và căn cứ; yêu cầu bị từ chối có kế hoạch bổ sung |
| GAP-02 | Cao | Báo cáo lịch sử gắn P4 với checkpoint B5, trong khi registry P4 là research_candidate và không downstream eligible | Người phụ trách model, đối chiếu quyết định registry và checkpoint | Một bảng model identity thống nhất; không đổi tên/chứng nhận hoặc sửa quyền registry chỉ để khớp báo cáo |
| GAP-03 | Cao | Bảng Chain/Weather có giá trị ghi cứng, chưa có so sánh từ dự báo cặp tương ứng | Theo quyết định DEV-01 | Có thực nghiệm mới hợp lệ và truy vết được, hoặc GVHD chấp nhận cách xử lý giới hạn; số cũ giữ trạng thái chưa xác minh |
| GAP-04 | Cao | Weighted Ensemble chưa phải Stacking | Theo DEV-02 | Chấp thuận thay phương pháp, hoặc OOF meta learner và đánh giá temporal riêng có bằng chứng |
| GAP-05 | Cao | HPO arrival không chứng minh departure checkpoint đã được Optuna tối ưu | Truy vết training config/model hash | Bảng ánh xạ study → tham số → model; thiếu thì báo rõ và bổ sung theo yêu cầu GVHD |
| GAP-06 | Cao | Chưa nghiệm thu giao diện bằng trình duyệt thật, máy chiếu và người dùng | Giai đoạn UI QA | Có ảnh chụp và biên bản các luồng dữ liệu thật, timeout, export, cancel/resume |
| GAP-07 | Cao | Chưa có full regression và báo cáo G13 cho phiên bản cuối | Sau thay đổi cần thiết | Chạy đúng toàn bộ test hiện hành, khóa phiên bản và inventory; kết quả ghi theo phạm vi thực thi |
| GAP-08 | Vừa | Luận văn Word/PDF và slide PPTX chưa có bản theo mẫu trường trong đợt này | Mẫu chính thức và nhóm | Đủ file xuất, kiểm tra bố cục, nguồn số liệu và trích dẫn |
| GAP-09 | Vừa | Phân công nhóm, họp hàng tuần, thời hạn nộp chưa có hồ sơ đối chiếu | Nhóm/GVHD | Có nhật ký thực tế; không tự tạo lịch sử hoặc chữ ký |
| GAP-10 | Vừa | Danh mục tài liệu tham khảo trích từ đề chưa được xác minh trực tuyến trong đợt này | Đợt rà soát thư mục tham khảo | Mỗi trích dẫn có tác giả/tên/DOI hoặc URL được đối chiếu nguồn gốc; không tự sửa theo phỏng đoán |
| GAP-11 | Vừa | Baseline median P08 arrival được lấy từ nhãn đánh giá | Kết quả hiện tại đã giới hạn ở chẩn đoán hồi cứu | Nếu cần baseline triển khai, fit median trên train từng fold và lưu cấu hình/dự báo trong một thí nghiệm mới |
| GAP-12 | Vừa | Không có bằng chứng mọi benchmark dùng cùng tổng wall-clock budget | Thiết kế benchmark cuối | Công bố thời gian build/search/verify và timeout; so sánh cùng chi phí, snapshot và ngân sách được kiểm soát |
| GAP-13 | Vừa | Monte Carlo web biết toàn bộ ngày khác causal B2 chính thức | Tài liệu hiện tại đã tách ngữ nghĩa | Chỉ triển khai online web nếu có yêu cầu riêng; kết quả hiện tại dùng đúng nhãn hồi cứu |
| GAP-14 | Vừa | Không tự chứng minh đủ tồn kho tàu đầu/cuối ngày, gate leasing và mọi ràng buộc hàng không | Phạm vi mô phỏng/GVHD | Giới hạn ghi trong phương pháp và demo; thêm ràng buộc chỉ khi có dữ liệu và yêu cầu cụ thể |
| GAP-15 | Cao | Hai calibrated classifier checkpoint chưa nạp độc lập được do lớp CalibratedPredictor được pickle dưới __main__ | Công việc đóng gói model riêng, giữ nguyên file gốc | Đưa wrapper vào module ổn định hoặc loader có kiểm soát, kiểm tra hash và predict_proba trên fixture; lưu phiên bản mới nếu cần |

Trạng thái nạp từng checkpoint nằm trong model_identity.json. Một checkpoint có file và hash không đồng nghĩa có thể deserialize độc lập hoặc đã hiệu chuẩn thống kê. Nếu có LOAD_FAILED, phải ghi thành hạng mục khắc phục trước khi sử dụng model đó ngoài luồng đã kiểm tra.

Các thay đổi training, solver, objective, feature set hoặc official MC500 không được thực hiện trong hai giai đoạn này. Bằng chứng mới sau này được lưu thành run độc lập, có đánh giá tác động và phê duyệt phạm vi khi cần.
