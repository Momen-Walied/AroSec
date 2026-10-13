"""AI Edge Behavior contract — EdgeAnomalyResultV1.

Lives ABOVE the frozen Data Foundation v0.2 contract. It never mutates v0.2 data.
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from src.schemas.base import ContractModel, ensure_utc

EDGE_ANOMALY_RESULT_SCHEMA_VERSION = "edge_anomaly_result_v1"


class Severity(StrEnum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AnomalyReason(ContractModel):
    code: str
    contribution: float = Field(..., ge=0.0, le=1.0)
    detail: str | None = None


class IdentityQuality(ContractModel):
    identity_method: str | None = None
    identity_confidence: float | None = Field(None, ge=0.0, le=1.0)
    identity_is_provisional: bool = True


class EdgeAnomalyResultV1(ContractModel):
    schema_version: str = EDGE_ANOMALY_RESULT_SCHEMA_VERSION
    model_version: str

    relationship_id: str
    window_start: datetime
    window_end: datetime

    anomaly_score: float = Field(..., ge=0.0, le=1.0)
    severity: Severity

    reasons: list[AnomalyReason] = Field(default_factory=list)
    feature_contributions: dict[str, float] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    identity_quality: IdentityQuality = Field(default_factory=IdentityQuality)

    inference_timestamp: datetime

    @field_validator("relationship_id")
    @classmethod
    def _rel_shape(cls, v: str) -> str:
        if not v.startswith("rel:"):
            raise ValueError("relationship_id must start with 'rel:'")
        return v

    @field_validator("window_start", "window_end", "inference_timestamp")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)  # type: ignore[return-value]

    @model_validator(mode="after")
    def _order(self) -> EdgeAnomalyResultV1:
        if self.window_start > self.window_end:
            raise ValueError("window_start must be <= window_end")
        return self
