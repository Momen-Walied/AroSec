"""Edge Behavior inference: EdgeFeatureWindowV2 -> EdgeAnomalyResultV1."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from ai.contracts.edge_anomaly_result import AnomalyReason, EdgeAnomalyResultV1, IdentityQuality
from ai.edge_behavior.baselines.base import BaseEdgeModel
from ai.edge_behavior.baselines.statistical import StatisticalEdgeModel
from ai.edge_behavior.calibration import severity_for
from ai.edge_behavior.features.builder import FEATURE_COLUMNS, build_feature_matrix


class EdgeBehaviorScorer:
    def __init__(self, model: BaseEdgeModel, statistical: StatisticalEdgeModel, calibration: dict,
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
    def from_artifact(cls, artifact_dir: Path, identity_map: dict | None = None) -> EdgeBehaviorScorer:
        artifact_dir = Path(artifact_dir)
        model = BaseEdgeModel.load(artifact_dir / "model.joblib")
        statistical = StatisticalEdgeModel.load(artifact_dir / "statistical.joblib")
        calibration = json.loads((artifact_dir / "calibration.json").read_text())
        feature_config = json.loads((artifact_dir / "feature_config.json").read_text())
        manifest = {}
        manifest_path = artifact_dir / "manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
        code_schema = feature_config.get("feature_schema_version")
        if code_schema != getattr(model, "feature_schema_version", None):
            raise ValueError(f"feature schema mismatch: artifact={code_schema}")
        return cls(model, statistical, calibration, feature_config, manifest, identity_map)

    def _feature_matrix(self, df: pd.DataFrame) -> pd.DataFrame:
        matrix = build_feature_matrix(df)
        missing = [c for c in FEATURE_COLUMNS if c not in matrix.columns]
        if missing:
            raise ValueError(f"feature schema mismatch: missing columns {missing}")
        return matrix

    def score_batch(self, df: pd.DataFrame) -> pd.DataFrame:
        matrix = self._feature_matrix(df)
        X = matrix[FEATURE_COLUMNS].to_numpy(dtype=float)
        scores = np.clip(self.model.score(X), 0.0, 1.0)
        explained = self.statistical.explain(X)
        comp = explained["component_scores"]
        weights = explained["component_weights"]
        names = explained["component_names"]

        out = matrix[["relationship_id", "src_asset_id", "dst_asset_id",
                      "window_start", "window_end"]].copy()
        out["anomaly_score"] = scores
        out["severity"] = [severity_for(float(s), self.severity_thresholds) for s in scores]
        reasons_col = []
        for i in range(len(out)):
            contrib = comp[i] * weights
            order = np.argsort(-contrib)
            reasons_col.append([
                {"code": names[j], "contribution": float(contrib[j])}
                for j in order[:5] if contrib[j] > 1e-6
            ])
        out["reasons"] = reasons_col
        return out.reset_index(drop=True)

    def score_edge(self, edge_feature_window: dict | pd.Series,
                   history: pd.DataFrame | None = None) -> EdgeAnomalyResultV1:
        row = dict(edge_feature_window)
        frame = pd.DataFrame([row])
        if history is not None and not history.empty:
            rel = row.get("relationship_id")
            prior = history[(history["relationship_id"] == rel) &
                            (pd.to_datetime(history["window_start"], utc=True)
                             < pd.to_datetime(row["window_start"], utc=True))]
            if not prior.empty:
                frame = pd.concat([prior, frame], ignore_index=True)
                target_index = len(frame) - 1
            else:
                target_index = 0
        else:
            target_index = 0

        matrix = self._feature_matrix(frame)
        X = matrix[FEATURE_COLUMNS].to_numpy(dtype=float)
        score = float(np.clip(self.model.score(X)[target_index], 0.0, 1.0))
        reasons = [AnomalyReason(**r) for r in self.statistical.reasons_for(X, target_index)]
        contributions = self.statistical.feature_contributions(X, target_index)

        src = str(row.get("src_asset_id", ""))
        identity = self.identity_map.get(src, {})
        identity_quality = IdentityQuality(
            identity_method=identity.get("identity_method"),
            identity_confidence=identity.get("identity_confidence"),
            identity_is_provisional=str(identity.get("identity_method", "")).endswith(
                ("ip_fallback", "ip_only_observation")
            ) or identity.get("identity_method") is None,
        )
        evidence_refs = [
            str(row.get("relationship_id", "")),
            f"window:{pd.to_datetime(row['window_start'], utc=True).isoformat()}",
            f"src:{src}",
            f"dst:{row.get('dst_asset_id', '')}",
        ]
        return EdgeAnomalyResultV1(
            model_version=self.model_version,
            relationship_id=str(row["relationship_id"]),
            window_start=pd.to_datetime(row["window_start"], utc=True).to_pydatetime(),
            window_end=pd.to_datetime(row["window_end"], utc=True).to_pydatetime(),
            anomaly_score=score,
            severity=severity_for(score, self.severity_thresholds),
            reasons=reasons,
            feature_contributions=contributions,
            evidence_refs=evidence_refs,
            identity_quality=identity_quality,
            inference_timestamp=datetime.now(UTC),
        )
