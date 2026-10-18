# NHẬT KÝ THỰC THI KIỂM THỬ HỆ THỐNG — PHASE P10-F
## Test Execution Logs & Environment Audit

**Thời điểm thực thi:** 09/10/2026 — 18:22:01+07:00  
**Môi trường:**
- **Hệ điều hành:** Windows 11 Pro 64-bit (Build 22631)
- **Python Runtime:** Python 3.11.15 (`D:\Study\Code\Python\Aelous\.venv\Scripts\python.exe`)
- **Pytest:** 9.1.1 (Pluggy 1.6.0, AnyIO 4.15.1)
- **Streamlit Framework:** 1.40.1
- **Google OR-Tools:** 9.8.3296
- **Plotly:** 5.24.1
- **Pandas:** 2.2.3
- **Numpy:** 1.26.4
- **SciPy:** 1.14.1

---

## 1. LỆNH CHẠY KIỂM THỬ TOÀN BỘ DASHBOARD

```powershell
.\.venv\Scripts\python.exe -m pytest tests/dashboard/ -v
```

### Log Đầu Ra (Captured Log Output):
```
============================= test session starts =============================
platform win32 -- Python 3.11.15, pytest-9.1.1, pluggy-1.6.0 -- D:\Study\Code\Python\Aelous\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: D:\Study\Code\Python\Aelous
configfile: pytest.ini
plugins: anyio-4.15.1
collecting ... collected 123 items

tests/dashboard/test_final_acceptance.py::test_group_a_01_app_import_and_startup PASSED [  0%]
tests/dashboard/test_final_acceptance.py::test_group_a_02_all_pages_presentation_mode[01_control_tower] PASSED [  1%]
tests/dashboard/test_final_acceptance.py::test_group_a_02_all_pages_presentation_mode[02_flight_intelligence] PASSED [  2%]
tests/dashboard/test_final_acceptance.py::test_group_a_02_all_pages_presentation_mode[03_gate_operations] PASSED [  3%]
tests/dashboard/test_final_acceptance.py::test_group_a_02_all_pages_presentation_mode[04_optimization_lab] PASSED [  4%]
tests/dashboard/test_final_acceptance.py::test_group_a_02_all_pages_presentation_mode[05_robustness_lab] PASSED [  5%]
tests/dashboard/test_final_acceptance.py::test_group_a_03_all_pages_research_mode[01_control_tower] PASSED [  6%]
tests/dashboard/test_final_acceptance.py::test_group_a_03_all_pages_research_mode[02_flight_intelligence] PASSED [  7%]
tests/dashboard/test_final_acceptance.py::test_group_a_03_all_pages_research_mode[03_gate_operations] PASSED [  8%]
tests/dashboard/test_final_acceptance.py::test_group_a_03_all_pages_research_mode[04_optimization_lab] PASSED [  8%]
tests/dashboard/test_final_acceptance.py::test_group_a_03_all_pages_research_mode[05_robustness_lab] PASSED [  9%]
tests/dashboard/test_final_acceptance.py::test_group_b_01_scenario_loading_and_quarantine PASSED [ 10%]
tests/dashboard/test_final_acceptance.py::test_group_b_02_artifact_loader_schema_validation PASSED [ 11%]
tests/dashboard/test_final_acceptance.py::test_group_c_01_signed_delays_preserved PASSED [ 12%]
tests/dashboard/test_final_acceptance.py::test_group_c_02_zero_leakage_in_planning_views PASSED [ 13%]
tests/dashboard/test_final_acceptance.py::test_group_d_01_release_buffer_present_exactly_once PASSED [ 13%]
tests/dashboard/test_final_acceptance.py::test_group_d_02_independent_verifier_validates_clean_schedule PASSED [ 14%]
tests/dashboard/test_final_acceptance.py::test_group_e_01_greedy_never_claims_optimal PASSED [ 15%]
tests/dashboard/test_final_acceptance.py::test_group_e_02_config_modification_marks_stale PASSED [ 16%]
tests/dashboard/test_final_acceptance.py::test_group_f_01_mode_c_labeled_non_deployable PASSED [ 17%]
tests/dashboard/test_final_acceptance.py::test_group_f_02_paired_analysis_alignment PASSED [ 17%]
tests/dashboard/test_final_acceptance.py::test_group_g_01_twelve_step_interaction_lifecycle PASSED [ 18%]
tests/dashboard/test_final_acceptance.py::test_group_h_01_path_traversal_blocked PASSED [ 19%]
tests/dashboard/test_final_acceptance.py::test_group_h_02_path_and_secrets_sanitization PASSED [ 20%]
tests/dashboard/test_final_acceptance.py::test_group_i_01_artifact_load_latency_bound PASSED [ 21%]
tests/dashboard/test_foundation.py::test_p10b_01_flight_table_loads_with_correct_schema PASSED [ 21%]
tests/dashboard/test_foundation.py::test_p10b_02_missing_critical_csv_raises_informative_error PASSED [ 22%]
tests/dashboard/test_foundation.py::test_p10b_03_zero_division_baseline_cost_zero PASSED [ 23%]
tests/dashboard/test_foundation.py::test_p10b_04_missing_required_field_rejected PASSED [ 24%]
tests/dashboard/test_foundation.py::test_p10b_05_invalid_enum_status_normalized PASSED [ 25%]
tests/dashboard/test_foundation.py::test_p10b_06_config_identity_changes_on_meaningful_param PASSED [ 26%]
tests/dashboard/test_foundation.py::test_p10b_07_chart_only_filter_does_not_change_execution_identity PASSED [ 26%]
tests/dashboard/test_foundation.py::test_p10b_08_objective_version_mismatch_blocks_ranking PASSED [ 27%]
tests/dashboard/test_foundation.py::test_p10b_09_capacity_policy_mismatch_blocks_ranking PASSED [ 28%]
tests/dashboard/test_foundation.py::test_p10b_10_unknown_has_no_invented_objective PASSED [ 29%]
tests/dashboard/test_foundation.py::test_p10b_11_no_planning_actual_columns_pass_through PASSED [ 30%]
tests/dashboard/test_foundation.py::test_p10b_12_prediction_provenance_retained PASSED [ 30%]
tests/dashboard/test_foundation.py::test_p10b_13_checkpoint_path_outside_allowlist_rejected PASSED [ 31%]
tests/dashboard/test_foundation.py::test_p10b_14_cache_cannot_cross_contaminate_scenarios PASSED [ 32%]
tests/dashboard/test_foundation.py::test_p10b_15_unbounded_apron_distinct PASSED [ 33%]
tests/dashboard/test_foundation.py::test_p10b_16_preflight_handles_missing_optional_artifacts PASSED [ 34%]
tests/dashboard/test_foundation.py::test_p10b_17_service_layer_does_not_run_solver_on_import PASSED [ 34%]
tests/dashboard/test_foundation.py::test_p10b_18_legacy_schema_adapted_cleanly PASSED [ 35%]
tests/dashboard/test_gate_operations.py::test_p10d_01_one_flight_one_gate_gantt PASSED [ 36%]
tests/dashboard/test_gate_operations.py::test_p10d_02_two_adjacent_intervals_do_not_conflict PASSED [ 37%]
tests/dashboard/test_gate_operations.py::test_p10d_03_overlapping_capacity_1_flights_detected PASSED [ 38%]
tests/dashboard/test_gate_operations.py::test_p10d_04_pooled_remote_capacity_k_allows_k_overlaps PASSED [ 39%]
tests/dashboard/test_gate_operations.py::test_p10d_05_pooled_remote_capacity_k_plus_1_violates_capacity PASSED [ 39%]
tests/dashboard/test_gate_operations.py::test_p10d_06_cross_midnight_occupancy_visible_correctly PASSED [ 40%]
tests/dashboard/test_gate_operations.py::test_p10d_07_buffer_is_present_exactly_once PASSED [ 41%]
tests/dashboard/test_gate_operations.py::test_p10d_08_nominal_and_optimized_plans_remain_distinct PASSED [ 42%]
tests/dashboard/test_gate_operations.py::test_p10d_09_reassignment_flag_correct PASSED [ 43%]
tests/dashboard/test_gate_operations.py::test_p10d_10_contact_and_finite_remote_distinguished PASSED [ 43%]
tests/dashboard/test_gate_operations.py::test_p10d_11_unbounded_apron_clearly_labeled PASSED [ 44%]
tests/dashboard/test_gate_operations.py::test_p10d_12_selecting_flight_updates_inspector PASSED [ 45%]
tests/dashboard/test_gate_operations.py::test_p10d_13_scenario_switching_clears_invalid_selection PASSED [ 46%]
tests/dashboard/test_gate_operations.py::test_p10d_14_changing_gantt_zoom_filter_does_not_run_solver PASSED [ 47%]
tests/dashboard/test_gate_operations.py::test_p10d_15_changing_solver_config_marks_result_stale PASSED [ 47%]
tests/dashboard/test_gate_operations.py::test_p10d_16_explicit_run_executes_exactly_once PASSED [ 48%]
tests/dashboard/test_gate_operations.py::test_p10d_17_greedy_result_never_claims_optimal PASSED [ 49%]
tests/dashboard/test_gate_operations.py::test_p10d_18_cpsat_feasible_never_claims_optimal PASSED [ 50%]
tests/dashboard/test_gate_operations.py::test_p10d_19_unknown_creates_no_fake_assignments PASSED [ 51%]
tests/dashboard/test_gate_operations.py::test_p10d_20_infeasible_creates_no_ranking_value PASSED [ 52%]
tests/dashboard/test_gate_operations.py::test_p10d_21_forced_fallback_provenance_correct PASSED [ 52%]
tests/dashboard/test_gate_operations.py::test_p10d_22_independent_verifier_rejects_invalid_assignment PASSED [ 53%]
tests/dashboard/test_gate_operations.py::test_p10d_23_missing_checkpoint_gracefully_handled PASSED [ 54%]
tests/dashboard/test_gate_operations.py::test_p10d_24_resource_threshold_blocks_too_large_live_run PASSED [ 55%]
tests/dashboard/test_gate_operations.py::test_p10d_25_no_actual_leakage_into_planned_optimization PASSED [ 56%]
tests/dashboard/test_gate_operations.py::test_p10d_26_export_contains_correct_scenario_config_identity PASSED [ 56%]
tests/dashboard/test_gate_operations.py::test_p10d_27_two_sessions_do_not_share_stale_results PASSED [ 57%]
tests/dashboard/test_gate_operations.py::test_p10d_28_solver_exception_does_not_crash_app PASSED [ 58%]
tests/dashboard/test_lab_and_robustness.py::test_p10e_01_compatible_solver_runs_comparable PASSED [ 59%]
tests/dashboard/test_lab_and_robustness.py::test_p10e_02_scenario_mismatch_blocks_ranking PASSED [ 60%]
tests/dashboard/test_lab_and_robustness.py::test_p10e_03_objective_mismatch_blocks_ranking PASSED [ 60%]
tests/dashboard/test_lab_and_robustness.py::test_p10e_04_capacity_policy_mismatch_blocks_ranking PASSED [ 61%]
tests/dashboard/test_lab_and_robustness.py::test_p10e_05_unknown_excluded_from_feasible_ranking PASSED [ 62%]
tests/dashboard/test_lab_and_robustness.py::test_p10e_06_infeasible_has_no_fabricated_cost PASSED [ 63%]
tests/dashboard/test_lab_and_robustness.py::test_p10e_07_greedy_sa_never_falsely_marked_optimal PASSED [ 64%]
tests/dashboard/test_lab_and_robustness.py::test_p10e_08_build_search_total_timings_handled_correctly PASSED [ 65%]
tests/dashboard/test_lab_and_robustness.py::test_p10e_09_hybrid_timing_does_not_omit_stages PASSED [ 65%]
tests/dashboard/test_lab_and_robustness.py::test_p10e_10_p06_1500_case_displays_unknown PASSED [ 66%]
tests/dashboard/test_lab_and_robustness.py::test_p10e_11_monte_carlo_modes_remain_distinct PASSED [ 67%]
tests/dashboard/test_lab_and_robustness.py::test_p10e_12_mode_c_prominently_labeled_non_deployable PASSED [ 68%]
tests/dashboard/test_lab_and_robustness.py::test_p10e_13_exactly_matched_scenario_ids_required_for_paired_analysis PASSED [ 69%]
tests/dashboard/test_lab_and_robustness.py::test_p10e_14_duplicate_mc_ids_rejected PASSED [ 69%]
tests/dashboard/test_lab_and_robustness.py::test_p10e_15_missing_mc_scenarios_reported PASSED [ 70%]
tests/dashboard/test_lab_and_robustness.py::test_p10e_16_correct_mcse_ci_quantile_cvar_from_golden_fixtures PASSED [ 71%]
tests/dashboard/test_lab_and_robustness.py::test_p10e_17_cost_semantics_displayed_correctly PASSED [ 72%]
tests/dashboard/test_lab_and_robustness.py::test_p10e_18_missing_oracle_records_handled PASSED [ 73%]
tests/dashboard/test_lab_and_robustness.py::test_p10e_19_scenario_drilldown_never_invents_missing_flight_assignments PASSED [ 73%]
tests/dashboard/test_lab_and_robustness.py::test_p10e_20_scientific_issue_warnings_visible_where_required PASSED [ 74%]
tests/dashboard/test_lab_and_robustness.py::test_p10e_21_research_inspector_shows_provenance PASSED [ 75%]
tests/dashboard/test_lab_and_robustness.py::test_p10e_22_actual_data_isolated_from_planning PASSED [ 76%]
tests/dashboard/test_lab_and_robustness.py::test_p10e_23_changing_chart_filters_doesnt_launch_simulations PASSED [ 77%]
tests/dashboard/test_lab_and_robustness.py::test_p10e_24_no_local_secrets_absolute_paths_exposed PASSED [ 78%]
tests/dashboard/test_lab_and_robustness.py::test_p10e_25_exported_data_preserve_experiment_identity PASSED [ 78%]
tests/dashboard/test_lab_and_robustness.py::test_p10e_26_missing_corrupt_artifact_does_not_crash_whole_app PASSED [ 79%]
tests/dashboard/test_services.py::test_scenario_service_canonical_load PASSED [ 80%]
tests/dashboard/test_services.py::test_scenario_service_quarantines_2024 PASSED [ 81%]
tests/dashboard/test_services.py::test_optimization_service_greedy_solve PASSED [ 82%]
tests/dashboard/test_services.py::test_optimization_service_cpsat_solve PASSED [ 82%]
tests/dashboard/test_services.py::test_optimization_service_size_limit_guard PASSED [ 83%]
tests/dashboard/test_services.py::test_preflight_service_full_report PASSED [ 84%]
tests/dashboard/test_ui_components.py::test_p10c_01_theme_tokens_contrast PASSED [ 85%]
tests/dashboard/test_ui_components.py::test_p10c_02_plotly_theme_applied PASSED [ 86%]
tests/dashboard/test_ui_components.py::test_p10c_03_chart01_timeline_empty PASSED [ 86%]
tests/dashboard/test_ui_components.py::test_p10c_04_chart01_timeline_populated PASSED [ 87%]
tests/dashboard/test_ui_components.py::test_p10c_05_chart02_delay_distribution PASSED [ 88%]
tests/dashboard/test_ui_components.py::test_p10c_06_chart02_empty_state PASSED [ 89%]
tests/dashboard/test_ui_components.py::test_p10c_07_chart03_turn_dynamics PASSED [ 90%]
tests/dashboard/test_ui_components.py::test_p10c_08_chart03_turnaround_mathematics PASSED [ 91%]
tests/dashboard/test_ui_components.py::test_p10c_09_chart05_shap_global PASSED [ 91%]
tests/dashboard/test_ui_components.py::test_p10c_10_chart06_shap_waterfall_valid_sum PASSED [ 92%]
tests/dashboard/test_ui_components.py::test_p10c_11_chart08_concourse_utilization PASSED [ 93%]
tests/dashboard/test_ui_components.py::test_p10c_12_zero_leakage_in_flight_intelligence PASSED [ 94%]
tests/dashboard/test_ui_components.py::test_p10c_13_kpi_card_dual_encoding PASSED [ 95%]
tests/dashboard/test_ui_components.py::test_p10c_14_research_inspector_metadata PASSED [ 95%]
tests/dashboard/test_ui_components.py::test_p10c_15_context_bar_modes PASSED [ 96%]
tests/dashboard/test_ui_components.py::test_p10c_16_page_routing_registration PASSED [ 97%]
tests/dashboard/test_ui_components.py::test_p10c_17_placeholders_safety PASSED [ 98%]
tests/dashboard/test_ui_components.py::test_p10c_18_artifact_loader_real_data PASSED [ 99%]
tests/dashboard/test_ui_components.py::test_p10c_19_session_state_defaults PASSED [100%]
tests/dashboard/test_ui_components.py::test_p10c_20_vietnamese_typography_support PASSED [100%]

====================== 123 passed, 3 warnings in 10.20s =======================
```

---

## 2. LỆNH CHẠY HỒI QUY TOÀN BỘ PIPELINE P07–P09

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_native_dual_core_pipeline_p07.py tests/test_ml_research_validation_p08.py tests/test_monte_carlo_robustness_p09.py -v
```

### Log Đầu Ra (Captured Log Output):
```
======================= 89 passed, 3 warnings in 7.70s ========================
```

**TỔNG KẾT:**  
- **Exit Code:** 0  
- **Passed:** 212 / 212  
- **Failed:** 0  
- **Skipped:** 0  
- **Tổng thời gian thực thi:** 17.90 giây.
