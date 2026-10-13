"""Correlator tests: determinism, temporal/relational grouping, bounds, safety."""
from __future__ import annotations

import random

import pytest

from ai.episodes.contracts.behavioral_episode import BehavioralEpisodeV1
from ai.episodes.correlator.correlator import correlate
from ai.episodes.evaluation.scenarios import build_scenario, rel, sig

GAP = 60
MAXD = 600


def test_deterministic_episode_ids():
    signals = build_scenario("SCN-E01_SAME_ENTITY_BURST")
    a = correlate(signals, GAP, MAXD)
    b = correlate(signals, GAP, MAXD)
    assert [e.episode_id for e in a] == [e.episode_id for e in b]


def test_order_independent_chronological_processing():
    signals = build_scenario("SCN-E01_SAME_ENTITY_BURST")
    shuffled = signals[:]
    random.Random(1).shuffle(shuffled)
    a = correlate(signals, GAP, MAXD)
    b = correlate(shuffled, GAP, MAXD)
    assert [(e.episode_id, len(e.involved_asset_ids)) for e in a] == \
           [(e.episode_id, len(e.involved_asset_ids)) for e in b]


def test_same_entity_burst_merges():
    eps = correlate(build_scenario("SCN-E01_SAME_ENTITY_BURST"), GAP, MAXD)
    assert len(eps) == 1
    assert str(eps[0].evidence_strength) == "STRONG"
    assert eps[0].edge_signal_count == 2 and eps[0].node_signal_count == 1


def test_shared_endpoint_chain_merges():
    eps = correlate(build_scenario("SCN-E02_CHAIN"), GAP, MAXD)
    assert len(eps) == 1


def test_unrelated_simultaneous_stay_separate():
    eps = correlate(build_scenario("SCN-E03_UNRELATED_SIMULTANEOUS"), GAP, MAXD)
    assert len(eps) == 2


def test_same_entity_large_gap_new_episode():
    eps = correlate(build_scenario("SCN-E04_SAME_ENTITY_LARGE_GAP"), GAP, MAXD)
    assert len(eps) == 2


def test_correlation_gap_sensitivity():
    signals = build_scenario("SCN-E04_SAME_ENTITY_LARGE_GAP")  # same asset 3600s apart
    assert len(correlate(signals, 60, MAXD)) == 2
    # tiny gap change doesn't merge; a huge gap still can't (3600 > any gap) -> still 2
    assert len(correlate(signals, 300, MAXD)) == 2
    # distinct: same asset 90s apart merges only when gap >= 90
    near = [sig("edge", ["asset:A", "asset:B"], rel("asset:A", "asset:B"), 0, 0.8, ["NEW_PEER"]),
            sig("edge", ["asset:A", "asset:C"], rel("asset:A", "asset:C"), 120, 0.8, ["NEW_PEER"])]
    # inactivity measured from the previous window_end (t+30) to the next window_start (t+120) = 90s
    assert len(correlate(near, 60, MAXD)) == 2
    assert len(correlate(near, 120, MAXD)) == 1


def test_max_episode_duration_bounds_percolation():
    eps = correlate(build_scenario("SCN-E07_PERCOLATION_STRESS"), GAP, MAXD)
    assert len(eps) >= 2
    assert all(e.duration_seconds <= MAXD + 60 for e in eps)


def test_active_episode_merge_is_deterministic():
    eps = correlate(build_scenario("SCN-E08_TWO_ACTIVE_MERGE"), GAP, MAXD)
    assert len(eps) == 1
    # canonical id = earliest start signal's episode
    first = sig("edge", ["asset:A", "asset:B"], rel("asset:A", "asset:B"), 0, 0.8, ["NEW_PEER"])
    from ai.episodes.correlator.correlator import _episode_id
    assert eps[0].episode_id == _episode_id(first.window_start, first.signal_id)


def test_alert_storm_is_bounded():
    eps = correlate(build_scenario("SCN-E06_ALERT_STORM"), GAP, MAXD)
    assert len(eps) == 1
    assert eps[0].edge_signal_count == 20


def test_no_future_leakage_on_closed_episode():
    signals = [
        sig("edge", ["asset:A", "asset:B"], rel("asset:A", "asset:B"), 0, 0.8, ["NEW_PEER"]),
        sig("edge", ["asset:A", "asset:C"], rel("asset:A", "asset:C"), 10, 0.8, ["NEW_PEER"]),
    ]
    eps = correlate(signals, GAP, MAXD)
    base_assets = set(eps[0].involved_asset_ids)
    future = signals + [sig("edge", ["asset:A", "asset:Z"], rel("asset:A", "asset:Z"), 100000, 0.8, ["NEW_PEER"])]
    eps2 = correlate(future, GAP, MAXD)
    first = next(e for e in eps2 if "asset:B" in e.involved_asset_ids)
    assert set(first.involved_asset_ids) == base_assets


def test_evidence_family_deduplication():
    signals = [sig("edge", ["asset:A", "asset:B"], rel("asset:A", "asset:B"), 0, 0.8,
                   ["NEW_PEER", "RELATIONSHIP_CREATION_BURST"])]
    eps = correlate(signals, GAP, MAXD)
    assert eps[0].evidence_families == ["PEER_NOVELTY"]
    assert set(eps[0].signal_reason_codes) == {"NEW_PEER", "RELATIONSHIP_CREATION_BURST"}


def test_primary_asset_ambiguous_is_null():
    # two disjoint-ish edges with different unique-max assets, no node signal
    signals = [
        sig("edge", ["asset:A", "asset:B"], rel("asset:A", "asset:B"), 0, 0.8, ["NEW_PEER"]),
        sig("edge", ["asset:A", "asset:B"], rel("asset:A", "asset:B"), 5, 0.8, ["PORT_NOVELTY"]),
    ]
    eps = correlate(signals, GAP, MAXD)
    # A appears in both, B appears in both -> tie -> null
    assert eps[0].primary_asset_id is None


def test_primary_asset_from_node_signal():
    signals = build_scenario("SCN-E05_NODE_EDGE_SUPPORT")
    eps = correlate(signals, GAP, MAXD)
    assert eps[0].primary_asset_id == "asset:A"


def test_evidence_refs_and_identity_preserved():
    im = {"asset:A": {"identity_method": "dataset_ip_fallback", "identity_confidence": 0.4}}
    eps = correlate(build_scenario("SCN-E05_NODE_EDGE_SUPPORT"), GAP, MAXD, identity_map=im)
    assert eps[0].evidence_refs
    assert eps[0].identity_methods == ["dataset_ip_fallback"]
    assert eps[0].minimum_identity_confidence == 0.4


def test_no_score_averaging_or_attack_fields():
    eps = correlate(build_scenario("SCN-E01_SAME_ENTITY_BURST"), GAP, MAXD)[0]
    assert eps.max_edge_score is not None and eps.max_node_score is not None
    import json
    blob = json.dumps(eps.model_dump(mode="json"))
    for term in ("fused", "combined_score", "attack_probability", "attack_stage", "attacker"):
        assert term not in blob
    assert eps.summary["episode_type"] == "behavioral"


def test_contract_forbids_attack_semantics():
    from pydantic import ValidationError

    signals = build_scenario("SCN-E01_SAME_ENTITY_BURST")
    eps = correlate(signals, GAP, MAXD)[0]
    data = eps.model_dump()
    data["attack_stage"] = "lateral_movement"
    with pytest.raises(ValidationError):
        BehavioralEpisodeV1.model_validate(data)
