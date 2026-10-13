"""Lightweight in-process metrics (counters, histograms, gauges).

A Prometheus adapter can be layered on top of `snapshot()`; no heavy infrastructure
is introduced for v1.
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np


class MetricsCollector:
    def __init__(self) -> None:
        self.counters: dict[str, float] = defaultdict(float)
        self.histograms: dict[str, list[float]] = defaultdict(list)
        self.gauges: dict[str, float] = {}

    def inc(self, name: str, amount: float = 1.0) -> None:
        self.counters[name] += amount

    def observe(self, name: str, value: float) -> None:
        self.histograms[name].append(float(value))

    def gauge(self, name: str, value: float) -> None:
        self.gauges[name] = float(value)

    @staticmethod
    def _percentiles(values: list[float]) -> dict:
        if not values:
            return {"count": 0}
        arr = np.asarray(values, dtype=float)
        return {
            "count": int(arr.size),
            "mean": float(arr.mean()),
            "p50": float(np.percentile(arr, 50)),
            "p95": float(np.percentile(arr, 95)),
            "p99": float(np.percentile(arr, 99)),
            "max": float(arr.max()),
        }

    def snapshot(self) -> dict:
        return {
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "histograms": {k: self._percentiles(v) for k, v in self.histograms.items()},
        }
