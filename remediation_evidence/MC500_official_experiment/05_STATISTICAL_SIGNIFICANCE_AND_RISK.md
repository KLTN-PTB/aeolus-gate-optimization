# 05. STATISTICAL SIGNIFICANCE, HYPOTHESIS TESTING & TAIL RISK

**Protocol:** AEOLUS-MC500-PRODUCTION  
**Methodology:** Paired Student-$t$ Hypothesis Testing under Common Random Numbers (CRN)  
**Sample Size:** $N = 500$ Paired Stochastic Realizations  

---

## 1. Kiểm Định So Sánh Cặp (Paired Statistical Comparisons)

Phương pháp Common Random Numbers (CRN) liên kết mỗi realization với đúng một chuỗi biến ngẫu nhiên hạt giống, triệt tiêu phương sai ngoại cảnh giữa các phương pháp. Dưới đây là kết quả kiểm định 5 cặp so sánh cốt lõi:

| Cặp So sánh Nghiên cứu | Ý nghĩa Khoa học | Chênh lệch TB ($\Delta$) | Sai số Chuẩn (SE) | Khoảng Tin cậy 95% (CI) | Giá trị $t$-statistic | $p$-value |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Mode A vs Mode B2** | **Lợi ích Vận hành của Ứng phó Nhân quả** | **+1329.68** | 50.78 | $[+1229.91, +1429.45]$ | $26.19$ | $< 10^{-15}$ |
| **Mode B1 vs Mode B2** | **Khoảng cách Giữa Hindsight và Online** | **-8.76** | 1.46 | $[-11.63, -5.89]$ | $-5.99$ | $4.00 \times 10^{-9}$ |
| **Mode B2 vs Mode C1** | **Chính sách Online vs Heuristic Tiên tri** | **+8.76** | 1.46 | $[+5.89, +11.63]$ | $5.99$ | $4.00 \times 10^{-9}$ |
| **Mode B2 vs Mode C2** | **Tổn thất Vận hành do Bất định (Causal Gap)**| **+19.10** | 1.61 | $[+15.93, +22.27]$ | $11.85$ | $< 10^{-15}$ |
| **Mode C1 vs Mode C2** | **Khoảng cách Heuristic Tiên tri vs Tối ưu Tuyệt đối** | **+10.34** | 0.59 | $[+9.18, +11.50]$ | $17.59$ | $< 10^{-15}$ |

### Nhận định Khoa học:
1. **Lợi ích của Ứng phó Thời gian thực (Mode A vs Mode B2):** Giảm trung bình $1,329.68$ điểm chi phí ($p < 10^{-15}$), chứng minh chính sách ứng phó nhân quả là bắt buộc để triệt tiêu các thảm họa tắc nghẽn dây chuyền trên sân đỗ.
2. **Giá trị của Thông tin Hoàn hảo (Causal Gap / Mode B2 vs Mode C2):** Chênh lệch giữa chính sách online có thể triển khai thực tế (Mode B2) và chặn dưới toán học lý thuyết (Mode C2) là **$19.10$ điểm chi phí** ($95\%$ CI: $[15.93, 22.27]$).
   > *Lưu ý Phương pháp luận:* Khoảng cách thực nghiệm này phản ánh **Tổn thất Vận hành do Tính không chắc chắn của Thời gian thực (Price of Uncertainty / Real-time Recourse Gap)**, không được gọi là formal EVPI (Expected Value of Perfect Information) vì cấu trúc hàm mục tiêu soft-cost có thành phần hình phạt vi phạm.

---

## 2. Phân Tích Rủi Ro Đuôi (Tail Risk & CVaR Analysis)

Trong điều hành sân bay, các sự kiện trễ nghiêm trọng ở đuôi phân phối (extreme events) có tính hủy hoại vận hành cao nhất. Bảng dưới đây phân tích các phân vị rủi ro và tổn thất kỳ vọng có điều kiện (Conditional Value-at-Risk):

| Chế độ Thực nghiệm | Phân vị P50 (Trung vị) | Phân vị P90 | Phân vị P95 | Phân vị P99 | $\text{CVaR}_{90}$ | $\text{CVaR}_{95}$ |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Mode A (Fixed Plan)** | 1109.96 | 2118.66 | 3125.41 | 6100.83 | 3636.57 | **4388.35** |
| **Mode B1 (Retrospective)** | 126.29 | 163.63 | 177.37 | 215.11 | 185.39 | **195.56** |
| **Mode B2 (Online Recourse)** | 132.30 | 176.68 | 195.30 | 338.45 | 231.06 | **275.67** |
| **Mode C1 (Greedy Foresight)**| 126.29 | 163.63 | 177.37 | 215.11 | 185.39 | **195.56** |
| **Mode C2 (Optimal Oracle)** | 118.12 | 141.74 | 149.94 | 173.49 | 154.26 | **160.23** |

### Đánh giá Rủi ro Vận hành:
- Khi không có cơ chế ứng phó (Mode A), rủi ro đuôi bùng nổ: $\text{CVaR}_{95} = 4,388.35$ (tăng hơn $300\%$ so với trung vị), dẫn tới hàng loạt chuyến bay bị trễ kéo dài và xung đột sân đỗ nghiêm trọng.
- Khi áp dụng Mode B2, rủi ro đuôi được kiểm soát chặt chẽ ở mức $\text{CVaR}_{95} = 275.67$, chỉ cao hơn trung vị $143.37$ điểm chi phí, bảo đảm độ tin cậy vận hành cho trung tâm điều hành sân bay (AOCC).
