# AEOLUS-MC500-P1: SCIENTIFIC ERRATA & AUDIT RECONCILIATION

**Date:** 2026-10-12  
**Auditor:** Principal Scientific Software Engineer, Monte Carlo Reproducibility Engineer  
**Sprint:** AEOLUS-MC500-P1  
**Status:** **FULLY RECONCILED & DOCUMENTED**

---

## 1. Executive Summary

Trong đợt kiểm toán tiền khởi chạy `AEOLUS-MC500-PREFLIGHT`, một số sai lệch giữa văn bản tường thuật (narrative report) và bằng chứng tệp thô (raw evidence artifacts) đã được phát hiện. Nhằm đảm bảo tính trung thực khoa học tuyệt đối (academic integrity) và khả năng bảo vệ kết luận khi bảo vệ khóa luận, tài liệu này công khai và giải quyết toàn bộ 9 sai lệch kỹ thuật.

---

## 2. Itemized Errata & Technical Reconciliation Matrix

| STT | Vấn đề / Sai lệch Phát hiện | Trạng thái trong Báo cáo Cũ (Preflight Narrative) | Thực tế trong Raw Artifacts / Code | Biện pháp Khắc phục Triệt để trong MC500-P1 |
|:---:|---|---|---|---|
| **1** | **Quy mô Kịch bản Thử nghiệm (Scenario Scale)** | Ghi là 40 chuyến bay, 10 cổng đỗ (`40 flights, 10 gates`). | Kịch bản thực tế trong `scripts/dry_run_mc500_preflight.py` là **120 chuyến bay, 25 cổng tiếp xúc, 5 bãi đỗ xa** (`SCEN_P09_CANONICAL_120`). | Chuẩn hóa toàn bộ báo cáo và script về đúng quy mô 120 flights chuẩn của khóa luận. |
| **2** | **Random Seed cơ sở** | Ghi seed là `42..46`. | Script thực tế sử dụng seed chuẩn **`202601`**. | Chuẩn hóa toàn bộ runner và test về seed `202601`. |
| **3** | **Mode B2 Mean Objective** | Báo cáo cũ ghi các con số phân tán khác nhau. | File thô `dry_run_ledger_entries.csv` ghi nhận trung bình Mode B2 là chính xác **133.32**. | Tính toán trực tiếp số liệu từ CSV bằng Python script, không gõ tay. Xác nhận lại tại Pilot N=5: mean = **133.32**. |
| **4** | **Thời gian thực thi Mode B2** | Ghi là 3.26 giây. | Log thực tế `RAW_EXECUTION_LOG.txt` ghi tổng thời gian giải của 15 evaluations Mode B2 là **115.77 ms**. | Phân biệt rõ thời gian giải của thuật toán (`solve_time`) và thời gian thực thi end-to-end (`wall-clock`). |
| **5** | **Thời gian Mode C1 + C2** | Ghi là 0.13 giây. | Log thực tế ghi nhận CP-SAT Oracle Mode C2 chiếm **2,298.30 ms** (tổng C1+C2 $\approx$ **2,300.10 ms**). | Ghi nhận chính xác chi phí giải của CP-SAT Oracle (~450 ms/kịch bản). |
| **6** | **Ngộ nhận Realization vs Evaluation** | Ghi 5 realizations $\times$ 3 solvers = "15 generated scenarios" trong ledger summary cũ. | Vi phạm nguyên tắc: stochastic realization chỉ được sinh 1 lần. | Tách bạch `ScenarioGenerationRecord` ($N=5$) và `ExecutionLedgerEntry` (55 evaluations). |
| **7** | **Thư mục Xuất cố định có nguy cơ ghi đè** | `scripts/run_g2_monte_carlo_remediation.py` có `OUTPUT_DIR = Path("artifacts/remediation/monte_carlo_remediated")` tại module-level. | Nguy cơ ghi đè kết quả G2 lịch sử khi import runner. | Thay thế bằng thư mục cô lập theo từng phiên chạy: `artifacts/remediation/monte_carlo_mc500/<run_id>/`. |
| **8** | **CLI Positional Argument Crash** | Runner cũ dùng `sys.argv[1]` chuyển đổi sang `int()`. | Khi truyền flag `--n-scenarios 5`, script crash với `ValueError`. | Nâng cấp lên `argparse` hỗ trợ `--n-scenarios`, `--seed`, `--output-dir`, `--dry-run`. |
| **9** | **Tham chiếu API không tồn tại trong bản vá cũ** | Dự thảo bản vá trước gọi `log_evaluation()`, `log_failure()`, `compute_file_sha256()`. | Các hàm này chưa từng được định nghĩa trong `monte_carlo_engine_v2.py`. | Định nghĩa chính thức và hỗ trợ đầy đủ các hàm này trong mã nguồn hiện hành. |

---

## 3. Academic Integrity Confirmation

Mọi số liệu trong báo cáo `06_PILOT_N5_RESULTS.md` và `07_PILOT_N20_RESULTS.md` đều được kết xuất trực tiếp từ các tệp dữ liệu thô (`execution_ledger_entries.csv`, `simulation_manifest.json`), không sử dụng số liệu ước tính hoặc số liệu sao chép thủ công.
