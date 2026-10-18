# AEOLUS-G10 — DELIVERABLE 10: FINAL INDEPENDENT AUDIT VERDICT & GOVERNANCE REPORT

---

**Audit Gate:** `AEOLUS-G10` — Independent Post-Remediation Source & Scientific Evidence Audit  
**Date of Audit:** 2026-10-11  
**Auditor Role:** Independent Principal Software Auditor, ML Scientific Reviewer & Academic Integrity Lead  
**Overall System Verdict:** **REJECTED FOR RELEASE / CONDITIONALLY ACCEPTED FOR ACADEMIC REVISION WITH MANDATORY CORRECTIONS**  

---

## 1. KẾT LUẬN KIỂM TOÁN TỔNG QUAN (EXECUTIVE VERDICT)

Qua quá trình kiểm toán độc lập toàn diện mã nguồn, tệp thực thi, bộ kiểm thử hồi quy và 95 văn bản báo cáo từ G0 đến G9, Hội đồng Kiểm toán Độc lập kết luận:

1. **Về Năng lực Kỹ thuật và Mã nguồn Phần mềm (EXCELLENT CODE BASE):**  
   Đội ngũ kỹ thuật đã xây dựng một hệ thống phần mềm tối ưu hóa và học máy có chất lượng chuyên môn rất cao:
   - Bộ giải **CP-SAT** giải quyết tối ưu toàn cục bài toán phân bổ cổng đỗ với độ chính xác tuyệt đối và thời gian phản hồi phần trăm giây.
   - Thuật toán **Monte Carlo Mode B2** triển khai thành công cơ chế cuốn chiếu nhân quả theo dòng sự kiện thời gian thực, triệt tiêu $100\%$ xung đột cổng vật lý mà không vi phạm nguyên tắc nhìn trước tương lai.
   - Kiến trúc kiểm soát dữ liệu tại điểm cắt $T-2h$ loại bỏ triệt để rò rỉ dữ liệu.
2. **Về Tính Trung thực của Báo cáo và Hồ sơ Khóa luận (SEVERE REPORTING & EVIDENCE DEFECTS):**  
   Báo cáo G8 và Khóa luận G9 đã mắc nhiều sai phạm nghiêm trọng về tính toàn vẹn học thuật và quản trị cấu hình:
   - **Tự nâng khống chỉ số ROC-AUC của mô hình chuyến bay đi** từ giá trị thực nghiệm $0,643$ lên $0,795$.
   - **Ngụy tạo toàn bộ cột chi phí trong Bảng 5.4 Monte Carlo** (ghi $10.0, 7.82, 12.45, 6.41$ trong khi số liệu thật trong artifact là $1606.43, 134.83, 147.43, 122.43$).
   - **Khai khống quy mô kịch bản Monte Carlo** từ 100 kịch bản thực tế lên 500 kịch bản.
   - **Tráo đổi bảng số liệu hồi quy của Chuyến bay Đi sang Chuyến bay Đến (Inbound NGBoost)**.
   - **Tuyên bố đã hoàn thành verified turnaround pairing** trong khi thực tế đo lường được là **đúng bằng 0** chu trình xác thực.
   - **Phát hành release giả định** dưới mã commit G0 baseline cũ trong khi toàn bộ mã nguồn nằm ở working tree chưa commit.
   - **Sai lệch thông tin sinh viên và hội đồng** so với đề cương chính thức của Nhà trường.

Do đó, hệ thống **CHƯA ĐỦ ĐIỀU KIỆN PHÁT HÀNH CHÍNH THỨC (BLOCKED FOR RELEASE)** và **BẢN THẢO KHÓA LUẬN G9 BUỘC PHẢI TIẾN HÀNH ĐÍNH CHÍNH BẮT BUỘC TRƯỚC KHI IN ẤN VÀ BẢO VỆ**.

---

## 2. PHÂN LOẠI MỨC ĐỘ ƯU TIÊN CỦA 10 VẤN ĐỀ ĐƯỢC XÁC MINH

| STT | Vấn đề Kiểm toán Xác minh | Mức độ Ưu tiên | Trạng thái Thực tế | Hành động Bắt buộc |
| :---: | :--- | :---: | :---: | :--- |
| **01** | **G3 Bảng Bin không khớp ECE tổng hợp** | `P1` | **CONFIRMED** | Bảng 4 trong G3-08 ghi số liệu minh họa; artifact thật ghi nhận ECE = 0.01192, prevalence = 20.63%. Đính chính lại bảng. |
| **02** | **G9 dùng ROC-AUC và MAE khác G3/G8** | `P0` | **CONFIRMED** | ROC-AUC thật là 0.643 (G9 ghi 0.795); G9 dán nhãn nhầm Departure MAE sang Inbound NGBoost. Bắt buộc thanh lọc số liệu ngụy tạo. |
| **03** | **G2 chỉ có 100 kịch bản, chưa có 500** | `P0` | **CONFIRMED** | Thực tế chỉ chạy 100 kịch bản; chi phí thật là 1606.43 vs 147.43 (G9 tự bịa 10.0 vs 12.45). Cập nhật số liệu thật vào Bảng 5.4. |
| **04** | **G5 Hybrid có chi phí cao hơn CP-SAT** | `P1` | **CONFIRMED** | Do chia đôi ngân sách thời gian (cp_ratio = 0.5) làm CP-SAT bị thiếu giờ ở N=200, 300. Giải thích bản chất phân bổ tài nguyên. |
| **05** | **G4 có 0 Verified Rotations** | `P0` | **CONFIRMED** | Dữ liệu BTS thiếu `TAIL_NUM`, pilot chạy 200 singletons, inferred ghép 59 cặp heuristic. Không được gọi là verified rotations. |
| **06** | **G7 có 4 test failures** | `P1` | **CONFIRMED** | 4 tests lỗi do manifest đóng băng lịch sử. Cần công bố tỷ lệ 2.113/2.117 (99.81%) và tạo manifest v4. |
| **07** | **G8 dùng baseline SHA cũ cho release** | `P0` | **CONFIRMED** | HEAD là G0 baseline; code nằm ở working tree. Phải commit và tạo Git tag chính thức. |
| **08** | **G9 sai thông tin sinh viên & đề tài** | `P0` | **CONFIRMED** | Đề cương có 3 sinh viên và mã đề tài chính thức. Phải sửa trang bìa và hủy các tuyên bố ký duyệt giả định. |
| **09** | **G8 và G9 ma trận yêu cầu không khớp** | `P1` | **CONFIRMED** | G9 tự nâng 3 yêu cầu từ LIMITATION lên FULLY_ACCEPTED. Phải giữ nguyên ma trận trung thực của G8. |
| **10** | **G6 Visual QA vẫn pending** | `P1` | **CONFIRMED** | 359 tests headless đạt; cần sinh viên chạy trực tiếp trên trình duyệt cá nhân để kiểm tra trước bảo vệ. |

---

## 3. DANH MỤC PHÂN ĐỊNH SỐ LIỆU ĐƯỢC PHÉP VÀ KHÔNG ĐƯỢC PHÉP SỬ DỤNG

### 3.1. Các Số liệu AN TOÀN TUYỆT ĐỐI được phép đưa vào Khóa luận và Bảo vệ
1. **Dữ liệu BTS ATL:** $4.167.269$ bản ghi chuyến bay đến tại ATL giai đoạn 2016–2024.
2. **Dự báo Chuyến bay Đi (Outbound Classifier):**
   - Calibrated XGBoost: $\text{ROC-AUC} = \mathbf{0.64289}$, $\text{PR-AUC} = \mathbf{0.32916}$, $\text{Brier} = \mathbf{0.15637}$, $\text{ECE} = \mathbf{0.01192}$.
   - Calibrated Logistic: $\text{ROC-AUC} = 0.61336$, $\text{Brier} = 0.15892$, $\text{ECE} = 0.01047$.
3. **Bộ giải Tối ưu hóa (Fair Benchmark N=4 đến N=300):**
   - CP-SAT chứng minh tối ưu toàn cục ($0.0\%$ Gap) trên các bài toán quy mô vừa và nhỏ ($0.052$s trên 60 chuyến; $44.5\text{ms}$ trên 30 chuyến).
   - Giải thuật Hybrid đạt mức cải thiện $0.00\%$ khi CP-SAT đã chứng minh tối ưu toàn cục.
   - Giải thích hiện tượng suy giảm hiệu năng của Hybrid ở $N=200, 300$ do phân bổ quỹ thời gian $2.5$s.
4. **Mô phỏng Monte Carlo (100 kịch bản có tương quan Copula $\rho=0.45$):**
   - Kế hoạch tĩnh Mode A chịu tỷ lệ xung đột cổng vật lý **$76,0\%$**, chi phí trung bình **$1.606,43$** điểm.
   - Cơ chế cuốn chiếu nhân quả Mode B2 triệt tiêu **$100\%$ xung đột cổng vật lý**, chi phí trung bình **$147,43$** điểm, số lần đổi cổng trung bình **$2,76$ lần/ngày**, $0\%$ rò rỉ nhìn trước tương lai.
   - Mô hình hồi tố Mode B1 đạt chi phí $134,83$ điểm (nhưng phi thực tế vì sử dụng thông tin tương lai).
   - Mode C2 Oracle đạt cận dưới tối ưu toàn cục $122,43$ điểm ($100\%$ trường hợp chứng minh tối ưu toàn cục).
5. **Thực nghiệm dữ liệu thật Lễ Tạ ơn 2023 (200 chuyến bay BTS):**
   - Chế độ Singleton: Phân bổ $200/200$ chuyến bay trong $0.342$ giây, $0$ xung đột.
   - Chế độ Inferred: Ghép thành công **59 cặp quay đầu suy diễn** và 82 chuyến đơn lẻ, giải trong $0.485$ giây, $0$ xung đột.

### 3.2. Các Số liệu ĐỘC HẠI BẮT BUỘC PHẢI LOẠI BỎ (TOXIC METRICS TO PURGE)
- ❌ **TUYỆT ĐỐI KHÔNG DÙNG:** Outbound XGBoost ROC-AUC = $0.795$ (Phải sửa thành $0.643$).
- ❌ **TUYỆT ĐỐI KHÔNG DÙNG:** Outbound Random Forest ROC-AUC = $0.779$ (Không có checkpoint thật).
- ❌ **TUYỆT ĐỐI KHÔNG DÙNG:** Bảng 5.4 chi phí Monte Carlo ($10.0, 7.82, 12.45, 6.41$) (Phải thay bằng $1606.43, 134.83, 147.43, 122.43$).
- ❌ **TUYỆT ĐỐI KHÔNG DÙNG:** Tuyên bố đã chạy "500 kịch bản Monte Carlo mới" (Phải sửa thành 100 kịch bản).
- ❌ **TUYỆT ĐỐI KHÔNG DÙNG:** Tuyên bố "Verified Aircraft Turn Pairing" trên dữ liệu thật (Phải sửa thành Inferred Turnaround Mode và ghi rõ 0 verified rotations do thiếu `TAIL_NUM`).
- ❌ **TUYỆT ĐỐI KHÔNG DÙNG:** Thông tin 1 sinh viên duy nhất và các tuyên bố ký duyệt/nghiệm thu giả định ngày 25/10/2026.

---

## 4. LỜI KHUYÊN DÀNH CHO SINH VIÊN VÀ GIẢNG VIÊN HƯỚNG DẪN

Hệ thống của các bạn sở hữu những điểm sáng kỹ thuật rất lớn (CP-SAT tối ưu toàn cục xuất sắc, Mode B2 nhân quả triệt tiêu $100\%$ xung đột, xử lý trơn tru dữ liệu thực tế lớn). Việc thừa nhận trung thực các hạn chế khách quan (như ROC-AUC thực tế của chuyến bay đi đạt $0.643$ do chỉ dùng thông tin lịch trình tại $T-2h$, dữ liệu BTS không có số hiệu đuôi máy bay, hoặc CP-SAT giải nhanh hơn Hybrid) **CHÍNH LÀ ĐIỂM CỘNG HỌC THUẬT LỚN NHẤT** thể hiện tư duy nghiên cứu khoa học nghiêm túc, bản lĩnh và không chạy theo thành tích ảo.

Hãy tự tin làm sạch số liệu theo đúng chỉ dẫn của báo cáo kiểm toán này trước khi bước vào phòng bảo vệ!
