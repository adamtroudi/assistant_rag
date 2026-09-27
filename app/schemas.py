from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain import SUPPORTED_MACHINE_IDS

MachineId = Literal["EPI_PumpStation1", "EPI_PumpStation2", "EPI_PickAndPlace"]


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=2, max_length=4000)
    machine_ids: list[MachineId] | None = Field(default=None, min_length=1)
    horizon_days: Literal[7, 15, 30] | None = None
    forecast_id: str | None = Field(default=None, min_length=1, max_length=200)
    forecast_results: "PlatformForecastInput | list[PlatformForecastInput] | None" = None

    @field_validator("machine_ids")
    @classmethod
    def unique_machine_ids(cls, value: list[MachineId] | None) -> list[MachineId] | None:
        if value is not None and len(set(value)) != len(value):
            raise ValueError("machine_ids ne doit pas contenir de doublons")
        return value


class SourceRef(BaseModel):
    source_id: str
    title: str | None = None
    url: str | None = None
    archive_path: str | None = None
    locator: str | None = None


class Citation(BaseModel):
    chunk_id: str
    machine_id: str | None
    source: SourceRef


class ForecastRef(BaseModel):
    forecast_id: str
    forecast_version: str
    machine_id: str
    horizon_days: Literal[7, 15, 30]
    start_utc: datetime
    end_utc: datetime
    quantity: str
    unit: Literal["kW", "kWh"]


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    forecast_refs: list[ForecastRef] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def validate_supported_machine_id(value: str) -> str:
    if value not in SUPPORTED_MACHINE_IDS:
        raise ValueError(f"machine hors périmètre: {value}")
    return value


class PlatformForecastInput(BaseModel):
    """Raw XGBoost output produced by the host platform."""

    model_config = ConfigDict(extra="allow")

    machine: str = Field(min_length=1, max_length=200)
    value_col: str = Field(min_length=1, max_length=100)
    frequency_minutes: int = Field(gt=0, le=1440)
    horizon_days: Literal[7, 15, 30]
    n_points: int = Field(gt=0)
    forecast: list[dict[str, Any]] = Field(min_length=1)
    unit: Literal["W", "kW", "kWh"] | None = None
    timezone: str | None = None
    forecast_id: str | None = Field(default=None, min_length=1, max_length=200)
    forecast_version: str | None = Field(default=None, min_length=1, max_length=100)


ChatRequest.model_rebuild()
