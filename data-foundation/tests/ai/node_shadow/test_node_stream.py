"""Node stream: duplicate safety, lateness, restart/recovery."""
from __future__ import annotations

from ai.shadow.features.online_node_builder import OnlineNodeFeatureBuilder
from ai.shadow.state.sqlite import SqliteStateStore
from tests.ai.node_shadow._helpers import T0, obs, sample_sequence


def _run(builder, seq):
    out = []
    for o in seq:
        out.extend(builder.add(o))
    out.extend(builder.flush())
    return out


def test_duplicate_is_idempotent():
    b = OnlineNodeFeatureBuilder()
    o = obs(0, "asset:a", "asset:b")
    b.add(o)
    b.add(o)
    assert b.counters["node_observations_duplicate_total"] == 1
    out = b.flush()
    a = next(w for w in out if w.asset_id == "asset:a")
    assert a.outgoing_connection_count == 1


def test_one_window_late_accepted():
    b = OnlineNodeFeatureBuilder(allowed_lateness_seconds=30)
    b.add(obs(2, "asset:a", "asset:b"))
    b.add(obs(1, "asset:a", "asset:b"))
    assert b.counters["node_observations_late_total"] == 0
    # 2 entities (a,b) x 2 windows (1,2) = 4 node windows
    assert len(b.flush()) == 4


def test_two_windows_late_quarantined():
    b = OnlineNodeFeatureBuilder(allowed_lateness_seconds=30)
    b.add(obs(3, "asset:a", "asset:b"))
    b.add(obs(1, "asset:a", "asset:b"))
    assert b.counters["node_observations_late_total"] == 1


def test_restart_keeps_peers_known():
    seq = sample_sequence()
    one_shot = _run(OnlineNodeFeatureBuilder(), seq)

    b = OnlineNodeFeatureBuilder()
    for o in seq[:2]:
        b.add(o)
    state = b.to_state()
    b2 = OnlineNodeFeatureBuilder.from_state(state)
    resumed = _run(b2, seq[2:])

    from ai.shadow.features.parity import compare_node_windows
    assert compare_node_windows(one_shot, resumed)["total_mismatches"] == 0

    # known peer stays known after restart
    from datetime import timedelta
    b3 = OnlineNodeFeatureBuilder()
    b3.add(obs(0, "asset:a", "asset:b"))
    st = b3.to_state()
    b4 = OnlineNodeFeatureBuilder.from_state(st)
    emitted = _run(b4, [obs(1, "asset:a", "asset:b")])
    a1 = next(w for w in emitted if w.asset_id == "asset:a"
              and w.window_start == T0 + timedelta(seconds=30))
    assert a1.new_outgoing_peer_count == 0


def test_sqlite_state_roundtrip(tmp_path):
    store = SqliteStateStore(tmp_path / "s.sqlite")
    b = OnlineNodeFeatureBuilder()
    b.add(obs(0, "asset:a", "asset:b"))
    store.save({"node": b.to_state()})
    store.close()
    store2 = SqliteStateStore(tmp_path / "s.sqlite")
    loaded = store2.load()
    b2 = OnlineNodeFeatureBuilder.from_state(loaded["node"])
    assert "asset:a" in b2.asset_state and "asset:b" in b2.asset_state
    store2.close()
