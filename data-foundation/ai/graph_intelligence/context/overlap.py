"""Feature-overlap audit: graph features vs existing Edge/Node local features.

We must add graph information, not rename Node/Edge features. For every graph feature we
find its strongest Pearson correlation with an existing local feature (aligned causally) and
classify it DUPLICATE (|r| >= 0.9), DERIVED (0.7 <= |r| < 0.9), or NEW GRAPH INFORMATION.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .scorers import GRAPH_FEATURES

EDGE_COMPARE = ["new_peer", "src_unique_peer_count", "src_new_peer_count",
                "protocol_novelty_count", "port_novelty_count",
                "historical_connection_count", "connections_count"]
NODE_COMPARE = ["unique_outgoing_peers", "new_outgoing_peer_count", "fan_out",
                "unique_incoming_peers", "new_incoming_peer_count", "fan_in",
                "relationship_creation_count"]


def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    if a.size < 3 or b.size < 3:
        return 0.0
    a = a.astype(float)
    b = b.astype(float)
    if a.std() < 1e-12 or b.std() < 1e-12:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def feature_overlap_audit(ctx: pd.DataFrame, edge: pd.DataFrame | None,
                          node: pd.DataFrame | None) -> pd.DataFrame:
    """ctx must carry relationship_id, window_start, src_asset_id, dst_asset_id."""
    base = ctx[["relationship_id", "window_start", "src_asset_id", "dst_asset_id"] + GRAPH_FEATURES]
    rows = []
    merged_edge = None
    if edge is not None and not edge.empty:
        merged_edge = base.merge(edge, on=["relationship_id", "window_start"], how="inner",
                                 suffixes=("", "_e"))
    merged_src = merged_dst = None
    if node is not None and not node.empty:
        merged_src = base.merge(node, left_on=["src_asset_id", "window_start"],
                                right_on=["asset_id", "window_start"], how="inner")
        merged_dst = base.merge(node, left_on=["dst_asset_id", "window_start"],
                                right_on=["asset_id", "window_start"], how="inner")

    for gf in GRAPH_FEATURES:
        best_r, best_name = 0.0, None
        if merged_edge is not None:
            for c in EDGE_COMPARE:
                if c in merged_edge:
                    r = _pearson(merged_edge[gf].to_numpy(), merged_edge[c].to_numpy())
                    if abs(r) > abs(best_r):
                        best_r, best_name = r, f"edge.{c}"
        for m in (merged_src, merged_dst):
            if m is None:
                continue
            for c in NODE_COMPARE:
                if c in m:
                    r = _pearson(m[gf].to_numpy(), m[c].to_numpy())
                    if abs(r) > abs(best_r):
                        best_r, best_name = r, f"node.{c}"
        a = abs(best_r)
        cls = "DUPLICATE" if a >= 0.9 else ("DERIVED" if a >= 0.7 else "NEW GRAPH INFORMATION")
        rows.append({"graph_feature": gf, "closest_existing_feature": best_name,
                     "pearson": round(best_r, 3), "abs_pearson": round(a, 3),
                     "classification": cls})
    return pd.DataFrame(rows).sort_values("abs_pearson", ascending=False).reset_index(drop=True)
