"""Analyst feedback contract + local store tests."""
from __future__ import annotations

from datetime import UTC, datetime

from ai.shadow.feedback.schema import AnalystFeedbackV1, AnalystVerdict
from ai.shadow.feedback.store import FeedbackStore


def test_feedback_schema_and_store(tmp_path):
    store = FeedbackStore(tmp_path / "feedback.jsonl")
    fb = AnalystFeedbackV1(
        inference_id="rel:asset:a|asset:b|COMMUNICATES_WITH@2024-03-02T02:13:00Z",
        verdict=AnalystVerdict.BENIGN_UNUSUAL,
        analyst_reason="scheduled maintenance",
        timestamp=datetime(2024, 3, 2, 3, 0, tzinfo=UTC),
    )
    store.add(fb)
    store.add(fb)
    loaded = store.read()
    assert len(loaded) == 2
    assert loaded[0].verdict == "benign_unusual"


def test_feedback_verdict_values():
    values = {v.value for v in AnalystVerdict}
    assert values == {"benign_expected", "benign_unusual", "suspicious",
                      "confirmed_security_incident", "unknown"}
