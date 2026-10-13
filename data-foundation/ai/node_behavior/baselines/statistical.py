"""Statistical node baseline: robust per-feature deviation + interpretable components."""
from __future__ import annotations

import numpy as np

from ai.node_behavior.baselines.base import BaseNodeModel
from ai.node_behavior.config import COMPONENTS, NODE_FEATURE_COLUMNS


class StatisticalNodeModel(BaseNodeModel):
    model_version = "node-stat-v1"

    def __init__(self, z_clip: float = 5.0) -> None:
        self.z_clip = float(z_clip)
        self.components = COMPONENTS
        self.median_: np.ndarray | None = None
        self.scale_: np.ndarray | None = None
        self._index = {name: i for i, name in enumerate(NODE_FEATURE_COLUMNS)}

    def fit(self, X: np.ndarray) -> StatisticalNodeModel:
        self.median_ = np.median(X, axis=0)
        mad = np.median(np.abs(X - self.median_), axis=0) * 1.4826
        std = np.std(X, axis=0)
        self.scale_ = np.where(mad > 1e-9, mad, np.where(std > 1e-9, std, 1.0))
        return self

    def robust_z(self, X: np.ndarray) -> np.ndarray:
        return np.clip((X - self.median_) / self.scale_, 0.0, self.z_clip)

    def score(self, X: np.ndarray) -> np.ndarray:
        return self.explain(X)["anomaly_score"]

    def explain(self, X: np.ndarray) -> dict:
        z = self.robust_z(X) / self.z_clip
        n = X.shape[0]
        comp_scores = np.zeros((n, len(self.components)))
        total_weight = sum(c["weight"] for c in self.components.values())
        for j, (_name, comp) in enumerate(self.components.items()):
            cols = [self._index[f] for f in comp["features"] if f in self._index]
            comp_scores[:, j] = z[:, cols].mean(axis=1) if cols else 0.0
        weights = np.array([c["weight"] for c in self.components.values()]) / total_weight
        # Top-1 (max) aggregation: sensitive to a single strong anomaly, without the
        # normal-noise accumulation of a sum/noisy-OR. Weights are reported for reason order.
        final = comp_scores.max(axis=1)
        return {"anomaly_score": np.clip(final, 0.0, 1.0), "component_scores": comp_scores,
                "component_names": list(self.components), "component_weights": weights, "feature_z": z}

    def explain_batch(self, X: np.ndarray, top_k: int = 5) -> tuple[list[list[dict]], list[dict]]:
        e = self.explain(X)
        comp = e["component_scores"]
        names = e["component_names"]
        Z = e["feature_z"]
        reasons_list: list[list[dict]] = []
        feats_list: list[dict] = []
        for i in range(X.shape[0]):
            order = np.argsort(-comp[i])
            reasons_list.append([{"code": names[j], "contribution": float(min(comp[i][j], 1.0))}
                                 for j in order[:top_k] if comp[i][j] > 1e-6])
            feats_list.append({name: float(Z[i, self._index[name]]) for name in NODE_FEATURE_COLUMNS})
        return reasons_list, feats_list

    def reasons_for(self, X: np.ndarray, row: int, top_k: int = 5) -> list[dict]:
        return self.explain_batch(X[row:row + 1], top_k)[0][0]
