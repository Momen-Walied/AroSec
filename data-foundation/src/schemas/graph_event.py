"""GraphEvent schema v0.1 — an append-only fact about how the graph changed.

Generated deterministically from normalized temporal data. Ordering is
(``timestamp``, ``graph_version``); ``graph_version`` is a monotonically
increasing counter so a point-in-time view ("what did the graph look like at T")
is a simple filter: ``graph_version <= v``.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator, model_validator

from src.schemas.base import (
    SCHEMA_VERSION,
    ContractModel,
    GraphEventType,
    SourceDataset,
    ensure_utc,
)


class GraphEvent(ContractModel):
    schema_version: str = SCHEMA_VERSION

    event_id: str
    timestamp: datetime
    event_type: GraphEventType

    asset_id: str | None = None
    edge_id: str | None = None
    observation_id: str | None = None
    src_asset_id: str | None = None
    dst_asset_id: str | None = None

    graph_version: int = Field(0, ge=0)
    evidence_source: str = "normalization"
    dataset_source: SourceDataset

    @field_validator("event_id")
    @classmethod
    def _id_shape(cls, v: str) -> str:
        if not v.startswith("evt:"):
            raise ValueError("event_id must start with 'evt:'")
        return v

    @field_validator("timestamp")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)  # type: ignore[return-value]

    @model_validator(mode="after")
    def _required_refs(self) -> GraphEvent:
        et = self.event_type
        asset_events = {
            GraphEventType.ASSET_ADDED,
            GraphEventType.ASSET_UPDATED,
            GraphEventType.IDENTITY_UPDATED,
            GraphEventType.IDENTITY_BINDING_ADDED,
            GraphEventType.IDENTITY_BINDING_EXPIRED,
        }
        relationship_events = {
            GraphEventType.EDGE_ADDED,
            GraphEventType.EDGE_UPDATED,
            GraphEventType.EDGE_REMOVED,
            GraphEventType.RELATIONSHIP_ADDED,
            GraphEventType.RELATIONSHIP_UPDATED,
            GraphEventType.COMMUNICATION_OBSERVED,
        }
        if et in asset_events and not self.asset_id:
            raise ValueError(f"{et} requires asset_id")
        if et in relationship_events:
            if not self.edge_id or not self.src_asset_id or not self.dst_asset_id:
                raise ValueError(f"{et} requires edge_id, src_asset_id and dst_asset_id")
        return self
