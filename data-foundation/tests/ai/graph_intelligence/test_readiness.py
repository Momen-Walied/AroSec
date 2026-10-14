"""Graph Data Readiness (Phase 4C) tests: metrics, rules, ground truth, clock, determinism."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ai.graph_intelligence.readiness.contracts import IdentityQualityLevel, ReadinessStatus
from ai.graph_intelligence.readiness.ground_truth import (
    classify_identity_quality,
    dataset_integrity,
    ground_truth_coverage,
    identity_level_index,
    role_holdout_feasibility,
    validate_clock,
    validate_ground_truth_provenance,
    validate_manifest,
)
from ai.graph_intelligence.readiness.readiness_report import assess_current
from ai.graph_intelligence.readiness.scenario_catalog import (
    CONTROLS,
    ENTRY_GATE,
    REPLICATION_MIN_INSTANCES,
    catalogue,
)
from ai.graph_intelligence.readiness.structural_metrics import compute_structural_metrics
from ai.graph_intelligence.readiness.temporal_metrics import compute_temporal_metrics
from ai.graph_intelligence.readiness.validators import (
    dataset_integrity_dimension,
    evaluate_readiness,
    identity_dimension,
    provenance_dimension,
    role_generalization_dimension,
    structural_dimension,
    two_hop_dimension,
)


def _df(rows):
    """rows: (src, dst, minutes) → edge_features-like frame."""
    base = np.datetime64("2020-01-01T00:00:00")
    recs = []
    for s, d, m in rows:
        recs.append({"relationship_id": f"rel:{s}:{d}", "src_asset_id": s, "dst_asset_id": d,
                     "window_start": base + np.timedelta64(m * 60, "s"),
                     "window_end": base + np.timedelta64(m * 60 + 60, "s"),
                     "new_peer": True})
    df = pd.DataFrame(recs)
    df["window_start"] = pd.to_datetime(df.window_start)
    df["window_end"] = pd.to_datetime(df.window_end)
    return df


def _star(n=30):
    return _df([("h", f"l{i}", i) for i in range(n)] + [("h", "l0", n + 1)])


def _multi_neighborhood():
    # three clusters with local hubs + non-hub-to-non-hub edges (≥20 nodes, no single hub)
    rows = []
    for c in ("a", "b", "c"):
        for i in range(8):
            rows.append((f"{c}{i}", f"{c}hub", i))
            rows.append((f"{c}hub", f"{c}{i}", i + 40))
        rows += [(f"{c}0", f"{c}1", 80), (f"{c}2", f"{c}3", 81)]
    return _df(rows)


# ------------------------------------------------------------------ structural metrics #
def test_hub_dominance_detection():
    m = compute_structural_metrics(_star(30))
    assert m["hub_dominance_top1"] >= 0.5
    assert m["independent_local_neighborhoods"] <= 1   # star: at most the isolated hub core


def test_non_hub_coverage():
    star = compute_structural_metrics(_star(30))
    assert star["non_hub_target_edges"] == 0
    multi = compute_structural_metrics(_multi_neighborhood())
    assert multi["non_hub_target_edges"] >= 1
    assert multi["independent_local_neighborhoods"] >= 1


def test_structural_metrics_shape():
    m = compute_structural_metrics(_multi_neighborhood())
    for k in ("node_count", "edge_count", "density", "degree_entropy", "hub_dominance_top5",
              "assortativity", "avg_clustering", "two_hop_minus_one_hop", "new_edge_count"):
        assert k in m


def test_temporal_metrics_shape():
    m = compute_temporal_metrics(_multi_neighborhood())
    for k in ("relationship_births", "inactivity_transitions_24h", "new_peer_events",
              "burst_windows", "chain_formations", "peer_set_turnover"):
        assert k in m


# ------------------------------------------------------------------ rules #
def test_structural_rule_pass_fail():
    star = structural_dimension(compute_structural_metrics(_star(30)))
    assert star.status == ReadinessStatus.FAIL
    multi = structural_dimension(compute_structural_metrics(_multi_neighborhood()))
    assert multi.status in (ReadinessStatus.PASS, ReadinessStatus.WARN)


def test_two_hop_rule_flags_global_collapse():
    star = compute_structural_metrics(_star(30))
    assert two_hop_dimension(star).status == ReadinessStatus.FAIL


def test_identity_quality_classification():
    assert classify_identity_quality("dataset_ip_fallback") == IdentityQualityLevel.LEVEL_0_IP_ONLY
    assert classify_identity_quality(None, {"mac": True}) == IdentityQualityLevel.LEVEL_1_IP_MAC
    assert classify_identity_quality(None, {"mac": True, "dhcp": True}) == IdentityQualityLevel.LEVEL_2_MAC_DHCP_DNS_OUI
    assert classify_identity_quality(None, {"operator_confirmed": True}) == IdentityQualityLevel.LEVEL_3_OPERATOR_CONFIRMED
    assert identity_level_index(IdentityQualityLevel.LEVEL_2_MAC_DHCP_DNS_OUI) == 2
    assert identity_dimension(IdentityQualityLevel.LEVEL_0_IP_ONLY).status == ReadinessStatus.FAIL
    assert identity_dimension(IdentityQualityLevel.LEVEL_2_MAC_DHCP_DNS_OUI).status == ReadinessStatus.PASS


def test_ground_truth_coverage_and_missing():
    cov = ground_truth_coverage([])
    assert cov["n"] == 0 and cov["has_expected_and_unusual"] is False
    rows = [{"transition_type": "unusual_structural_transition", "expectedness": "UNUSUAL",
             "scenario_id": "S1", "scenario_origin": "LAB_CONTROLLED"},
            {"transition_type": "normal_role_consistent_new_edge", "expectedness": "EXPECTED",
             "scenario_id": "S2", "scenario_origin": "LAB_CONTROLLED"}]
    cov = ground_truth_coverage(rows)
    assert cov["has_expected_and_unusual"] is True
    assert cov["min_scenario_replication"] == 1


# ------------------------------------------------------------------ clock / manifest #
def test_clock_quality():
    ok = validate_clock(pd.date_range("2020-01-01", periods=10, freq="30s").to_numpy())
    assert ok["status"] == "PASS" and ok["out_of_order"] == 0
    unsorted = np.array(["2020-01-01T00:00:30", "2020-01-01T00:00:00"], dtype="datetime64[ns]")
    assert validate_clock(unsorted)["out_of_order"] == 1


def test_manifest_validation():
    ok = validate_manifest({"scenario_id": "S1", "site_id": "lab", "start_time": "t0", "end_time": "t1",
                            "operator": "op", "assets_involved": ["a"], "expected_transition": "x",
                            "capture_complete": True, "time_sync_status": "ok"})
    assert ok["ok"] is True
    assert validate_manifest({"scenario_id": "S1"})["status"] == "FAIL"


# ------------------------------------------------------------------ catalog / gate #
def test_scenario_catalog_and_controls():
    cat = catalogue()
    assert len(cat) == 12
    assert {c["scenario_id"] for c in cat} >= {"LAB-G01", "LAB-G04", "LAB-G08", "LAB-G12"}
    assert len(CONTROLS) >= 2
    assert REPLICATION_MIN_INSTANCES >= 3
    assert len(ENTRY_GATE) >= 10


# ------------------------------------------------------------------ determinism + UNSW #
def test_readiness_deterministic():
    s = compute_structural_metrics(_multi_neighborhood())
    t = compute_temporal_metrics(_multi_neighborhood())
    kw = dict(structural=s, temporal=t, identity_level=IdentityQualityLevel.LEVEL_0_IP_ONLY,
              ground_truth_rows=[], new_node_samples=0, role_coverage=0.0, zone_coverage=0.0)
    a = [str(d.status) for d in evaluate_readiness(**kw)]
    b = [str(d.status) for d in evaluate_readiness(**kw)]
    assert a == b


def test_current_unsw_correctly_evaluated():
    a = assess_current()
    assert a["overall"] == "FAIL"
    assert a["gnn_entry_gate_passed"] is False
    assert a["identity_level"] == "L0_ip_only"
    st = a["structural"]
    assert st["hub_dominance_top1"] >= 0.3
    assert st["independent_local_neighborhoods"] <= 1
    statuses = {d.dimension: str(d.status) for d in a["dimensions"]}
    assert statuses["GROUND_TRUTH_QUALITY"] == "FAIL"
    assert statuses["GROUND_TRUTH_PROVENANCE"] == "FAIL"
    assert statuses["NON_HUB_COVERAGE"] == "FAIL"
    assert statuses["ROLE_GENERALIZATION"] == "FAIL"
    assert statuses["DATASET_INTEGRITY"] in ("WARN", "FAIL")


# ------------------------------------------------------- amendments 1/2/3 #
def test_role_holdout_feasibility():
    assert role_holdout_feasibility({"camera": 3, "plc": 3})["feasible"] is True
    infeasible = role_holdout_feasibility({"plc": 1, "camera": 3})
    assert infeasible["feasible"] is False
    assert infeasible["infeasible_roles"] == {"plc": 1}


def test_role_generalization_dimension_rules():
    assert role_generalization_dimension({}).status == ReadinessStatus.FAIL          # no roles
    many_single_roles = {f"role{i}": 1 for i in range(30)}                          # 30 nodes, all single
    assert role_generalization_dimension(many_single_roles).status == ReadinessStatus.FAIL
    mixed = {"camera": 3, "plc": 1}
    assert role_generalization_dimension(mixed).status == ReadinessStatus.WARN
    good = {"camera": 3, "plc": 4, "hmi": 3}
    assert role_generalization_dimension(good).status == ReadinessStatus.PASS


def test_many_nodes_cannot_fake_readiness():
    # 30 nodes, one device per role → NOT suitable for inductive evaluation
    assert role_generalization_dimension({f"role{i}": 1 for i in range(30)}).status == ReadinessStatus.FAIL


def test_ground_truth_provenance_rules():
    forbidden = [{"ground_truth_source": "graph_context_score", "ground_truth_recorded_at": "t"}]
    assert validate_ground_truth_provenance(forbidden)["ok"] is False
    assert provenance_dimension(forbidden).status == ReadinessStatus.FAIL
    missing = [{"transition_type": "x"}]
    assert validate_ground_truth_provenance(missing)["missing_source"] == 1
    good = [{"ground_truth_source": "LAB_ORCHESTRATOR", "ground_truth_recorded_at": "t"}]
    assert validate_ground_truth_provenance(good)["ok"] is True
    assert provenance_dimension(good).status == ReadinessStatus.PASS


def test_dataset_integrity_rules():
    assert dataset_integrity({"dataset_id": "d"})["status"] == "FAIL"
    assert dataset_integrity({"dataset_id": "d", "dataset_version": "v1"})["status"] == "WARN"
    full = {"dataset_id": "d", "dataset_version": "v1", "capture_id": "c", "lab_run_id": "r",
            "schema_versions": {"x": "1"}, "generated_at": "t", "source_manifests": ["m"],
            "checksums": {"a": "b"}}
    assert dataset_integrity(full)["status"] == "PASS"
    assert dataset_integrity_dimension({"dataset_id": "d"}).status == ReadinessStatus.FAIL
