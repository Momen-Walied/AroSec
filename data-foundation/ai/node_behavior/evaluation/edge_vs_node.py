"""Edge Behavior v1 vs Node Behavior v1 head-to-head on equivalent anomaly families.

Both sides use their interpretable statistical models so the comparison is like-for-like.
Node scenarios SCN-N* are mapped to the equivalent edge scenarios SCN-* (Phase 1).
"""
from __future__ import annotations

import pandas as pd

from ai.edge_behavior.baselines.base import BaseEdgeModel
from ai.edge_behavior.evaluation.scenarios import build_scenario_frames
from ai.edge_behavior.features.builder import FEATURE_COLUMNS as EDGE_COLS
from ai.edge_behavior.features.builder import build_feature_matrix
from ai.node_behavior.evaluation.scenarios import build_node_scenario_frames
from ai.node_behavior.inference.scorer import NodeBehaviorScorer
from src.config import PROJECT_ROOT

# node scenario -> equivalent edge scenario (Phase 1)
NODE_TO_EDGE = {
    "SCN-N01_NEW_PEER_BURST": "SCN-001_NEW_PEER",
    "SCN-N02_FAN_OUT_BURST": "SCN-004_FAN_OUT_BURST",
    "SCN-N03_PROTOCOL_SHIFT": "SCN-003_NEW_PROTOCOL",
    "SCN-N04_PORT_DIVERSITY_BURST": "SCN-002_NEW_PORT",
    "SCN-N05_OUTBOUND_VOLUME_SPIKE": "SCN-005_TRAFFIC_VOLUME_SPIKE",
    "SCN-N06_PEER_SET_REPLACEMENT": "SCN-001_NEW_PEER",
    "SCN-N07_INBOUND_TARGETING": "SCN-001_NEW_PEER",
    "SCN-N08_COMPOUND": "SCN-006_COMPOUND",
}


def _edge_test_frame(dataset: str, window: str) -> pd.DataFrame:
    path = PROJECT_ROOT / "data" / "processed" / "v2" / "edge_features" / f"{dataset}_{window}.parquet"
    df = pd.read_parquet(path)
    df["window_start"] = pd.to_datetime(df["window_start"], utc=True)
    return df


def compare(node_scorer: NodeBehaviorScorer, node_threshold: float,
            dataset: str = "unsw_iotraffic", window: str = "30s",
            node_test_windows=None, n: int = 300, seed: int = 7) -> dict:
    edge_model = BaseEdgeModel.load(PROJECT_ROOT / "ai/edge_behavior/artifacts/edge_behavior/edge-stat-v1/model.joblib")
    import json
    edge_cal = json.loads((PROJECT_ROOT / "ai/edge_behavior/artifacts/edge_behavior/edge-stat-v1/calibration.json").read_text())
    edge_threshold = edge_cal["threshold"]

    edge_df = _edge_test_frame(dataset, window)
    edge_frames = build_scenario_frames(edge_df, n, seed=seed)
    edge_det = {}
    for scen, frame in edge_frames.items():
        X = build_feature_matrix(frame)[EDGE_COLS].to_numpy(dtype=float)
        edge_det[scen] = float((edge_model.score(X) >= edge_threshold).mean())

    node_frames = build_node_scenario_frames(node_test_windows, n, seed=seed)
    node_det = {}
    for scen, windows in node_frames.items():
        scored = node_scorer.score_batch(windows)
        node_det[scen] = float((scored["anomaly_score"] >= node_threshold).mean())

    rows = {}
    for nscen, escen in NODE_TO_EDGE.items():
        rows[nscen] = {"node_detection": node_det.get(nscen, 0.0),
                       "edge_detection": edge_det.get(escen, 0.0),
                       "edge_scenario": escen}
    return {"thresholds": {"node": node_threshold, "edge": edge_threshold}, "comparison": rows}
