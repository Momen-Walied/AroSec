"""AI-derived NodeFeatureWindowV2 (above the frozen v0.2 contract).

Symmetric (inbound + outbound) entity behavior facts. Derived only from
CommunicationObservation v0.2; never modifies frozen schemas.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator

from src.schemas.base import SCHEMA_VERSION, ContractModel, SourceDataset, ensure_utc


class NodeFeatureWindowV2(ContractModel):
    schema_version: str = SCHEMA_VERSION

    asset_id: str
    window_start: datetime
    window_end: datetime

    outgoing_connection_count: int = Field(0, ge=0)
    incoming_connection_count: int = Field(0, ge=0)
    outgoing_packet_count: int = Field(0, ge=0)
    incoming_packet_count: int = Field(0, ge=0)
    outgoing_bytes: int = Field(0, ge=0)
    incoming_bytes: int = Field(0, ge=0)

    unique_outgoing_peers: int = Field(0, ge=0)
    unique_incoming_peers: int = Field(0, ge=0)
    new_outgoing_peer_count: int = Field(0, ge=0)
    new_incoming_peer_count: int = Field(0, ge=0)

    unique_outgoing_ports: int = Field(0, ge=0)
    unique_incoming_ports: int = Field(0, ge=0)

    outbound_protocol_count: int = Field(0, ge=0)
    inbound_protocol_count: int = Field(0, ge=0)
    outbound_app_protocol_count: int = Field(0, ge=0)
    inbound_app_protocol_count: int = Field(0, ge=0)

    protocol_novelty_count: int = Field(0, ge=0)
    port_novelty_count: int = Field(0, ge=0)

    fan_out: int = Field(0, ge=0)
    fan_in: int = Field(0, ge=0)

    relationship_creation_count: int = Field(0, ge=0)

    dataset_source: SourceDataset

    @field_validator("asset_id")
    @classmethod
    def _asset_shape(cls, v: str) -> str:
        if not v.startswith("asset:"):
            raise ValueError("asset_id must start with 'asset:'")
        return v

    @field_validator("window_start", "window_end")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)  # type: ignore[return-value]
