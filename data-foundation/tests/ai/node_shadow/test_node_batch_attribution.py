"""Regression coverage: batched Node score -> window attribution must be identity-based.

Guards the Phase 3.5 fix. The defect mapped sorted feature-frame rows back to windows by
index (`windows[i]`), so whenever a scoring batch contained more than one window, node
scores/reasons could be attached to the wrong node window. This test asserts the per-window
node scores are identical across batch sizes on a multi-asset, multi-window sequence (where
sorting by `(asset_id, window_start)` reorders rows relative to insertion order).
"""
from __future__ import annotations

import pytest

from ai.shadow.config import ShadowConfig
from ai.shadow.inference.model_bundle import ShadowModelBundle
from ai.shadow.inference.node_bundle import load_node_scorer
from ai.shadow.runtime import ShadowRuntime
from ai.shadow.sinks.memory import InMemoryShadowSink
from ai.shadow.sources.list import ListObservationSource
from ai.shadow.state.memory import InMemoryStateStore
from tests.ai.node_behavior._helpers import obs

CFG = ShadowConfig(dataset_id="synthetic")


def _artifacts_available() -> bool:
    try:
        ShadowModelBundle.load(CFG.model_bundle)
        load_node_scorer(CFG.node_model_artifact)
        return True
    except Exception:  # noqa: BLE001
        return False


requires = pytest.mark.skipif(not _artifacts_available(), reason="model bundles not regenerated locally")


def _sequence():
    a, b, c, d = "asset:a", "asset:b", "asset:c", "asset:d"
    seq = []
    for w in range(4):
        # interleave assets within a window so sorted order != insertion order
        seq += [
            obs(w, a, b, dport=443),
            obs(w, b, a, dport=80),
            obs(w, a, c, proto="UDP", dport=53),
            obs(w, a, d, dport=445),
        ]
    return seq


def _node_scores(batch_size: int) -> dict:
    sink = InMemoryShadowSink()
    ShadowRuntime(
        CFG, ListObservationSource(_sequence()), sink, InMemoryStateStore(),
        edge_bundle=None, node_scorer=load_node_scorer(CFG.node_model_artifact),
        batch_size=batch_size).run()
    return {
        (r.feature_window.asset_id, r.feature_window.window_start.isoformat()):
            r.anomaly_result.anomaly_score
        for r in sink.node_records()
    }


@requires
def test_node_scores_attributed_to_correct_window_across_batch_sizes():
    small = _node_scores(1)
    mid = _node_scores(3)
    large = _node_scores(2048)
    assert small, "expected node records"
    assert small == mid == large
