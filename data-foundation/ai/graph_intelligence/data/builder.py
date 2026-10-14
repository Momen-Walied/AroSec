"""Deterministic, versioned Temporal Graph dataset builder (framework-independent).

Consumes frozen/derived v0.2 tables and writes canonical artifacts:

    nodes.parquet      NodeIndexEntry rows (asset index)
    events.parquet     TemporalEdgeEvent rows (causal event stream, edge features)
    samples.parquet    TemporalGraphSampleV1 rows (causal ego subgraphs)
    targets.parquet    GraphTarget rows (self-supervised next-edge labels)
    metadata.json      config + boundaries + schema + deterministic ids

No PyG/DGL/NumPy-framework objects are persisted. Sort order is (window_start,
event_id) everywhere; ids are deterministic (see ``contracts.py``).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..config import GraphIntelligenceConfig
from ..contracts import ColdStartCategory, event_id_for, sample_id_for, target_id_for
from .loader import EDGE_FEATURE_COLUMNS, load_edge_features
from .splits import assign_split, compute_boundaries

BUILD_ROOT = Path(__file__).resolve().parent / "build"


def build_events(cfg: GraphIntelligenceConfig, df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["window_start", "relationship_id"], kind="mergesort").reset_index(drop=True)
    first = df.groupby("relationship_id").cumcount() == 0
    ev = pd.DataFrame({
        "event_id": [event_id_for(r, w) for r, w in zip(df.relationship_id, df.window_start, strict=False)],
        "relationship_id": df.relationship_id,
        "src_asset_id": df.src_asset_id,
        "dst_asset_id": df.dst_asset_id,
        "window_start": df.window_start,
        "window_end": df.window_end,
        "is_new_relationship": first.to_numpy(),
        "new_peer": df["new_peer"].astype(bool),
    })
    for c in EDGE_FEATURE_COLUMNS:
        ev[c] = df[c].astype(float) if df[c].dtype != bool else df[c]
    return ev


def build_nodes(cfg: GraphIntelligenceConfig, events: pd.DataFrame) -> pd.DataFrame:
    first = events.groupby("src_asset_id").window_start.min()
    last = events.groupby("src_asset_id").window_start.max()
    d_first = events.groupby("dst_asset_id").window_start.min()
    d_last = events.groupby("dst_asset_id").window_start.max()
    nodes = sorted(set(events.src_asset_id) | set(events.dst_asset_id))
    rows = []
    for i, n in enumerate(nodes):
        fs = min(first.get(n, d_first.get(n)), d_first.get(n, first.get(n)))
        ls = max(last.get(n, d_last.get(n)), d_last.get(n, last.get(n)))
        rows.append({"node_id": n, "node_index": i, "first_seen": fs, "last_seen": ls,
                     "identity_method": "dataset_ip_fallback", "identity_confidence": 0.5,
                     "identity_is_provisional": True})
    return pd.DataFrame(rows)


def _cold_start(src_seen_before: bool, dst_seen_before: bool, edge_seen_before: bool) -> str:
    if not src_seen_before and not dst_seen_before:
        return ColdStartCategory.NEW_NODE_NEW_EDGE
    if not (src_seen_before and dst_seen_before):
        return ColdStartCategory.NEW_NODE_KNOWN_NETWORK
    if not edge_seen_before:
        return ColdStartCategory.KNOWN_NODE_NEW_EDGE
    return ColdStartCategory.KNOWN_NODE_KNOWN_EDGE


def build_samples(cfg: GraphIntelligenceConfig, events: pd.DataFrame, *, max_samples: int | None = None) -> pd.DataFrame:
    ws = events.window_start.to_numpy()
    src = events.src_asset_id.to_numpy()
    dst = events.dst_asset_id.to_numpy()
    eid = events.event_id.to_numpy()
    new_rel = events.is_new_relationship.to_numpy()
    rel = events.relationship_id.to_numpy()

    boundaries = compute_boundaries(ws, cfg)

    # node first-seen (for cold-start categories)
    node_first: dict[str, np.datetime64] = {}
    for s, d, t in zip(src, dst, ws, strict=False):
        for n in (s, d):
            if n not in node_first or t < node_first[n]:
                node_first[n] = t
    rel_first: dict[str, np.datetime64] = {}
    for r, t in zip(rel, ws, strict=False):
        if r not in rel_first or t < rel_first[r]:
            rel_first[r] = t

    rows = []
    order = range(len(events)) if max_samples is None else range(min(len(events), max_samples))
    for i in order:
        t = ws[i]
        lo = np.searchsorted(ws, t - np.timedelta64(cfg.lookback_seconds, "s"), side="left")
        hi = np.searchsorted(ws, t, side="left")  # strictly before the target window
        if hi <= lo:
            ego = {"neighbor_node_ids": [], "causal_event_ids": [], "target_delta_s": None,
                   "neighborhood_span_s": None}
        else:
            s = src[lo:hi]
            d = dst[lo:hi]
            ego = {
                "neighbor_node_ids": sorted(set(s.tolist()) | set(d.tolist())),
                "causal_event_ids": [str(x) for x in eid[lo:hi]],
                "target_delta_s": None,
                "neighborhood_span_s": float((t - ws[lo]) / np.timedelta64(1, "s")),
            }
        src_seen = bool(node_first.get(src[i], t) < t)
        dst_seen = bool(node_first.get(dst[i], t) < t)
        edge_seen = bool(rel_first.get(rel[i], t) < t)
        row = {
            "sample_id": sample_id_for(str(eid[i]), cfg.hops, cfg.lookback_seconds),
            "representation": cfg.representation,
            "target_event_id": str(eid[i]),
            "relationship_id": str(rel[i]),
            "src_asset_id": str(src[i]),
            "dst_asset_id": str(dst[i]),
            "as_of": t,
            "hops": cfg.hops,
            "lookback_seconds": cfg.lookback_seconds,
            "neighbor_node_ids": ego["neighbor_node_ids"],
            "causal_event_ids": ego["causal_event_ids"],
            "target_delta_s": ego["target_delta_s"],
            "neighborhood_span_s": ego["neighborhood_span_s"],
            "split": str(assign_split(t, boundaries)),
            "cold_start_category": _cold_start(src_seen, dst_seen, edge_seen),
            "identity_method": "dataset_ip_fallback",
            "identity_confidence": 0.5,
            "is_new_edge": bool(new_rel[i]),
        }
        rows.append(row)
    return pd.DataFrame(rows), boundaries


def build_targets(samples: pd.DataFrame, cfg: GraphIntelligenceConfig) -> pd.DataFrame:
    rows = []
    for r in samples.itertuples(index=False):
        rows.append({
            "target_id": target_id_for(r.sample_id, 1, cfg.horizon_windows),
            "sample_id": r.sample_id,
            "task": "next_edge",
            "relationship_id": r.relationship_id,
            "src_asset_id": r.src_asset_id,
            "dst_asset_id": r.dst_asset_id,
            "as_of": r.as_of,
            "horizon_windows": cfg.horizon_windows,
            "label": 1,
            "label_kind": "positive_observed",
            "scenario_id": None,
        })
    return pd.DataFrame(rows)


def build(cfg: GraphIntelligenceConfig | None = None, *, max_samples: int | None = None) -> dict:
    cfg = cfg or GraphIntelligenceConfig()
    cfg.validate()
    out = BUILD_ROOT / f"{cfg.dataset_id}_{cfg.window_label}"
    out.mkdir(parents=True, exist_ok=True)

    raw = load_edge_features(cfg)
    events = build_events(cfg, raw)
    nodes = build_nodes(cfg, events)
    samples, boundaries = build_samples(cfg, events, max_samples=max_samples)
    targets = build_targets(samples, cfg)

    events.to_parquet(out / "events.parquet", index=False)
    nodes.to_parquet(out / "nodes.parquet", index=False)
    samples.to_parquet(out / "samples.parquet", index=False)
    targets.to_parquet(out / "targets.parquet", index=False)

    meta = {
        "config": cfg.to_metadata(),
        "split_boundaries": boundaries.as_dict(),
        "counts": {"nodes": int(len(nodes)), "events": int(len(events)),
                   "samples": int(len(samples)), "targets": int(len(targets))},
        "schema": {
            "nodes": list(nodes.columns), "events": list(events.columns),
            "samples": list(samples.columns), "targets": list(targets.columns),
        },
        "cold_start": samples.cold_start_category.value_counts().to_dict(),
        "splits": samples.split.value_counts().to_dict(),
        "output_dir": str(out),
    }
    (out / "metadata.json").write_text(json.dumps(meta, indent=2, default=str))
    return meta


def main() -> None:  # pragma: no cover - CLI
    import argparse

    ap = argparse.ArgumentParser(description="Build the Temporal Graph dataset")
    ap.add_argument("--dataset", default="unsw_iotraffic")
    ap.add_argument("--window", default="30s")
    ap.add_argument("--max-samples", type=int, default=None)
    a = ap.parse_args()
    cfg = GraphIntelligenceConfig(dataset_id=a.dataset, window_label=a.window)
    print(json.dumps(build(cfg, max_samples=a.max_samples), indent=2, default=str))


if __name__ == "__main__":  # pragma: no cover
    main()
