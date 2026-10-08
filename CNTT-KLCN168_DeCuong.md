---
document_type: "Đề cương chi tiết Khóa luận tốt nghiệp"
ma_de_tai: "CNTT-KLCN168"
ten_de_tai: "Ứng dụng học máy và lập trình ràng buộc trong dự báo độ trễ chuyến bay và tối ưu tái phân bổ cổng đỗ tàu bay"
khoa_hoc: "Khóa luận cử nhân ngành CNTT, năm học 2026 - 2027"
dinh_huong: "Định hướng nghiên cứu"
gvhd:
  - "TS. Phùng Thế Bảo (baopt@huit.edu.vn)"
  - "TS. Nguyễn Huy Liêm (liemnh@huit.edu.vn)"
nhom_sinh_vien:
  - "Nguyễn Tiến Đạt - MSSV 2001230161 - Lớp 14DHTH12"
  - "Đặng Gia Hào - MSSV 2001230212 - Lớp 14DHTH12"
  - "Nguyễn Văn Hậu - MSSV 2001230225 - Lớp 14DHTH12"
thoi_gian_thuc_hien: "12 tuần, 10/08/2026 - 25/10/2026, Học kỳ 1 - Năm học 2026-2027"
nguon: "Chuyển đổi từ CNTT-KLCN168_PhungTheBao.docx để đối chiếu tiến độ với AI coding agent"
---

# Đề cương chi tiết — CNTT-KLCN168

**Khóa luận cử nhân ngành CNTT, năm học 2026 – 2027**
**Định hướng nghiên cứu**

> File này được chuyển đổi trực tiếp từ bản đề cương `.docx` gốc, giữ nguyên toàn bộ nội dung (mục tiêu, yêu cầu, thang điểm, lịch tuần, tài liệu tham khảo) để AI coding agent trong VS Code dùng làm tài liệu đối chiếu tiến độ và yêu cầu của khóa luận.

## 1. Mã đề tài: CNTT-KLCN168

## 2. Tên đề tài: Ứng dụng học máy và lập trình ràng buộc trong dự báo độ trễ chuyến bay và tối ưu tái phân bổ cổng đỗ tàu bay

## 3. Thông tin GVHD

-   Họ tên giảng viên: TS. Phùng Thế Bảo, TS. Nguyễn Huy Liêm

-   Email: baopt@huit.edu.vn, liemnh@huit.edu.vn

## 4. Nhóm sinh viên thực hiện đề tài

1)  Nguyễn Tiến Đạt MSSV: 2001230161 Lớp: 14DHTH12

2)  Đặng Gia Hào MSSV: 2001230212 Lớp: 14DHTH12

3)  Nguyễn Văn Hậu MSSV: 2001230225 Lớp: 14DHTH12

## 5. Mục tiêu

**Mục tiêu tổng quát:**

-   Xây dựng hệ thống hỗ trợ ra quyết định cho bài toán tái phân bổ cổng đỗ tàu bay, kết hợp mô hình học máy dự báo độ trễ chuyến bay với mô hình tối ưu hóa có ràng buộc trên môi trường sân bay mô phỏng, nhằm giảm tác động của độ trễ và hạn chế xung đột tài nguyên cổng.

> **Mục tiêu cụ thể:**

-   Thu thập và thực hiện tiền xử lý với bộ dữ liệu Aeolus: A Multi-structural Flight Delay Dataset.

-   Xây dựng mô hình Machine Learning (Random Forest, Logistic Regression, XGBoost) dự đoán xác suất chuyến bay bị trễ và mức độ trễ ước tính từ các đặc trưng có thể biết trước thời điểm khai thác, bao gồm lịch bay, thông tin chuyến bay, thời tiết và đặc trưng ngữ cảnh khác.

-   Tối ưu hyperparameter của mô hình ML bằng Bayesian Optimization (Optuna) và đánh giá theo quy trình chia dữ liệu theo thời gian nhằm hạn chế temporal leakage.

-   Xây dựng bộ giải Constraint Programming (CP-SAT, Google OR-Tools) cho bài toán phân cổng trên môi trường sân bay mô phỏng, bảo đảm các ràng buộc vận hành cứng.

-   Áp dụng Simulated Annealing để cải thiện lời giải khả thi của CP-SAT theo các tiêu chí mềm và giảm chi phí phát sinh do tái phân bổ cổng.

-   Đánh giá hệ thống bằng cách so sánh Greedy, CP-SAT và CP-SAT kết hợp Simulated Annealing; đồng thời kiểm tra độ bền của phương án phân cổng bằng Monte Carlo Simulation.

-   Xây dựng dashboard trực quan hóa kết quả dự báo, lịch phân cổng, các kịch bản mô phỏng và các chỉ số hiệu suất của hệ thống.

## 6. Yêu cầu

-   **Lý do chọn đề tài:** Bài toán phân bổ và tái phân bổ cổng đỗ tàu bay (gate assignment) có ý nghĩa thực tiễn cao vì độ trễ chuyến bay có thể lan truyền giữa các chuyến bay liên tiếp và gây xung đột tài nguyên cổng. Đề tài kết hợp ML và Constraint Programming theo kiến trúc "Predict then Optimize" --- hướng tiếp cận phù hợp với xu hướng nghiên cứu hiện nay và với năng lực, định hướng Khoa học Dữ liệu và AI của nhóm.

-   **Tình hình nghiên cứu:** Nhiều nghiên cứu đã ứng dụng ML (Random Forest, XGBoost) để dự đoán trễ chuyến bay dựa trên đặc trưng lịch bay và thời tiết [9]--[11]. Bài toán Gate Assignment Problem (GAP) được nghiên cứu rộng rãi bằng quy hoạch nguyên, heuristic và metaheuristic như Simulated Annealing [12]--[14]. Elmachtoub và Grigas [15] hệ thống hóa hướng tiếp cận "Smart Predict then Optimize", xem xét chất lượng dự báo cùng tác động của nó lên quyết định tối ưu. Khoảng trống nghiên cứu nằm ở việc kết nối trực tiếp dự báo độ trễ với bài toán tái phân bổ cổng trong một pipeline thống nhất trên môi trường mô phỏng có kiểm soát.

-   **Giải pháp đề xuất và nhiệm vụ nghiên cứu:** Đề tài đề xuất pipeline gồm: (1) tiền xử lý dữ liệu Aeolus (2) dự báo rủi ro trễ bằng XGBoost; (3) sử dụng kết quả dự báo làm đầu vào cho bộ giải CP-SAT giải bài toán tái phân bổ cổng, kết hợp Simulated Annealing để cải thiện lời giải theo các tiêu chí mềm; (4) đánh giá bằng so sánh Greedy/CP-SAT/CP-SAT+SA và Monte Carlo Simulation, trực quan hóa kết quả trên dashboard.

-   **Mô tả bài toán:** Dự báo độ trễ chuyến bay: dự đoán P(delay ≥ 15 phút) và mức độ trễ ước tính ΔT từ các đặc trưng biết trước thời điểm khai thác trên bộ dữ liệu Aeolus: A Multi-structural Flight Delay Dataset. Gate Assignment Problem (GAP): phân/tái phân bổ cổng cho các chuyến bay trên môi trường sân bay mô phỏng (20--50 cổng, 100--300 chuyến bay/ngày), bảo đảm các ràng buộc vận hành cứng.

-   **Giới thiệu thuật toán:** XGBoost: mô hình gradient boosting dùng để dự báo phân loại/hồi quy độ trễ. Logistic Regression, Random Forest và Stacking Ensemble dùng để so sánh hiệu quả dự báo. CP-SAT (Google OR-Tools): bộ giải Constraint Programming cho bài toán GAP với các ràng buộc cứng. Simulated Annealing: metaheuristic cải thiện lời giải khả thi của CP-SAT theo các tiêu chí mềm. Optuna: framework tối ưu hyperparameter bằng Bayesian Optimization.

-   **Đánh giá thuật toán:** XGBoost có ưu điểm về độ chính xác và khả năng diễn giải qua SHAP nhưng cần điều chỉnh siêu tham số cẩn thận để tránh overfitting. CP-SAT bảo đảm tính khả thi của các ràng buộc cứng nhưng có thể tốn thời gian giải khi quy mô lớn; Simulated Annealing bổ sung khả năng cải thiện các mục tiêu mềm mà CP-SAT không tối ưu trực tiếp, đổi lại không bảo đảm tối ưu toàn cục.

-   **Mô tả cấu hình hệ thống và ngôn ngữ lập trình:** Windows 11, CPU tối thiểu Core i5, RAM ≥ 16GB, ổ SSD. Ngôn ngữ lập trình: Python 3.11 trở lên, sử dụng các thư viện Pandas, NumPy, Scikit-learn, XGBoost, Optuna, Google OR-Tools (CP-SAT) và SHAP.

-   **Cài đặt thực nghiệm thuật toán:** Huấn luyện mô hình XGBoost dự báo trễ với tối ưu hyperparameter bằng Optuna; cài đặt bộ giải CP-SAT cho bài toán GAP với các ràng buộc cứng; cài đặt Simulated Annealing để cải thiện lời giải CP-SAT theo các tiêu chí mềm.

-   **Đánh giá mô hình dự báo** bằng ROC-AUC, MAE, RMSE, Precision, Recall, F1 trên tập kiểm thử chia theo thời gian (temporal split). So sánh mô hình chỉ sử dụng Tabular với mô hình kết hợp Tabular + Flight Chain Features. Đánh giá bài toán tối ưu bằng cách so sánh Greedy, CP-SAT và CP-SAT kết hợp Simulated Annealing theo tổng chi phí do trễ, số lần tái phân bổ, xung đột cổng và thời gian giải; kiểm tra độ bền của phương án phân cổng bằng Monte Carlo Simulation (500 kịch bản).

-   **Xây dựng dashboard** (Streamlit/Plotly Dash) minh họa tính ứng dụng của hệ thống, gồm: Các biểu đồ hiển thị lịch phân cổng và cảnh báo rủi ro trễ theo từng chuyến bay; mô-đun so sánh Greedy/CP-SAT/CP-SAT kết hợp Simulated Annealing và biểu đồ phân phối kết quả Monte Carlo Simulation.

## 7. Môi trường thực hiện

Thực hiện trên máy tính cá nhân kết hợp với các nền tảng mã nguồn mở phục vụ tiền xử lý dữ liệu, xây dựng mô hình học máy, tối ưu hóa có ràng buộc, mô phỏng và trực quan hóa. Để phù hợp với quy mô dữ liệu Aeolus, khóa luận sử dụng tập con dữ liệu theo thời gian/sân bay thay vì yêu cầu tải và xử lý toàn bộ dataset cùng lúc.

-   **Hệ điều hành:** Windows 11 (hoặc Ubuntu 22.04 LTS).

-   **Ngôn ngữ lập trình:** Python 3.11 trở lên.

-   **Môi trường phát triển:** Visual Studio Code, Jupyter Notebook, Antigravity IDE.

-   **Thư viện xử lý dữ liệu:** Pandas, NumPy, Optuna.

-   **Thư viện trực quan hóa dữ liệu:** Matplotlib, Seaborn, Plotly.

-   **Thư viện ML:** Scikit-learn, XGBoost; có thể sử dụng thêm LightGBM hoặc CatBoost làm baseline mở rộng khi tài nguyên cho phép.

-   **Thư viện tối ưu hóa:** Google OR-Tools (Constraint Programming -- CP-SAT).

-   **Thư viện giải thích mô hình:** SHAP.

-   **Quản lý mã nguồn:** Git và GitHub.

-   **Thiết bị thực hiện:** Máy tính cá nhân có tối thiểu CPU Intel Core i5 hoặc tương đương, RAM từ 16 GB trở lên và ổ cứng SSD; ưu tiên sử dụng SSD và xử lý dữ liệu theo từng tập con/chunk để hạn chế yêu cầu bộ nhớ.

## 8. Thời gian thực hiện:

-   **Thời gian thực hiện:** 12 tuần (từ ngày **10/08/2026** đến ngày **25/10/2026**).

-   **Học kỳ / Năm học:** Học kỳ 1 -- Năm học 2026 -- 2027.

## 9. Thang điểm

+---------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+---------+----------+
| **STT**       | **Nội dung**                                                                                                                                                                                                          | **CLO** | **Điểm** |
+===============+=======================================================================================================================================================================================================================+=========+==========+
| 1.            | Tổng quan về đề tài                                                                                                                                                                                                   | CLO1.1  | 0.25     |
|               |                                                                                                                                                                                                                       |         |          |
|               | -   Xác định lý do chọn đề tài, mục tiêu nghiên cứu                                                                                                                                                                   |         | 0.75     |
|               |                                                                                                                                                                                                                       |         |          |
|               | -   Khảo sát các công trình nghiên cứu liên quan                                                                                                                                                                      |         | 0.25     |
|               |                                                                                                                                                                                                                       |         |          |
|               | -   Xác định đối tượng, phương pháp và độ đo của nghiên cứu                                                                                                                                                           |         |          |
+---------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+---------+----------+
| 2.            | Lập kế hoạch và phân công thực hiện công việc                                                                                                                                                                         | CLO6    | 0.25     |
+---------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+---------+----------+
| 3.            | Nghiên cứu các nội dung liên quan:                                                                                                                                                                                    | CLO1.2  | 0.5      |
|               |                                                                                                                                                                                                                       |         |          |
|               | -   Mô tả các khái niệm, định nghĩa liên quan: dự báo độ trễ chuyến bay, Gate Assignment Problem (GAP), Constraint Programming (CP-SAT), Simulated Annealing và kiến trúc Predict-then-Optimize                       |         | 0.25     |
|               |                                                                                                                                                                                                                       |         |          |
|               | -   Ví dụ minh hoạ: một kịch bản chuyến bay bị trễ làm phát sinh xung đột cổng và cách bài toán tối ưu tái phân bổ cổng xử lý tình huống này                                                                          |         |          |
+---------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+---------+----------+
| 4.            | Mô tả thuật toán:                                                                                                                                                                                                     | CLO2.1  | 0.25     |
|               |                                                                                                                                                                                                                       |         |          |
|               | -   Mô tả các bước thực hiện của thuật toán: quy trình huấn luyện XGBoost dự báo P(delay ≥ 15 phút) và ΔT trễ; mô hình CP-SAT cho bài toán GAP; cơ chế cải thiện lời giải bằng Simulated Annealing                    |         | 0.25     |
|               |                                                                                                                                                                                                                       |         |          |
|               | -   Phân tích ưu, nhược điểm của XGBoost, CP-SAT và Simulated Annealing so với các phương pháp Greedy/heuristic truyền thống trong bài toán dự báo trễ và phân cổng                                                   |         |          |
+---------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+---------+----------+
|               | -   Mô tả bộ dữ liệu thực nghiệm Aeolus: A Multi-structural Flight Delay Dataset (Tabular, Flight Chain), nguồn gốc từ BTS và Meteostat, phạm vi 2016--2024 và tập con sử dụng                                        | CLO2.2  | 0.5      |
+---------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+---------+----------+
| 5.            | Cài đặt thuật toán và ứng dụng minh hoạ:                                                                                                                                                                              | CLO3    | **4.0**  |
|               |                                                                                                                                                                                                                       |         |          |
|               | -   Mô tả cấu hình hệ thống: hệ điều hành Windows 11/Ubuntu 22.04, CPU tối thiểu Core i5, RAM ≥ 16GB, Lựa chọn môi trường thử nghiệm: Visual Studio Code, Jupyter Notebook để phát triển mô hình ML và bộ giải CP-SAT |         | 0.25     |
|               |                                                                                                                                                                                                                       |         |          |
|               | -   Lựa chọn môi trường thử nghiệm: Visual Studio Code, Jupyter Notebook để phát triển mô hình ML và bộ giải CP-SAT.                                                                                                  |         | 0.25     |
|               |                                                                                                                                                                                                                       |         |          |
|               | -   Lựa chọn ngôn ngữ lập trình: Sử dụng ngôn ngữ Python để huấn luyện mô hình ML, bộ giải CP-SAT và xây dựng dashboard                                                                                               |         | 0.25     |
|               |                                                                                                                                                                                                                       |         |          |
|               | -   Cài đặt thực nghiệm thuật toán:                                                                                                                                                                                   |         | 0.5      |
|               |                                                                                                                                                                                                                       |         |          |
|               | + Cài đặt mô hình XGBoost Classifier/Regressor dự báo P(delay ≥ 15 phút) và ΔT trễ; cài đặt bộ giải CP-SAT (Google OR-Tools) cho bài toán Gate Assignment với các ràng buộc cứng                                     |         | 0.5      |
|               |                                                                                                                                                                                                                       |         |          |
|               | + Cài đặt tối ưu hyperparameter bằng Bayesian Optimization (Optuna) cho mô hình XGBoost; cài đặt Simulated Annealing để cải thiện lời giải khả thi của CP-SAT theo các tiêu chí mềm                                  |         | 0.5      |
|               |                                                                                                                                                                                                                       |         |          |
|               | + Đánh giá thực nghiệm bằng ROC-AUC, MAE, RMSE, Precision, Recall, F1 (temporal split); so sánh Greedy, CP-SAT và CP-SAT kết hợp Simulated Annealing; kiểm tra độ bền bằng Monte Carlo Simulation (500 kịch bản)     |         | 0.5      |
|               |                                                                                                                                                                                                                       |         |          |
|               | -   Cài đặt chức năng, giao diện ứng dụng                                                                                                                                                                             |         | 0.25     |
|               |                                                                                                                                                                                                                       |         |          |
|               | + Cài đặt giao diện dashboard trực quan hóa (Streamlit/Plotly Dash) hiển thị lịch phân cổng, cảnh báo rủi ro trễ và các chỉ số hiệu suất hệ thống                                                                    |         | 0.5      |
|               |                                                                                                                                                                                                                       |         |          |
|               | + Tổ chức cấu trúc lưu trữ kết quả: mô hình XGBoost đã huấn luyện, lịch phân cổng CP-SAT/CP-SAT+SA, log Optuna và kết quả Monte Carlo theo từng kịch bản                                                             |         | 0.5      |
|               |                                                                                                                                                                                                                       |         |          |
|               | + Cài đặt chức năng 1: Gantt chart hiển thị lịch phân cổng và cảnh báo rủi ro trễ theo từng chuyến bay                                                                                                               |         |          |
|               |                                                                                                                                                                                                                       |         |          |
|               | + Cài đặt chức năng 2: mô-đun so sánh Greedy/CP-SAT/CP-SAT+SA và biểu đồ phân phối kết quả Monte Carlo Simulation                                                                                                    |         |          |
+---------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+---------+----------+
|               | Triển khai trên dữ liệu thực tế: chạy toàn bộ pipeline (tiền xử lý, dự báo XGBoost, tối ưu CP-SAT/SA) trên tập con dữ liệu Aeolus theo sân bay/thời gian đã lựa chọn                                                  | CLO4    | 0.75     |
+---------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+---------+----------+
| 6.            | Nội dung kiến thức trình bày trong quyển báo cáo                                                                                                                                                                      | CLO5.1  | 0.5      |
+---------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+---------+----------+
| 7.            | Hình thức, định dạng quyển báo cáo                                                                                                                                                                                    | CLO5.1  | 0.5      |
+---------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+---------+----------+
| 8.            | Thái độ, tác phong làm việc                                                                                                                                                                                           | CLO6    | 0.5      |
+---------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+---------+----------+
| 9.            | Phong cách báo cáo, Slide.                                                                                                                                                                                            | CLO5.2  | 0.5      |
+---------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+---------+----------+
| 10.           | Cộng điểm khuyến khích cho nhóm sinh viên tham gia thực hiện NCKH liên quan nội dung đề tài (tổng điểm chung không vượt quá 10 điểm)                                                                                  | CLO3    | **1.0**  |
|               |                                                                                                                                                                                                                       |         |          |
|               | -   Thi SV NCKH đạt giải cấp Khoa hoặc có bài báo đăng hội thảo cấp Khoa.                                                                                                                                             |         | 0.5      |
|               |                                                                                                                                                                                                                       |         |          |
|               | -   Thi SV NCKH đạt giải cấp Trường hoặc có bài báo đăng tạp chí khoa học cấp Trường trở lên                                                                                                                          |         | 1.0      |
+---------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+---------+----------+
| **Tổng cộng** |                                                                                                                                                                                                                       |         | **10.0** |
+---------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+---------+----------+

## 10. Thời gian và các công việc trong tuần:

+----------+----------------------------------------------------------------------------------------------------------+
| **Tuần** | **Nội dung công việc**                                                                                   |
+==========+==========================================================================================================+
| 1.       | -   Nghiên cứu tổng quan về bài toán dự báo độ trễ chuyến bay và tái phân bổ cổng đỗ tàu bay.            |
|          |                                                                                                          |
|          | -   Khảo sát các nghiên cứu liên quan về ML, Constraint Programming và Predict then Optimize.            |
|          |                                                                                                          |
|          | -   Tìm hiểu cấu trúc và giới hạn của bộ dữ liệu Aeolus.                                                 |
+----------+----------------------------------------------------------------------------------------------------------+
| 11.      | -   Khảo sát schema, quy mô và các modality của Aeolus.                                                  |
|          |                                                                                                          |
|          | -   Xác định tập con dữ liệu theo thời gian/sân bay và chiến lược temporal split.                        |
|          |                                                                                                          |
|          | -   Xác định biến đầu vào, nhãn và các trường có nguy cơ data leakage.                                   |
+----------+----------------------------------------------------------------------------------------------------------+
| 12.      | -   Tiền xử lý dữ liệu, xử lý giá trị thiếu và dữ liệu bất thường.                                       |
|          |                                                                                                          |
|          | -   Feature Engineering từ lịch bay, thời tiết và Flight Chain.                                          |
|          |                                                                                                          |
|          | -   Xây dựng pipeline dữ liệu tái lập và kiểm tra leakage.                                               |
+----------+----------------------------------------------------------------------------------------------------------+
| 13.      | -   Xây dựng baseline cho bài toán classification/regression.                                            |
|          |                                                                                                          |
|          | -   Đánh giá Logistic Regression và Random Forest làm các mô hình baseline và thiết lập mốc so sánh**.** |
+----------+----------------------------------------------------------------------------------------------------------+
| 14.      | -   Xây dựng và tối ưu mô hình XGBoost.                                                                  |
|          |                                                                                                          |
|          | -   Điều chỉnh siêu tham số bằng Optuna.                                                                 |
|          |                                                                                                          |
|          | -   Đánh giá ROC-AUC, MAE, RMSE, Precision, Recall, F1 trên validation/test theo thời gian.              |
+----------+----------------------------------------------------------------------------------------------------------+
| 15.      | -   Phân tích Feature Importance và SHAP.                                                                |
|          |                                                                                                          |
|          | -   Kiểm tra temporal leakage và độ ổn định của mô hình.                                                 |
+----------+----------------------------------------------------------------------------------------------------------+
| 16.      | -   Khảo sát bài toán Gate Assignment và Gate Reassignment.                                              |
|          |                                                                                                          |
|          | -   Xây dựng môi trường sân bay mô phỏng với 20--50 cổng.                                                |
|          |                                                                                                          |
|          | -   Xây dựng biến quyết định, ràng buộc cứng và hàm mục tiêu.                                            |
+----------+----------------------------------------------------------------------------------------------------------+
| 17.      | -   Xây dựng bộ giải CP-SAT bằng Google OR-Tools.                                                        |
|          |                                                                                                          |
|          | -   Kiểm thử tính khả thi và thời gian giải trên nhiều quy mô kịch bản.                                  |
+----------+----------------------------------------------------------------------------------------------------------+
| 18.      | -   Kết nối dự báo delay với bài toán tái phân bổ cổng.                                                  |
|          |                                                                                                          |
|          | -   Xây dựng Simulated Annealing để cải thiện lời giải CP-SAT.                                           |
|          |                                                                                                          |
|          | -   Thực hiện các kịch bản phát sinh độ trễ và tái phân bổ cổng.                                         |
+----------+----------------------------------------------------------------------------------------------------------+
| 19.      | -   Đánh giá Greedy, CP-SAT và CP-SAT + Simulated Annealing.                                             |
|          |                                                                                                          |
|          | -   Chạy Monte Carlo 500 kịch bản để đánh giá robustness.                                                |
+----------+----------------------------------------------------------------------------------------------------------+
| 20.      | -   Viết và hoàn thiện các chương của khóa luận.                                                         |
|          |                                                                                                          |
|          | -   Chuẩn hóa hình ảnh, bảng biểu, metric và tài liệu tham khảo.                                         |
|          |                                                                                                          |
|          | -   Chỉnh sửa theo góp ý của giảng viên hướng dẫn.                                                       |
+----------+----------------------------------------------------------------------------------------------------------+
| 21.      | -   Hoàn chỉnh báo cáo và kết quả thực nghiệm.                                                           |
|          |                                                                                                          |
|          | -   Hoàn thiện slide, kịch bản demo và mã nguồn tái lập.                                                 |
|          |                                                                                                          |
|          | -   Nộp báo cáo và chuẩn bị bảo vệ.                                                                      |
+----------+----------------------------------------------------------------------------------------------------------+

## 11. Tài liệu tham khảo

**[1]** L. Breiman, "Random Forests," *Machine Learning*, vol. 45, no. 1, pp. 5--32, 2001.

**[2]** T. Chen and C. Guestrin, "XGBoost: A Scalable Tree Boosting System," in *Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining*, 2016, pp. 785--794.

**[3]** G. Ke, Q. Meng, T. Finley, T. Wang, W. Chen, W. Ma, Q. Ye, and T.-Y. Liu, "LightGBM: A Highly Efficient Gradient Boosting Decision Tree," *Advances in Neural Information Processing Systems (NeurIPS)*, vol. 30, 2017.

**[4]** A. V. Dorogush, V. Ershov, and A. Gulin, "CatBoost: Gradient Boosting with Categorical Features Support," *arXiv preprint arXiv:1810.11363*, 2018.

**[5]** L. Perron and V. Furnon, "OR-Tools Constraint Programming Solver," *Google OR-Tools Documentation*, Google LLC. [Online]. Available: <https://developers.google.com/optimization>

**[6]** S. Kirkpatrick, C. D. Gelatt, and M. P. Vecchi, "Optimization by Simulated Annealing," *Science*, vol. 220, no. 4598, pp. 671--680, 1983. <https://doi.org/10.1126/science.220.4598.671>

**[7]** T. Akiba, S. Sano, T. Yanase, T. Ohta, and M. Koyama, "Optuna: A Next-generation Hyperparameter Optimization Framework," in *Proceedings of the 25th ACM SIGKDD International Conference on Knowledge Discovery & Data Mining*, 2019, pp. 2623--2631. <https://doi.org/10.1145/3292500.3330701>

**[8]** S. M. Lundberg and S.-I. Lee, "A Unified Approach to Interpreting Model Predictions," *Advances in Neural Information Processing Systems (NeurIPS)*, vol. 30, 2017.

**[9]** L. Carvalho, A. Sternberg, L. Goncalves, A. Cruz, J. Soares, D. Brandão, G. Carvalho, and E. Ogasawara, "On the Relevance of Data Science for Flight Delay Research: A Systematic Review," *Transport Reviews*, vol. 41, no. 4, pp. 499--528, 2021. <https://doi.org/10.1080/01441647.2020.1861123>

**[10]** Z. Guo, B. Yu, M. Hao, W. Wang, Y. Jiang, and F. Zong, "A Novel Hybrid Method for Flight Departure Delay Prediction Using Random Forest Regression and Maximal Information Coefficient," *Aerospace Science and Technology*, vol. 116, p. 106822, 2021. <https://doi.org/10.1016/j.ast.2021.106822>

**[11]** I. Hatıpoğlu, Ö. Tosun, and N. Tosun, "Flight Delay Prediction Based with Machine Learning," *LogForum*, vol. 18, no. 1, pp. 97--111, 2022. <https://doi.org/10.17270/J.LOG.2022.655>

**[12]** A. Bolat, "Procedures for Providing Robust Gate Assignments for Arriving Aircrafts," *European Journal of Operational Research*, vol. 120, no. 1, pp. 63--80, 2000. <https://doi.org/10.1016/S0377-2217(98)00375-0>

**[13]** A. Haghani and M.-C. Chen, "Optimizing Gate Assignments at Airport Terminals," *Transportation Research Part A: Policy and Practice*, vol. 32, no. 6, pp. 437--454, 1998. <https://doi.org/10.1016/S0965-8564(98)00003-4>

**[14]** A. Bolat, "Models and a Genetic Algorithm for Static Aircraft-Gate Assignment Problem," *Journal of the Operational Research Society*, vol. 52, no. 10, pp. 1107--1120, 2001. <https://doi.org/10.1057/palgrave.jors.2601190>

**[15]** A. N. Elmachtoub and P. Grigas, "Smart 'Predict, then Optimize'," *Management Science*, vol. 68, no. 1, pp. 9--26, 2022. <https://doi.org/10.1287/mnsc.2020.3922>

**[16]** Bureau of Transportation Statistics (BTS), "Airline On-Time Performance Data," U.S. Department of Transportation. [Online]. Available: <https://www.bts.gov/>

**[17]** Meteostat, "Historical weather and climate data." [Online]. Available: https://meteostat.net/

**[18]** Flnny, "Delay-data: Aeolus: A Multi-structural Flight Delay Dataset," GitHub repository. [Online]. Available: https://github.com/Flnny/Delay-data

**[19]** Lin Xu, Xinyun Yuan, Yuxuan Liang, Suwan Yin, and Yuankai Wu, "Aeolus: A Multi-structural Flight Delay Dataset," Advances in Neural Information Processing Systems 38 (NeurIPS 2025), Datasets and Benchmarks Track, 2025. [Online]. Available: https://papers.neurips.cc/paper_files/paper/2025/file/586fbdff064d506f5af3e3db82681f84-Abstract-Datasets_and_Benchmarks_Track.html

## 12. Một số yêu cầu khác

-   Số lượng SV tối đa thực hiện đề tài: 3 sinh viên.

-   Có khả năng và tư duy lập trình, đọc hiểu tiếng Anh,...

-   Gặp giảng viên hướng dẫn ít nhất 1 lần/tuần, thực hiện đề tài theo sự phân công của giảng viên hướng dẫn. Trước mỗi buổi báo cáo, sinh viên phải tích hợp những nội dung được phân công vào chung trong một tài liệu/ phần mềm.

Tp.HCM, ngày 18 tháng 7 năm 2026

  -----------------------------------------------------------------------
  ***Trưởng bộ môn***                 ***Giảng viên hướng dẫn***
  ----------------------------------- -----------------------------------
  *(ký và ghi rõ họ tên)*             *(ký và ghi rõ họ tên)*

  -----------------------------------------------------------------------
