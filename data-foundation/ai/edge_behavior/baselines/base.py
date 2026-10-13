"""Shared interface for Edge Behavior models."""
from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np

from ai.edge_behavior.features.builder import FEATURE_SCHEMA_VERSION


class BaseEdgeModel:
    model_version: str = "base"
    feature_schema_version: str = FEATURE_SCHEMA_VERSION

    def fit(self, X: np.ndarray) -> BaseEdgeModel:  # pragma: no cover - interface
        raise NotImplementedError

    def score(self, X: np.ndarray) -> np.ndarray:  # pragma: no cover - interface
        raise NotImplementedError

    def calibrate_normalization(self, X: np.ndarray) -> BaseEdgeModel:
        """Set score-normalization center/scale from a calibration set (validation)."""
        return self

    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)
        return path

    @classmethod
    def load(cls, path: Path) -> BaseEdgeModel:
        model = joblib.load(path)
        if not isinstance(model, cls):
            raise TypeError(f"artifact {path} is {type(model).__name__}, expected {cls.__name__}")
        if getattr(model, "feature_schema_version", None) != FEATURE_SCHEMA_VERSION:
            raise ValueError(
                f"feature schema mismatch: artifact={getattr(model, 'feature_schema_version', None)} "
                f"code={FEATURE_SCHEMA_VERSION}"
            )
        return model


def sigmoid_normalize(raw: np.ndarray, center: float, scale: float) -> np.ndarray:
    """Smooth map to [0,1]: 0.5 at the TRAIN center; no hard saturation under drift."""
    scale = scale if scale > 1e-12 else 1.0
    return 1.0 / (1.0 + np.exp(-(raw - center) / scale))


def robust_center_scale(raw: np.ndarray) -> tuple[float, float]:
    center = float(np.median(raw))
    iqr = float(np.percentile(raw, 75) - np.percentile(raw, 25))
    if iqr < 1e-12:
        iqr = float(np.std(raw))
    if iqr < 1e-12:
        iqr = 1.0
    return center, 2.0 * iqr
