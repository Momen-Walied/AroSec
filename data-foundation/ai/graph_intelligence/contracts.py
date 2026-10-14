"""Temporal Graph Intelligence — versioned AI-layer contracts (above frozen v0.2).

These are framework-independent descriptions. The canonical persisted artifacts are
Parquet tables whose columns match these models (see ``ai/graph_intelligence/data/builder.py``).
Nothing here mutates the frozen Data Foundation v0.2 contracts or the existing
Edge/Node/Episode intelligence contracts.
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from enum import StrEnum

from pydantic import Field, field_validator

from src.schemas.base import ContractModel, SourceDataset, ensure_utc

from .config import DATASET_SCHEMA, TEMPORAL_GRAPH_SAMPLE_SCHEMA


class SplitName(StrEnum):
    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"


class ColdStartCategory(StrEnum):
    """Cold-start evaluation buckets (reported separately, never aggregated away)."""

    KNOWN_NODE_KNOWN_EDGE = "known_node_known_edge"
    KNOWN_NODE_NEW_EDGE = "known_node_new_edge"
    NEW_NODE_KNOWN_NETWORK = "new_node_known_network"
    NEW_NODE_NEW_EDGE = "new_node_new_edge"


def event_id_for(relationship_id: str, window_start: datetime) -> str:
    h = hashlib.sha1(f"{relationship_id}|{window_start.isoformat()}".encode()).hexdigest()[:20]
    return f"gte:{h}"


def sample_id_for(target_event_id: str, hops: int, lookback_seconds: int) -> str:
    h = hashlib.sha1(f"{target_event_id}|h{hops}|l{lookback_seconds}".encode()).hexdigest()[:20]
    return f"tgs:{h}"


def target_id_for(sample_id: str, label: int, horizon_windows: int) -> str:
    h = hashlib.sha1(f"{sample_id}|y{label}|hz{horizon_windows}".encode()).hexdigest()[:20]
    return f"tgt:{h}"


class NodeIndexEntry(ContractModel):
    """A node in the temporal asset-communication graph (identity is provisional)."""

    schema_version: str = DATASET_SCHEMA
    node_id: str
    node_index: int = Field(..., ge=0)
    first_seen: datetime
    last_seen: datetime
    identity_method: str | None = None
    identity_confidence: float | None = Field(None, ge=0.0, le=1.0)
    identity_is_provisional: bool = True
    dataset_source: SourceDataset

    @field_validator("first_seen", "last_seen")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)  # type: ignore[return-value]


class TemporalEdgeEvent(ContractModel):
    """One causal temporal edge observation: the canonical event-stream atom.

    All features are STRICTLY causal (derived from information available at/before this
    window by the frozen Edge Feature builder). ``is_new_relationship`` is true only for
    the first time a relationship is ever observed.
    """

    schema_version: str = DATASET_SCHEMA
    event_id: str
    relationship_id: str
    src_asset_id: str
    dst_asset_id: str
    window_start: datetime
    window_end: datetime
    is_new_relationship: bool = False
    new_peer: bool = False
    features: dict[str, float] = Field(default_factory=dict)
    dataset_source: SourceDataset

    @field_validator("window_start", "window_end")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)  # type: ignore[return-value]


class GraphTarget(ContractModel):
    """A learning target attached to a graph sample (self-supervised or scenario)."""

    schema_version: str = DATASET_SCHEMA
    target_id: str
    sample_id: str
    task: str
    relationship_id: str | None = None
    src_asset_id: str
    dst_asset_id: str
    as_of: datetime
    horizon_windows: int = Field(1, ge=1)
    label: int = Field(..., ge=0, le=1)
    label_kind: str = "next_edge"      # next_edge | scenario | negative
    scenario_id: str | None = None

    @field_validator("as_of")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)  # type: ignore[return-value]


class TemporalGraphSampleV1(ContractModel):
    """Causal ego/local temporal subgraph around a target edge-window at time ``as_of``.

    The sample references (does not embed) causal neighborhood members so the canonical
    representation stays framework-independent. ``neighbor_node_ids`` and
    ``causal_event_ids`` contain ONLY events with ``window_start < as_of`` (no future
    edges, no future neighbors).
    """

    schema_version: str = TEMPORAL_GRAPH_SAMPLE_SCHEMA
    sample_id: str
    representation: str = "ego_temporal_subgraph"
    target_event_id: str
    relationship_id: str
    src_asset_id: str
    dst_asset_id: str
    as_of: datetime

    hops: int = Field(..., ge=1)
    lookback_seconds: int = Field(..., ge=1)

    neighbor_node_ids: list[str] = Field(default_factory=list)
    causal_event_ids: list[str] = Field(default_factory=list)
    target_delta_s: float | None = None
    neighborhood_span_s: float | None = None

    split: SplitName = SplitName.TRAIN
    cold_start_category: ColdStartCategory = ColdStartCategory.KNOWN_NODE_KNOWN_EDGE

    identity_method: str | None = None
    identity_confidence: float | None = Field(None, ge=0.0, le=1.0)

    @field_validator("as_of")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)  # type: ignore[return-value]
