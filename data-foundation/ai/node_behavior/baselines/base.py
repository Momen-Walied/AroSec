"""Shared interface for Node Behavior models."""
from __future__ import annotations

from pathlib import Path

import joblib

from ai.edge_behavior.baselines.base import robust_center_scale, sigmoid_normalize  # noqa: F401
from ai.node_behavior.config import NODE_FEATURE_SCHEMA_VERSION


class BaseNodeModel:
    model_version: str = "base"
    feature_schema_version: str = NODE_FEATURE_SCHEMA_VERSION

    def fit(self, X):  # pragma: no cover - interface
        raise NotImplementedError

    def score(self, X):  # pragma: no cover - interface
        raise NotImplementedError

    def calibrate_normalization(self, X) -> BaseNodeModel:
        return self

    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)
        return path

    @classmethod
    def load(cls, path: Path) -> BaseNodeModel:
        model = joblib.load(path)
        if not isinstance(model, cls):
            raise TypeError(f"artifact {path} is {type(model).__name__}, expected {cls.__name__}")
        if getattr(model, "feature_schema_version", None) != NODE_FEATURE_SCHEMA_VERSION:
            raise ValueError(
                f"feature schema mismatch: artifact={getattr(model, 'feature_schema_version', None)} "
                f"code={NODE_FEATURE_SCHEMA_VERSION}")
        return model
