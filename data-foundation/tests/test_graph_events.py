"""Graph-event ordering + point-in-time view tests."""
from __future__ import annotations

from datetime import UTC, datetime

from src.graph.temporal_graph import TemporalGraph
from src.normalization import pipeline
from src.schemas.base import GraphEventType


def _build(bundle, source):
    assets = pipeline.build_assets(bundle, source)
    edges = pipeline.build_edges(bundle, assets, source, 30)
    events = pipeline.build_graph_events(assets, edges, source)
    labels = pipeline.build_labels(bundle, assets, source)
    return assets, edges, events, labels


def test_events_sorted_and_versioned(scenario_bundle, scenario_source):
    _, _, events, _ = _build(scenario_bundle, scenario_source)
    timestamps = [e.timestamp for e in events]
    assert timestamps == sorted(timestamps)
    assert [e.graph_version for e in events] == list(range(len(events)))


def test_edge_added_before_edge_updated(scenario_bundle, scenario_source):
    _, _, events, _ = _build(scenario_bundle, scenario_source)
    added = [e for e in events if e.event_type == GraphEventType.EDGE_ADDED]
    updated = [e for e in events if e.event_type == GraphEventType.EDGE_UPDATED]
    assert added
    assert updated
    cam_nvr_added = min(
        (e for e in added if (e.edge_id or "").find("21|") >= 0), key=lambda e: e.timestamp
    )
    cam_nvr_updated = min(
        (e for e in updated if (e.edge_id or "").find("21|") >= 0), key=lambda e: e.timestamp, default=None
    )
    assert cam_nvr_updated is None or cam_nvr_updated.timestamp >= cam_nvr_added.timestamp


def test_snapshot_at_time(scenario_bundle, scenario_source):
    assets, edges, events, labels = _build(scenario_bundle, scenario_source)
    graph = TemporalGraph(assets, edges, events, labels)
    early = datetime(2024, 3, 2, 2, 13, 5, tzinfo=UTC)
    snap = graph.snapshot(early)
    assert snap["assets"]
    late = datetime(2024, 3, 2, 2, 30, 0, tzinfo=UTC)
    assert len(graph.snapshot(late)["edges"]) >= len(snap["edges"])


def test_required_queries(scenario_bundle, scenario_source):
    assets, edges, events, labels = _build(scenario_bundle, scenario_source)
    graph = TemporalGraph(assets, edges, events, labels)
    cam = next(a.asset_id for a in assets if a.asset_id.endswith("21"))
    _ = next(a.asset_id for a in assets if a.asset_id.endswith("33"))

    peers = graph.neighbors_during(cam, datetime(2024, 3, 2, 2, 12, tzinfo=UTC),
                                   datetime(2024, 3, 2, 2, 20, tzinfo=UTC))
    assert len(peers) >= 2

    paths = graph.paths_between(cam, next(a.asset_id for a in assets if a.asset_id.endswith("7")))
    assert any(cam in p for p in paths)

    assert graph.lateral_movement_nodes()
