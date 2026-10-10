"""Feature-window schemas v0.1 (EdgeFeatureWindow, NodeFeatureWindow).

These are FACTUAL, leakage-safe derivations computed for a (window_start,
window_end] interval using ONLY observations strictly before window_end — and
for "novelty"/"new_peer"/"historical" style fields, only observations strictly
before window_start.

These tables are inputs for a future Temporal GNN / attack-path model.
NO model is trained here; NO predictions are stored here.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator, model_validator

from src.schemas.base import SCHEMA_VERSION, ContractModel, SourceDataset, ensure_utc


class EdgeFeatureWindow(ContractModel):
    """Per (src,dst) edge behaviour for one aggregation window."""

    schema_version: str = SCHEMA_VERSION

    src_asset_id: str
    dst_asset_id: str

    window_start: datetime
    window_end: datetime

    connections_count: int = Field(0, ge=0)
    packet_count: int = Field(0, ge=0)
    outbound_bytes: int = Field(0, ge=0)
    inbound_bytes: int = Field(0, ge=0)
    unique_destination_ports: int = Field(0, ge=0)

    edge_age_seconds: float | None = Field(None, ge=0.0)
    historical_connection_count: int = Field(0, ge=0)

    new_peer: bool = False
    src_unique_peer_count: int = Field(0, ge=0)
    src_new_peer_count: int = Field(0, ge=0)

    protocol_novelty: bool = False
    time_of_day_frequency: float | None = Field(None, ge=0.0, le=1.0)

    dataset_source: SourceDataset

    @field_validator("window_start", "window_end")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)  # type: ignore[return-value]

    @model_validator(mode="after")
    def _order(self) -> EdgeFeatureWindow:
        if self.window_start > self.window_end:
            raise ValueError("window_start must be <= window_end")
        return self


class NodeFeatureWindow(ContractModel):
    """Per-asset behaviour for one aggregation window (outbound-centric)."""

    schema_version: str = SCHEMA_VERSION

    asset_id: str
    window_start: datetime
    window_end: datetime

    connection_count: int = Field(0, ge=0)

    unique_destination_ips: int = Field(0, ge=0)
    unique_destination_assets: int = Field(0, ge=0)
    new_peer_count: int = Field(0, ge=0)
    unique_destination_ports: int = Field(0, ge=0)

    outbound_bytes: int = Field(0, ge=0)
    inbound_bytes: int = Field(0, ge=0)
    packet_count: int = Field(0, ge=0)

    fan_out: int = Field(0, ge=0)
    protocol_count: int = Field(0, ge=0)

    dns_query_rate: float | None = Field(None, ge=0.0)
    failed_connection_ratio: float | None = Field(None, ge=0.0, le=1.0)

    dataset_source: SourceDataset

    @field_validator("window_start", "window_end")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)  # type: ignore[return-value]

    @field_validator("asset_id")
    @classmethod
    def _asset_shape(cls, v: str) -> str:
        if not v.startswith("asset:"):
            raise ValueError("asset_id must start with 'asset:'")
        return v

    @model_validator(mode="after")
    def _order(self) -> NodeFeatureWindow:
        if self.window_start > self.window_end:
            raise ValueError("window_start must be <= window_end")
        return self
