"""Calibration + severity tests."""
from __future__ import annotations

import numpy as np

from ai.edge_behavior.calibration import calibrate, severity_for


def test_threshold_hits_target_alert_rate():
    rng = np.random.default_rng(0)
    scores = rng.random(10_000)
    calib = calibrate(scores, {"calibration": {"target_alert_rate": 0.05, "severity_quantiles": {}}})
    assert abs(calib["validation_alert_rate"] - 0.05) < 0.01
    assert 0.0 <= calib["threshold"] <= 1.0


def test_severity_monotonic_and_ordered():
    rng = np.random.default_rng(1)
    scores = rng.random(10_000)
    calib = calibrate(scores, {"calibration": {"target_alert_rate": 0.01, "severity_quantiles": {}}})
    st = calib["severity_thresholds"]
    assert st["INFO"] <= st["LOW"] <= st["MEDIUM"] <= st["HIGH"] <= st["CRITICAL"]
    assert severity_for(0.0, st) == "INFO"
    assert severity_for(1.0, st) == "CRITICAL"


def test_severity_uses_validation_not_hardcoded():
    scores = np.concatenate([np.zeros(9900), np.ones(100)])
    calib = calibrate(scores, {"calibration": {"target_alert_rate": 0.01, "severity_quantiles": {}}})
    assert abs(calib["threshold"] - float(np.quantile(scores, 0.99))) < 1e-9
