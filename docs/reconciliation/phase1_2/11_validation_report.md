# Báo cáo hoàn tất đối chiếu và chuẩn hóa bằng chứng

## Phạm vi đã thực hiện

Ngày đối chiếu 19/10/2026, mã nguồn nền aed54a1. Đề gốc được trích xuất có SHA-256; các bảng rubric được giữ nguyên cấu trúc ô. Có 35 hạng mục yêu cầu và 7 nội dung trình GVHD, bao gồm yêu cầu ngoài phần mềm như báo cáo, phân công và trao đổi hàng tuần.

Giai đoạn 1 đạt **READY_FOR_ADVISOR_REVIEW**. Chưa có bằng chứng GVHD chấp thuận bất kỳ DEV-01…07 nào. Giai đoạn 2 đã tạo bộ số liệu, tài liệu hợp nhất và công cụ đối soát; các thiếu sót được giữ rõ trong backlog, không tự nâng thành đạt đề.

## Kiểm tra số học và nguồn

[validation.json](../../../artifacts/reconciliation/phase1_2/validation.json) ghi từng phép kiểm tra thay cho một kết luận chứng nhận chung:

- Mỗi yêu cầu có vị trí và trích đoạn từ đề; không tự tạo chấp thuận.
- Các study Optuna khớp best trial/giá trị/tham số SQLite mở read-only.
- MC500 đủ 500 realizations, 5.500 slots, không trùng khóa; các bảng mode khớp ledger sau mapping định danh và dung sai làm tròn bốn chữ số.
- TreeSHAP departure tính lại trên đúng 1.000 mẫu, kiểm tra tính cộng và importance.
- SHA-256 các đầu vào được giữ nguyên trong quá trình đối soát.

Model identity ghi rõ 19 file checkpoint/preprocessor, trong đó hai calibrated classifier chưa deserialize độc lập được vì wrapper được pickle dưới __main__. Đây là **GAP-15**, không bị che bởi trạng thái PASS của phép đối soát số học. Luồng native/web đang dùng regressor và arrival checkpoint được nạp riêng; không xác nhận mọi model đều có thể phục vụ độc lập.

## Kiểm tra công cụ và tài liệu

Bộ tests/reconciliation kiểm tra metric với dữ liệu biết trước, pooled so với macro, label/probability sai, identity/rounding của ledger, nguồn bị sửa, quyền chỉ đọc SQLite, chế độ check không ghi file, rubric đề, trạng thái GVHD, registry metric có đơn vị/hash và liên kết tài liệu.

Kết quả thực thi cuối cùng:

| Kiểm tra | Kết quả |
|---|---|
| tests/reconciliation | **24 passed**, 1,81 giây |
| reconcile_phase1_2.py --check | **PASS**, tái tính khớp 16 đầu ra, không ghi file |
| render_phase1_2_reports.py --check | **PASS**, báo cáo dẫn xuất khớp dữ liệu hiện tại |
| git diff --check | **PASS** sau khi xử lý khoảng trắng ở nhãn lịch sử trong docs/README |
| Đầu vào được kiểm tra hash | **275 file**, giữ nguyên trong quá trình đọc và đối soát |
| Registry chỉ số | **533 bản ghi**, có task, đơn vị, phương pháp tổng hợp và hash nguồn |
| Checkpoint được kiểm tra nạp | **17 LOADED, 2 LOAD_FAILED**; vấn đề được công bố ở GAP-15 |

Các lệnh kiểm tra:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/reconcile_phase1_2.py --check
.\.venv\Scripts\python.exe -X utf8 scripts/render_phase1_2_reports.py --check
.\.venv\Scripts\python.exe -m pytest tests/reconciliation -q --basetemp=.pytest_tmp_reconciliation_final
git diff --check
```

## Những kết luận không được suy ra

Kết quả của tests/reconciliation chưa phải full test suite của repo hoặc G13. Đợt clone sạch trước đây ghi 447 tests Python đạt, 1 skipped và 13 frontend tests đạt trong phạm vi ứng dụng; không cộng số đó thành full regression mới.

Đợt này không train, không chạy lại official MC500, không đổi solver/objective, model registry hoặc feature policy. Không đọc dòng raw/processed 2024. Quyết định chấp nhận khác biệt đề, visual QA, hồ sơ Word/PDF/PPTX cuối và xác minh trực tuyến thư mục tham khảo vẫn cần thực hiện theo backlog.

Các entrypoint README, README_DASHBOARD, PROJECT_SUMMARY và docs/README dẫn tới bộ hiện hành. Nội dung báo cáo/chứng nhận lịch sử, G9/G12C, cấu hình đóng băng và checkpoint giữ nguyên. Không commit hoặc push trong đợt này.
