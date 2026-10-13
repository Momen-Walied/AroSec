"""Isolation Forest node baseline."""
from __future__ import annotations

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import RobustScaler

from ai.edge_behavior.baselines.base import robust_center_scale, sigmoid_normalize
from ai.node_behavior.baselines.base import BaseNodeModel


class IsolationForestNodeModel(BaseNodeModel):
    model_version = "node-iforest-v1"

    def __init__(self, seed: int = 42, n_estimators: int = 200, max_samples=4096,
                 contamination="auto") -> None:
        self.seed = seed
        self.n_estimators = n_estimators
        self.max_samples = max_samples
        self.contamination = contamination
        self.scaler: RobustScaler | None = None
        self.model: IsolationForest | None = None
        self._center = 0.0
        self._scale = 1.0

    def fit(self, X: np.ndarray) -> IsolationForestNodeModel:
        self.scaler = RobustScaler().fit(X)
        Xs = self.scaler.transform(X)
        self.model = IsolationForest(n_estimators=self.n_estimators, max_samples=self.max_samples,
                                     contamination=self.contamination, random_state=self.seed,
                                     n_jobs=1).fit(Xs)
        self._center, self._scale = robust_center_scale(self.raw_score(X))
        return self

    def raw_score(self, X: np.ndarray) -> np.ndarray:
        return -self.model.score_samples(self.scaler.transform(X))

    def calibrate_normalization(self, X: np.ndarray) -> IsolationForestNodeModel:
        self._center, self._scale = robust_center_scale(self.raw_score(X))
        return self

    def score(self, X: np.ndarray) -> np.ndarray:
        return sigmoid_normalize(self.raw_score(X), self._center, self._scale)
