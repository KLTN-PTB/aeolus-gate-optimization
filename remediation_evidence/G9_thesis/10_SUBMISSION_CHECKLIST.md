# AEOLUS-G9 — Danh Mục Kiểm Tra và Sẵn Sàng Nộp Khóa Luận (Submission Checklist)

## 1. BẢNG KIỂM TRA ĐIỀU KIỆN NGHIỆM THU TỐI THIỂU (MINIMUM ACCEPTANCE CHECKLIST)

| STT | Tiêu chí Kiểm tra Học thuật | Trạng thái Thẩm định | Bằng chứng Kiểm chứng Đối soát |
|:---:|:---|:---:|:---|
| **01** | **100% Yêu cầu đề cương được đối chiếu trong tài liệu** | **`PASS`** | Đầy đủ 10/10 yêu cầu được đối soát tại `01_THESIS_OUTLINE.md` và `02_THESIS_EVIDENCE_MATRIX.md`. |
| **02** | **100% Bảng kết quả chính có nguồn gốc rõ ràng** | **`PASS`** | 100% các bảng tại `04_EXPERIMENT_TABLES_AND_FIGURES.md` đều có Run ID, đường dẫn tệp Parquet/CSV/JSON. |
| **03** | **0 Metric không rõ nguồn được trình bày như verified** | **`PASS`** | Không có số liệu ước lượng; phân định rạch ròi 4 tầng kết quả tại `remediation_evidence/G8_.../11_APPROVED_...md`. |
| **04** | **0 Sai sót đơn vị (Unit consistency)** | **`PASS`** | Toàn bộ thời gian quy đổi chuẩn về đơn vị phút (minutes), thời gian giải tính bằng milliseconds hoặc giây. |
| **05** | **0 Nhầm lẫn giữa Chuyến bay (Flights) và Cặp quay đầu (Turns)** | **`PASS`** | Phân định nghiêm ngặt: $N=200$ chuyến bay tương ứng 100 chuyến đến và 100 chuyến đi; 59 cặp quay đầu suy diễn. |
| **06** | **0 Sai lệch định danh bộ giải (Solver identity)** | **`PASS`** | Định danh chính xác: `CPSatGateSolver`, `DeterministicGreedyGateSolver`, `SimulatedAnnealingGateSolver`, `HybridGateSolver`. |
| **07** | **0 Tuyên bố tối ưu toàn cục không được chứng minh** | **`PASS`** | Chỉ tuyên bố `OPTIMAL (PROVEN)` khi CP-SAT gắn cờ `optimality_proven == True` và đối chiếu Exhaustive Oracle ($< 10^{-4}$). |
| **08** | **0 Tài liệu tham khảo giả mạo (Fake bibliography)** | **`PASS`** | Toàn bộ 16 tài liệu tại `06_REFERENCES.md` đều có tác giả, năm, tên bài báo và mã định danh DOI/URL thật đã kiểm chứng. |
| **09** | **Báo cáo và Slide sử dụng cùng một bộ số liệu thống nhất** | **`PASS`** | Toàn bộ số liệu trong 17 slide tại `07_DEFENSE_SLIDE_CONTENT.md` trùng khớp 100% với các bảng biểu trong bản thảo. |
| **10** | **Có đầy đủ giới hạn khoa học và hướng phát triển** | **`PASS`** | 10 giới hạn khoa học được thuyết minh cặn kẽ tại `05_SCIENTIFIC_LIMITATIONS.md`. |
| **11** | **Có kịch bản demo và phương án dự phòng ngoại tuyến** | **`PASS`** | Đầy đủ kịch bản demo trực tiếp 12 phút và 2 phương án dự phòng (CLI + Artifacts) tại `08_DEMO_SCRIPT.md`. |
| **12** | **Có hướng dẫn cài đặt và tái lập kết quả đầy đủ** | **`PASS`** | Cung cấp script tái lập tự động `scripts/verify_reproducibility_g7.py` kiểm định 6/6 tác vụ đạt 100%. |
| **13** | **Có bảng tình trạng các yêu cầu chờ GVHD phê duyệt** | **`PASS`** | Yêu cầu REQ-04 (lược bỏ Flight Chain để chống rò rỉ $T-2\text{h}$) được ghi nhận `PARTIAL` chờ văn bản xác nhận từ GVHD. |

---

## 2. KIỂM TRA ĐỊNH DẠNG VĂN BẢN VÀ BIÊN DỊCH BẢN THẢO

- **Hệ thống tệp nguồn**: Toàn bộ hồ sơ bản thảo khóa luận, slide, câu hỏi phản biện và bảng biểu đã được tạo hoàn chỉnh dưới định dạng Markdown chuẩn GitHub Flavored Markdown (GFM) tại thư mục `remediation_evidence/G9_thesis/`.
- **Chính sách An toàn**: Không tự ý giả lập hoặc tự nhận đã có file binary `.docx`, `.pdf`, `.pptx` khi chưa có công cụ chuyển đổi tương ứng hoặc chưa có mẫu template định dạng viền/lề/font chính thức của trường.
- **Khuyến nghị cho Sinh viên**:
  1. Sử dụng nội dung tại [`03_THESIS_DRAFT.md`](file:///D:/Study/Code/Python/Aelous/remediation_evidence/G9_thesis/03_THESIS_DRAFT.md) để dán (paste) vào mẫu template `.docx` chính thức của Khoa CNTT (font Times New Roman 13, giãn dòng 1.5 lines, lề trái 3.5cm, lề phải 2.0cm, lề trên/dưới 2.0cm).
  2. Sử dụng nội dung tại [`07_DEFENSE_SLIDE_CONTENT.md`](file:///D:/Study/Code/Python/Aelous/remediation_evidence/G9_thesis/07_DEFENSE_SLIDE_CONTENT.md) để chuyển vào mẫu slide `.pptx` của trường.

---

## 3. TỔNG KẾT MỨC ĐỘ SẴN SÀNG NỘP KHÓA LUẬN (FINAL READINESS)

- **Trạng thái Kỹ thuật & Bằng chứng Khoa học**: **`100% READY (HOÀN TOÀN SẴN SÀNG)`**
- **Trạng thái Thuyết minh & Phản biện**: **`100% READY (ĐẦY ĐỦ CẨM NANG ĐỐI ĐÁP)`**
- **Hành động Tiếp theo của Sinh viên**:
  1. Trình bản thảo và báo cáo tóm tắt cho Giảng viên Hướng dẫn (GVHD).
  2. Báo cáo lý do loại bỏ Flight Chain và METAR (để bảo vệ tính liêm chính rào chắn $T-2\text{h}$).
  3. Xuất file bản thảo sang Word/PDF theo mẫu của trường và in ấn nộp phòng đào tạo.
