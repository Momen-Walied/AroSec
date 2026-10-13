"""Shadow inference tests (skipped if the regeneration-only model bundle is absent)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai.shadow.config import ShadowConfig
from ai.shadow.inference.model_bundle import ModelBundleError, ShadowModelBundle
from ai.shadow.runtime import ShadowRuntime
from ai.shadow.sinks.memory import InMemoryShadowSink
from ai.shadow.sources.list import ListObservationSource
from ai.shadow.state.memory import InMemoryStateStore
from tests.ai.shadow._helpers import sample_sequence

BUNDLE = ShadowConfig().model_bundle


def _bundle_available() -> bool:
    try:
        ShadowModelBundle.load(BUNDLE)
        return True
    except Exception:  # noqa: BLE001
        return False


requires_bundle = pytest.mark.skipif(not _bundle_available(),
                                     reason="model bundle not regenerated locally")


def _run(obs_seq):
    cfg = ShadowConfig(dataset_id="synthetic")
    sink = InMemoryShadowSink()
    bundle = ShadowModelBundle.load(cfg.model_bundle)
    runtime = ShadowRuntime(cfg, ListObservationSource(obs_seq), sink, InMemoryStateStore(), bundle)
    runtime.run()
    return sink.records


@requires_bundle
def test_one_result_per_finalized_window():
    records = _run(sample_sequence())
    # rel a-b at windows 0,1,4 ; rel a-c at windows 2,3 => 5 finalized windows
    assert len(records) == 5
    keys = {(r.feature_window.relationship_id, r.feature_window.window_start) for r in records}
    assert len(keys) == 5


@requires_bundle
def test_deterministic_scoring():
    s1 = _run(sample_sequence())
    s2 = _run(sample_sequence())
    assert [r.anomaly_result.anomaly_score for r in s1] == [r.anomaly_result.anomaly_score for r in s2]


@requires_bundle
def test_batch_size_invariance():
    """Scores must not depend on the internal scoring batch size."""
    from ai.shadow.state.memory import InMemoryStateStore as _Mem

    def run_with(batch_size):
        cfg = ShadowConfig(dataset_id="synthetic")
        sink = InMemoryShadowSink()
        bundle = ShadowModelBundle.load(cfg.model_bundle)
        rt = ShadowRuntime(cfg, ListObservationSource(sample_sequence()), sink, _Mem(), bundle,
                           batch_size=batch_size)
        rt.run()
        return {r.feature_window.window_start: r.anomaly_result.anomaly_score for r in sink.records}

    assert run_with(1) == run_with(2048)


@requires_bundle
def test_new_relationship_scores_higher_than_stable():
    records = _run(sample_sequence())
    stable = next(r for r in records
                  if r.feature_window.relationship_id.endswith("asset:demo:a|asset:demo:b|COMMUNICATES_WITH")
                  and not r.feature_window.new_peer)
    novel = next(r for r in records if r.feature_window.new_peer)
    assert novel.anomaly_result.anomaly_score >= stable.anomaly_result.anomaly_score


def test_schema_mismatch_fails_clearly(tmp_path):
    bad = tmp_path / "bundle.json"
    bad.write_text(json.dumps({
        "bundle_version": "x", "feature_schema_version": "edge_features_OLD",
        "components": [], "calibration": {"severity_thresholds": {}},
    }))
    with pytest.raises(ModelBundleError):
        ShadowModelBundle.load(bad)


def test_missing_artifact_fails_clearly(tmp_path):
    spec = json.loads(Path(BUNDLE).read_text())
    spec["components"][0]["artifact"] = "ai/edge_behavior/artifacts/edge_behavior/does-not-exist"
    bad = tmp_path / "bundle.json"
    bad.write_text(json.dumps(spec))
    with pytest.raises(ModelBundleError):
        ShadowModelBundle.load(bad)
