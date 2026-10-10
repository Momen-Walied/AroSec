"""Parquet/JSONL round-trip tests."""
from __future__ import annotations

from datetime import UTC, datetime

from src.normalization import io, pipeline
from src.schemas import Asset, GraphEvent
from src.schemas.base import SourceDataset


def test_asset_roundtrip(tmp_path):
    asset = Asset(
        asset_id="asset:synth:host-cam-01",
        ip_addresses=["10.0.0.21", "10.0.0.22"],
        mac_addresses=["aa:bb:cc:dd:ee:ff"],
        hostname="cam-01",
        first_seen=datetime(2024, 3, 1, tzinfo=UTC),
        last_seen=datetime(2024, 3, 2, tzinfo=UTC),
        evidence_sources=["synth:flows"],
        dataset_source=SourceDataset.SYNTHETIC,
    )
    path = io.write_parquet(io.models_to_frame([asset]), tmp_path / "assets.parquet")
    restored = io.frame_to_models(io.read_parquet(path), Asset)
    assert len(restored) == 1
    assert restored[0].asset_id == asset.asset_id
    assert sorted(restored[0].ip_addresses) == ["10.0.0.21", "10.0.0.22"]
    assert restored[0].first_seen == asset.first_seen


def test_graph_events_timestamps_not_nat(scenario_bundle, scenario_source, tmp_path):
    assets = pipeline.build_assets(scenario_bundle, scenario_source)
    edges = pipeline.build_edges(scenario_bundle, assets, scenario_source, 30)
    events = pipeline.build_graph_events(assets, edges, scenario_source)
    path = io.write_parquet(io.models_to_frame(events), tmp_path / "events.parquet")
    df = io.read_parquet(path)
    assert df["timestamp"].isna().sum() == 0
    restored = io.frame_to_models(df, GraphEvent)
    assert all(e.timestamp is not None for e in restored)


def test_mixed_precision_timestamps_preserved(scenario_bundle, scenario_source, tmp_path):
    assets = pipeline.build_assets(scenario_bundle, scenario_source)
    edges = pipeline.build_edges(scenario_bundle, assets, scenario_source, 30)
    events = pipeline.build_graph_events(assets, edges, scenario_source)
    path = io.write_parquet(io.models_to_frame(events), tmp_path / "e.parquet")
    df = io.read_parquet(path)
    assert not df.empty
    assert df["timestamp"].notna().all()
