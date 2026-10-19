# Trạng thái hiện hành sau đối soát

Mốc mã nguồn: aed54a1. Học thuật: READY_FOR_ADVISOR_REVIEW; chưa có xác nhận đổi phạm vi hoặc G13 mới.
Nhất quán nội bộ: PASS. Kết quả này không phải full regression hay chứng nhận vận hành sân bay.

## Luồng đang chạy

Raw Parquet → chuẩn hóa ngày sự kiện ATL → dự báo arrival/departure → ghép cặp suy diễn hoặc single-leg → dựng khoảng chiếm dụng → Greedy/CP-SAT/Hybrid → checker độc lập → lưu kết quả.
Streamlit giữ kịch bản đăng ký; React/FastAPI hỗ trợ upload, benchmark bốn solver và Monte Carlo riêng.
Cutoff đặc trưng là CRS_DEP_TIME − 2h. Replay dùng actual timestamps là hồi cứu, không chứng minh chất lượng ML.

## Định danh model

| Registry ID | Task | Status | Role | Downstream eligible |
|---|---|---|---|---|
| P4_ngboost_student_t | core_arrival | research_candidate | probabilistic_candidate_p4_heavy_tail | False |
| arrival_weighted_ensemble_v1 | core_arrival | current_core | core_point_ensemble | True |
| b5_ngboost_student_t | core_arrival | legacy_frozen | historical_probabilistic_comparator | True |
| departure_certified_point_v1 | core_departure | downstream_eligible | GATE_OUT_PREDICTION | True |

Checkpoint arrival deserialize thành src.models.probabilistic.baselines.B5NGBoostStudentT.
SHA-256: e7e7462f17b65b276ebdee9c7beced15e090f69b088a18896d5a91aaa8cb062f.
Native arrival ID là b5_ngboost_student_t (legacy_frozen). Tên P4 trong chứng nhận lịch sử thuộc một thế hệ báo cáo; registry hiện tại không coi P4 research_candidate và B5 là cùng ID có quyền ngang nhau.
Departure point model là XGBoost Regressor, khác outbound calibrated classifier.
Đợt này không đổi quyền registry hoặc checkpoint.

## Khả năng nạp checkpoint

| File | Bytes | Nạp | Loại đối tượng hoặc lỗi |
|---|---:|---|---|
| artifacts/dual_core/models/departure_distribution_v1.joblib | 375309 | LOADED | src.models.probabilistic.departure_distributions.DepartureNGBoostStudentTModel |
| artifacts/dual_core/models/departure_empirical_residual_v1.joblib | 1243679 | LOADED | src.models.probabilistic.departure_distributions.DepartureEmpiricalBaseline |
| artifacts/dual_core/models/departure_gaussian_residual_v1.joblib | 646248 | LOADED | src.models.probabilistic.departure_distributions.DepartureGaussianResidualModel |
| artifacts/dual_core/models/departure_linear_preprocessor_v1.joblib | 212590 | LOADED | src.data.departure_preprocessing.DeparturePreprocessingPipeline |
| artifacts/dual_core/models/departure_linear_preprocessor_v1_fold4.joblib | 211949 | LOADED | src.data.departure_preprocessing.DeparturePreprocessingPipeline |
| artifacts/dual_core/models/departure_ngboost_student_t_v1.joblib | 375309 | LOADED | src.models.probabilistic.departure_distributions.DepartureNGBoostStudentTModel |
| artifacts/dual_core/models/departure_ridge_baseline_v1.joblib | 2217 | LOADED | sklearn.linear_model._ridge.Ridge |
| artifacts/dual_core/models/departure_ridge_baseline_v1_fold4.joblib | 2201 | LOADED | sklearn.linear_model._ridge.Ridge |
| artifacts/dual_core/models/departure_tree_preprocessor_v1.joblib | 207187 | LOADED | src.data.departure_preprocessing.DeparturePreprocessingPipeline |
| artifacts/dual_core/models/departure_tree_preprocessor_v1_fold4.joblib | 206594 | LOADED | src.data.departure_preprocessing.DeparturePreprocessingPipeline |
| artifacts/dual_core/models/departure_xgboost_baseline_v1.joblib | 498135 | LOADED | xgboost.sklearn.XGBRegressor |
| artifacts/dual_core/models/departure_xgboost_baseline_v1_fold4.joblib | 497455 | LOADED | xgboost.sklearn.XGBRegressor |
| artifacts/models/refactored/best_hgb_absolute_weighted.joblib | 550712 | LOADED | sklearn.ensemble._hist_gradient_boosting.gradient_boosting.HistGradientBoostingRegressor |
| artifacts/models/refactored/best_hurdle_delay_predictor.joblib | 1189093 | LOADED | src.models.hurdle_inference.HurdleDelayPredictor |
| artifacts/probabilistic/ngboost_student_t/model_weights_frozen_v1.joblib | 243595 | LOADED | src.models.probabilistic.baselines.B5NGBoostStudentT |
| artifacts/remediation/outbound_classification/models/outbound_logistic_calibrated_v1.joblib | 5714 | LOAD_FAILED | AttributeError: Can't get attribute 'CalibratedPredictor' |
| artifacts/remediation/outbound_classification/models/outbound_logistic_classifier_v1.joblib | 2431 | LOADED | sklearn.linear_model._logistic.LogisticRegression |
| artifacts/remediation/outbound_classification/models/outbound_xgboost_calibrated_v1.joblib | 498237 | LOAD_FAILED | AttributeError: Can't get attribute 'CalibratedPredictor' |
| artifacts/remediation/outbound_classification/models/outbound_xgboost_classifier_v1.joblib | 497335 | LOADED | xgboost.sklearn.XGBClassifier |

Nạp được chỉ kiểm tra deserialize trên môi trường hiện tại, không chứng minh chất lượng thống kê hoặc khả năng phục vụ mọi model.

## Các bộ thực nghiệm

- Baseline arrival: 16.000 dòng OOF; tuned XGBoost: 1.254.518 dòng. Có pooled và macro riêng.
- Departure selection 2023: 332.734 dòng; dùng đúng classifier/regressor.
- G4 strict native run: 200 legs, 0 verified/inferred pairs, các turn single-leg. Không gọi là 200 rotations xác thực.
- Official MC500: 500 realizations, 5.500 slots, Gaussian copula 0,45 và marginal cấu hình.
- Web MC: arrival marginals độc lập, departure point giữ cố định; recourse biết toàn bộ ngày.
- Replay ATL 2026: 1.500 movements = 750 occupancies, 150 contact gates mô phỏng; khác sample upload cả ngày.

## Giới hạn nghiệm thu

SHAP: RECOMPUTED_TREESHAP, departure regression; không gán cho flight upload mới.
Visual QA, nhật ký nhóm, quyết định GVHD, Word/PDF/PPTX cuối và G13 nằm trong backlog.
P14/G12C và current_state.yaml giữ nguyên lịch sử. Bộ này là lớp đối chiếu hiện hành, không ghi đè quyết định LOCKED.
