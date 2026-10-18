# 03. RAW LEDGER ACCOUNTING AUDIT & CONSERVATION EQUATIONS

**Protocol:** AEOLUS-MC500-PRODUCTION  
**Run ID:** `mc500_20261012_173538_afa5db`  
**Raw Source File:** `artifacts/remediation/monte_carlo_mc500/mc500_20261012_173538_afa5db/execution_ledger_entries.csv` (5,500 rows)  
**Generation Source:** `artifacts/remediation/monte_carlo_mc500/mc500_20261012_173538_afa5db/execution_ledger_generation.csv` (500 rows)  

---

## 1. Phương Trình Bảo Toàn Tổng Thể (Global Conservation Equations)

Toàn bộ 5,500 lượt đánh giá trên 500 kịch bản ngẫu nhiên tuân thủ nghiêm ngặt các phương trình bảo toàn sau:

1. **Bảo toàn Kịch bản Phát sinh (Scenario Generation Conservation):**
   $$N_{\text{requested}} = N_{\text{generated}} + N_{\text{gen\_failures}} = 500 + 0 = 500$$
2. **Bảo toàn Slots Đánh giá (Evaluation Slot Conservation):**
   $$N_{\text{expected\_evaluations}} = N_{\text{generated}} \times 11 = 500 \times 11 = 5,500$$
   $$N_{\text{completed}} + N_{\text{missing}} = 5,500 + 0 = 5,500$$
3. **Bảo toàn Tính Khả thi (Feasibility Partition Conservation):**
   $$N_{\text{completed}} = N_{\text{feasible}} + N_{\text{infeasible}} + N_{\text{failures}}$$
   $$5,500 = 4,378 + 1,122 + 0$$
   Kiểm toán xác nhận: Đúng $100\%$ không có sai lệch ($4,378 + 1,122 = 5,500$).

---

## 2. Bảng Phân Rã Chi Tiết 11 Evaluation Slots Trên 500 Realizations

| Recourse Mode | Initial Solver | Tổng số Lượt | Số lượt Khả thi (Feasible) | Số lượt Không khả thi (Infeasible) | Tỷ lệ Khả thi | Lỗi / Timeout |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **MODE_A** | Deterministic Greedy | 500 | 126 | 374 | 25.20% | 0 / 0 |
| **MODE_A** | CP-SAT Solver | 500 | 126 | 374 | 25.20% | 0 / 0 |
| **MODE_A** | Hybrid Solver | 500 | 126 | 374 | 25.20% | 0 / 0 |
| **MODE_B1** | Deterministic Greedy | 500 | 500 | 0 | **100.00%** | 0 / 0 |
| **MODE_B1** | CP-SAT Initial | 500 | 500 | 0 | **100.00%** | 0 / 0 |
| **MODE_B1** | Hybrid Initial | 500 | 500 | 0 | **100.00%** | 0 / 0 |
| **MODE_B2** | Causal Online (Greedy init) | 500 | 500 | 0 | **100.00%** | 0 / 0 |
| **MODE_B2** | Causal Online (CPSat init) | 500 | 500 | 0 | **100.00%** | 0 / 0 |
| **MODE_B2** | Causal Online (Hybrid init) | 500 | 500 | 0 | **100.00%** | 0 / 0 |
| **MODE_C1** | Foresight Greedy | 500 | 500 | 0 | **100.00%** | 0 / 0 |
| **MODE_C2** | Mathematical Oracle (CP-SAT)| 500 | 500 | 0 | **100.00%** | 0 / 0 |
| **TỔNG CỘNG** | **11 Slots / Realization** | **5,500** | **4,378** | **1,122** | **79.60%** | **0 / 0** |

---

## 3. Kiểm Toán Mẫu Số Tỷ Lệ Theo Hợp Đồng (Contract Denominators)

1. **`generation_failure_rate`:**
   $$\text{Rate} = \frac{N_{\text{gen\_failures}}}{N_{\text{requested}}} = \frac{0}{500} = \mathbf{0.00\%} \quad (\text{Mẫu số: } 500)$$
2. **`evaluation_failure_rate`:**
   $$\text{Rate} = \frac{N_{\text{eval\_failures}}}{N_{\text{expected\_evaluations}}} = \frac{0}{5,500} = \mathbf{0.00\%} \quad (\text{Mẫu số bắt buộc: } 5,500)$$
3. **`composite_feasible_rate`:**
   $$\text{Rate} = \frac{N_{\text{feasible}}}{N_{\text{completed\_evaluations}}} = \frac{4,378}{5,500} = \mathbf{79.60\%} \quad (\text{Mẫu số: } 5,500)$$

---

## 4. Kiểm Toán Khóa Chính & Tính Toàn Vẹn Dữ Liệu (Primary Key Uniqueness Audit)

Tập bản ghi thô gồm $5,500$ dòng của `execution_ledger_entries.csv` được kiểm tra trùng lặp trên bộ khóa chính:
$$(\text{run\_id}, \text{scenario\_id}, \text{recourse\_mode}, \text{initial\_plan\_solver})$$
- Số lượng bản ghi trùng lặp: **0** (dups = 0).
- Số lượng kịch bản bị bỏ quên (silent drops): **0**.
- Số lượng slot bị thiếu: **0**.
- Đầy đủ 500 realizations ngẫu nhiên độc lập được đánh giá nhất quán qua đúng 11 khe quy định của giao thức Common Random Numbers (CRN).
