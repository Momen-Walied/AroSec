"""Expanded temporal-integrity tests for the architecture review.

Covers: multi-protocol windows, out-of-order records, repeated relationships,
changing IPs, first/last seen, historical counts, new_peer/protocol novelty
uniqueness, window boundaries, and strict no-future-leakage.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.datasets.base import RawBundle, RawObservation
from src.normalization import pipeline
from src.normalization.features import build_edge_features
from src.schemas.base import SourceDataset

SRC = SourceDataset.SYNTHETIC
T0 = datetime(2024, 3, 2, 2, 13, 0, tzinfo=UTC)


def mk(sec: float, proto: str = "TCP", dport: int = 443, *, src: str = "10.0.0.1",
       dst: str = "10.0.0.2", out: int = 10, inb: int = 5, mac: str | None = None) -> RawObservation:
    return RawObservation(timestamp=T0 + timedelta(seconds=sec), src_ip=src, dst_ip=dst,
                          src_mac=mac, network_protocol=proto, dst_port=dport,
                          bytes_out=out, bytes_in=inb, packet_count=1)


def edges_of(obss: list[RawObservation], window: int = 30):
    bundle = RawBundle(observations=obss)
    assets = pipeline.build_assets(bundle, SRC)
    return pipeline.build_edges(bundle, assets, SRC, window), assets


def _sig(edges):
    return sorted((e.edge_id, e.window_start.isoformat(), e.historical_connection_count,
                   e.is_new_peer, e.last_seen.isoformat()) for e in edges)


def test_window_boundary_half_open():
    edges, _ = edges_of([mk(0), mk(30), mk(60)], 30)
    offsets = {(e.window_start - T0).total_seconds() for e in edges}
    assert offsets == {0.0, 30.0, 60.0}  # obs at boundary lands in the next window


def test_out_of_order_records_equivalent():
    base = [mk(0), mk(10), mk(70), mk(75, proto="UDP", dport=53)]
    import random

    shuffled = base[:]
    random.Random(3).shuffle(shuffled)
    e_sorted, _ = edges_of(base)
    e_shuf, _ = edges_of(shuffled)
    assert _sig(e_sorted) == _sig(e_shuf)


def test_historical_count_monotonic_and_correct():
    obss = [mk(0), mk(5), mk(40), mk(45), mk(80)]
    edges, _ = edges_of(obss, 30)
    pair = [e for e in edges if e.src_asset_id.endswith("1") and e.dst_asset_id.endswith("2")]
    pair.sort(key=lambda e: e.window_start)
    running = 0
    for e in pair:
        assert e.historical_connection_count == running
        running += e.connection_count
    assert pair[0].is_new_peer is True
    assert all(not e.is_new_peer for e in pair[1:])


def test_new_peer_true_exactly_once_per_pair():
    edges, _ = edges_of([mk(0), mk(40), mk(80), mk(120, proto="UDP", dport=53)])
    by_pair: dict[tuple[str, str], int] = {}
    for e in edges:
        key = (e.src_asset_id, e.dst_asset_id)
        by_pair[key] = by_pair.get(key, 0) + int(e.is_new_peer)
    assert all(count == 1 for count in by_pair.values())


def test_protocol_novelty_true_once_per_pair_protocol():
    obss = [mk(0, "TCP", 443), mk(40, "TCP", 443), mk(80, "UDP", 53), mk(120, "UDP", 53)]
    edges, assets = edges_of(obss, 30)
    feats = build_edge_features(edges, SRC)
    seen: dict[tuple[str, str, str], int] = {}
    for f in feats:
        edge = next(e for e in edges if e.src_asset_id == f.src_asset_id and
                    e.dst_asset_id == f.dst_asset_id and e.window_start == f.window_start)
        k = (f.src_asset_id, f.dst_asset_id, edge.network_protocol)
        seen[k] = seen.get(k, 0) + int(f.protocol_novelty)
    assert seen and all(v == 1 for v in seen.values())


def test_first_and_last_seen_invariants():
    edges, _ = edges_of([mk(0), mk(10), mk(70), mk(100)], 30)
    for e in edges:
        assert e.first_seen <= e.window_start
        assert e.last_seen <= e.window_end
        assert e.first_seen <= e.last_seen


def test_multiprotocol_same_window_no_cross_contamination():
    obss = [mk(0, "TCP", 443), mk(5, "UDP", 53), mk(10, "TCP", 445)]
    edges, _ = edges_of(obss, 30)
    assert {e.network_protocol for e in edges} == {"TCP", "UDP"}
    for e in edges:
        assert e.last_seen <= e.window_end
        assert e.historical_connection_count == 0
        assert e.is_new_peer is True


def test_no_future_leakage_after_extending():
    base = [mk(0), mk(10), mk(40)]
    extended = base + [mk(200), mk(400, proto="UDP", dport=53)]
    e_base, _ = edges_of(base, 30)
    e_ext, _ = edges_of(extended, 30)
    early = next(e for e in e_base if e.window_start == T0)
    early_ext = next(e for e in e_ext if e.window_start == T0)
    assert early.historical_connection_count == early_ext.historical_connection_count == 0
    assert early.is_new_peer == early_ext.is_new_peer is True


def test_same_mac_changing_ip_is_one_asset():
    bundle = RawBundle(observations=[
        mk(0, src="10.0.0.5", mac="aa:bb:cc:dd:ee:ff"),
        mk(60, src="10.0.0.6", mac="aa:bb:cc:dd:ee:ff"),
    ])
    assets = pipeline.build_assets(bundle, SRC)
    mac_assets = [a for a in assets if a.asset_id == "asset:synth:mac-aabbccddeeff"]
    assert len(mac_assets) == 1
    assert set(mac_assets[0].ip_addresses) == {"10.0.0.5", "10.0.0.6"}


def test_v01_two_phase_no_fragmentation():
    bundle = RawBundle(observations=[
        mk(0, src="192.168.1.50", mac="aa:aa:aa:aa:aa:01"),
        mk(3600, src="192.168.1.50", mac="aa:aa:aa:aa:aa:02"),
    ])
    assets = pipeline.build_assets(bundle, SRC)
    sharing = [a for a in assets if "192.168.1.50" in a.ip_addresses]
    assert len(sharing) == 1
    assert set(sharing[0].mac_addresses) == {"aa:aa:aa:aa:aa:01", "aa:aa:aa:aa:aa:02"}
