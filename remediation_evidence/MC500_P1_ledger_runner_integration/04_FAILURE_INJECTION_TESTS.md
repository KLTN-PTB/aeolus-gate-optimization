# AEOLUS-MC500-P1: ADVERSARIAL FAILURE INJECTION & REGRESSION AUDIT

**Date:** 2026-10-12  
**Auditor:** Principal Scientific Software Engineer, Monte Carlo Reproducibility Engineer  
**Suite:** `tests/test_mc500_ledger_runner_integration.py` (21 Tests)  
**Status:** **21/21 PASS (100% SUCCESS in 10.04s)**

---

## 1. Executive Summary

Để đảm bảo hệ thống không chỉ hoạt động tốt trong điều kiện lý tưởng (happy path) mà còn có khả năng tự vệ vững chắc trước các lỗi tiềm ẩn (silent corruption, missing data, crashes, timeouts), bộ kiểm thử đối kháng `tests/test_mc500_ledger_runner_integration.py` đã được thiết kế với 21 kịch bản kiểm tra nghiêm ngặt (LEDGER-01 đến LEDGER-20 cùng test kiểm tra tích hợp runner thật).

---

## 2. Adversarial Test Matrix & Verification Results

| Mã Test | Mục tiêu & Kịch bản Đối kháng | Cơ chế Kiểm chứng (Assertion Logic) | Kết quả |
|---|---|---|:---:|
| **LEDGER-01** | Hạch toán chuẩn 5 realizations và 55 evaluations | $N_{\text{req}}=5, N_{\text{gen}}=5, N_{\text{eval}}=55$. Không nhầm $N=5$ với 55. | **PASS** |
| **LEDGER-02** | Ngoại suy chuẩn 500 realizations $\times$ 11 slots | Xác minh protocol 11 slots tính ra chính xác $5.500$ evaluation slots. | **PASS** |
| **LEDGER-03** | **Cố tình bỏ sót slot (Mode B2, Hybrid)** | `validate_ledger()` phát hiện ngay và raise `ValueError: Missing required evaluation slot (MODE_B2, Hybrid)`. | **PASS** |
| **LEDGER-04** | **Cố tình bỏ sót toàn bộ Mode C2** | `validate_ledger()` phát hiện thiếu toàn bộ Mode C2 và raise `ValueError`. | **PASS** |
| **LEDGER-05** | **CRN rỗng (Empty entries)** | `validate_paired_crn()` từ chối trả về PASS khi ledger có 0 bản ghi, raise `ValueError`. | **PASS** |
| **LEDGER-06** | **Trùng lặp cùng kịch bản, mode và solver** | Ledger chặn trùng lặp, raise `ValueError: Duplicate scenario_id`. | **PASS** |
| **LEDGER-07** | **Cùng kịch bản và solver trên các mode khác nhau** | Greedy chạy trên Mode A, B1, B2 được chấp nhận là 3 bản ghi độc lập hợp lệ. | **PASS** |
| **LEDGER-08** | **Lệch mã băm kịch bản (Mismatched realization hash)** | Phát hiện sai khác giữa hash khi sinh và hash khi đánh giá, raise `ValueError`. | **PASS** |
| **LEDGER-09** | **Bơm lỗi ngoại lệ sinh kịch bản (Generation crash)** | Ghi nhận đúng `n_generation_failures=1`, bảo toàn phương trình $N_{\text{req}}=N_{\text{gen}}+N_{\text{gen\_fail}}$. | **PASS** |
| **LEDGER-10** | **Bơm lỗi ngoại lệ đánh giá thuật toán (Evaluation crash)** | Ghi nhận `n_evaluation_failures=1`, lưu trữ `exception_type='RuntimeError'`. | **PASS** |
| **LEDGER-11** | **Bơm lỗi quá thời gian giải (Solver timeout)** | Ghi nhận `n_timeouts=1`, lưu trữ cờ `timeout=True` và status `TIMEOUT`. | **PASS** |
| **LEDGER-12** | **Phân biệt Feasible / Infeasible / Unknown** | Tách bạch giữa nghiệm khả thi (1), bất khả thi do hết chỗ đỗ (1), và không xác định (1). | **PASS** |
| **LEDGER-13** | **Bơm lỗi sập pipeline giữa chừng bằng monkeypatch** | Xác nhận `simulation_manifest.json` **KHÔNG được tạo**; tạo `simulation_manifest_failed.json` (FAILED). | **PASS** |
| **LEDGER-14** | **Thay đổi cấu hình/mã nguồn làm đổi mã băm** | Thay đổi seed hoặc tham số copula sinh ra fingerprint SHA-256 hoàn toàn mới. | **PASS** |
| **LEDGER-15** | **Không ghi đè thư mục lịch sử G2** | Kiểm chứng `DEFAULT_BASE_OUTPUT_DIR` chỉ trỏ tới `monte_carlo_mc500`, không chạm `monte_carlo_remediated`. | **PASS** |
| **LEDGER-16** | **Cách ly hoàn toàn giữa các Run ID** | Hai phiên chạy sinh ra hai thư mục con độc lập, không ghi đè dữ liệu của nhau. | **PASS** |
| **LEDGER-17** | **Tái lập tất định (Deterministic replay)** | Hai lần chạy cùng seed 202601 cho kết quả objective value và realization hash trùng khớp 100%. | **PASS** |
| **LEDGER-18** | **Kiểm tra tính nhất quán danh mục Mode và Solver** | Toàn bộ 11 slots khớp 100% với định nghĩa: A, B1, B2 (Greedy, CPSat, Hybrid), C1, C2. | **PASS** |
| **LEDGER-19** | **Kiểm tra mẫu số và tỷ lệ lỗi toán học** | Xác minh chính xác các mẫu số: $N_{\text{req}}$ cho generation failure, $N_{\text{gen}}$ cho eval failure, $N_{\text{eval}}$ cho feasible rate. | **PASS** |
| **LEDGER-20** | **Không nhiễm chéo trạng thái giữa các instance** | Hai đối tượng ledger độc lập không làm thay đổi trạng thái của nhau. | **PASS** |
| **RUNNER-INT** | **Xác nhận Production Runner đã tích hợp Ledger** | Xác minh source `scripts/run_g2_monte_carlo_remediation.py` trực tiếp gọi các hàm của ledger. | **PASS** |

---

## 3. Raw Execution Output Log
```text
============================= test session starts =============================
platform win32 -- Python 3.11.15, pytest-9.1.1, pluggy-1.6.0
rootdir: D:\Study\Code\Python\Aelous
collected 21 items

tests/test_mc500_ledger_runner_integration.py::test_ledger_01_five_scenarios_55_evaluations_five_generated PASSED [  4%]
tests/test_mc500_ledger_runner_integration.py::test_ledger_02_five_hundred_scenarios_expected_slots PASSED [  9%]
tests/test_mc500_ledger_runner_integration.py::test_ledger_03_missing_b2_hybrid_fails PASSED [ 14%]
tests/test_mc500_ledger_runner_integration.py::test_ledger_04_missing_entire_mode_c2_fails PASSED [ 19%]
tests/test_mc500_ledger_runner_integration.py::test_ledger_05_empty_crn_records_fail PASSED [ 23%]
tests/test_mc500_ledger_runner_integration.py::test_ledger_06_duplicate_scenario_mode_solver_fails PASSED [ 28%]
tests/test_mc500_ledger_runner_integration.py::test_ledger_07_same_scenario_solver_across_different_modes_allowed PASSED [ 33%]
tests/test_mc500_ledger_runner_integration.py::test_ledger_08_mismatched_realization_hashes_fail PASSED [ 38%]
tests/test_mc500_ledger_runner_integration.py::test_ledger_09_generation_exception_accounted PASSED [ 42%]
tests/test_mc500_ledger_runner_integration.py::test_ledger_10_evaluation_exception_accounted PASSED [ 47%]
tests/test_mc500_ledger_runner_integration.py::test_ledger_11_timeout_accounted PASSED [ 52%]
tests/test_mc500_ledger_runner_integration.py::test_ledger_12_feasible_infeasible_unknown_distinguished PASSED [ 57%]
tests/test_mc500_ledger_runner_integration.py::test_ledger_13_incomplete_run_does_not_create_complete_manifest PASSED [ 61%]
tests/test_mc500_ledger_runner_integration.py::test_ledger_14_config_source_hash_fingerprint_change PASSED [ 66%]
tests/test_mc500_ledger_runner_integration.py::test_ledger_15_legacy_g2_artifacts_not_overwritten PASSED [ 71%]
tests/test_mc500_ledger_runner_integration.py::test_ledger_16_run_id_output_isolation PASSED [ 76%]
tests/test_mc500_ledger_runner_integration.py::test_ledger_17_deterministic_replay PASSED [ 80%]
tests/test_mc500_ledger_runner_integration.py::test_ledger_18_all_mode_and_solver_identities_match_registry PASSED [ 85%]
tests/test_mc500_ledger_runner_integration.py::test_ledger_19_correct_count_denominators_and_rates PASSED [ 90%]
tests/test_mc500_ledger_runner_integration.py::test_ledger_20_multiple_runs_do_not_contaminate_each_other PASSED [ 95%]
tests/test_mc500_ledger_runner_integration.py::test_production_runner_has_active_ledger_integration PASSED [100%]

============================= 21 passed in 10.04s =============================
```
