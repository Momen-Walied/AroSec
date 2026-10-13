"""Threshold + severity calibration (validation-derived, configurable)."""
from __future__ import annotations

import numpy as np

from ai.edge_behavior.config import load_config

_SEVERITY_ORDER = ["INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"]


def calibrate(scores_validation: np.ndarray, config: dict | None = None) -> dict:
    cfg = (config or load_config())["calibration"]
    target = float(cfg["target_alert_rate"])
    scores = np.asarray(scores_validation, dtype=float)
    threshold = float(np.quantile(scores, 1.0 - target)) if scores.size else 1.0

    # Severity anchored to operational alert-rate targets (not arbitrary cutoffs):
    # LOW = the alert threshold; each higher level is a rarer tail of the normal
    # validation distribution.
    rate_by_severity = {
        "INFO": 1.0,
        "LOW": target,
        "MEDIUM": target / 2.0,
        "HIGH": target / 5.0,
        "CRITICAL": target / 20.0,
    }
    severity_thresholds = {
        sev: (float(np.quantile(scores, 1.0 - rate)) if scores.size and rate < 1.0 else 0.0)
        for sev, rate in rate_by_severity.items()
    }
    prev = -1.0
    for sev in _SEVERITY_ORDER:
        severity_thresholds[sev] = max(severity_thresholds.get(sev, 0.0), prev)
        prev = severity_thresholds[sev]
    return {
        "threshold": threshold,
        "target_alert_rate": target,
        "validation_alert_rate": float(np.mean(scores >= threshold)) if scores.size else 0.0,
        "severity_thresholds": severity_thresholds,
    }


def severity_for(score: float, severity_thresholds: dict) -> str:
    level = "INFO"
    for sev in _SEVERITY_ORDER:
        if score >= severity_thresholds.get(sev, float("inf")):
            level = sev
    return level
