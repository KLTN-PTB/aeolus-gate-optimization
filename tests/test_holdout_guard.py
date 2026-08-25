import pytest

from src.data.access_guard import DataAccessDenied, assert_data_access_allowed


@pytest.mark.parametrize("year", range(2016, 2023))
def test_development_years_2016_to_2022_are_allowed(year: int) -> None:
    assert_data_access_allowed(year, "development")


def test_2023_development_is_allowed() -> None:
    assert_data_access_allowed(2023, "development")


def test_2024_development_is_blocked() -> None:
    with pytest.raises(DataAccessDenied, match="sealed from development"):
        assert_data_access_allowed(2024, "development")


def test_2024_schema_audit_path_is_allowed() -> None:
    assert_data_access_allowed(2024, "schema_audit")


def test_2024_canonicalize_holdout_is_allowed_without_unsealing_development() -> None:
    assert_data_access_allowed(2024, "canonicalize_holdout")


def test_2024_final_evaluation_is_blocked_without_freeze_manifest() -> None:
    with pytest.raises(DataAccessDenied, match="freeze manifest"):
        assert_data_access_allowed(2024, "final_evaluation")
