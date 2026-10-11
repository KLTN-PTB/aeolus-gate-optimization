# UI-R01 — 04. MONTE CARLO MULTI-SOLVER CONTAMINATION GUARD REPORT

## 1. MÔ TẢ LỖI PHÁT HIỆN TẠI UI-R00 (ISSUE-R00-03)

### 1.1. Hiện tượng ô nhiễm dữ liệu thực nghiệm
Tập tin kết quả mô phỏng Monte Carlo `artifacts/remediation/monte_carlo/fixed_plan_results.csv` và `recourse_results.csv` chứa tổng cộng **1.500 dòng**, được chia đều cho 3 thuật toán tối ưu hóa nền tảng:
- 500 kịch bản đánh giá trên nền nghiệm của **Greedy**.
- 500 kịch bản đánh giá trên nền nghiệm của **CP-SAT**.
- 500 kịch bản đánh giá trên nền nghiệm của **Hybrid**.

Trong khi đó, tập tin `oracle_results.csv` chỉ chứa 500 dòng của `Oracle_Greedy`.

### 1.2. Hậu quả trên các biểu đồ thống kê Pre-R01
Trước khi thực hiện UI-R01, trang `page_05_robustness_lab.py` đã truyền thẳng toàn bộ DataFrame 1.500 dòng chưa qua lọc vào các hàm tạo biểu đồ Plotly:
1. **CHART-12 (Histogram phân phối chi phí):** Trộn lẫn 1.500 điểm chi phí của 3 thuật toán vào làm một cột histogram duy nhất mang tên "Mode B: Reactive Recourse", tạo ra một phân phối đa đỉnh sai lệch không phản ánh bất kỳ thuật toán đơn lẻ nào.
2. **CHART-13 (Hàm phân phối tích lũy thực nghiệm ECDF):** Tính toán xác suất tích lũy $P(\text{Cost} \le x)$ trên 1.500 điểm bị pha tạp, làm sai lệch hoàn toàn chỉ số rủi ro đuôi P95 và CVaR.
3. **CHART-14 (Boxplot số lần đổi cổng & cổng xa):** Vẽ biểu đồ hộp dựa trên cỡ mẫu 1.500 thay vì 500.
4. **CHART-15 (Vết hội tụ kỳ vọng Monte Carlo - Running Mean Convergence Trace):**
   - Vết hội tụ kỳ vọng chạy qua 1.500 bước liên tiếp: 500 bước đầu là kịch bản của Greedy, tiếp theo là 500 bước của CP-SAT, và 500 bước cuối là của Hybrid.
   - Đây là một sai lầm toán học nghiêm trọng: running mean $\mu_n = \frac{1}{n} \sum_{i=1}^n X_i$ bị nhảy giật mạnh khi chuyển từ phân phối của thuật toán này sang thuật toán khác, phá hủy hoàn toàn ý nghĩa chứng minh định lý giới hạn trung tâm và tính ổn định của mô phỏng.
5. **Scenario Drill-down:** Hàm `adapt_mc_scenario_drilldown` lấy dòng đầu tiên khớp `realization_id` (`iloc[0]`), dẫn đến việc luôn luôn hiển thị kết quả của thuật toán Greedy thay vì thuật toán CP-SAT.

---

## 2. KIẾN TRÚC BẢO VỆ ĐÃ TRIỂN KHAI (GUARD ARCHITECTURE)

### 2.1. Thư viện Kiểm định Khoa học Core Validation
Đã bổ sung phương thức `validate_single_solver_dataframe` vào `ScientificValidator` ([`dashboard/core/validation.py`](file:///D:/Study/Code/Python/Aelous/dashboard/core/validation.py)):
```python
@classmethod
def validate_single_solver_dataframe(
    cls,
    df: Any,
    target_solver: Optional[str] = "CPSat",
    allow_filter: bool = True,
) -> Any:
    """Validate that a Monte Carlo DataFrame is homogeneous (contains only a single solver)."""
    if not isinstance(df, pd.DataFrame) or df.empty or "solver_name" not in df.columns:
        return df
    unique_solvers = df["solver_name"].dropna().unique()
    if len(unique_solvers) <= 1:
        return df
    if not allow_filter:
        raise IncompatibleComparisonError(
            f"Multi-solver contamination detected: DataFrame contains multiple solvers {list(unique_solvers)}. "
            "Monte Carlo statistical analysis requires homogeneous single-solver datasets."
        )
    if target_solver and target_solver in unique_solvers:
        return df[df["solver_name"] == target_solver].copy()
    return df[df["solver_name"] == unique_solvers[0]].copy()
```

### 2.2. Bảo vệ Visualizers Robustness Charts
Trong [`dashboard/visualizers/robustness_charts.py`](file:///D:/Study/Code/Python/Aelous/dashboard/visualizers/robustness_charts.py):
- Mọi hàm visualizer (`create_mc_cost_distribution_figure`, `create_mc_ecdf_figure`, `create_mc_boxplot_figure`, `create_mc_convergence_figure`) đều được bổ sung tham số `solver_name: Optional[str] = "CPSat"`.
- Trước khi xử lý tính toán số học, các hàm đều tự động áp dụng bộ lọc `validate_single_solver_dataframe(df, solver_name)`.
- Nhờ đó, ngay cả khi một module giao diện nào đó vô tình truyền vào một DataFrame 1.500 dòng bị lẫn solver, visualizer sẽ tự động cô lập đúng tập 500 dòng của solver được yêu cầu, bảo toàn tính toán học và tính hội tụ.

### 2.3. Điều khiển Tương tác trên Page 05
Trong [`dashboard/pages/page_05_robustness_lab.py`](file:///D:/Study/Code/Python/Aelous/dashboard/pages/page_05_robustness_lab.py):
- Bổ sung bộ chọn thuật toán cơ sở:
  ```python
  available_solvers = ["CPSat", "Greedy", "Hybrid"]
  selected_solver = st.selectbox(
      "Thuật toán khảo sát độ vững (Robustness Baseline Solver):",
      available_solvers,
      index=0,
      help="Lọc dữ liệu Monte Carlo theo thuật toán được áp dụng cho kế hoạch cơ sở. Mặc định là CP-SAT.",
  )
  ```
- Dữ liệu `fixed_sub` và `recourse_sub` được lọc dứt khoát theo `selected_solver` trước khi truyền vào 4 biểu đồ, khối phân tích so sánh cặp (Paired Differences) và khối truy vết kịch bản chi tiết (Scenario Drill-down).
- Hàm `adapt_mc_scenario_drilldown` được truyền `solver_name=selected_solver` để truy xuất chính xác bản ghi của thuật toán đang được khảo sát.

---

## 3. BẰNG CHỨNG THỰC NGHIỆM TỰ ĐỘNG

Bộ test tự động `tests/dashboard/test_ui_r01_data_integrity.py` đã xác minh:
- `test_r01_t10_validate_single_solver_dataframe_filters_to_target`: Đảm bảo từ 1.500 dòng lọc sạch còn đúng 500 dòng CP-SAT.
- `test_r01_t11_validate_single_solver_dataframe_single_solver_unchanged`: Đảm bảo dữ liệu đơn solver không bị thay đổi.
- `test_r01_t12_cost_distribution_figure_guards_against_mixing`: Đảm bảo CHART-12 ngăn chặn trộn mẫu thành công.
- `test_r01_t13_ecdf_figure_guards_against_mixing`: Đảm bảo CHART-13 ngăn chặn trộn mẫu thành công.
- `test_r01_t14_boxplot_and_convergence_guard_against_mixing`: Đảm bảo CHART-14 và CHART-15 chạy đúng trên 500 điểm, không bị kéo dài thành 1.500 điểm.
- `test_r01_t15_mc_drilldown_respects_solver_name`: Đảm bảo drill-down trả về đúng solver được chỉ định.
- `test_r01_t16_scientific_validator_strict_contamination_rejection`: Đảm bảo kích hoạt `IncompatibleComparisonError` khi cấm trộn dữ liệu.
