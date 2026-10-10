"""v0.2 validation + metrics (schema re-validation, leakage, v0.1 loss quantification)."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from src.config import Settings, get_settings
from src.normalization import io
from src.schemas import (
    Asset,
    CommunicationObservation,
    CommunicationRelationship,
    EdgeFeatureWindowV2,
    GraphEvent,
)
from src.schemas.v2 import AssetIdentifierObservation


def _load(path: Path, model):
    return io.frame_to_models(io.read_parquet(path), model)


def validate_v2_dataset(dataset_id: str, window: str = "30s", settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    base = settings.processed_dir / "v2"
    errors: list[str] = []
    result: dict = {"dataset_id": dataset_id, "schema_errors": [], "tables": {}}

    spec = [
        ("assets", base / "assets" / f"{dataset_id}.parquet", Asset),
        ("asset_identifiers", base / "asset_identifiers" / f"{dataset_id}.parquet", AssetIdentifierObservation),
        ("relationships", base / "relationships" / f"{dataset_id}.parquet", CommunicationRelationship),
        ("observations", base / "communication_observations" / f"{dataset_id}_obs_{window}.parquet", CommunicationObservation),
        ("edge_features", base / "edge_features" / f"{dataset_id}_{window}.parquet", EdgeFeatureWindowV2),
        ("events", base / "graph_events" / f"{dataset_id}.parquet", GraphEvent),
    ]
    loaded: dict[str, list] = {}
    for name, path, model in spec:
        if not path.exists():
            continue
        try:
            rows = _load(path, model)
            loaded[name] = rows
            result["tables"][name] = len(rows)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{name}: {exc}")
    result["schema_errors"] = errors

    observations = loaded.get("observations", [])
    features = loaded.get("edge_features", [])
    assets = loaded.get("assets", [])

    method_dist: dict[str, int] = defaultdict(int)
    for a in assets:
        method_dist[str(a.identity_method)] += 1
    result["identity_method_distribution"] = dict(method_dist)

    # multi-protocol / multi-port pair-windows
    multi_proto = sum(1 for f in features if len(f.protocol_distribution) > 1)
    multi_port = sum(1 for f in features if f.unique_destination_ports > 1)
    result["pair_windows"] = len(features)
    result["multi_protocol_pair_windows"] = multi_proto
    result["multi_port_pair_windows"] = multi_port
    denom = max(len(features), 1)
    result["pct_multi_protocol_pair_windows"] = round(100 * multi_proto / denom, 2)
    result["pct_multi_port_pair_windows"] = round(100 * multi_port / denom, 2)

    # ports lost under v0.1 (min-port collapse): per (src,dst,proto,window) distinct ports - 1
    port_buckets: dict[tuple, set] = defaultdict(set)
    for o in observations:
        if o.dst_port is not None:
            port_buckets[(o.src_asset_id, o.dst_asset_id, o.network_protocol, o.window_start)].add(o.dst_port)
    result["ports_lost_under_v01"] = sum(max(0, len(v) - 1) for v in port_buckets.values())

    # temporal leakage: historical_connection_count must equal sum of strictly-earlier windows connections
    by_rel: dict[str, list] = defaultdict(list)
    for f in features:
        by_rel[f.relationship_id].append(f)
    violations = 0
    for _rel, rows in by_rel.items():
        rows.sort(key=lambda r: r.window_start)
        running = 0
        new_peer_seen = 0
        for f in rows:
            if f.historical_connection_count != running:
                violations += 1
            if f.new_peer:
                new_peer_seen += 1
            running += f.connections_count
        if new_peer_seen != 1:
            violations += 1
    result["temporal_leakage_violations"] = violations

    for f in features:
        if f.relationship_age_seconds is not None and f.relationship_age_seconds < 0:
            result["temporal_leakage_violations"] += 1

    return result
