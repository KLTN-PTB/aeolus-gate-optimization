"""Validated public configuration for local, schedule-only inference."""
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

PRESETS = {"large": 150, "medium": 50, "small": 20}
MAX_UPLOAD_BYTES = 500 * 1024 * 1024
MAX_SELECTED_LEGS = 3000


class ExperimentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["benchmark", "montecarlo"]
    mode: Literal["quick", "research"] = "quick"
    algorithms: list[Literal["greedy", "cpsat", "sa", "hybrid"]] = Field(default_factory=lambda: ["greedy", "cpsat", "sa", "hybrid"], min_length=1, max_length=4)
    solver_profile: Literal["optimized", "baseline"] = "optimized"
    seed: int = Field(default=202601, ge=0, le=2147483640)
    scenarios: int | None = Field(default=None, ge=10, le=1000)
    time_limit_sec: float | None = Field(default=None, ge=1, le=120)
    plan_ids: list[str] = Field(default_factory=list, max_length=4)

    @model_validator(mode="after")
    def expand_defaults(self):
        self.algorithms = list(dict.fromkeys(self.algorithms))
        self.plan_ids = list(dict.fromkeys(self.plan_ids))
        if self.scenarios is None:
            self.scenarios = 500 if self.mode == "research" else 20
        if self.time_limit_sec is None:
            self.time_limit_sec = (30 if self.mode == "research" else 5) if self.kind == "benchmark" else (5 if self.mode == "research" else 2)
        return self


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    service_date: date
    airport: Literal["ATL"] = "ATL"
    preset: Literal["large", "medium", "small", "custom"] = "large"
    contact_gates: int = Field(default=150, ge=1, le=300)
    remote_gates: int = Field(default=0, ge=0, le=100)
    min_turnaround_min: int = Field(default=45, ge=15, le=180)
    default_dwell_min: int = Field(default=60, ge=15, le=720)
    buffer_min: int = Field(default=15, ge=0, le=120)
    solver: Literal["cpsat", "greedy", "hybrid"] = "cpsat"
    time_limit_sec: float = Field(default=30, ge=1, le=120)
    greedy_fallback: bool = True

    @model_validator(mode="after")
    def validate_assumptions(self):
        if self.service_date.year == 2024:
            raise ValueError("Năm 2024 được cách ly theo chính sách holdout của dự án.")
        if self.default_dwell_min < self.min_turnaround_min:
            raise ValueError("Thời gian chiếm dụng giả định phải ≥ thời gian quay đầu tối thiểu.")
        if self.preset != "custom" and self.contact_gates != PRESETS[self.preset]:
            raise ValueError("Số cổng không khớp quy mô; chọn Tùy chỉnh để nhập số cổng khác.")
        return self
