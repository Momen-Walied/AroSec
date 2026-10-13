"""Inference contract tests: EdgeAnomalyResultV1, determinism, evidence refs."""
from __future__ import annotations

from ai.contracts.edge_anomaly_result import EdgeAnomalyResultV1
from ai.edge_behavior.baselines.statistical import StatisticalEdgeModel
from ai.edge_behavior.calibration import calibrate
from ai.edge_behavior.features.builder import FEATURE_COLUMNS, build_feature_matrix, feature_config
from ai.edge_behavior.inference.scorer import EdgeBehaviorScorer
from tests.ai.edge_behavior._helpers import make_frame


def _scorer():
    df = make_frame(400)
    X = build_feature_matrix(df)[FEATURE_COLUMNS].to_numpy(dtype=float)
    model = StatisticalEdgeModel().fit(X)
    calib = calibrate(model.score(X))
    return EdgeBehaviorScorer(model, model, calib, feature_config()), df


def test_score_edge_contract_and_evidence():
    scorer, df = _scorer()
    row = df.iloc[0].to_dict()
    result = scorer.score_edge(row)
    assert isinstance(result, EdgeAnomalyResultV1)
    assert 0.0 <= result.anomaly_score <= 1.0
    assert result.relationship_id.startswith("rel:")
    assert any("window:" in r for r in result.evidence_refs)
    assert result.identity_quality.identity_is_provisional is True


def test_inference_is_deterministic():
    scorer, df = _scorer()
    row = df.iloc[5].to_dict()
    a = scorer.score_edge(row)
    b = scorer.score_edge(row)
    assert a.anomaly_score == b.anomaly_score
    assert [r.code for r in a.reasons] == [r.code for r in b.reasons]


def test_batch_scores_in_range_and_has_reasons():
    scorer, df = _scorer()
    out = scorer.score_batch(df)
    assert out["anomaly_score"].between(0.0, 1.0).all()
    assert "reasons" in out.columns
    assert out["severity"].isin(["INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"]).all()


def test_schema_mismatch_in_feature_config():
    scorer, df = _scorer()
    scorer.feature_config["feature_schema_version"] = "edge_features_OLD"
    # score_batch still works (columns present) but artifact-load path guards version;
    # here we assert the guard exists on the classmethod.
    import json
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        scorer.model.save(d / "model.joblib")
        scorer.statistical.save(d / "statistical.joblib")
        (d / "calibration.json").write_text(json.dumps(scorer.calibration))
        (d / "feature_config.json").write_text(json.dumps(scorer.feature_config))
        try:
            EdgeBehaviorScorer.from_artifact(d)
            raise AssertionError("expected schema mismatch failure")
        except ValueError:
            pass
