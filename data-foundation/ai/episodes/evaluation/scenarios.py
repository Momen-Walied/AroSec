"""Deterministic synthetic correlation scenarios (EVALUATION ONLY)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ai.episodes.correlator.signals import Signal

T0 = datetime(2024, 3, 2, 2, 13, 0, tzinfo=UTC)

SCENARIOS = [
    "SCN-E01_SAME_ENTITY_BURST",
    "SCN-E02_CHAIN",
    "SCN-E03_UNRELATED_SIMULTANEOUS",
    "SCN-E04_SAME_ENTITY_LARGE_GAP",
    "SCN-E05_NODE_EDGE_SUPPORT",
    "SCN-E06_ALERT_STORM",
    "SCN-E07_PERCOLATION_STRESS",
    "SCN-E08_TWO_ACTIVE_MERGE",
]


def sig(stype: str, assets: list[str], rel: str | None, t: float, score: float,
        reasons: list[str], tag: str = "") -> Signal:
    ws = T0 + timedelta(seconds=t)
    we = ws + timedelta(seconds=30)
    if stype == "edge":
        sid = f"sig:edge:{rel}:{ws.isoformat()}"
    else:
        sid = f"sig:node:{assets[0]}:{ws.isoformat()}"
    if tag:
        sid = f"{sid}:{tag}"
    return Signal(signal_id=sid, signal_type=stype, window_start=ws, window_end=we, score=score,
                  severity="HIGH" if score >= 0.7 else "MEDIUM", reason_codes=tuple(sorted(reasons)),
                  asset_ids=tuple(sorted(assets)), relationship_id=rel, result_ref=sid,
                  evidence_refs=(sid,))


def rel(a: str, b: str) -> str:
    return f"rel:{a}|{b}|COMMUNICATES_WITH"


def build_scenario(name: str) -> list[Signal]:
    a, b, c, d = "asset:A", "asset:B", "asset:C", "asset:D"
    x, y = "asset:X", "asset:Y"
    if name == "SCN-E01_SAME_ENTITY_BURST":
        return [sig("edge", [a, b], rel(a, b), 0, 0.8, ["NEW_PEER"]),
                sig("edge", [a, c], rel(a, c), 10, 0.8, ["PORT_NOVELTY"]),
                sig("node", [a], None, 20, 0.9, ["NEW_PEER_BURST", "FAN_OUT_DEVIATION"])]
    if name == "SCN-E02_CHAIN":
        return [sig("edge", [a, b], rel(a, b), 0, 0.8, ["NEW_PEER"]),
                sig("edge", [b, c], rel(b, c), 20, 0.8, ["NEW_PEER"])]
    if name == "SCN-E03_UNRELATED_SIMULTANEOUS":
        return [sig("edge", [a, b], rel(a, b), 0, 0.8, ["NEW_PEER"]),
                sig("edge", [x, y], rel(x, y), 0, 0.8, ["NEW_PEER"])]
    if name == "SCN-E04_SAME_ENTITY_LARGE_GAP":
        return [sig("edge", [a, b], rel(a, b), 0, 0.8, ["NEW_PEER"]),
                sig("edge", [a, c], rel(a, c), 3600, 0.8, ["NEW_PEER"])]
    if name == "SCN-E05_NODE_EDGE_SUPPORT":
        return [sig("node", [a], None, 0, 0.9, ["NEW_PEER_BURST"]),
                sig("edge", [a, b], rel(a, b), 5, 0.8, ["NEW_PEER"]),
                sig("edge", [a, c], rel(a, c), 10, 0.8, ["PORT_NOVELTY"])]
    if name == "SCN-E06_ALERT_STORM":
        return [sig("edge", [a, f"asset:P{i}"], rel(a, f"asset:P{i}"), i * 2, 0.8, ["NEW_PEER"])
                for i in range(20)]
    if name == "SCN-E07_PERCOLATION_STRESS":
        nodes = [f"asset:N{i}" for i in range(14)]
        return [sig("edge", [nodes[i], nodes[i + 1]], rel(nodes[i], nodes[i + 1]), i * 60, 0.8, ["NEW_PEER"])
                for i in range(len(nodes) - 1)]
    if name == "SCN-E08_TWO_ACTIVE_MERGE":
        return [sig("edge", [a, b], rel(a, b), 0, 0.8, ["NEW_PEER"]),
                sig("edge", [c, d], rel(c, d), 10, 0.8, ["NEW_PEER"]),
                sig("edge", [b, c], rel(b, c), 20, 0.8, ["NEW_PEER"])]
    raise KeyError(name)


def all_scenarios() -> dict[str, list[Signal]]:
    return {name: build_scenario(name) for name in SCENARIOS}
