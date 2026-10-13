"""Watermark-driven episode finalization (release-blocker + streaming cases)."""
from __future__ import annotations

from datetime import timedelta

import pytest

from ai.episodes.correlator.correlator import BehavioralEpisodeCorrelator
from ai.episodes.evaluation.scenarios import rel, sig
from ai.shadow.config import ShadowConfig
from ai.shadow.inference.model_bundle import ShadowModelBundle
from ai.shadow.inference.node_bundle import load_node_scorer
from ai.shadow.runtime import ShadowRuntime
from ai.shadow.sinks.memory import InMemoryShadowSink
from ai.shadow.sources.list import ListObservationSource
from ai.shadow.state.memory import InMemoryStateStore
from tests.ai.node_behavior._helpers import obs

CFG = ShadowConfig(dataset_id="synthetic")
GAP, MAXD, SLACK = 60, 600, 60  # slack = window(30) + lateness(30)


def _artifacts() -> bool:
    try:
        ShadowModelBundle.load(CFG.model_bundle)
        load_node_scorer(CFG.node_model_artifact)
        return True
    except Exception:  # noqa: BLE001
        return False


requires = pytest.mark.skipif(not _artifacts(), reason="model bundles not regenerated locally")


def _rt(seq, bs=2048, flush=False):
    sink = InMemoryShadowSink()
    rt = ShadowRuntime(CFG, ListObservationSource(seq), sink, InMemoryStateStore(),
                       edge_bundle=ShadowModelBundle.load(CFG.model_bundle),
                       node_scorer=load_node_scorer(CFG.node_model_artifact), batch_size=bs)
    rt.run(flush_at_end=flush)
    return rt, sink


def quiet_seq():
    # one anomaly at window 0, then quiet repeats (no new signals) advancing the watermark
    return [obs(0, "asset:A", "asset:B", dport=443)] + \
           [obs(w, "asset:A", "asset:B", dport=443) for w in range(1, 15)]


# ---------------------------------------------------------------- release blocker #
@requires
def test_quiet_stream_closes_without_further_signal():
    rt, sink = _rt(quiet_seq(), flush=False)
    closed = sink.episodes()
    assert len(closed) >= 1
    assert len(rt.correlator.active) == 0                # closed by watermark, not end-of-stream
    ep = closed[0]
    assert ep.end_time <= max(w.window_start for w in quiet_seq())   # end_time is last signal time


@requires
def test_record_closed_at_is_runtime_watermark_end_time_is_semantic():
    rt, sink = _rt(quiet_seq(), flush=False)
    assert len(sink.episode_records) >= 1
    rec = sink.episode_records[0]
    # runtime close watermark is on the envelope, strictly after the semantic end_time
    assert rec.closed_at is not None
    assert rec.closed_at > rec.episode.end_time
    # end_time remains the last behavioral signal's event time
    assert rec.episode.end_time <= max(w.window_start for w in quiet_seq())


@requires
def test_two_unrelated_episodes_close_independently():
    seq = [obs(0, "asset:A", "asset:B", dport=443), obs(0, "asset:X", "asset:Y", dport=445)] + \
          [obs(w, "asset:A", "asset:B", dport=443) for w in range(1, 15)]
    rt, sink = _rt(seq, flush=False)
    assert len(sink.episodes()) == 2
    assert len(rt.correlator.active) == 0


@requires
def test_batch_size_invariance_episode_ids():
    seq = quiet_seq()
    _, s1 = _rt(seq, bs=1)
    _, s2 = _rt(seq, bs=2048)
    ids1 = sorted(e.episode_id for e in s1.episodes())
    ids2 = sorted(e.episode_id for e in s2.episodes())
    assert ids1 == ids2 and len(ids1) >= 1


@requires
def test_restart_before_expiry_equals_uninterrupted(tmp_path):
    from ai.episodes.evaluation.parity import compare_episodes
    from ai.shadow.state.sqlite import SqliteStateStore

    seq = quiet_seq()
    _, full = _rt(seq, flush=True)
    expected = full.episodes()

    store = SqliteStateStore(tmp_path / "s.sqlite")
    a, b = InMemoryShadowSink(), InMemoryShadowSink()
    ShadowRuntime(CFG, ListObservationSource(seq[:5]), a, store,
                  edge_bundle=ShadowModelBundle.load(CFG.model_bundle),
                  node_scorer=load_node_scorer(CFG.node_model_artifact)).run(flush_at_end=False)
    ShadowRuntime(CFG, ListObservationSource(seq[5:]), b, store,
                  edge_bundle=ShadowModelBundle.load(CFG.model_bundle),
                  node_scorer=load_node_scorer(CFG.node_model_artifact)).run()
    store.close()
    assert compare_episodes(expected, a.episodes() + b.episodes())["total_mismatches"] == 0


@requires
def test_late_anomaly_after_closure_not_rewritten():
    seq = quiet_seq() + [obs(30, "asset:A", "asset:Z", dport=999)]
    rt, sink = _rt(seq, flush=True)
    for ep in sink.episodes():
        assert "asset:Z" not in ep.involved_asset_ids or ep.start_time > seq[0].window_start


# ---------------------------------------------------------------- correlator-level #
def test_not_closed_before_watermark_is_safe():
    c = BehavioralEpisodeCorrelator(GAP, MAXD, None, 30, 30)
    s = sig("edge", ["asset:A", "asset:B"], rel("asset:A", "asset:B"), 0, 0.8, ["NEW_PEER"])
    c.add(s)
    end = s.window_end
    assert c.advance_watermark(end + timedelta(seconds=GAP)) == []              # not safe yet
    assert len(c.active) == 1
    closed = c.advance_watermark(end + timedelta(seconds=GAP + SLACK + 1))      # safe now
    assert len(closed) == 1 and len(c.active) == 0


def test_max_duration_bounds_continuously_active_chain():
    from ai.episodes.evaluation.scenarios import build_scenario
    eps = BehavioralEpisodeCorrelator(GAP, MAXD, None, 30, 30)
    out = []
    for s in build_scenario("SCN-E07_PERCOLATION_STRESS"):
        out.extend(eps.add(s))
    out.extend(eps.flush())
    assert len(out) >= 2
    assert all(e.duration_seconds <= MAXD + SLACK + 30 for e in out)


def test_quiet_shutdown_flush_works():
    c = BehavioralEpisodeCorrelator(GAP, MAXD)
    c.add(sig("edge", ["asset:A", "asset:B"], rel("asset:A", "asset:B"), 0, 0.8, ["NEW_PEER"]))
    eps = c.flush()
    assert len(eps) == 1 and eps[0].status == "closed"
