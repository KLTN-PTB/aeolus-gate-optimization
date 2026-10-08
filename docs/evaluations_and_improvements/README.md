# Thư mục Báo cáo Đánh giá & Hướng dẫn Cải tiến Mô hình

Thư mục này tập trung toàn bộ các tài liệu đánh giá thực nghiệm (Classification & Regression) và các hướng dẫn, đặc tả kỹ thuật nhằm tối ưu hóa mô hình và dữ liệu kịch bản phục vụ bài toán xếp cổng:

---

## 1. Báo cáo Kết quả & Đánh giá Thực nghiệm
* [`classification_results_evaluation.md`](classification_results_evaluation.md): Báo cáo đánh giá chi tiết 4 mô hình phân loại dự báo trễ (XGBoost, LightGBM, CatBoost, Stacking Classifier) trên tập kiểm thử Holdout 2024. Phân tích ROC-AUC, PR-AUC, F1-Score và mức độ nhạy ngưỡng rủi ro.
* [`regression_results_evaluation.md`](regression_results_evaluation.md): Báo cáo đánh giá các mô hình hồi quy ước lượng số phút trễ (MAE, RMSE, R²).

---

## 2. Hướng dẫn & Nhật ký Cải thiện Kỹ thuật
* [`model_improvement_guide.md`](model_improvement_guide.md): Cẩm nang toàn diện về kỹ thuật tối ưu hóa mô hình học máy: xử lý biến phân loại, tuning hyperparameters, kiểm soát overfitting và phân tích Feature Importance.
* [`toi_uu_2_notebook_huan_luyen.md`](toi_uu_2_notebook_huan_luyen.md): Hướng dẫn thực hành tối ưu 2 Jupyter Notebooks huấn luyện (`tabular_classification_notebook.ipynb` và `tabular_regression_notebook.ipynb`).
* [`prediction_artifact_improvements.md`](prediction_artifact_improvements.md): Đặc tả phân tích các thiếu sót trong dữ liệu đầu ra và chuẩn hóa lược đồ kịch bản (CRS times, aircraft type, chain group, safety buffers) cho bộ giải tối ưu hóa cổng đỗ (CP-SAT).
* [`update.md`](update.md): Nhật ký tóm tắt các nâng cấp code và kiến trúc mô hình trong Giai đoạn 2.

---

## 3. Báo Cáo Tổng Hợp Tiến Độ Toàn Diện (Gửi GVHD)
* [`bao_cao_tong_hop_ket_qua_he_thong_klcn.md`](../result/bao_cao_tong_hop_ket_qua_he_thong_klcn.md): **Tệp báo cáo tổng hợp cao nhất** kết nối toàn bộ chu trình từ ML, Mô phỏng Turnaround đến Solver CP-SAT Full-Day 1.500 chuyến bay, kèm kế hoạch chi tiết các bước tiếp theo phục vụ báo cáo Giảng viên hướng dẫn.
