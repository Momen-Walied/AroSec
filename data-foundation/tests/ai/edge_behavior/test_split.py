"""Chronological split tests."""
from __future__ import annotations

import pandas as pd

from ai.edge_behavior.training.split import chronological_split
from tests.ai.edge_behavior._helpers import make_frame


def test_chronological_split_is_ordered_and_disjoint():
    df = make_frame(1000)
    split = chronological_split(df, 0.6, 0.2, 0.2)
    assert len(split.train) == 600
    assert len(split.validation) == 200
    assert len(split.test) == 200
    assert split.train["window_start"].max() <= split.validation["window_start"].min()
    assert split.validation["window_start"].max() <= split.test["window_start"].min()


def test_boundaries_recorded():
    df = make_frame(100)
    split = chronological_split(df, 0.6, 0.2, 0.2)
    b = split.boundaries
    assert b["n_total"] == 100
    assert b["train"][0] <= b["train"][1]
    assert b["train"][1] <= b["validation"][0]
    assert b["validation"][1] <= b["test"][0]


def test_fraction_validation_error():
    df = make_frame(10)
    try:
        chronological_split(df, 0.5, 0.2, 0.2)
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_no_random_shuffle():
    df = make_frame(300)
    split = chronological_split(df, 0.6, 0.2, 0.2)
    combined = pd.concat([split.train, split.validation, split.test])
    assert combined["window_start"].is_monotonic_increasing
