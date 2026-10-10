"""End-to-end build: raw -> normalized parquet -> feature windows -> graph export."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from src.config import Settings, get_settings
from src.datasets.base import NormalizedData
from src.datasets.registry import get_adapter
from src.graph.export import export_neo4j_csv
from src.normalization import io
from src.normalization.features import build_edge_features, build_node_features


@dataclass
class BuildSummary:
    dataset_id: str
    window: str
    raw_observation_count: int = 0
    assets: int = 0
    edges: int = 0
    labels: int = 0
    campaigns: int = 0
    events: int = 0
    edge_features: int = 0
    node_features: int = 0
    outputs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _write_parquet_named(models, path: Path) -> Path:
    return io.write_parquet(io.models_to_frame(models), path)


def build_dataset(
    dataset_id: str,
    window: str = "30s",
    settings: Settings | None = None,
    synthetic: bool = False,
) -> BuildSummary:
    from src.config import WINDOW_SECONDS

    settings = settings or get_settings()
    window_seconds = WINDOW_SECONDS[window]

    if dataset_id == "cicapt_iiot" and synthetic:
        from src.datasets.cicapt import CicaptAdapter

        adapter = CicaptAdapter(settings=settings, synthetic=True)
    else:
        adapter = get_adapter(dataset_id)
    nd: NormalizedData = adapter.normalize(window_seconds)

    processed = settings.processed_dir
    summary = BuildSummary(
        dataset_id=dataset_id,
        window=window,
        raw_observation_count=nd.raw_observation_count,
        assets=len(nd.assets),
        edges=len(nd.edges),
        labels=len(nd.labels),
        campaigns=len(nd.campaigns),
        events=len(nd.events),
    )

    def emit(models, path: Path, sample_name: str | None = None) -> None:
        _write_parquet_named(models, path)
        summary.outputs.append(str(path.relative_to(settings.processed_dir.parent)))
        if sample_name and models:
            io.write_jsonl(models[:200], settings.samples_dir / sample_name)

    if nd.assets:
        emit(nd.assets, processed / "assets" / f"{dataset_id}.parquet", f"{dataset_id}_assets.jsonl")
    if nd.edges:
        emit(nd.edges, processed / "communication_edges" / f"{dataset_id}_edges_{window}.parquet",
             f"{dataset_id}_edges.jsonl")
    if nd.labels:
        emit(nd.labels, processed / "labels" / f"{dataset_id}.parquet")
    if nd.campaigns:
        emit(nd.campaigns, processed / "campaigns" / f"{dataset_id}.parquet")
    if nd.events:
        emit(nd.events, processed / "graph_events" / f"{dataset_id}.parquet", f"{dataset_id}_events.jsonl")

    if nd.edges:
        edge_feats = build_edge_features(nd.edges, adapter.source)
        node_feats = build_node_features(nd.edges, nd.assets, adapter.source, window_seconds)
        summary.edge_features = len(edge_feats)
        summary.node_features = len(node_feats)
        emit(edge_feats, processed / "features" / f"{dataset_id}_edge_features_{window}.parquet")
        emit(node_feats, processed / "features" / f"{dataset_id}_node_features_{window}.parquet")

    if nd.assets and nd.edges:
        nodes_path, rels_path = export_neo4j_csv(
            nd.assets, nd.edges, processed / "graph" / "neo4j", prefix=dataset_id
        )
        for p in (nodes_path, rels_path):
            summary.outputs.append(str(p.relative_to(settings.processed_dir.parent)))

    manifest_path = processed / "build_manifest.json"
    _update_manifest(manifest_path, summary)
    summary.outputs.append(str(manifest_path.relative_to(settings.processed_dir.parent)))
    return summary


def _update_manifest(path: Path, summary: BuildSummary) -> None:
    data = {}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("builds", {})
    entry = summary.to_dict()
    entry["built_at"] = datetime.now(UTC).isoformat()
    data["builds"][f"{summary.dataset_id}:{summary.window}"] = entry
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
