"""Feature preparation: determinism + no-future-leakage."""
from __future__ import annotations

import pandas as pd

from ai.edge_behavior.features.builder import (
    FEATURE_COLUMNS,
    FEATURE_SCHEMA_VERSION,
    build_feature_matrix,
    feature_config,
)
from tests.ai.edge_behavior._helpers import make_frame


def test_feature_columns_and_config():
    cfg = feature_config()
    assert cfg["feature_schema_version"] == FEATURE_SCHEMA_VERSION
    assert set(cfg["feature_columns"]) == set(FEATURE_COLUMNS)


def test_deterministic_feature_preparation():
    df = make_frame(300)
    a = build_feature_matrix(df)
    b = build_feature_matrix(df.copy())
    pd.testing.assert_frame_equal(a, b)


def test_no_future_leakage_when_appending_future_rows():
    df = make_frame(200)
    base = build_feature_matrix(df)
    future = make_frame(200).copy()
    future["window_start"] = future["window_start"] + pd.Timedelta(days=30)
    future["window_end"] = future["window_end"] + pd.Timedelta(days=30)
    extended = build_feature_matrix(pd.concat([df, future], ignore_index=True))

    key = ["relationship_id", "window_start"]
    merged = base.merge(extended, on=key, suffixes=("_base", "_ext"))
    assert len(merged) == len(base)
    for col in FEATURE_COLUMNS:
        assert (merged[f"{col}_base"] == merged[f"{col}_ext"]).all()


def test_causal_app_protocol_novelty():
    df = make_frame(20, n_relationships=1)
    df["application_protocol_distribution"] = [
        {"TLS": 1} if i < 10 else {"SMB": 1} for i in range(len(df))
    ]
    matrix = build_feature_matrix(df)
    matrix = matrix.sort_values("window_start")
    novelty = matrix["app_protocol_novelty_count"].to_numpy()
    assert novelty[0] == 1  # TLS first seen
    assert novelty[10] == 1  # SMB first seen
    assert novelty[11:].sum() == 0  # no repeats counted
