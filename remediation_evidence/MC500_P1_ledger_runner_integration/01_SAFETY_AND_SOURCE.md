# AEOLUS-MC500-P1: SAFETY BASELINE & SOURCE INTEGRITY AUDIT

**Date:** 2026-10-12  
**Auditor:** Principal Scientific Software Engineer, Monte Carlo Reproducibility Engineer  
**Sprint:** AEOLUS-MC500-P1  
**Status:** **PASSED / BASELINE FROZEN & VERIFIED**

---

## 1. Executive Summary

Giai đoạn **AEOLUS-MC500-P1** thực hiện giải quyết triệt để các phát hiện (findings) từ đợt kiểm toán tiền khởi chạy `AEOLUS-MC500-PREFLIGHT`, đưa hệ thống từ trạng thái **BLOCKED** chuyển sang trạng thái sẵn sàng nghiệm thu khoa học **MC500_READY**.

Tài liệu này xác lập đường cơ sở mã nguồn (authoritative source baseline), kiểm chứng tính toàn vẹn của backup an toàn và chứng minh tuân thủ 100% các quy tắc an toàn tuyệt đối (Absolute Safety Rules).

---

## 2. Source Baseline & Git Identity

- **Active Branch:** `remediation/g7-regression`
- **HEAD Commit:** `c95caef53808a561b1a7d3a5a09399cc52f754f5`
- **Python Environment:** Python 3.11.15 (`.venv\Scripts\python.exe`), Pytest 9.1.1
- **Platform:** Windows 11 (win32)

### Danh mục các tệp mã nguồn trọng tâm:
| Đường dẫn tệp | SHA-256 Checksum (Working Tree) | Trạng thái Git | Vai trò trong hệ thống |
|---|---|:---:|---|
| `src/simulation/monte_carlo_engine_v2.py` | `6ab89d34346743c7b3967d022a10df7ddba3a79f1dbfb445f14e5ad0808aee0c` | Modified | Core Simulation Engine, `SimulationExecutionLedger`, `ScenarioGenerationRecord` |
| `scripts/run_g2_monte_carlo_remediation.py` | `0d8c01d41c10706692bbdaecf53995f573c5cf0f19504a5bf4955f1ff9791485` | Modified | Production Monte Carlo Runner với CLI và Ledger |
| `tests/test_mc500_ledger_runner_integration.py` | `48419ba282fa2f96cf157d079979b9087c24f60faae13554035aa32a26c483d9` | Modified | 21 Adversarial Regression Tests (LEDGER-01 đến LEDGER-20) |
| `tests/test_g12b_r1_contract_integrity.py` | `44bf48bbf6d14cca1b41efe86a7fe2b4c3382047b8d8acc9b999f5d57d879c70` | Unmodified | 31 Unit Tests kiểm chứng hợp đồng R1 |
| `src/optimization/solvers/hybrid_solver.py` | `7dbe88c94640145c568bde52b3cbefe837e53ac9675b4fb1975ad8bf8c44d94a` | Unmodified | Hybrid CP-SAT + SA Solver |
| `src/optimization/sa/annealer.py` | `e6b49165fb2e6aeb760743d480653acbcd5eb5150b6986794e6a9334f9d341e8` | Unmodified | Simulated Annealing Engine với wall-clock deadline |

---

## 3. Pre-Modification Safety Backup & Restore Verification

Trước khi tiến hành sửa đổi mã nguồn, một bản sao lưu an toàn kèm manifest SHA-256 đã được thiết lập tại:  
`remediation_evidence/MC500_P1_ledger_runner_integration/safety_backup/`

### Bảng đối chiếu bản sao lưu an toàn (`SAFETY_MANIFEST.json`):
```json
{
  "created_at": "2026-10-12T19:35:00+07:00",
  "git_head": "c95caef53808a561b1a7d3a5a09399cc52f754f5",
  "files": {
    "src/simulation/monte_carlo_engine_v2.py": {
      "sha256": "17d367712fabd42e0811097015140c0565eab255f2aaa03a8646ded440fa0ad2",
      "backup_name": "monte_carlo_engine_v2.py"
    },
    "scripts/run_g2_monte_carlo_remediation.py": {
      "sha256": "12341f4921b1834927cb7801df072049a4e036e476fe3ea833a694931a293673",
      "backup_name": "run_g2_monte_carlo_remediation.py"
    },
    "tests/test_mc500_ledger_runner_integration.py": {
      "sha256": "0ef924c328798373d182eea9709861adcedef295e308d462af4e15795cbd7eb7",
      "backup_name": "test_mc500_ledger_runner_integration.py"
    }
  }
}
```

### Kiểm chứng phục hồi độc lập (Restore Check):
Quá trình restore thử nghiệm được thực thi tự động trên thư mục tạm `tempfile.TemporaryDirectory()`. Toàn bộ mã băm SHA-256 sau khi khôi phục trùng khớp 100% với file gốc trước khi sửa đổi (`Exit Code: 0`).

---

## 4. Absolute Safety Rules Compliance Verification

| Quy tắc An toàn Tuyệt đối | Trạng thái Tuân thủ | Cơ chế Giám sát & Bằng chứng |
|---|:---:|---|
| **Không sửa raw datasets & ML checkpoints** | **TUÂN THỦ 100%** | Không có tệp dữ liệu raw (`data/`) hay checkpoint (`checkpoints/`) nào bị chỉnh sửa. |
| **Không ghi đè frozen artifacts (G0–G12B-R1)** | **TUÂN THỦ 100%** | Toàn bộ các thư mục `artifacts/remediation/monte_carlo/`, `artifacts/remediation/monte_carlo_remediated/` được bảo tồn nguyên vẹn. Thư mục xuất mới được cách ly tại `artifacts/remediation/monte_carlo_mc500/`. |
| **Không thay đổi objective weights** | **TUÂN THỦ 100%** | Trọng số hàm mục tiêu giữ nguyên định nghĩa chuẩn của khóa luận. |
| **Không tự commit, push, rebase, clean** | **TUÂN THỦ 100%** | Git tree giữ nguyên trạng thái không commit. Zero Git clean/reset. |
| **Không chạy thí nghiệm N=500** | **TUÂN THỦ 100%** | Chỉ thực hiện các thử nghiệm có kiểm soát: $N=5$ (Dry-run & Replay) và $N=20$ (Pilot). |
| **Không che giấu exceptions hoặc silent-drop** | **TUÂN THỦ 100%** | Mọi ngoại lệ đều được ghi vào ledger dưới trạng thái `FAILURE`, đồng thời kích hoạt manifest `FAILED` thay vì `COMPLETE`. |
