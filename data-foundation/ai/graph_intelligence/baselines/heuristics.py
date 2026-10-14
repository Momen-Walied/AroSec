"""Graph-aware, non-neural baselines — the minimum bar a GNN must beat.

All baselines are computed on the CAUSAL graph state at ``as_of`` (events strictly before
the target). They never see the target edge or any future edge.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass

import numpy as np


@dataclass
class CausalGraph:
    adj: dict[str, set[str]]                       # undirected
    out_freq: dict[tuple[str, str], int]          # directed observation counts
    last_seen: dict[tuple[str, str], np.datetime64]
    node_deg: dict[str, int]
    as_of: np.datetime64

    def seconds_since(self, u: str, v: str) -> float | None:
        last = self.last_seen.get((u, v)) or self.last_seen.get((v, u))
        if last is None:
            return None
        return float((self.as_of - last) / np.timedelta64(1, "s"))


def build_causal_graph(event_src, event_dst, event_win, window_end) -> CausalGraph:
    adj: dict[str, set[str]] = defaultdict(set)
    out_freq: dict[tuple[str, str], int] = defaultdict(int)
    last: dict[tuple[str, str], np.datetime64] = {}
    deg: dict[str, int] = defaultdict(int)
    for u, v, t in zip(event_src, event_dst, event_win, strict=False):
        if u == v:
            continue
        adj[u].add(v)
        adj[v].add(u)
        out_freq[(u, v)] += 1
        if (u, v) not in last or t > last[(u, v)]:
            last[(u, v)] = t
    for n, ns in adj.items():
        deg[n] = len(ns)
    return CausalGraph(adj=dict(adj), out_freq=dict(out_freq), last_seen=last,
                       node_deg=dict(deg), as_of=window_end)


def _nbr(g: CausalGraph, n: str) -> set[str]:
    return g.adj.get(n, set())


class GraphHeuristics:
    """Named heuristics; higher = more likely to be a real/appearing edge."""

    NAMES = ("frequency", "recency", "source_destination_frequency", "preferential_attachment",
             "common_neighbors", "jaccard", "adamic_adar", "peer_overlap",
             "degree_deviation", "structural_novelty")

    def __init__(self, g: CausalGraph) -> None:
        self.g = g

    def frequency(self, u: str, v: str) -> float:
        return float(self.g.out_freq.get((u, v), 0) + self.g.out_freq.get((v, u), 0))

    def recency(self, u: str, v: str) -> float:
        s = self.g.seconds_since(u, v)
        return 0.0 if s is None else 1.0 / (1.0 + s)

    def source_destination_frequency(self, u: str, v: str) -> float:
        total = sum(c for (a, _), c in self.g.out_freq.items() if a == u)
        if total == 0:
            return 0.0
        return self.g.out_freq.get((u, v), 0) / total

    def preferential_attachment(self, u: str, v: str) -> float:
        return float(self.g.node_deg.get(u, 0) * self.g.node_deg.get(v, 0))

    def common_neighbors(self, u: str, v: str) -> float:
        return float(len(_nbr(self.g, u) & _nbr(self.g, v)))

    def jaccard(self, u: str, v: str) -> float:
        a, b = _nbr(self.g, u), _nbr(self.g, v)
        union = a | b
        return len(a & b) / len(union) if union else 0.0

    def adamic_adar(self, u: str, v: str) -> float:
        s = 0.0
        for w in _nbr(self.g, u) & _nbr(self.g, v):
            d = self.g.node_deg.get(w, 0)
            if d > 1:
                s += 1.0 / math.log(d)
        return s

    def peer_overlap(self, u: str, v: str) -> float:
        a, b = _nbr(self.g, u), _nbr(self.g, v)
        m = min(len(a), len(b))
        return len(a & b) / m if m else 0.0

    def degree_deviation(self, u: str, v: str) -> float:
        return float(abs(self.g.node_deg.get(u, 0) - self.g.node_deg.get(v, 0)))

    def structural_novelty(self, u: str, v: str) -> float:
        return 1.0 if v not in _nbr(self.g, u) else 0.0

    def all_scores(self, u: str, v: str) -> dict[str, float]:
        return {name: float(getattr(self, name)(u, v)) for name in self.NAMES}
