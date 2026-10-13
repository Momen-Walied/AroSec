"""Node Behavior inference: NodeFeatureWindowV2 -> NodeAnomalyResultV1."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from ai.contracts.node_anomaly_result import NodeAnomalyReason, NodeAnomalyResultV1
from ai.edge_behavior.calibration import severity_for
from ai.node_behavior.baselines.base import BaseNodeModel
from ai.node_behavior.baselines.statistical import StatisticalNodeModel
from ai.node_behavior.config import NODE_FEATURE_COLUMNS
from ai.node_behavior.features.builder import build_node_feature_matrix
from ai.node_behavior.features.schema import NodeFeatureWindowV2


class NodeBehaviorScorer:
    def __init__(self, model: BaseNodeModel, statistical: StatisticalNodeModel, calibration: dict,
                 feature_config: dict, manifest: dict | None = None,
                 identity_map: dict | None = None) -> None:
        self.model = model
        self.statistical = statistical
        self.calibration = calibration
        self.feature_config = feature_config
        self.manifest = manifest or {}
        self.identity_map = identity_map or {}
        self.model_version = getattr(model, "model_version", "unknown")
        self.severity_thresholds = calibration.get("severity_thresholds", {})

    @classmethod
    def from_artifact(cls, artifact_dir: Path, identity_map: dict | None = None) -> NodeBehaviorScorer:
        artifact_dir = Path(artifact_dir)
        model = BaseNodeModel.load(artifact_dir / "model.joblib")
        statistical = StatisticalNodeModel.load(artifact_dir / "statistical.joblib")
        calibration = json.loads((artifact_dir / "calibration.json").read_text())
        feature_config = json.loads((artifact_dir / "feature_config.json").read_text())
        manifest = {}
        if (artifact_dir / "manifest.json").exists():
            manifest = json.loads((artifact_dir / "manifest.json").read_text())
        return cls(model, statistical, calibration, feature_config, manifest, identity_map)

    def _matrix(self, windows: list[NodeFeatureWindowV2]) -> pd.DataFrame:
        matrix = build_node_feature_matrix(windows)
        missing = [c for c in NODE_FEATURE_COLUMNS if c not in matrix.columns]
        if missing:
            raise ValueError(f"feature schema mismatch: missing {missing}")
        return matrix

    def score_batch(self, windows: list[NodeFeatureWindowV2]) -> pd.DataFrame:
        matrix = self._matrix(windows)
        X = matrix[NODE_FEATURE_COLUMNS].to_numpy(dtype=float)
        scores = np.clip(self.model.score(X), 0.0, 1.0)
        reasons_list, _ = self.statistical.explain_batch(X)
        out = matrix[["asset_id", "window_start"]].copy()
        out["anomaly_score"] = scores
        out["severity"] = [severity_for(float(s), self.severity_thresholds) for s in scores]
        out["reasons"] = reasons_list
        return out.reset_index(drop=True)

    def score_node(self, window: NodeFeatureWindowV2) -> NodeAnomalyResultV1:
        matrix = self._matrix([window])
        X = matrix[NODE_FEATURE_COLUMNS].to_numpy(dtype=float)
        score = float(np.clip(self.model.score(X)[0], 0.0, 1.0))
        reasons_list, feats_list = self.statistical.explain_batch(X)
        identity = self.identity_map.get(window.asset_id, {})
        return NodeAnomalyResultV1(
            model_version=self.model_version,
            asset_id=window.asset_id,
            window_start=window.window_start, window_end=window.window_end,
            anomaly_score=score,
            severity=severity_for(score, self.severity_thresholds),
            reasons=[NodeAnomalyReason(**r) for r in reasons_list[0]],
            feature_contributions=feats_list[0],
            identity_method=identity.get("identity_method"),
            identity_confidence=identity.get("identity_confidence"),
            evidence_refs=[window.asset_id, f"window:{window.window_start.isoformat()}"],
            inference_timestamp=datetime.now(UTC),
        )
