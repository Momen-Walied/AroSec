"""False-merge tests: proximity alone must NOT merge signals."""
from __future__ import annotations

from ai.episodes.correlator.correlator import correlate
from ai.episodes.evaluation.scenarios import sig


def _two_unrelated(reason_a: list[str], reason_b: list[str], t_a: float, t_b: float) -> list:
    return [
        sig("edge", ["asset:A", "asset:B"], "rel:asset:A|asset:B|COMMUNICATES_WITH", t_a, 0.8, reason_a),
        sig("edge", ["asset:X", "asset:Y"], "rel:asset:X|asset:Y|COMMUNICATES_WITH", t_b, 0.8, reason_b),
    ]


def false_merge_report(gap: int = 60) -> dict:
    cases = {
        "same_timestamp_only": _two_unrelated(["NEW_PEER"], ["NEW_PEER"], 0, 0),
        "same_severity_only": _two_unrelated(["NEW_PEER"], ["PORT_NOVELTY"], 0, 10),
        "same_reason_only": _two_unrelated(["NEW_PEER"], ["NEW_PEER"], 0, 20),
        "unrelated_simultaneous": _two_unrelated(["NEW_PEER"], ["FAN_OUT_DEVIATION"], 0, 0),
    }
    out = {}
    for name, signals in cases.items():
        episodes = correlate(signals, correlation_gap_seconds=gap, max_episode_duration_seconds=600)
        out[name] = {"episodes": len(episodes), "merged": len(episodes) == 1}
    # a genuinely connected pair SHOULD merge (positive control)
    positive = [
        sig("edge", ["asset:A", "asset:B"], "rel:asset:A|asset:B|COMMUNICATES_WITH", 0, 0.8, ["NEW_PEER"]),
        sig("node", ["asset:A"], None, 10, 0.9, ["NEW_PEER_BURST"]),
    ]
    pos_eps = correlate(positive, correlation_gap_seconds=gap, max_episode_duration_seconds=600)
    out["positive_control_connected"] = {"episodes": len(pos_eps), "merged": len(pos_eps) == 1}
    return out
