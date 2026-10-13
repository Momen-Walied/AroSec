"""Statistical baseline: robust per-feature deviation + component reasons.

Interpretable by construction. Score in [0,1]; component-level reasons preserved.
"""
from __future__ import annotations

import numpy as np

from ai.edge_behavior.baselines.base import BaseEdgeModel
from ai.edge_behavior.config import load_config
from ai.edge_behavior.features.builder import FEATURE_COLUMNS


class StatisticalEdgeModel(BaseEdgeModel):
    model_version = "edge-stat-v1"

    def __init__(self, config: dict | None = None) -> None:
        cfg = (config or load_config())["statistical"]
        self.z_clip = float(cfg.get("z_clip", 5.0))
        self.components: dict[str, dict] = cfg["components"]
        self.median_: np.ndarray | None = None
        self.scale_: np.ndarray | None = None
        self._index = {name: i for i, name in enumerate(FEATURE_COLUMNS)}

    def fit(self, X: np.ndarray) -> StatisticalEdgeModel:
        self.median_ = np.median(X, axis=0)
        mad = np.median(np.abs(X - self.median_), axis=0) * 1.4826
        std = np.std(X, axis=0)
        scale = np.where(mad > 1e-9, mad, np.where(std > 1e-9, std, 1.0))
        self.scale_ = scale
        return self

    def robust_z(self, X: np.ndarray) -> np.ndarray:
        z = (X - self.median_) / self.scale_
        return np.clip(z, 0.0, self.z_clip)

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
        final = comp_scores @ weights
        return {
            "anomaly_score": np.clip(final, 0.0, 1.0),
            "component_scores": comp_scores,
            "component_names": list(self.components),
            "component_weights": weights,
            "feature_z": z,
        }

    def reasons_for(self, X: np.ndarray, row: int, top_k: int = 5) -> list[dict]:
        explained = self.explain(X[row:row + 1])
        comps = explained["component_scores"][0]
        weights = explained["component_weights"]
        contrib = comps * weights
        order = np.argsort(-contrib)
        names = explained["component_names"]
        out = []
        for idx in order[:top_k]:
            if contrib[idx] <= 1e-6:
                continue
            out.append({"code": names[idx], "contribution": float(contrib[idx])})
        return out

    def feature_contributions(self, X: np.ndarray, row: int) -> dict[str, float]:
        z = self.explain(X[row:row + 1])["feature_z"][0]
        return {name: float(z[self._index[name]]) for name in FEATURE_COLUMNS if name in self._index}

    def explain_batch(self, X: np.ndarray, top_k: int = 5) -> tuple[list[list[dict]], list[dict]]:
        """Reasons + feature contributions for many rows in ONE explain pass."""
        explained = self.explain(X)
        comp = explained["component_scores"]
        weights = explained["component_weights"]
        names = explained["component_names"]
        Z = explained["feature_z"]
        contrib = comp * weights
        reasons_list: list[list[dict]] = []
        feats_list: list[dict] = []
        for i in range(X.shape[0]):
            row = contrib[i]
            order = np.argsort(-row)
            reasons_list.append([
                {"code": names[j], "contribution": float(row[j])}
                for j in order[:top_k] if row[j] > 1e-6
            ])
            feats_list.append({
                name: float(Z[i, self._index[name]]) for name in FEATURE_COLUMNS if name in self._index
            })
        return reasons_list, feats_list
