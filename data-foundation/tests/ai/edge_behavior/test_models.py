"""Model tests: score range, train-only scaler, artifacts, schema mismatch."""
from __future__ import annotations

import numpy as np
import pytest

from ai.edge_behavior.baselines import (
    AutoencoderEdgeModel,
    IsolationForestEdgeModel,
    StatisticalEdgeModel,
)
from ai.edge_behavior.baselines.base import BaseEdgeModel
from ai.edge_behavior.features.builder import FEATURE_COLUMNS, build_feature_matrix
from tests.ai.edge_behavior._helpers import make_frame


def _X(n=300):
    df = make_frame(n)
    return build_feature_matrix(df)[FEATURE_COLUMNS].to_numpy(dtype=float)


def test_statistical_score_range_and_reasons():
    X = _X()
    model = StatisticalEdgeModel().fit(X)
    scores = model.score(X)
    assert scores.min() >= 0.0 and scores.max() <= 1.0
    reasons = model.reasons_for(X, 0)
    assert isinstance(reasons, list)


def test_isolation_forest_score_range_and_train_only_scaler():
    X = _X(300)
    model = IsolationForestEdgeModel().fit(X)
    scores = model.score(X)
    assert scores.min() >= 0.0 and scores.max() <= 1.0
    assert np.allclose(model.scaler.center_, np.median(X, axis=0))


def test_autoencoder_score_range():
    X = _X(200)
    model = AutoencoderEdgeModel().fit(X)
    scores = model.score(X)
    assert scores.min() >= 0.0 and scores.max() <= 1.0


def test_artifact_roundtrip(tmp_path):
    X = _X(150)
    model = StatisticalEdgeModel().fit(X)
    path = model.save(tmp_path / "model.joblib")
    loaded = BaseEdgeModel.load(path)
    assert np.allclose(model.score(X), loaded.score(X))


def test_schema_mismatch_fails_cleanly(tmp_path):
    X = _X(120)
    model = StatisticalEdgeModel().fit(X)
    model.feature_schema_version = "edge_features_OLD"
    path = model.save(tmp_path / "model.joblib")
    with pytest.raises(ValueError, match="feature schema mismatch"):
        BaseEdgeModel.load(path)
