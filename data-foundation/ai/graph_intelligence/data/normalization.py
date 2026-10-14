"""Train-only feature normalization (leakage class G).

Any scaler/statistic used by an eventual model MUST be fit on TRAIN only and merely
applied (transform) to VALIDATION/TEST. This tiny helper makes that contract explicit and
testable without any model dependency.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class TrainOnlyStandardizer:
    mean_: np.ndarray | None = None
    std_: np.ndarray | None = None

    def fit(self, x_train: np.ndarray) -> TrainOnlyStandardizer:
        x = np.asarray(x_train, dtype=float)
        self.mean_ = x.mean(axis=0)
        std = x.std(axis=0)
        self.std_ = np.where(std < 1e-12, 1.0, std)
        return self

    def transform(self, x: np.ndarray) -> np.ndarray:
        if self.mean_ is None or self.std_ is None:
            raise RuntimeError("standardizer not fitted")
        return (np.asarray(x, dtype=float) - self.mean_) / self.std_
