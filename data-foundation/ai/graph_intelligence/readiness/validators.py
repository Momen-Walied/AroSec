"""Readiness validators: transparent per-dimension PASS / WARN / FAIL rules.

Thresholds are explicit and justified (see reports/ai/graph_data_readiness/readiness_framework.md).
Critical dimensions must PASS for the Temporal GNN entry gate to open.
"""
from __future__ import annotations

from .contracts import DimensionResult, IdentityQualityLevel, ReadinessStatus
from .ground_truth import (
    dataset_integrity,
    ground_truth_coverage,
    identity_level_index,
    role_holdout_feasibility,
    validate_ground_truth_provenance,
)

# --- thresholds (documented, not arbitrary) --------------------------------- #
TH = {
    "min_nodes": 20,
    "hub_dominance_fail": 0.50,      # one node incident to >=50% of edge-windows
    "hub_dominance_warn": 0.30,
    "min_independent_neighbourhoods_fail": 2,
    "min_independent_neighbourhoods_warn": 4,
    "two_hop_min_gain_fail": 0.5,    # 2-hop minus 1-hop average gain
    "non_hub_edges_fail": 100,
    "non_hub_edges_warn": 500,
    "new_edges_fail": 50,
    "new_edges_warn": 200,
    "temporal_births_fail": 50,
    "inactivity_fail": 10,
    "identity_min_level": 2,
    "cold_start_fail": 20,
    "replication_min": 3,
    "min_scenarios": 8,
}


def _st(fail: bool, warn: bool) -> ReadinessStatus:
    return ReadinessStatus.FAIL if fail else (ReadinessStatus.WARN if warn else ReadinessStatus.PASS)


def structural_dimension(s: dict) -> DimensionResult:
    fail = (s["hub_dominance_top1"] >= TH["hub_dominance_fail"]
            or s["independent_local_neighborhoods"] < TH["min_independent_neighbourhoods_fail"]
            or s["two_hop_minus_one_hop"] <= TH["two_hop_min_gain_fail"]
            or s["node_count"] < TH["min_nodes"])
    warn = (s["hub_dominance_top1"] >= TH["hub_dominance_warn"]
            or s["independent_local_neighborhoods"] < TH["min_independent_neighbourhoods_warn"])
    reasons = []
    if s["hub_dominance_top1"] >= TH["hub_dominance_fail"]:
        reasons.append(f"top-1 node incident to {s['hub_dominance_top1']:.1%} of edge-windows")
    if s["independent_local_neighborhoods"] < TH["min_independent_neighbourhoods_fail"]:
        reasons.append(f"only {s['independent_local_neighborhoods']} independent local neighbourhood(s)")
    if s["two_hop_minus_one_hop"] <= TH["two_hop_min_gain_fail"]:
        reasons.append(f"2-hop adds ~{s['two_hop_minus_one_hop']} nodes (no context gain)")
    if s["node_count"] < TH["min_nodes"]:
        reasons.append(f"only {s['node_count']} nodes")
    return DimensionResult(dimension="STRUCTURAL_DIVERSITY", status=_st(fail, warn),
                           critical=True, metrics=s, reasons=reasons)


def temporal_dimension(t: dict) -> DimensionResult:
    fail = t["relationship_births"] < TH["temporal_births_fail"] or t["inactivity_transitions_24h"] < TH["inactivity_fail"]
    warn = t["relationship_births"] < TH["new_edges_warn"]
    reasons = []
    if t["relationship_births"] < TH["temporal_births_fail"]:
        reasons.append(f"only {t['relationship_births']} relationship births")
    if t["inactivity_transitions_24h"] < TH["inactivity_fail"]:
        reasons.append(f"only {t['inactivity_transitions_24h']} inactivity transitions (>24h)")
    return DimensionResult(dimension="TEMPORAL_DIVERSITY", status=_st(fail, warn),
                           critical=True, metrics=t, reasons=reasons)


def identity_dimension(level: IdentityQualityLevel) -> DimensionResult:
    idx = identity_level_index(level)
    fail = idx < TH["identity_min_level"]
    reasons = [] if not fail else [f"identity level {level} below required L{TH['identity_min_level']}"]
    return DimensionResult(dimension="IDENTITY_QUALITY", status=_st(fail, False),
                           critical=True, metrics={"level": str(level), "index": idx}, reasons=reasons)


def ground_truth_dimension(rows: list[dict]) -> DimensionResult:
    cov = ground_truth_coverage(rows)
    fail = cov["n"] == 0 or not cov["has_expected_and_unusual"]
    warn = bool(cov["missing_transition_types"]) and not fail
    reasons = []
    if cov["n"] == 0:
        reasons.append("no structural ground truth recorded")
    elif not cov["has_expected_and_unusual"]:
        reasons.append("expected/unusual controls missing")
    if cov["missing_transition_types"]:
        reasons.append(f"missing transition types: {', '.join(cov['missing_transition_types'])}")
    return DimensionResult(dimension="GROUND_TRUTH_QUALITY", status=_st(fail, warn),
                           critical=True, metrics=cov, reasons=reasons)


def non_hub_dimension(s: dict) -> DimensionResult:
    n = s["non_hub_target_edges"]
    fail = n < TH["non_hub_edges_fail"]
    warn = n < TH["non_hub_edges_warn"]
    reasons = [] if not fail else [f"only {n} non-hub target edges"]
    return DimensionResult(dimension="NON_HUB_COVERAGE", status=_st(fail, warn),
                           critical=True, metrics={"non_hub_target_edges": n,
                                                  "non_hub_edge_share": s["non_hub_edge_share"]}, reasons=reasons)


def new_edge_dimension(s: dict) -> DimensionResult:
    n = s["new_edge_count"]
    fail = n < TH["new_edges_fail"]
    warn = n < TH["new_edges_warn"]
    reasons = [] if not fail else [f"only {n} new-edge events"]
    return DimensionResult(dimension="NEW_EDGE_COVERAGE", status=_st(fail, warn),
                           critical=True, metrics={"new_edge_count": n}, reasons=reasons)


def cold_start_dimension(new_node_samples: int) -> DimensionResult:
    fail = new_node_samples < TH["cold_start_fail"]
    reasons = [] if not fail else [f"only {new_node_samples} new-node samples"]
    return DimensionResult(dimension="COLD_START_COVERAGE", status=_st(fail, False),
                           critical=True, metrics={"new_node_samples": new_node_samples}, reasons=reasons)


def role_dimension(role_coverage: float, zone_coverage: float) -> DimensionResult:
    fail = role_coverage <= 0.0 or zone_coverage <= 0.0
    warn = role_coverage < 0.8 or zone_coverage < 0.8
    reasons = []
    if fail:
        reasons.append("no role/zone metadata available")
    return DimensionResult(dimension="ROLE_DIVERSITY", status=_st(fail, warn),
                           critical=True, metrics={"role_coverage": role_coverage,
                                                   "zone_coverage": zone_coverage}, reasons=reasons)


def replication_dimension(rows: list[dict]) -> DimensionResult:
    cov = ground_truth_coverage(rows)
    fail = cov["min_scenario_replication"] < TH["replication_min"] or cov["distinct_scenarios"] < TH["min_scenarios"]
    reasons = []
    if cov["n"] == 0:
        reasons.append("no scenario instances")
    else:
        if cov["min_scenario_replication"] < TH["replication_min"]:
            reasons.append(f"min replication {cov['min_scenario_replication']} < {TH['replication_min']}")
        if cov["distinct_scenarios"] < TH["min_scenarios"]:
            reasons.append(f"only {cov['distinct_scenarios']} distinct scenarios")
    return DimensionResult(dimension="SCENARIO_REPLICATION", status=_st(fail, False),
                           critical=True, metrics=cov, reasons=reasons)


def split_dimension(s: dict) -> DimensionResult:
    fail = s["independent_local_neighborhoods"] < TH["min_independent_neighbourhoods_fail"]
    reasons = [] if not fail else ["no independent topology regions to hold out"]
    return DimensionResult(dimension="SPLIT_QUALITY", status=_st(fail, False),
                           critical=True, metrics={"independent_local_neighborhoods": s["independent_local_neighborhoods"]},
                           reasons=reasons)


def two_hop_dimension(s: dict) -> DimensionResult:
    gain = s["two_hop_minus_one_hop"]
    global_collapse = gain >= 0.8 * max(s["node_count"] - 2, 1)
    fail = gain <= TH["two_hop_min_gain_fail"] or global_collapse
    reasons = []
    if gain <= TH["two_hop_min_gain_fail"]:
        reasons.append(f"2-hop adds ~{gain} nodes (no context gain)")
    if global_collapse:
        reasons.append(f"2-hop gain {gain} ~ whole graph (hub collapse, not local context)")
    return DimensionResult(dimension="TWO_HOP_CONTEXT", status=_st(fail, False),
                           critical=True, metrics={"two_hop_minus_one_hop": gain}, reasons=reasons)


def evaluate_readiness(*, structural: dict, temporal: dict, identity_level: IdentityQualityLevel,
                       ground_truth_rows: list[dict], new_node_samples: int,
                       role_coverage: float, zone_coverage: float,
                       roles: dict[str, int] | None = None,
                       dataset_identity: dict | None = None) -> list[DimensionResult]:
    return [
        structural_dimension(structural),
        temporal_dimension(temporal),
        identity_dimension(identity_level),
        ground_truth_dimension(ground_truth_rows),
        provenance_dimension(ground_truth_rows),
        non_hub_dimension(structural),
        new_edge_dimension(structural),
        cold_start_dimension(new_node_samples),
        role_dimension(role_coverage, zone_coverage),
        role_generalization_dimension(roles or {}),
        replication_dimension(ground_truth_rows),
        split_dimension(structural),
        two_hop_dimension(structural),
        dataset_integrity_dimension(dataset_identity or {}),
    ]


def provenance_dimension(rows: list[dict]) -> DimensionResult:
    """Ground truth must come from an independent source (never the anomaly outputs)."""
    p = validate_ground_truth_provenance(rows)
    fail = not p["ok"]
    reasons = list(p["reasons"]) if fail else []
    return DimensionResult(dimension="GROUND_TRUTH_PROVENANCE", status=_st(fail, False),
                           critical=True, metrics=p, reasons=reasons)


def role_generalization_dimension(roles: dict[str, int]) -> DimensionResult:
    """>= N independent assets per key role for hold-out generalization (amendment 1)."""
    f = role_holdout_feasibility(roles)
    if not roles:
        fail = True
    elif not f["feasible"]:
        # all key roles single-instance → cannot hold out any role
        fail = len(f["infeasible_roles"]) == len(roles)
    else:
        fail = False
    warn = bool(f["infeasible_roles"]) and not fail
    reasons = []
    if not roles:
        reasons.append("no role assignments (cannot test role hold-out)")
    elif f["infeasible_roles"]:
        reasons.append("key roles with < {} independent assets: {}".format(
            f["min_instances"], ", ".join(f"{r}({n})" for r, n in f["infeasible_roles"].items())))
    return DimensionResult(dimension="ROLE_GENERALIZATION", status=_st(fail, warn),
                           critical=True, metrics=f, reasons=reasons)


def dataset_integrity_dimension(identity: dict) -> DimensionResult:
    integ = dataset_integrity(identity)
    fail = integ["status"] == "FAIL"
    warn = integ["status"] == "WARN"
    reasons = []
    if integ["missing_required"]:
        reasons.append(f"missing required identity: {', '.join(integ['missing_required'])}")
    if integ["missing_recommended"]:
        reasons.append(f"missing recommended integrity: {', '.join(integ['missing_recommended'])}")
    return DimensionResult(dimension="DATASET_INTEGRITY", status=_st(fail, warn),
                           critical=True, metrics=integ, reasons=reasons)
