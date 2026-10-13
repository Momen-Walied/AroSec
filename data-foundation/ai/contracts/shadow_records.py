"""Shadow runtime envelopes (ABOVE the frozen/model contracts).

Wraps EdgeFeatureWindowV2 + EdgeAnomalyResultV1 (edge) and NodeFeatureWindowV2 +
NodeAnomalyResultV1 (node) with runtime metadata. Never modifies the frozen contracts or
the model result contracts. Edge and Node records are kept SEPARATE (no fusion).
"""
from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator

from ai.contracts.edge_anomaly_result import EdgeAnomalyResultV1
from ai.contracts.node_anomaly_result import NodeAnomalyResultV1
from ai.episodes.contracts.behavioral_episode import BehavioralEpisodeV1
from ai.node_behavior.features.schema import NodeFeatureWindowV2
from src.schemas.base import ContractModel, ensure_utc
from src.schemas.v2 import EdgeFeatureWindowV2

SHADOW_RECORD_SCHEMA_VERSION = "shadow_inference_record_v1"
SHADOW_NODE_RECORD_SCHEMA_VERSION = "shadow_node_inference_record_v1"


class ShadowInferenceRecordV1(ContractModel):
    schema_version: str = SHADOW_RECORD_SCHEMA_VERSION
    runtime_version: str
    intelligence_type: str = "edge"

    received_at: datetime
    processed_at: datetime

    feature_window: EdgeFeatureWindowV2
    anomaly_result: EdgeAnomalyResultV1

    processing_latency_ms: float = Field(..., ge=0.0)

    late_record_count: int = Field(0, ge=0)
    identity_method: str | None = None
    identity_confidence: float | None = Field(None, ge=0.0, le=1.0)

    shadow_mode: bool = True

    @field_validator("intelligence_type")
    @classmethod
    def _edge_type(cls, v: str) -> str:
        if v != "edge":
            raise ValueError("intelligence_type must be 'edge' for ShadowInferenceRecordV1")
        return v

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


class ShadowNodeInferenceRecordV1(ContractModel):
    schema_version: str = SHADOW_NODE_RECORD_SCHEMA_VERSION
    runtime_version: str
    intelligence_type: str = "node"

    received_at: datetime
    processed_at: datetime

    feature_window: NodeFeatureWindowV2
    anomaly_result: NodeAnomalyResultV1

    processing_latency_ms: float = Field(..., ge=0.0)

    late_record_count: int = Field(0, ge=0)
    identity_method: str | None = None
    identity_confidence: float | None = Field(None, ge=0.0, le=1.0)

    shadow_mode: bool = True

    @field_validator("intelligence_type")
    @classmethod
    def _node_type(cls, v: str) -> str:
        if v != "node":
            raise ValueError("intelligence_type must be 'node' for ShadowNodeInferenceRecordV1")
        return v

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


ShadowRecord = ShadowInferenceRecordV1 | ShadowNodeInferenceRecordV1


class EpisodeShadowRecordV1(ContractModel):
    """Runtime envelope for a BehavioralEpisodeV1 (keeps runtime metadata out of the contract)."""

    schema_version: str = "episode_shadow_record_v1"
    runtime_version: str
    intelligence_type: str = "episode"

    processing_latency_ms: float = Field(0.0, ge=0.0)
    episode: BehavioralEpisodeV1

    # Runtime (event-time) watermark at which the runtime finalized the episode. This is
    # operational metadata and is deliberately NOT part of BehavioralEpisodeV1 semantics
    # (episode.end_time remains the last behavioral signal's event time).
    closed_at: datetime | None = None

    shadow_mode: bool = True

    @field_validator("intelligence_type")
    @classmethod
    def _ep_type(cls, v: str) -> str:
        if v != "episode":
            raise ValueError("intelligence_type must be 'episode'")
        return v

    @field_validator("shadow_mode")
    @classmethod
    def _shadow_only(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("shadow_mode must be true; this runtime cannot act on the network")
        return v
