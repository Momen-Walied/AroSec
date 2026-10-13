"""Node Behavior result contract (AI layer, above the frozen v0.2 contract)."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, field_validator

from src.schemas.base import ContractModel, ensure_utc

NODE_ANOMALY_RESULT_SCHEMA_VERSION = "node_anomaly_result_v1"


class NodeSeverity(StrEnum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class NodeAnomalyReason(ContractModel):
    code: str
    contribution: float = Field(..., ge=0.0, le=1.0)
    detail: str | None = None


class NodeIdentityQuality(ContractModel):
    identity_method: str | None = None
    identity_confidence: float | None = Field(None, ge=0.0, le=1.0)
    identity_is_provisional: bool = True


class NodeAnomalyResultV1(ContractModel):
    schema_version: str = NODE_ANOMALY_RESULT_SCHEMA_VERSION
    model_version: str

    asset_id: str
    window_start: datetime
    window_end: datetime

    anomaly_score: float = Field(..., ge=0.0, le=1.0)
    severity: NodeSeverity

    reasons: list[NodeAnomalyReason] = Field(default_factory=list)
    feature_contributions: dict[str, float] = Field(default_factory=dict)

    identity_method: str | None = None
    identity_confidence: float | None = Field(None, ge=0.0, le=1.0)

    evidence_refs: list[str] = Field(default_factory=list)
    inference_timestamp: datetime

    @field_validator("asset_id")
    @classmethod
    def _asset_shape(cls, v: str) -> str:
        if not v.startswith("asset:"):
            raise ValueError("asset_id must start with 'asset:'")
        return v

    @field_validator("window_start", "window_end", "inference_timestamp")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)  # type: ignore[return-value]
