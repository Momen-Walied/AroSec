"""BehavioralEpisodeV1 contract (AI layer, above the frozen v0.2 and model contracts).

A Behavioral Episode is a temporally and relationally coherent group of Edge/Node anomaly
signals. It is NOT a Security Incident and carries NO attack semantics.
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from src.schemas.base import ContractModel, ensure_utc

BEHAVIORAL_EPISODE_SCHEMA_VERSION = "behavioral_episode_v1"

_FORBIDDEN = {"attack_probability", "attack_stage", "attacker", "victim", "objective", "attack_path"}


class EpisodeStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class EvidenceStrength(StrEnum):
    WEAK = "WEAK"
    MODERATE = "MODERATE"
    STRONG = "STRONG"


class BehavioralEpisodeV1(ContractModel):
    schema_version: str = BEHAVIORAL_EPISODE_SCHEMA_VERSION

    episode_id: str
    start_time: datetime
    end_time: datetime
    duration_seconds: float = Field(..., ge=0.0)
    status: EpisodeStatus = EpisodeStatus.CLOSED

    involved_asset_ids: list[str] = Field(default_factory=list)
    relationship_ids: list[str] = Field(default_factory=list)

    edge_signal_ids: list[str] = Field(default_factory=list)
    node_signal_ids: list[str] = Field(default_factory=list)
    edge_signal_count: int = Field(0, ge=0)
    node_signal_count: int = Field(0, ge=0)

    max_edge_score: float | None = Field(None, ge=0.0, le=1.0)
    max_node_score: float | None = Field(None, ge=0.0, le=1.0)

    signal_reason_codes: list[str] = Field(default_factory=list)
    evidence_families: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)

    identity_methods: list[str] = Field(default_factory=list)
    minimum_identity_confidence: float | None = Field(None, ge=0.0, le=1.0)

    primary_asset_id: str | None = None
    episode_severity: str
    evidence_strength: EvidenceStrength

    context: dict = Field(default_factory=dict)
    summary: dict = Field(default_factory=dict)

    created_at: datetime
    closed_at: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def _reject_attack_fields(cls, data: object) -> object:
        if isinstance(data, dict):
            bad = _FORBIDDEN.intersection(data.keys())
            if bad:
                raise ValueError(f"BehavioralEpisodeV1 forbids attack semantics: {sorted(bad)}")
        return data

    @field_validator("episode_id")
    @classmethod
    def _id_shape(cls, v: str) -> str:
        if not v.startswith("episode:"):
            raise ValueError("episode_id must start with 'episode:'")
        return v

    @field_validator("involved_asset_ids")
    @classmethod
    def _asset_shape(cls, v: list[str]) -> list[str]:
        for a in v:
            if not a.startswith("asset:"):
                raise ValueError(f"asset id must start with 'asset:': {a}")
        return v

    @field_validator("relationship_ids")
    @classmethod
    def _rel_shape(cls, v: list[str]) -> list[str]:
        for r in v:
            if not r.startswith("rel:"):
                raise ValueError(f"relationship id must start with 'rel:': {r}")
        return v

    @field_validator("start_time", "end_time", "created_at", "closed_at")
    @classmethod
    def _utc(cls, v: datetime | None) -> datetime | None:
        return ensure_utc(v)

    @model_validator(mode="after")
    def _order(self) -> BehavioralEpisodeV1:
        if self.start_time > self.end_time:
            raise ValueError("start_time must be <= end_time")
        return self
