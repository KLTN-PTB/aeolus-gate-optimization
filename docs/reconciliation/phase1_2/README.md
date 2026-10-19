# Đối chiếu đề cương và chuẩn hóa bằng chứng Aeolus

Bộ tài liệu hiện hành này đối chiếu đề CNTT-KLCN168 với mã nguồn và bằng chứng tại commit `aed54a1`, ngày 19/10/2026. Mục đích là chuẩn bị hồ sơ để nhóm làm việc với GVHD và sử dụng cùng một bộ số liệu khi viết luận văn, slide và demo.

**Giai đoạn 1: READY_FOR_ADVISOR_REVIEW. GVHD chưa phê duyệt thay đổi phạm vi.** Giai đoạn 2 chuẩn hóa số liệu có thể tính lại; các khoảng thiếu được công bố riêng. Trạng thái này không thay thế G13 hoặc xác nhận toàn bộ đề đã đáp ứng.

## Tài liệu sử dụng

| Nội dung | Tài liệu |
|---|---|
| Yêu cầu và liên kết về nguyên văn đề, CLO | [Ma trận 35 yêu cầu](01_requirements.md) |
| Nội dung đề nghị GVHD xác nhận | [Bản trình GVHD](02_advisor_review.md) |
| Khoảng thiếu và tiêu chí xử lý | [Backlog](03_gap_backlog.md) |
| Quy tắc sử dụng số liệu | [Chính sách bằng chứng](04_evidence_policy.md) |
| Kết quả và phạm vi từng phép so sánh | [Kết quả hiện hành](05_results.md) |
| Kiến trúc, model và trạng thái ứng dụng | [Trạng thái hiện hành](06_current_state.md) |
| Nội dung hợp nhất cho báo cáo | [Bản thảo sử dụng hiện tại](07_current_thesis.md) |
| Nội dung trình bày | [Slide dạng Markdown](08_defense_slides.md) |
| Demo và trả lời phản biện | [Demo và Q&A](09_demo_and_qa.md) |
| Theo dõi sửa đổi và nguồn kế thừa | [Nhật ký hiệu đính](10_change_log.md) |
| Kiểm tra và giới hạn nghiệm thu | [Báo cáo kiểm tra](11_validation_report.md) |
| Danh mục tham khảo được trích từ đề | [Tài liệu tham khảo](12_references.md) |

Các bản G9, G8, G12C và chứng nhận P14 tiếp tục lưu nguyên trạng như hồ sơ lịch sử. Bản hợp nhất ở đây thay thế nội dung sử dụng khi viết tiếp báo cáo; trích dẫn một kết quả lịch sử vẫn cần giữ đúng năm, task, split và phạm vi của nó.

## Cách tái kiểm tra

Từ root dự án, trong môi trường Python nghiên cứu hiện có:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/reconcile_phase1_2.py --check
.\.venv\Scripts\python.exe -X utf8 scripts/render_phase1_2_reports.py --check
.\.venv\Scripts\python.exe -m pytest tests/reconciliation -q --basetemp=.pytest_tmp_reconciliation
```

Bỏ `--check` để tạo lại các đầu ra reconciliation. Công cụ đầu tiên chỉ ghi vào `artifacts/reconciliation/phase1_2/`; công cụ thứ hai chỉ tạo các bảng/báo cáo dẫn xuất trong bộ tài liệu này. Không gọi script P08 cũ để tạo lại bằng chứng.

Đối soát toàn phần cần đề gốc ở root và các dữ liệu nghiên cứu đã lưu, gồm partition 2023 dùng cho TreeSHAP. Đây là yêu cầu của đợt kiểm toán, khác bộ dữ liệu nhỏ đủ chạy dashboard từ clone sạch. Không có file nguồn thì ghi nhận thiếu bằng chứng; không tự thay mẫu khác.

## Các đầu ra máy đọc

[Nguyên văn đề và bảng thang điểm](../../../artifacts/reconciliation/phase1_2/proposal_extract.json), [ma trận JSON](../../../artifacts/reconciliation/phase1_2/requirements.json), [CSV chỉ số](../../../artifacts/reconciliation/phase1_2/metric_registry.csv), [kiểm tra tính nhất quán](../../../artifacts/reconciliation/phase1_2/validation.json), [hash nguồn](../../../artifacts/reconciliation/phase1_2/source_inventory.json).

`requirements_catalog.json` là đầu vào biên tập có kiểm soát. Các file JSON/CSV ở artifacts là kết quả tạo từ danh mục đó và nguồn được đọc. Không sửa trực tiếp giá trị dẫn xuất để làm kiểm tra đạt.
