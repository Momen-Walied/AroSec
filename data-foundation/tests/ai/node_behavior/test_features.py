"""Node feature building: inbound/outbound aggregation, novelty, determinism."""
from __future__ import annotations

from ai.node_behavior.features.builder import (
    build_node_feature_matrix,
    build_node_feature_windows_v2,
)
from tests.ai.node_behavior._helpers import T0, by_asset, obs  # noqa: F401


def test_inbound_outbound_aggregation():
    seq = [
        obs(0, "asset:a", "asset:b", dport=443),
        obs(0, "asset:a", "asset:c", proto="TCP", dport=445),
        obs(0, "asset:b", "asset:a", dport=80),
    ]
    windows = build_node_feature_windows_v2(seq)
    a = by_asset(windows, "asset:a", 0)
    assert a.outgoing_connection_count == 2
    assert a.incoming_connection_count == 1
    assert a.unique_outgoing_peers == 2
    assert a.unique_incoming_peers == 1
    assert a.fan_out == 2 and a.fan_in == 1
    assert a.unique_outgoing_ports == 2
    assert a.unique_incoming_ports == 1


def test_new_peer_history_is_causal():
    seq = [
        obs(0, "asset:a", "asset:b", dport=443),
        obs(1, "asset:a", "asset:b", dport=443),
        obs(1, "asset:a", "asset:c", dport=445),
    ]
    windows = build_node_feature_windows_v2(seq)
    a0 = by_asset(windows, "asset:a", 0)
    a1 = by_asset(windows, "asset:a", 1)
    assert a0.new_outgoing_peer_count == 1          # b is new
    assert a1.new_outgoing_peer_count == 1          # only c is new; b known
    assert a1.unique_outgoing_peers == 2


def test_protocol_and_port_novelty():
    seq = [
        obs(0, "asset:a", "asset:b", proto="TCP", dport=443),
        obs(1, "asset:a", "asset:b", proto="UDP", dport=53),
    ]
    windows = build_node_feature_windows_v2(seq)
    a0 = by_asset(windows, "asset:a", 0)
    a1 = by_asset(windows, "asset:a", 1)
    assert a0.protocol_novelty_count == 1
    assert a0.port_novelty_count == 1
    assert a1.protocol_novelty_count == 1   # UDP new
    assert a1.port_novelty_count == 1       # 53 new


def test_peer_set_change_and_relationship_creation():
    seq = [
        obs(0, "asset:a", "asset:b"),
        obs(1, "asset:a", "asset:c"),
        obs(1, "asset:a", "asset:d"),
    ]
    windows = build_node_feature_windows_v2(seq)
    a1 = by_asset(windows, "asset:a", 1)
    assert a1.new_outgoing_peer_count == 2
    assert a1.relationship_creation_count == 2


def test_deterministic_feature_matrix():
    seq = [obs(0, "asset:a", "asset:b"), obs(1, "asset:a", "asset:c")]
    w = build_node_feature_windows_v2(seq)
    m1 = build_node_feature_matrix(w)
    m2 = build_node_feature_matrix(w)
    import pandas as pd
    pd.testing.assert_frame_equal(m1, m2)


def test_no_future_leakage():
    base = [obs(0, "asset:a", "asset:b"), obs(1, "asset:a", "asset:b")]
    extended = base + [obs(50, "asset:a", "asset:z")]
    w_base = build_node_feature_windows_v2(base)
    w_ext = build_node_feature_windows_v2(extended)
    a0b = by_asset(w_base, "asset:a", 0)
    a0e = by_asset(w_ext, "asset:a", 0)
    assert a0b.new_outgoing_peer_count == a0e.new_outgoing_peer_count
    assert a0b.unique_outgoing_peers == a0e.unique_outgoing_peers
    assert a0b.fan_out == a0e.fan_out
