"""Stream correctness: duplicates, lateness, out-of-order, boundaries."""
from __future__ import annotations

from datetime import timedelta

from ai.shadow.features.online_builder import OnlineFeatureBuilder
from tests.ai.shadow._helpers import T0, obs


def _builder(lateness: int = 30) -> OnlineFeatureBuilder:
    return OnlineFeatureBuilder(window_seconds=30, allowed_lateness_seconds=lateness)


def test_duplicate_observation_is_idempotent():
    b = _builder()
    o = obs(0, "asset:a", "asset:b")
    b.add(o)
    b.add(o)  # duplicate
    assert b.counters["observations_duplicate_total"] == 1
    windows = b.flush()
    rel = [w for w in windows if w.relationship_id == o.relationship_id]
    assert len(rel) == 1
    assert rel[0].connections_count == o.connection_count


def test_one_window_late_is_accepted():
    b = _builder(lateness=30)
    b.add(obs(2, "asset:a", "asset:b"))   # advance watermark
    b.add(obs(1, "asset:a", "asset:b"))   # one window late -> accepted
    assert b.counters["observations_late_total"] == 0
    assert len(b.flush()) == 2


def test_two_windows_late_is_quarantined():
    b = _builder(lateness=30)
    b.add(obs(3, "asset:a", "asset:b"))   # advance watermark
    b.add(obs(1, "asset:a", "asset:b"))   # two windows late -> quarantined
    assert b.counters["observations_late_total"] == 1
    assert len(b.flush()) == 1


def test_out_of_order_records_do_not_double_count():
    b = _builder(lateness=30)
    for o in [obs(2, "asset:a", "asset:b"), obs(0, "asset:a", "asset:b"), obs(1, "asset:a", "asset:b")]:
        b.add(o)
    windows = b.flush()
    total_conn = sum(w.connections_count for w in windows)
    assert total_conn == 2  # the too-late window 0 is quarantined, not counted twice


def test_half_open_window_boundary_preserved():
    b = _builder()
    out = b.add(obs(1, "asset:a", "asset:b"))
    out += b.flush()
    w = out[0]
    assert w.window_start == T0 + timedelta(seconds=30)
    assert (w.window_end - w.window_start).total_seconds() == 30
