"""Pydantic models: telemetry validation (FR-09 / NFR-S2) and API request bodies."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Status = Literal["RUNNING", "IDLE", "STOPPED"]
Level = Literal["green", "yellow", "orange", "red"]
FaultKind = Literal["temp_ramp", "vib_spike", "stop", "anomaly"]


class TelemetryIn(BaseModel):
    """One telemetry sample. Invalid values (negative temperature, unknown status...) are rejected."""

    model_config = ConfigDict(extra="ignore")

    machine_id: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_\-]+$")
    ts: float | None = Field(default=None, ge=0)
    temperature: float = Field(ge=0, le=500)
    vibration: float = Field(ge=0, le=100)
    status: Status
    cycle_count: int = Field(ge=0)
    good_count: int | None = Field(default=None, ge=0)

    @field_validator("status", mode="before")
    @classmethod
    def _upper(cls, v):
        return v.upper() if isinstance(v, str) else v


class InjectFaultIn(BaseModel):
    machine_id: str = Field(min_length=1, max_length=40)
    kind: FaultKind
    duration_s: float | None = Field(default=None, ge=5, le=900)


class ClearFaultIn(BaseModel):
    machine_id: str | None = None


class SpeedIn(BaseModel):
    factor: float = Field(ge=1, le=10)


class AssignIn(BaseModel):
    technician: str = Field(min_length=1, max_length=80)


class ResolveIn(BaseModel):
    notes: str = Field(default="", max_length=2000)


class FeedbackIn(BaseModel):
    verdict: Literal["true_positive", "false_positive"]
    comment: str = Field(default="", max_length=1000)


class MaintenanceIn(BaseModel):
    machine_id: str = Field(min_length=1, max_length=40)
    alert_id: int | None = None
    action: str = Field(min_length=2, max_length=200)
    notes: str = Field(default="", max_length=2000)
    technician: str = Field(default="", max_length=80)
    status: Literal["open", "in_progress", "closed"] = "open"


class MaintenancePatch(BaseModel):
    action: str | None = Field(default=None, min_length=2, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)
    technician: str | None = Field(default=None, max_length=80)
    status: Literal["open", "in_progress", "closed"] | None = None


class OutageIn(BaseModel):
    enabled: bool
