"""Drift monitoring foundation (metrics only; NO automatic retraining).

Compares recent runtime distributions against a reference profile derived from
training/validation data using PSI (population stability index) and the KS statistic.
"""
from __future__ import annotations

import numpy as np

DRIFT_NONE = "DRIFT_NONE"
DRIFT_WARNING = "DRIFT_WARNING"
DRIFT_HIGH = "DRIFT_HIGH"

PSI_WARNING = 0.10
PSI_HIGH = 0.25


def reference_profile(values: np.ndarray, bins: int = 10) -> dict:
    arr = np.asarray(values, dtype=float)
    edges = np.quantile(arr, np.linspace(0, 1, bins + 1))
    edges[0] -= 1e-9
    edges[-1] += 1e-9
    hist, _ = np.histogram(arr, bins=edges)
    proportions = hist / max(hist.sum(), 1)
    return {"edges": edges.tolist(), "proportions": proportions.tolist(), "n": int(arr.size)}


def psi(recent: np.ndarray, reference: dict) -> float:
    edges = np.asarray(reference["edges"], dtype=float)
    expected = np.asarray(reference["proportions"], dtype=float)
    hist, _ = np.histogram(np.asarray(recent, dtype=float), bins=edges)
    actual = hist / max(hist.sum(), 1)
    eps = 1e-6
    actual = np.clip(actual, eps, None)
    expected = np.clip(expected, eps, None)
    return float(np.sum((actual - expected) * np.log(actual / expected)))


def ks_statistic(recent: np.ndarray, reference_values: np.ndarray) -> float:
    from scipy.stats import ks_2samp

    if len(recent) == 0 or len(reference_values) == 0:
        return 0.0
    return float(ks_2samp(np.asarray(recent, dtype=float),
                          np.asarray(reference_values, dtype=float)).statistic)


def classify(psi_value: float) -> str:
    if psi_value >= PSI_HIGH:
        return DRIFT_HIGH
    if psi_value >= PSI_WARNING:
        return DRIFT_WARNING
    return DRIFT_NONE


def drift_report(recent: dict[str, np.ndarray], reference: dict[str, np.ndarray],
                 bins: int = 10) -> dict:
    """recent/reference: metric_name -> values. Returns per-metric PSI + KS + class."""
    out: dict[str, dict] = {}
    worst = DRIFT_NONE
    order = {DRIFT_NONE: 0, DRIFT_WARNING: 1, DRIFT_HIGH: 2}
    for name, ref_values in reference.items():
        rec = recent.get(name)
        if rec is None or len(rec) == 0:
            continue
        profile = reference_profile(np.asarray(ref_values, dtype=float), bins=bins)
        psi_value = psi(np.asarray(rec, dtype=float), profile)
        ks_value = ks_statistic(np.asarray(rec, dtype=float), np.asarray(ref_values, dtype=float))
        klass = classify(psi_value)
        out[name] = {"psi": psi_value, "ks": ks_value, "class": klass}
        if order[klass] > order[worst]:
            worst = klass
    out["_overall"] = worst
    return out
