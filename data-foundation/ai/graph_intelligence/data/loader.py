"""Load frozen/derived v0.2 tables for graph dataset construction (read-only)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config import get_settings

from ..config import GraphIntelligenceConfig


def _v2(name: str) -> Path:
    return get_settings().processed_dir / "v2" / name


def load_edge_features(cfg: GraphIntelligenceConfig) -> pd.DataFrame:
    p = _v2("edge_features") / f"{cfg.dataset_id}_{cfg.window_label}.parquet"
    df = pd.read_parquet(p)
    return df.sort_values(["window_start", "relationship_id"], kind="mergesort").reset_index(drop=True)


def load_relationships(cfg: GraphIntelligenceConfig) -> pd.DataFrame:
    return pd.read_parquet(_v2("relationships") / f"{cfg.dataset_id}.parquet")


def load_assets(cfg: GraphIntelligenceConfig) -> pd.DataFrame:
    return pd.read_parquet(_v2("assets") / f"{cfg.dataset_id}.parquet")


def load_observations(cfg: GraphIntelligenceConfig) -> pd.DataFrame:
    p = _v2("communication_observations") / f"{cfg.dataset_id}_obs_{cfg.window_label}.parquet"
    return pd.read_parquet(p).sort_values(["window_start", "observation_id"], kind="mergesort")


# Edge-feature numeric columns carried into the canonical temporal event stream.
EDGE_FEATURE_COLUMNS = [
    "connections_count", "packet_count", "outbound_bytes", "inbound_bytes",
    "unique_destination_ports", "unique_source_ports",
    "relationship_age_seconds", "historical_connection_count",
    "src_unique_peer_count", "src_new_peer_count",
    "protocol_novelty_count", "protocol_novelty_ratio", "port_novelty_count",
]
