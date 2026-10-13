"""Online correlator streaming semantics (dedupe, late, gap, flush, false-merge regression)."""
from __future__ import annotations

from datetime import timedelta

from ai.episodes.correlator.correlator import BehavioralEpisodeCorrelator, correlate
from ai.episodes.evaluation.scenarios import SCENARIOS, rel, sig

GAP, MAXD = 60, 600


def _run(signals, gap=GAP):
    c = BehavioralEpisodeCorrelator(gap, MAXD, None, 30, 30)
    out = []
    for s in sorted(signals, key=lambda x: (x.window_start, x.signal_type, x.signal_id)):
        out.extend(c.add(s))
    out.extend(c.flush())
    return out, c


def test_scenarios_regression():
    expected = {"SCN-E01_SAME_ENTITY_BURST": 1, "SCN-E02_CHAIN": 1, "SCN-E03_UNRELATED_SIMULTANEOUS": 2,
                "SCN-E04_SAME_ENTITY_LARGE_GAP": 2, "SCN-E05_NODE_EDGE_SUPPORT": 1, "SCN-E06_ALERT_STORM": 1,
                "SCN-E08_TWO_ACTIVE_MERGE": 1}
    from ai.episodes.evaluation.scenarios import build_scenario
    for name in SCENARIOS:
        n = len(correlate(build_scenario(name), GAP, MAXD))
        if name in expected:
            assert n == expected[name], name
        else:
            assert n >= 2  # SCN-E07 percolation bounded


def test_signal_idempotency():
    s = sig("edge", ["asset:A", "asset:B"], rel("asset:A", "asset:B"), 0, 0.8, ["NEW_PEER"])
    c = BehavioralEpisodeCorrelator(GAP, MAXD)
    c.add(s)
    c.add(s)  # duplicate
    assert c.counters["episode_signals_duplicate_total"] == 1
    eps = c.flush()
    assert len(eps) == 1 and eps[0].edge_signal_count == 1


def test_late_before_finalization_correlates():
    a = sig("edge", ["asset:A", "asset:B"], rel("asset:A", "asset:B"), 0, 0.8, ["NEW_PEER"])
    b = sig("edge", ["asset:A", "asset:C"], rel("asset:A", "asset:C"), 40, 0.8, ["NEW_PEER"])
    eps, _ = _run([a, b])
    assert len(eps) == 1  # within gap


def test_late_after_finalization_quarantined():
    c = BehavioralEpisodeCorrelator(GAP, MAXD, None, 30, 30)
    c.add(sig("edge", ["asset:A", "asset:B"], rel("asset:A", "asset:B"), 100000, 0.8, ["NEW_PEER"]))
    c.add(sig("edge", ["asset:A", "asset:C"], rel("asset:A", "asset:C"), 0, 0.8, ["NEW_PEER"]))
    assert c.counters["episode_signals_late_total"] == 1


def test_gap_timeout_new_episode():
    a = sig("edge", ["asset:A", "asset:B"], rel("asset:A", "asset:B"), 0, 0.8, ["NEW_PEER"])
    b = sig("edge", ["asset:A", "asset:C"], rel("asset:A", "asset:C"), 120, 0.8, ["NEW_PEER"])
    assert len(correlate([a, b], GAP, MAXD)) == 2
    assert len(correlate([a, b], 120, MAXD)) == 1


def test_advance_watermark_is_parity_safe():
    from ai.episodes.evaluation.scenarios import build_scenario
    signals = build_scenario("SCN-E01_SAME_ENTITY_BURST")
    base = correlate(signals, GAP, MAXD)
    c = BehavioralEpisodeCorrelator(GAP, MAXD, None, 30, 30)
    out = []
    for s in sorted(signals, key=lambda x: (x.window_start, x.signal_type, x.signal_id)):
        out.extend(c.add(s))
    out.extend(c.advance_watermark(signals[-1].window_end + timedelta(seconds=GAP + 300)))
    out.extend(c.flush())
    assert {e.episode_id for e in out} == {e.episode_id for e in base}


def test_end_of_stream_flush_closes_open():
    c = BehavioralEpisodeCorrelator(GAP, MAXD)
    c.add(sig("edge", ["asset:A", "asset:B"], rel("asset:A", "asset:B"), 0, 0.8, ["NEW_PEER"]))
    assert len(c.active) == 1
    eps = c.flush()
    assert len(eps) == 1 and len(c.active) == 0


def test_false_merge_regression():
    from ai.episodes.evaluation.false_merge import false_merge_report
    fm = false_merge_report(GAP)
    assert fm["same_timestamp_only"]["merged"] is False
    assert fm["same_severity_only"]["merged"] is False
    assert fm["same_reason_only"]["merged"] is False
    assert fm["positive_control_connected"]["merged"] is True


def test_merge_semantics_deterministic():
    from ai.episodes.evaluation.scenarios import build_scenario
    eps = correlate(build_scenario("SCN-E08_TWO_ACTIVE_MERGE"), GAP, MAXD)
    assert len(eps) == 1
