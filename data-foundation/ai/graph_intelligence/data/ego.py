"""Causal ego / local temporal subgraph extraction.

The extraction is STRICTLY causal: a sample at ``as_of`` sees only events with
``window_start < as_of`` (never the target itself, never a future edge, never a future
neighbor). This is the enforcement point for leakage classes A/C/D/E in
``docs/TEMPORAL_GRAPH_LEAKAGE_MODEL.md``.
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np


def build_undirected_adjacency(src: np.ndarray, dst: np.ndarray) -> dict[str, set[str]]:
    adj: dict[str, set[str]] = defaultdict(set)
    for u, v in zip(src, dst, strict=False):
        if u == v:
            continue
        adj[u].add(v)
        adj[v].add(u)
    return adj


def hop_ball(adj: dict[str, set[str]], origins: set[str], hops: int) -> set[str]:
    """Nodes within ``hops`` undirected hops of any origin (origins included)."""
    seen = set(origins)
    frontier = set(origins)
    for _ in range(hops):
        nxt: set[str] = set()
        for n in frontier:
            for m in adj.get(n, ()):  # type: ignore[arg-type]
                if m not in seen:
                    seen.add(m)
                    nxt.add(m)
        frontier = nxt
        if not frontier:
            break
    return seen


def extract_ego(
    *,
    as_of,
    src: str,
    dst: str,
    lookback_seconds: int,
    hops: int,
    max_neighbors: int,
    max_events: int,
    event_windows: np.ndarray,
    event_src: np.ndarray,
    event_dst: np.ndarray,
    event_ids: np.ndarray,
    last_seen_by_rel: dict[str, np.datetime64] | None = None,
    relationship_id: str | None = None,
) -> dict:
    """Return the causal neighborhood for one target edge-window at ``as_of``.

    Only events with ``as_of - lookback <= window_start < as_of`` are eligible.
    """
    lo = np.datetime64(as_of) - np.timedelta64(int(lookback_seconds), "s")
    mask = (event_windows >= lo) & (event_windows < np.datetime64(as_of))
    idx = np.nonzero(mask)[0]
    if idx.size > max_events:  # deterministic recency-truncation
        idx = idx[-max_events:]

    c_src, c_dst = event_src[idx], event_dst[idx]
    adj = build_undirected_adjacency(c_src, c_dst)
    reach = hop_ball(adj, {src, dst}, hops)
    reach = {n for n in reach if n != src and n != dst}

    # causal events are those entirely inside the hop ball (both endpoints reached)
    keep = [(int(i), s, d) for i, s, d in zip(idx, c_src, c_dst, strict=False) if s in reach and d in reach]
    causal_event_ids = [str(event_ids[i]) for i, _, _ in keep]
    span = None
    if keep:
        span = float((np.datetime64(as_of) - event_windows[[i for i, _, _ in keep]].min())
                     / np.timedelta64(1, "s"))

    delta = None
    if last_seen_by_rel and relationship_id and relationship_id in last_seen_by_rel:
        delta = float((np.datetime64(as_of) - last_seen_by_rel[relationship_id])
                      / np.timedelta64(1, "s"))

    neighbors = sorted(reach)[:max_neighbors]
    return {
        "neighbor_node_ids": neighbors,
        "causal_event_ids": causal_event_ids[:max_events],
        "target_delta_s": delta,
        "neighborhood_span_s": span,
    }
