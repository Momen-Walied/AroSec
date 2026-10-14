"""Causal graph-context feature extraction (GraphContextEdgeFeaturesV1).

For a target edge-window at ``T`` this computes local temporal graph-context features from
graph state observable strictly before ``T``:

  recent   window = [T - lookback, T)
  baseline window = [T - 2*lookback, T - lookback)   (for deltas / set change)

No future edge, neighbour, degree, or frequency ever enters a feature. Hub bucketing uses a
node's causal degree (distinct peers observed before ``T``) against a degree percentile —
never a hardcoded asset id.
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd

from .contracts import GRAPH_CONTEXT_FEATURES_SCHEMA


def _jaccard(a: set, b: set) -> float:
    u = a | b
    return len(a & b) / len(u) if u else 0.0


def _hop_ball(adj: dict[str, set[str]], origins: set[str], hops: int) -> set[str]:
    seen = set(origins)
    frontier = set(origins)
    for _ in range(hops):
        nxt: set[str] = set()
        for n in frontier:
            for m in adj.get(n, ()):
                if m not in seen:
                    seen.add(m)
                    nxt.add(m)
        frontier = nxt
    return seen


def _adjacency(s, d):
    und: dict[str, set[str]] = defaultdict(set)
    out: dict[str, set[str]] = defaultdict(set)
    inn: dict[str, set[str]] = defaultdict(set)
    for u, v in zip(s, d, strict=False):
        if u == v:
            continue
        und[u].add(v)
        und[v].add(u)
        out[u].add(v)
        inn[v].add(u)
    return und, out, inn


class ContextExtractor:
    def __init__(self, events: pd.DataFrame, *, lookback_seconds: int, hops: int,
                 hub_percentile: float = 0.95):
        ev = events.sort_values(["window_start", "event_id"], kind="mergesort").reset_index(drop=True)
        self.ws = ev.window_start.to_numpy()
        self.we = ev.window_end.to_numpy()
        self.src = ev.src_asset_id.to_numpy()
        self.dst = ev.dst_asset_id.to_numpy()
        self.eid = ev.event_id.to_numpy()
        self.rel = ev.relationship_id.to_numpy()
        self.newrel = ev.is_new_relationship.to_numpy()
        self.lookback = lookback_seconds
        self.hops = hops

        # first time each (node_a -> node_b) pair is observed, for causal degree
        peer_first: dict[str, dict[str, np.datetime64]] = defaultdict(dict)
        for u, v, t in zip(self.src, self.dst, self.ws, strict=False):
            for a, b in ((u, v), (v, u)):
                if b not in peer_first[a] or t < peer_first[a][b]:
                    peer_first[a][b] = t
        self.node_peer_first = dict(peer_first)
        deg = np.array([len(d) for d in peer_first.values()]) if peer_first else np.array([0])
        # structural hub threshold: high percentile with a floor so a mostly-degree-1
        # distribution does not classify every leaf as a hub
        self.hub_threshold = max(float(np.quantile(deg, hub_percentile)), 5.0)
        self.hub_percentile = hub_percentile

    def _causal_degree(self, n: str, t) -> int:
        pf = self.node_peer_first.get(n)
        return sum(1 for ts in pf.values() if ts < t) if pf else 0

    def _bucket(self, n: str, t) -> str:
        return "hub" if self._causal_degree(n, t) >= self.hub_threshold else "low"

    def extract(self, i: int) -> dict:
        t = self.ws[i]
        L = np.timedelta64(self.lookback, "s")
        r_lo = np.searchsorted(self.ws, t - L, "left")
        r_hi = np.searchsorted(self.ws, t, "left")
        b_lo = np.searchsorted(self.ws, t - 2 * L, "left")
        s_r, d_r, n_r = self.src[r_lo:r_hi], self.dst[r_lo:r_hi], self.newrel[r_lo:r_hi]
        s_b, d_b = self.src[b_lo:r_lo], self.dst[b_lo:r_lo]

        und_r, out_r, in_r = _adjacency(s_r, d_r)
        und_b, out_b, in_b = _adjacency(s_b, d_b)
        src, dst = str(self.src[i]), str(self.dst[i])

        def nbr(und, n):
            return und.get(n, set())

        src_nr, dst_nr = nbr(und_r, src), nbr(und_r, dst)
        src_nb, dst_nb = nbr(und_b, src), nbr(und_b, dst)

        source_new_out = len(out_r.get(src, set()) - out_b.get(src, set()))
        source_new_in = len(in_r.get(src, set()) - in_b.get(src, set()))
        dest_new_in = len(in_r.get(dst, set()) - in_b.get(dst, set()))
        common = src_nr & dst_nr
        aa = sum(1.0 / np.log(len(nbr(und_r, w))) for w in common if len(nbr(und_r, w)) > 1)

        ball = _hop_ball(und_r, {src, dst}, self.hops)
        local_mask = np.array([s in ball and d in ball for s, d in zip(s_r, d_r, strict=False)],
                              dtype=bool) if len(s_r) else np.zeros(0, dtype=bool)
        local_events = int(local_mask.sum())
        local_new = int(n_r[local_mask].sum()) if local_events else 0
        deg_change = float(np.mean([abs(len(nbr(und_r, n)) - len(nbr(und_b, n))) for n in ball])) if ball else 0.0

        chain = sum(1 for x in out_r.get(src, set())
                    if dst in out_r.get(x, set()) and x not in (src, dst))
        out_deg, in_deg = len(out_r.get(src, set())), len(in_r.get(dst, set()))

        return {
            "schema_version": GRAPH_CONTEXT_FEATURES_SCHEMA,
            "relationship_id": str(self.rel[i]),
            "src_asset_id": src, "dst_asset_id": dst,
            "window_start": t, "window_end": self.we[i],
            "lookback_seconds": self.lookback, "hops": self.hops,
            "neighborhood_size": len(ball),
            "source_out_degree_recent": out_deg,
            "source_in_degree_recent": len(in_r.get(src, set())),
            "source_new_out_neighbors_recent": source_new_out,
            "source_new_in_neighbors_recent": source_new_in,
            "source_degree_delta": out_deg - len(out_b.get(src, set())),
            "source_neighbor_set_change": 1.0 - _jaccard(src_nr, src_nb),
            "destination_out_degree_recent": len(out_r.get(dst, set())),
            "destination_in_degree_recent": in_deg,
            "destination_new_in_neighbors_recent": dest_new_in,
            "destination_degree_delta": in_deg - len(in_b.get(dst, set())),
            "destination_neighbor_set_change": 1.0 - _jaccard(dst_nr, dst_nb),
            "historical_peer_overlap": len(common),
            "source_neighbor_similarity": _jaccard(out_r.get(src, set()), out_r.get(dst, set())),
            "destination_neighbor_similarity": _jaccard(in_r.get(src, set()), in_r.get(dst, set())),
            "common_neighbor_count": len(common),
            "causal_jaccard": _jaccard(src_nr, dst_nr),
            "causal_adamic_adar": float(aa),
            "relationships_created_in_local_neighborhood": local_new,
            "local_edge_event_rate": local_events / self.lookback,
            "local_new_edge_rate": local_new / self.lookback,
            "local_degree_change_rate": deg_change,
            "target_structural_novelty": 0.0 if dst in src_nr else 1.0,
            "source_peer_set_novelty": source_new_out / max(1, out_deg),
            "destination_peer_set_novelty": dest_new_in / max(1, in_deg),
            "chain_count": int(chain),
            "chain_support": chain / max(1, out_deg),
            "src_degree_bucket": self._bucket(src, t),
            "dst_degree_bucket": self._bucket(dst, t),
            "hub_involved": self._bucket(src, t) == "hub" or self._bucket(dst, t) == "hub",
        }

    def extract_all(self, *, max_samples: int | None = None, stride: int | None = None) -> pd.DataFrame:
        if stride is None:
            n = len(self.ws) if max_samples is None else min(len(self.ws), max_samples)
            idxs = range(n)
        else:
            idxs = range(0, len(self.ws), max(1, stride))
        return pd.DataFrame([self.extract(i) for i in idxs])


def build_context_features(events: pd.DataFrame, *, lookback_seconds: int = 3600, hops: int = 1,
                           max_samples: int | None = None, stride: int | None = None) -> pd.DataFrame:
    ex = ContextExtractor(events, lookback_seconds=lookback_seconds, hops=hops)
    return ex.extract_all(max_samples=max_samples, stride=stride)
