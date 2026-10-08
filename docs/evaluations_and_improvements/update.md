# BẢN CẬP NHẬT — GIAI ĐOẠN 2: CẢI THIỆN ĐỘ CHÍNH XÁC MÔ HÌNH
**Ngày: 27/09/2026 | File được cập nhật: `src/notebooks/tabular_classification_notebook.ipynb`**

---

## TÓM TẮT THAY ĐỔI

### Mục tiêu
Nâng ROC-AUC từ **~0.70** (baseline 55 features + XGBoost mặc định) lên **0.73 – 0.77+** bằng cách:
1. Sửa lỗi xử lý biến Categorical (loại bỏ `StandardScaler` cho mô hình cây, bật native categorical)
2. Thêm 2 mô hình Gradient Boosting mạnh: LightGBM & CatBoost
3. Nâng cấp cấu hình XGBoost (tăng số cây, kiểm soát overfit)
4. Nâng cấp Feature Importance Analysis đa mô hình
5. **MỚI**: Tích hợp mô hình học kết hợp **Stacking Ensemble (`StackingClassifier`)** huấn luyện end-to-end trong 1 lệnh gọi

---

## CHI TIẾT CÁC THAY ĐỔI

### 1. Sửa lỗi xử lý Biến Phân loại (Cell 2 + Cell 6)

**Vấn đề cũ:** Tất cả các cột (bao gồm `OP_CARRIER_CODE`, `ORIGIN_CODE`, `DEST_CODE`) đều bị chuẩn hóa qua `StandardScaler` → mô hình cây hiểu sai thứ tự (ví dụ: mã sân bay 5 > mã sân bay 3, vô nghĩa).

**Cách sửa:**
- Định nghĩa rõ ràng `CATEGORICAL_COLS = ["OP_CARRIER_CODE", "ORIGIN_CODE", "DEST_CODE"]`
- **Mô hình cây** (XGBoost, LightGBM, CatBoost, RF): Dùng dữ liệu **gốc không scale**, categorical được chuyển sang kiểu `category` trong pandas
- **Mô hình tuyến tính** (Logistic Regression): Chỉ scale các cột `float32/float64` **không bao gồm categorical**

### 2. Thêm LightGBM (Cell 2 + Cell 6)

```python
lgb.LGBMClassifier(
    n_estimators=500, max_depth=7, learning_rate=0.05,
    num_leaves=63, subsample=0.8, colsample_bytree=0.8,
    min_child_samples=100, reg_alpha=0.1, reg_lambda=1.0,
    scale_pos_weight=spw,  # Xử lý mất cân bằng nhãn
)
```
- Hỗ trợ native categorical split tự động
- Early stopping 50 rounds trên tập Validation
- Huấn luyện nhanh hơn XGBoost 2-5x trên dữ liệu lớn

### 3. Thêm CatBoost (Cell 2 + Cell 6)

```python
CatBoostClassifier(
    iterations=500, depth=7, learning_rate=0.05,
    l2_leaf_reg=3.0, auto_class_weights="Balanced",
    cat_features=[idx_carrier, idx_origin, idx_dest],  # Native categorical
    task_type="GPU",  # Tận dụng GPU, tự động fallback CPU
)
```
- Xử lý biến phân loại **tốt nhất** trong 3 thư viện (Ordered Target Encoding nội bộ)
- `auto_class_weights="Balanced"` tự động xử lý mất cân bằng nhãn
- Tự động phát hiện và fallback sang CPU nếu GPU không khả dụng

### 4. Nâng cấp XGBoost (Cell 6)

| Tham số | Giá trị cũ | Giá trị mới | Lý do |
|:---|:---:|:---:|:---|
| `n_estimators` | 150 | **300** | Tăng số cây để học sâu hơn |
| `max_depth` | 6 | **7** | Tăng độ phức tạp để nắm bắt tương tác |
| `learning_rate` | 0.08 | **0.05** | Giảm tốc độ học, cần nhiều cây hơn nhưng ổn định hơn |
| `min_child_weight` | *(mặc định 1)* | **10** | Tránh overfit trên dữ liệu hàng chục triệu dòng |
| `reg_alpha` | *(mặc định 0)* | **0.1** | Regularization L1 |
| `reg_lambda` | *(mặc định 1)* | **1.0** | Regularization L2 |
| `enable_categorical` | *(không có)* | **True** | Bật native categorical split |

### 5. Mở rộng danh sách mô hình huấn luyện (Cell 8 + Cell 10)

```python
# CŨ:
model_types=['xgb']

# MỚI:
model_types=['xgb', 'lgbm', 'catboost', 'lr']
```

Cả 4 mô hình sẽ được huấn luyện và đánh giá trên cùng dữ liệu cho cả 2 bài toán (Arrival + Departure).

### 6. Nâng cấp Feature Importance Analysis (Cell 14)

- Thu thập Feature Importance từ **cả 3 mô hình cây** (XGBoost, LightGBM, CatBoost)
- Chuẩn hóa về phần trăm để so sánh công bằng
- Tính **trung bình importance** xếp hạng
- Hiển thị bảng **Top 20 features** quan trọng nhất
- Vẽ biểu đồ **so sánh song song 3 mô hình**
- Tự động phát hiện features gần như **không đóng góp** (<0.01%)

### 7. Tích hợp Mô hình Stacking Ensemble (Cell 15 Markdown + Cell 16 Code)

**Kiến trúc:**
- **Tầng 1 (Base Models)**: Kết hợp đồng thời `XGBoost` + `LightGBM` + `CatBoost` (hoặc `RandomForest` dự phòng nếu chưa cài CatBoost).
- **Tầng 2 (Meta-Learner)**: `LogisticRegression` học cách gán trọng số tối ưu từ ma trận xác suất ngoại lai (Out-of-Fold probability predictions).
- **Cơ chế**: Dùng `StackingClassifier(cv=3, stack_method='predict_proba')`.
- **Cấu hình tối ưu thời gian**: Biến `MAX_STACK_TRAIN_SAMPLES = 500_000` (mặc định lấy mẫu ngẫu nhiên 500k dòng để fit nhanh trong vài phút, người dùng có thể đặt `None` nếu muốn fit toàn bộ 41M dòng).
- **Đánh giá đầy đủ**: Tính ROC-AUC, PR-AUC, quét ngưỡng cắt tối ưu $T^*$ trên Validation, in Classification Report trên Test 2024, và tự động cập nhật vào bảng tổng hợp kết quả cuối cùng.

---

## CÁC FILE BỊ ẢNH HƯỞNG

| File | Chi tiết thay đổi |
|:---|:---|
| `src/notebooks/tabular_classification_notebook.ipynb` | • Cập nhật Cell 2, 5, 6, 8, 10, 14<br>• Thêm mới Cell 15 (Markdown) và Cell 16 (Code Stacking Ensemble) |

## THƯ VIỆN CẦN CÀI ĐẶT THÊM (NẾU CHƯA CÓ)

```bash
pip install lightgbm catboost
```
*(Lưu ý: Notebook đã được lập trình an toàn với cơ chế fallback tự động — nếu chưa kịp cài `lightgbm` hoặc `catboost`, mô hình Stacking sẽ tự động sử dụng `RandomForest` thay thế mà không gây lỗi dừng chương trình).*

## CÁCH CHẠY

1. Mở `src/notebooks/tabular_classification_notebook.ipynb` trong Jupyter / VS Code.
2. Chạy lần lượt từ Cell 1 đến Cell 14 để so sánh các mô hình đơn lẻ.
3. Chạy Cell 16 để huấn luyện và đánh giá mô hình **Stacking Ensemble**.
4. So sánh kết quả Stacking với các mô hình đơn lẻ trong bảng tổng kết ở cuối Cell 16.
