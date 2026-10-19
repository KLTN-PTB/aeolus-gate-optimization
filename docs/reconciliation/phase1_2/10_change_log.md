# Nhật ký hiệu đính và nguồn kế thừa

G9/G8/G12C và chứng nhận lịch sử được giữ nguyên. Bản sử dụng hiện tại nằm trong bộ này.
Không khẳng định GVHD đã duyệt. Giá trị bị rút bỏ có thể tồn tại trong lịch sử để truy vết.

| Nội dung trước đây | Hiện tại | Nơi sử dụng | Căn cứ |
|---|---|---|---|
| AUC bản nháp không có nguồn phù hợp | Dùng đúng task/split và phép tính mới | 07_current_thesis.md; 08_defense_slides.md | ml_metrics.json |
| P08 ghi macro cho phép tính pooled | Công bố riêng pooled, macro, N và fold | 05_results.md | ml_metrics.json |
| P08 tuned row là hằng số | Dùng full OOF 1.254.518 dòng, không so gain với subset khác | 05_results.md | ml_metrics.json; hpo_audit.json |
| Chain/Weather như ablation đã xác minh | Hằng số thiếu prediction lineage, bỏ gain khỏi kết luận chính | 02_advisor_review.md | lineage_audit.json |
| Weighted Ensemble như Stacking | Hai phương pháp khác nhau; DEV-02 chờ GVHD | 01_requirements.md | lineage_audit.json |
| P4 và B5 như cùng engine | Đối chiếu class deserialize, registry và native ID | 06_current_state.md | model_identity.json |
| Sigmoid regression như classifier | Ghi HEURISTIC_DERIVED riêng | 05_results.md | ml_metrics.json |
| XGBoost calibration ghi isotonic | XGBoost dùng sigmoid; LR dùng isotonic | 07_current_thesis.md | scripts/train_outbound_classifiers_g3.py |
| Mode A theo số pilot cũ | 25,2% feasible; 682 overlaps mỗi initial solver; 0 buffer violations | 05_results.md | mc500_audit.json |
| C2 100% optimum hoặc B2−C2 là EVPI | 499 OPTIMAL, 1 FEASIBLE; policy-to-foresight gap | 08_defense_slides.md | mc500_audit.json |
| CI95 được xem là cùng phép tính | Công bố Student t; CSV cũ dùng xấp xỉ 1,96 | 04_evidence_policy.md | mc500_audit.json |
| Hybrid luôn bằng/thắng CP-SAT | Báo cáo kết quả từng run; không khái quát ngân sách | 05_results.md | benchmark_audit.json |
| BTS nói chung thiếu TAIL_NUM | Phát biểu theo dataset cụ thể; tail chưa xác thực rotation | 07_current_thesis.md | model_identity.json; src/simulation/bts_daily_replay.py |
| Median làm chứng minh lợi thế triển khai | Tách median từ eval labels; cần train-only nếu dùng deployment baseline | 04_evidence_policy.md | lineage_audit.json |
| Web recourse là causal online | Ghi hồi cứu biết toàn bộ ngày, khác B2 chính thức | 09_demo_and_qa.md | web_dashboard/experiments.py |
| Số test mọi mốc như full suite hiện tại | Giữ scope/date; G13 còn riêng | 11_validation_report.md | docs/dashboard/EXPERIMENT_ACCEPTANCE.md |
