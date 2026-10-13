"""Analyst feedback contract (future-facing; NOT a training-label pipeline)."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import field_validator

from src.schemas.base import ContractModel, ensure_utc

ANALYST_FEEDBACK_SCHEMA_VERSION = "analyst_feedback_v1"


class AnalystVerdict(StrEnum):
    BENIGN_EXPECTED = "benign_expected"
    BENIGN_UNUSUAL = "benign_unusual"
    SUSPICIOUS = "suspicious"
    CONFIRMED_SECURITY_INCIDENT = "confirmed_security_incident"
    UNKNOWN = "unknown"


class AnalystFeedbackV1(ContractModel):
    schema_version: str = ANALYST_FEEDBACK_SCHEMA_VERSION
    inference_id: str
    verdict: AnalystVerdict
    analyst_reason: str | None = None
    timestamp: datetime

    @field_validator("timestamp")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)  # type: ignore[return-value]
