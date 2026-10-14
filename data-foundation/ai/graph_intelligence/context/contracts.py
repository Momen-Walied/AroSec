"""Graph-Context Edge Anomaly v1 (Phase 4B) — AI-layer contracts.

Above the frozen v0.2 contract; never mutates frozen schemas or the Edge/Node/Episode
intelligence contracts. No attack semantics are present (no attack probability, stage,
attacker, victim, or objective).
"""
from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator

from src.schemas.base import ContractModel, ensure_utc

GRAPH_CONTEXT_FEATURES_SCHEMA = "graph_context_edge_features_v1"
GRAPH_CONTEXT_RESULT_SCHEMA = "graph_context_anomaly_result_v1"


class GraphContextEdgeFeaturesV1(ContractModel):
    """Causal local temporal graph-context features for one target edge-window.

    Every field is computed from graph state observable strictly before the target
    ``window_start`` (see docs/TEMPORAL_GRAPH_LEAKAGE_MODEL.md). ``NEW INFORMATION`` fields
    are not derivable from the Edge/Node local feature windows; they are flagged in
    ``feature_overlap_audit.md``.
    """

    schema_version: str = GRAPH_CONTEXT_FEATURES_SCHEMA
    relationship_id: str
    src_asset_id: str
    dst_asset_id: str
    window_start: datetime
    window_end: datetime

    lookback_seconds: int = Field(..., gt=0)
    hops: int = Field(..., ge=1)
    neighborhood_size: int = Field(0, ge=0)

    # A. source structure
    source_out_degree_recent: int = Field(0, ge=0)
    source_in_degree_recent: int = Field(0, ge=0)
    source_new_out_neighbors_recent: int = Field(0, ge=0)
    source_new_in_neighbors_recent: int = Field(0, ge=0)
    source_degree_delta: int = 0
    source_neighbor_set_change: float = Field(0.0, ge=0.0, le=1.0)

    # B. destination structure
    destination_out_degree_recent: int = Field(0, ge=0)
    destination_in_degree_recent: int = Field(0, ge=0)
    destination_new_in_neighbors_recent: int = Field(0, ge=0)
    destination_degree_delta: int = 0
    destination_neighbor_set_change: float = Field(0.0, ge=0.0, le=1.0)

    # C. relational structure
    historical_peer_overlap: int = Field(0, ge=0)
    source_neighbor_similarity: float = Field(0.0, ge=0.0, le=1.0)
    destination_neighbor_similarity: float = Field(0.0, ge=0.0, le=1.0)
    common_neighbor_count: int = Field(0, ge=0)
    causal_jaccard: float = Field(0.0, ge=0.0, le=1.0)
    causal_adamic_adar: float = Field(0.0, ge=0.0)

    # D. local temporal change
    relationships_created_in_local_neighborhood: int = Field(0, ge=0)
    local_edge_event_rate: float = Field(0.0, ge=0.0)
    local_new_edge_rate: float = Field(0.0, ge=0.0)
    local_degree_change_rate: float = Field(0.0, ge=0.0)

    # E. structural novelty
    target_structural_novelty: float = Field(0.0, ge=0.0, le=1.0)
    source_peer_set_novelty: float = Field(0.0, ge=0.0, le=1.0)
    destination_peer_set_novelty: float = Field(0.0, ge=0.0, le=1.0)

    # F. chain / local motif (causally observable only)
    chain_count: int = Field(0, ge=0)
    chain_support: float = Field(0.0, ge=0.0, le=1.0)

    # hub context (structural, not an asset id)
    src_degree_bucket: str = "low"
    dst_degree_bucket: str = "low"
    hub_involved: bool = False

    @field_validator("window_start", "window_end")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)  # type: ignore[return-value]


class GraphContextAnomalyResultV1(ContractModel):
    """Independent graph-context anomaly result. NOT fused with Edge Behavior."""

    schema_version: str = GRAPH_CONTEXT_RESULT_SCHEMA
    model_version: str

    relationship_id: str
    window_start: datetime
    window_end: datetime

    graph_context_score: float = Field(..., ge=0.0, le=1.0)
    reason_codes: list[str] = Field(default_factory=list)
    feature_contributions: dict[str, float] = Field(default_factory=dict)

    neighborhood_size: int = Field(0, ge=0)
    lookback_seconds: int = Field(..., gt=0)

    hub_context: dict = Field(default_factory=dict)   # {src_degree, dst_degree, hub_involved}
    identity_method: str | None = None
    identity_confidence: float | None = Field(None, ge=0.0, le=1.0)

    evidence_refs: list[str] = Field(default_factory=list)
    inference_timestamp: datetime

    @field_validator("window_start", "window_end", "inference_timestamp")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return ensure_utc(v)  # type: ignore[return-value]
