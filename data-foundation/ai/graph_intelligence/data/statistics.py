"""Graph statistics for the current temporal asset-communication graph.

All figures are computed from the frozen/derived v0.2 tables and are meant to ground the
design decisions (sample representation, hop count, lookback) rather than to be pretty.
"""
from __future__ import annotations

from collections import defaultdict, deque

import numpy as np

from ..config import GraphIntelligenceConfig
from .loader import load_edge_features, load_relationships

LOOKBACKS = {"5min": 300, "30min": 1800, "1h": 3600, "6h": 21600, "24h": 86400}


def _components(nodes: list[str], adj: dict[str, set[str]]) -> list[int]:
    seen: set[str] = set()
    sizes: list[int] = []
    for n in nodes:
        if n in seen:
            continue
        q = deque([n])
        seen.add(n)
        c = 1
        while q:
            x = q.popleft()
            for y in adj.get(x, ()):  # type: ignore[arg-type]
                if y not in seen:
                    seen.add(y)
                    c += 1
                    q.append(y)
        sizes.append(c)
    return sorted(sizes, reverse=True)


def _khops(adj: dict[str, set[str]], n: str, k: int) -> int:
    seen = {n}
    frontier = {n}
    for _ in range(k):
        nxt: set[str] = set()
        for x in frontier:
            for y in adj.get(x, ()):  # type: ignore[arg-type]
                if y not in seen:
                    seen.add(y)
                    nxt.add(y)
        frontier = nxt
    return len(seen) - 1


def _q(a: np.ndarray, ps=(0.5, 0.9, 0.99)) -> dict:
    if a.size == 0:
        return {f"p{int(p*100)}": None for p in ps}
    return {**{f"p{int(p*100)}": float(np.quantile(a, p)) for p in ps}, "max": float(a.max())}


def compute_graph_statistics(cfg: GraphIntelligenceConfig, *, lookback_sample_step: int = 25) -> dict:
    df = load_edge_features(cfg)
    rel = load_relationships(cfg)

    nodes = sorted(set(df.src_asset_id) | set(df.dst_asset_id))
    pairs = df[["src_asset_id", "dst_asset_id"]].drop_duplicates()
    n, e = len(nodes), len(pairs)

    adj: dict[str, set[str]] = defaultdict(set)
    for u, v in zip(pairs.src_asset_id, pairs.dst_asset_id, strict=False):
        adj[u].add(v)
        adj[v].add(u)

    outdeg = df.groupby("src_asset_id").dst_asset_id.nunique().to_numpy()
    indeg = df.groupby("dst_asset_id").src_asset_id.nunique().to_numpy()

    lifetime_days = ((rel.last_seen - rel.first_seen).dt.total_seconds() / 86400).to_numpy()
    edge_windows_per_rel = df.groupby("relationship_id").size().to_numpy()

    span_days = float((df.window_end.max() - df.window_start.min()).total_seconds() / 86400)
    distinct_windows = int(df.window_start.nunique())
    expected_windows = int(round((df.window_end.max() - df.window_start.min()).total_seconds() / cfg.window_seconds))

    epw = df.groupby("window_start").size().to_numpy()
    newrel = rel.copy()
    newrel["day"] = newrel.first_seen.dt.floor("D")
    new_per_day = newrel.groupby("day").size()

    one_hop = np.array([len(adj[x]) for x in nodes])
    two_hop = np.array([_khops(adj, x, 2) for x in nodes])

    # lookback analysis (distinct causal edges / neighbors seen per target)
    df_sorted = df.sort_values("window_start").reset_index(drop=True)
    sample = df_sorted.iloc[::lookback_sample_step]
    ws = df_sorted.window_start.to_numpy()
    ss = df_sorted.src_asset_id.to_numpy()
    dd = df_sorted.dst_asset_id.to_numpy()
    lookback_stats: dict[str, dict] = {}
    for label, sec in LOOKBACKS.items():
        edges_hist, nbr_hist = [], []
        for t in sample.window_start.to_numpy():
            lo = t - np.timedelta64(int(sec), "s")
            m = (ws >= lo) & (ws < t)
            e_pairs = set(zip(ss[m].tolist(), dd[m].tolist(), strict=False))
            edges_hist.append(len(e_pairs))
            nb: set[str] = set()
            for a, b in e_pairs:
                nb.add(a)
                nb.add(b)
            nbr_hist.append(len(nb))
        lookback_stats[label] = {"edges": _q(np.array(edges_hist), (0.5, 0.9)),
                                 "neighbors": _q(np.array(nbr_hist), (0.5, 0.9))}

    return {
        "dataset_id": cfg.dataset_id,
        "window_label": cfg.window_label,
        "time_range": {"start": str(df.window_start.min()), "end": str(df.window_end.max()),
                       "span_days": round(span_days, 3)},
        "nodes": n,
        "directed_edges": int(e),
        "density_directed": round(e / (n * (n - 1)), 6) if n > 1 else 0.0,
        "edge_instances": int(len(df)),
        "observations_span_windows": {"distinct": distinct_windows, "expected": expected_windows,
                                      "occupancy": round(distinct_windows / expected_windows, 4)},
        "degree": {"out": _q(outdeg, (0.5, 0.9)),
                   "in": _q(indeg, (0.5, 0.9)),
                   "out_mean": round(float(outdeg.mean()), 3), "in_mean": round(float(indeg.mean()), 3)},
        "neighborhood": {"one_hop": _q(one_hop, (0.5, 0.9)),
                         "two_hop": _q(two_hop, (0.5, 0.9))},
        "relationship_lifetime_days": _q(lifetime_days, (0.5, 0.9)),
        "edge_windows_per_relationship": _q(edge_windows_per_rel, (0.5, 0.9)),
        "new_relationships": {"total": int(len(rel)), "days_with_new": int(new_per_day.size),
                              "mean_per_active_day": round(float(new_per_day.mean()), 3)},
        "edges_per_window": _q(epw, (0.5, 0.9)),
        "connected_components_undirected": _components(nodes, adj),
        "reciprocity": {"reciprocal_edges": int(sum(
            1 for u, v in zip(pairs.src_asset_id, pairs.dst_asset_id, strict=False)
            if (v, u) in set(zip(pairs.src_asset_id, pairs.dst_asset_id, strict=False)))),
            "of": int(e)},
        "lookback_neighborhood": lookback_stats,
    }
