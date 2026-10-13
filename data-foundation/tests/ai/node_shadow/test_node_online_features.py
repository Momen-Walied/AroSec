"""Online node feature semantics (directional aggregation, novelty, determinism)."""
from __future__ import annotations

from ai.shadow.features.online_node_builder import OnlineNodeFeatureBuilder
from tests.ai.node_shadow._helpers import T0, obs


def _collect(seq, **kw):
    b = OnlineNodeFeatureBuilder(**kw)
    out = []
    for o in seq:
        out.extend(b.add(o))
    out.extend(b.flush())
    return out, b


def _by(out, asset, win):
    from datetime import timedelta

    target = T0 + timedelta(seconds=30 * win)
    return next(w for w in out if w.asset_id == asset and w.window_start == target)


def test_offline_online_parity_none():
    from ai.node_behavior.features.builder import build_node_feature_windows_v2
    from ai.shadow.features.parity import compare_node_windows
    from tests.ai.node_shadow._helpers import sample_sequence

    seq = sample_sequence()
    off = build_node_feature_windows_v2(seq)
    on, _ = _collect(seq, window_seconds=30, allowed_lateness_seconds=0)
    assert compare_node_windows(off, on)["total_mismatches"] == 0


def test_directional_update_from_one_observation():
    seq = [obs(0, "asset:src", "asset:dst", dport=443)]
    out, _ = _collect(seq)
    src = _by(out, "asset:src", 0)
    dst = _by(out, "asset:dst", 0)
    assert src.outgoing_connection_count == 1 and src.incoming_connection_count == 0
    assert dst.incoming_connection_count == 1 and dst.outgoing_connection_count == 0


def test_inbound_and_outbound_aggregation():
    from tests.ai.node_shadow._helpers import sample_sequence
    out, _ = _collect(sample_sequence())
    a0 = _by(out, "asset:a", 0)
    assert a0.outgoing_connection_count == 1   # a->b
    assert a0.incoming_connection_count == 1   # b->a
    assert a0.unique_outgoing_peers == 1 and a0.unique_incoming_peers == 1
    assert a0.fan_out == 1 and a0.fan_in == 1


def test_new_peers_protocol_port_novelty():
    from tests.ai.node_shadow._helpers import sample_sequence
    out, _ = _collect(sample_sequence())
    a0 = _by(out, "asset:a", 0)
    a1 = _by(out, "asset:a", 1)
    a2 = _by(out, "asset:a", 2)
    assert a0.new_outgoing_peer_count == 1            # b
    assert a1.new_outgoing_peer_count == 1            # c (new), b known
    assert a1.protocol_novelty_count == 1             # UDP new
    assert a1.port_novelty_count == 1                 # 53 new
    assert a2.new_outgoing_peer_count == 1            # d
    assert a2.relationship_creation_count == 1


def test_deterministic_online_features():
    from tests.ai.node_shadow._helpers import sample_sequence
    seq = sample_sequence()
    a, _ = _collect(seq)
    b, _ = _collect(seq)
    assert [w.model_dump() for w in a] == [w.model_dump() for w in b]
