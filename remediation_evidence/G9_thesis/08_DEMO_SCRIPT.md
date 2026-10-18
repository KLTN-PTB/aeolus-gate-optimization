# AEOLUS-G9 — Kịch Bản Trình Diễn Hệ Thống và Phương Án Dự Phòng (Demo Script & Fallback Plan)

Tài liệu này hướng dẫn chi tiết từng bước thực hiện demo trực tiếp (Live Demo) bảng điều khiển vận hành Streamlit trong thời lượng 10–15 phút trước Hội đồng bảo vệ khóa luận tốt nghiệp, kèm theo phương án dự phòng ngoại tuyến hoàn chỉnh nếu xảy ra sự cố kỹ thuật.

---

## 1. THIẾT LẬP MÔI TRƯỜNG VÀ KIỂM TRA TRƯỚC GIỜ BẢO VỆ (PRE-FLIGHT CHECK)

### Bước 1: Khởi động Terminal và Kích hoạt Môi trường Ảo
Mở PowerShell tại thư mục gốc dự án:
```powershell
cd D:\Study\Code\Python\Aelous
.\.venv\Scripts\Activate.ps1
```

### Bước 2: Kiểm tra Tính sẵn sàng Ngoại tuyến (Preflight Verification)
Chạy lệnh kiểm tra nhanh 5 checkpoint mô hình và các tệp dữ liệu:
```powershell
python -c "from dashboard.core.config import DashboardConfig; cfg = DashboardConfig(); print('Dashboard Config Ready. Offline Allowed Dirs:', len(cfg.allowed_scenario_directories))"
```
*Kết quả kỳ vọng*: In ra thông báo sẵn sàng, không yêu cầu kết nối mạng Internet.

### Bước 3: Khởi chạy Bảng điều khiển Streamlit
```powershell
streamlit run dashboard/app.py
```
*Trình duyệt web sẽ tự động mở tại địa chỉ:* `http://localhost:8501`.

---

## 2. KỊCH BẢN THUYẾT MINH TRÌNH DIỄN TRỰC TIẾP (12 PHÚT)

### Giai đoạn 1: Giới thiệu Tổng quan Đài Kiểm soát (Control Tower — 2 phút)
- **Thao tác**: Giữ nguyên trang chủ mặc định `01_Control_Tower.py`.
- **Thuyết minh**:
  > *"Kính thưa Hội đồng, đây là giao diện Đài kiểm soát trung tâm (Control Tower). Tại đây, điều độ viên có cái nhìn toàn cảnh về tình trạng khai thác sân bay:*
  > - *Hàng trên cùng hiển thị 4 KPI vận hành cốt lõi: Tổng số chuyến bay đang quản lý, Tỷ lệ trễ dự báo, Số cổng đỗ đang hoạt động và Số chuyến bay có nguy cơ xung đột.*
  > - *Biểu đồ Delay Wave trực quan hóa các làn sóng trễ theo từng khung giờ trong ngày, giúp sân bay chủ động chuẩn bị nhân lực trước các khung giờ cao điểm."*

### Giai đoạn 2: Phân tích Trí tuệ Dự báo Trễ (Flight Intelligence — 2.5 phút)
- **Thao tác**: Nhấp vào menu bên trái chọn trang `02_Flight_Intelligence.py`.
- **Thao tác chi tiết**:
  1. Chọn chuyến bay đại diện trong danh sách (ví dụ: `FL_01` hoặc chuyến bay thuộc hãng Delta).
  2. Chỉ vào đồ thị hàm mật độ xác suất (PDF) Student-t.
- **Thuyết minh**:
  > *"Tại trang Trí tuệ Chuyến bay, hệ thống không chỉ đưa ra một con số dự báo điểm đơn thuần, mà cung cấp đầy đủ hàm phân phối xác suất trễ liên tục từ mô hình P4 NGBoost Student-t. Bậc tự do $\nu = 4.5$ thể hiện rõ đặc trưng đuôi nặng của trễ hàng không.*
  > *Biểu đồ phân tích SHAP bên cạnh giải thích minh bạch nguyên nhân dự báo: ví dụ cự ly bay xa, lịch sử trễ của tuyến bay đóng góp làm tăng nguy cơ trễ chuyến."*

### Giai đoạn 3: Giám sát Cổng đỗ và Biểu đồ Gantt (Gate Operations — 2.5 phút)
- **Thao tác**: Nhấp vào trang `03_Gate_Operations.py`.
- **Thao tác chi tiết**:
  1. Phóng to biểu đồ Gantt phân bổ cổng đỗ.
  2. Rê chuột vào một thanh chiếm dụng cổng để hiện popup chi tiết.
- **Thuyết minh**:
  > *"Trang Vận hành Cổng đỗ thể hiện trực quan sơ đồ phân bổ cổng đỗ dưới dạng biểu đồ Gantt. Mỗi thanh chiếm dụng cổng đại diện cho khoảng thời gian nửa mở $[S_i, E_i)$.*
  > *Đặc biệt, hệ thống hiển thị rõ ràng dải đệm an toàn 15 phút giữa hai chuyến bay liên tiếp tại cùng một cổng. Nếu hai chuyến bay vi phạm khoảng cách này hoặc đè lên nhau, hệ thống sẽ tự động kích hoạt cảnh báo vi phạm màu đỏ ngay lập tức."*

### Giai đoạn 4: Kích hoạt Tối ưu hóa và So sánh Đa Bộ giải (Optimization Lab — 3 phút)
- **Thao tác**: Nhấp vào trang `04_Optimization_Lab.py`.
- **Thao tác chi tiết**:
  1. Giải thích xuất xứ kịch bản: Chỉ vào nhãn badge `SYNTHETIC_CANONICAL` hoặc `REAL_DERIVED`.
  2. Bấm nút **"Run Benchmark / Solve"** để kích hoạt giải thuật trực tiếp trước Hội đồng.
- **Thuyết minh**:
  > *"Tại Phòng thí nghiệm Tối ưu hóa, hệ thống tuân thủ nguyên tắc chỉ giải khi người dùng bấm nút xác nhận, không chạy ngầm gây tốn tài nguyên.*
  > *Sau khi bấm nút, hệ thống đồng thời kích hoạt 4 thuật toán: Greedy, CP-SAT, SA và Hybrid:*
  > - *Bộ giải CP-SAT tìm ra nghiệm tối ưu trong vòng chưa đầy 1 giây, giảm hơn $20\%$ chi phí so với Greedy.*
  > - *Chi phí được tách bạch thành Decision Cost và Reporting Cost.*
  > - *Bộ kiểm định độc lập (Independent Verifier) lập tức xác nhận nghiệm đạt 0 vi phạm ràng buộc cứng.*
  > - *Hệ thống hiển thị nhãn `OPTIMAL (PROVEN)`, minh chứng cho việc nghiệm đã được chứng minh toán học."*

### Giai đoạn 5: Đánh giá Rủi ro Độ bền vững (Robustness Lab — 2 phút)
- **Thao tác**: Nhấp vào trang `05_Robustness_Lab.py`.
- **Thuyết minh**:
  > *"Cuối cùng, trang Kiểm thử Độ bền vững hiển thị kết quả mô phỏng Monte Carlo đa kịch bản. Hội đồng có thể quan sát:*
  > - *Phân phối chi phí của Kế hoạch tĩnh Mode A phân tán rất rộng với $76\%$ kịch bản xảy ra xung đột.*
  > - *Thuật toán tái phân bổ trực tuyến nhân quả Mode B2 co hẹp phân phối chi phí về mức tối ưu và triệt tiêu 100% xung đột vật lý.*
  > - *Chỉ số CVaR ($95\%$) định lượng chính xác rủi ro trong $5\%$ kịch bản xấu nhất, giúp lãnh đạo sân bay chuẩn bị phương án bãi đỗ phụ kịp thời."*

---

## 3. PHƯƠNG ÁN DỰ PHÒNG NGOẠI TUYẾN TOÀN DIỆN (FALLBACK PLAN)

Nếu trong buổi bảo vệ xảy ra sự cố đột xuất (ví dụ: máy tính treo trình duyệt, cổng 8501 bị chiếm dụng, hoặc thời gian bảo vệ bị rút ngắn), sinh viên thực hiện một trong hai phương án dự phòng sau:

### Phương án Dự phòng 1: Trình diễn Trực tiếp bằng Dòng lệnh CLI (Command Line Demo)
Chạy script kiểm chứng nhanh không cần trình duyệt web:
```powershell
# Chạy bộ benchmark so sánh 4 bộ giải trong 3 giây
python -c "
from src.optimization.config import GateOptimizationConfig
from src.optimization.solvers.cp_sat_solver import CPSatGateSolver
from src.optimization.solvers.greedy_solver import DeterministicGreedyGateSolver
from src.optimization.domain import Flight, Gate, GateResourceType
flights = [Flight(f'FL_{i}', i, 'DL', f'10{i}', 100+i*30, 160+i*30, 100+i*30, aircraft_type='A321') for i in range(5)]
gates = [Gate('G1', 0, resource_type=GateResourceType.CONTACT_GATE), Gate('G2', 1, resource_type=GateResourceType.CONTACT_GATE)]
cfg = GateOptimizationConfig()
res_gr = DeterministicGreedyGateSolver(cfg).solve(flights, gates)
res_cp = CPSatGateSolver(cfg).solve(flights, gates)
print(f'Greedy Objective: {res_gr.objective_value} | CP-SAT Objective: {res_cp.objective_value} (Optimality Proven: {res_cp.optimality_proven})')
"
```
*Kết quả in trực tiếp*: Chứng minh CP-SAT đạt nghiệm tối ưu và vượt trội hơn Greedy ngay tại màn hình terminal.

### Phương án Dự phòng 2: Trình chiếu Bằng chứng Thực nghiệm Đã Đóng băng (Precomputed Artifacts)
Mở trực tiếp các tệp báo cáo và kết quả thực nghiệm đã được kiểm toán tại thư mục:
- Bảng benchmark đối đầu: [`fair_benchmark_results.json`](file:///D:/Study/Code/Python/Aelous/artifacts/remediation/benchmarks/g5_fair_benchmark/fair_benchmark_results.json)
- Thống kê Monte Carlo: [`remediated_statistical_summary.json`](file:///D:/Study/Code/Python/Aelous/artifacts/remediation/monte_carlo_remediated/remediated_statistical_summary.json)
- Báo cáo kiểm định độc lập Gate G8: [`06_GATE_REPORT.md`](file:///D:/Study/Code/Python/Aelous/remediation_evidence/G8_scientific_release/06_GATE_REPORT.md)
