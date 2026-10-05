"""Tests for OOF adapter — chuyển đổi OOF từ bất kỳ mô hình ML nào sang CP-SAT."""

import warnings

import pandas as pd
import pytest

from src.optimization.oof_adapter import (
    COLUMN_ALIASES,
    _crs_time_str_to_minutes,
    _find_column,
    diagnose_oof,
    oof_to_problem_instance,
)


# =====================================================================
# TEST: CRS_DEP_TIME STRING → MINUTES CONVERSION
# =====================================================================

class TestCrsTimeConversion:
    def test_normal_time_string(self) -> None:
        assert _crs_time_str_to_minutes("0800") == 480

    def test_midnight(self) -> None:
        assert _crs_time_str_to_minutes("0000") == 0

    def test_afternoon(self) -> None:
        assert _crs_time_str_to_minutes("1430") == 870

    def test_end_of_day(self) -> None:
        assert _crs_time_str_to_minutes("2400") == 1440

    def test_short_string(self) -> None:
        """'800' → pad to '0800' → 480 minutes."""
        assert _crs_time_str_to_minutes("800") == 480

    def test_numeric_float(self) -> None:
        """800.0 → '800' → '0800' → 480."""
        assert _crs_time_str_to_minutes(800.0) == 480

    def test_numeric_int(self) -> None:
        assert _crs_time_str_to_minutes(1430) == 870

    def test_nan_returns_zero(self) -> None:
        assert _crs_time_str_to_minutes(float("nan")) == 0

    def test_none_returns_zero(self) -> None:
        assert _crs_time_str_to_minutes(None) == 0


# =====================================================================
# TEST: COLUMN ALIAS DETECTION
# =====================================================================

class TestFindColumn:
    def test_finds_exact_match(self) -> None:
        df = pd.DataFrame({"flight_key": ["F1"], "other": [1]})
        assert _find_column(df, "flight_id") == "flight_key"

    def test_finds_xgboost_prob_column(self) -> None:
        df = pd.DataFrame({"xgb_prob": [0.5], "xgb_pred": [10.0]})
        assert _find_column(df, "p_delay") == "xgb_prob"
        assert _find_column(df, "delay_est_min") == "xgb_pred"

    def test_finds_oof_standard_columns(self) -> None:
        df = pd.DataFrame({"p_arr_delay_15": [0.3], "predicted_arr_delay_min": [5.0]})
        assert _find_column(df, "p_delay") == "p_arr_delay_15"
        assert _find_column(df, "delay_est_min") == "predicted_arr_delay_min"

    def test_returns_none_when_missing(self) -> None:
        df = pd.DataFrame({"unrelated": [1]})
        assert _find_column(df, "p_delay") is None

    def test_priority_order(self) -> None:
        """Khi có cả 2 cột, ưu tiên cột đầu tiên trong danh sách alias."""
        df = pd.DataFrame({"p_arr_delay_15": [0.3], "prob_delay": [0.4]})
        assert _find_column(df, "p_delay") == "p_arr_delay_15"


# =====================================================================
# TEST: OOF → PROBLEM INSTANCE CONVERSION
# =====================================================================

class TestOofToProblemInstance:
    """Tests chạy offline (không cần dữ liệu tabular_by_year thật)."""

    def _make_xgboost_oof(self) -> pd.DataFrame:
        """Giả lập OOF output từ XGBoost với đầy đủ cột."""
        return pd.DataFrame({
            "flight_key": ["FL_001", "FL_002", "FL_003"],
            "xgb_prob": [0.85, 0.20, 0.10],
            "xgb_pred": [25.0, 0.0, -5.0],
            "CRS_DEP_TIME": ["0600", "0630", "0700"],
            "CRS_ELAPSED_TIME": [45.0, 50.0, 40.0],
            "chain_id": ["ROT_A", "ROT_A", None],
        })

    def _make_standard_oof(self) -> pd.DataFrame:
        """Giả lập OOF output theo format chuẩn Week 4."""
        return pd.DataFrame({
            "flight_key": ["FL_001", "FL_002", "FL_003"],
            "p_arr_delay_15": [0.85, 0.20, 0.10],
            "predicted_arr_delay_min": [25.0, 0.0, -5.0],
            "CRS_DEP_TIME": ["0600", "0630", "0700"],
            "CRS_ELAPSED_TIME": [45.0, 50.0, 40.0],
        })

    def _make_minimal_oof(self) -> pd.DataFrame:
        """OOF chỉ có flight_key và 1 cột dự báo — tối thiểu nhất."""
        return pd.DataFrame({
            "flight_key": ["FL_001", "FL_002"],
            "prob": [0.7, 0.3],
        })

    def test_xgboost_format(self) -> None:
        df = self._make_xgboost_oof()
        instance = oof_to_problem_instance(df, num_gates=5, auto_enrich=False)

        assert len(instance.flights) == 3
        assert len(instance.gates) == 5
        assert instance.flights[0].p_delay == 0.85
        assert instance.flights[0].delay_est_min == 25.0
        assert instance.flights[0].sched_time_min == 360  # 06:00 = 360 min
        assert instance.flights[0].dwell_time_min == 45

    def test_standard_oof_format(self) -> None:
        df = self._make_standard_oof()
        instance = oof_to_problem_instance(df, num_gates=3, auto_enrich=False)

        assert len(instance.flights) == 3
        assert instance.flights[1].p_delay == 0.20
        assert instance.flights[1].delay_est_min == 0.0

    def test_minimal_oof_with_warning(self) -> None:
        df = self._make_minimal_oof()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            instance = oof_to_problem_instance(df, num_gates=3, auto_enrich=False)
            # Phải có warning về thiếu delay_est_min
            delay_warnings = [x for x in w if "phút trễ" in str(x.message)]
            assert len(delay_warnings) >= 1

        assert len(instance.flights) == 2
        assert instance.flights[0].p_delay == 0.7
        assert instance.flights[0].delay_est_min == 0.0  # default

    def test_raises_on_no_prediction_columns(self) -> None:
        df = pd.DataFrame({
            "flight_key": ["FL_001"],
            "unrelated_col": [42],
        })
        with pytest.raises(ValueError, match="cột dự báo"):
            oof_to_problem_instance(df, auto_enrich=False)

    def test_raises_on_no_flight_key_with_enrich(self) -> None:
        """Khi auto_enrich=True mà không có flight_key, enrich phải raise ValueError."""
        df = pd.DataFrame({
            "prob": [0.5],
            "pred": [10.0],
        })
        with pytest.raises(ValueError, match="flight_key"):
            oof_to_problem_instance(df, auto_enrich=True)

    def test_fallback_id_when_no_flight_key(self) -> None:
        """Khi auto_enrich=False mà không có flight_key, dùng index làm flight_id."""
        df = pd.DataFrame({
            "prob": [0.5],
        })
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            instance = oof_to_problem_instance(df, num_gates=3, auto_enrich=False)
        assert instance.flights[0].flight_id == "FL_0000"

    def test_chain_id_mapping(self) -> None:
        df = self._make_xgboost_oof()
        instance = oof_to_problem_instance(df, num_gates=3, auto_enrich=False)

        assert instance.flights[0].chain_group_id == "ROT_A"
        assert instance.flights[1].chain_group_id == "ROT_A"
        assert instance.flights[2].chain_group_id is None

    def test_crs_dep_time_conversion(self) -> None:
        """CRS_DEP_TIME string → phút từ 00:00."""
        df = self._make_xgboost_oof()
        instance = oof_to_problem_instance(df, num_gates=3, auto_enrich=False)

        assert instance.flights[0].sched_time_min == 360   # "0600"
        assert instance.flights[1].sched_time_min == 390   # "0630"
        assert instance.flights[2].sched_time_min == 420   # "0700"

    def test_p_delay_clamped_to_valid_range(self) -> None:
        """p_delay ngoài [0, 1] phải được clamp."""
        df = pd.DataFrame({
            "flight_key": ["FL_001", "FL_002"],
            "p_arr_delay_15": [1.5, -0.3],
            "predicted_arr_delay_min": [10.0, 5.0],
            "CRS_DEP_TIME": ["0800", "0900"],
        })
        instance = oof_to_problem_instance(df, num_gates=3, auto_enrich=False)

        assert instance.flights[0].p_delay == 1.0
        assert instance.flights[1].p_delay == 0.0

    def test_default_dwell_time_when_missing(self) -> None:
        df = pd.DataFrame({
            "flight_key": ["FL_001"],
            "prob": [0.5],
            "CRS_DEP_TIME": ["1000"],
        })
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            instance = oof_to_problem_instance(
                df, num_gates=3, default_dwell_time_min=60, auto_enrich=False,
            )
        assert instance.flights[0].dwell_time_min == 60

    def test_gates_generated_correctly(self) -> None:
        df = self._make_standard_oof()
        instance = oof_to_problem_instance(df, num_gates=10, auto_enrich=False)

        assert len(instance.gates) == 10
        assert instance.gates[0].gate_id == "G01"
        assert instance.gates[9].gate_id == "G10"
        assert all(g.compatible_types == ["ALL"] for g in instance.gates)


# =====================================================================
# TEST: DIAGNOSE OOF
# =====================================================================

class TestDiagnoseOof:
    def test_full_oof_ready(self) -> None:
        df = pd.DataFrame({
            "flight_key": ["F1"],
            "p_arr_delay_15": [0.5],
            "predicted_arr_delay_min": [10.0],
            "CRS_DEP_TIME": ["0800"],
            "CRS_ELAPSED_TIME": [45.0],
            "chain_id": ["C1"],
        })
        report = diagnose_oof(df)
        assert report["ready_for_cpsat"] is True
        assert report["enrich_needed"] is False

    def test_minimal_oof_needs_enrich(self) -> None:
        df = pd.DataFrame({
            "flight_key": ["F1"],
            "p_arr_delay_15": [0.5],
            "predicted_arr_delay_min": [10.0],
        })
        report = diagnose_oof(df)
        assert report["ready_for_cpsat"] is True
        assert report["enrich_needed"] is True
        assert "sched_time" in report["missing_fields"]
        assert "chain_id" in report["missing_fields"]

    def test_no_predictions_not_ready(self) -> None:
        df = pd.DataFrame({
            "flight_key": ["F1"],
            "unrelated": [42],
        })
        report = diagnose_oof(df)
        assert report["ready_for_cpsat"] is False


# =====================================================================
# TEST: UNIFIED PREDICTIONS & SCENARIO FILTERING
# =====================================================================

class TestUnifiedPredictionsSupport:
    def test_flight_idx_recognized_as_flight_id(self) -> None:
        df = pd.DataFrame({
            "flight_idx": [101, 102],
            "p_arr_delay_15": [0.4, 0.6],
            "predicted_arr_delay_min": [12.0, 5.0],
            "ARR_HOUR": [8, 14],
        })
        instance = oof_to_problem_instance(df, auto_enrich=False)
        assert instance.flights[0].flight_id == "101"
        assert instance.flights[1].flight_id == "102"
        assert instance.flights[0].sched_time_min == 480   # 8 * 60
        assert instance.flights[1].sched_time_min == 840   # 14 * 60

    def test_airport_and_date_filtering(self) -> None:
        df = pd.DataFrame({
            "flight_idx": [1, 2, 3],
            "DEST_AIRPORT": ["ATL", "JFK", "ATL"],
            "ORIGIN_AIRPORT": ["ORD", "ATL", "DFW"],
            "MONTH": [1, 1, 2],
            "DAY": [1, 1, 1],
            "ARR_HOUR": [10, 11, 12],
            "p_arr_delay_15": [0.2, 0.3, 0.4],
            "predicted_arr_delay_min": [5.0, 6.0, 7.0],
        })
        instance = oof_to_problem_instance(
            df,
            airport="ATL",
            month=1,
            day=1,
            direction="ARR",
            auto_enrich=False,
        )
        assert len(instance.flights) == 1
        assert instance.flights[0].flight_id == "1"
        assert instance.airport == "ATL"

    def test_solve_full_turn_unified_artifact_if_present(self) -> None:
        from pathlib import Path
        from src.optimization.oof_adapter import solve_from_oof_file

        artifact_path = Path("src/artifacts/predictions/full_turn_unified_predictions_for_cpsat.parquet")
        if artifact_path.exists():
            assignment, status, wall_time = solve_from_oof_file(
                artifact_path,
                airport="ATL",
                planning_date="2024-01-01",
                num_gates=25,
                time_limit_sec=10,
                auto_enrich=False,
            )
            assert status in ("OPTIMAL", "FEASIBLE")
            assert len(assignment) == 162
            assert wall_time < 10.0
