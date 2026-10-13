"""Episode metrics + signal compression (observational; NO attack semantics)."""
from __future__ import annotations

from collections import Counter

import numpy as np


def _pct(values: list[float]) -> dict:
    if not values:
        return {"p50": 0.0, "p90": 0.0, "p95": 0.0, "p99": 0.0}
    a = np.asarray(values, dtype=float)
    return {p: float(np.percentile(a, int(p[1:]))) for p in ("p50", "p90", "p95", "p99")}


def episode_metrics(episodes: list, span_days: float) -> dict:
    n = len(episodes)
    if n == 0:
        return {"episodes": 0}
    durations = [e.duration_seconds for e in episodes]
    signals_per = [e.edge_signal_count + e.node_signal_count for e in episodes]
    assets_per = [len(e.involved_asset_ids) for e in episodes]
    rels_per = [len(e.relationship_ids) for e in episodes]
    edge_only = sum(1 for e in episodes if e.node_signal_count == 0)
    node_only = sum(1 for e in episodes if e.edge_signal_count == 0)
    mixed = sum(1 for e in episodes if e.edge_signal_count > 0 and e.node_signal_count > 0)
    strength = Counter(str(e.evidence_strength) for e in episodes)
    severity = Counter(str(e.episode_severity) for e in episodes)
    families: Counter = Counter()
    for e in episodes:
        for f in e.evidence_families:
            families[f] += 1
    return {
        "episodes": n,
        "episodes_per_site_per_day": n / max(span_days, 1e-9),
        "duration_seconds": _pct(durations),
        "signals_per_episode": _pct(signals_per),
        "mean_signals_per_episode": float(np.mean(signals_per)),
        "assets_per_episode": _pct(assets_per),
        "relationships_per_episode": _pct(rels_per),
        "edge_only_pct": edge_only / n,
        "node_only_pct": node_only / n,
        "mixed_pct": mixed / n,
        "evidence_strength_distribution": dict(strength),
        "severity_distribution": dict(severity),
        "top_evidence_families": families.most_common(10),
        "episodes_with_gt1_asset": sum(1 for a in assets_per if a > 1),
        "episodes_with_gt1_relationship": sum(1 for r in rels_per if r > 1),
    }


def compression_metrics(n_signals: int, episodes: list, span_days: float) -> dict:
    n = len(episodes)
    signals_per = [e.edge_signal_count + e.node_signal_count for e in episodes] or [0]
    return {
        "raw_signals": n_signals,
        "episodes": n,
        "signal_compression_ratio": (n_signals / n) if n else float("inf"),
        "signals_per_day": n_signals / max(span_days, 1e-9),
        "episodes_per_day": n / max(span_days, 1e-9),
        "mean_signals_per_episode": float(np.mean(signals_per)),
        "median_signals_per_episode": float(np.median(signals_per)),
        "p95_signals_per_episode": float(np.percentile(signals_per, 95)),
    }
