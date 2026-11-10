"""Core dashboard models, contracts, configuration, and validation rules."""

from dashboard.core.config import DashboardConfig
from dashboard.core.contracts import (
    ProvenanceType,
    RiskCategory,
    UIJobState,
    ScenarioContext,
    FlightPredictionView,
    AircraftTurnView,
    GateTimelineView,
    SolverRunView,
    RobustnessView,
    ExperimentManifestView,
    ArtifactValidationResult,
)
from dashboard.core.status_mapping import StatusBadge, map_solver_status_to_badge
from dashboard.core.validation import (
    ScientificValidator,
    DataLeakageError,
    IncompatibleComparisonError,
)
from dashboard.core.state import (
    SessionStateKeys,
    get_initial_session_state,
)

__all__ = [
    "DashboardConfig",
    "ProvenanceType",
    "RiskCategory",
    "UIJobState",
    "ScenarioContext",
    "FlightPredictionView",
    "AircraftTurnView",
    "GateTimelineView",
    "SolverRunView",
    "RobustnessView",
    "ExperimentManifestView",
    "ArtifactValidationResult",
    "StatusBadge",
    "map_solver_status_to_badge",
    "ScientificValidator",
    "DataLeakageError",
    "IncompatibleComparisonError",
    "SessionStateKeys",
    "get_initial_session_state",
]
