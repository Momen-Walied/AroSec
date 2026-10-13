"""Node inference: contract, identity preservation, determinism, scenarios."""
from __future__ import annotations

import numpy as np

from ai.contracts.node_anomaly_result import NodeAnomalyResultV1
from ai.edge_behavior.calibration import calibrate
from ai.node_behavior.baselines.statistical import StatisticalNodeModel
from ai.node_behavior.config import NODE_FEATURE_COLUMNS
from ai.node_behavior.evaluation.scenarios import build_node_scenario_frames
from ai.node_behavior.features.builder import (
    build_node_feature_matrix,
    build_node_feature_windows_v2,
)
from ai.node_behavior.inference.scorer import NodeBehaviorScorer
from ai.node_behavior.training.train import feature_config
from tests.ai.node_behavior._helpers import obs


def _sequence():
    return [
        obs(0, "asset:a", "asset:b", dport=443),
        obs(0, "asset:a", "asset:c", dport=445),
        obs(1, "asset:a", "asset:b", dport=443),
        obs(1, "asset:b", "asset:a", dport=80),
        obs(2, "asset:a", "asset:c", proto="UDP", dport=53),
        obs(2, "asset:b", "asset:c", dport=445),
    ]


def _scorer():
    windows = build_node_feature_windows_v2(_sequence())
    X = build_node_feature_matrix(windows)[NODE_FEATURE_COLUMNS].to_numpy(dtype=float)
    model = StatisticalNodeModel().fit(X)
    calib = calibrate(np.clip(model.score(X), 0, 1))
    return NodeBehaviorScorer(model, model, calib, feature_config(),
                              identity_map={"asset:a": {"identity_method": "dataset_ip_fallback",
                                                        "identity_confidence": 0.4}}), windows


def test_score_node_contract_and_identity():
    scorer, windows = _scorer()
    a = next(w for w in windows if w.asset_id == "asset:a")
    result = scorer.score_node(a)
    assert isinstance(result, NodeAnomalyResultV1)
    assert result.asset_id.startswith("asset:")
    assert 0.0 <= result.anomaly_score <= 1.0
    assert result.identity_method == "dataset_ip_fallback"
    assert result.identity_confidence == 0.4
    assert any("window:" in r for r in result.evidence_refs)


def test_inference_deterministic():
    scorer, windows = _scorer()
    a = next(w for w in windows if w.asset_id == "asset:a")
    assert scorer.score_node(a).anomaly_score == scorer.score_node(a).anomaly_score


def test_score_batch_range_and_reasons():
    scorer, windows = _scorer()
    out = scorer.score_batch(windows)
    assert out["anomaly_score"].between(0.0, 1.0).all()
    assert "reasons" in out.columns


def test_new_peer_burst_scenario_detected():
    windows = build_node_feature_windows_v2(_sequence())
    X = build_node_feature_matrix(windows)[NODE_FEATURE_COLUMNS].to_numpy(dtype=float)
    model = StatisticalNodeModel().fit(np.vstack([X, X]))
    threshold = float(np.quantile(np.clip(model.score(X), 0, 1), 0.5))
    frames = build_node_scenario_frames(windows, n_per_scenario=len(windows), seed=1)
    burst = frames["SCN-N01_NEW_PEER_BURST"]
    scored = NodeBehaviorScorer(model, model, calibrate(np.clip(model.score(X), 0, 1)),
                                feature_config()).score_batch(burst)
    assert float((scored["anomaly_score"] >= threshold).mean()) >= 0.5
