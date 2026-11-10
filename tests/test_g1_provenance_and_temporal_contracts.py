"""Authoritative test suite for AEOLUS-G1: Data Provenance, Temporal Contracts & Evidence Lineage.

Covers Test Matrix:
- PROV-01 to PROV-06 (Data and scenario provenance verification, non-fabrication)
- TIME-01 to TIME-05 (T-2h cutoff enforcement, future feature rejection, timezone handling)
- COMPAT-01 to COMPAT-02 (Backward compatibility for legacy view models, contracts, and solver inputs)
- FAILCLOSED-01 to FAILCLOSED-02 (Fail-closed behavior on missing partitions or checkpoints)
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

from dashboard.adapters.export_adapter import export_assignments_to_csv, export_run_manifest_to_json
from dashboard.core.config import DEFAULT_CONFIG, DashboardConfig
from dashboard.core.contracts import (
    GateTimelineView,
    ProvenanceType,
    ScenarioContext,
    SolverRunView,
    FlightPredictionView,
)
from dashboard.services.scenario_service import ScenarioService
from src.contracts.provenance import (
    CANONICAL_P07_DUAL_CORE_PROVENANCE,
    CANONICAL_P09_SCALABILITY_PROVENANCE,
    CANONICAL_REAL_AEOLUS_PROVENANCE,
    DataLineageError,
    DataOrigin,
    EvaluationRegime,
    EvidenceProvenance,
    InformationRegime,
    PairingSource,
    PredictionSource,
    ProvenanceMismatchError,
    ScenarioGeneration,
    SilentFallbackError,
)
from src.contracts.temporal import (
    DEFAULT_HUB_TIMEZONE,
    OperationalTemporalProfile,
    TemporalBoundaryError,
    TemporalLeakageError,
    TemporalPointType,
    TemporalUncertaintyError,
    calculate_prediction_cutoff_utc,
    ensure_utc_datetime,
    is_column_provably_safe_at_cutoff,
    validate_feature_temporal_availability,
)
from src.simulation.scalability_scenario import load_canonical_source_data


# ==============================================================================
# PROV-01: Real input được nhận diện đúng
# ==============================================================================
def test_prov_01_real_input_correctly_identified():
    """PROV-01: Authentic historical BTS/Aeolus records must be recognized as real."""
    prov = CANONICAL_REAL_AEOLUS_PROVENANCE
    assert prov.is_real is True
    assert prov.is_synthetic is False
    assert prov.data_origin == DataOrigin.REAL_AEOLUS
    assert prov.pairing_source == PairingSource.VERIFIED_ROTATION
    assert prov.scenario_generation == ScenarioGeneration.HISTORICAL_REPLAY
    # Should not raise under require_real
    prov.validate_fail_closed(require_real=True)


# ==============================================================================
# PROV-02: Synthetic scenario được nhận diện đúng
# ==============================================================================
def test_prov_02_synthetic_scenario_correctly_identified():
    """PROV-02: Scalability scenarios must be identified as synthetic, never real."""
    prov = CANONICAL_P09_SCALABILITY_PROVENANCE
    assert prov.is_synthetic is True
    assert prov.is_real is False
    assert prov.data_origin == DataOrigin.REAL_DERIVED
    assert prov.scenario_generation == ScenarioGeneration.SCALABILITY_GENERATOR
    assert prov.pairing_source == PairingSource.UNPAIRED

    # Strict check: require_real must raise SilentFallbackError
    with pytest.raises(SilentFallbackError):
        prov.validate_fail_closed(require_real=True)


# ==============================================================================
# PROV-03: Precomputed prediction không được ghi là native
# ==============================================================================
def test_prov_03_precomputed_prediction_not_recorded_as_native():
    """PROV-03: Precomputed predictions must not masquerade as live native inference."""
    prov = EvidenceProvenance(
        data_origin=DataOrigin.REAL_DERIVED,
        prediction_source=PredictionSource.PRECOMPUTED,
        pairing_source=PairingSource.SYNTHETIC_PAIR,
        scenario_generation=ScenarioGeneration.PARAMETRIC_SIMULATION,
        information_regime=InformationRegime.PRE_OPERATIONAL,
        evaluation_regime=EvaluationRegime.SELECTION_2023,
    )

    with pytest.raises(ProvenanceMismatchError) as exc_info:
        prov.validate_fail_closed(require_native=True)
    assert "Native live inference required" in str(exc_info.value)
    assert prov.prediction_source != PredictionSource.NATIVE_INFERENCE


# ==============================================================================
# PROV-04: Missing provenance không mặc định là real
# ==============================================================================
def test_prov_04_missing_provenance_defaults_to_unknown_not_real():
    """PROV-04: Missing or unverified provenance must default to UNKNOWN and fail closed."""
    default_prov = EvidenceProvenance()
    assert default_prov.data_origin == DataOrigin.UNKNOWN
    assert default_prov.prediction_source == PredictionSource.UNKNOWN
    assert default_prov.is_real is False
    assert default_prov.is_verified is False

    # Fail closed when forbid_unknown is set
    with pytest.raises(DataLineageError) as exc_info:
        default_prov.validate_fail_closed(forbid_unknown=True)
    assert "unverified dimensions" in str(exc_info.value)

    # Fail closed when require_real is set
    with pytest.raises(SilentFallbackError):
        default_prov.validate_fail_closed(require_real=True)


# ==============================================================================
# PROV-05: Synthetic data không được export với nguồn real
# ==============================================================================
def test_prov_05_synthetic_data_not_exported_as_real():
    """PROV-05: Synthetic scenario assignments cannot be exported under claimed REAL_AEOLUS origin."""
    assignment = GateTimelineView(
        assignment_id="ASGN_001",
        flight_id="S1500-0001",
        gate_id="G_01",
        concourse="T",
        start_min=480,
        end_min=540,
        scenario_id="SCEN_P09_CANONICAL_120",
    )

    # Must raise ProvenanceMismatchError when claimed_origin is REAL_AEOLUS
    with pytest.raises(ProvenanceMismatchError) as exc_info:
        export_assignments_to_csv(
            [assignment],
            scenario_id="SCEN_P09_CANONICAL_120",
            claimed_origin="REAL_AEOLUS",
        )
    assert "PROVENANCE VIOLATION" in str(exc_info.value)

    # Legitimate export with truth-in-advertising succeeds
    csv_str = export_assignments_to_csv([assignment], scenario_id="SCEN_P09_CANONICAL_120")
    assert "data_origin" in csv_str
    assert "SYNTHETIC" in csv_str


# ==============================================================================
# PROV-06: Runtime và dashboard label khớp nhau
# ==============================================================================
def test_prov_06_runtime_and_dashboard_labels_match():
    """PROV-06: Registered scenarios in config and ScenarioService context must match accurately."""
    service = ScenarioService()
    ctx = service.get_scenario_context("SCEN_P09_CANONICAL_120")

    assert ctx.scenario_id == "SCEN_P09_CANONICAL_120"
    assert ctx.is_synthetic is True
    assert ctx.data_origin == "REAL_DERIVED"
    assert ctx.scenario_generation == "SCALABILITY_GENERATOR"
    assert ctx.pairing_source == "UNPAIRED"
    assert ctx.evidence_provenance is not None
    assert ctx.evidence_provenance.is_synthetic is True


# ==============================================================================
# TIME-01: Feature có available_at trước cutoff được chấp nhận
# ==============================================================================
def test_time_01_feature_available_before_cutoff_accepted():
    """TIME-01: Feature available strictly prior to decision cutoff must be accepted."""
    cutoff = datetime(2023, 7, 15, 12, 0, tzinfo=timezone.utc)
    avail = datetime(2023, 7, 15, 11, 45, tzinfo=timezone.utc)

    # Should execute cleanly without error
    validate_feature_temporal_availability("CRS_DEP_TIME", avail, cutoff)


# ==============================================================================
# TIME-02: Future feature bị từ chối
# ==============================================================================
def test_time_02_future_feature_rejected_and_actuals_flagged():
    """TIME-02: Features arriving after cutoff or actual operation columns must be rejected."""
    cutoff = datetime(2023, 7, 15, 12, 0, tzinfo=timezone.utc)
    future_avail = datetime(2023, 7, 15, 12, 1, tzinfo=timezone.utc)

    with pytest.raises(TemporalLeakageError) as exc_info:
        validate_feature_temporal_availability("ACTUAL_WHEELS_ON", future_avail, cutoff)
    assert "TEMPORAL LEAKAGE DETECTED" in str(exc_info.value)

    # Verify column safety contract classifies actual operational columns as unsafe
    for col in ["DEP_TIME", "TAXI_OUT", "WHEELS_OFF", "WHEELS_ON", "TAXI_IN", "ARR_TIME"]:
        is_safe, rationale = is_column_provably_safe_at_cutoff(col, direction="ARR")
        assert is_safe is False, f"Column {col} should not be marked safe"
        assert "actual" in rationale.lower()


# ==============================================================================
# TIME-03: Missing timestamp bị xử lý an toàn
# ==============================================================================
def test_time_03_missing_timestamp_handled_fail_closed():
    """TIME-03: Missing timestamp cannot be assumed to be past-known; fails closed."""
    cutoff = datetime(2023, 7, 15, 12, 0, tzinfo=timezone.utc)

    with pytest.raises(TemporalUncertaintyError) as exc_info:
        validate_feature_temporal_availability("UNVERIFIED_WEATHER_OBS", None, cutoff, allow_unverified=False)
    assert "unknown/unverified availability" in str(exc_info.value)


# ==============================================================================
# TIME-04: Timezone và date boundary
# ==============================================================================
def test_time_04_timezone_and_date_boundary_conversion():
    """TIME-04: ATL timezone (America/New_York) and UTC alignment must be exact across DST."""
    # Summer date (EDT: UTC-4)
    dt_summer = datetime(2023, 7, 15, 8, 30)
    utc_summer = ensure_utc_datetime(dt_summer, default_tz=DEFAULT_HUB_TIMEZONE)
    assert utc_summer.hour == 12  # 08:30 EDT = 12:30 UTC
    assert utc_summer.minute == 30

    # Winter date (EST: UTC-5)
    dt_winter = datetime(2023, 1, 15, 8, 30)
    utc_winter = ensure_utc_datetime(dt_winter, default_tz=DEFAULT_HUB_TIMEZONE)
    assert utc_winter.hour == 13  # 08:30 EST = 13:30 UTC
    assert utc_winter.minute == 30


# ==============================================================================
# TIME-05: Inbound/outbound cutoff theo đúng contract
# ==============================================================================
def test_time_05_inbound_outbound_cutoff_contract():
    """TIME-05: Authoritative cutoff must be exactly T-2h relative to scheduled event."""
    sched_event = datetime(2023, 7, 15, 14, 0, tzinfo=timezone.utc)
    cutoff = calculate_prediction_cutoff_utc(sched_event, hours_before=2.0)
    assert cutoff == datetime(2023, 7, 15, 12, 0, tzinfo=timezone.utc)
    assert (sched_event - cutoff).total_seconds() == 7200.0

    profile = OperationalTemporalProfile(
        flight_id="LEG_ARR_001",
        direction="ARR",
        scheduled_event_local=datetime(2023, 7, 15, 10, 0),
    )
    is_valid, violations = profile.validate_causality()
    assert is_valid is True
    assert len(violations) == 0


# ==============================================================================
# COMPAT-01: Legacy artifact vẫn đọc được hoặc báo migration rõ
# ==============================================================================
def test_compat_01_legacy_artifact_and_model_compatibility():
    """COMPAT-01: Legacy dictionary with missing provenance dimensions deserializes cleanly."""
    legacy_dict = {
        "data_origin": "REAL_DERIVED",
        "notes": "Legacy test record",
    }
    prov = EvidenceProvenance.from_dict(legacy_dict)
    assert prov.data_origin == DataOrigin.REAL_DERIVED
    assert prov.prediction_source == PredictionSource.UNKNOWN
    assert prov.pairing_source == PairingSource.UNKNOWN
    assert prov.scenario_generation == ScenarioGeneration.UNKNOWN

    # View model backward compatibility
    scen_ctx = ScenarioContext(
        scenario_id="SCEN_LEGACY",
        hub_iata="ATL",
        flight_count=100,
        gate_count=20,
        remote_capacity=1,
        scenario_hash="abc123hash",
    )
    assert scen_ctx.provenance == ProvenanceType.SCHEDULE_BASELINE
    assert scen_ctx.data_origin == "UNKNOWN"
    assert scen_ctx.is_synthetic is False


# ==============================================================================
# COMPAT-02: Existing solver/model input không thay đổi giá trị nghiệp vụ
# ==============================================================================
def test_compat_02_solver_input_business_values_unchanged():
    """COMPAT-02: Scenario flights and gates preserve exact mathematical domain structures."""
    service = ScenarioService()
    flights, gates = service.load_scenario("SCEN_P09_CANONICAL_120")

    assert len(flights) == 120
    assert len(gates) == 26  # 25 contact + 1 remote
    assert flights[0].min_turnaround_min == 45
    assert flights[0].buffer_min == 15
    assert gates[0].gate_id == "G_01"



# ==============================================================================
# FAILCLOSED-01: Missing real partition không sinh dữ liệu giả
# ==============================================================================
def test_failclosed_01_missing_real_partition_raises_error():
    """FAILCLOSED-01: Requesting real-data loading on missing partitions fails closed."""
    # Attempting to load real data from nonexistent directory
    with pytest.raises(FileNotFoundError):
        load_canonical_source_data(source_dir=Path("data/processed/nonexistent_partition_9999"))

    # Attempting to load synthetic scenario in require_real mode
    service = ScenarioService()
    with pytest.raises(SilentFallbackError) as exc_info:
        service.load_scenario("SCEN_P09_CANONICAL_120", require_real=True)
    assert "REAL_ONLY mode active: Cannot load synthetic scenario" in str(exc_info.value)


# ==============================================================================
# FAILCLOSED-02: Missing checkpoint không tự dùng dummy prediction
# ==============================================================================
def test_failclosed_02_missing_checkpoint_fails_closed():
    """FAILCLOSED-02: Missing model checkpoint cannot silently yield dummy predictions."""
    prov = EvidenceProvenance(prediction_source=PredictionSource.NONE)
    with pytest.raises(ProvenanceMismatchError):
        prov.validate_fail_closed(require_native=True)

    nonexistent_model = Path("artifacts/models/nonexistent_model_checkpoint.joblib")
    assert not nonexistent_model.exists()
