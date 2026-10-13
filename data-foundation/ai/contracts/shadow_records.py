"""Shadow runtime envelope (ABOVE the frozen/model contracts).

Wraps EdgeFeatureWindowV2 + EdgeAnomalyResultV1 with runtime metadata. It does NOT
modify EdgeAnomalyResultV1.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator

from ai.contracts.edge_anomaly_result import EdgeAnomalyResultV1
from src.schemas.base import ContractModel, ensure_utc
from src.schemas.v2 import EdgeFeatureWindowV2

SHADOW_RECORD_SCHEMA_VERSION = "shadow_inference_record_v1"


class ShadowInferenceRecordV1(ContractModel):
    schema_version: str = SHADOW_RECORD_SCHEMA_VERSION
    runtime_version: str

    received_at: datetime
    processed_at: datetime

    feature_window: EdgeFeatureWindowV2
    anomaly_result: EdgeAnomalyResultV1

    processing_latency_ms: float = Field(..., ge=0.0)

    late_record_count: int = Field(0, ge=0)
    identity_method: str | None = None
    identity_confidence: float | None = Field(None, ge=0.0, le=1.0)

    shadow_mode: bool = True

    @field_validator("received_at", "processed_at")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)  # type: ignore[return-value]

    @field_validator("shadow_mode")
    @classmethod
    def _shadow_only(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("shadow_mode must be true; this runtime cannot act on the network")
        return v
