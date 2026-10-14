"""Temporal diversity metrics for graph readiness."""
from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd


def compute_temporal_metrics(df: pd.DataFrame) -> dict:
    df = df.sort_values("window_start")
    span_days = float((df.window_end.max() - df.window_start.min()).total_seconds() / 86400)

    first = df.groupby("relationship_id").window_start.min()
    births = first.dt.floor("D").value_counts()
    # inactivity transitions: consecutive gaps > 1h and > 24h
    gaps = df.groupby("relationship_id").window_start.diff().dt.total_seconds().dropna()
    inactive_1h = int((gaps > 3600).sum())
    inactive_24h = int((gaps > 86400).sum())

    epw = df.groupby("window_start").size()
    p99 = float(epw.quantile(0.99))
    burst_windows = int((epw >= p99).sum())

    new_peer_events = int(df["new_peer"].sum()) if "new_peer" in df else 0

    # peer-set turnover per node (first half vs second half of its peer sets)
    mid = df.window_start.min() + (df.window_end.max() - df.window_start.min()) / 2
    first_half = df[df.window_start <= mid]
    second_half = df[df.window_start > mid]

    def _peers(frame):
        m = defaultdict(set)
        for s, d in zip(frame.src_asset_id, frame.dst_asset_id, strict=False):
            m[s].add(d)
            m[d].add(s)
        return m

    p1, p2 = _peers(first_half), _peers(second_half)
    turns = []
    for n in set(p1) | set(p2):
        a, b = p1.get(n, set()), p2.get(n, set())
        u = a | b
        turns.append(0.0 if not u else 1.0 - len(a & b) / len(u))
    turnover = float(np.mean(turns)) if turns else 0.0

    # persistent-edge 2-hop chains (A->B->C)
    edges = set(zip(df.src_asset_id, df.dst_asset_id, strict=False))
    out_map: dict[str, set[str]] = defaultdict(set)
    for a, b in edges:
        out_map[a].add(b)
    chains = sum(len(out_map.get(b, ())) for _, b in edges)

    return {
        "span_days": round(span_days, 3),
        "relationship_births": int(len(first)),
        "relationship_births_per_day": round(float(births.mean()), 3) if len(births) else 0.0,
        "days_with_births": int(len(births)),
        "inactivity_transitions_1h": inactive_1h,
        "inactivity_transitions_24h": inactive_24h,
        "new_peer_events": new_peer_events,
        "burst_windows": burst_windows,
        "chain_formations": int(chains),
        "peer_set_turnover": round(turnover, 4),
    }
