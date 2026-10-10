"""v0.2 tests: identity, lossless observations, features, events, v0.1 compat."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.compat.v01 import to_v01_edges
from src.datasets.base import RawBundle, RawObservation
from src.identity.resolver_v2 import TwoPhaseResolver
from src.normalization import build_v2
from src.schemas.base import SourceDataset

SRC = SourceDataset.SYNTHETIC
T0 = datetime(2024, 3, 2, 2, 13, 0, tzinfo=UTC)


def mk(sec, *, proto="TCP", app=None, sport=None, dport=None, src="10.0.0.21",
       dst="10.0.0.10", mac=None, host=None, dev=None, out=100, inb=20, packets=2) -> RawObservation:
    return RawObservation(timestamp=T0 + timedelta(seconds=sec), src_ip=src, dst_ip=dst,
                          src_mac=mac, src_hostname=host, src_device=dev, src_port=sport,
                          dst_port=dport, network_protocol=proto, application_protocol=app,
                          bytes_out=out, bytes_in=inb, packet_count=packets)


def build(obss, window=30):
    bundle = RawBundle(observations=list(obss))
    resolver = TwoPhaseResolver()
    resolved = resolver.resolve(bundle, SRC)
    records = build_v2.canonical_records(bundle, resolver, SRC)
    rels = build_v2.build_relationships(records, SRC)
    obs = build_v2.build_observations(records, SRC, window)
    feats = build_v2.build_edge_features_v2(rels, obs, SRC)
    events = build_v2.build_events_v2(resolved.assets, resolved.bindings, rels, obs, SRC)
    return resolved, rels, obs, feats, events


def test_transitive_identifier_merging():
    obss = [
        mk(0, src="10.0.0.5", mac="aa:bb:cc:dd:ee:ff", dst="10.0.0.9"),
        mk(10, src="10.0.0.6", host="cam-01", dst="10.0.0.9"),
        mk(20, src="10.0.0.7", mac="aa:bb:cc:dd:ee:ff", host="cam-01", dst="10.0.0.9"),
    ]
    resolved, *_ = build(obss)
    cam = [a for a in resolved.assets if a.asset_id == "asset:synth:mac-aabbccddeeff"]
    assert len(cam) == 1
    assert cam[0].hostname == "cam-01"
    assert str(cam[0].identity_method) == "multi_signal"
    assert set(cam[0].ip_addresses) == {"10.0.0.5", "10.0.0.6", "10.0.0.7"}


def test_ip_reuse_non_overlapping_distinct_assets():
    obss = [
        mk(0, src="192.168.1.50", mac="aa:aa:aa:aa:aa:01", dst="10.0.0.9"),
        mk(3600, src="192.168.1.50", mac="aa:aa:aa:aa:aa:02", dst="10.0.0.9"),
    ]
    resolved, *_ = build(obss)
    sharing = [a for a in resolved.assets if "192.168.1.50" in a.ip_addresses]
    assert len(sharing) == 2
    assert {str(a.identity_method) for a in sharing} == {"mac_based"}
    ip_bindings = [b for b in resolved.bindings if b.identifier_value == "192.168.1.50"]
    assert len(ip_bindings) == 2
    assert ip_bindings[0].valid_from != ip_bindings[1].valid_from


def test_multiple_protocols_preserved():
    obss = [mk(0, proto="TCP", app="TLS", dport=443),
            mk(5, proto="TCP", app="SMB", dport=445),
            mk(10, proto="UDP", app="DNS", dport=53)]
    _, _, obs, feats, _ = build(obss)
    assert len(obs) == 3
    assert {(o.network_protocol, o.application_protocol, o.dst_port) for o in obs} == {
        ("TCP", "TLS", 443), ("TCP", "SMB", 445), ("UDP", "DNS", 53)}
    f = feats[0]
    assert f.protocol_distribution == {"TCP": 2, "UDP": 1}
    assert f.application_protocol_distribution == {"TLS": 1, "SMB": 1, "DNS": 1}


def test_multiple_destination_ports_preserved():
    obss = [mk(0, proto="TCP", dport=443), mk(5, proto="TCP", dport=445)]
    _, _, obs, feats, _ = build(obss)
    assert len(obs) == 2
    assert feats[0].observed_destination_ports == [443, 445]
    assert feats[0].unique_destination_ports == 2


def test_port_scan_preserved():
    ports = list(range(1000, 1019))
    obss = [mk(i, proto="TCP", dport=p) for i, p in enumerate(ports)]
    _, _, obs, feats, _ = build(obss)
    assert len(obs) == 19
    assert feats[0].unique_destination_ports == 19
    assert feats[0].observed_destination_ports == sorted(ports)


def test_deterministic_relationship_and_observation_ids():
    obss = [mk(0, proto="TCP", app="TLS", dport=443), mk(5, proto="UDP", app="DNS", dport=53)]
    _, rels_a, obs_a, _, _ = build(obss)
    _, rels_b, obs_b, _, _ = build(list(reversed(obss)))
    assert [r.relationship_id for r in rels_a] == [r.relationship_id for r in rels_b]
    assert sorted(o.observation_id for o in obs_a) == sorted(o.observation_id for o in obs_b)


def test_observation_ordering():
    obss = [mk(70, proto="UDP", dport=53), mk(0, proto="TCP", dport=443), mk(35, proto="TCP", dport=445)]
    _, _, obs, _, _ = build(obss, 30)
    starts = [o.window_start for o in obs]
    assert starts == sorted(starts)


def test_relationship_first_last_and_totals():
    obss = [mk(0), mk(10), mk(45), mk(90)]
    _, rels, obs, _, _ = build(obss, 30)
    rel = rels[0]
    assert rel.first_seen == T0
    assert rel.last_seen == T0 + timedelta(seconds=90)
    assert rel.total_connection_count == 4
    assert rel.total_observation_count == 3


def test_features_no_future_leakage():
    base = [mk(0), mk(10), mk(40)]
    extended = base + [mk(200), mk(400, proto="UDP", dport=53)]
    _, _, _, feats_base, _ = build(base, 30)
    _, _, _, feats_ext, _ = build(extended, 30)
    early = next(f for f in feats_base if f.window_start == T0)
    early_ext = next(f for f in feats_ext if f.window_start == T0)
    assert early.historical_connection_count == early_ext.historical_connection_count == 0
    assert early.new_peer == early_ext.new_peer is True


def test_historical_monotonic():
    _, _, _, feats, _ = build([mk(0), mk(40), mk(80)], 30)
    feats.sort(key=lambda f: f.window_start)
    running = 0
    for f in feats:
        assert f.historical_connection_count == running
        running += f.connections_count


def test_protocol_novelty_counts():
    obss = [mk(0, proto="TCP", dport=443), mk(40, proto="TCP", dport=443),
            mk(80, proto="UDP", dport=53), mk(120, proto="UDP", dport=53)]
    _, _, _, feats, _ = build(obss, 30)
    feats.sort(key=lambda f: f.window_start)
    assert feats[0].protocol_novelty_count == 1
    assert feats[1].protocol_novelty_count == 0
    assert feats[2].protocol_novelty_count == 1
    assert feats[2].protocol_novelty_ratio == 1.0


def test_port_novelty_counts():
    obss = [mk(0, proto="TCP", dport=443), mk(40, proto="TCP", dport=443),
            mk(80, proto="TCP", dport=8080)]
    _, _, _, feats, _ = build(obss, 30)
    feats.sort(key=lambda f: f.window_start)
    assert feats[0].port_novelty_count == 1
    assert feats[1].port_novelty_count == 0
    assert feats[2].port_novelty_count == 1


def test_half_open_windows():
    _, _, obs, _, _ = build([mk(0), mk(30), mk(60)], 30)
    offsets = {(o.window_start - T0).total_seconds() for o in obs}
    assert offsets == {0.0, 30.0, 60.0}


def test_events_v2_include_new_types():
    _, _, _, _, events = build([mk(0), mk(40), mk(60, proto="UDP", dport=53)])
    types = {str(e.event_type) for e in events}
    assert {"ASSET_ADDED", "RELATIONSHIP_ADDED", "RELATIONSHIP_UPDATED",
            "COMMUNICATION_OBSERVED"} <= types
    versions = [e.graph_version for e in events]
    assert versions == sorted(versions)
    assert versions == list(range(len(events)))


def test_v01_compat_is_lossy_for_ports():
    obss = [mk(0, proto="TCP", app="TLS", dport=443), mk(5, proto="TCP", app="SMB", dport=445)]
    resolved, rels, obs, _, _ = build(obss)
    v01 = to_v01_edges(rels, obs, SRC, 30)
    assert len(v01) == 1
    assert v01[0].dst_port == 443
    assert v01[0].application_protocol in {"SMB", "TLS"}


def test_app_protocol_normalized_before_keying():
    obss = [mk(0, proto="TCP", app="", dport=443), mk(5, proto="TCP", app=None, dport=443)]
    _, _, obs, _, _ = build(obss)
    assert len(obs) == 1
    assert obs[0].application_protocol is None


def test_identity_binding_expired_on_ip_handover():
    obss = [
        mk(0, src="192.168.1.50", mac="aa:aa:aa:aa:aa:01", dst="10.0.0.9"),
        mk(3600, src="192.168.1.50", mac="aa:aa:aa:aa:aa:02", dst="10.0.0.9"),
    ]
    _, _, _, _, events = build(obss)
    types = [str(e.event_type) for e in events]
    assert "IDENTITY_BINDING_ADDED" in types
    assert "IDENTITY_BINDING_EXPIRED" in types
