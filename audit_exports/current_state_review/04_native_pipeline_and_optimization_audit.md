# BÁO CÁO KIỂM TOÁN 04: KIỂM TOÁN PIPELINE HAI LÕI BẢN ĐỊA VÀ BỘ GIẢI PHÂN BỔ CỔNG (PIPELINE & SOLVER AUDIT)

**Dự án:** Aeolus Gate Optimization (`aeolus-gate-optimization`)  
**Khóa luận:** Cử nhân Công nghệ Thông tin  
**Thời điểm kiểm toán:** 2026-10-11T15:44:00+07:00  
**Vai trò thẩm định:** Principal Software Architect, Operations Research Auditor  

---

## 1. Kiểm toán Pipeline Hai Lõi Bản địa P07 (Native Dual-Core Predict-Then-Optimize)

### 1.1. Luồng Suy luận Bản địa (Native Inference Verification)
Kiểm toán đã lần vết chi tiết phương thức `run_native_inference` trong `src/simulation/native_dual_core_pipeline.py`:
* **Nạp mô hình thật:** Pipeline nạp trực tiếp `P4_ngboost_student_t` (`model_weights_frozen_v1.joblib`) và `departure_xgboost_baseline_v1.joblib` thông qua kiểm tra băm SHA-256 bắt buộc.
* **Suy luận phân phối thật:** Với chuyến bay đến, pipeline gọi `arr_model.predict_distribution(X_arr)`, trích xuất các tham số $\mu, \sigma, \nu$ (bậc tự do Student-T), và tính toán hàm sống sót (survival function) $P(\text{delay} \ge 15) = 1 - F(15)$.
* **Suy luận điểm thật:** Với chuyến bay đi, pipeline chuyển đổi đặc trưng qua `departure_tree_preprocessor_v1.joblib` và gọi `dep_model.predict(X_prep)`.
* **Kết luận:** Quá trình suy luận của P07 là **suy luận thời gian chạy thực thụ (True Native Inference)**, hoàn toàn không sử dụng dữ liệu dự báo tạo sẵn (precomputed dummy predictions).

### 1.2. Thẩm định Quy trình Ghép cặp Lượt bay (Aircraft Turn Pairing Forensics)
* **Quy tắc Ghép cặp:** Tàu bay đến và tàu bay đi được ghép thành một lượt quay vòng (Aircraft Turn) dựa trên cùng số đuôi máy bay (`TAIL_NUM`) hoặc cùng hãng hàng không (`OP_CARRIER`), đảm bảo thời gian quay vòng tối thiểu kỹ thuật 45 phút (`min_turnaround_min = 45`) và đệm phân cách cổng 15 phút (`buffer_min = 15`).
* **Phát hiện Bất thường trong Run Manifest P07:**
  * Tại `artifacts/remediation/native_dual_core/run_manifest.json` (dòng 38–50):
    * `total_pairs`: **30**
    * `synthetic_pairs_count`: **30**
    * `verified_pairs_count`: **0**
  * **Nguyên nhân:** Trong script thực thi `scripts/run_native_dual_core_pipeline.py` (hàm `build_legs_and_pairs_from_frames`, dòng 237–261), script đơn thuần ghép hàng thứ $i$ của bảng Inbound với hàng thứ $i$ của bảng Outbound. Do số đuôi máy bay của hai hàng này không trùng nhau ngẫu nhiên, hệ thống đã tự động gán nhãn toàn bộ 30 lượt bay này là `SYNTHETIC_PAIR`.
  * **Quy mô Lượt chạy:** Lượt chạy được chứng nhận chính thức của P07 chỉ thực thi trên **30 chuyến bay / 25 cổng** (quy mô smoke slice), chưa thực hiện trên tập 100–300 chuyến bay thực tế trong ngày với 100% số đuôi máy bay được đối soát thật (`VERIFIED_PAIR`).

---

## 2. Kiểm toán Bộ giải Phân bổ Cổng (Gate Solver Correctness & Formulations)

Hệ thống triển khai 4 thuật toán tối ưu hóa: **Deterministic Greedy**, **Google OR-Tools CP-SAT**, **Simulated Annealing (SA)**, và **Hybrid (CP-SAT + SA)**.

### 2.1. Tính Đúng đắn của Ràng buộc Cứng trong CP-SAT (P06 Refactoring)
P06 đã tái cấu trúc mô hình CP-SAT từ dạng bất đẳng thức cặp thô ($O(N^2 \cdot G)$ ràng buộc) sang dạng biến khoảng thời gian nguyên bản (Native Interval Variables) của OR-Tools:
1. **Ràng buộc Duy nhất (Exactly-One Assignment):** $\sum_{g \in \mathcal{G}_i} x_{i,g} = 1, \quad \forall i \in \mathcal{F}$.
2. **Ràng buộc Không Trùng lặp (Zero-Overlap on Contact Gates):** Sử dụng `model.AddNoOverlap([interval_{i,g}])` cho từng cổng tiếp xúc, triệt tiêu hoàn toàn hiện tượng xung đột vật lý.
3. **Ràng buộc Sức chứa Cổng Từ xa Hữu hạn (Finite Remote Stand Capacity):** Sử dụng `model.AddCumulative([interval_{i,r}], demands=[1], capacity=K)` với $K = 5$ vị trí đỗ ngoài bãi.
4. **Ràng buộc Tương thích Cổng (Gate Compatibility):** Tự động loại trừ các cặp biến không tương thích về loại máy bay hoặc hãng hàng không.
* **Chứng nhận Khớp Toán học (Mathematical Parity):** Bộ giải đạt **100% kết quả khớp tuyệt đối** khi đối chiếu với combinatorial oracle (thuật toán duyệt toàn bộ $G^N$ nghiệm) trên các kịch bản biên trong `artifacts/remediation/cp_sat/parity_results.json`.

### 2.2. Kiểm toán Hiệu năng Quy mô Lớn (Scalability Matrix 100 đến 1.500 Chuyến bay)
Kiểm toán đã kiểm tra toàn bộ tệp `artifacts/remediation/cp_sat/scalability_results.csv`:

| Quy mô Thử nghiệm | Số Chuyến | Số Cổng | Công thức | Trạng thái Bộ giải | Thời gian Xây dựng (ms) | Thời gian Tìm kiếm (ms) | Giá trị Mục tiêu ($J$) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **100x20** | 100 | 21 | `dense_pairwise` | **OPTIMAL** | 1,320.1 ms | 212.9 ms | 264.93 |
| **100x20** | 100 | 21 | `sparse_interval` | **FEASIBLE** | 311.1 ms | 10,010.9 ms (Timeout) | 264.93 |
| **200x30** | 200 | 31 | `dense_pairwise` | **OPTIMAL** | 7,144.7 ms | 1,461.1 ms | 729.73 |
| **300x50** | 300 | 51 | `dense_pairwise` | **OPTIMAL** | 25,976.3 ms | 5,296.3 ms | 959.20 |
| **500x50** | 500 | 51 | `sparse_interval` | **FEASIBLE** | 3,892.4 ms | 10,035.3 ms (Timeout) | 9,434.80 |
| **750x50** | 750 | 51 | `sparse_interval` | **UNKNOWN** | 5,880.3 ms | 7,396.0 ms (Timeout) | Không tìm ra nghiệm |
| **1000x50** | 1000 | 51 | `sparse_interval` | **UNKNOWN** | 7,920.6 ms | 6,854.5 ms (Timeout) | Không tìm ra nghiệm |
| **1500x50** | 1500 | 51 | `sparse_interval` | **UNKNOWN** | 12,110.4 ms | 10,372.8 ms (Timeout)| Không tìm ra nghiệm |

#### ⚠️ Phát hiện Trọng yếu về Quy mô:
* Tại quy mô 100, 200, 300 chuyến bay (đúng phạm vi đề cương khóa luận): Bộ giải CP-SAT giải ra nghiệm **TỐI ƯU TOÀN CỤC (OPTIMAL)**.
* Tại quy mô 500 chuyến bay: Bộ giải tìm ra nghiệm **KHẢ THI (FEASIBLE)** với chi phí mục tiêu hợp lý trong ngân sách thời gian.
* Tại quy mô 750, 1.000, 1.500 chuyến bay với thời hạn 10 giây: Trạng thái là **`UNKNOWN`** (hết thời gian tìm kiếm mà chưa kịp tìm thấy nghiệm khả thi đầu tiên).
* **Quy tắc Kiểm toán:** Tuyệt đối không được coi `UNKNOWN` là `INFEASIBLE` (Không khả thi), và không được coi `FEASIBLE` là `OPTIMAL`.

### 2.3. Kiểm toán Thuật toán Mô phỏng Luyện kim (SA) và Bộ giải Lai (Hybrid)
Một yêu cầu trọng tâm trong đề cương là: *"Áp dụng Simulated Annealing cải thiện lời giải; So sánh Greedy, CP-SAT, CP-SAT+SA"*.

Kiểm toán đã phân tích tệp `artifacts/development_end_to_end/aggregate_metrics.json` trên 40 kịch bản thực nghiệm:
1. **So sánh CP-SAT và Hybrid (CP-SAT + SA):**
   * Giá trị mục tiêu trung bình của CP-SAT: **`9351.6850`**
   * Giá trị mục tiêu trung bình của Hybrid (SA_CPSAT_Incumbent): **`9351.6850`**
   * Tỷ lệ cải thiện của SA trên nghiệm CP-SAT: **`0.0000%` (Không cải thiện được bất kỳ điểm số nào trên toàn bộ 40 kịch bản!)**
   * Thời gian chạy: CP-SAT tốn $1.082$ ms; Hybrid tốn $1.298$ ms (lãng phí thêm $216$ ms để chạy các vòng lặp hạ nhiệt mà không tìm ra nghiệm tốt hơn).
2. **So sánh Greedy và SA (Greedy Warm-Start + SA):**
   * Giá trị mục tiêu trung bình của Greedy: **`9430.4350`**
   * Giá trị mục tiêu trung bình của SA khởi tạo từ Greedy: **`9416.1850`**
   * Tỷ lệ cải thiện: SA cải thiện được **14.25 điểm chi phí** so với Greedy, nhưng vẫn kém hơn CP-SAT ($9351.6850$).
3. **Kết luận Khoa học:**
   * Khi CP-SAT đã tìm ra nghiệm tối ưu toàn cục, Simulated Annealing không thể cải thiện thêm về mặt toán học.
   * Do đó, việc tuyên bố "Hybrid CP-SAT+SA vượt trội hơn CP-SAT" là **sai lệch khoa học**. Thực tế thực nghiệm chứng minh: **CP-SAT thuần túy là bộ giải tối ưu nhất, còn SA chỉ có tác dụng cải thiện cục bộ khi khởi đầu từ nghiệm Heuristic Greedy**.

---

## 3. Các Phát hiện Kiểm toán Trọng yếu (Findings Register for Solvers)

### FINDING-P1-03: Lượt Chạy Chứng nhận P07 Chỉ Sử dụng 30 Chuyến bay và Toàn bộ là Cặp bay Giả lập (Synthetic Pairs)
* **Severity:** `P1 (HIGH)`
* **Expected:** Pipeline P07 được kiểm chứng đầu-cuối trên 100–300 chuyến bay/ngày với các cặp luân chuyển máy bay thật (`VERIFIED_PAIR` theo tail number).
* **Observed:** Trong `artifacts/remediation/native_dual_core/run_manifest.json`, số chuyến bay là 30, và có 30 `synthetic_pairs_count`, 0 `verified_pairs_count`.
* **Impact:** Chưa có một tệp artifact chứng nhận duy nhất ghi nhận lượt chạy đồng thời trên 300 chuyến bay thật với tail-number matching hoàn hảo trong P07.
* **Proposed Resolution:** Chạy bổ sung một kịch bản 120–200 chuyến bay với module ghép cặp tail-number thật trong thư mục kiểm toán nếu cần thiết minh chứng.
* **Confidence:** `HIGH`

### FINDING-P2-02: Bộ giải Lai Hybrid (CP-SAT + SA) Không Mang lại Cải thiện nào so với CP-SAT Thuần túy
* **Severity:** `P2 (MEDIUM)`
* **Expected:** Khóa luận cần làm rõ vai trò thực tế của SA khi kết hợp với CP-SAT.
* **Observed:** Bằng chứng thực nghiệm tại `aggregate_metrics.json` chứng minh 100% nghiệm của Hybrid trùng khít với CP-SAT.
* **Impact:** Cần điều chỉnh kết luận trong bài viết khóa luận để phản ánh đúng bản chất toán học: SA đóng vai trò là thuật toán dự phòng (metaheuristic fallback) khi không có solver thương mại/chính xác, chứ không nâng cao được nghiệm tối ưu của CP-SAT.
* **Confidence:** `HIGH`
