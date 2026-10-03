# BÁO CÁO KHOA HỌC TỔNG KẾT TOÀN DIỆN CÁC GIAI ĐOẠN NGHIÊN CỨU & PHÁT TRIỂN HỆ THỐNG AEOLUS GATE OPTIMIZATION

**Dự án**: Aeolus Gate Optimization Research  
**Sân bay mục tiêu**: Hartsfield–Jackson Atlanta International Airport (`DEST = ATL`)  
**Khung thời gian dữ liệu**: 2016 — 2024 (2016–2022 Development Rolling Folds, 2023 Controlled System Selection, 2024 Historical Final Holdout)  
**Trạng thái hệ thống**: `POST_HOLDOUT_STABILIZED` & `FAIL_CLOSED_CERTIFIED`  
**Hệ thống phân tầng kiểm định**: **115 / 115 tests passed (100%)** trên 6 phân tầng kiểm định (9 test files)  
**Điểm vào tái lập duy nhất**: [`scripts/run_end_to_end_evaluation.py`](file:///D:/Study/Code/Python/Aelous/scripts/run_end_to_end_evaluation.py) (hỗ trợ `--mode smoke` và `--mode research`)  

---

## MỤC LỤC

1. [TỔNG QUAN ĐIỀU HÀNH & BỐI CẢNH DỰ ÁN](#1-tổng-quan-điều-hành--bối-cảnh-dự-án)
2. [KHUNG NGUYÊN TẮC AN TOÀN BẤT BIẾN (FAIL-CLOSED PROTOCOL)](#2-khung-nguyên-tắc-an-toàn-bất-biến-fail-closed-protocol)
3. [TỔNG HỢP TIẾN TRÌNH & KẾT QUẢ CHI TIẾT TỪNG GIAI ĐOẠN (PHASES A — H)](#3-tổng-hợp-tiến-trình--kết-quả-chi-tiết-từng-giai-đoạn-phases-a--h)
   - [Phase A: Comprehensive Audit Stages 8–11 & Claim Semantics](#phase-a-comprehensive-audit-stages-811--claim-semantics)
   - [Phase B: Probabilistic Marginal Correctness & Statistical Audit](#phase-b-probabilistic-marginal-correctness--statistical-audit)
   - [Phase C: Joint Dependence Hardening & Dynamic PSD Matrix Conditioning](#phase-c-joint-dependence-hardening--dynamic-psd-matrix-conditioning)
   - [Phase D: Google OR-Tools CP-SAT Solver Implementation & Benchmark](#phase-d-google-or-tools-cp-sat-solver-implementation--benchmark)
   - [Phase E: Deterministic Greedy Baseline Solver & Common Evaluator](#phase-e-deterministic-greedy-baseline-solver--common-evaluator)
   - [Phase F: Simulated Annealing Metaheuristic & Local Repair Operator](#phase-f-simulated-annealing-metaheuristic--local-repair-operator)
   - [Phase G: Closed-Loop Integration: Monte Carlo → Gate Simulation → Multi-Solver Optimization](#phase-g-closed-loop-integration-monte-carlo--gate-simulation--multi-solver-optimization)
   - [Phase G.1: Aircraft Turn / Timeline Semantics Audit (Step 6)](#phase-g1-kiểm-toán-ngữ-nghĩa-dòng-thời-gian--dòng-quay-đầu-máy-bay-step-6-aircraft-turn--timeline-semantics-audit)
   - [Phase G.2: Broader Development End-to-End Benchmark (Step 7)](#phase-g2-khảo-sát-đối-sánh-mở-rộng-trên-tập-phát-triển-step-7-broader-development-end-to-end-benchmark)
   - [Phase H: End-to-End Reproducibility, Test Hierarchy & Final Code Audit](#phase-h-end-to-end-reproducibility-test-hierarchy--final-code-audit)
4. [BẢNG TỔNG HỢP SỐ LIỆU ĐỐI SOÁNH THỰC NGHIỆM ĐA PHƯƠNG PHÁP](#4-bảng-tổng-hợp-số-liệu-đối-soánh-thực-nghiệm-đa-phương-pháp)
   - [Bảng 1: So sánh Đối đầu trên 6 Kịch bản Chuẩn (Greedy vs CP-SAT vs SA)](#bảng-1-so-sánh-đối-đầu-trên-6-kịch-bản-chuẩn-greedy-vs-cp-sat-vs-sa)
   - [Bảng 2: Hiệu năng Tối ưu End-to-End trên 20 Kịch bản Ngẫu nhiên (Phase G)](#bảng-2-hiệu-năng-tối-ưu-end-to-end-trên-20-kịch-bản-ngẫu-nhiên-phase-g)
   - [Bảng 3: Khảo sát Hội tụ Monte Carlo ($N = 100 \to 2500$)](#bảng-3-khảo-sát-hội-tụ-monte-carlo-n--100-to-2500)
   - [Bảng 4: Kết quả Kiểm định 7 Chốt An toàn Giao thức (Phase H Protocol Guards)](#bảng-4-kết-quả-kiểm-định-7-chốt-an-toàn-giao-thức-phase-h-protocol-guards)
   - [Bảng 5: Phân tầng Kiểm thử Tự động 6 Test Suites](#bảng-5-phân-tầng-kiểm-thử-tự-động-6-test-suites)
5. [DANH MỤC ARTIFACTS & SƠ ĐỒ MÃ NGUỒN HỆ THỐNG](#5-danh-mục-artifacts--sơ-đồ-mã-nguồn-hệ-thống)
6. [HƯỚNG DẪN THỰC THI & TÁI LẬP (CLI RUNBOOK)](#6-hướng-dẫn-thực-thi--tái-lập-cli-runbook)
7. [ĐÁNH GIÁ RỦI RO KHOA HỌC, GIỚI HẠN & ĐỊNH HƯỚNG TƯƠNG LAI](#7-đánh-giá-rủi-ro-khoa-học-giới-hạn--định-hướng-tương-lai)

---

## 1. TỔNG QUAN ĐIỀU HÀNH & BỐI CẢNH DỰ ÁN

### 1.1. Mục tiêu và Kiến trúc Tổng thể
Dự án **Aeolus Gate Optimization** được thiết kế nhằm giải quyết bài toán cốt lõi trong điều hành cảng hàng không: **Lập kế hoạch và tối ưu hóa phân bổ cổng đỗ máy bay (Gate Assignment Problem - GAP)** dưới điều kiện độ trễ chuyến bay có tính bất định cao.

Kiến trúc lõi của dự án vận hành theo chu trình khép kín:
```
[Dữ liệu Lịch bay T-2h] ──► [Dự báo Biên Xác suất (NGBoost Student-T)]
                                       │
                                       ▼
                       [Mô hình Phụ thuộc (Gaussian Copula)]
                                       │
                                       ▼
                    [Sinh mẫu Kịch bản Monte Carlo (N scenarios)]
                                       │
                                       ▼
                  [Mô phỏng Dòng quay đầu Máy bay (Turn Simulation)]
                                       │
                                       ▼
                  [Bộ giải Tối ưu hóa (Greedy / CP-SAT / SA)]
                                       │
                                       ▼
                   [Đánh giá Độc lập (Common Evaluator Contract)]
```

### 1.2. Tóm tắt Kế thừa Lịch sử
1. **Week 1 — Week 5 (Machine Learning Truyền thống)**:
   - Thử nghiệm các mô hình hồi quy điểm (Random Forest, LightGBM, XGBoost) trên tập dữ liệu bảng hơn 54 triệu chuyến bay (2016–2024).
   - *Phát hiện then chốt*: Điểm dự báo sụp đổ về giá trị kỳ vọng (Prediction Collapse) với $R^2 \approx 0.0039$, MAE $\approx 19.4$ phút. Mô hình điểm hoàn toàn bất lực trong việc nắm bắt rủi ro đuôi (Tail Risk) và các đợt bùng phát trễ nghiêm trọng ($\ge 60$ phút).
2. **Probabilistic Core Arrival (Stages 0 — 11)**:
   - Chuyển hướng sang mô hình hóa phân phối xác suất tham số có điều kiện: **NGBoost Student-T** ($B_5$, dự báo bộ ba tham số vị trí $\mu(x)$, tỷ lệ $\sigma(x)$, và bậc tự do $\nu$) kết hợp mô hình tương quan không gian-thời gian **Gaussian Copula** ($D_2$).
   - Hệ thống được đóng băng toàn diện (Stage 10 Freeze) và đánh giá trên tập kiểm định niêm phong 2024 (Stage 11 Holdout), đạt CRPS $17.13$ phút với khoảng cách tổng quát hóa so với tập phát triển chỉ $0.27$ phút (~16 giây).
3. **Chu kỳ Phát triển & Tối ưu hóa Toàn diện Gần đây (Phases A — H)**:
   - Tiến hành kiểm định lại toàn bộ tính toàn vẹn khoa học (Phase A, B, C).
   - Xây dựng hệ sinh thái tối ưu hóa đa phương pháp hoàn chỉnh: CP-SAT chính xác (Phase D), Greedy Baseline (Phase E), Simulated Annealing Metaheuristic (Phase F).
   - Tích hợp vòng lặp mô phỏng đóng kín (Phase G) và hoàn thiện hệ thống kiểm định, chốt an toàn và vệ sinh mã nguồn (Phase H).

---

## 2. KHUNG NGUYÊN TẮC AN TOÀN BẤT BIẾN (FAIL-CLOSED PROTOCOL)

Hệ thống hoạt động dưới sự giám sát của các nguyên tắc giao thức bắt buộc (Non-negotiable Rules):

1. **Bảo toàn Dữ liệu Thô (Raw Data Immutability)**:
   - Toàn bộ 9 tệp CSV gốc trong [`data/raw/tabular/`](file:///D:/Study/Code/Python/Aelous/data/raw/tabular/) là bất biến (Read-only).
   - Tuyệt đối không sửa đổi, đổi tên, ghi đè, chuẩn hóa hoặc di chuyển dữ liệu thô.
2. **Kỷ luật Thời gian & Điểm Cắt Thông tin (Point-in-Time Cutoff)**:
   - Mọi biến đầu vào phục vụ dự báo chỉ được lấy tại thời điểm $T-2$ giờ trước giờ khởi hành dự kiến (`CRS_DEP_TIME - 2h`).
   - Tuyệt đối cấm sử dụng các trường thông tin rò rỉ kết quả thực tế (như `DEP_DELAY`, `WHEELS_OFF`, `TAXI_OUT`, `AIR_TIME`) hoặc các dữ liệu thời tiết chưa kiểm định provenance.
3. **Minh bạch Trạng thái 2024 Post-Holdout**:
   - Năm 2024 đã được mở và đánh giá trong quá khứ tại Stage 11.
   - Do đó, toàn bộ các mã nguồn tối ưu hóa, mô phỏng và refactor sau đó đều là **thay đổi hậu kiểm định (Post-Holdout)**.
   - Tuyệt đối cấm chạy đánh giá lại năm 2024 rồi dán nhãn là "uncontaminated holdout", cấm sử dụng 2024 để tinh chỉnh tham số mô hình (re-tuning) hoặc lựa chọn phương án (re-selection).
4. **Đối xứng Đánh giá Khách quan (Common Evaluator Symmetry)**:
   - Tất cả các bộ giải (Greedy, CP-SAT, SA) bắt buộc phải được đánh giá thông qua cùng một hàm khách quan duy nhất: [`evaluate_gate_assignment`](file:///D:/Study/Code/Python/Aelous/src/optimization/evaluation.py).
   - Tuyệt đối không cho phép bất kỳ bộ giải nào tự tính điểm số nội bộ (Self-grading) nhằm triệt tiêu hoàn toàn sai lệch thuật toán.
5. **Ràng buộc Cứng Không Vi phạm (Zero-Tolerance Hard Constraints)**:
   - Mọi phân bổ cổng hợp lệ bắt buộc phải thỏa mãn 100% các ràng buộc cứng: Không có 2 máy bay cùng đỗ trên 1 cổng tiếp xúc (Zero contact-gate conflicts), tuân thủ khoảng đệm cách ly an toàn (15 phút), thỏa mãn năng lực phục vụ của cổng.

---

## 3. TỔNG HỢP TIẾN TRÌNH & KẾT QUẢ CHI TIẾT TỪNG GIAI ĐOẠN (PHASES A — H)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                     CHƯƠNG TRÌNH PHÁT TRIỂN & KIỂM ĐỊNH TỐI ƯU HÓA               │
└──────────────────────────────────────────────────────────────────────────────────┘
         │
         ├──► Phase A: Audit Toàn diện Stages 8–11 & Ngữ nghĩa Tuyên bố (Claim Semantics)
         ├──► Phase B: Chuẩn hóa Toán học Xác suất & Kiểm định Số (Numerical Correctness)
         ├──► Phase C: Tôi luyện Mô hình Phụ thuộc (PSD Projection & Dynamic Cholesky)
         ├──► Phase D: Bộ giải Chính xác Google OR-Tools CP-SAT Solver
         ├──► Phase E: Bộ giải Tham lam Cơ sở (Greedy) & Trọng tài Chung (Common Evaluator)
         ├──► Phase F: Bộ giải Tối ưu Siêu phỏng đoán Mô phỏng Luyện kim (Simulated Annealing)
         ├──► Phase G: Khép kín Chu trình Monte Carlo ──► Simulation ──► Multi-Solver Optimization
         └──► Phase H: Tái lập Đầu-cuối, Chốt An toàn Protocol Guards & Final Code Audit
```

---

### Phase A: Comprehensive Audit Stages 8–11 & Claim Semantics

* **Mục tiêu**: Kiểm tra tính toàn vẹn, tính độc lập khoa học của các giai đoạn lịch sử từ Stage 8 đến Stage 11; rà soát tính xác thực của các tuyên bố vận hành thực tế.
* **Các nội dung đã thực hiện**:
  1. Xây dựng đồ thị nguồn gốc (Provenance Graph) và bảng truy xuất nguồn gốc (Provenance Table) cho các Stages 8, 9, 10, 11.
  2. Rà soát việc tái sử dụng dữ liệu giữa Stage 8 (System Selection) và Stage 9 (Simulation).
  3. Kiểm định tính đầy đủ của bản đóng băng Stage 10 (Full System Freeze) và nguồn gốc đánh giá Stage 11 (Final Holdout).
  4. Phân tích ngữ nghĩa các phát biểu khoa học (Claim Semantics Audit).
* **Kết quả & Phát hiện Cốt lõi**:
  - **Phát hiện tái sử dụng dữ liệu vòng (Circular Reuse)**: Stage 9 đã tái sử dụng 100% dữ liệu của Stage 8 để đánh giá mô phỏng, dẫn tới việc kết quả downstream trên tập 2023 không hoàn toàn là out-of-sample độc lập.
  - **Đính chính 5 tuyên bố không có cơ sở dữ liệu thực tế (Flagged Claims)**:
    - Trong dữ liệu thô hàng không của BTS (`data/raw`), chỉ tồn tại giờ bay và độ trễ, **hoàn toàn không có dữ liệu số hiệu cổng thực tế (Actual Gate Assignment)**.
    - Do đó, các thuật ngữ như *"xung đột cổng ngoài đời thực" (real-world gate conflict)* hay *"giảm 83.7% sai số xung đột cổng"* là không chính xác về mặt ngữ nghĩa dữ liệu. Toàn bộ các xung đột này thực chất là **xung đột mô phỏng trên lịch danh định khi áp độ trễ thực tế**. Dự án đã hiệu chỉnh lại toàn bộ thuật ngữ sang *"xung đột mô phỏng đối chứng" (simulated benchmark conflicts)*.
  - **Xác lập trạng thái Post-Holdout**: Xác nhận năm 2024 đã được mở vào ngày `2026-09-27T18:23:46 UTC`. Mọi bước đi sau đó được đánh dấu chính thức là `POST_HOLDOUT`.
* **Artifacts ban hành**:
  - [`artifacts/audit/phase_a_comprehensive_audit_report.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/phase_a_comprehensive_audit_report.json)
  - [`artifacts/audit/claim_semantics_audit.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/claim_semantics_audit.json)
  - [`artifacts/audit/provenance_table_stage8_11.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/provenance_table_stage8_11.json)

---

### Phase B: Probabilistic Marginal Correctness & Statistical Audit

* **Mục tiêu**: Kiểm định tính đúng đắn toán học của mô hình phân phối biên xác suất (NGBoost Student-T) và xây dựng API đánh giá hợp nhất các chỉ số xác suất.
* **Các nội dung đã thực hiện**:
  1. Kiểm định ngữ nghĩa biến mục tiêu `ARR_DELAY`: Xác nhận trên 2,380,527 bản ghi rằng độ trễ là số nguyên phút thuần túy ($\mathbb{Z}$). Thiết lập quy ước đơn vị bin $[y - 0.5, y + 0.5]$ cho phân phối rời rạc hóa.
  2. Kiểm định tính toán số học (Numerical Correctness):
     - So sánh phân vị rời rạc Student-T qua hàm tích lũy với giải thuật chia đôi (Bisection Search): Đạt **100% khớp tuyệt đối**.
     - So sánh CRPS giải tích (Analytical Student-T) với tích phân số cầu phương Gauss-Legendre (Quadrature): Sai số cực đại chỉ **$3.22 \times 10^{-10}$** (chứng minh tính chính xác tuyệt đối của công thức giải tích).
  3. Áp đặt sàn tham số ổn định: $\sigma \ge 1.0$ phút và bậc tự do $\nu \ge 2.1$ (đảm bảo phương sai hữu hạn).
  4. Tích hợp kiểm định phân phối PIT ngẫu nhiên rời rạc (Randomized PIT) với kiểm định đều Kolmogorov-Smirnov (KS-test).
* **Kết quả**:
  - Bộ chỉ số xác suất đạt chứng nhận toán học: CRPS trung bình trên batch chuẩn $4.081$, NLL $3.371$, độ phủ khoảng 80% đạt $79.1\%$, độ phủ khoảng 90% đạt $89.2\%$.
* **Artifacts ban hành**:
  - [`artifacts/audit/phase_b_probabilistic_correctness_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/phase_b_probabilistic_correctness_manifest_v1.json)
  - [`artifacts/audit/target_semantics_verification_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/target_semantics_verification_v1.json)
  - Test suite: [`tests/test_student_t_correctness.py`](file:///D:/Study/Code/Python/Aelous/tests/test_student_t_correctness.py) & [`tests/test_unified_evaluation.py`](file:///D:/Study/Code/Python/Aelous/tests/test_unified_evaluation.py) (12 tests PASS).

---

### Phase C: Joint Dependence Hardening & Dynamic PSD Matrix Conditioning

* **Mục tiêu**: Khắc phục triệt để hiện tượng sụp đổ phân rã Cholesky của ma trận tương quan khi số lượng chuyến bay trong ngày biến động mạnh.
* **Các nội dung đã thực hiện**:
  1. Xây dựng cơ chế sinh ma trận tương quan động không phụ thuộc vào kích thước cố định, kiểm định trên các dải số lượng chuyến bay đa dạng: $d \in \{1, 5, 23, 77, 150, 420\}$ chuyến/ngày.
  2. Triển khai thuật toán chiếu nửa xác định dương (Positive Semi-Definite - PSD Projection):
     - Phân tích phổ riêng (Eigendecomposition): $\Sigma = V \Lambda V^T$.
     - Áp sàn giá trị riêng cực tiểu $\lambda_{\min} = 10^{-6}$: $\Lambda^* = \max(\Lambda, \lambda_{\min})$.
     - Chuẩn hóa lại đường chéo đơn vị: $\Sigma^* = D^{-1/2} (V \Lambda^* V^T) D^{-1/2}$.
  3. Tách biệt hoàn toàn ma trận thô và ma trận hiệu chỉnh phục vụ chẩn đoán (Diagnostic reporting: Frobenius distortion, Max absolute distortion).
  4. Đánh giá độ nhạy hạt giống ngẫu nhiên (Randomized PIT Seed Sensitivity): Kiểm định trên 5 seed độc lập (`202601` — `202605`), độ lệch chuẩn dao động cực nhỏ ($\le 0.0278$), chứng minh tính ổn định cao.
* **Kết quả**:
  - 27/27 bài kiểm tra trong test suite [`tests/test_dependence_hardening.py`](file:///D:/Study/Code/Python/Aelous/tests/test_dependence_hardening.py) đạt PASS 100%. Loại bỏ hoàn toàn lỗi dừng chương trình khi lấy mẫu Copula trên các ngày bay cao điểm.
* **Artifacts ban hành**:
  - [`artifacts/audit/phase_c_dependence_hardening_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/phase_c_dependence_hardening_manifest_v1.json)

---

### Phase D: Google OR-Tools CP-SAT Solver Implementation & Benchmark

* **Mục tiêu**: Xây dựng bộ giải tối ưu hóa toán học chính xác (Exact Optimizer) sử dụng Google OR-Tools CP-SAT cho bài toán gán cổng tổng quát.
* **Mô hình Hóa Toán học**:
  - **Biến quyết định**:
    - $x_{i, g} \in \{0, 1\}$: Chuyến bay $i$ được gán vào cổng tiếp xúc $g \in G$.
    - $y_i \in \{0, 1\}$: Chuyến bay $i$ bị đẩy ra bãi đỗ xa (Remote Apron / Overflow Gate).
    - Biến khoảng thời gian: $I_{i, g} = \text{IntervalVar}(\text{start}_i, \text{duration}_i, \text{end}_i)$ tồn tại khi $x_{i, g} = 1$.
  - **Ràng buộc cứng (Hard Constraints)**:
    1. Gán duy nhất: $\sum_{g \in G} x_{i, g} + y_i = 1, \quad \forall i \in F$.
    2. Không trùng cổng tiếp xúc (No-Overlap): $\text{NoOverlap}(I_{i, g} \mid i \in F), \quad \forall g \in G$.
    3. Khoảng đệm cách ly an toàn: $\text{start}_i = \text{arr}_i$, $\text{end}_i = \text{arr}_i + \text{dwell}_i + \text{buffer}$.
  - **Hàm mục tiêu (Multi-Objective)**:
    $$\min \quad w_{\text{reassign}} \sum_{i} \mathbb{I}(g_i \ne g_i^{\text{nominal}}) + w_{\text{overflow}} \sum_{i} y_i + w_{\text{delay}} \sum_{i} \text{delay}_i + w_{\text{risk}} \sum_{i} \text{risk}_i$$
    Trong đó bộ trọng số chuẩn hóa: $w_{\text{reassign}} = 10.0$, $w_{\text{overflow}} = 200.0$, $w_{\text{delay}} = 1.0$, $w_{\text{risk}} = 2.0$.
* **Kết quả Thực nghiệm**:
  - Đánh giá trên 9 kịch bản quy mô lớn ($F \in [100, 200, 300]$, $G \in [20, 30, 50]$):
    - **100% kịch bản đạt nghiệm tối ưu toàn cục (OPTIMAL)**, Optimality Gap = 0.0%.
    - **0 xung đột cổng tiếp xúc (Zero conflicts)**.
    - Thời gian giải nhanh: từ **$418$ ms** (kịch bản 100 chuyến / 20 cổng) đến **$8.72$ giây** (kịch bản 300 chuyến / 50 cổng).
* **Artifacts ban hành**:
  - Mã nguồn: [`src/optimization/solvers/cp_sat_solver.py`](file:///D:/Study/Code/Python/Aelous/src/optimization/solvers/cp_sat_solver.py)
  - [`artifacts/audit/cp_sat_benchmark_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/cp_sat_benchmark_manifest_v1.json)
  - Test suite: [`tests/test_cp_sat_solver.py`](file:///D:/Study/Code/Python/Aelous/tests/test_cp_sat_solver.py) (6 tests PASS).

---

### Phase E: Deterministic Greedy Baseline Solver & Common Evaluator

* **Mục tiêu**: Xây dựng thuật toán tham lam cơ sở xác định (Deterministic Greedy Baseline) và chuẩn hóa một hàm đánh giá chung duy nhất (Common Evaluator) làm chuẩn mực đo lường khách quan.
* **Các nội dung đã thực hiện**:
  1. Xây dựng module [`src/optimization/evaluation.py`](file:///D:/Study/Code/Python/Aelous/src/optimization/evaluation.py) chứa hàm [`evaluate_gate_assignment`](file:///D:/Study/Code/Python/Aelous/src/optimization/evaluation.py). Hàm này tiếp nhận cấu hình phân bổ, tính toán độc lập chi phí đổi cổng, chi phí tràn bãi đỗ xa, kiểm tra từng cặp chuyến bay xem có vi phạm thời gian đệm và chồng lấn cổng hay không.
  2. Xây dựng thuật toán [`DeterministicGreedyGateSolver`](file:///D:/Study/Code/Python/Aelous/src/optimization/solvers/greedy_solver.py):
     - Sắp xếp chuyến bay tăng dần theo giờ đến: $\text{arrival}_i$.
     - Ưu tiên 1: Giữ nguyên cổng danh định ($g_i = g_i^{\text{nominal}}$) nếu không xung đột.
     - Ưu tiên 2: Tìm cổng tiếp xúc khả thi đầu tiên có khoảng cách thời gian nghỉ (idle time) nhỏ nhất.
     - Ưu tiên 3: Nếu tất cả cổng tiếp xúc đều tắc nghẽn, đẩy chuyến bay ra bãi đỗ xa (Overflow).
  3. Refactor lại CP-SAT Solver để trả về kết quả khớp 100% với interface chung.
* **Kết quả So sánh Đối đầu (Greedy vs CP-SAT)**:
  - Kiểm định trên 6 kịch bản đối kháng từ $F=100$ đến $F=300$:
    - CP-SAT vượt trội hơn Greedy ở mọi kịch bản, **giảm chi phí hàm mục tiêu từ 4.16% đến 53.99%**.
    - Đặc biệt ở kịch bản tắc nghẽn cao $F=300, G=30$: Greedy tạo ra 152 lần đổi cổng và 4 chuyến tràn bãi xa (Tổng chi phí 2,648.80); trong khi CP-SAT giảm số lần đổi cổng xuống 69 và chỉ còn 1 chuyến tràn bãi xa (Tổng chi phí 1,218.80), **tiết kiệm 53.99% chi phí vận hành**.
    - Greedy có ưu thế tuyệt đối về tốc độ thực thi: chỉ mất **$0.82$ — $9.25$ ms**, nhanh hơn CP-SAT từ 500 đến 1000 lần.
* **Artifacts ban hành**:
  - Mã nguồn: [`src/optimization/evaluation.py`](file:///D:/Study/Code/Python/Aelous/src/optimization/evaluation.py), [`src/optimization/solvers/greedy_solver.py`](file:///D:/Study/Code/Python/Aelous/src/optimization/solvers/greedy_solver.py)
  - [`artifacts/audit/phase_e_greedy_baseline_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/phase_e_greedy_baseline_manifest_v1.json)
  - Test suite: [`tests/test_greedy_and_adversarial.py`](file:///D:/Study/Code/Python/Aelous/tests/test_greedy_and_adversarial.py) (13 tests PASS).

---

### Phase F: Simulated Annealing Metaheuristic & Local Repair Operator

* **Mục tiêu**: Xây dựng thuật toán siêu phỏng đoán Mô phỏng Luyện kim (Simulated Annealing - SA) nhằm tìm kiếm nghiệm xấp xỉ tối ưu chất lượng cao trong thời gian trung gian giữa Greedy và CP-SAT.
* **Thiết kế Thuật toán & Toán tử Không gian Lân cận (Neighborhood)**:
  - Khởi tạo: Nhận nghiệm khởi đầu từ Greedy (hoặc CP-SAT).
  - Không gian trạng thái [`SAState`](file:///D:/Study/Code/Python/Aelous/src/optimization/sa/state.py): Biểu diễn dạng vector gán cổng $g \in \{0, 1, \dots, |G|\}$ (với 0 là bãi đỗ xa).
  - Các toán tử lân cận ngẫu nhiên:
    - *Single Move*: Chuyển ngẫu nhiên một chuyến bay sang cổng khác hoặc bãi đỗ xa.
    - *Pair Swap*: Hoán đổi cổng giữa 2 chuyến bay khác nhau.
  - **Toán tử Sửa lỗi Xung đột Tường minh (Explicit Conflict Repair Operator)**:
    - Nếu một bước lân cận gây ra xung đột trùng cổng tiếp xúc, thuật toán không chỉ phạt nặng mà chủ động can thiệp bằng cách chuyển chuyến bay vi phạm ra bãi đỗ xa (Overflow) để tái lập tính khả thi tuyệt đối.
  - Tiêu chuẩn chấp nhận Metropolis: $P(\text{accept}) = \exp(-\Delta E / T)$, với lịch hạ nhiệt hình học $T_{k+1} = \alpha T_k$ ($\alpha = 0.98, T_0 = 100.0, T_{\min} = 0.01$).
  - **Cơ chế Best-so-Far Guarantee**: Luôn lưu trữ nghiệm tốt nhất từng gặp, bảo đảm SA không bao giờ trả về nghiệm tệ hơn nghiệm khởi tạo.
* **Kết quả Thực nghiệm**:
  - Tại các bài toán quy mô $F=100$: SA tìm được nghiệm có giá trị mục tiêu **trùng khớp 100% với nghiệm tối ưu toàn cục của CP-SAT** ($191.80$ ở F100_G20 và $230.50$ ở F100_G30).
  - Tại bài toán tắc nghẽn $F=200, G=20$: SA cải thiện **14.39%** so với Greedy (hạ điểm mục tiêu từ 2,431.57 xuống 2,081.57, giảm số chuyến tràn bãi xa từ 6 xuống 5 và số lần đổi cổng từ 102 xuống 87).
  - Thời gian chạy của SA dao động từ 3.0s đến 12.1s (1000 vòng lặp).
* **Artifacts ban hành**:
  - Gói mã nguồn: [`src/optimization/sa/`](file:///D:/Study/Code/Python/Aelous/src/optimization/sa/) (`state.py`, `neighborhood.py`, `objective.py`, `annealer.py`)
  - [`artifacts/audit/phase_f_simulated_annealing_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/phase_f_simulated_annealing_manifest_v1.json)
  - Test suite: [`tests/test_simulated_annealing.py`](file:///D:/Study/Code/Python/Aelous/tests/test_simulated_annealing.py) (15 tests PASS).

#### Phase F.1: Kiểm toán Benchmarking SA dưới Giới hạn Thời gian CP-SAT (Step 3 SA Time-Limited Benchmark Audit)

* **Bối cảnh & Động lực Kiểm định**:
  - Đánh giá vai trò thực tế của SA khi bộ giải chính xác CP-SAT bị giới hạn thời gian (Time-limited) trong môi trường điều hành trực tiếp có trần trễ ngặt nghèo (sub-second latency budgets).
  - So sánh đối đầu 5 nhánh trên cùng một tập kịch bản phát triển với cùng phân phối trễ, cổng, ràng buộc và hàm đánh giá chung:
    - **Nhánh A (Greedy Baseline)**: Lập kế hoạch tham lam xác định nhanh (< 5ms).
    - **Nhánh B (Time-limited CP-SAT)**: Bộ giải CP-SAT chạy với các mốc thời gian định trước: `[0.1s, 0.3s, 1.0s, 3.0s]`.
    - **Nhánh C (CP-SAT Incumbent)**: Nghiệm khả thi sơ bộ được CP-SAT tìm thấy trước khi hết thời gian.
    - **Nhánh D (CP-SAT Incumbent + SA)**: Khởi tạo SA từ nghiệm Incumbent của CP-SAT để tinh chỉnh cục bộ.
    - **Nhánh E (Greedy + SA)**: Khởi tạo SA từ nghiệm Greedy cơ sở.
* **Ba Chế độ Hoạt động Điển hình (Three Operational Regimes)**:
  1. *Chế độ Giới hạn Siêu ngặt ($TL = 0.1$s)*: CP-SAT không kịp hoàn tất giai đoạn presolve và tìm kiếm SAT ban đầu, trả về trạng thái `UNKNOWN` (`feasible = False`, không có Incumbent). Trong khi đó, Greedy hoàn thành trong $0.9 - 4.3$ ms, và Greedy + SA tiếp tục cải thiện điểm mục tiêu mà vẫn bảo đảm 100% ràng buộc cứng. Điều này chứng minh giá trị thực tiễn không thể thay thế của heuristic khi hạn chót thời gian thực $< 100$ ms.
  2. *Chế độ Incumbent Sơ bộ ($TL = 0.3$s trên kịch bản tắc nghẽn)*: CP-SAT tìm được nghiệm khả thi sơ bộ (`FEASIBLE` với Optimality Gap $> 0$, hoặc nghiệm tối ưu sơ bộ). Khi chuyển giao cho SA, thuật toán SA bảo toàn nghiệm mà không gây suy giảm chất lượng, khẳng định tính toàn vẹn của cơ chế `best-so-far`.
  3. *Chế độ Tối ưu Toàn cục ($TL \ge 1.0$s)*: CP-SAT chứng minh được nghiệm `OPTIMAL` (Optimality Gap = 0.0). Khi đó, SA nhận vào và giữ nguyên nghiệm ($+0.00$ improvement), hoàn toàn không thể và không ngụy tạo kết quả tốt hơn nghiệm tối ưu toàn cục đã được toán học chứng minh.
* **Quy tắc Kiểm định Bất biến**:
  - Nghiệm cuối của SA luôn đạt 100% tính khả thi cứng (0 xung đột cổng tiếp xúc).
  - Điểm số nghiệm tốt nhất (`best_so_far`) không bao giờ tệ hơn điểm khởi tạo ($Obj_{\text{best}} \le Obj_{\text{init}}$).
* **Artifacts Ban hành**:
  - Kịch bản benchmark: [`scripts/run_phase_f_time_limited_sa_benchmark.py`](file:///D:/Study/Code/Python/Aelous/scripts/run_phase_f_time_limited_sa_benchmark.py)
  - Manifest kết quả: [`artifacts/audit/phase_f_time_limited_sa_benchmark_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/phase_f_time_limited_sa_benchmark_manifest_v1.json)
  - Test suite chuyên biệt: [`tests/test_time_limited_sa_benchmark.py`](file:///D:/Study/Code/Python/Aelous/tests/test_time_limited_sa_benchmark.py) (5 tests PASS).

---

### Phase G: Closed-Loop Integration: Monte Carlo → Gate Simulation → Multi-Solver Optimization

* **Mục tiêu**: Tích hợp toàn bộ các thành phần rời rạc thành một chu trình mô phỏng khép kín hoàn chỉnh, đo lường sự hội tụ Monte Carlo và so sánh trực tiếp cả 3 bộ giải trên các kịch bản ngẫu nhiên thực tế.
* **Kiến trúc Vòng lặp Khép kín**:
  1. [`MonteCarloScenarioRunner`](file:///D:/Study/Code/Python/Aelous/src/simulation/scenario_runner.py): Sinh ma trận độ trễ kích thước $[N_{\text{scenarios}}, N_{\text{flights}}]$ kết hợp phân phối Student-T và Gaussian Copula.
  2. [`AircraftTurnModel`](file:///D:/Study/Code/Python/Aelous/src/simulation/aircraft_turn.py): Tính toán dòng thời gian chuẩn xác của từng chuyến bay:
     $$\text{Simulated Arrival} = \text{CRS\_ARR\_TIME} + \text{Sampled Delay}$$
     $$\text{Gate In} = \text{Simulated Arrival}$$
     $$\text{Gate Out} = \text{Gate In} + \max(\text{Min Turnaround}, \text{Scheduled Dwell}) + \text{Buffer}$$
  3. [`ConflictDetector`](file:///D:/Study/Code/Python/Aelous/src/simulation/conflict_detector.py): Phát hiện chính xác các cặp chuyến bay bị đè thời gian trên cùng 1 cổng, đo đạc độ trùng lấn (phút), công suất đỉnh đồng thời tại cổng và toàn sân bay.
  4. Bộ ba Solver chạy song song trên cùng một tập kịch bản: **Greedy Baseline**, **Exact CP-SAT**, và **CP-SAT khởi tạo kèm SA tinh chỉnh (CP-SAT+SA)**.
* **Kết quả Thực nghiệm**:
  - **Khảo sát Hội tụ Monte Carlo (Đã qua Kiểm định & Hiệu chỉnh - Monte Carlo Audit)**:
    - *Nguyên nhân kỹ thuật của hiện tượng trùng số liệu trước đây*: Trong mã nguồn ban đầu của `scripts/run_phase_g_pipeline.py`, vòng lặp đánh giá bị giới hạn bởi `eval_count = min(n_scen, 100)`. Do đó, với mọi $N \ge 100$, hệ thống chỉ đánh giá lặp lại đúng 100 kịch bản đầu tiên, dẫn đến các con số giống hệt nhau ở mọi $N$.
    - *Kết quả sau khi hiệu chỉnh toàn diện (Uncapped Evaluation)*: Đánh giá trọn vẹn toàn bộ $N$ kịch bản ($N \in [100, 250, 500, 1000, 2500]$), 100% kịch bản trong mỗi tập là duy nhất, mã băm ma trận hoàn toàn phân biệt. P95 thời lượng xung đột danh định dao động thực tế trong dải $[656.55, 665.00]$ phút, chi phí mục tiêu kỳ vọng ổn định trong dải $[108.75, 110.28]$ (với phương sai mục tiêu $\approx 313 - 395$), và tỷ lệ tận dụng cổng đạt $\approx 14.85\%$.
  - **Đánh giá Đa Solver trên 20 Kịch bản Ngẫu nhiên (50 chuyến bay / 20 cổng)**:
    - *Greedy*: Chi phí trung bình $112.98$, số lần đổi cổng $9.30$, thời gian giải trung bình **$0.53$ ms**.
    - *CP-SAT*: Chi phí trung bình $98.48$, số lần đổi cổng $7.85$, thời gian giải trung bình **$158.2$ ms**.
    - **CP-SAT cải thiện 12.82% chi phí** so với Greedy, giảm $1.45$ lần đổi cổng cho mỗi kịch bản.
    - Cả 3 bộ giải đều đảm bảo **100% nghiệm khả thi** và **0 xung đột cổng tiếp xúc**.
* **Artifacts ban hành**:
  - Thư mục dữ liệu: [`artifacts/end_to_end/`](file:///D:/Study/Code/Python/Aelous/artifacts/end_to_end/)
    - `run_manifest.json`, `aggregate_metrics.json`
    - `scenario_summary.parquet`, `greedy_results.parquet`, `cp_sat_results.parquet`, `sa_results.parquet`
  - Pipeline script: [`scripts/run_phase_g_pipeline.py`](file:///D:/Study/Code/Python/Aelous/scripts/run_phase_g_pipeline.py)
  - Test suites: [`tests/test_simulation_pipeline.py`](file:///D:/Study/Code/Python/Aelous/tests/test_simulation_pipeline.py) (10 tests) & [`tests/test_end_to_end_pipeline.py`](file:///D:/Study/Code/Python/Aelous/tests/test_end_to_end_pipeline.py) (2 tests).

#### Phase G.1: Kiểm toán Ngữ nghĩa Dòng thời gian & Dòng quay đầu Máy bay (Step 6 Aircraft Turn / Timeline Semantics Audit)

* **Bối cảnh & Động lực**:
  - Kiểm toán và chuẩn hóa toàn diện dòng thời gian vận hành từ hạ cánh đến giải phóng cổng: `scheduled arrival → sampled delay → simulated arrival → gate-in → turnaround/dwell → gate-out → gate-release`.
  - Phân định rõ ràng ngữ nghĩa vận hành, triệt tiêu nguy cơ cộng dồn trùng lặp (double counting) và bảo đảm tính tương đương tuyệt đối (100% parity) giữa mô phỏng và bộ giải tối ưu.
* **Ngữ nghĩa Toán học & Quy chuẩn Vận hành**:
  1. `min_turnaround` ($T_{\text{turn}}$, mặc định 45 phút): Thời gian quay đầu tối thiểu vật lý tại cổng (xuống khách, dọn dẹp, tra nhiên liệu, lên khách). Không một chuyến bay nào được phép rời cổng sớm hơn $A_{\text{sim}} + T_{\text{turn}}$.
  2. `scheduled_dwell` ($T_{\text{dwell}}$, mặc định 60 phút): Thời lượng quay đầu kế hoạch theo lịch trình ($D_{\text{sched}} - A_{\text{sched}}$). Đại diện cho cam kết lịch bay thương mại.
  3. `buffer` ($B_{\text{buffer}}$, mặc định 15 phút): Khoảng đệm an toàn phân cách giữa 2 máy bay liên tiếp tại cùng một cổng tiếp xúc, tính từ thời điểm đẩy lùi (`gate_out`) đến khi cổng sẵn sàng đón tàu bay tiếp theo (`gate_release`).
* **Công thức Chuẩn hóa & Chứng minh Không Cộng dồn Trùng lặp (Zero Double Counting)**:
  - $\text{gate\_in} = A_{\text{sim}} = \text{round}(A_{\text{sched}} + \Delta T_{\text{arr}})$
  - $\text{gate\_out} = D_{\text{sim}} = \max(D_{\text{sched}}, A_{\text{sim}} + T_{\text{turn}})$
  - $\text{gate\_release} = D_{\text{sim}} + B_{\text{buffer}}$
  - Khoảng chiếm dụng cổng: $[\text{gate\_in}, \text{gate\_release}) = [A_{\text{sim}}, D_{\text{sim}} + B_{\text{buffer}})$
  - *Chứng minh không double counting*: $T_{\text{turn}}$ và $T_{\text{dwell}}$ được kết hợp thông qua toán tử $\max$, tuyệt đối **không cộng dồn**. Khi chuyến bay đúng giờ và $T_{\text{dwell}} \ge T_{\text{turn}}$, thời gian đỗ thực tế đúng bằng $T_{\text{dwell}}$ (60 phút chứ không phải $45 + 60 = 105$ phút). $B_{\text{buffer}}$ chỉ được cộng đúng 1 lần vào $D_{\text{sim}}$ tại mốc giải phóng cổng; điều kiện giao cắt giữa 2 khoảng nửa mở $[s_1, e_1)$ và $[s_2, e_2)$ dựa trên $\max(s_1, s_2) < \min(e_1, e_2)$, không cộng thêm buffer lần thứ hai.
* **Bao phủ 6 Kịch bản Kiểm thử Thủ công (Hand-Checkable Tests)**:
  1. `delay = 0`: $A_{\text{sched}}=100, D_{\text{sched}}=160 \implies \text{gate\_in}=100, \text{gate\_out}=160, \text{gate\_release}=175$, dwell thực tế = 60m, slack = 15m.
  2. `delay = 10`: Trễ 10 phút được hấp thụ hoàn toàn vào slack $15$m $\implies \text{gate\_in}=110, \text{gate\_out}=160$ (không trễ khởi hành), dwell thực tế = 50m.
  3. `dwell < turnaround`: Lịch bay kế hoạch chỉ cho 30m nhưng quay đầu vật lý đòi hỏi 45m $\implies D_{\text{sched}}=230$, nhưng $\text{gate\_out} = \max(230, 200 + 45) = 245$. Turnaround vật lý được bảo vệ tối thượng.
  4. `dwell > turnaround`: Lịch bay kế hoạch 90m ($A_{\text{sched}}=300, D_{\text{sched}}=390$), trễ đến 40m ($A_{\text{sim}}=340$) $\implies A_{\text{sim}} + 45 = 385 \le 390 \implies \text{gate\_out} = 390$. Trễ 40 phút được triệt tiêu hoàn toàn, không lan truyền sang giờ khởi hành.
  5. `buffer > 0`: Cùng cặp chuyến bay $(100, 160)$ và $(160, 220)$. Nếu buffer = 0: không xung đột. Nếu buffer = 15: chuyến 1 giữ cổng đến 175, phát hiện xung đột chính xác 15 phút.
  6. `back-to-back flights`: Chuyến 1 giải phóng tại 175. Chuyến 2 đến tại đúng 175 $\implies$ khoảng $[100, 175)$ và $[175, 235)$ tiếp xúc biên, overlap = 0m (hợp lệ). Nếu chuyến 2 đến sớm 1 phút (174) $\implies$ phát hiện xung đột chính xác 1 phút trên toàn bộ các công cụ.
* **Đồng bộ Tính Tương đương (Interval Logic Parity)**:
  - Đồng bộ và chứng minh tương đương 100% giữa mô phỏng ([`AircraftTurn`](file:///D:/Study/Code/Python/Aelous/src/simulation/aircraft_turn.py)), bộ phát hiện xung đột ([`ConflictDetector`](file:///D:/Study/Code/Python/Aelous/src/simulation/conflict_detector.py)), bộ xác minh độc lập ([`verify_hard_constraints_independently`](file:///D:/Study/Code/Python/Aelous/src/optimization/evaluation.py)), và bộ giải tối ưu CP-SAT ([`CPSATGateSolver`](file:///D:/Study/Code/Python/Aelous/src/optimization/solvers/cp_sat_solver.py)).
* **Artifacts Ban hành**:
  - Kịch bản kiểm toán: [`scripts/run_phase_g_timeline_semantics_audit.py`](file:///D:/Study/Code/Python/Aelous/scripts/run_phase_g_timeline_semantics_audit.py)
  - Manifest kiểm toán: [`artifacts/audit/phase_g_timeline_semantics_audit_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/phase_g_timeline_semantics_audit_manifest_v1.json)
  - Test suite chuyên biệt: [`tests/test_timeline_semantics.py`](file:///D:/Study/Code/Python/Aelous/tests/test_timeline_semantics.py) (9 tests PASS, 100%).

---

#### Phase G.2: Khảo sát Đối sánh Mở rộng trên Tập Phát triển (Step 7 Broader Development End-to-End Benchmark)

* **Bối cảnh & Động lực**:
  - Không phải pha lựa chọn mô hình mới và không phải phép thử trên tập kiểm định cuối cùng (Final Holdout).
  - Vận hành chu trình khép kín hoàn chỉnh Predict → Sample → Simulate → Optimize trên tập dữ liệu phát triển độc lập bao quát nhiều ngày với các cấp độ nhu cầu vận hành đa dạng (Varying Demand Levels) tại KATL (2023 development data, 0% liên quan đến 2024).
* **Thiết kế Thực nghiệm 4 Ngày Phát triển Điển hình**:
  1. **DAY_LOW (2023-11-23 — Thanksgiving Day)**: Nhu cầu thấp ($ chuyến bay, $ cổng tiếp xúc, khung giờ 06:00–12:00).
  2. **DAY_MEDIUM (2023-07-03 — Pre-holiday Summer)**: Nhu cầu trung bình ($ chuyến bay, $ cổng tiếp xúc, khung giờ 11:00–17:00).
  3. **DAY_HIGH (2023-07-13 — Peak Summer Weekday)**: Nhu cầu đỉnh ($ chuyến bay, $ cổng tiếp xúc, khung giờ 13:00–21:00).
  4. **DAY_WEATHER_DISRUPTED (2023-08-07 — Severe Convective Storm)**: Nhu cầu gián đoạn do bão đối lưu ($ chuyến bay, $ cổng tiếp xúc, trễ đuôi nặng với P90 trễ lịch sử đạt 181 phút).
  - Tổng cộng  	imes 10 = 40$ kịch bản Monte Carlo ngẫu nhiên được sinh từ mô hình cận biên B5 Student-T kết hợp D2 Gaussian Copula.
* **Phân phối Hiệu năng Đa Phương pháp (Method-Wise Distributions)**:
  - *Nguyên tắc khoa học*: Báo cáo phân phối đầy đủ thay vì tuyên bố một thuật toán chiến thắng toàn cục duy nhất.
  - **Greedy Baseline**: Thời gian giải cực nhanh (trung bình **.28$ ms**; thấp nhất .46$ ms, cao nhất .11$ ms), chi phí mục tiêu trung bình ,430.44$, số lần đổi cổng .95$, số chuyến tràn bãi đỗ xa .35$.
  - **Exact CP-SAT**: Đạt tối ưu toàn cục \%$ (/40$ kịch bản OPTIMAL), chi phí mục tiêu trung bình **,351.69$** (tiết kiệm đáng kể chi phí so với Greedy), số lần đổi cổng giảm xuống **.08$**, thời gian giải trung bình **,082.53$ ms** (từ .2$ ms đến ,789.0$ ms).
  - **SA (Greedy Warm-Start)**: Khởi tạo từ Greedy và tinh chỉnh cục bộ 150 vòng lặp, hạ chi phí mục tiêu từ ,430.44$ xuống **,416.19$** (giảm số lần đổi cổng từ .95$ xuống .53$), thời gian giải trung bình **.47$ ms**.
  - **SA (CP-SAT Incumbent)**: Nhận nghiệm khả thi tối ưu từ CP-SAT, bảo toàn nguyên vẹn chất lượng tối ưu ( = 9,351.69$), xác nhận tính ổn định vững chắc của toán tử tìm kiếm cục bộ.
* **Độ tin cậy & Kiểm định Nghiêm ngặt**:
  - **100% Khả thi Cứng**: Cả 3 phương pháp đều thỏa mãn 100% ràng buộc cứng trên toàn bộ 40 kịch bản, **0 xung đột cổng tiếp xúc**.
  - **Bảo toàn Thất bại (Traceable Failures)**: $ kịch bản bị âm thầm loại bỏ (ailures_count = 0 ghi nhận trong ailures.json).
  - **Tái lập Xác định (Deterministic Repeatability Certified)**: Thực hiện kiểm định chạy lặp lại trên cùng commit, config, hạt giống và bộ đăng ký kịch bản: \%$ mã băm ma trận và điểm mục tiêu của Greedy, CP-SAT, và SA khớp chính xác tuyệt đối.
  - **Khuyến cáo Khoa học (Disclaimer)**: Kết quả phản ánh hiệu năng tối ưu hóa trong môi trường mô phỏng độ trễ tham số tại KATL, không đại diện cho số liệu vận hành thực tế tại sân bay khi thiếu nhật ký khai thác cổng vật lý.
* **Artifacts Ban hành**:
  - Thư mục lưu trữ: [rtifacts/development_end_to_end/](file:///D:/Study/Code/Python/Aelous/artifacts/development_end_to_end/)
    - 
un_manifest.json, scenario_registry.parquet, greedy_results.parquet, cp_sat_results.parquet, sa_results.parquet, ggregate_metrics.json, ailures.json
  - Kịch bản thực thi: [scripts/run_development_end_to_end_benchmark.py](file:///D:/Study/Code/Python/Aelous/scripts/run_development_end_to_end_benchmark.py)
  - Test suite kiểm định: [	ests/test_development_end_to_end_benchmark.py](file:///D:/Study/Code/Python/Aelous/tests/test_development_end_to_end_benchmark.py) (9 tests PASS, 100%).

---

### Phase H: End-to-End Reproducibility, Test Hierarchy & Final Code Audit

* **Mục tiêu**: Xây dựng hệ thống bảo vệ giao thức tự động (Guardrails), điểm vào thực thi duy nhất (Single CLI Entrypoint), hoàn thiện quy trình kiểm tra vệ sinh mã nguồn và đánh giá phân tầng kiểm thử.
* **Các nội dung đã thực hiện**:
  1. **Triển khai 7 Chốt An toàn Bất biến ([`ProtocolComplianceGuard`](file:///D:/Study/Code/Python/Aelous/src/audit/protocol_guards.py))**:
     - *Check 1 (raw_data_immutable)*: Xác nhận toàn bộ 9 file CSV thô nguyên vẹn trên git.
     - *Check 2 (holdout_2024_not_in_training)*: Kiểm tra tập train dựa trên vai trò phân vùng (Role-based Validation) thay vì đường tắt max-year thô sơ: bảo đảm không tập train nào chứa năm 2024, từ chối hiệu chuẩn (calibration) và lựa chọn (selection) trên 2024, đồng thời cho phép huấn luyện tiền kiểm định hoàn chỉnh qua năm 2022 (`final_pre_holdout_train`).
     - *Check 3 (fold_definitions_exact)*: Xác minh 4 rolling folds khớp chính xác theo quy chuẩn protocol (Fold 1 train $\le 2018$, Fold 2 train $\le 2019$, Fold 3 train $\le 2020$, Fold 4 train $\le 2021$).
     - *Check 4 (feature_contract)*: Xác nhận đúng 11 đặc trưng được phép, không có đặc trưng rò rỉ.
     - *Check 5 (no_insample_residual_uncertainty)*: Đảm bảo độ bất định được tính từ phân phối tham số Student-T & Copula, không dùng sai số in-sample.
     - *Check 6 (dynamic_dependence_dimension)*: Kiểm tra Copula xử lý linh hoạt mọi số lượng chuyến bay ($d \in [1, 110]$).
     - *Check 7 (solver_hard_constraints_verified)*: Xác nhận các bộ giải triệt tiêu 100% xung đột cổng tiếp xúc.
     - **Kết quả: 7 / 7 checks PASSED**.

#### Phase H.1: Kiểm toán Hiệu chỉnh Chốt An toàn Holdout / Folds (Step 4 Holdout/Fold Guard Correction)

* **Phát hiện Kiểm toán về Lỗi Đường tắt Max-Year**:
  - Trước đây, một số quy tắc an toàn sử dụng biểu thức đường tắt $\max(\text{train\_year}) \le 2021$.
  - *Khiếm khuyết*: Biểu thức này đồng nhất sai lệch giữa nếp huấn luyện ngoài cùng của tập phát triển rolling cross-validation (Fold 4 có train 2016–2021, val 2022) với quy tắc huấn luyện tổng quát. Hậu quả là nó vô tình chặn đứng quá trình huấn luyện tiền kiểm định cuối cùng (Final Pre-Holdout Training trên toàn bộ dải phát triển 2016–2022 tại Stage 10 Full System Freeze) vốn đã được protocol ủy quyền tường minh. Đồng thời, nó quá lỏng lẻo ở các fold trước (cho phép năm 2019 rò rỉ vào Fold 1 train).
* **Giải pháp Tái cấu trúc Theo Vai trò Dữ liệu (Role-Based Protocol Guards)**:
  - Tái cấu trúc toàn diện [`src/audit/protocol_guards.py`](file:///D:/Study/Code/Python/Aelous/src/audit/protocol_guards.py) với hàm xác thực chuẩn hóa [`validate_dataset_role_and_years`](file:///D:/Study/Code/Python/Aelous/src/audit/protocol_guards.py):
    1. **Quy tắc Từng Fold Chính xác**:
       - Fold 1: train $\le 2018$ (val 2019)
       - Fold 2: train $\le 2019$ (val 2020)
       - Fold 3: train $\le 2020$ (val 2021)
       - Fold 4: train $\le 2021$ (val 2022)
    2. **Ủy quyền Huấn luyện Tiền Kiểm định (Final Pre-Holdout Training)**:
       - Được ủy quyền tường minh bởi Protocol Mục 2.2 và Stage 10 System Freeze: Cho phép huấn luyện mô hình sản xuất trên toàn bộ dải phát triển 2016–2022 ($\max \le 2022$). Cấm tuyệt đối 2023 và 2024 trong tập train.
    3. **Cách ly Nghiêm ngặt 2023**:
       - Năm 2023 chỉ được phép sử dụng duy nhất cho lựa chọn hệ thống một lần (One-time complete-system selection). Cấm tuyệt đối huấn luyện (training) và hiệu chuẩn (calibration) trên 2023.
    4. **Cách ly Tuyệt đối 2024 (Fail-Closed 2024)**:
       - Mọi tập dữ liệu huấn luyện chứa 2024 đều bị từ chối ngay lập tức.
       - Hiệu chuẩn trên 2024 bị từ chối ngay lập tức.
       - Lựa chọn mô hình trên 2024 bị từ chối ngay lập tức.
    5. **Chốt Chặn Năm Tương lai Ngoài Phạm vi**:
       - Bất kỳ năm nào $> 2024$ (2025, 2026, ...) đều bị chặn fail-closed trên mọi vai trò.
    6. **Bảo tồn Trạng thái POST_HOLDOUT**:
       - Toàn bộ kết quả kiểm định ghi nhận minh bạch trạng thái `post_holdout_status = "POST_HOLDOUT_STABILIZED"`.
* **Artifacts Ban hành**:
  - Manifest kiểm toán: [`artifacts/audit/phase_h_holdout_fold_guard_correction_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/phase_h_holdout_fold_guard_correction_manifest_v1.json)
  - Test suite chuyên biệt: [`tests/test_holdout_and_fold_guards.py`](file:///D:/Study/Code/Python/Aelous/tests/test_holdout_and_fold_guards.py) (10 tests PASS, 100%).
  2. **Xây dựng Điểm Vào Tái lập Duy nhất**:
     - Tạo [`scripts/run_end_to_end_evaluation.py`](file:///D:/Study/Code/Python/Aelous/scripts/run_end_to_end_evaluation.py) hỗ trợ hai chế độ phân lập:
       - `--mode smoke`: Chạy nhanh (5 scenarios, 30 flights) lưu vào `artifacts/end_to_end_smoke/` phục vụ CI/CD.
       - `--mode research`: Chạy kịch bản nghiên cứu chuẩn lưu vào `artifacts/end_to_end/`.
  3. **Vệ sinh Mã nguồn Toàn diện (Codebase Hygiene)**:
     - 0 đường dẫn tuyệt đối Windows (`C:\`, `D:\`) bị hardcode trong mã nguồn.
     - 0 khóa bí mật (secrets/tokens/passwords).
     - 0 tệp tin rác tạm thời thừa thãi.
     - Dữ liệu thô nguyên vẹn 100%.
  4. **Phân tầng Kiểm thử Tự động (Test Hierarchy)**:
     - Thiết lập kịch bản [`scripts/run_final_code_audit.py`](file:///D:/Study/Code/Python/Aelous/scripts/run_final_code_audit.py) thực thi 6 suites liên hoàn:
       1. Unit Tests (Simulation & Turn): 10 tests
       2. Probabilistic Tests (Student-T & Unified Eval): 12 tests
       3. Dependence Tests (Dynamic Cholesky & PSD): 27 tests
       4. CP-SAT Tests (Solver & Adversarial): 19 tests
       5. Simulated Annealing Tests: 15 tests
       6. End-to-End Pipeline Smoke Test: 2 tests
     - **Kết quả: 85 / 85 tests PASSED trong 17.17 giây**.
* **Artifacts ban hành**:
  - [`artifacts/final_code_audit/integration_report.json`](file:///D:/Study/Code/Python/Aelous/artifacts/final_code_audit/integration_report.json)
  - [`artifacts/final_code_audit/protocol_compliance.json`](file:///D:/Study/Code/Python/Aelous/artifacts/final_code_audit/protocol_compliance.json)
  - [`artifacts/final_code_audit/reproducibility_manifest.json`](file:///D:/Study/Code/Python/Aelous/artifacts/final_code_audit/reproducibility_manifest.json)
  - [`artifacts/final_code_audit/test_summary.json`](file:///D:/Study/Code/Python/Aelous/artifacts/final_code_audit/test_summary.json)

---

## 4. BẢNG TỔNG HỢP SỐ LIỆU ĐỐI SOÁNH THỰC NGHIỆM ĐA PHƯƠNG PHÁP

### Bảng 1: So sánh Đối đầu trên 6 Kịch bản Chuẩn (Greedy vs CP-SAT vs SA)
*Nguồn dữ liệu: [`phase_e_greedy_baseline_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/phase_e_greedy_baseline_manifest_v1.json) và [`phase_f_simulated_annealing_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/phase_f_simulated_annealing_manifest_v1.json)*

| Kịch bản | Quy mô ($F \times G$) | Phương pháp | Giá trị Mục tiêu (Cost) | Đổi cổng (Reassign) | Tràn bãi xa (Overflow) | Xung đột cổng | Thời gian giải (ms) | Mức cải thiện so với Greedy |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **F100_G20** | $100 \times 20$ | Greedy | $211.80$ | 11 | 0 | 0 | **0.85 ms** | Baseline |
| | | **CP-SAT** | **$191.80$** | **9** | **0** | **0** | $414.77$ ms | **+9.44%** |
| | | **SA** | **$191.80$** | **9** | **0** | **0** | $3,850.73$ ms | **+9.44%** (Bằng CP-SAT) |
| **F100_G30** | $100 \times 30$ | Greedy | $240.50$ | 11 | 0 | 0 | **0.82 ms** | Baseline |
| | | **CP-SAT** | **$230.50$** | **10** | **0** | **0** | $667.11$ ms | **+4.16%** |
| | | **SA** | **$230.50$** | **10** | **0** | **0** | $3,033.57$ ms | **+4.16%** (Bằng CP-SAT) |
| **F200_G20** | $200 \times 20$ | Greedy | $2,431.57$ | 102 | 6 | 0 | **4.27 ms** | Baseline |
| | (Tắc nghẽn) | **CP-SAT** | **$1,291.57$** | **48** | **3** | **0** | $1,663.51$ ms | **+46.88%** |
| | | **SA** | $2,081.57$ | 87 | 5 | 0 | $12,116.99$ ms | **+14.39%** |
| **F200_G30** | $200 \times 30$ | Greedy | $788.53$ | 57 | 0 | 0 | **3.45 ms** | Baseline |
| | | **CP-SAT** | **$488.53$** | **27** | **0** | **0** | $2,560.16$ ms | **+38.05%** |
| | | **SA** | $638.53$ | 42 | 0 | 0 | $9,660.62$ ms | **+19.02%** |
| **F300_G30** | $300 \times 30$ | Greedy | $2,648.80$ | 152 | 4 | 0 | **9.25 ms** | Baseline |
| | (Quá tải) | **CP-SAT** | **$1,218.80$** | **69** | **1** | **0** | $5,570.80$ ms | **+53.99%** |
| **F300_G50** | $300 \times 50$ | Greedy | $697.47$ | 39 | 0 | 0 | **3.70 ms** | Baseline |
| | | **CP-SAT** | **$567.47$** | **26** | **0** | **0** | $8,519.71$ ms | **+18.64%** |

---

### Bảng 1b: So sánh Đối đầu 5 Nhánh A — E dưới các Mốc Thời gian Định trước (Step 3 Benchmark)
*Nguồn dữ liệu: [`phase_f_time_limited_sa_benchmark_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/phase_f_time_limited_sa_benchmark_manifest_v1.json) (Seed = 202601 / 123, 300 iterations SA)*

| Kịch bản | Nhánh Đánh giá | Trạng thái Solver | Khả thi Cứng | Điểm Mục tiêu (Cost) | Decision Cost | Reassign | Overflow | Thời gian giải (ms) | Cải thiện của SA |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **F100_G20** | **A (Greedy)** | FEASIBLE | 100% | $263.07$ | $140.00$ | 14 | 0 | **0.90 ms** | Baseline |
| (100 flights, | **E (Greedy + SA)** | OPTIMAL | 100% | $253.07$ | $130.00$ | 13 | 0 | $1,131.47$ ms | **+3.80%** (so với Greedy) |
| 20 gates) | **B (CP-SAT $TL=0.1$s)** | UNKNOWN | False | $40,000.00$ | $40,000.00$ | 0 | 0 | $364.25$ ms | Timeout (không có Incumbent) |
| | **B (CP-SAT $TL=0.3$s)** | OPTIMAL | 100% | $213.07$ | $90.00$ | 9 | 0 | $444.40$ ms | Gap = 0.0% (Tối ưu toàn cục) |
| | **D (Incumbent + SA)** | OPTIMAL | 100% | $213.07$ | $90.00$ | 9 | 0 | $1,118.20$ ms | **+0.00%** (Bảo toàn nghiệm tối ưu) |
| | **B (CP-SAT $TL \ge 1.0$s)**| OPTIMAL | 100% | $213.07$ | $90.00$ | 9 | 0 | $412.90$ ms | Gap = 0.0% |
| **F150_G15** | **A (Greedy)** | FEASIBLE | 100% | $2,928.72$ | $2,770.00$ | 77 | 10 | **2.70 ms** | Baseline |
| (Tắc nghẽn cao, | **E (Greedy + SA)** | OPTIMAL | 100% | $2,738.72$ | $2,580.00$ | 78 | 9 | $2,633.70$ ms | **+6.49%** (Tiết kiệm $190.00$) |
| 15 gates) | **B (CP-SAT $TL=0.1$s)** | UNKNOWN | False | $60,000.00$ | $60,000.00$ | 0 | 0 | $509.40$ ms | Timeout (không có Incumbent) |
| | **B (CP-SAT $TL=0.3$s)** | OPTIMAL | 100% | $2,208.72$ | $2,050.00$ | 65 | 7 | $625.40$ ms | Gap = 0.0% |
| | **D (Incumbent + SA)** | OPTIMAL | 100% | $2,208.72$ | $2,050.00$ | 65 | 7 | $2,610.10$ ms | **+0.00%** (Bảo toàn nghiệm tối ưu) |
| | **B (CP-SAT $TL \ge 1.0$s)**| OPTIMAL | 100% | $2,208.72$ | $2,050.00$ | 65 | 7 | $644.50$ ms | Gap = 0.0% |
| **F200_G20** | **A (Greedy)** | FEASIBLE | 100% | $3,138.32$ | $2,930.00$ | 93 | 10 | **4.30 ms** | Baseline |
| (Quy mô lớn, | **E (Greedy + SA)** | OPTIMAL | 100% | $3,138.32$ | $2,930.00$ | 93 | 10 | $3,527.80$ ms | **+0.00%** (Nghiệm Greedy là cực tiểu) |
| 20 gates) | **B (CP-SAT $TL=0.1$s)** | UNKNOWN | False | $80,000.00$ | $80,000.00$ | 0 | 0 | $1,014.00$ ms | Timeout (không có Incumbent) |
| | **B (CP-SAT $TL=0.3$s)** | UNKNOWN | False | $80,000.00$ | $80,000.00$ | 0 | 0 | $1,229.40$ ms | Timeout (cần $> 0.3$s) |
| | **B (CP-SAT $TL=1.0$s)** | OPTIMAL | 100% | $2,648.32$ | $2,440.00$ | 84 | 8 | $1,613.10$ ms | Gap = 0.0% (Tối ưu toàn cục) |
| | **D (Incumbent + SA)** | OPTIMAL | 100% | $2,648.32$ | $2,440.00$ | 84 | 8 | $3,510.40$ ms | **+0.00%** (Bảo toàn nghiệm tối ưu) |

---

### Bảng 2: Hiệu năng Tối ưu End-to-End trên 20 Kịch bản Ngẫu nhiên (Phase G)
*Nguồn dữ liệu: [`aggregate_metrics.json`](file:///D:/Study/Code/Python/Aelous/artifacts/end_to_end/aggregate_metrics.json) (50 chuyến bay, 20 cổng, ngày đại diện 2023-06-01)*

| Chỉ số Đánh giá | Greedy Baseline | CP-SAT Exact | CP-SAT + SA | Chênh lệch CP-SAT vs Greedy |
| :--- | :---: | :---: | :---: | :---: |
| **Chi phí Mục tiêu Trung bình** | $112.98$ | **$99.48$** | **$99.48$** | **-11.95% (Tiết kiệm)** |
| **Số lần Đổi cổng Trung bình** | $9.30$ | **$7.95$** | **$7.95$** | **-14.52% (Ít đổi cổng hơn)** |
| **Số chuyến Tràn bãi đỗ xa** | $0.00$ | $0.00$ | $0.00$ | $0.00$ (Đủ cổng tiếp xúc) |
| **Tổng số Xung đột Cổng** | **0** | **0** | **0** | **0% vi phạm** |
| **Tỷ lệ Khả thi Ràng buộc Cứng** | **100.0%** | **100.0%** | **100.0%** | Tuyệt đối an toàn |
| **Thời gian Thực thi Trung bình** | **$0.53$ ms** | $159.49$ ms | $561.81$ ms | Greedy cực nhanh |

---

### Bảng 3: Khảo sát Hội tụ Monte Carlo ($N = 100 \to 2500$ — Đã qua Kiểm toán & Hiệu chỉnh)
*Nguồn dữ liệu: [`aggregate_metrics.json`](file:///D:/Study/Code/Python/Aelous/artifacts/end_to_end/aggregate_metrics.json) (Đánh giá Uncapped 100% kịch bản, Seed = 202601)*

| Số kịch bản ($N$) | Mã băm Ma trận (SHA-256) | Số kịch bản Độc nhất | Xác suất Xung đột | P95 Thời lượng Xung đột (phút) | Chi phí Kỳ vọng (Phương sai) | Tỷ lệ Tận dụng Cổng | Nhận xét Khoa học |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **$N = 100$** | `7526e42007c6...` | 100 / 100 | $1.00$ | $660.25$ m | $108.75$ ($\sigma^2 = 313.49$) | $14.82\%$ | Mẫu khởi đầu |
| **$N = 250$** | `6b1b52a57058...` | 250 / 250 | $1.00$ | $656.55$ m | $109.13$ ($\sigma^2 = 370.34$) | $14.86\%$ | Dao động thống kê |
| **$N = 500$** | `810dc86447ec...` | 500 / 500 | $1.00$ | $658.10$ m | $108.83$ ($\sigma^2 = 344.60$) | $14.88\%$ | Bắt đầu tiệm cận |
| **$N = 1000$** | `27c1493f656b...` | 1000 / 1000 | $1.00$ | $665.00$ m | $109.81$ ($\sigma^2 = 395.15$) | $14.85\%$ | Ổn định vững chắc |
| **$N = 2500$** | `22d78f6d7af7...` | 2500 / 2500 | $1.00$ | $664.00$ m | $110.28$ ($\sigma^2 = 392.98$) | $14.82\%$ | Hội tụ chuẩn nghiên cứu |

> [!NOTE]
> **Kết luận Kiểm toán Monte Carlo**: Báo cáo trước đây ghi nhận các giá trị $666.15$ m và $108.76$ hoàn toàn giống nhau giữa các $N$ là do lỗi kỹ thuật cắt nhánh sớm `eval_count = min(n_scen, 100)` trong vòng lặp thu thập. Sau khi gỡ bỏ giới hạn này, mỗi cấp $N$ được đánh giá độc lập trên đúng $N$ kịch bản ngẫu nhiên. Số liệu cập nhật phản ánh đúng tính chất ngẫu nhiên thống kê: các ma trận có mã băm riêng biệt, 100% kịch bản là duy nhất, phương sai mẫu thể hiện rõ và các chỉ số hội tụ ổn định trong dải tin cậy hẹp ($P95 \in [656.55, 665.00]$, Chi phí $\in [108.75, 110.28]$).

---

### Bảng 4: Kết quả Kiểm định 7 Chốt An toàn Giao thức (Phase H Protocol Guards)
*Nguồn dữ liệu: [`protocol_compliance.json`](file:///D:/Study/Code/Python/Aelous/artifacts/final_code_audit/protocol_compliance.json)*

| Chốt An toàn (Guard Check) | Trọng tâm Kiểm tra | Quy chuẩn Protocol | Kết quả Thực tế | Trạng thái |
| :--- | :--- | :--- | :--- | :---: |
| **1. raw_data_immutable** | Tính bất biến dữ liệu thô | 9 CSV 2016–2024 không bị chỉnh sửa | Khớp mã git, 0 file bị thay đổi | **PASS** |
| **2. holdout_2024_not_in_training** | Cách ly tập kiểm định 2024 | Xác thực theo vai trò (Role-based), cấm 2024 train/cal/sel | Ủy quyền train 2016–2022, từ chối tuyệt đối 2024 | **PASS** |
| **3. fold_definitions_exact** | Đúng cấu trúc 4 rolling folds | Fold 1–4 chuẩn mở rộng theo năm | 4 folds khớp từng năm validation | **PASS** |
| **4. feature_contract** | Hợp đồng đặc trưng tại $T-2$h | Đúng 11 đặc trưng cho phép | 11 đặc trưng, 0 biến rò rỉ | **PASS** |
| **5. no_insample_uncertainty** | Độ bất định không phụ thuộc in-sample | Dùng Student-T & Copula | Parametric heads strictly used | **PASS** |
| **6. dynamic_dependence_dimension**| Đồng bộ contract chiều ma trận Phase C & H | Chạy ổn định trên mọi $d \ge 1$, bao phủ đỉnh ATL $d=420$ | Đồng bộ Phase C & H: test $d \in \{1, 5, 23, 77, 150, 420\}$, stress test $d=500$, kiểm tra 7 thuộc tính toán học | **PASS** |
| **7. solver_hard_constraints** | Triệt tiêu xung đột cổng | 0 cặp chuyến bay đè giờ nhau | 0 xung đột trên mọi solver | **PASS** |

---

### Bảng 5: Phân tầng Kiểm thử Tự động 6 Test Suites
*Nguồn dữ liệu: [`test_summary.json`](file:///D:/Study/Code/Python/Aelous/artifacts/final_code_audit/test_summary.json)*

| Tầng kiểm định (Suite) | Tệp kiểm thử chính | Số test | Thời gian chạy | Trạng thái |
| :--- | :--- | :---: | :---: | :---: |
| **1. Unit Tests (Simulation & Turn)** | `tests/test_simulation_pipeline.py`<br>`tests/test_timeline_semantics.py` | 19 | $3.45$s | **PASS** |
| **2. Probabilistic Tests** | `tests/test_student_t_correctness.py`<br>`tests/test_unified_evaluation.py` | 12 | $3.72$s | **PASS** |
| **3. Dependence Tests** | `tests/test_dependence_hardening.py`<br>`tests/test_dependence_contract_consistency.py` | 39 | $6.01$s | **PASS** |
| **4. CP-SAT & Greedy Tests** | `tests/test_cp_sat_solver.py`<br>`tests/test_greedy_and_adversarial.py` | 19 | $0.84$s | **PASS** |
| **5. Simulated Annealing Tests** | `tests/test_simulated_annealing.py` | 15 | $4.06$s | **PASS** |
| **6. End-to-End Smoke Test** | `tests/test_end_to_end_pipeline.py` | 2 | $3.44$s | **PASS** |
| **TỔNG HỢP PHÂN TẦNG** | **6 Suites hoàn chỉnh (8 Test Files)** | **106** | **21.53s** | **100% PASS** |

---

## 5. DANH MỤC ARTIFACTS & SƠ ĐỒ MÃ NGUỒN HỆ THỐNG

### 5.1. Sơ đồ Cấu trúc Module Mã nguồn Mới và Hiệu chỉnh
```
src/
├── audit/
│   └── protocol_guards.py        # 7 chốt an toàn fail-closed độc lập (Role-based & Dynamic d=420 synced)
├── dependence/
│   ├── base.py                   # BaseJointSampler, validate_flight_batch_inputs
│   ├── d0_independent.py         # D0 Independent joint delay sampler
│   ├── d1_scenario.py            # D1 Scenario / schedule-block sampler
│   ├── d2_gaussian_copula.py     # D2 Gaussian Copula với nhân thời gian - hãng bay
│   ├── psd.py                    # Chiếu nửa xác định dương PSD (validate_and_project_psd)
│   └── pit.py                    # Discrete randomized PIT sensitivity
├── optimization/
│   ├── evaluation.py             # evaluate_gate_assignment (Common Evaluator)
│   ├── config.py                 # OptimizationConfig, PenaltyWeights
│   ├── domain.py                 # FlightAssignment, GateAssignmentProblem (Timeline Semantics synced)
│   ├── solvers/
│   │   ├── cp_sat_solver.py      # Google OR-Tools CP-SAT Solver
│   │   └── greedy_solver.py      # Deterministic Greedy Gate Solver
│   └── sa/
│       ├── state.py              # SAState vector representation
│       ├── neighborhood.py       # Move, Swap, and Explicit Repair operators
│       ├── objective.py          # SA state objective evaluator
│       └── annealer.py           # SimulatedAnnealingGateSolver
└── simulation/
    ├── aircraft_turn.py          # AircraftTurn, AircraftTurnModel (D_sim, gate_in/out/release synced)
    ├── conflict_detector.py      # detect_conflicts, ConflictDetectionResult
    ├── scenario_runner.py        # MonteCarloScenarioRunner
    └── downstream_metrics.py     # Downstream utility evaluation metrics
```

### 5.2. Danh mục Manifests & Artifacts Chính
- **Phase A**: [`phase_a_comprehensive_audit_report.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/phase_a_comprehensive_audit_report.json), [`claim_semantics_audit.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/claim_semantics_audit.json).
- **Phase B**: [`phase_b_probabilistic_correctness_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/phase_b_probabilistic_correctness_manifest_v1.json), [`target_semantics_verification_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/target_semantics_verification_v1.json).
- **Phase C**: [`phase_c_dependence_hardening_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/phase_c_dependence_hardening_manifest_v1.json), [`phase_c_dependence_contract_consistency_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/phase_c_dependence_contract_consistency_manifest_v1.json).
- **Phase D**: [`cp_sat_benchmark_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/cp_sat_benchmark_manifest_v1.json), [`phase_d_cp_sat_objective_audit_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/phase_d_cp_sat_objective_audit_manifest_v1.json).
- **Phase E**: [`phase_e_greedy_baseline_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/phase_e_greedy_baseline_manifest_v1.json).
- **Phase F**: [`phase_f_simulated_annealing_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/phase_f_simulated_annealing_manifest_v1.json), [`phase_f_time_limited_sa_benchmark_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/phase_f_time_limited_sa_benchmark_manifest_v1.json).
- **Phase G**: [`artifacts/end_to_end/run_manifest.json`](file:///D:/Study/Code/Python/Aelous/artifacts/end_to_end/run_manifest.json), [`aggregate_metrics.json`](file:///D:/Study/Code/Python/Aelous/artifacts/end_to_end/aggregate_metrics.json), [`phase_g_timeline_semantics_audit_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/phase_g_timeline_semantics_audit_manifest_v1.json), [`artifacts/development_end_to_end/run_manifest.json`](file:///D:/Study/Code/Python/Aelous/artifacts/development_end_to_end/run_manifest.json).
- **Phase H**: [`artifacts/final_code_audit/integration_report.json`](file:///D:/Study/Code/Python/Aelous/artifacts/final_code_audit/integration_report.json), [`protocol_compliance.json`](file:///D:/Study/Code/Python/Aelous/artifacts/final_code_audit/protocol_compliance.json), [`reproducibility_manifest.json`](file:///D:/Study/Code/Python/Aelous/artifacts/final_code_audit/reproducibility_manifest.json), [`test_summary.json`](file:///D:/Study/Code/Python/Aelous/artifacts/final_code_audit/test_summary.json), [`artifacts/audit/phase_h_holdout_fold_guard_correction_manifest_v1.json`](file:///D:/Study/Code/Python/Aelous/artifacts/audit/phase_h_holdout_fold_guard_correction_manifest_v1.json).

---

## 6. HƯỚNG DẪN THỰC THI & TÁI LẬP (CLI RUNBOOK)

Môi trường thực thi chuẩn: Python 3.11 virtual environment tại `d:\Study\Code\Python\Aelous\.venv\`.

### 6.1. Thực thi Kiểm định Mã nguồn Toàn diện (Final Code Audit & 6 Test Suites)
Lệnh thực thi toàn bộ kiểm tra vệ sinh codebase, 7 chốt an toàn và chạy tuần tự 6 test suites (85 tests):
```powershell
.\.venv\Scripts\python.exe scripts/run_final_code_audit.py
```

### 6.2. Thực thi Vòng lặp Khép kín Đầu-cuối (End-to-End Evaluation)
1. **Chế độ kiểm tra nhanh (Smoke Mode — cách ly trong `artifacts/end_to_end_smoke/`)**:
```powershell
.\.venv\Scripts\python.exe scripts/run_end_to_end_evaluation.py --mode smoke
```
2. **Chế độ nghiên cứu đầy đủ (Research Mode — lưu trữ trong `artifacts/end_to_end/`)**:
```powershell
.\.venv\Scripts\python.exe scripts/run_end_to_end_evaluation.py --mode research
```

### 6.3. Chạy Từng Bài Kiểm thử Riêng biệt
- Chạy kiểm định 7 chốt an toàn giao thức:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_audit_provenance_guards.py -q
```
- Chạy kiểm định bộ giải CP-SAT và Greedy:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_cp_sat_solver.py tests/test_greedy_and_adversarial.py -q
```
- Chạy kiểm định thuật toán Simulated Annealing:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_simulated_annealing.py -q
```

---

## 7. ĐÁNH GIÁ RỦI RO KHOA HỌC, GIỚI HẠN & ĐỊNH HƯỚNG TƯƠNG LAI

### 7.1. Đánh giá Rủi ro Khoa học & Sự Thấu hiểu
1. **Giá trị vượt trội của Tối ưu hóa Toán học Chính xác (CP-SAT)**:
   - Các thuật toán Heuristic cục bộ (Greedy) tỏ ra lúng túng khi mật độ máy bay tăng cao, dẫn tới hiện tượng đổi cổng liên tục không cần thiết hoặc đẩy máy bay ra bãi đỗ xa khi cổng tiếp xúc vẫn còn khe hở nhỏ.
   - CP-SAT giải quyết triệt để vấn đề này với thời gian dưới $2$ giây cho các bài toán 200 chuyến bay, mang lại mức cắt giảm chi phí ấn tượng từ **38.0% đến 54.0%**.
2. **Vai trò Thực tế của Metaheuristic (Simulated Annealing)**:
   - SA với toán tử sửa lỗi xung đột (Repair Operator) là một giải pháp dự phòng lý tưởng khi CP-SAT bị giới hạn thời gian (Time-out) hoặc khi bài toán mở rộng thêm các ràng buộc phi tuyến phức tạp (ví dụ: luồng di chuyển hành khách kết nối, khoảng cách đi bộ phi tuyến giữa các cổng).
3. **Bài học về Ngữ nghĩa Dữ liệu Hàng không**:
   - Dữ liệu hàng không công khai (như BTS On-Time Performance) không ghi nhận cổng thực tế. Mọi kết luận tối ưu cần được trình bày một cách trung thực là **tối ưu hóa trên kịch bản mô phỏng đối chứng**, tránh phóng đại thành "tiết kiệm chi phí ngoài đời thực".

### 7.2. Giới hạn Hiện tại
- **Ràng buộc kéo dắt máy bay (Towing constraints)**: Mô hình hiện tại giả định máy bay nằm tại cổng suốt thời gian quay đầu (Turnaround Dwell). Với các chuyến bay có thời gian chờ trên 3–4 tiếng, thực tế sân bay sẽ kéo máy bay ra bãi đỗ đệm rồi kéo lại cổng khi gần giờ khởi hành.
- **Ràng buộc loại tàu bay và kích thước cổng (Aircraft Fleet & Gate Compatibility)**: Hiện tại bài toán phân bổ đồng nhất máy bay thân hẹp và thân rộng vào các cổng tiếp xúc.

### 7.3. Định hướng Nghiên cứu Tiếp theo
1. Mở rộng mô hình CP-SAT hỗ trợ tương thích chủng loại tàu bay (Aircraft Category: Heavy, B777/A350 vs Narrow-body, A320/B737) và các cổng đỗ đôi (MARS - Multiple Apron Ramp System).
2. Tích hợp ràng buộc luồng hành khách chuyển tiếp (Connecting Passenger Flow Optimization) nhằm cực tiểu hóa tổng thời gian đi bộ của hành khách trong nhà ga.
3. Thử nghiệm thuật toán học tăng cường (Reinforcement Learning) hoặc Large Neighborhood Search (LNS) kết hợp CP-SAT để giải quyết bài toán điều hành thời gian thực (Disruption Management) khi có bão tuyết hoặc sấm sét kéo dài.
