"""Chronological dataset splitting (no random splits)."""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class ChronologicalSplit:
    train: pd.DataFrame
    validation: pd.DataFrame
    test: pd.DataFrame
    boundaries: dict = field(default_factory=dict)

    def summary(self) -> dict:
        return {
            "boundaries": self.boundaries,
            "train_rows": len(self.train),
            "validation_rows": len(self.validation),
            "test_rows": len(self.test),
        }


def chronological_split(df: pd.DataFrame, train: float = 0.6, validation: float = 0.2,
                        test: float = 0.2, time_col: str = "window_start") -> ChronologicalSplit:
    if abs((train + validation + test) - 1.0) > 1e-9:
        raise ValueError("train+validation+test must sum to 1.0")
    ordered = df.sort_values(time_col, kind="mergesort").reset_index(drop=True)
    n = len(ordered)
    n_train = int(n * train)
    n_val = int(n * validation)
    train_df = ordered.iloc[:n_train].copy()
    val_df = ordered.iloc[n_train:n_train + n_val].copy()
    test_df = ordered.iloc[n_train + n_val:].copy()

    def _ts(frame: pd.DataFrame) -> tuple:
        if frame.empty:
            return (None, None)
        return (frame[time_col].min().isoformat(), frame[time_col].max().isoformat())

    boundaries = {
        "time_col": time_col,
        "fractions": {"train": train, "validation": validation, "test": test},
        "train": _ts(train_df),
        "validation": _ts(val_df),
        "test": _ts(test_df),
        "n_total": n,
        "n_train": len(train_df),
        "n_validation": len(val_df),
        "n_test": len(test_df),
    }
    return ChronologicalSplit(train=train_df, validation=val_df, test=test_df, boundaries=boundaries)
