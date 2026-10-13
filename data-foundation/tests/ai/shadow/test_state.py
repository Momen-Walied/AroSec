"""State persistence + restart/recovery tests."""
from __future__ import annotations

from ai.shadow.features.online_builder import OnlineFeatureBuilder
from ai.shadow.features.parity import compare_windows
from ai.shadow.state.memory import InMemoryStateStore
from ai.shadow.state.sqlite import SqliteStateStore
from tests.ai.shadow._helpers import obs, sample_sequence


def _collect(builder: OnlineFeatureBuilder, observations) -> list:
    out = []
    for o in observations:
        out.extend(builder.add(o))
    out.extend(builder.flush())
    return out


def test_state_roundtrip_matches_one_shot():
    seq = sample_sequence()
    one_shot = _collect(OnlineFeatureBuilder(), seq)

    b = OnlineFeatureBuilder()
    for o in seq[:3]:
        b.add(o)
    state = b.to_state()
    b2 = OnlineFeatureBuilder.from_state(state)
    rest = _collect(b2, seq[3:])

    report = compare_windows(one_shot, rest)
    assert report["total_mismatches"] == 0
    assert report["missing_in_online"] == 0


def test_relationship_stays_known_after_restart():
    from datetime import timedelta

    from tests.ai.shadow._helpers import T0

    b = OnlineFeatureBuilder()
    b.add(obs(0, "asset:a", "asset:b"))
    state = b.to_state()
    b2 = OnlineFeatureBuilder.from_state(state)
    emitted = b2.add(obs(1, "asset:a", "asset:b"))
    emitted += b2.flush()
    by_start = {w.window_start: w for w in emitted}
    assert by_start[T0].new_peer is True                                  # first window
    assert by_start[T0 + timedelta(seconds=30)].new_peer is False         # not new again after restart


def test_sqlite_state_store_restart(tmp_path):
    path = tmp_path / "state.sqlite"
    store = SqliteStateStore(path)
    b = OnlineFeatureBuilder()
    b.add(obs(0, "asset:a", "asset:b"))
    store.save(b.to_state())
    store.close()

    store2 = SqliteStateStore(path)
    loaded = store2.load()
    assert loaded is not None
    b2 = OnlineFeatureBuilder.from_state(loaded)
    assert "rel:asset:a|asset:b|COMMUNICATES_WITH" in b2.rel_state
    store2.close()


def test_memory_state_store_roundtrip():
    store = InMemoryStateStore()
    assert store.load() is None
    store.save({"x": 1})
    assert store.load() == {"x": 1}
