"""Data Foundation v0.2 contracts (additive — v0.1 contracts remain available).

Adds:
  * AssetIdentifierObservation — time-bounded identity bindings
  * CommunicationRelationship  — persistent logical edge (window-independent id)
  * CommunicationObservation   — lossless per-window, per-protocol, per-port facts
  * EdgeFeatureWindowV2        — ML-oriented wide view per relationship + window
"""
from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator, model_validator

from src.schemas.base import (
    SCHEMA_VERSION,
    ContractModel,
    Direction,
    IdentifierType,
    RelationshipType,
    SourceDataset,
    ensure_utc,
)


class AssetIdentifierObservation(ContractModel):
    schema_version: str = SCHEMA_VERSION

    asset_id: str
    identifier_type: IdentifierType
    identifier_value: str

    valid_from: datetime | None = None
    valid_to: datetime | None = None

    evidence_source: str
    confidence: float = Field(0.5, ge=0.0, le=1.0)

    evidence_id: str | None = None
    source_record_id: str | None = None
    dataset_source: SourceDataset

    @field_validator("asset_id")
    @classmethod
    def _asset_shape(cls, v: str) -> str:
        if not v.startswith("asset:"):
            raise ValueError("asset_id must start with 'asset:'")
        return v

    @field_validator("valid_from", "valid_to")
    @classmethod
    def _utc(cls, v: datetime | None) -> datetime | None:
        return ensure_utc(v)

    @model_validator(mode="after")
    def _order(self) -> AssetIdentifierObservation:
        if self.valid_from and self.valid_to and self.valid_from > self.valid_to:
            raise ValueError("valid_from must be <= valid_to")
        return self


class CommunicationRelationship(ContractModel):
    schema_version: str = SCHEMA_VERSION

    relationship_id: str
    src_asset_id: str
    dst_asset_id: str
    relationship_type: RelationshipType = RelationshipType.COMMUNICATES_WITH

    first_seen: datetime
    last_seen: datetime

    total_observation_count: int = Field(1, ge=0)
    total_connection_count: int = Field(0, ge=0)

    direction: Direction = Direction.UNKNOWN

    evidence_sources: list[str] = Field(default_factory=list)
    evidence_id: str | None = None
    source_record_id: str | None = None
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    dataset_source: SourceDataset

    @field_validator("relationship_id")
    @classmethod
    def _rel_shape(cls, v: str) -> str:
        if not v.startswith("rel:"):
            raise ValueError("relationship_id must start with 'rel:'")
        return v

    @field_validator("src_asset_id", "dst_asset_id")
    @classmethod
    def _asset_shape(cls, v: str) -> str:
        if not v.startswith("asset:"):
            raise ValueError("src/dst asset ids must start with 'asset:'")
        return v

    @field_validator("first_seen", "last_seen")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)  # type: ignore[return-value]

    @model_validator(mode="after")
    def _order(self) -> CommunicationRelationship:
        if self.first_seen > self.last_seen:
            raise ValueError("first_seen must be <= last_seen")
        return self


class CommunicationObservation(ContractModel):
    schema_version: str = SCHEMA_VERSION

    observation_id: str
    relationship_id: str
    src_asset_id: str
    dst_asset_id: str

    window_start: datetime
    window_end: datetime

    network_protocol: str | None = None
    application_protocol: str | None = None

    src_port: int | None = Field(None, ge=0, le=65535)
    dst_port: int | None = Field(None, ge=0, le=65535)

    connection_count: int = Field(0, ge=0)
    packet_count: int = Field(0, ge=0)
    bytes_out: int = Field(0, ge=0)
    bytes_in: int = Field(0, ge=0)

    direction: Direction = Direction.UNKNOWN

    evidence_source: str = "normalization"
    evidence_id: str | None = None
    source_record_id: str | None = None
    dataset_source: SourceDataset

    @field_validator("observation_id")
    @classmethod
    def _obs_shape(cls, v: str) -> str:
        if not v.startswith("obs:"):
            raise ValueError("observation_id must start with 'obs:'")
        return v

    @field_validator("relationship_id")
    @classmethod
    def _rel_shape(cls, v: str) -> str:
        if not v.startswith("rel:"):
            raise ValueError("relationship_id must start with 'rel:'")
        return v

    @field_validator("src_asset_id", "dst_asset_id")
    @classmethod
    def _asset_shape(cls, v: str) -> str:
        if not v.startswith("asset:"):
            raise ValueError("src/dst asset ids must start with 'asset:'")
        return v

    @field_validator("window_start", "window_end")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)  # type: ignore[return-value]

    @field_validator("network_protocol", "application_protocol", mode="before")
    @classmethod
    def _na(cls, v: object) -> object:
        if isinstance(v, str) and v.strip().lower() in {"", "null", "nan", "none", "*", "-"}:
            return None
        return v

    @model_validator(mode="after")
    def _order(self) -> CommunicationObservation:
        if self.window_start > self.window_end:
            raise ValueError("window_start must be <= window_end")
        return self


class EdgeFeatureWindowV2(ContractModel):
    """Wide, leakage-safe edge features per (relationship, window).

    Distribution denominators:
      * protocol_distribution[p] / application_protocol_distribution[a]
          -> share is value / connections_count (this window).
      * protocol_novelty_ratio = protocol_novelty_count / distinct protocols in window.
    All history/novelty fields use observations STRICTLY before window_start.
    """

    schema_version: str = SCHEMA_VERSION

    relationship_id: str
    src_asset_id: str
    dst_asset_id: str

    window_start: datetime
    window_end: datetime

    connections_count: int = Field(0, ge=0)
    packet_count: int = Field(0, ge=0)
    outbound_bytes: int = Field(0, ge=0)
    inbound_bytes: int = Field(0, ge=0)

    protocol_distribution: dict[str, int] = Field(default_factory=dict)
    application_protocol_distribution: dict[str, int] = Field(default_factory=dict)

    observed_destination_ports: list[int] = Field(default_factory=list)
    observed_source_ports: list[int] = Field(default_factory=list)
    unique_destination_ports: int = Field(0, ge=0)
    unique_source_ports: int = Field(0, ge=0)

    relationship_age_seconds: float | None = Field(None, ge=0.0)
    historical_connection_count: int = Field(0, ge=0)

    new_peer: bool = False

    src_unique_peer_count: int = Field(0, ge=0)
    src_new_peer_count: int = Field(0, ge=0)

    protocol_novelty_count: int = Field(0, ge=0)
    protocol_novelty_ratio: float | None = Field(None, ge=0.0, le=1.0)
    port_novelty_count: int = Field(0, ge=0)

    dataset_source: SourceDataset

    @field_validator("relationship_id")
    @classmethod
    def _rel_shape(cls, v: str) -> str:
        if not v.startswith("rel:"):
            raise ValueError("relationship_id must start with 'rel:'")
        return v

    @field_validator("window_start", "window_end")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)  # type: ignore[return-value]

    @model_validator(mode="after")
    def _order(self) -> EdgeFeatureWindowV2:
        if self.window_start > self.window_end:
            raise ValueError("window_start must be <= window_end")
        return self
