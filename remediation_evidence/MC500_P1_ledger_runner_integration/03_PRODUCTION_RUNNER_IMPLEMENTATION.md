# AEOLUS-MC500-P1: PRODUCTION RUNNER IMPLEMENTATION AUDIT

**Date:** 2026-10-12  
**Auditor:** Principal Scientific Software Engineer, Monte Carlo Reproducibility Engineer  
**Script:** `scripts/run_g2_monte_carlo_remediation.py`  
**Status:** **FULLY INTEGRATED & VERIFIED**

---

## 1. Executive Summary

Production Runner `scripts/run_g2_monte_carlo_remediation.py` đã được nâng cấp toàn diện để tích hợp trực tiếp `SimulationExecutionLedger`. Bản nâng cấp giải quyết triệt để các rủi ro đã được phát hiện trong đợt preflight:
1. Loại bỏ đường dẫn cố định `artifacts/remediation/monte_carlo_remediated/` ở cấp độ module, thay thế bằng thư mục cô lập `artifacts/remediation/monte_carlo_mc500/<run_id>/`.
2. Thay thế CLI đối số vị trí (positional argument) bằng `argparse` hỗ trợ `--n-scenarios`, `--seed`, `--output-dir`, `--dry-run` và tương thích ngược với đối số vị trí.
3. Tích hợp đầy đủ việc hạch toán 11 evaluation slots trên 5 chế độ mô phỏng.
4. Bắt và hạch toán mọi ngoại lệ; nếu xảy ra gián đoạn, kết xuất `execution_ledger_entries_partial.csv` và phát hành manifest `FAILED`.

---

## 2. Key Architectural Enhancements

### 2.1. Isolated Run-Directory & Provenance Fingerprinting
Mỗi phiên chạy sinh ra một `run_id` duy nhất dạng `mc500_YYYYMMDD_HHMMSS_<hex>`.
Mã nguồn engine và cấu hình giải thuật được băm SHA-256 tự động trước khi bắt đầu:
```python
source_hash = compute_file_sha256("src/simulation/monte_carlo_engine_v2.py")
config_dict = {
    "n_flights": N_FLIGHTS,
    "n_contact_gates": N_CONTACT_GATES,
    "n_remote_stands": N_REMOTE_STANDS,
    "finite_remote_capacity": config.finite_remote_capacity,
    "enforce_remote_capacity": config.enforce_remote_capacity,
    "allow_unbounded_overflow": config.allow_unbounded_overflow,
    "time_limit_seconds": config.time_limit_seconds,
    "random_seed": config.random_seed,
    "copula_rho": 0.45,
    "base_seed": seed,
}
config_hash = hashlib.sha256(json.dumps(config_dict, sort_keys=True).encode("utf-8")).hexdigest()
```

### 2.2. Robust CLI Argument Parsing
```python
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aeolus Remediated Monte Carlo Pipeline (G2/MC500 Production Runner)"
    )
    parser.add_argument("--n-scenarios", "-n", type=int, default=100)
    parser.add_argument("--seed", "-s", type=int, default=202601)
    parser.add_argument("--output-dir", "-o", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("positional_n", nargs="?", type=int, default=None)
    return parser.parse_args()
```

### 2.3. End-to-End Evaluation & Ledger Event Logging
Mỗi lần gọi giải thuật trong 5 chế độ đều được bao bọc bởi khối `try...except` với đo đạc thời gian phân giải (`solve_time_sec`) và thời gian thực thi (`runtime_ms`):

```python
# Ví dụ luồng Mode B2 Rolling Online Recourse:
for s in scenarios:
    for solver_name, init_res in initial_solvers:
        t0 = time.perf_counter()
        try:
            r_b2 = evaluate_mode_b2_rolling_online_recourse(...)
            dt_ms = (time.perf_counter() - t0) * 1000.0
            ledger.record_evaluation_success(
                scenario_id=s.scenario_id,
                realization_hash=s.realization_hash,
                initial_plan_solver=solver_name,
                recourse_mode="MODE_B2",
                solver_status=r_b2.solver_status,
                composite_feasible=r_b2.feasibility.composite_feasible,
                objective_value=r_b2.objective_value,
                runtime_ms=dt_ms,
            )
        except Exception as exc:
            dt_ms = (time.perf_counter() - t0) * 1000.0
            ledger.record_evaluation_failure(
                scenario_id=s.scenario_id,
                reason=str(exc),
                realization_hash=s.realization_hash,
                initial_plan_solver=solver_name,
                recourse_mode="MODE_B2",
                exception_type=type(exc).__name__,
                runtime_ms=dt_ms,
            )
            raise
```

---

## 3. Strict Pre-Finalization Verification Gates

Trước khi xuất manifest `COMPLETE`, runner bắt buộc thực thi 2 cổng kiểm tra:
1. `ledger.validate_ledger(required_evaluations=CANONICAL_PROTOCOL_EVALUATIONS)`
2. `ledger.validate_paired_crn(required_solvers=["Greedy", "CPSat", "Hybrid"], required_modes=["MODE_A", "MODE_B1", "MODE_B2"])`

Nếu có bất kỳ kịch bản nào bị thiếu slot đánh giá hoặc lệch mã băm, quá trình chạy sẽ dừng ngay lập tức và raise `ValueError`.

---

## 4. Interruption & Failure Handling Protocol

Nếu xảy ra sự cố bất ngờ trong quá trình thực thi:
1. Khối `except Exception as pipeline_err` được kích hoạt.
2. Ledger hiện tại lập tức được xuất ra file:
   `execution_ledger_entries_partial.csv`
3. Một manifest báo lỗi được xuất:
   `simulation_manifest_failed.json` (chứa `status: "FAILED"`, `error_message`, `run_id`).
4. **Tuyệt đối không phát hành `simulation_manifest.json` với trạng thái `COMPLETE` khi run chưa đạt 100% nghiệm thu.**
