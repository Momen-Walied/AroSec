"""Leakage-safe feature derivation tests."""
from __future__ import annotations

from src.datasets.base import RawBundle
from src.normalization import pipeline
from src.normalization.features import build_edge_features, build_node_features
from tests.conftest import obs


def _edges_features(bundle, source, window=30):
    assets = pipeline.build_assets(bundle, source)
    edges = pipeline.build_edges(bundle, assets, source, window)
    return assets, edges, build_edge_features(edges, source)


def test_new_peer_and_protocol_novelty(scenario_bundle, scenario_source):
    _, _, feats = _edges_features(scenario_bundle, scenario_source)
    cam_nvr = sorted(
        (f for f in feats if f.src_asset_id.endswith("21") and f.dst_asset_id.endswith("10")),
        key=lambda f: f.window_start,
    )
    assert cam_nvr[0].new_peer is True
    assert cam_nvr[0].protocol_novelty is True
    assert cam_nvr[1].new_peer is False
    assert cam_nvr[1].protocol_novelty is False


def test_edge_age_and_history(scenario_bundle, scenario_source):
    _, _, feats = _edges_features(scenario_bundle, scenario_source)
    cam_nvr = sorted(
        (f for f in feats if f.src_asset_id.endswith("21") and f.dst_asset_id.endswith("10")),
        key=lambda f: f.window_start,
    )
    assert cam_nvr[0].edge_age_seconds == 0.0
    assert cam_nvr[1].edge_age_seconds == 30.0
    assert cam_nvr[1].historical_connection_count == 3


def test_src_new_peer_count(scenario_bundle, scenario_source):
    _, _, feats = _edges_features(scenario_bundle, scenario_source)
    cam_eng = [f for f in feats if f.src_asset_id.endswith("21") and f.dst_asset_id.endswith("33")]
    assert len(cam_eng) == 1
    assert cam_eng[0].new_peer is True
    assert cam_eng[0].src_new_peer_count == 1
    assert cam_eng[0].src_unique_peer_count == 1


def test_time_of_day_frequency(scenario_bundle, scenario_source):
    _, _, feats = _edges_features(scenario_bundle, scenario_source)
    cam_nvr = sorted(
        (f for f in feats if f.src_asset_id.endswith("21") and f.dst_asset_id.endswith("10")),
        key=lambda f: f.window_start,
    )
    assert cam_nvr[0].time_of_day_frequency == 0.0
    assert cam_nvr[1].time_of_day_frequency == 1.0


def test_no_future_leakage(scenario_bundle, scenario_source):
    _, _, feats_before = _edges_features(scenario_bundle, scenario_source)

    extended = RawBundle(observations=list(scenario_bundle.observations) + [
        obs(200, "10.0.0.21", "10.0.0.10", dst_port=554, app="RTSP"),
        obs(400, "10.0.0.21", "10.0.0.99", dst_port=22),
    ])
    _, _, feats_after = _edges_features(extended, scenario_source)

    early_before = sorted(
        (f for f in feats_before if f.src_asset_id.endswith("21") and f.dst_asset_id.endswith("10")),
        key=lambda f: f.window_start,
    )
    early_after = sorted(
        (f for f in feats_after if f.src_asset_id.endswith("21") and f.dst_asset_id.endswith("10")
         and f.window_start == early_before[0].window_start),
        key=lambda f: f.window_start,
    )
    b, a = early_before[0], early_after[0]
    assert b.connections_count == a.connections_count
    assert b.historical_connection_count == a.historical_connection_count
    assert b.new_peer == a.new_peer
    assert b.src_new_peer_count == a.src_new_peer_count


def test_node_features_fan_out(scenario_bundle, scenario_source):
    assets = pipeline.build_assets(scenario_bundle, scenario_source)
    edges = pipeline.build_edges(scenario_bundle, assets, scenario_source, 30)
    node_feats = build_node_features(edges, assets, scenario_source, 30)
    cam = sorted(
        (f for f in node_feats if f.asset_id.endswith("21")),
        key=lambda f: f.window_start,
    )
    assert cam[0].fan_out == 1
    assert cam[-1].unique_destination_assets >= 1
