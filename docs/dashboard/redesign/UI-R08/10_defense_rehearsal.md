# UI-R08 Deliverable 10: 12-Minute Thesis Defense Script & Committee Rehearsal Runbook

**Auditor:** Thesis Defense Reliability Lead & Scientific Presentation Coach  
**Target Duration:** 10 – 12 Minutes (Strict Defense Time Limit)  
**Primary Display Mode:** Presentation Mode (with Research Mode toggled for deep-dive questions)  
**Target Audience:** Academic Thesis Defense Committee & Aviation Operations Evaluators

---

## 1. Minute-by-Minute Rehearsal Script

```
0:00 ─── 1:30 ─── 3:30 ───────── 6:00 ────────── 8:00 ────────── 10:00 ──── 12:00
  [Intro &        [Dual-Core ML     [Live Gate      [Optimization   [Monte Carlo    [Conclusion
   Control Tower]  & Turn Dynamics]  Assignment]     Benchmarking]   Robustness]     & Q&A]
```

### Stage 1: Problem Formulation & Control Tower Overview (0:00 – 1:30)
- **Action:** Open Dashboard on `01_control_tower` in **Presentation Mode**.
- **Spoken Script:**
  > "Kính thưa Hội đồng, bài toán phân bổ cổng máy bay tại các sân bay trung tâm như Atlanta (ATL) đối mặt với thách thức lớn khi các chuyến bay bị chậm trễ dây chuyền. Lịch bay tĩnh ban đầu nhanh chóng bị vỡ khi gặp biến động thực tế.
  >
  > Trên màn hình là **Control Tower**, cung cấp bức tranh toàn cảnh về đợt sóng trễ (Delay Wave), tải trọng các concourse (T, A, Remote) và trạng thái hệ thống. Hệ thống của chúng tôi tích hợp trọn vẹn từ mô hình dự báo ML hai lõi, tổng hợp chu trình quay vòng máy bay (Aircraft Turn), giải bài toán tối ưu hóa phân cổng bằng CP-SAT, và kiểm chứng độ bền vững qua mô phỏng Monte Carlo."
- **Visual Highlight:** Point to Context Bar (`ATL Peak Morning: 120 flights, 25 gates`) and Delay Wave histogram.

---

### Stage 2: Dual-Core ML Delay Forecasting & Aircraft Turn Dynamics (1:30 – 3:30)
- **Action:** Navigate to `02_flight_intelligence`.
- **Spoken Script:**
  > "Thay vì giả định độ trễ ngẫu nhiên đơn giản, chúng tôi triển khai kiến trúc **Dual-Core Machine Learning**: một lõi dự báo độ trễ đến (Inbound) và một lõi dự báo độ trễ đi (Outbound), loại bỏ hoàn toàn rò rỉ dữ liệu (Target Leakage) theo nguyên tắc D1-D3.
  >
  > Chuyển sang Tab B: Chu trình quay vòng máy bay liên kết chuyến đến và chuyến đi của cùng một tàu bay. Chúng tôi áp dụng công thức vật lý: thời gian xuất bến tối thiểu $D_{\text{gate\_out}} = \max(D_{\text{pred}}, A_{\text{pred}} + 45)$, cộng thêm đúng 15 phút buffer phân cách an toàn. Khoảng thời gian dôi dư (slack) hấp thụ độ trễ đến; phần trễ vượt ngưỡng mới lan truyền sang chuyến đi."
- **Visual Highlight:** Click Tab B, highlight the Aircraft Turn Gantt chart showing the 45-min minimum dwell, absorbed slack, and 15-min safety buffer.

---

### Stage 3: Live Gate Assignment Optimization & Gantt Operations (3:30 – 6:00)
- **Action:** Navigate to `03_gate_operations`.
- **Spoken Script:**
  > "Bước sang trung tâm vận hành: **Gate Operations**.
  >
  > Ở kế hoạch danh định (Nominal Plan), do các chuyến bay đến bị trễ, biểu đồ Gantt phát hiện ngay các xung đột chồng lấn cổng (Gate Conflicts) được đánh dấu màu đỏ.
  >
  > Bây giờ, tôi tiến hành kích hoạt bộ giải tối ưu hóa **CP-SAT** trực tiếp..."
- **Action:** Click button `Chạy Phân Cổng CP-SAT (Solve Interactive)`. Wait ~1.5s for solve completion.
- **Spoken Script:**
  > "Như Hội đồng thấy, bộ giải CP-SAT đã tái phân bổ thông minh: các xung đột được triệt tiêu hoàn toàn (Conflicts = 0). Huy hiệu xác minh độc lập `XÁC MINH HỢP LỆ (VERIFIED)` xác nhận kế hoạch thỏa mãn tuyệt đối các ràng buộc cứng: không chồng lấn khoảng nửa mở $[start, release)$, tôn trọng sức chứa hữu hạn của sân đỗ Remote, và hạn chế tối đa việc đẩy máy bay ra Apron xa."
- **Visual Highlight:** Point to independent verification badge and zero conflicts on the Master Gantt.

---

### Stage 4: Scientific Solver Benchmarking & Scalability Bounds (6:00 – 8:00)
- **Action:** Navigate to `04_optimization_lab`.
- **Spoken Script:**
  > "Tại **Optimization Lab**, chúng tôi so sánh khách quan bốn thuật toán: Tham lam (Greedy), Quy hoạch ràng buộc (CP-SAT), Mô phỏng luyện kim (Simulated Annealing) và Thuật toán lai (Hybrid).
  >
  > Chúng tôi phân biệt rõ ràng Chi phí Quyết định (Decision Cost) và Chi phí Báo cáo (Reporting Cost). CP-SAT đạt nghiệm tối ưu toàn cục đã được chứng minh (`OPTIMAL_PROVEN`) trên quy mô 120 chuyến bay.
  >
  > Tuy nhiên, bài toán kiểm tra độ co giãn (Scalability) lên tới 1.500 chuyến bay chỉ ra rằng CP-SAT chạm ngưỡng thời gian 30 giây mà chưa tìm thấy nghiệm (`UNKNOWN`), chứng minh tính cấp thiết của việc áp dụng thuật toán Heuristic và Hybrid khi mở rộng sang các siêu sân bay."
- **Visual Highlight:** Show Pareto Frontier curve and Point to the $N=1500$ `UNKNOWN` annotation on the Scalability chart.

---

### Stage 5: Monte Carlo Robustness Evaluation & Tail Risk (8:00 – 10:00)
- **Action:** Navigate to `05_robustness_lab`.
- **Spoken Script:**
  > "Một kế hoạch tối ưu trên dự báo điểm có thể thất bại khi vận hành thực tế. Do đó, chúng tôi tiến hành đánh giá độ bền vững qua 500 kịch bản ngẫu nhiên **Monte Carlo**:
  >
  > - **Mode A (Kế hoạch cố định):** Khi giữ nguyên cổng mà không điều chỉnh, tỷ lệ xung đột thực tế lên tới **74,8%**, chứng minh kế hoạch tĩnh hoàn toàn đổ vỡ dưới biến động thời gian thực.
  > - **Mode B (Tái điều phối thích ứng):** Khi áp dụng cơ chế Recourse, 100% xung đột được hóa giải.
  > - **Đánh giá rủi ro đuôi (Tail Risk):** Chúng tôi phân tích thước đo rủi ro kết hợp CVaR 95% ($CVaR_{95} \ge p95$), cung cấp cho điều phối viên mức dự phòng tài chính và vận hành an toàn nhất."
- **Visual Highlight:** Click Tab A (Violin comparison) and Tab C (Tail Risk CVaR vs p95 chart).

---

### Stage 6: Defense Conclusion & Committee Q&A (10:00 – 12:00)
- **Spoken Script:**
  > "Tóm lại, hệ thống Aeolus đã cung cấp giải pháp toàn diện từ dự báo chuẩn xác, phân cổng tối ưu với chứng minh toán học, đến kiểm chứng độ bền vững thực nghiệm. Em xin trân trọng cảm ơn Quý Thầy Cô trong Hội đồng và xin lắng nghe các câu hỏi đóng góp."

---

## 2. Anticipated Committee Questions & Authoritative Answers

### Q1: "Tại sao CP-SAT lại không tìm được nghiệm ở quy mô 1.500 chuyến bay trong 30 giây?"
> **Câu trả lời chuẩn:**  
> "Dạ thưa Thầy Cô, bài toán phân cổng với khoảng thời gian nửa mở là bài toán NP-hard. Với 1.500 chuyến bay trên 50 cổng, số lượng ràng buộc không chồng lấn tăng theo bậc $O(N^2)$ với hàng triệu cặp khoảng thời gian. Trong giới hạn 30 giây quy định cho phản ứng vận hành thời gian thực, cây tìm kiếm nhánh-và-cắt (branch-and-bound) của CP-SAT chưa kịp hội tụ đến nghiệm nguyên khả thi đầu tiên. Kết quả này được nhóm báo cáo trung thực là `UNKNOWN` thay vì ngụy tạo số liệu, và đây chính là cơ sở khoa học để chúng em phát triển thuật toán Hybrid trong nghiên cứu."

### Q2: "Tại sao ở Mode C trong Monte Carlo lại sử dụng Greedy thay vì CP-SAT?"
> **Câu trả lời chuẩn:**  
> "Dạ thưa Thầy Cô, Mode C là kịch bản chuẩn tham chiếu hậu nghiệm (Perfect-Foresight Oracle), tức là giải lại bài toán khi đã biết trước toàn bộ độ trễ thực tế trên 500 kịch bản ngẫu nhiên. Trong nghiên cứu hiện tại, giải 500 lần CP-SAT liên tục tốn rất nhiều giờ tính toán, nên nhóm sử dụng Greedy Heuristic làm cận tham chiếu. Theo đúng khuyến nghị kiểm toán khoa học của nhóm, Mode C được dán nhãn rõ ràng là 'Tham chiếu hậu nghiệm không thể triển khai thực tế' và tuyệt đối không tuyên bố là nghiệm tối ưu toàn cục."

### Q3: "Làm thế nào để đảm bảo mô hình Machine Learning không bị rò rỉ dữ liệu (Data Leakage)?"
> **Câu trả lời chuẩn:**  
> "Dạ thưa Thầy Cô, nhóm tuân thủ nghiêm ngặt các phát hiện D1-D3:
> 1. Tại thời điểm lập kế hoạch (pre-departure), các trường dữ liệu thực tế như `actual_arr_delay` bị loại bỏ hoàn toàn khỏi không gian đặc trưng.
> 2. Hệ thống tích hợp bộ kiểm tra `ScientificValidator.check_prediction_data_leakage`, tự động kích hoạt ngoại lệ `DataLeakageError` nếu phát hiện bất kỳ cột nhãn thực tế nào lọt vào giao diện lập kế hoạch.
> 3. Tập dữ liệu kiểm thử năm 2024 được cách ly tuyệt đối (`quarantined_years`) khỏi tập huấn luyện 2023."

### Q4: "Tại sao kế hoạch tối ưu ban đầu không có xung đột, nhưng sang Mode A lại có 74,8% tỷ lệ xung đột?"
> **Câu trả lời chuẩn:**  
> "Dạ thưa Thầy Cô, kế hoạch tối ưu ở Page 03 được xây dựng dựa trên kỳ vọng dự báo điểm (Point Forecast) cộng với buffer 15 phút. Tuy nhiên, trong mô phỏng ngẫu nhiên Monte Carlo, độ trễ thực tế tuân theo phân phối đuôi nặng (Heavy-tailed distribution). Khi chuyến bay đến trễ vượt quá 15 phút buffer, thời gian chiếm dụng cổng bị xê dịch và đè lên khoảng chiếm dụng của chuyến bay kế tiếp. Con số 74,8% chứng minh một kết luận khoa học quan trọng: **Lập kế hoạch tĩnh đơn thuần là không đủ; sân bay bắt buộc phải có cơ chế tái điều phối động (Recourse) như Mode B.**"
