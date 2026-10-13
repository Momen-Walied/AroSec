"""Isolation Forest baseline."""
from __future__ import annotations

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import RobustScaler

from ai.edge_behavior.baselines.base import BaseEdgeModel, robust_center_scale, sigmoid_normalize
from ai.edge_behavior.config import load_config


class IsolationForestEdgeModel(BaseEdgeModel):
    model_version = "edge-iforest-v1"

    def __init__(self, config: dict | None = None) -> None:
        cfg = (config or load_config())
        self.seed = int(cfg.get("random_seed", 42))
        ifc = cfg["isolation_forest"]
        self.n_estimators = int(ifc.get("n_estimators", 200))
        self.max_samples = ifc.get("max_samples", "auto")
        self.contamination = ifc.get("contamination", "auto")
        self.scaler: RobustScaler | None = None
        self.model: IsolationForest | None = None
        self._lo: float = 0.0
        self._hi: float = 1.0

    def fit(self, X: np.ndarray) -> IsolationForestEdgeModel:
        self.scaler = RobustScaler().fit(X)
        Xs = self.scaler.transform(X)
        self.model = IsolationForest(
            n_estimators=self.n_estimators,
            max_samples=self.max_samples,
            contamination=self.contamination,
            random_state=self.seed,
            n_jobs=1,
        ).fit(Xs)
        raw = -self.model.score_samples(Xs)
        self._center, self._scale = robust_center_scale(raw)
        return self

    def raw_score(self, X: np.ndarray) -> np.ndarray:
        return -self.model.score_samples(self.scaler.transform(X))

    def calibrate_normalization(self, X: np.ndarray) -> IsolationForestEdgeModel:
        self._center, self._scale = robust_center_scale(self.raw_score(X))
        return self

    def score(self, X: np.ndarray) -> np.ndarray:
        return sigmoid_normalize(self.raw_score(X), self._center, self._scale)
