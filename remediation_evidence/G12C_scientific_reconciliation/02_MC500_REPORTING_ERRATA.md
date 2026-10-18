# BÁO CÁO 02: BẢNG HIỆU ĐÍNH BÁO CÁO KHOA HỌC MC500 (REPORTING ERRATA)
## AEOLUS-G12C — SCIENTIFIC RECONCILIATION & CORRECTION REGISTRY

**Dự án:** Aeolus Gate Optimization  
**Giai đoạn:** G12C — Scientific Reconciliation, Historical Regression & Thesis Readiness  
**Đối tượng:** Hiệu đính toàn bộ sai lệch trình bày giữa các báo cáo MC500 trước đây và dữ liệu thô đã đóng băng  
**Nguyên tắc:** *Không sửa tệp kết quả thô; thiết lập chế độ báo cáo hiệu đính độc lập có kiểm chứng số học 100%.*  

---

## 1. TỔNG QUAN HIỆU ĐÍNH (ERRATA OVERVIEW)

Đợt kiểm toán độc lập G12C đã phát hiện một số sai lệch giữa số liệu trình bày trong các báo cáo giai đoạn MC500-PRODUCTION và dữ liệu thô thực tế trong các tệp CSV. Các sai lệch này chủ yếu bắt nguồn từ:
1. Nhầm lẫn giữa phân vị của các bản chạy pilot thử nghiệm trước đó hoặc làm tròn thủ công.
2. Nhầm lẫn kịch bản sử dụng 2 vị trí bãi đỗ xa (`S0442` bị ghi nhầm thành `S0183`).
3. Sử dụng tên định danh cũ (`REMOTE_APRON_01` thay vì `REMOTE_STAND_01` đã chuẩn hóa).
4. Nhầm lẫn giữa đơn vị "trên mỗi kịch bản" và "trên mỗi chuyến bay" đối với số lượng xung đột cổng.
5. Tuyên bố khái quát hóa quá mức về tính tối ưu tuyệt đối của Mode C2 và việc chạm ngưỡng deadline thời gian.

Tất cả các điểm sai lệch đã được tính toán lại bằng script độc lập `scripts/verify_g12c_mc500_raw.py` và lập thành bảng hiệu đính chính thức dưới đây.

---

## 2. BẢNG HIỆU ĐÍNH 12 SAI LỆCH TRỌNG YẾU (MASTER ERRATA TABLE)

| STT | Tên Chỉ Số / Khoản Mục | Giá Trị Cũ (Báo Cáo Trước) | Giá Trị Thô Thực Tế (Raw Verified) | Nguyên Nhân Sai Lệch | Giá Trị Hiệu Đính Chính Thức | Mức Độ Ảnh Hưởng |
|:---:|:---|:---:|:---:|:---|:---:|:---:|
| **1** | **Mode A P90 Objective** | 2118.66 | **3106.27** | Dùng nhầm phân vị từ bản tính thử nghiệm ngoại tuyến cũ | **3106.27** | Báo cáo trình bày |
| **2** | **Mode A P99 Objective** | 6100.83 | **5106.08** | Lấy nhầm giá trị cực đại Max thay vì phân vị 99% thực tế | **5106.08** | Báo cáo trình bày |
| **3** | **Mode A CVaR90** | 3636.57 | **3751.65** | Sai lệch cận tích phân đuôi trong công thức tính CVaR cũ | **3751.65** | Báo cáo trình bày |
| **4** | **Mode B2 P99 Objective** | 338.45 | **356.02** | Sử dụng giá trị nội suy phân vị mẫu nhỏ của pilot | **356.02** | Báo cáo trình bày |
| **5** | **Mode C2 P99 Objective** | 173.49 | **165.79** | Dùng nhầm giá trị phân vị khi chưa lọc kịch bản FEASIBLE | **165.79** | Báo cáo trình bày |
| **6** | **Mode C2 P95 Runtime** | 1500.20 ms | **443.26 ms** | Nhầm lẫn giữa phân vị P95 ($443.26$ ms) và cận trên Max / Timeout | **443.26 ms** (Max: $1572.82$ ms) | Báo cáo trình bày |
| **7** | **Kịch bản Remote Count = 2** | `MC_REM_S0183` | `MC_REM_S0442` | Nhầm kịch bản do cả 2 đều nằm trong danh sách 10 kịch bản dùng remote | **`MC_REM_S0442`** | Định danh kịch bản |
| **8** | **Định danh Bãi đỗ xa** | `REMOTE_APRON_01` | `REMOTE_STAND_01` | Dùng tên định danh cũ trước đợt refactor Topology Gate | **`REMOTE_STAND_01`** | Định danh tài nguyên |
| **9** | **Đơn vị Xung đột Mode A** | 1.364 / chuyến bay | **1.364 / kịch bản** | Lỗi diễn giải đơn vị: 682 xung đột trên 500 kịch bản của 1 initial solver | **1.364 xung đột / kịch bản** | Diễn giải khoa học |
| **10** | **Vi phạm Buffer Mode A** | 13.2 phút buffer | **0 vi phạm buffer** | Nhầm lẫn giữa xung đột đè chồng tiếp xúc và vi phạm đệm cách | **0 vi phạm buffer** (2,046 contact overlaps) | Diễn giải khoa học |
| **11** | **Thời hạn Bộ giải (Time Limits)** | "0 solver chạm time limit" | **1 kịch bản chạm 1.5s** | Tuyên bố khái quát hóa; kịch bản 183 chạm deadline 1.5s CP-SAT | **499 < 1.5s, 1 chạm deadline 1.5s** | Minh bạch thuật toán |
| **12** | **Tính Tối ưu Mode C2** | "100% certified global optimum" | **499 OPTIMAL, 1 FEASIBLE** | Không công bố kịch bản 183 dừng ở FEASIBLE khi chạm deadline 1.5s | **99.8% OPTIMAL, 0.2% FEASIBLE** | Trung thực khoa học |

---

## 3. PHÂN TÍCH CHI TIẾT CÁC ĐIỂM HIỆU ĐÍNH TRỌNG TÂM

### 3.1. Phân Vị Phân Phối và Chỉ Số Rủi Ro Đuôi (Items 1–6)
Trong các báo cáo trước, một số phân vị (P90, P99, CVaR90) bị sai lệch nhẹ do việc sử dụng lại số liệu từ các phân tích ngoại tuyến cũ mà không đồng bộ tự động từ tệp CSV chính thức `execution_ledger_entries.csv`. 
- **Chính sách khắc phục:** Toàn bộ bảng số liệu phân vị trong Báo cáo 01 và các báo cáo sau này được trích xuất trực tiếp từ mã nguồn `numpy.percentile(objs, q)` và hàm tính toán `compute_cvar` có kiểm chứng bằng script tự động, xóa bỏ hoàn toàn việc nhập liệu thủ công.

### 3.2. Định Danh Kịch Bản và Tài Nguyên Bãi Đỗ Xa (Items 7 & 8)
- Trong log chạy Mode B2, kịch bản số 183 (`MC_REM_S0183`) là kịch bản duy nhất khiến CP-SAT của Mode C2 chạm ngưỡng deadline $1.5$s. Do kịch bản này cũng kích hoạt bãi đỗ xa (`remote_count = 1`), người tổng hợp báo cáo trước đã nhầm lẫn kịch bản 183 là kịch bản có `remote_count = 2`.
- **Dữ liệu thô thực tế chứng minh:**
  - Kịch bản `MC_REM_S0183` có `remote_count = 1`, `max_concurrent_remote_usage = 1`.
  - Kịch bản `MC_REM_S0442` mới chính là kịch bản duy nhất có `remote_count = 2`, `max_concurrent_remote_usage = 2`.
- Định danh bãi đỗ xa trong `gate_inventory.json` là `REMOTE_STAND_01`, thuộc loại `FINITE_REMOTE_STAND` với sức chứa 5.0. Tên cũ `REMOTE_APRON_01` chính thức được bãi bỏ.

### 3.3. Bản Chất Xung Đột Mode A: Phân Biệt Overlap và Buffer Violation (Items 9 & 10)
- Mô hình đánh giá độc lập `verify_hard_constraints_independently` phân định rõ:
  - `physical_contact_conflict_count`: Số cặp chuyến bay có thời gian chiếm dụng đè chồng lên nhau trên cùng một cổng tiếp xúc.
  - `buffer_violation_count`: Số cặp chuyến bay liên tiếp cách nhau nhỏ hơn $\Delta_{\text{buffer}} = 15$ phút nhưng không đè chồng.
- Trong dữ liệu thô của Mode A:
  - `physical_contact_conflict_count` tổng cộng là $2,046$ trên $1,500$ lượt đánh giá (trung bình $1.364$ xung đột trên mỗi kịch bản của một bộ giải ban đầu).
  - `buffer_violation_count` bằng $0$.
- Do đó, việc tuyên bố "Mode A có vi phạm buffer 13.2 phút" là sai lệch so với dữ liệu thô và được loại bỏ hoàn toàn.

### 3.4. Minh Bạch Tính Tối Ưu và Giới Hạn Thời Gian Mode C2 (Items 11 & 12)
- Mode C2 được cấu hình với giới hạn thời gian $1.5$s (`time_limit_seconds=1.5`).
- Ở 499 kịch bản, bộ giải OR-Tools CP-SAT đã chứng minh tính tối ưu toàn cục toán học (trạng thái `OPTIMAL`, `is_optimal_proven=True`).
- Ở kịch bản `MC_REM_S0183`, bộ giải chạy trong $1,572.82$ ms (chạm deadline), trả về trạng thái `FEASIBLE` với chi phí $168.80$.
- **Tuyên bố khoa học trung thực:** Khóa luận khẳng định Mode C2 đạt **$99.8\%$ Tối ưu toàn cục có chứng minh toán học, $0.2\%$ Nghiệm khả thi chất lượng cao**, không tuyên bố tuyệt đối $100\%$ provably optimal.
