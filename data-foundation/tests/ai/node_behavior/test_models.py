"""Node model tests: score range, artifacts, schema mismatch."""
from __future__ import annotations

import numpy as np
import pytest

from ai.node_behavior.baselines import (
    AutoencoderNodeModel,
    IsolationForestNodeModel,
    StatisticalNodeModel,
)
from ai.node_behavior.baselines.base import BaseNodeModel


def _X(n=400, seed=0):
    rng = np.random.default_rng(seed)
    return rng.random((n, 23))


def test_statistical_score_range_and_reasons():
    X = _X()
    m = StatisticalNodeModel().fit(X)
    s = m.score(X)
    assert s.min() >= 0.0 and s.max() <= 1.0
    assert isinstance(m.reasons_for(X, 0), list)


def test_isolation_forest_score_range():
    X = _X()
    m = IsolationForestNodeModel().fit(X)
    s = m.score(X)
    assert s.min() >= 0.0 and s.max() <= 1.0


def test_autoencoder_score_range():
    X = _X(200)
    m = AutoencoderNodeModel().fit(X)
    s = m.score(X)
    assert s.min() >= 0.0 and s.max() <= 1.0


def test_artifact_roundtrip(tmp_path):
    X = _X(150)
    m = StatisticalNodeModel().fit(X)
    loaded = BaseNodeModel.load(m.save(tmp_path / "model.joblib"))
    assert np.allclose(m.score(X), loaded.score(X))


def test_schema_mismatch_fails(tmp_path):
    X = _X(120)
    m = StatisticalNodeModel().fit(X)
    m.feature_schema_version = "node_features_OLD"
    with pytest.raises(ValueError, match="feature schema mismatch"):
        BaseNodeModel.load(m.save(tmp_path / "model.joblib"))
