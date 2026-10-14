"""Temporal Graph Intelligence v1 — leakage, determinism, causality and scenario tests."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ai.graph_intelligence.config import GraphIntelligenceConfig
from ai.graph_intelligence.contracts import (
    ColdStartCategory,
    TemporalGraphSampleV1,
    event_id_for,
    sample_id_for,
    target_id_for,
)
from ai.graph_intelligence.data.builder import (
    _cold_start,
    build_events,
    build_nodes,
    build_samples,
    build_targets,
)
from ai.graph_intelligence.data.ego import extract_ego
from ai.graph_intelligence.data.loader import load_edge_features
from ai.graph_intelligence.data.negative_sampling import is_temporal_safe, sample_negatives
from ai.graph_intelligence.data.normalization import TrainOnlyStandardizer
from ai.graph_intelligence.data.statistics import compute_graph_statistics
from ai.graph_intelligence.evaluation.harness import run_scenarios
from ai.graph_intelligence.evaluation.scenarios import all_scenarios

CFG = GraphIntelligenceConfig()
MAX = 1500


@pytest.fixture(scope="module")
def events() -> pd.DataFrame:
    raw = load_edge_features(CFG)
    return build_events(CFG, raw)


@pytest.fixture(scope="module")
def samples(events):
    df, boundaries = build_samples(CFG, events, max_samples=MAX)
    return df, boundaries


# ---------------------------------------------------------------- causality / leakage #
def test_no_future_edges_referenced(samples, events):
    df, _ = samples
    ws_by_id = dict(zip(events.event_id, events.window_start, strict=False))
    for r in df.itertuples(index=False):
        for eid in r.causal_event_ids:
            assert ws_by_id[eid] < r.as_of


def test_no_future_neighbors(samples, events):
    df, _ = samples
    # every neighbor of a sample is an endpoint of a causal event (pre-as_of)
    ev = events.set_index("event_id")
    for r in df.itertuples(index=False):
        endpoints = set()
        for eid in r.causal_event_ids:
            row = ev.loc[eid]
            endpoints.add(row.src_asset_id)
            endpoints.add(row.dst_asset_id)
        assert set(r.neighbor_node_ids) <= endpoints


def test_samples_chronologically_ordered(samples):
    df, _ = samples
    ts = pd.to_datetime(df.as_of).to_numpy()
    assert np.all(ts[:-1] <= ts[1:])


def test_sample_has_no_episode_fields():
    fields = set(TemporalGraphSampleV1.model_fields)
    assert not any("episode" in f for f in fields)


# ---------------------------------------------------------------- determinism #
def test_deterministic_ids(events):
    a, _ = build_samples(CFG, events, max_samples=300)
    b, _ = build_samples(CFG, events, max_samples=300)
    assert list(a.sample_id) == list(b.sample_id)
    assert list(a.target_event_id) == list(b.target_event_id)
    t1 = build_targets(a, CFG)
    t2 = build_targets(b, CFG)
    assert list(t1.target_id) == list(t2.target_id)


def test_event_ids_unique_and_shaped(events):
    assert events.event_id.is_unique
    assert events.event_id.iloc[0].startswith("gte:")


def test_id_helpers_deterministic():
    import datetime as dt
    w = dt.datetime(2016, 10, 1, tzinfo=dt.UTC)
    assert event_id_for("rel:x", w) == event_id_for("rel:x", w)
    s = sample_id_for("gte:abc", 1, 3600)
    assert target_id_for(s, 1, 1).startswith("tgt:")


def test_reproducible_dataset_metadata(events):
    a, _ = build_samples(CFG, events, max_samples=400)
    b, _ = build_samples(CFG, events, max_samples=400)
    assert a.cold_start_category.tolist() == b.cold_start_category.tolist()
    assert a.neighbor_node_ids.tolist() == b.neighbor_node_ids.tolist()


# ---------------------------------------------------------------- negative sampling #
def _adj():
    return {"a": {"b", "c"}, "b": {"a"}, "c": {"a"}, "d": {"e"}, "e": {"d"}}


def test_negative_sampling_deterministic():
    kw = dict(src="a", dst="b", as_of="T", all_nodes=["a", "b", "c", "d", "e"],
              known_edges_before={("a", "b")}, future_edges_within_horizon=set(),
              adjacency=_adj(), k=3, seed=7)
    assert sample_negatives(**kw) == sample_negatives(**kw)


def test_negative_sampling_temporal_safe():
    negs = sample_negatives(src="a", dst="b", as_of="T",
                            all_nodes=["a", "b", "c", "d", "e"],
                            known_edges_before={("a", "b")},
                            future_edges_within_horizon={("a", "d")},
                            adjacency=_adj(), k=5, seed=7)
    picked = {n["dst_asset_id"] for n in negs}
    assert "b" not in picked          # known edge excluded
    assert "d" not in picked          # future positive excluded
    assert all(n["temporal_safe"] for n in negs)
    assert is_temporal_safe("a", "d", {("a", "b")}, {("a", "d")}) is False


def test_negative_categories_assigned():
    negs = sample_negatives(src="a", dst="b", as_of="T",
                            all_nodes=["a", "b", "c", "d", "e"],
                            known_edges_before={("a", "b")}, future_edges_within_horizon=set(),
                            adjacency=_adj(), k=5, seed=1)
    cats = {n["category"] for n in negs}
    assert cats & {"hard", "temporally_plausible", "new_peer", "random_non_edge"}


# ---------------------------------------------------------------- cold start #
def test_cold_start_categories():
    assert _cold_start(True, True, True) == ColdStartCategory.KNOWN_NODE_KNOWN_EDGE
    assert _cold_start(True, True, False) == ColdStartCategory.KNOWN_NODE_NEW_EDGE
    assert _cold_start(True, False, True) == ColdStartCategory.NEW_NODE_KNOWN_NETWORK
    assert _cold_start(False, False, True) == ColdStartCategory.NEW_NODE_NEW_EDGE


def test_cold_start_present_in_real_samples(samples):
    df, _ = samples
    assert set(df.cold_start_category) <= {c.value for c in ColdStartCategory}


# ---------------------------------------------------------------- normalization #
def test_train_only_fitting_differs_from_full_fit():
    x = np.arange(20, dtype=float).reshape(10, 2)
    train, test = x[:6], x[6:]
    s = TrainOnlyStandardizer().fit(train)
    assert not np.allclose(s.mean_, x.mean(axis=0))
    # transform uses train statistics only
    assert np.allclose(s.transform(train).mean(axis=0), 0.0, atol=1e-9)
    assert s.transform(test).mean(axis=0).shape == (2,)


# ---------------------------------------------------------------- ego extraction #
def test_causal_neighborhood_extraction_only_past():
    base = np.datetime64("2016-10-01T00:00:00")
    ws = base + np.arange(4) * np.timedelta64(30, "s")
    src = np.array(["a", "b", "c", "a"])
    dst = np.array(["b", "c", "d", "d"])
    eid = np.array(["e0", "e1", "e2", "e3"])
    out = extract_ego(as_of=(base + np.timedelta64(90, "s")), src="a", dst="d",
                      lookback_seconds=120, hops=1, max_neighbors=10, max_events=10,
                      event_windows=ws, event_src=src, event_dst=dst, event_ids=eid)
    assert "e3" not in out["causal_event_ids"]        # target window excluded
    assert all(x in {"e0", "e1", "e2"} for x in out["causal_event_ids"])


# ---------------------------------------------------------------- statistics #
def test_graph_statistics_calculations(samples):
    st = compute_graph_statistics(CFG, lookback_sample_step=400)
    assert st["nodes"] == 63
    assert st["directed_edges"] == 74
    assert abs(st["density_directed"] - 74 / (63 * 62)) < 1e-6
    assert st["connected_components_undirected"][0] == 63
    assert st["neighborhood"]["two_hop"]["p50"] == 62.0


# ---------------------------------------------------------------- scenarios #
def test_scenarios_present_and_labelled():
    sc = {s.scenario_id: s for s in all_scenarios()}
    assert len(sc) == 8
    assert sc["SCN-G06_NORMAL_NEW_EDGE"].structurally_unusual is False
    assert sc["SCN-G07_UNUSUAL_EDGE"].structurally_unusual is True


def test_scenarios_scored():
    out = run_scenarios()
    assert len(out) == 8
    assert "structural_novelty" in next(iter(out.values()))["scores"]


# ---------------------------------------------------------------- targets linkage #
def test_targets_link_to_samples(samples):
    df, _ = samples
    t = build_targets(df, CFG)
    assert set(t.sample_id) <= set(df.sample_id)
    assert (t.label == 1).all()


def test_nodes_index_contiguous(events):
    nodes = build_nodes(CFG, events)
    assert list(nodes.node_index) == list(range(len(nodes)))
    assert nodes.node_id.is_unique
