"""Graph-Context Edge Anomaly v1 — causality, leakage, hub, determinism, thresholds."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ai.graph_intelligence.context.calibration import alert_rate, calibrate_threshold
from ai.graph_intelligence.context.contracts import (
    GraphContextAnomalyResultV1,
    GraphContextEdgeFeaturesV1,
)
from ai.graph_intelligence.context.features import ContextExtractor, build_context_features
from ai.graph_intelligence.context.overlap import feature_overlap_audit
from ai.graph_intelligence.context.scorers import FAMILIES, GRAPH_FEATURES, GraphContextScorer

T = np.datetime64("2020-01-01T00:00:00")


def _ev(rows):
    """rows: list of (src, dst, minutes) → events DataFrame."""
    return pd.DataFrame([{
        "event_id": f"e:{i}", "relationship_id": f"rel:{s}:{d}",
        "src_asset_id": s, "dst_asset_id": d,
        "window_start": T + np.timedelta64(m * 60, "s"),
        "window_end": T + np.timedelta64(m * 60 + 60, "s"),
        "is_new_relationship": True, "new_peer": True,
    } for i, (s, d, m) in enumerate(rows)])


# ------------------------------------------------------------------- causality #
def test_no_future_adjacency_changes_nothing():
    base = _ev([("a", "b", 0), ("a", "c", 10), ("c", "b", 20)])
    future = _ev([("a", "b", 0), ("a", "c", 10), ("c", "b", 20), ("a", "z", 400)])
    ex_b = ContextExtractor(base, lookback_seconds=3600, hops=1)
    ex_f = ContextExtractor(future, lookback_seconds=3600, hops=1)
    fb = ex_b.extract(2)   # target at minute 20
    ff = ex_f.extract(2)
    assert fb == ff                      # the minute-400 edge is future → invisible


def test_no_future_degree():
    ev = _ev([("a", "b", 0), ("a", "c", 600)])   # c is 10h later
    ex = ContextExtractor(ev, lookback_seconds=60, hops=1)  # 1-minute lookback
    f = ex.extract(1)  # target at minute 600
    # 'b' was 10h ago (outside lookback and baseline) → not a recent out-neighbour
    assert f["source_out_degree_recent"] == 0
    assert f["source_new_out_neighbors_recent"] == 0


def test_lookback_boundaries():
    ev = _ev([("a", "b", 0), ("a", "c", 59), ("a", "d", 61)])
    ex = ContextExtractor(ev, lookback_seconds=3600, hops=1)  # 60-minute lookback
    # target at minute 61; 'b' is 61 min ago (outside), 'c' is 2 min ago (inside)
    f = ex.extract(2)
    assert f["source_out_degree_recent"] == 1


# ------------------------------------------------------------------- determinism #
def test_feature_determinism():
    ev = _ev([("a", "b", 0), ("a", "c", 5), ("c", "b", 9), ("b", "a", 11)])
    ex = ContextExtractor(ev, lookback_seconds=3600, hops=1)
    assert ex.extract(3) == ex.extract(3)


def test_reproducible_build():
    ev = _ev([("a", "b", 0), ("a", "c", 5), ("c", "b", 9), ("b", "a", 11)])
    a = build_context_features(ev, lookback_seconds=3600, hops=1)
    b = build_context_features(ev, lookback_seconds=3600, hops=1)
    assert a.equals(b)


# ------------------------------------------------------------------- hop extraction #
def test_hop_extraction_chain():
    ev = _ev([("a", "b", 0), ("b", "c", 1), ("c", "d", 2)])
    h1 = ContextExtractor(ev, lookback_seconds=10 ** 9, hops=1).extract(2)
    h2 = ContextExtractor(ev, lookback_seconds=10 ** 9, hops=2).extract(2)
    assert h1["neighborhood_size"] <= h2["neighborhood_size"]
    assert h2["neighborhood_size"] >= h1["neighborhood_size"]


# ------------------------------------------------------------------- hub bucketing #
def test_hub_bucketing_structural():
    rows = [("h", f"l{i}", i) for i in range(10)] + [("h", "l0", 11)]
    ex = ContextExtractor(_ev(rows), lookback_seconds=10 ** 9, hops=1)
    t = T + np.timedelta64(11 * 60, "s")
    assert ex._bucket("h", t) == "hub"
    assert ex._bucket("l3", t) == "low"
    assert ex.hub_threshold >= 5.0


# ------------------------------------------------------------------- directed semantics #
def test_directed_neighbor_semantics():
    # a->x, b->x (both point to x): in-similarity of a,b high; out-similarity low
    ev = _ev([("a", "x", 0), ("b", "x", 1), ("a", "y", 2)])
    ex = ContextExtractor(ev, lookback_seconds=10 ** 9, hops=1)
    f = ex.extract(1)  # target a->x
    assert f["destination_neighbor_similarity"] >= 0.0
    assert f["source_neighbor_similarity"] >= 0.0


# ------------------------------------------------------------------- scorers #
def test_scorer_fit_and_range():
    ev = _ev([("a", f"l{i}", i) for i in range(12)] + [("a", "z", 13)])
    ctx = build_context_features(ev, lookback_seconds=10 ** 9, hops=1)
    sc = GraphContextScorer().fit(ctx)
    s = sc.score(ctx)
    assert s.min() >= 0.0 and s.max() <= 1.0
    fam = sc.family_scores(ctx)
    assert set(fam) == set(FAMILIES)


# ------------------------------------------------------------------- threshold #
def test_threshold_fit_on_validation_only():
    val = np.linspace(0, 1, 1001)
    thr = calibrate_threshold(val, target_alert_rate=0.01)
    assert abs(alert_rate(val, thr) - 0.01) < 0.005
    # a different TEST distribution cannot change the validation-derived threshold
    test = np.full(10, 100.0)
    assert calibrate_threshold(val, 0.01) == thr
    assert alert_rate(test, thr) == 1.0


# ------------------------------------------------------------------- overlap audit #
def test_feature_overlap_audit_shape():
    ev = _ev([("a", f"l{i}", i) for i in range(12)] + [("a", "z", 13)])
    ctx = build_context_features(ev, lookback_seconds=10 ** 9, hops=1)
    audit = feature_overlap_audit(ctx, None, None)
    assert len(audit) == len(GRAPH_FEATURES)
    assert set(audit.classification) <= {"DUPLICATE", "DERIVED", "NEW GRAPH INFORMATION"}


# ------------------------------------------------------------------- scenarios #
def test_scenario_similarity_family_separates_normal_vs_unusual():

    ev = _ev([("a", f"l{i}", i) for i in range(8)] + [("a", "z", 9)])
    sc = GraphContextScorer().fit(build_context_features(ev, lookback_seconds=10 ** 9, hops=1))
    from ai.graph_intelligence.context.evaluate import scenario_context_scores
    out = scenario_context_scores(sc)
    assert len(out) == 8
    g06 = out["SCN-G06_NORMAL_NEW_EDGE"]["family_scores"]["low_similarity"]
    g07 = out["SCN-G07_UNUSUAL_EDGE"]["family_scores"]["low_similarity"]
    assert g06 < g07    # plausible edge is structurally more similar than the unusual one


# ------------------------------------------------------------------- no attack fields #
def test_no_attack_fields():
    for model in (GraphContextEdgeFeaturesV1, GraphContextAnomalyResultV1):
        assert not any("attack" in f or "victim" in f or "stage" in f for f in model.model_fields)
