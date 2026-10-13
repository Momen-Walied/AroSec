"""Combined Edge+Node shadow runtime: separation, isolation, no fusion, idempotency."""
from __future__ import annotations

import pytest

from ai.contracts.shadow_records import ShadowNodeInferenceRecordV1
from ai.shadow.config import ShadowConfig
from ai.shadow.inference.model_bundle import ShadowModelBundle
from ai.shadow.inference.node_bundle import NodeModelBundleError, load_node_scorer
from ai.shadow.runtime import ShadowRuntime
from ai.shadow.sinks.memory import InMemoryShadowSink
from ai.shadow.sources.list import ListObservationSource
from ai.shadow.state.memory import InMemoryStateStore
from tests.ai.node_shadow._helpers import sample_sequence

CFG = ShadowConfig(dataset_id="synthetic")


def _artifacts_available() -> bool:
    try:
        ShadowModelBundle.load(CFG.model_bundle)
        load_node_scorer(CFG.node_model_artifact)
        return True
    except Exception:  # noqa: BLE001
        return False


requires = pytest.mark.skipif(not _artifacts_available(), reason="model bundles not regenerated locally")


def _run(edge=True, node=True, seq=None, batch_size=2048):
    sink = InMemoryShadowSink()
    runtime = ShadowRuntime(
        CFG, ListObservationSource(seq or sample_sequence()), sink, InMemoryStateStore(),
        edge_bundle=ShadowModelBundle.load(CFG.model_bundle) if edge else None,
        node_scorer=load_node_scorer(CFG.node_model_artifact) if node else None,
        batch_size=batch_size)
    runtime.run()
    return sink


@requires
def test_both_pipelines_produce_separate_records():
    sink = _run()
    edge = sink.edge_records()
    node = sink.node_records()
    assert edge and node
    assert all(r.intelligence_type == "edge" for r in edge)
    assert all(r.intelligence_type == "node" for r in node)
    assert all(hasattr(r.feature_window, "relationship_id") for r in edge)
    assert all(hasattr(r.feature_window, "asset_id") for r in node)


@requires
def test_no_fused_score_present():
    sink = _run()
    payloads = [r.canonical_json() for r in sink.records]
    for term in ("fused", "combined_score", "incident_score", "node_edge_score"):
        assert all(term not in p for p in payloads)
    assert set(r.intelligence_type for r in sink.records) <= {"edge", "node"}


@requires
def test_duplicate_is_idempotent_across_both_pipelines():
    seq = sample_sequence()
    dup = list(seq) + [seq[0], seq[1]]  # duplicate first two observations
    base = _run(seq=seq)
    with_dup = _run(seq=dup)
    assert len(with_dup.edge_records()) == len(base.edge_records())
    assert len(with_dup.node_records()) == len(base.node_records())


@requires
def test_edge_only_isolation_when_node_disabled():
    sink = _run(node=False)
    assert sink.node_records() == []
    assert sink.edge_records() != []


@requires
def test_node_only_isolation_when_edge_disabled():
    sink = _run(edge=False)
    assert sink.edge_records() == []
    assert sink.node_records() != []


@requires
def test_batch_size_invariance_for_node_scores():
    a = {(r.feature_window.asset_id, r.feature_window.window_start.isoformat()): r.anomaly_result.anomaly_score
         for r in _run(batch_size=1).node_records()}
    b = {(r.feature_window.asset_id, r.feature_window.window_start.isoformat()): r.anomaly_result.anomaly_score
         for r in _run(batch_size=2048).node_records()}
    assert a == b


def test_node_record_shadow_mode_invariant():
    from datetime import UTC, datetime

    from pydantic import ValidationError

    from ai.contracts.node_anomaly_result import NodeAnomalyResultV1, NodeSeverity
    from ai.node_behavior.features.builder import build_node_feature_windows_v2
    from tests.ai.node_shadow._helpers import obs

    w = build_node_feature_windows_v2([obs(0, "asset:a", "asset:b")])[0]
    ar = NodeAnomalyResultV1(model_version="x", asset_id=w.asset_id, window_start=w.window_start,
                             window_end=w.window_end, anomaly_score=0.1, severity=NodeSeverity.LOW,
                             inference_timestamp=datetime.now(UTC))
    data = {"runtime_version": "x", "received_at": datetime.now(UTC), "processed_at": datetime.now(UTC),
            "feature_window": w.model_dump(), "anomaly_result": ar.model_dump(),
            "processing_latency_ms": 1.0, "shadow_mode": False}
    with pytest.raises(ValidationError):
        ShadowNodeInferenceRecordV1.model_validate(data)


def test_node_bundle_missing_fails_clearly(tmp_path):
    with pytest.raises(NodeModelBundleError):
        load_node_scorer(tmp_path / "does-not-exist")
