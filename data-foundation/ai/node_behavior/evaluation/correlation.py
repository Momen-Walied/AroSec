"""Cross-model correlation between Edge and Node anomaly scores (complementarity, not causation)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 2 or np.std(a) == 0 or np.std(b) == 0:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 2:
        return 0.0
    ra = pd.Series(a).rank().to_numpy()
    rb = pd.Series(b).rank().to_numpy()
    return _pearson(ra, rb)


def window_correlation(edge_scored: pd.DataFrame, node_scored: pd.DataFrame,
                       edge_threshold: float, node_threshold: float) -> dict:
    """Aggregate to window level (max score per window) and compare."""
    e = edge_scored.copy()
    n = node_scored.copy()
    e["win"] = pd.to_datetime(e["window_start"], utc=True)
    n["win"] = pd.to_datetime(n["window_start"], utc=True)
    e_win = e.groupby("win")["anomaly_score"].max()
    n_win = n.groupby("win")["anomaly_score"].max()
    joined = pd.concat([e_win.rename("edge"), n_win.rename("node")], axis=1).dropna()
    if joined.empty:
        return {"windows": 0}
    ev = joined["edge"].to_numpy()
    nv = joined["node"].to_numpy()
    e_high = ev >= edge_threshold
    n_high = nv >= node_threshold
    return {
        "windows": int(len(joined)),
        "pearson": _pearson(ev, nv),
        "spearman": _spearman(ev, nv),
        "pct_high_node_with_high_edge": float((e_high & n_high).sum() / max(n_high.sum(), 1)),
        "pct_high_edge_while_node_normal": float((e_high & ~n_high).sum() / max(e_high.sum(), 1)),
        "pct_high_node_while_edge_normal": float((n_high & ~e_high).sum() / max(n_high.sum(), 1)),
    }


def entity_edge_alignment(edge_scored: pd.DataFrame, node_scored: pd.DataFrame,
                          edge_threshold: float, node_threshold: float) -> dict:
    """At window level, do edge alerts occur on the same windows as node alerts?"""
    e = edge_scored.copy()
    e["win"] = pd.to_datetime(e["window_start"], utc=True)
    e_high_windows = set(e.loc[e["anomaly_score"] >= edge_threshold, "win"])
    n = node_scored.copy()
    n["win"] = pd.to_datetime(n["window_start"], utc=True)
    n_high_windows = set(n.loc[n["anomaly_score"] >= node_threshold, "win"])
    return {
        "edge_high_windows": len(e_high_windows),
        "node_high_windows": len(n_high_windows),
        "overlap_windows": len(e_high_windows & n_high_windows),
        "edge_only_windows": len(e_high_windows - n_high_windows),
        "node_only_windows": len(n_high_windows - e_high_windows),
    }
