"""Ground-truth, identity-quality, clock-quality and manifest validation helpers."""
from __future__ import annotations

from collections import Counter

import numpy as np

from .contracts import Expectedness, IdentityQualityLevel, TransitionType

CLOCK_TOLERANCE_SECONDS = 1.0
CLOCK_SKEW_WARN_SECONDS = 5.0
CLOCK_SKEW_FAIL_SECONDS = 60.0


def classify_identity_quality(identity_method: str | None, fields: dict | None = None) -> IdentityQualityLevel:
    """Map an identity method / available fields to a readiness identity level."""
    fields = fields or {}
    method = (identity_method or "").lower()
    if "operator" in method or fields.get("operator_confirmed"):
        return IdentityQualityLevel.LEVEL_3_OPERATOR_CONFIRMED
    has_mac = bool(fields.get("mac")) or "mac" in method
    corroborated = bool(fields.get("dhcp") or fields.get("dns") or fields.get("oui"))
    if has_mac and corroborated:
        return IdentityQualityLevel.LEVEL_2_MAC_DHCP_DNS_OUI
    if has_mac:
        return IdentityQualityLevel.LEVEL_1_IP_MAC
    return IdentityQualityLevel.LEVEL_0_IP_ONLY


def identity_level_index(level: IdentityQualityLevel) -> int:
    return {"L0_ip_only": 0, "L1_ip_mac": 1, "L2_mac_dhcp_dns_oui": 2,
            "L3_operator_confirmed": 3}[str(level)]


def validate_clock(timestamps) -> dict:
    """Clock-quality validation over a timestamp series (already parsed, sorted or not)."""
    ts = np.asarray(timestamps, dtype="datetime64[ns]")
    n = int(ts.size)
    if n == 0:
        return {"n": 0, "missing": 0, "out_of_order": 0, "max_gap_seconds": None,
                "status": "FAIL", "reasons": ["no timestamps"]}
    missing = int(np.isnat(ts).sum())
    valid = ts[~np.isnat(ts)]
    out_of_order = int((np.diff(valid.astype("int64")) < 0).sum()) if valid.size > 1 else 0
    gaps = np.diff(valid.astype("int64")) / 1e9 if valid.size > 1 else np.array([0.0])
    max_gap = float(gaps.max()) if gaps.size else 0.0
    reasons = []
    status = "PASS"
    if missing > 0:
        status = "FAIL"
        reasons.append(f"{missing} missing timestamps")
    if out_of_order > 0:
        status = "WARN" if status != "FAIL" else status
        reasons.append(f"{out_of_order} out-of-order records (documented, not silently reordered)")
    return {"n": n, "missing": missing, "out_of_order": out_of_order,
            "max_gap_seconds": max_gap, "tolerance_seconds": CLOCK_TOLERANCE_SECONDS,
            "status": status, "reasons": reasons}


def ground_truth_coverage(rows: list[dict]) -> dict:
    """Coverage + replication over structural ground-truth rows."""
    by_type = Counter(r.get("transition_type") for r in rows)
    by_expected = Counter(r.get("expectedness") for r in rows)
    by_origin = Counter(r.get("scenario_origin") for r in rows)
    replication = Counter(r.get("scenario_id") for r in rows)
    required = {str(t) for t in TransitionType}
    missing = sorted(required - set(by_type))
    has_unusual = by_expected.get(str(Expectedness.UNUSUAL), 0) > 0
    has_expected = by_expected.get(str(Expectedness.EXPECTED), 0) > 0
    return {
        "n": len(rows),
        "by_transition_type": dict(by_type),
        "by_expectedness": dict(by_expected),
        "by_origin": dict(by_origin),
        "missing_transition_types": missing,
        "has_expected_and_unusual": bool(has_expected and has_unusual),
        "min_scenario_replication": min(replication.values()) if replication else 0,
        "max_scenario_replication": max(replication.values()) if replication else 0,
        "distinct_scenarios": len(replication),
    }


REQUIRED_MANIFEST_FIELDS = ("scenario_id", "site_id", "start_time", "end_time", "operator",
                            "assets_involved", "expected_transition", "capture_complete",
                            "time_sync_status")


def validate_manifest(manifest: dict) -> dict:
    missing = [f for f in REQUIRED_MANIFEST_FIELDS if f not in manifest or manifest.get(f) in (None, "")]
    return {"ok": not missing, "missing_fields": missing,
            "status": "PASS" if not missing else "FAIL"}


# --- amendment 2: ground-truth independence / provenance -------------------- #
ALLOWED_GROUND_TRUTH_SOURCES = {"LAB_ORCHESTRATOR", "OPERATOR_ACTION_LOG",
                                "EXPERIMENT_CONTROLLER", "CHANGE_TICKET", "DATASET_LABELS"}
# these are the anomaly outputs under evaluation; using them as ground truth is forbidden
FORBIDDEN_GROUND_TRUTH_SOURCES = {
    "edge_anomaly_result", "node_anomaly_result", "graph_context_score",
    "behavioral_episode", "traffic_spike", "edge_score", "node_score",
}


def validate_ground_truth_provenance(rows: list[dict]) -> dict:
    """Every ground-truth row must carry an independent source + recorded-at timestamp."""
    if not rows:
        return {"ok": False, "n": 0, "missing_source": 0, "forbidden_source": 0,
                "missing_recorded_at": 0, "reasons": ["no ground truth rows"]}
    missing_source = forbidden = missing_rec = 0
    reasons = []
    for r in rows:
        src = r.get("ground_truth_source")
        if src is None:
            missing_source += 1
        elif str(src) in FORBIDDEN_GROUND_TRUTH_SOURCES:
            forbidden += 1
            reasons.append(f"forbidden ground-truth source: {src}")
        elif str(src) not in ALLOWED_GROUND_TRUTH_SOURCES:
            reasons.append(f"unknown ground-truth source: {src}")
        if not r.get("ground_truth_recorded_at"):
            missing_rec += 1
    ok = (missing_source == 0 and forbidden == 0 and missing_rec == 0)
    if missing_source:
        reasons.append(f"{missing_source} rows missing ground_truth_source")
    if missing_rec:
        reasons.append(f"{missing_rec} rows missing ground_truth_recorded_at")
    return {"ok": ok, "n": len(rows), "missing_source": missing_source,
            "forbidden_source": forbidden, "missing_recorded_at": missing_rec, "reasons": reasons}


# --- amendment 1: role-holdout feasibility ---------------------------------- #
ROLE_MIN_INSTANCES = 3


def role_holdout_feasibility(role_counts: dict[str, int], min_instances: int = ROLE_MIN_INSTANCES) -> dict:
    """A key role needs >= min_instances independent assets to be hold-out testable."""
    infeasible = {role: n for role, n in role_counts.items() if n < min_instances}
    return {"roles": dict(role_counts), "min_instances": min_instances,
            "infeasible_roles": infeasible,
            "feasible": len(role_counts) > 0 and not infeasible}


# --- amendment 3: dataset package integrity --------------------------------- #
INTEGRITY_REQUIRED = ("dataset_id", "dataset_version")
INTEGRITY_RECOMMENDED = ("capture_id", "lab_run_id", "schema_versions", "generated_at",
                         "source_manifests", "checksums")


def dataset_integrity(identity: dict) -> dict:
    missing_required = [f for f in INTEGRITY_REQUIRED if not identity.get(f)]
    missing_recommended = [f for f in INTEGRITY_RECOMMENDED if not identity.get(f)]
    status = "FAIL" if missing_required else ("WARN" if missing_recommended else "PASS")
    return {"status": status, "missing_required": missing_required,
            "missing_recommended": missing_recommended,
            "identity": {k: identity.get(k) for k in identity}}
