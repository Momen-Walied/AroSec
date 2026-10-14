"""Evaluation harness for Temporal Graph Intelligence v1 (heuristics + scenarios).

Produces the numbers behind ``reports/ai/temporal_graph_design/``. No neural model is
trained or evaluated here — this is the non-GNN bar.
"""
from __future__ import annotations

import numpy as np

from ..baselines.heuristics import GraphHeuristics, build_causal_graph
from ..config import GraphIntelligenceConfig
from ..data.loader import load_edge_features
from ..data.negative_sampling import sample_negatives
from ..data.splits import assign_split, compute_boundaries
from . import metrics
from .scenarios import all_scenarios


def _causal_slice(ws, t, lookback_seconds):
    lo = np.searchsorted(ws, t - np.timedelta64(int(lookback_seconds), "s"), side="left")
    hi = np.searchsorted(ws, t, side="left")
    return lo, hi


def run_link_prediction(cfg: GraphIntelligenceConfig | None = None, *, max_queries: int = 4000,
                        seed: int = 42) -> dict:
    """Self-supervised next-edge ranking: rank the true edge above temporal-safe negatives."""
    cfg = cfg or GraphIntelligenceConfig()
    df = load_edge_features(cfg)
    ws = df.window_start.to_numpy()
    src = df.src_asset_id.to_numpy()
    dst = df.dst_asset_id.to_numpy()
    all_nodes = sorted(set(src.tolist()) | set(dst.tolist()))
    boundaries = compute_boundaries(ws, cfg)
    future_window = np.timedelta64(int(cfg.horizon_windows * cfg.window_seconds), "s")

    n = len(df)
    step = max(1, n // max_queries)
    idxs = list(range(0, n, step))[:max_queries]

    per_heur: dict[str, list] = {}
    by_split: dict[str, dict[str, list]] = {"train": {}, "validation": {}, "test": {}}
    by_cold: dict[str, dict[str, list]] = {}
    neg_category_counts: dict[str, int] = {}

    for i in idxs:
        t = ws[i]
        lo, hi = _causal_slice(ws, t, cfg.lookback_seconds)
        if hi <= lo:
            continue
        s_slice, d_slice, t_slice = src[lo:hi], dst[lo:hi], ws[lo:hi]
        g = build_causal_graph(s_slice, d_slice, t_slice, t)
        known = set(zip(s_slice.tolist(), d_slice.tolist(), strict=False))
        fmask = (ws > t) & (ws <= t + future_window)
        future = set(zip(src[fmask].tolist(), dst[fmask].tolist(), strict=False))

        negs = sample_negatives(src=src[i], dst=dst[i], as_of=str(t), all_nodes=all_nodes,
                                known_edges_before=known, future_edges_within_horizon=future,
                                adjacency=g.adj, k=cfg.negatives_per_positive, seed=seed)
        if not negs:
            continue
        for nb in negs:
            neg_category_counts[nb["category"]] = neg_category_counts.get(nb["category"], 0) + 1

        heur = GraphHeuristics(g)
        pos_scores = heur.all_scores(src[i], dst[i])
        neg_scores = [heur.all_scores(nb["src_asset_id"], nb["dst_asset_id"]) for nb in negs]
        split = str(assign_split(t, boundaries))
        cat = "known_edge" if (src[i], dst[i]) in known else "new_edge"

        for name in GraphHeuristics.NAMES:
            scores = np.array([pos_scores[name]] + [ns[name] for ns in neg_scores], dtype=float)
            per_heur.setdefault(name, []).append((scores, 0))
            by_split[split].setdefault(name, []).append((scores, 0))
            by_cold.setdefault(cat, {}).setdefault(name, []).append((scores, 0))

    ranked = sorted(((k, metrics.ranking_metrics(v)) for k, v in per_heur.items()),
                    key=lambda kv: kv[1]["mrr"], reverse=True)
    return {
        "task": "next_edge_ranking",
        "n_queries": len(next(iter(per_heur.values()))) if per_heur else 0,
        "heuristics": {k: v for k, v in ranked},
        "ranked_by_mrr": [{"heuristic": k, **v} for k, v in ranked],
        "by_split": {s: {k: metrics.ranking_metrics(v) for k, v in d.items()} for s, d in by_split.items()},
        "by_cold_start": {c: {k: metrics.ranking_metrics(v) for k, v in d.items()} for c, d in by_cold.items()},
        "negative_categories": neg_category_counts,
    }


def run_scenarios() -> dict:
    """Score each synthetic structural scenario target with the heuristics."""
    out = {}
    for sc in all_scenarios():
        s = [u for u, _ in sc.history]
        d = [v for _, v in sc.history]
        ws = np.arange(len(sc.history)).astype("timedelta64[s]")
        g = build_causal_graph(s, d, ws, ws[-1] if len(ws) else np.timedelta64(0, "s"))
        out[sc.scenario_id] = {"structurally_unusual": sc.structurally_unusual,
                               "target": list(sc.target),
                               "scores": GraphHeuristics(g).all_scores(*sc.target)}
    return out


if __name__ == "__main__":  # pragma: no cover
    import json

    print(json.dumps(run_link_prediction(), indent=2, default=float))
