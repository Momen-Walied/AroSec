"""CommunicationEdge schema v0.1 — the MOST IMPORTANT contract.

This represents FACTS only. AI-generated scores are FORBIDDEN here
(``attack_probability``, ``lateral_movement_probability``, ``edge_anomaly_score``,
``malicious_probability``). The AI layer produces those later, downstream.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator, model_validator

from src.schemas.base import (
    SCHEMA_VERSION,
    ContractModel,
    Direction,
    RelationshipType,
    SourceDataset,
    ensure_utc,
)

_FORBIDDEN_FIELDS = {
    "attack_probability",
    "lateral_movement_probability",
    "edge_anomaly_score",
    "malicious_probability",
    "anomaly_score",
    "risk_score",
}


class CommunicationEdge(ContractModel):
    schema_version: str = SCHEMA_VERSION

    edge_id: str = Field(..., description="Stable id over (src,dst,relationship,protocol).")
    src_asset_id: str
    dst_asset_id: str

    relationship_type: RelationshipType = RelationshipType.COMMUNICATES_WITH
    direction: Direction = Direction.UNKNOWN

    network_protocol: str | None = None       # e.g. TCP, UDP, ICMP, ARP
    application_protocol: str | None = None   # e.g. HTTP, MQTT, Modbus, CoAP

    src_port: int | None = Field(None, ge=0, le=65535)
    dst_port: int | None = Field(None, ge=0, le=65535)

    window_start: datetime
    window_end: datetime

    connection_count: int = Field(0, ge=0)
    packet_count: int = Field(0, ge=0)
    bytes_out: int = Field(0, ge=0)
    bytes_in: int = Field(0, ge=0)

    first_seen: datetime
    last_seen: datetime

    historical_connection_count: int = Field(0, ge=0)
    is_new_peer: bool = False

    evidence_sources: list[str] = Field(default_factory=list)
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    dataset_source: SourceDataset

    # ------------------------------------------------------------------ #
    @model_validator(mode="before")
    @classmethod
    def _reject_ai_fields(cls, data: object) -> object:
        if isinstance(data, dict):
            bad = _FORBIDDEN_FIELDS.intersection(data.keys())
            if bad:
                raise ValueError(
                    f"CommunicationEdge is a FACTS-only contract; forbidden AI fields: {sorted(bad)}"
                )
        return data

    @field_validator("edge_id")
    @classmethod
    def _id_shape(cls, v: str) -> str:
        if not v.startswith("edge:"):
            raise ValueError("edge_id must start with 'edge:'")
        return v

    @field_validator("src_asset_id", "dst_asset_id")
    @classmethod
    def _asset_shape(cls, v: str) -> str:
        if not v.startswith("asset:"):
            raise ValueError("src/dst asset ids must start with 'asset:'")
        return v

    @field_validator("window_start", "window_end", "first_seen", "last_seen")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)  # type: ignore[return-value]

    @field_validator("network_protocol", "application_protocol", mode="before")
    @classmethod
    def _proto_norm(cls, v: object) -> object:
        if isinstance(v, str):
            s = v.strip()
            if s.lower() in {"", "null", "nan", "none", "*", "-"}:
                return None
            return s.upper() if len(s) <= 6 else s
        return v

    @model_validator(mode="after")
    def _temporal_order(self) -> CommunicationEdge:
        if self.window_start > self.window_end:
            raise ValueError("window_start must be <= window_end")
        if self.first_seen > self.last_seen:
            raise ValueError("first_seen must be <= last_seen")
        if self.first_seen > self.window_start:
            raise ValueError("first_seen must be <= window_start")
        if self.last_seen > self.window_end:
            raise ValueError("last_seen must be <= window_end (no future leakage)")
        return self
