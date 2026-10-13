"""Runtime-level episode shadow tests: parity, restart, isolation, sink, safety."""
from __future__ import annotations

import json
import sqlite3

import pytest

from ai.contracts.shadow_records import EpisodeShadowRecordV1
from ai.episodes.correlator.correlator import correlate
from ai.episodes.correlator.signals import all_signals
from ai.episodes.evaluation.parity import compare_episodes
from ai.shadow.config import ShadowConfig
from ai.shadow.inference.model_bundle import ShadowModelBundle
from ai.shadow.inference.node_bundle import load_node_scorer
from ai.shadow.runtime import ShadowRuntime
from ai.shadow.sinks.memory import InMemoryShadowSink
from ai.shadow.sinks.sqlite import SqliteShadowSink
from ai.shadow.sources.list import ListObservationSource
from ai.shadow.state.memory import InMemoryStateStore
from ai.shadow.state.sqlite import SqliteStateStore
from tests.ai.node_behavior._helpers import obs

CFG = ShadowConfig(dataset_id="synthetic")


def _artifacts() -> bool:
    try:
        ShadowModelBundle.load(CFG.model_bundle)
        load_node_scorer(CFG.node_model_artifact)
        return True
    except Exception:  # noqa: BLE001
        return False


requires = pytest.mark.skipif(not _artifacts(), reason="model bundles not regenerated locally")


def obs_seq():
    return [
        obs(0, "asset:A", "asset:B", dport=443),
        obs(0, "asset:A", "asset:C", dport=445),
        obs(0, "asset:B", "asset:A", dport=80),
        obs(1, "asset:A", "asset:B", dport=443),
        obs(1, "asset:A", "asset:D", proto="UDP", dport=53),
        obs(2, "asset:A", "asset:E", dport=445),
    ]


def _rt(obs_list, sink, store):
    return ShadowRuntime(CFG, ListObservationSource(obs_list), sink, store,
                         edge_bundle=ShadowModelBundle.load(CFG.model_bundle),
                         node_scorer=load_node_scorer(CFG.node_model_artifact))


@requires
def test_online_offline_episode_parity():
    sink = InMemoryShadowSink()
    _rt(obs_seq(), sink, InMemoryStateStore()).run()
    online = sink.episodes()
    signals = all_signals(sink.edge_records(), sink.node_records(), CFG.shadow_threshold, CFG.node_threshold)
    offline = correlate(signals, CFG.episode_correlation_gap_seconds, CFG.episode_max_duration_seconds,
                        None, CFG.window_seconds, CFG.allowed_lateness_seconds)
    parity = compare_episodes(offline, online)
    assert parity["total_mismatches"] == 0


@requires
def test_restart_in_middle_matches_uninterrupted(tmp_path):
    full = InMemoryShadowSink()
    _rt(obs_seq(), full, InMemoryStateStore()).run()
    uninterrupted = full.episodes()

    store = SqliteStateStore(tmp_path / "st.sqlite")
    a, b = InMemoryShadowSink(), InMemoryShadowSink()
    _rt(obs_seq()[:3], a, store).run(flush_at_end=False)
    _rt(obs_seq()[3:], b, store).run()
    store.close()
    restart = a.episodes() + b.episodes()
    assert compare_episodes(uninterrupted, restart)["total_mismatches"] == 0


@requires
def test_component_isolation_episode_failure_does_not_stop_edge_node():
    sink = InMemoryShadowSink()
    rt = _rt(obs_seq(), sink, InMemoryStateStore())

    def boom(_signal):
        raise RuntimeError("correlator down")

    rt.correlator.add = boom  # simulate episode-layer failure
    rt.run()
    assert len(sink.edge_records()) > 0
    assert len(sink.node_records()) > 0
    assert rt.metrics.counters.get("episode_correlator_errors_total", 0) > 0


@requires
def test_episode_sink_idempotent(tmp_path):
    sink = InMemoryShadowSink()
    _rt(obs_seq(), sink, InMemoryStateStore()).run()
    episodes = sink.episodes()
    assert episodes, "expected at least one episode"
    path = tmp_path / "ep.sqlite"
    s = SqliteShadowSink(path)
    for ep in episodes:
        rec = EpisodeShadowRecordV1(runtime_version="test", episode=ep)
        s.write_episode(rec)
        s.write_episode(rec)  # duplicate
    s.close()
    conn = sqlite3.connect(str(path))
    n = conn.execute("SELECT COUNT(*) FROM behavioral_episodes").fetchone()[0]
    conn.close()
    assert n == len(episodes)


@requires
def test_no_attack_fields_in_episode_records():
    sink = InMemoryShadowSink()
    _rt(obs_seq(), sink, InMemoryStateStore()).run()
    for rec in sink.episode_records:
        blob = json.dumps(rec.model_dump(mode="json"))
        for term in ("attack_probability", "attack_stage", "attacker", "victim", "objective", "attack_path"):
            assert term not in blob
        assert rec.intelligence_type == "episode"


def test_episode_record_shadow_invariants():
    from pydantic import ValidationError

    from ai.episodes.evaluation.scenarios import build_scenario
    ep = correlate(build_scenario("SCN-E01_SAME_ENTITY_BURST"), 60, 600)[0]
    with pytest.raises(ValidationError):
        EpisodeShadowRecordV1(runtime_version="t", episode=ep, shadow_mode=False)
    with pytest.raises(ValidationError):
        EpisodeShadowRecordV1(runtime_version="t", episode=ep, intelligence_type="incident")


def test_non_shadow_mode_rejected():
    with pytest.raises(ValueError):
        ShadowConfig(mode="active")


@requires
def test_node_scores_batch_invariant_on_longer_sequence():
    """Regression: batched node scoring must not shuffle scores across windows."""
    seq = []
    for w in range(12):
        for p in range(4):
            seq.append(obs(w, "asset:A", f"asset:P{p}", dport=4000 + p))
        seq.append(obs(w, f"asset:B{w % 3}", "asset:A", dport=80))

    def scores(bs):
        sink = InMemoryShadowSink()
        ShadowRuntime(
            CFG, ListObservationSource(seq), sink, InMemoryStateStore(),
            edge_bundle=ShadowModelBundle.load(CFG.model_bundle),
            node_scorer=load_node_scorer(CFG.node_model_artifact), batch_size=bs).run()
        return {(r.feature_window.asset_id, r.feature_window.window_start.isoformat()):
                r.anomaly_result.anomaly_score for r in sink.node_records()}

    assert scores(1) == scores(2048)
