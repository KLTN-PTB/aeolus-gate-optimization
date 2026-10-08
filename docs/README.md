# Aeolus V4 — Master Documentation Index & Navigation Map

**Current Certified Status**: `CERTIFIED_WITH_LIMITATIONS` (Phase P14 Final Certification, `REBUILD_REQUIRED = NO`)  
**Total Documentation Artifacts**: 92 markdown files across specialized directories and root forensic package  
**Authoritative Reading Priority**: P14 Scientific Certification Package $\gg$ P11-R Post-Holdout Report $\gg$ P12-R1 Test Reconciliation $\gg$ P13 Reproducibility Audit $\gg$ V5 Forensic Certification (R37) $\gg$ System State Registry (v4.0.0) $\gg$ Historical Artifacts  

---

## 1. Documentation Supercedence Matrix (Thứ bậc hiệu lực tài liệu)

Để đảm bảo người đọc và hội đồng nghiệm thu không bị nhầm lẫn giữa các thế hệ văn bản và báo cáo kiểm toán, bảng ma trận dưới đây phân định rõ trạng thái hiệu lực của các tài liệu:

| Lĩnh vực | Tài liệu Hiện hành (AUTHORITATIVE / HIGHEST PRECEDENCE) | Tài liệu Lịch sử Đã thay thế (SUPERSEDED / HISTORICAL) | Diễn giải thay đổi pháp y |
| :--- | :--- | :--- | :--- |
| **Chứng nhận Khoa học Tối hậu** | [`../FINAL_SCIENTIFIC_CERTIFICATION_REPORT.md`](../FINAL_SCIENTIFIC_CERTIFICATION_REPORT.md) (Phase P14) | [`audit/FINAL_EVIDENCE_CERTIFICATION_V5.md`](audit/FINAL_EVIDENCE_CERTIFICATION_V5.md) (R37)<br>`FINAL_EVIDENCE_CERTIFICATION_V4.md` (R31) | P14 là văn bản chứng nhận khoa học cao nhất, thẩm định 13 claims, xác nhận `REBUILD_REQUIRED = NO` và kết luận `CERTIFIED_WITH_LIMITATIONS`. |
| **Tái đánh giá Hậu đóng băng 2024** | [`../P11R_FINAL_REPORT.md`](../P11R_FINAL_REPORT.md) (Phase P11-R) | `run_post_holdout_evaluation_v2.py` (R23/R37) | P11-R là kết quả đánh giá 2024 duy nhất sau khi sửa chữa phương pháp luận (P4 Student-T CRPS 18.33 min, NLL 4.62, MAE 21.97 min, $\nu=2.52$). |
| **Hợp nhất Test Suite** | [`../FINAL_TEST_SCOPE_RECONCILIATION.md`](../FINAL_TEST_SCOPE_RECONCILIATION.md) (Phase P12-R1) | `audit/FINAL_EVIDENCE_RECONCILIATION_V2.md` (R36)<br>`audit/R30_...md` | Xác lập 1.216 bài test active (100% pass), 75 certification gate tests, và cách ly an toàn 4 legacy freeze guards trong `pytest.ini`. |
| **Kiểm toán Khả năng Tái lập** | [`../SCOPED_REPRODUCIBILITY_AUDIT.md`](../SCOPED_REPRODUCIBILITY_AUDIT.md) (Phase P13) | `audit/R35_SOLVER_REPRODUCIBILITY_AUDIT.md` (R35) | Phán quyết `PASS_WITH_RESERVATION`, phân loại chính thức là `CONTAINED_SPECIFICATION_REPRODUCIBILITY` trên môi trường Python 3.11.15 Win AMD64. |
| **Chuẩn hóa Bằng chứng Luận văn** | [`../THESIS_EVIDENCE_NORMALIZATION_REPORT.md`](../THESIS_EVIDENCE_NORMALIZATION_REPORT.md) (Phase P15) | Toàn bộ tài liệu luận văn tiền chuẩn hóa | Đồng bộ hóa toàn diện tài liệu với phán quyết P14 mà không sửa đổi bất kỳ mã nguồn khoa học hay tệp dữ liệu nào. |
| **Trạng thái Hệ thống** | [`CURRENT_STATE.md`](CURRENT_STATE.md) (v4.0.0) | `CURRENT_STATE.md` (v3.0.0, R37) | Phiên bản 4.0.0 phản ánh đầy đủ dual 2024 reporting, P4 Role C, P5 Role B, và 1.216 bài test active. |
| **Kiểm toán Số liệu P4** | [`audit/R33_P4_METRIC_LINEAGE.md`](audit/R33_P4_METRIC_LINEAGE.md) | Đoạn số liệu $17.15/4.032$ trong `audit/R32_...md` | Xác định $17.6532/4.6307$ là số liệu holdout lịch sử thật; loại bỏ lỗi chép nhầm $17.15/4.032$ trong văn bản R32. |
| **Toán học Mô hình P5** | [`audit/R34_P5_MATHEMATICAL_AUDIT.md`](audit/R34_P5_MATHEMATICAL_AUDIT.md) | Ghi chú "5 quantiles" trong script R28 | Xác nhận P5 là mô hình 9 phân vị chính thức; chỉ số $16.77$ min là `CRPS_QUANTILE_APPROXIMATION` (pinball loss là $6.82$ min). |
| **Công bằng Solver** | [`audit/R35_SOLVER_REPRODUCIBILITY_AUDIT.md`](audit/R35_SOLVER_REPRODUCIBILITY_AUDIT.md) | Các mô tả cũ về "equal compute" | Khóa ngữ nghĩa `EQUAL_WALL_CLOCK_BUDGET` (trần 2.0s); từ chối đồng nhất wall-clock với equal computational work. |
| **Tổng quan Dự án** | [`../PROJECT_SUMMARY.md`](../PROJECT_SUMMARY.md) (Tháng 10/2026) | Bản tóm tắt R37 (03/10/2026) | Cập nhật đầy đủ tiến trình P10–P15, P11-R results, và phán quyết tối hậu P14. |

---

## 2. Danh mục Chỉ dẫn Tài liệu theo Nhóm Chức năng

```text
Aeolus/
├── [MỤC 0] BỘ BÁO CÁO CHỨNG NHẬN KHOA HỌC TỐI HẬU P10–P15 (Root Directory)
├── docs/
│   ├── [MỤC 1] BÁO CÁO PHÁP Y & CHỨNG NHẬN CHÍNH THỨC (docs/audit/)
│   ├── [MỤC 2] BÁO CÁO TỔNG KẾT TIẾN TRÌNH DỰ ÁN BẰNG TIẾNG VIỆT
│   ├── [MỤC 3] KIẾN TRÚC HỆ THỐNG & QUYẾT ĐỊNH THIẾT KẾ (ADRs)
│   ├── [MỤC 4] KIỂM TOÁN DỮ LIỆU, THỜI TIẾT & CHUỖI TÀU BAY (docs/dataset_audit/)
│   └── [MỤC 5] LỊCH SỬ THỰC NGHIỆM & KẾ HOẠCH BẢO LƯU (docs/experiments/, roadmap/)
```

---

### MỤC 0: BỘ BÁO CÁO CHỨNG NHẬN KHOA HỌC TỐI HẬU P10–P15 (Root Directory)
*Bộ tài liệu tối hậu có hiệu lực pháp lý và học thuật cao nhất trong toàn bộ repository:*

1. 🏛️ **Chứng nhận Khoa học Tối hậu & Quyết định Xây lại (P14)**: [`../FINAL_SCIENTIFIC_CERTIFICATION_REPORT.md`](../FINAL_SCIENTIFIC_CERTIFICATION_REPORT.md)  
   *Xác lập `CERTIFIED_WITH_LIMITATIONS`, thẩm định 13 luận điểm khoa học, kết luận `REBUILD_REQUIRED = NO`.*
2. 🔄 **Báo cáo Tái đánh giá Hậu đóng băng 2024 sau Sửa chữa Phương pháp luận (P11-R)**: [`../P11R_FINAL_REPORT.md`](../P11R_FINAL_REPORT.md)  
   *Đánh giá độc lập 2024 sau khi đóng băng hệ thống: P4 Continuous CRPS 18.33 min, NLL 4.62, MAE 21.97 min, $\nu=2.52$; P4 native downstream 100% feasibility.*
3. ⚖️ **Biên bản Hợp nhất Phạm vi Kiểm thử & Chứng nhận Gate (P12-R1)**: [`../FINAL_TEST_SCOPE_RECONCILIATION.md`](../FINAL_TEST_SCOPE_RECONCILIATION.md)  
   *Hợp nhất 1.216 bài test active (100% pass), 75 certification gate tests, và cách ly 4 legacy freeze-guard tests an toàn.*
4. 🔬 **Kiểm toán Khả năng Tái lập Phạm vi Hẹp (P13)**: [`../SCOPED_REPRODUCIBILITY_AUDIT.md`](../SCOPED_REPRODUCIBILITY_AUDIT.md)  
   *Chứng nhận khả năng tái lập trong phạm vi xác định (`CONTAINED_SPECIFICATION_REPRODUCIBILITY`).*
5. 📝 **Báo cáo Chuẩn hóa Bằng chứng Luận văn (P15)**: [`../THESIS_EVIDENCE_NORMALIZATION_REPORT.md`](../THESIS_EVIDENCE_NORMALIZATION_REPORT.md)  
   *Biên bản chuẩn hóa toàn bộ hệ thống tài liệu đồng bộ với phán quyết P14 mà không sửa đổi mã nguồn khoa học.*

1. 🏛️ **Chứng nhận Pháp y Tối hậu V5**: [`audit/FINAL_EVIDENCE_CERTIFICATION_V5.md`](audit/FINAL_EVIDENCE_CERTIFICATION_V5.md)  
   *Văn bản chính thức xác lập trạng thái `CERTIFIED_WITH_LIMITATIONS`, khóa 8 ranh giới cấm, 5 sự thật được chứng nhận, và bảng kết quả Holdout 2024 & Downstream Solver.*
2. ⚖️ **Biên bản Hợp nhất Bằng chứng V2**: [`audit/FINAL_EVIDENCE_RECONCILIATION_V2.md`](audit/FINAL_EVIDENCE_RECONCILIATION_V2.md)  
   *Hợp nhất ma trận ranh giới cho toàn bộ 13 Claims khoa học và 13 Domains kỹ thuật; hạch toán 224 đơn vị thực nghiệm.*
3. 🔬 **Ba Mũi Kiểm toán Pháp y Chuyên sâu (R33 – R35)**:
   - **P4 Metric Lineage**: [`audit/R33_P4_METRIC_LINEAGE.md`](audit/R33_P4_METRIC_LINEAGE.md)  
     *Điều tra độ lệch số liệu P4, chứng minh xuất xứ của CRPS 17.6532 / NLL 4.6307 và loại bỏ lỗi gõ nhầm R32.*
   - **P5 Quantile & Math**: [`audit/R34_P5_MATHEMATICAL_AUDIT.md`](audit/R34_P5_MATHEMATICAL_AUDIT.md)  
     *Xác minh cấu hình 9 phân vị và phân loại toán học chỉ số 16.85 min là CRPS Quantile Approximation.*
   - **Solver & Environment**: [`audit/R35_SOLVER_REPRODUCIBILITY_AUDIT.md`](audit/R35_SOLVER_REPRODUCIBILITY_AUDIT.md)  
     *Kiểm toán công bằng solver (wall-clock 2.0s), tính tối ưu CP-SAT 28/28 bài toán, và môi trường chuẩn Python 3.11.15.*
4. 🕵️ **Kiểm toán Pháp y Độc lập (R32)**: [`audit/R32_INDEPENDENT_FORENSIC_VERIFICATION.md`](audit/R32_INDEPENDENT_FORENSIC_VERIFICATION.md)  
   *Biên bản rà soát độc lập toàn diện repository, nguồn gốc khởi phát các vấn đề được giải quyết tại R33–R35.*
5. 📜 **Chuỗi Kiểm toán Pháp y Tiền chứng nhận (R25 – R31)**:
   - Tóm tắt chuỗi R25-R31: [`audit/R25_R31_FORENSIC_SUMMARY.md`](audit/R25_R31_FORENSIC_SUMMARY.md)
   - R25 Point Selection Consistency: [`audit/R25_POINT_SELECTION_CONSISTENCY.md`](audit/R25_POINT_SELECTION_CONSISTENCY.md)
   - R26 Solver Equal Compute: [`audit/R26_SOLVER_EQUAL_COMPUTE.md`](audit/R26_SOLVER_EQUAL_COMPUTE.md)
   - R27 Test Hardening: [`audit/R27_CERTIFICATION_TEST_HARDENING.md`](audit/R27_CERTIFICATION_TEST_HARDENING.md)
   - R28 Probabilistic Audit: [`audit/R28_PROBABILISTIC_AUDIT.md`](audit/R28_PROBABILISTIC_AUDIT.md)
   - R29 Execution Provenance: [`audit/R29_EXECUTION_PROVENANCE.md`](audit/R29_EXECUTION_PROVENANCE.md)
   - R30 Reconciliation V1: [`audit/R30_FINAL_EVIDENCE_RECONCILIATION.md`](audit/R30_FINAL_EVIDENCE_RECONCILIATION.md)
   - R31 Forensic Certification V4: [`audit/FINAL_EVIDENCE_CERTIFICATION_V4.md`](audit/FINAL_EVIDENCE_CERTIFICATION_V4.md)
6. 🗄️ **Báo cáo Kiểm toán Lịch sử Giai đoạn Đầu (R10 – R20)**:
   - R13 / R10 Execution Audit: [`audit/R13_R10_EXECUTION_AUDIT.md`](audit/R13_R10_EXECUTION_AUDIT.md)
   - R17 Downstream Semantics: [`audit/R17_DOWNSTREAM_SEMANTICS_AUDIT.md`](audit/R17_DOWNSTREAM_SEMANTICS_AUDIT.md)
   - R19 Probabilistic Audit: [`audit/R19_PROBABILISTIC_AUDIT.md`](audit/R19_PROBABILISTIC_AUDIT.md)
   - R20 Freeze Audit: [`audit/R20_FREEZE_AUDIT.md`](audit/R20_FREEZE_AUDIT.md)

---

### MỤC 2: BÁO CÁO TỔNG KẾT TIẾN TRÌNH DỰ ÁN BẰNG TIẾNG VIỆT
*Các báo cáo tổng thuật được viết bằng tiếng Việt theo trình tự phát triển thực tế của đề tài:*

1. **Giai đoạn Khởi động & Tiền xử lý (Step 1 – Step 7)**:  
   [`BAO_CAO_TIEN_TRINH_VA_KET_QUA_STEP_1_DEN_STEP_7.md`](BAO_CAO_TIEN_TRINH_VA_KET_QUA_STEP_1_DEN_STEP_7.md)  
   *Báo cáo xử lý dữ liệu thô BTS 2016-2024, xây dựng phân hoạch thời gian, kiểm soát rò rỉ dữ liệu và thiết lập baseline.*
2. **Giai đoạn Chuỗi Nhiệm vụ R0 đến R12**:  
   [`BAO_CAO_TONG_KET_CHUOI_NHIEM_VU_R0_DEN_R12.md`](BAO_CAO_TONG_KET_CHUOI_NHIEM_VU_R0_DEN_R12.md)  
   *Tổng hợp quá trình hoàn thiện các chặng thực nghiệm ban đầu và rà soát các hợp đồng dữ liệu.*
3. **Giai đoạn Mô hình Xác suất (Stage 0 đến Stage 11)**:  
   [`BAO_CAO_TONG_KET_PROBABILISTIC_CORE_ARRIVAL_STAGE_0_11.md`](BAO_CAO_TONG_KET_PROBABILISTIC_CORE_ARRIVAL_STAGE_0_11.md)  
   *Tổng kết 12 giai đoạn phát triển các mô hình xác suất P1-P5 và xây dựng khế ước phân phối.*
4. **Giai đoạn Tối ưu hóa Cổng Hạ nguồn (Phase E – H)**:  
   [`BAO_CAO_TONG_KET_PHASE_E_F_G_H_OPTIMIZATION.md`](BAO_CAO_TONG_KET_PHASE_E_F_G_H_OPTIMIZATION.md)  
   *Tổng kết thực nghiệm các bộ giải Greedy, CP-SAT, Simulated Annealing và đánh giá độ bền vững Monte Carlo.*
5. **Tổng kết Toàn diện Tiến trình Phase 0 đến Phase 11**:  
   [`TONG_KET_TIEN_TRINH_PHASE_0_DEN_PHASE_11.md`](TONG_KET_TIEN_TRINH_PHASE_0_DEN_PHASE_11.md)  
   *Bản tổng kết xuyên suốt toàn bộ các pha nghiên cứu trước khi bước vào giai đoạn kiểm toán pháp y R25-R37.*

---

### MỤC 3: KIẾN TRÚC HỆ THỐNG & QUYẾT ĐỊNH THIẾT KẾ (ADRs)

1. **Sổ đăng ký Trạng thái Hệ thống & Danh mục Mô hình (v3.0.0)**:  
   [`CURRENT_STATE.md`](CURRENT_STATE.md)  
   *Nguồn thông tin chính xác về các mô hình active, vai trò chức năng, trạng thái downstream admissibility và các bất biến kiến trúc.*
2. **Sổ đăng ký Quyết định Kiến trúc (Decision Registry)**:  
   [`decisions/decision_registry.md`](decisions/decision_registry.md)  
   *Lưu trữ toàn bộ các quyết định đã khóa từ D001 đến D030 (bao gồm phân tách vai trò mô hình D027, công bằng wall-clock D028, phạm vi tái lập D029, và phán quyết V5 D030).*
3. **Kiến trúc Dự báo Kép V4 (Dual Prediction Architecture)**:  
   [`decisions/decision_dual_prediction_architecture_v4.md`](decisions/decision_dual_prediction_architecture_v4.md)  
   *Nguyên tắc bức tường lửa cách ly giữa Core Arrival (Inbound ATL) và Auxiliary Departure (Outbound ATL).*
4. **Quyết định về Chuỗi Tàu bay**:  
   - [`decisions/decision_include_chain.md`](decisions/decision_include_chain.md) *(Khóa loại bỏ raw chain .pt)*
   - [`decisions/decision_reconstructed_chain.md`](decisions/decision_reconstructed_chain.md) *(Đánh giá ablation reconstructed chain)*

---

### MỤC 4: KIỂM TOÁN DỮ LIỆU, THỜI TIẾT & CHUỖI TÀU BAY (`docs/dataset_audit/`)

1. **Kiểm toán Rò rỉ Dữ liệu & Schema Chuẩn hóa**:
   - Schema dữ liệu 34 trường: [`dataset_audit/canonical_schema_v1.md`](dataset_audit/canonical_schema_v1.md)
   - Kiểm toán rò rỉ thông tin: [`dataset_audit/leakage_audit.md`](dataset_audit/leakage_audit.md)
   - Ma trận tương thích schema 2016-2024: [`dataset_audit/schema_compatibility_matrix.md`](dataset_audit/schema_compatibility_matrix.md)
   - Từ điển dữ liệu: [`dataset_audit/data_dictionary_v1.md`](dataset_audit/data_dictionary_v1.md)
2. **Kiểm toán Ranh giới Thời tiết (Weather Timing)**:
   - Kiểm toán thời điểm thông tin thời tiết: [`dataset_audit/weather_timing_audit.md`](dataset_audit/weather_timing_audit.md)
   - Khế ước kiểm toán thời tiết point-in-time W1-W15: [`dataset_audit/weather_point_in_time_contract_v1.md`](dataset_audit/weather_point_in_time_contract_v1.md)
   - Kế hoạch kiểm toán nguồn thời tiết bên ngoài: [`dataset_audit/point_in_time_weather_plan_v1.md`](dataset_audit/point_in_time_weather_plan_v1.md)
3. **Kiểm toán Tính khả thi Chuỗi Tàu bay (Flight Chain)**:
   - Báo cáo khả thi chuỗi tàu bay ban đầu: [`dataset_audit/flight_chain_feasibility_report.md`](dataset_audit/flight_chain_feasibility_report.md)
   - Báo cáo tái cấu trúc chuỗi lịch bay 2016-2023: [`dataset_audit/flight_chain_reconstruction_report.md`](dataset_audit/flight_chain_reconstruction_report.md)
   - Kiểm toán E006 loại bỏ chuỗi khỏi Core Arrival: [`dataset_audit/reconstructed_chain_feature_availability_audit_v1.md`](dataset_audit/reconstructed_chain_feature_availability_audit_v1.md)

---

### MỤC 5: LỊCH SỬ THỰC NGHIỆM & KẾ HOẠCH BẢO LƯU

1. **Lộ trình Phát triển 12 Tuần Ban đầu (Roadmap Archives)**:
   - Lộ trình V4 Đồng bộ: [`roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md`](roadmap/01_Roadmap_12_tuan_Aeolus_Gate_Optimization_V4_DONG_BO.md)
   - Bộ công nghệ V4: [`roadmap/02_Bo_cong_nghe_de_xuat_Aeolus_Gate_Optimization_V4_DONG_BO.md`](roadmap/02_Bo_cong_nghe_de_xuat_Aeolus_Gate_Optimization_V4_DONG_BO.md)
   - Chi tiết từng tuần V4: [`roadmap/03_Chi_tiet_tung_tuan_Roadmap_Aeolus_Gate_Optimization_V4_DONG_BO.md`](roadmap/03_Chi_tiet_tung_tuan_Roadmap_Aeolus_Gate_Optimization_V4_DONG_BO.md)
   - Bộ tài liệu lộ trình V3 bảo lưu: `docs/roadmap/*_V3_DONG_BO.md`
2. **Nhật ký Thực nghiệm Giai đoạn Giữa (Experiments & Notes)**:
   - Nhật ký thực nghiệm: [`experiments/experiment_log.md`](experiments/experiment_log.md)
   - Thực nghiệm Week 4 Core Arrival baselines: [`experiments/week4_core_arrival_baselines.md`](experiments/week4_core_arrival_baselines.md)
   - Thực nghiệm Week 5 XGBoost Optuna HPO: [`experiments/week5_core_arrival_xgboost_optuna.md`](experiments/week5_core_arrival_xgboost_optuna.md)
   - Ghi chú kỹ thuật Day 1 - Day 3: [`notes/day1_feature_gap_closure.md`](notes/day1_feature_gap_closure.md), [`notes/day3_metric_reconciliation.md`](notes/day3_metric_reconciliation.md)
3. **Ghi chú Luận văn & Giới hạn Phương pháp luận (Thesis Notes)**:
   - Các giả định học thuật: [`thesis_notes/assumptions.md`](thesis_notes/assumptions.md)
   - Các giới hạn nghiên cứu: [`thesis_notes/limitations.md`](thesis_notes/limitations.md)
   - Tổng hợp kết quả đã hoàn thành: [`thesis_notes/tong_hop_ket_qua_da_hoan_thanh.md`](thesis_notes/tong_hop_ket_qua_da_hoan_thanh.md)

---

## 3. Hướng dẫn Trích dẫn & Sử dụng Số liệu

Khi trích dẫn số liệu hoặc kết quả cho bài báo, slide báo cáo, hoặc luận văn tốt nghiệp, người thực hiện **BẮT BUỘC** phải tuân theo các quy tắc sau:

1. **Phân định rõ 2 thế hệ số liệu Holdout 2024**:
   - **Thế hệ Hậu sửa chữa phương pháp luận (`P11R_POST_HOLDOUT_REEVALUATION`)**: Phải trích dẫn từ [`../P11R_FINAL_REPORT.md`](../P11R_FINAL_REPORT.md) và [`../FINAL_SCIENTIFIC_CERTIFICATION_REPORT.md`](../FINAL_SCIENTIFIC_CERTIFICATION_REPORT.md):
     - P4 NGBoost Student-T (Role C): Continuous CRPS **$18.33$ min** (tính bằng công thức giải tích đóng Student-T của Jordan et al.), Continuous NLL **$4.62$**, Point MAE **$21.97$ min**, RMSE **$54.21$ min**, Brier ($Y \ge 15$) **$0.1544$**, bậc tự do trung bình $\nu = \mathbf{2.52} \in [2.10, 2.78]$.
     - Ridge Regression Baseline: Point MAE **$23.39$ min**.
     - P5 Quantile Regression: Giữ nguyên là Role B (forecast-only, không tái huấn luyện hay tái cấu trúc theo R39/P10-A).
   - **Thế hệ Lịch sử trước sửa chữa (`HISTORICAL_2024_RESULTS`)**: Trích dẫn từ [`audit/FINAL_EVIDENCE_CERTIFICATION_V5.md`](audit/FINAL_EVIDENCE_CERTIFICATION_V5.md) với chú thích rõ ràng là kết quả lịch sử (Ridge MAE $22.91$ min; P5 Approx CRPS $16.77$ min, Pinball $6.82$ min; P4 Continuous CRPS $17.65$ min, Continuous NLL $4.6307$).
2. **Tuyệt đối không khẳng định "Quán quân duy nhất"**: Trình bày kết quả theo các vai trò tách biệt (Point Baseline vs Role B Quantile Forecast vs Role C Continuous Simulation).
3. **Số liệu mô phỏng gán cổng hạ nguồn**: Trích dẫn kết quả từ bảng 28 kịch bản mùa (CP-SAT tối ưu 28/28 bài trong $0.44$s) và 16 kịch bản P11-R (P4 native draws đạt 100% khả thi dưới 500 cú sốc mùa hè). Nhấn mạnh toàn bộ mô phỏng được thực hiện trên kịch bản nghiên cứu tổng hợp; zero real-world ATL operations claimed.
4. **Mô tả công bằng thời gian thực**: Luôn nêu rõ các solver được so sánh dưới cùng trần thời gian thực ($T = 2.0$ giây), không suy diễn thành "công tính toán bằng nhau".
5. **Quy mô bộ kiểm thử**: Trích dẫn chính xác toàn bộ hệ thống gồm **1.216 bài test active (100% pass)** và **75 certification gate tests** theo [`../FINAL_TEST_SCOPE_RECONCILIATION.md`](../FINAL_TEST_SCOPE_RECONCILIATION.md) (4 bài test freeze-guard cũ đã được cách ly bảo lưu an toàn qua `pytest.ini`).
