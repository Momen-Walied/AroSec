"""Compact tabular autoencoder baseline (sklearn MLPRegressor bottleneck).

Intentionally small and CPU-only. Reconstruction error is the anomaly score.
"""
from __future__ import annotations

import numpy as np
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import RobustScaler

from ai.edge_behavior.baselines.base import BaseEdgeModel, robust_center_scale, sigmoid_normalize
from ai.edge_behavior.config import load_config


class AutoencoderEdgeModel(BaseEdgeModel):
    model_version = "edge-ae-v1"

    def __init__(self, config: dict | None = None) -> None:
        cfg = (config or load_config())
        self.seed = int(cfg.get("random_seed", 42))
        ae = cfg["autoencoder"]
        self.hidden = tuple(ae.get("hidden", [64, 32, 16, 32, 64]))
        self.max_iter = int(ae.get("max_iter", 300))
        self.early_stopping = bool(ae.get("early_stopping", True))
        self.scaler: RobustScaler | None = None
        self.model: MLPRegressor | None = None
        self._lo: float = 0.0
        self._hi: float = 1.0

    def fit(self, X: np.ndarray) -> AutoencoderEdgeModel:
        self.scaler = RobustScaler().fit(X)
        Xs = self.scaler.transform(X)
        self.model = MLPRegressor(
            hidden_layer_sizes=self.hidden,
            activation="relu",
            solver="adam",
            alpha=1e-4,
            learning_rate_init=1e-3,
            max_iter=self.max_iter,
            early_stopping=self.early_stopping,
            n_iter_no_change=15,
            random_state=self.seed,
        ).fit(Xs, Xs)
        err = self._recon_error(Xs)
        self._center, self._scale = robust_center_scale(err)
        return self

    def _recon_error(self, Xs: np.ndarray) -> np.ndarray:
        recon = self.model.predict(Xs)
        return np.mean((Xs - recon) ** 2, axis=1)

    def raw_score(self, X: np.ndarray) -> np.ndarray:
        return self._recon_error(self.scaler.transform(X))

    def calibrate_normalization(self, X: np.ndarray) -> AutoencoderEdgeModel:
        self._center, self._scale = robust_center_scale(self.raw_score(X))
        return self

    def score(self, X: np.ndarray) -> np.ndarray:
        return sigmoid_normalize(self.raw_score(X), self._center, self._scale)
