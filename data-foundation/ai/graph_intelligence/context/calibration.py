"""Train-only normalization and validation-only threshold calibration."""
from __future__ import annotations

import numpy as np


def calibrate_threshold(scores_validation: np.ndarray, target_alert_rate: float = 0.01) -> float:
    """Pick the alert threshold on VALIDATION only at the target alert rate (higher score = alert)."""
    s = np.asarray(scores_validation, dtype=float)
    if s.size == 0:
        return float("inf")
    rate = min(max(target_alert_rate, 0.0), 1.0)
    if rate <= 0:
        return float(np.nextafter(s.max(), np.inf))
    return float(np.quantile(s, 1.0 - rate))


def alert_rate(scores: np.ndarray, threshold: float) -> float:
    s = np.asarray(scores, dtype=float)
    return float((s >= threshold).mean()) if s.size else 0.0
