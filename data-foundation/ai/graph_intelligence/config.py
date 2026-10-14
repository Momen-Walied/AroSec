"""Temporal Graph Intelligence v1 configuration (provisional research values).

Values here are *hypotheses to be evaluated*, not production settings. They are recorded
in the dataset metadata so every dataset build is reproducible and versioned.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

GRAPH_INTELLIGENCE_VERSION = "temporal_graph_v1"
TEMPORAL_GRAPH_SAMPLE_SCHEMA = "temporal_graph_sample_v1"
DATASET_SCHEMA = "temporal_graph_dataset_v1"


@dataclass(frozen=True)
class GraphIntelligenceConfig:
    dataset_id: str = "unsw_iotraffic"
    window_label: str = "30s"
    window_seconds: int = 30

    # Feature versions are recorded so samples are reproducible against frozen inputs.
    edge_feature_version: str = "edge_feature_window_v2"
    node_feature_version: str = "node_feature_window_v2"

    # Sample representation (see docs/AI_TEMPORAL_GRAPH_INTELLIGENCE_V1_DESIGN.md).
    representation: str = "ego_temporal_subgraph"
    hops: int = 1                 # 1-hop; 2-hop collapses to the whole graph (hub effect)
    lookback_seconds: int = 3600  # 1h causal lookback (provisional; see graph_statistics.md)
    max_neighbors: int = 64
    max_events: int = 512

    # Chronological split, reused from Edge/Node Behavior (source of truth).
    train_fraction: float = 0.6
    validation_fraction: float = 0.2
    test_fraction: float = 0.2
    split_time_col: str = "window_start"

    # Link-prediction horizon (in observation windows) for next-edge targets.
    horizon_windows: int = 1

    # Negative sampling.
    negatives_per_positive: int = 5
    random_seed: int = 42

    def to_metadata(self) -> dict:
        return {"graph_intelligence_version": GRAPH_INTELLIGENCE_VERSION,
                "sample_schema": TEMPORAL_GRAPH_SAMPLE_SCHEMA,
                "dataset_schema": DATASET_SCHEMA, **asdict(self)}

    def validate(self) -> None:
        if abs(self.train_fraction + self.validation_fraction + self.test_fraction - 1.0) > 1e-9:
            raise ValueError("split fractions must sum to 1.0")
        if self.hops < 1:
            raise ValueError("hops must be >= 1")
        if self.lookback_seconds <= 0:
            raise ValueError("lookback_seconds must be positive")
        if self.horizon_windows < 1:
            raise ValueError("horizon_windows must be >= 1")
