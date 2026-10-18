# 04. COMPREHENSIVE RECOURSE MODE COMPARISON & NUMERICAL AUDIT

**Protocol:** AEOLUS-MC500-PRODUCTION  
**Sample Size:** $N = 500$ Stochastic Realizations, 11 Canonical Evaluation Slots ($5,500$ Total Evaluations)  
**Run ID:** `mc500_20261012_173538_afa5db`  

---

## 1. Bảng Tổng Hợp Chỉ Số Hiệu Năng Của 5 Chế Độ (Comprehensive Performance Metrics)

| Chế độ & Bộ giải | Chi phí TB (Mean) | Độ lệch chuẩn (Std) | Trung vị (Median) | Phân vị P95 | Rủi ro đuôi CVaR95 | Tỷ lệ Khả thi | Sử dụng Remote TB | Thời gian chạy TB (ms) | P95 Thời gian (ms) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Mode A (Greedy init)** | 1469.17 | 1161.92 | 1109.96 | 3125.41 | 4388.35 | 25.20% | 0.000 | 1.51 | 2.15 |
| **Mode A (CPSat init)** | 1469.17 | 1161.92 | 1109.96 | 3125.41 | 4388.35 | 25.20% | 0.000 | 1.50 | 2.12 |
| **Mode A (Hybrid init)** | 1469.17 | 1161.92 | 1109.96 | 3125.41 | 4388.35 | 25.20% | 0.000 | 1.50 | 2.11 |
| **Mode B1 (Greedy init)**| 130.73 | 25.37 | 126.29 | 177.37 | 195.56 | **100.00%** | 0.000 | 3.08 | 4.60 |
| **Mode B1 (CPSat init)** | 130.73 | 25.37 | 126.29 | 177.37 | 195.56 | **100.00%** | 0.000 | 3.08 | 4.62 |
| **Mode B1 (Hybrid init)**| 130.73 | 25.37 | 126.29 | 177.37 | 195.56 | **100.00%** | 0.000 | 3.19 | 4.71 |
| **Mode B2 (Greedy init)**| 139.49 | 44.54 | 132.30 | 195.30 | 275.67 | **100.00%** | 0.022 | 3.96 | 5.80 |
| **Mode B2 (CPSat init)** | 139.49 | 44.54 | 132.30 | 195.30 | 275.67 | **100.00%** | 0.022 | 3.96 | 5.81 |
| **Mode B2 (Hybrid init)**| 139.49 | 44.54 | 132.30 | 195.30 | 275.67 | **100.00%** | 0.022 | 3.95 | 5.79 |
| **Mode C1 (Greedy Foresight)**| 130.73 | 25.37 | 126.29 | 177.37 | 195.56 | **100.00%** | 0.000 | 2.65 | 3.90 |
| **Mode C2 (Optimal Oracle)** | **120.39** | **16.61** | **118.12** | **149.94** | **160.23** | **100.00%** | 0.000 | 360.26 | 1500.20 |

---

## 2. Kiểm Toán Tính Tối Ưu Mode C2 (Mode C2 Optimality Verification)

Theo quy định bắt buộc của hợp đồng kiểm toán khoa học:
- **Số lượt chứng minh tối ưu toán học (`OPTIMAL`, `is_optimal_proven = True`):** **$499 / 500$ lượt ($99.80\%$)**.
- **Số lượt chỉ đạt khả thi (`FEASIBLE`, `is_optimal_proven = False`):** **$1 / 500$ lượt ($0.20\%$)**.
- **Kịch bản ngoại lệ:** Kịch bản `scenario_index = 183` (`SCEN_0183`).
  - Trạng thái solver: `FEASIBLE` (chưa chứng minh được khoảng cách tối ưu gap trong ngân sách thời gian).
  - Chi phí đạt được: $168.80$.
  - Thời gian chạy solver: $1,572.82$ ms (chạm ngưỡng giới hạn thời gian $1.5$ giây của CP-SAT).
- **Kết luận khoa học:** Toàn bộ 500 lượt của Mode C2 đều đạt tính khả thi hợp lệ ($100\%$). Tuy nhiên, do có 1 kịch bản đạt `FEASIBLE`, báo cáo này **không tuyên bố 100% 500 kịch bản là Proven Optimal Oracle**, mà khẳng định chính xác: **$99.8\%$ đạt Chứng chỉ Tối ưu Tuyệt đối (Proven Optimal), $0.2\%$ đạt Khả thi Cận tối ưu (Feasible Bound)**.

---

## 3. Hệ Thống Phân Cấp Chặn Lý Thuyết (Theoretical Monotonicity)

Dữ liệu thực nghiệm trên 500 realizations ngẫu nhiên xác nhận hoàn hảo bất đẳng thức lý thuyết của Vận trù học ngẫu nhiên:

$$\mathbf{120.39 \le 130.73 \le 139.49 \ll 1469.17}$$

1. **Mode C2 ($120.39$):** Chặn dưới lý thuyết với thông tin tương lai hoàn hảo.
2. **Mode B1 ($130.73$):** Tái lập kế hoạch toàn diện sau sự cố (Retrospective Hindsight Benchmark).
3. **Mode B2 ($139.49$):** Chính sách ứng phó nhân quả vận hành thời gian thực (Causal Online Recourse).
4. **Mode A ($1469.17$):** Kế hoạch tĩnh không ứng phó, gánh chịu trung bình $1.34$ va chạm vật lý mỗi chuyến và $13.2$ phút vi phạm đệm an toàn.
