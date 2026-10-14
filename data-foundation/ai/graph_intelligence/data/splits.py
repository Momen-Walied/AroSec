"""Temporal-safe chronological partitioning (no random graph splits).

Boundaries are derived from the ordered observation timeline and reused so comparisons
with Edge/Node Behavior are meaningful. Because we evaluate an *online* system, graph
history carries forward: TRAIN history flows into VALIDATION, and TRAIN+VALIDATION history
flows into TEST (model parameters are frozen at each boundary). The graph is never reset
between partitions.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..config import GraphIntelligenceConfig
from ..contracts import SplitName


@dataclass(frozen=True)
class TemporalBoundaries:
    train_end: np.datetime64
    validation_end: np.datetime64
    n_total: int
    n_train: int
    n_validation: int
    n_test: int

    def as_dict(self) -> dict:
        return {
            "train_end": str(self.train_end), "validation_end": str(self.validation_end),
            "n_total": self.n_total, "n_train": self.n_train,
            "n_validation": self.n_validation, "n_test": self.n_test,
        }


def compute_boundaries(times: np.ndarray, cfg: GraphIntelligenceConfig) -> TemporalBoundaries:
    """Chronological 60/20/20 boundaries over sorted target timestamps."""
    ordered = np.sort(times)
    n = len(ordered)
    if n == 0:
        raise ValueError("no timestamps to split")
    n_train = int(n * cfg.train_fraction)
    n_val = int(n * cfg.validation_fraction)
    n_train = max(n_train, 1)
    train_end = ordered[n_train - 1]
    val_end = ordered[min(n_train + n_val - 1, n - 1)]
    return TemporalBoundaries(train_end=train_end, validation_end=val_end,
                              n_total=n, n_train=n_train, n_validation=n_val,
                              n_test=n - n_train - n_val)


def assign_split(t, b: TemporalBoundaries) -> SplitName:
    if t <= b.train_end:
        return SplitName.TRAIN
    if t <= b.validation_end:
        return SplitName.VALIDATION
    return SplitName.TEST
