"""Compact tabular autoencoder node baseline (sklearn MLPRegressor bottleneck)."""
from __future__ import annotations

import numpy as np
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import RobustScaler

from ai.edge_behavior.baselines.base import robust_center_scale, sigmoid_normalize
from ai.node_behavior.baselines.base import BaseNodeModel


class AutoencoderNodeModel(BaseNodeModel):
    model_version = "node-ae-v1"

    def __init__(self, seed: int = 42, hidden: tuple = (16, 8, 4, 8, 16), max_iter: int = 400,
                 early_stopping: bool = True) -> None:
        self.seed = seed
        self.hidden = hidden
        self.max_iter = max_iter
        self.early_stopping = early_stopping
        self.scaler: RobustScaler | None = None
        self.model: MLPRegressor | None = None
        self._center = 0.0
        self._scale = 1.0

    def fit(self, X: np.ndarray) -> AutoencoderNodeModel:
        self.scaler = RobustScaler().fit(X)
        Xs = self.scaler.transform(X)
        self.model = MLPRegressor(hidden_layer_sizes=self.hidden, activation="relu", solver="adam",
                                  alpha=1e-3, learning_rate_init=1e-3, max_iter=self.max_iter,
                                  early_stopping=self.early_stopping, n_iter_no_change=15,
                                  random_state=self.seed).fit(Xs, Xs)
        self._center, self._scale = robust_center_scale(self.raw_score(X))
        return self

    def _recon_error(self, Xs: np.ndarray) -> np.ndarray:
        return np.mean((Xs - self.model.predict(Xs)) ** 2, axis=1)

    def raw_score(self, X: np.ndarray) -> np.ndarray:
        return self._recon_error(self.scaler.transform(X))

    def calibrate_normalization(self, X: np.ndarray) -> AutoencoderNodeModel:
        self._center, self._scale = robust_center_scale(self.raw_score(X))
        return self

    def score(self, X: np.ndarray) -> np.ndarray:
        return sigmoid_normalize(self.raw_score(X), self._center, self._scale)
