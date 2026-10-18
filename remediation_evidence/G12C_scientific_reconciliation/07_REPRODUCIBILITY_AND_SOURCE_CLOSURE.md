# BÁO CÁO 07: ĐÓNG GÓI MÔI TRƯỜNG, MÃ NGUỒN VÀ KHẢ NĂNG TÁI LẬP
## AEOLUS-G12C — REPRODUCIBILITY & SOURCE DEPENDENCY CLOSURE

**Dự án:** Aeolus Gate Optimization  
**Giai đoạn:** G12C — Scientific Reconciliation, Historical Regression & Thesis Readiness  
**Phạm vi:** Kiểm toán môi trường thực thi, đóng gói phụ thuộc và xác lập tính tất định tái lập  

---

## 1. ĐỐI CHIẾU MÔI TRƯỜNG THỰC THI CHUẨN XÁC (RUNTIME ENVIRONMENT INVENTORY)

Môi trường thực thi được kiểm toán trực tiếp từ Python runtime:

| Thành phần Môi trường | Phiên bản Thực tế | Phiên bản Quy định trong Manifest | Trạng thái Đối chiếu |
|:---|:---:|:---:|:---:|
| **Hệ điều hành (OS)** | Windows 11 Professional (AMD64) | Windows 11 AMD64 | **MATCH** |
| **Python Runtime** | `3.11.15` (CPython 64-bit) | Python 3.11+ | **MATCH** |
| **Google OR-Tools** | `9.8.3296` | `9.8.3296` | **MATCH (Exact bitwise)** |
| **NumPy** | `1.26.4` | `1.26.4` | **MATCH (Exact bitwise)** |
| **SciPy** | `1.13.0` | `1.13.0` | **MATCH (Exact bitwise)** |
| **Pandas** | `2.2.2` | `2.2.2` | **MATCH (Exact bitwise)** |
| **Scikit-Learn** | `1.4.1.post1` | `1.4.1.post1` | **MATCH (Exact bitwise)** |
| **XGBoost** | `2.0.3` | `2.0.3` | **MATCH (Exact bitwise)** |
| **Pytest** | `9.1.1` | `9.1.1` | **MATCH (Exact bitwise)** |
| **Streamlit** | `1.32.2` | `1.32.2` | **MATCH (Exact bitwise)** |

---

## 2. TÍNH ĐÓNG KÍN VÀ TẤT ĐỊNH CỦA PHỤ THUỘC (DEPENDENCY CLOSURE)

1. **Cô lập Môi trường Ảo (Virtual Environment):**
   - Dự án vận hành độc lập bên trong `.venv/` tại `D:\Study\Code\Python\Aelous\.venv`.
   - Toàn bộ dependencies được khóa chặt trong môi trường ảo, không dựa vào bất kỳ thư viện toàn cục nào của hệ thống.
2. **Khả năng Thực thi Ngoại tuyến (Offline Execution):**
   - Pipeline tối ưu hóa và mô phỏng Monte Carlo vận hành $100\%$ cục bộ.
   - Không có bất kỳ lệnh gọi mạng (network call), tải dữ liệu động hay kết nối dịch vụ ngoài nào trong quá trình chạy thí nghiệm, đảm bảo tính bền vững và an toàn thông tin.
3. **Tính Tất định Thống kê (Deterministic Reproducibility):**
   - Hạt giống ngẫu nhiên được ấn định chặt chẽ: `seed = 202601`.
   - Chạy trên môi trường đơn tiến trình (single-worker process).
   - Với cùng cấu hình và seed, kết quả sinh $500$ kịch bản và $5,500$ lượt đánh giá là bất biến từng byte ($100\%$ bitwise deterministic).

---

## 3. DANH MỤC KHÓA BĂNG MÃ NGUỒN CỐT LÕI (FROZEN SOURCE INVENTORY)

Mã băm SHA-256 của các thành phần mã nguồn cốt lõi sau khi hoàn tất hiệu đính G12C:

| Tên File | Đường dẫn Tương đối | SHA-256 Checksum | Trạng Thái |
|:---|:---|:---|:---:|
| `run_g2_monte_carlo_remediation.py` | `scripts/run_g2_monte_carlo_remediation.py` | `c1ca2bdeb0d87d49e1cda52c407e1c5bf36012b5b0c710f4cd55405880a4a324` | **FROZEN / UNMODIFIED** |
| `monte_carlo_engine_v2.py` | `src/simulation/monte_carlo_engine_v2.py` | `49a78ecbac8313240c54713d7c30e11da9ce1b15243a959e6c314ee045208cf4` | **FROZEN / UNMODIFIED** |
| `scalability_scenario.py` | `src/simulation/scalability_scenario.py` | `4654a04adca65596e00fad0c4065a2bacb47f5b22f5d36ced6d5a3b8c55138c0` | **FROZEN / UNMODIFIED** |
| `downstream_comparison_v2.py` | `src/evaluation/downstream_comparison_v2.py` | `a258616b25f29a79b3922171c9ce670e3a0b87315471ae3ea0f77a4397d64da7` | **FROZEN / UNMODIFIED** |
| `domain.py` | `src/optimization/domain.py` | `7e2101388729ee48f1f4555c6ee859a0525b4a7a901c76e33c6b3adde78ea580` | **FROZEN / UNMODIFIED** |
| `config.py` | `src/optimization/config.py` | `7d0b06102cd900ef13c16d40c7728bca251b0f7027ef43ea452d936edc0b1669` | **FROZEN / UNMODIFIED** |
| `final_evaluation_guard_v2.py` | `src/evaluation/final_evaluation_guard_v2.py` | `10058b8f2d5930064eb651c6b6d3b499877e8a93e506692803b9b4f97129598d` | **AUDITED ADAPTER** |
| `test_model_registry.py` | `tests/benchmark/test_model_registry.py` | `1d30c4fa48da0c49a37a6bcae88eebe63b081dd002d259fae6aa0f39ec03ddc2` | **UPDATED ASSERTION** |
| `test_r27_certification_hardening.py` | `tests/test_r27_certification_hardening.py` | `61f185dd1f900e4b85c2c5108f9f60cb0d3c0fb8d3c126d4ca9d545089e525ae` | **UPDATED ASSERTION** |

> [!NOTE]
> Mã nguồn thực thi Monte Carlo (`run_g2_monte_carlo_remediation.py`, `monte_carlo_engine_v2.py`, `scalability_scenario.py`) được giữ nguyên $100\%$ không thay đổi, bảo đảm tính hợp lệ tuyệt đối của toàn bộ dữ liệu thí nghiệm chính thức N=500.
