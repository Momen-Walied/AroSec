"""Temporal aggregation tests: windows, first/last seen, history, new_peer."""
from __future__ import annotations

from datetime import UTC, timedelta

from src.normalization import pipeline


def _edges(bundle, source, window=30):
    assets = pipeline.build_assets(bundle, source)
    return pipeline.build_edges(bundle, assets, source, window)


def test_window_grouping_and_counts(scenario_bundle, scenario_source):
    edges = _edges(scenario_bundle, scenario_source, 30)
    cam_nvr = [e for e in edges if e.src_asset_id.endswith("21") and e.dst_asset_id.endswith("10")]
    assert len(cam_nvr) == 2
    first, second = cam_nvr
    assert first.connection_count == 3
    assert second.connection_count == 1
    assert (second.window_start - first.window_start).total_seconds() == 30


def test_historical_count_and_new_peer(scenario_bundle, scenario_source):
    edges = _edges(scenario_bundle, scenario_source, 30)
    cam_nvr = sorted(
        (e for e in edges if e.src_asset_id.endswith("21") and e.dst_asset_id.endswith("10")),
        key=lambda e: e.window_start,
    )
    assert cam_nvr[0].is_new_peer is True
    assert cam_nvr[0].historical_connection_count == 0
    assert cam_nvr[1].is_new_peer is False
    assert cam_nvr[1].historical_connection_count == 3


def test_global_first_seen_across_windows(scenario_bundle, scenario_source):
    edges = _edges(scenario_bundle, scenario_source, 30)
    cam_nvr = sorted(
        (e for e in edges if e.src_asset_id.endswith("21") and e.dst_asset_id.endswith("10")),
        key=lambda e: e.window_start,
    )
    assert cam_nvr[0].first_seen == cam_nvr[1].first_seen
    assert cam_nvr[1].last_seen > cam_nvr[0].last_seen


def test_new_peer_appears_in_correct_window(scenario_bundle, scenario_source):
    edges = _edges(scenario_bundle, scenario_source, 30)
    cam_eng = [e for e in edges if e.src_asset_id.endswith("21") and e.dst_asset_id.endswith("33")]
    assert len(cam_eng) == 1
    assert cam_eng[0].is_new_peer is True
    assert cam_eng[0].historical_connection_count == 0


def test_no_future_leakage_in_history(scenario_bundle, scenario_source):
    edges = _edges(scenario_bundle, scenario_source, 30)
    cam_nvr_first = sorted(
        (e for e in edges if e.src_asset_id.endswith("21") and e.dst_asset_id.endswith("10")),
        key=lambda e: e.window_start,
    )[0]
    assert cam_nvr_first.historical_connection_count == 0
    assert cam_nvr_first.is_new_peer is True


def test_window_size_respected(scenario_bundle, scenario_source):
    edges = _edges(scenario_bundle, scenario_source, 60)
    # at 60s: obs at 0,10,20,35 collapse into one window; 60,80 into another
    cam_nvr = sorted(
        (e for e in edges if e.src_asset_id.endswith("21") and e.dst_asset_id.endswith("10")),
        key=lambda e: e.window_start,
    )
    assert cam_nvr[0].connection_count == 4
    assert (cam_nvr[0].window_end - cam_nvr[0].window_start) == timedelta(seconds=60)


def test_self_loops_excluded(scenario_bundle, scenario_source):
    edges = _edges(scenario_bundle, scenario_source, 30)
    assert all(e.src_asset_id != e.dst_asset_id for e in edges)


def test_multiprotocol_no_future_leakage(scenario_source):
    from datetime import datetime

    from src.datasets.base import RawBundle

    t0 = datetime(2024, 3, 2, 2, 13, 0, tzinfo=UTC)

    def mk(sec, proto):
        from datetime import timedelta

        from src.datasets.base import RawObservation

        return RawObservation(timestamp=t0 + timedelta(seconds=sec), src_ip="10.0.0.1",
                              dst_ip="10.0.0.2", network_protocol=proto, dst_port=443, bytes_out=100)

    bundle = RawBundle(observations=[mk(0, "TCP"), mk(10, "TCP"), mk(40, "ARP")])
    edges = _edges(bundle, scenario_source, 30)
    tcp = [e for e in edges if e.network_protocol == "TCP"][0]
    assert tcp.historical_connection_count == 0
    assert tcp.is_new_peer is True
    assert tcp.last_seen <= tcp.window_end
    for e in edges:
        assert e.last_seen <= e.window_end
        assert e.first_seen <= e.window_start
