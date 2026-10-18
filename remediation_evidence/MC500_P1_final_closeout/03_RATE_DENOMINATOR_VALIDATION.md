# AEOLUS-MC500-P1: RATE DENOMINATOR VALIDATION & CONSERVATION AUDIT

**Date:** 2026-10-12  
**Auditor:** Scientific Reproducibility Engineer & Python Integration Verification Engineer  
**Sprint:** AEOLUS-MC500-P1-CLOSEOUT  
**Target Code:** `src/simulation/monte_carlo_engine_v2.py` (`SimulationExecutionLedger.compute_rates()`)  
**Test Suite:** `tests/test_mc500_ledger_runner_integration.py` (`LEDGER-21`)  
**Status:** **PASSED / RATE DENOMINATORS MATHEMATICALLY RIGOROUS & TEST-VERIFIED**

---

## 1. Executive Summary

Báo cáo kiểm toán độc lập đã phát hiện lỗi logic mẫu số trong phương thức tính tỷ lệ `SimulationExecutionLedger.compute_rates()`:
- Tại thử nghiệm $N=5$, `evaluation_failure_rate.denominator` được ghi nhận là **5**, trong khi tài liệu thiết kế và hợp đồng bảo tồn toán học quy định mẫu số của tỷ lệ lỗi đánh giá phải là **55 expected evaluation slots** ($5 \text{ realizations} \times 11 \text{ protocol slots}$).
- Mặc dù số lỗi thực tế trong hai pilot bằng 0 ($0 / 5 = 0.0$ và $0 / 55 = 0.0$), dẫn đến tỷ lệ tính ra vô tình bằng $0.0$, nhưng đây là sự đúng ngẫu nhiên không thể chấp nhận trong kiểm toán khoa học (Accidental correctness).

Tuân thủ quy tắc kiểm chuẩn không khoan nhượng (Non-negotiable rule):
1. Kiểm toán viên đã viết ca kiểm thử đối kháng tiêm lỗi `LEDGER-21` với 5 realizations, 55 expected slots và 1 evaluation failure.
2. Chứng minh kiểm thử **FAIL** trên mã nguồn cũ (`AssertionError: assert 5 == 55`).
3. Thực hiện sửa đổi tối thiểu trong `compute_rates()` để gán mẫu số đúng bằng `acc["n_expected_evaluations"]`.
4. Chứng minh toàn bộ các bài test **PASS** (22/22 adversarial ledger tests, 168/168 tổng bộ test).
5. Tái thực thi Pilot N=5 và N=20 để cập nhật tệp kết quả thô.

---

## 2. Hợp đồng Định nghĩa Mẫu số (Rate Denominators Contract)

Theo kiến trúc hạch toán hai tầng (Two-Tier Conservation Ledger Architecture), các mẫu số được định nghĩa chặt chẽ như sau:

| Tỷ lệ Thống kê (`Metric`) | Tử số (`Numerator`) | Mẫu số Chuẩn (`Authoritative Denominator`) | Ý nghĩa Xác suất & Thống kê | Mẫu số trong N=5 | Mẫu số trong N=20 |
|---|---|---|---|:---:|:---:|
| `generation_failure_rate` | Số kịch bản ngẫu nhiên sinh thất bại (`n_generation_failures`) | Tổng số kịch bản được yêu cầu (`n_requested` / `n_requested_realizations`) | Xác suất mô hình Copula hoặc phân phối Student-t gặp lỗi lấy mẫu trên không gian tham số. | **5** | **20** |
| `evaluation_failure_rate` | Số lượt đánh giá solver bị crash/exception (`n_evaluation_failures`) | Tổng số lượt đánh giá solver dự kiến (`n_expected_evaluations` = $N_{\text{gen}} \times 11$) | Xác suất một slot tối ưu hóa cụ thể (ví dụ Mode B2-Hybrid) bị sập thuật toán. | **55** | **220** |
| `composite_feasible_rate` | Số lượt đánh giá thỏa mãn toàn bộ ràng buộc cứng (`n_feasible`) | Tổng số lượt đánh giá đã hoàn thành hợp lệ (`n_completed_evaluations` / `n_evaluated`) | Tỷ lệ khả thi vận hành thực tế của các giải thuật trên các kịch bản đã giải xong. | **55** (nếu 0 lỗi) | **220** (nếu 0 lỗi) |

---

## 3. Điều tra Mã nguồn và Phân tích Lỗi Trước Sửa

### Mã nguồn cũ tại `src/simulation/monte_carlo_engine_v2.py`:
```python
    def compute_rates(self) -> dict[str, dict[str, float | int]]:
        """Compute failure and feasibility rates with explicitly stated denominators."""
        summary = self.compute_summary()
        acc = summary["accounting"]
        n_req = acc["n_requested"]
        n_gen = acc["n_generated"]        # <-- SỐ REALIZATIONS (5 hoặc 20)
        n_eval = acc["n_evaluated"]

        return {
            "generation_failure_rate": {
                "numerator": acc["n_generation_failures"],
                "denominator": n_req,
                "rate": acc["n_generation_failures"] / n_req if n_req > 0 else 0.0,
            },
            "evaluation_failure_rate": {
                "numerator": acc["n_evaluation_failures"],
                "denominator": n_gen,     # <-- LỖI: Dùng n_gen (5) thay vì n_expected (55)!
                "rate": acc["n_evaluation_failures"] / n_gen if n_gen > 0 else 0.0,
            },
            "composite_feasible_rate": {
                "numerator": acc["n_feasible"],
                "denominator": n_eval,
                "rate": acc["n_feasible"] / n_eval if n_eval > 0 else 0.0,
            },
        }
```

**Hậu quả toán học nếu có lỗi solver:**  
Nếu có 1 evaluation slot bị crash trong đợt chạy N=5:
- Mẫu số cũ ghi nhận: $\text{Rate} = 1 / 5 = 20.0\%$.
- Mẫu số đúng phải là: $\text{Rate} = 1 / 55 = 1.818\%$.  
Cách tính cũ đã thổi phồng tỷ lệ lỗi của hệ thống lên gấp 11 lần, làm sai lệch nghiêm trọng phân tích độ tin cậy khoa học của bài toán.

---

## 4. Quá trình Kiểm chuẩn TDD: Failing Test Trước, PASS Sau

### Bước 1: Thiết lập Ca Kiểm thử Đối kháng Tiêm Lỗi (`LEDGER-21`)
Tại `tests/test_mc500_ledger_runner_integration.py`:
```python
def test_ledger_21_rate_denominators_with_injected_evaluation_failure():
    """LEDGER-21: Rate denominators with 5 realizations, 55 expected evaluations, and 1 evaluation failure."""
    ledger = SimulationExecutionLedger(
        run_id="TEST_21",
        requested_n=5,
        required_evaluations=CANONICAL_PROTOCOL_EVALUATIONS,
    )
    for i in range(5):
        s_id = f"SCEN_{i:02d}"
        ledger.record_scenario_generated(
            scenario_id=s_id,
            scenario_index=i,
            seed=202601 + i,
            realization_hash=f"hash_{i}",
        )
        for mode, solver in CANONICAL_PROTOCOL_EVALUATIONS:
            if i == 0 and mode == "MODE_B2" and solver == "Hybrid":
                ledger.record_evaluation_failure(
                    scenario_id=s_id,
                    reason="Injected solver failure",
                    realization_hash=f"hash_{i}",
                    initial_plan_solver=solver,
                    recourse_mode=mode,
                    exception_type="RuntimeError",
                )
            else:
                ledger.record_evaluation_success(
                    scenario_id=s_id,
                    realization_hash=f"hash_{i}",
                    initial_plan_solver=solver,
                    recourse_mode=mode,
                    solver_status="OPTIMAL",
                    composite_feasible=True,
                    objective_value=100.0 + i,
                    runtime_ms=1.5,
                )

    summary = ledger.compute_summary()
    acc = summary["accounting"]
    assert acc["n_requested_realizations"] == 5
    assert acc["n_generated_realizations"] == 5
    assert acc["n_expected_evaluations"] == 55
    assert acc["n_completed_evaluations"] == 54
    assert acc["n_evaluation_failures"] == 1

    rates = ledger.compute_rates()
    # evaluation_failure_rate: denominator = expected evaluation slots (55, NOT 5!)
    assert rates["evaluation_failure_rate"]["numerator"] == 1
    assert rates["evaluation_failure_rate"]["denominator"] == 55
    assert rates["evaluation_failure_rate"]["rate"] == pytest.approx(1 / 55)
```

### Bước 2: Bằng chứng Kiểm thử FAIL Trước Sửa
Thực thi lệnh pytest trên mã nguồn ban đầu:
```text
.venv\Scripts\python -m pytest tests/test_mc500_ledger_runner_integration.py -k test_ledger_21
...
>       assert rates["evaluation_failure_rate"]["denominator"] == 55
E       assert 5 == 55

tests\test_mc500_ledger_runner_integration.py:445: AssertionError
FAILED tests/test_mc500_ledger_runner_integration.py::test_ledger_21_rate_denominators_with_injected_evaluation_failure
====================== 1 failed in 1.47s =======================
```

### Bước 3: Áp dụng Bản vá Tối thiểu (Minimal Code Fix)
Tại `src/simulation/monte_carlo_engine_v2.py`:
```python
<<<<
        n_gen = acc["n_generated"]
        n_eval = acc["n_evaluated"]

        return {
            ...
            "evaluation_failure_rate": {
                "numerator": acc["n_evaluation_failures"],
                "denominator": n_gen,
                "rate": acc["n_evaluation_failures"] / n_gen if n_gen > 0 else 0.0,
            },
====
        n_expected = acc["n_expected_evaluations"]
        n_eval = acc["n_evaluated"]

        return {
            ...
            "evaluation_failure_rate": {
                "numerator": acc["n_evaluation_failures"],
                "denominator": n_expected,
                "rate": acc["n_evaluation_failures"] / n_expected if n_expected > 0 else 0.0,
            },
>>>>
```

### Bước 4: Bằng chứng Kiểm thử PASS Sau Sửa
```text
.venv\Scripts\python -m pytest tests/test_mc500_ledger_runner_integration.py -k test_ledger_21
collected 22 items / 21 deselected / 1 selected

tests\test_mc500_ledger_runner_integration.py .                          [100%]
====================== 1 passed, 21 deselected in 1.33s =======================
```
Sau đó kiểm tra hồi quy toàn bộ:
- `tests/test_mc500_ledger_runner_integration.py`: **22/22 PASS (9.79s)**
- Bộ 7 hồi quy contract suites (`test_g12b_r1`, `test_g12b_closure`, `test_g5`,...): **146/146 PASS (20.75s)**
- Tổng cộng: **168/168 PASS (100%)**.

---

## 5. Xác minh Trực tiếp trên Artifacts Pilot Tái thực thi

Sau khi tái chạy hai đợt pilot với bản vá:

### Pilot N=5 (`artifacts/remediation/monte_carlo_mc500/pilot_n5_run1/execution_ledger_summary.json`):
```json
{
  "rates": {
    "generation_failure_rate": {
      "numerator": 0,
      "denominator": 5,
      "rate": 0.0
    },
    "evaluation_failure_rate": {
      "numerator": 0,
      "denominator": 55,
      "rate": 0.0
    },
    "composite_feasible_rate": {
      "numerator": 40,
      "denominator": 55,
      "rate": 0.7272727272727273
    }
  }
}
```

### Pilot N=20 (`artifacts/remediation/monte_carlo_mc500/pilot_n20/execution_ledger_summary.json`):
```json
{
  "rates": {
    "generation_failure_rate": {
      "numerator": 0,
      "denominator": 20,
      "rate": 0.0
    },
    "evaluation_failure_rate": {
      "numerator": 0,
      "denominator": 220,
      "rate": 0.0
    },
    "composite_feasible_rate": {
      "numerator": 166,
      "denominator": 220,
      "rate": 0.7545454545454545
    }
  }
}
```

Mẫu số đánh giá lỗi đã được khép chuẩn hoàn toàn: **55 tại N=5** và **220 tại N=20**.
