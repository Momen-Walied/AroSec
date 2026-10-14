"""Structural diversity metrics for graph readiness (framework-independent)."""
from __future__ import annotations

from collections import defaultdict, deque

import numpy as np
import pandas as pd


def _undirected_adj(src, dst) -> dict[str, set[str]]:
    adj: dict[str, set[str]] = defaultdict(set)
    for u, v in zip(src, dst, strict=False):
        if u == v:
            continue
        adj[u].add(v)
        adj[v].add(u)
    return dict(adj)


def _components(nodes, adj) -> list[int]:
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
            for y in adj.get(x, ()):
                if y not in seen:
                    seen.add(y)
                    c += 1
                    q.append(y)
        sizes.append(c)
    return sorted(sizes, reverse=True)


def _khops(adj, n, k) -> int:
    seen = {n}
    frontier = {n}
    for _ in range(k):
        nxt: set[str] = set()
        for x in frontier:
            for y in adj.get(x, ()):
                if y not in seen:
                    seen.add(y)
                    nxt.add(y)
        frontier = nxt
    return len(seen) - 1


def _entropy(degrees) -> float:
    d = np.asarray(degrees, dtype=float)
    if d.sum() <= 0:
        return 0.0
    p = d / d.sum()
    p = p[p > 0]
    h = -float((p * np.log(p)).sum())
    return h / np.log(len(d)) if len(d) > 1 else 0.0


def _assortativity(pairs, deg) -> float:
    a = np.array([deg[u] for u, _ in pairs], dtype=float)
    b = np.array([deg[v] for _, v in pairs], dtype=float)
    if a.std() < 1e-12 or b.std() < 1e-12 or len(a) < 3:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def _clustering(adj) -> float:
    vals = []
    for nbrs in adj.values():
        k = len(nbrs)
        if k < 2:
            continue
        links = sum(1 for a in nbrs for b in nbrs if a < b and b in adj.get(a, ()))
        vals.append(2 * links / (k * (k - 1)))
    return float(np.mean(vals)) if vals else 0.0


def compute_structural_metrics(df: pd.DataFrame) -> dict:
    """df: edge_features (relationship_id, src_asset_id, dst_asset_id, window_start, ...)."""
    pairs_series = df[["src_asset_id", "dst_asset_id"]].drop_duplicates()
    pairs = list(zip(pairs_series.src_asset_id, pairs_series.dst_asset_id, strict=False))
    nodes = sorted(set(df.src_asset_id) | set(df.dst_asset_id))
    adj = _undirected_adj(df.src_asset_id.to_numpy(), df.dst_asset_id.to_numpy())
    deg = {n: len(adj.get(n, ())) for n in nodes}

    comps = _components(nodes, adj)
    core_nodes = [n for n in nodes if deg[n] >= 2]
    core_adj = {n: {m for m in adj.get(n, ()) if deg[m] >= 2} for n in core_nodes}
    core_comps = _components(core_nodes, core_adj) if core_nodes else []

    # hub dominance measured on edge-WINDOWS (incidence share)
    inc = defaultdict(int)
    for u, v in zip(df.src_asset_id, df.dst_asset_id, strict=False):
        inc[u] += 1
        inc[v] += 1
    total_inc = sum(inc.values()) or 1
    ranked = sorted(inc.values(), reverse=True)
    top1 = ranked[0] / total_inc if ranked else 0.0
    top5 = sum(ranked[:5]) / total_inc if ranked else 0.0

    hub_threshold = max(float(np.quantile(list(deg.values()), 0.95)), 5.0)
    hub_nodes = {n for n in nodes if deg[n] >= hub_threshold}
    both_non_hub = int(sum(1 for u, v in zip(df.src_asset_id, df.dst_asset_id, strict=False)
                           if u not in hub_nodes and v not in hub_nodes))

    one = np.array([len(adj.get(n, ())) for n in nodes])
    two = np.array([_khops(adj, n, 2) for n in nodes])

    new_edges = int(df.groupby("relationship_id").cumcount().eq(0).sum())
    # relationships that go inactive (>24h gap) and reappear
    gaps = df.sort_values("window_start").groupby("relationship_id").window_start.diff().dt.total_seconds()
    reappearing = int((gaps > 86400).sum())

    return {
        "node_count": len(nodes),
        "edge_count": len(pairs),
        "density": round(len(pairs) / (len(nodes) * (len(nodes) - 1)), 6) if len(nodes) > 1 else 0.0,
        "weak_components": len(comps),
        "largest_component_share": round(comps[0] / len(nodes), 4) if comps else 0.0,
        "degree_p50": int(np.median(one)), "degree_p90": int(np.quantile(one, 0.9)),
        "degree_max": int(one.max()),
        "degree_entropy": round(_entropy(list(deg.values())), 4),
        "hub_dominance_top1": round(top1, 4),
        "hub_dominance_top5": round(top5, 4),
        "hub_node_count": len(hub_nodes),
        "assortativity": round(_assortativity(pairs, deg), 4),
        "avg_clustering": round(_clustering(adj), 4),
        "core_components": len(core_comps),
        "core_component_sizes": core_comps[:10],
        "independent_local_neighborhoods": len(core_comps),
        "mean_1hop": round(float(one.mean()), 3),
        "mean_2hop": round(float(two.mean()), 3),
        "two_hop_minus_one_hop": round(float((two - one).mean()), 3),
        "new_edge_count": new_edges,
        "reappearing_relationships": reappearing,
        "non_hub_target_edges": both_non_hub,
        "non_hub_edge_share": round(both_non_hub / max(len(df), 1), 6),
    }
