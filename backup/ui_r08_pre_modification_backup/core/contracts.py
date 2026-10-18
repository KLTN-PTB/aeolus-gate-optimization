"""Typed View Models and Data Contracts for the Aeolus Dashboard.

These view models decouple the presentation layer from backend internal
structures while preserving full numeric precision, provenances, and validation.
"""

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class ProvenanceType(str, Enum):
    """Data provenance classification (strictly preserved across layers)."""

    NATIVE_INFERENCE = "NATIVE_INFERENCE"
    PRECOMPUTED_PREDICTION = "PRECOMPUTED_PREDICTION"
    SYNTHETIC_SIMULATION = "SYNTHETIC_SIMULATION"
    SCHEDULE_BASELINE = "SCHEDULE_BASELINE"


class RiskCategory(str, Enum):
    """Operational turnaround slack and delay risk classification."""

    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class UIJobState(str, Enum):
    """Frontend lifecycle job state (decoupled from mathematical solver status)."""

    INIT_LOADING = "INIT_LOADING"
    READY_IDLE = "READY_IDLE"
    PARAM_STALE = "PARAM_STALE"
    SOLVING_LIVE = "SOLVING_LIVE"
    SOLVE_SUCCESS = "SOLVE_SUCCESS"
    FALLBACK_USED = "FALLBACK_USED"
    ERROR_BOUNDARY = "ERROR_BOUNDARY"
    # Canonical lifecycle states (Task R02-D)
    IDLE = "IDLE"
    VALIDATING = "VALIDATING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    STALE_RESULT = "STALE_RESULT"
    INCOMPATIBLE_RESULT = "INCOMPATIBLE_RESULT"


@dataclass(frozen=True)
class ScenarioDataIdentity:
    """Authoritative canonical scenario dataset identity (Task R02-B)."""

    scenario_id: str
    scenario_digest: str
    flight_count: int
    gate_count: int
    remote_capacity: int = 1
    hub_iata: str = "ATL"
    dataset_version: str = "BTS_2023_V1"
    generator_seed: Optional[int] = None
    schema_version: str = "2.0"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProblemIdentity:
    """Mathematical optimization problem identity (Task R02-B)."""

    scenario_digest: str
    objective_version: str = "P10_STANDARD"
    w_pref: float = 10.0
    w_remote: float = 200.0
    w_conflict: float = 1000.0
    buffer_time_min: int = 15
    allow_overflow: bool = True
    finite_remote_capacity: bool = True
    prediction_source: str = "SCHEDULE_BASELINE"
    schema_version: str = "2.0"

    @property
    def problem_digest(self) -> str:
        """Deterministic digest of mathematical problem formulation."""
        import hashlib
        import json
        payload = {
            "scenario_digest": self.scenario_digest,
            "objective_version": self.objective_version,
            "w_pref": float(self.w_pref),
            "w_remote": float(self.w_remote),
            "w_conflict": float(self.w_conflict),
            "buffer_time_min": int(self.buffer_time_min),
            "allow_overflow": bool(self.allow_overflow),
            "finite_remote_capacity": bool(self.finite_remote_capacity),
            "prediction_source": self.prediction_source,
            "schema_version": self.schema_version,
        }
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["problem_digest"] = self.problem_digest
        return d


@dataclass(frozen=True)
class ExecutionIdentity:
    """Execution configuration identity for a specific solver run (Task R02-B)."""

    problem_digest: str
    requested_solver: str
    effective_solver: str
    formulation: str = "sparse_interval"
    time_limit_sec: float = 30.0
    warm_start: bool = False
    solver_seed: Optional[int] = 42
    fallback_policy: str = "greedy_fallback"
    run_id: str = ""
    schema_version: str = "2.0"

    @property
    def execution_digest(self) -> str:
        """Deterministic digest of solver execution configuration."""
        import hashlib
        import json
        payload = {
            "problem_digest": self.problem_digest,
            "requested_solver": str(self.requested_solver).lower(),
            "effective_solver": str(self.effective_solver),
            "formulation": self.formulation,
            "time_limit_sec": float(self.time_limit_sec),
            "warm_start": bool(self.warm_start),
            "solver_seed": self.solver_seed,
            "fallback_policy": self.fallback_policy,
            "schema_version": self.schema_version,
        }
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["execution_digest"] = self.execution_digest
        return d


@dataclass(frozen=True)
class ScenarioContext:
    """View model representing the active operational scenario context."""

    scenario_id: str
    hub_iata: str
    flight_count: int
    gate_count: int
    remote_capacity: int
    scenario_hash: str
    scenario_digest: Optional[str] = None
    provenance: ProvenanceType = ProvenanceType.SCHEDULE_BASELINE
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        if not self.scenario_id:
            raise ValueError("scenario_id cannot be empty")
        if self.flight_count < 0:
            raise ValueError(f"flight_count must be non-negative: {self.flight_count}")
        if self.gate_count < 0:
            raise ValueError(f"gate_count must be non-negative: {self.gate_count}")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FlightPredictionView:
    """View model for flight delay predictions in planning mode.

    Enforces zero-data-leakage: ground-truth historical actual delay is forbidden.
    Supports both Inbound (ARR) and Outbound (DEP) flights under Dual-Core ML.
    """

    flight_id: str
    carrier: str = "N/A"
    origin: str = "N/A"
    destination: str = "N/A"
    sched_arr_time_min: Optional[int] = None
    predicted_arr_delay_min: float = 0.0
    lower_bound_delay_min: Optional[float] = None
    upper_bound_delay_min: Optional[float] = None
    confidence_score: Optional[float] = None
    risk_category: RiskCategory = RiskCategory.LOW
    top_shap_features: Dict[str, float] = field(default_factory=dict)
    provenance: ProvenanceType = ProvenanceType.PRECOMPUTED_PREDICTION
    schema_version: str = "1.0"
    flight_direction: str = "ARR"
    prediction_model: Optional[str] = None
    prediction_cutoff_utc: Optional[str] = None
    probability_delay_15: Optional[float] = None
    predictive_quantiles: Dict[str, float] = field(default_factory=dict)
    scheduled_time_min: Optional[int] = None
    predicted_time_min: Optional[int] = None

    def __post_init__(self) -> None:
        if not self.flight_id:
            raise ValueError("flight_id cannot be empty")
        if self.sched_arr_time_min is not None and not (0 <= self.sched_arr_time_min <= 2880):  # Allow up to 48 hours for cross-midnight
            raise ValueError(
                f"sched_arr_time_min must be between 0 and 2880: {self.sched_arr_time_min}"
            )
        if self.scheduled_time_min is not None and not (0 <= self.scheduled_time_min <= 2880):
            raise ValueError(
                f"scheduled_time_min must be between 0 and 2880: {self.scheduled_time_min}"
            )
        if self.confidence_score is not None and not (0.0 <= self.confidence_score <= 1.0):
            raise ValueError(
                f"confidence_score must be between 0.0 and 1.0: {self.confidence_score}"
            )
        if self.probability_delay_15 is not None and not (0.0 <= self.probability_delay_15 <= 1.0):
            raise ValueError(
                f"probability_delay_15 must be between 0.0 and 1.0: {self.probability_delay_15}"
            )

    @property
    def effective_scheduled_time_min(self) -> Optional[int]:
        return self.scheduled_time_min if self.scheduled_time_min is not None else self.sched_arr_time_min

    @property
    def effective_predicted_time_min(self) -> Optional[int]:
        if self.predicted_time_min is not None:
            return self.predicted_time_min
        if self.effective_scheduled_time_min is not None:
            return int(self.effective_scheduled_time_min + round(self.predicted_arr_delay_min))
        return None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["risk_category"] = self.risk_category.value
        d["provenance"] = self.provenance.value
        return d


@dataclass(frozen=True)
class AircraftTurnView:
    """View model for an aircraft turnaround connecting an inbound leg to an outbound leg."""

    turn_id: str
    inbound_flight_id: str
    outbound_flight_id: str
    tail_number: str
    aircraft_type: str
    sched_turn_window_min: int
    min_turn_time_min: int
    sched_slack_min: int
    inbound_delay_absorbed_min: float
    remaining_slack_min: float
    propagated_outbound_delay_min: float
    slack_risk_index: RiskCategory
    gate_occupancy_start_min: int
    gate_occupancy_end_min: int
    buffer_min: int = 15
    provenance: ProvenanceType = ProvenanceType.PRECOMPUTED_PREDICTION
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        if not self.turn_id:
            raise ValueError("turn_id cannot be empty")
        if self.gate_occupancy_end_min < self.gate_occupancy_start_min:
            raise ValueError("gate_occupancy_end_min cannot be earlier than start_min")

    @property
    def total_blocked_end_min(self) -> int:
        """Total time gate is blocked including the 15-minute release buffer."""
        return self.gate_occupancy_end_min + self.buffer_min

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["slack_risk_index"] = self.slack_risk_index.value
        d["provenance"] = self.provenance.value
        return d


@dataclass(frozen=True)
class GateTimelineView:
    """View model for a single aircraft gate assignment interval."""

    assignment_id: str
    flight_id: str
    gate_id: str
    concourse: str
    start_min: int
    end_min: int
    buffer_min: int = 15
    is_reassigned: bool = False
    is_remote: bool = False
    has_conflict: bool = False
    provenance: ProvenanceType = ProvenanceType.PRECOMPUTED_PREDICTION
    carrier: str = "DL"
    flight_number: str = ""
    nominal_gate_id: Optional[str] = None
    resource_type: str = "CONTACT_GATE"
    scenario_id: str = "SCEN_P09_CANONICAL_120"
    prediction_source: str = "NATIVE_DUAL_CORE"
    gate_out_min: Optional[int] = None
    gate_release_min: Optional[int] = None
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        if not self.flight_id:
            raise ValueError("flight_id cannot be empty")
        if not self.gate_id:
            raise ValueError("gate_id cannot be empty")
        if self.end_min < self.start_min:
            raise ValueError(f"end_min ({self.end_min}) cannot be < start_min ({self.start_min})")

    @property
    def actual_gate_out_min(self) -> int:
        """Physical aircraft gate-out / pushback time."""
        return self.gate_out_min if self.gate_out_min is not None else self.end_min

    @property
    def actual_gate_release_min(self) -> int:
        """Gate release time including 15-minute separation buffer."""
        return self.gate_release_min if self.gate_release_min is not None else (self.actual_gate_out_min + self.buffer_min)

    @property
    def occupancy_interval(self) -> Tuple[int, int]:
        """Half-open aircraft physical presence interval [start, end)."""
        return (self.start_min, self.actual_gate_out_min)

    @property
    def total_blocked_interval(self) -> Tuple[int, int]:
        """Total gate blocked interval including buffer [start, release)."""
        return (self.start_min, self.actual_gate_release_min)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["provenance"] = self.provenance.value
        return d


@dataclass(frozen=True)
class SolverRunView:
    """View model for an optimization solver solution run."""

    solver_name: str
    scenario_id: str
    objective_value: Optional[float]
    decision_cost: float
    reporting_cost: float
    reassignment_count: int
    remote_gate_count: int
    conflict_count: int
    solve_time_sec: float
    status: str
    termination_reason: str
    is_optimal_proven: bool
    optimality_gap: Optional[float] = None
    assignments: List[GateTimelineView] = field(default_factory=list)
    solver_config: Dict[str, Any] = field(default_factory=dict)
    provenance: ProvenanceType = ProvenanceType.PRECOMPUTED_PREDICTION
    schema_version: str = "2.0"
    requested_solver: Optional[str] = None
    effective_solver: Optional[str] = None
    fallback_used: bool = False
    problem_digest: Optional[str] = None
    execution_digest: Optional[str] = None
    run_id: Optional[str] = None
    verifier_diagnostics: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        if not self.solver_name:
            raise ValueError("solver_name cannot be empty")
        if self.solve_time_sec < 0:
            raise ValueError("solve_time_sec cannot be negative")
        if self.requested_solver is None:
            object.__setattr__(self, "requested_solver", self.solver_name)
        if self.effective_solver is None:
            object.__setattr__(self, "effective_solver", self.solver_name)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["provenance"] = self.provenance.value
        d["assignments"] = [a.to_dict() for a in self.assignments]
        return d


@dataclass(frozen=True)
class RobustnessView:
    """View model for Monte Carlo robustness mode evaluations (Mode A, B, C)."""

    mode_name: str
    scenario_count: int
    mean_cost: Optional[float] = None
    median_cost: Optional[float] = None
    std_cost: Optional[float] = None
    cvar_95_cost: Optional[float] = None
    physical_conflict_rate: Optional[float] = None  # Finding D1: actual spatial collisions
    static_invalidation_rate: Optional[float] = None  # Finding D1: schedule slot mismatches
    mean_reassignments: Optional[float] = None
    mean_remote_usage: Optional[float] = None
    is_deployable: bool = True  # Mode C is non-deployable oracle
    academic_notes: str = ""  # Finding D2: greedy equivalence notes
    provenance: ProvenanceType = ProvenanceType.PRECOMPUTED_PREDICTION
    schema_version: str = "1.0"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["provenance"] = self.provenance.value
        return d


@dataclass(frozen=True)
class ExperimentManifestView:
    """View model for system run provenance and experiment reproducibility."""

    manifest_id: str
    timestamp_iso: str
    scenario_hash: str
    model_inbound_hash: str
    model_outbound_hash: str
    objective_version: str
    capacity_policy: str
    solver_seed: int
    artifact_paths: Dict[str, str] = field(default_factory=dict)
    schema_version: str = "1.0"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ArtifactValidationResult:
    """Result of an artifact schema, type, and boundary validation pass."""

    artifact_path: str
    is_valid: bool
    row_count: int
    columns_found: List[str]
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    schema_version: str = "1.0"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
