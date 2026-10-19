# Kịch bản demo và trả lời phản biện hiện hành

## Demo khoảng 12 phút

1. Phút 0–2: trình bày đề, mô hình mô phỏng ATL và các giả định. Chỉ rõ Streamlit và web là hai ứng dụng riêng.
2. Phút 2–5: trên web, upload file repo data/raw/ATL_20260701_02_schedule_raw.parquet; chọn ngày 2026-07-01, 150 contact gates và 30 remote stands, Greedy. File có FL_DATE 01–02/07 nên chưa chứng minh đầy đủ chuyến đến từ ngày nguồn 30/06.
3. Phút 5–7: xem dự báo arrival/departure, nguồn model và cảnh báo ngoài giai đoạn phát triển. Không gọi mức trễ đã dự báo là mức giảm nhờ phân cổng.
4. Phút 7–9: xem Gantt/occupancy, checker độc lập và resource capacity; tải ZIP. Đọc số movement và occupancy của chính run đang mở.
5. Phút 9–11: mở benchmark/Monte Carlo đã lưu hoặc chạy chế độ nhanh nếu ngân sách cho phép; nói rõ recourse web là hồi cứu.
6. Phút 11–12: đối chiếu bảng MC500 chính thức trong hồ sơ, giới hạn và phần còn chờ GVHD.

Đây là hướng dẫn chuẩn bị, chưa phải biên bản đã kiểm tra trực tiếp trên trình duyệt/máy chiếu. Bằng chứng HTTP ngày 19/10 có 1.848 movements, 1.193 occupancies và nghiệm Greedy không xung đột trên cấu hình đã ghi; run mới có thể khác nếu dữ liệu/cấu hình thay đổi.

## Phương án khi có lỗi

Nếu solver timeout hoặc UNKNOWN, giữ đúng trạng thái và không công bố objective nghiệm chưa hợp lệ. Với pipeline có fallback, trình bày actual_solver là Greedy nếu fallback đã dùng. Không đổi nhãn heuristic thành CP-SAT tối ưu.

Nếu không đủ sức chứa, trình bày peak demand và tài nguyên hữu hạn. Có thể đổi cấu hình để trình diễn, nhưng đó là run mới có assumptions riêng. Không che giấu nhu cầu bằng bãi tràn vô hạn.

Dùng bundle/snapshot đã chuẩn bị để trình bày kết quả có provenance khi không đủ thời gian chạy. Lịch minh họa được ghi nhãn minh họa. Không tái gán MC500 hoặc SHAP cũ cho file upload.

## Câu hỏi và nội dung trả lời

**Tại sao AUC khác số trong bản nháp?** Bản hiện hành tính từ đúng prediction-level artifact. Departure calibrated classifier AUC 0,64289; arrival có task/population riêng. Giá trị từ bản nháp chưa xác minh đã được rút khỏi kết luận chính.

**Tại sao sigmoid từ regression có AUC cao hơn classifier?** Đó là hai mô hình/đầu ra khác nhau. Ranking metric không xác nhận hiệu chuẩn xác suất; Brier, calibration và threshold cũng phải công bố.

**Tại sao không dùng Weather/Flight Chain?** Chưa đủ provenance trước cutoff cho các feature dự kiến. Bảng ablation B/C hiện chưa có pipeline dự báo để xác minh mức gain. Nhóm đang trình GVHD cách xử lý yêu cầu gốc.

**Weighted Ensemble có phải Stacking không?** Không thể gọi tương đương chỉ từ nhãn ensemble. Stacking cần meta learner huấn luyện bằng dự báo ngoài mẫu; hiện cần quyết định DEV-02.

**Model arrival là P4 hay B5?** Checkpoint đang nạp là B5NGBoostStudentT, native ID b5_ngboost_student_t. Báo cáo P4 lịch sử và registry hiện hành có trạng thái khác nhau; bảng model identity ghi rõ điều đó.

**SA có bắt buộc cải thiện CP-SAT không?** Không có thuật toán nào giảm objective dưới optimum đã chứng minh của cùng bài toán. Với nghiệm chưa tối ưu, cải thiện phụ thuộc ngân sách và neighborhood. Báo cáo thực nghiệm không bảo đảm tăng dương.

**Tại sao Mode A có khả thi 25,2%?** Đây là kết quả official MC500 được đối soát theo từng initial solver. Các cột raw ghi 682 contact overlaps và 0 buffer violations mỗi solver; không dùng giải thích buffer từ pilot cũ.

**C2 có phải 100% optimum không?** Có 499 OPTIMAL và 1 FEASIBLE. Feasibility và optimality là hai điều khác nhau.

**Web Monte Carlo có vận hành online không?** Hiện recourse được giải khi biết toàn bộ kịch bản ngày, là hồi cứu. Official B2 là thí nghiệm causal online riêng.

**Có thể triển khai tại sân bay thật ngay không?** Chưa có bằng chứng để kết luận như vậy. Đây là ứng dụng nghiên cứu/mô phỏng; thiếu dữ liệu và nghiệm thu vận hành thực tế.

**GVHD đã duyệt các thay đổi chưa?** Hiện chưa có xác nhận trong hồ sơ. Bản trình và decision log giữ PENDING đến khi có căn cứ.
