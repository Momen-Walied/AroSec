"""Generate Phase 4C graph-data-readiness artifacts.

    python -m ai.graph_intelligence.readiness.readiness_report
"""
from __future__ import annotations

import json
from pathlib import Path

from ai.graph_intelligence.config import GraphIntelligenceConfig
from ai.graph_intelligence.data.loader import load_assets, load_edge_features
from src.config import get_settings

from .contracts import ReadinessStatus
from .ground_truth import classify_identity_quality, validate_clock
from .scenario_catalog import (
    CONTROLS,
    ENTRY_GATE,
    REPLICATION_DIMENSIONS,
    REPLICATION_MIN_INSTANCES,
    catalogue,
)
from .structural_metrics import compute_structural_metrics
from .temporal_metrics import compute_temporal_metrics
from .validators import TH, evaluate_readiness

CFG = GraphIntelligenceConfig()
REPORTS: Path | None = None


def _w(name: str, lines: list[str]) -> Path:
    assert REPORTS is not None
    p = REPORTS / name
    p.write_text("\n".join(lines) + "\n")
    return p


def _new_node_samples() -> int:
    """Reuse Phase 4A cold-start counts if the design report is present."""
    p = get_settings().reports_dir / "ai" / "temporal_graph_design" / "results.json"
    if p.exists():
        d = json.loads(p.read_text())
        cs = d.get("cold_start_counts", {})
        return int(cs.get("new_node_known_network", 0)) + int(cs.get("new_node_new_edge", 0))
    return 0


def assess_current(cfg: GraphIntelligenceConfig | None = None) -> dict:
    cfg = cfg or CFG
    df = load_edge_features(cfg)
    assets = load_assets(cfg)
    structural = compute_structural_metrics(df)
    temporal = compute_temporal_metrics(df)

    method = assets["identity_method"].iloc[0] if "identity_method" in assets and len(assets) else None
    level = classify_identity_quality(method)

    role_cov = float((assets["asset_type"].notna() & (assets["asset_type"] != "unknown")).mean()) if "asset_type" in assets else 0.0
    zone_cov = 0.0
    for c in ("vlan_id", "subnet"):
        if c in assets and assets[c].notna().any():
            zone_cov = max(zone_cov, float(assets[c].notna().mean()))

    # roles exclude the placeholder 'unknown' (a real role requires actual role metadata)
    roles: dict[str, int] = {}
    if "asset_type" in assets:
        real = assets[assets["asset_type"].notna() & (assets["asset_type"] != "unknown")]
        roles = {str(k): int(v) for k, v in real["asset_type"].value_counts().items()}

    dataset_identity = {
        "dataset_id": cfg.dataset_id, "dataset_version": "v0.2",
        "capture_id": None, "lab_run_id": None,
        "schema_versions": {"data_contract": "0.2"},
        "generated_at": None, "source_manifests": ["processed/v2/build_manifest_v2.json"],
        "checksums": {},
    }

    ground_truth_rows: list[dict] = []   # UNSW has structural ground truth: NONE
    new_node_samples = _new_node_samples()

    dims = evaluate_readiness(structural=structural, temporal=temporal, identity_level=level,
                              ground_truth_rows=ground_truth_rows, new_node_samples=new_node_samples,
                              role_coverage=role_cov, zone_coverage=zone_cov,
                              roles=roles, dataset_identity=dataset_identity)
    overall = ReadinessStatus.PASS if all(d.status == ReadinessStatus.PASS for d in dims if d.critical) \
        else (ReadinessStatus.FAIL if any(d.status == ReadinessStatus.FAIL for d in dims if d.critical)
              else ReadinessStatus.WARN)
    clock = validate_clock(df.window_start.to_numpy())
    return {"structural": structural, "temporal": temporal, "identity_level": str(level),
            "role_coverage": role_cov, "zone_coverage": zone_cov,
            "roles": roles, "dataset_identity": dataset_identity,
            "new_node_samples": new_node_samples, "clock": clock,
            "dimensions": dims, "overall": str(overall),
            "gnn_entry_gate_passed": overall == ReadinessStatus.PASS}


def generate(cfg: GraphIntelligenceConfig | None = None) -> dict:
    global REPORTS
    REPORTS = get_settings().reports_dir / "ai" / "graph_data_readiness"
    REPORTS.mkdir(parents=True, exist_ok=True)
    a = assess_current(cfg)
    s, t = a["structural"], a["temporal"]
    dim_rows = [(d.dimension, str(d.status), str(d.critical), "; ".join(d.reasons) or "-")
                for d in a["dimensions"]]

    written = []
    written.append(_w("readiness_framework.md", [
        "# Readiness Framework", "",
        "Transparent, framework-independent validators that decide whether a dataset may be used "
        "for Temporal GNN research. Dimensions are reported individually (never hidden in one "
        "opaque score); each is PASS / WARN / FAIL, and **every critical dimension must PASS** for "
        "the entry gate to open.", "",
        "| dimension | critical | rule (summary) |", "|---|---|---|",
        "| STRUCTURAL_DIVERSITY | yes | hub dominance, independent neighbourhoods, 2-hop gain, node count |",
        "| TEMPORAL_DIVERSITY | yes | relationship births, inactivity transitions |",
        "| IDENTITY_QUALITY | yes | identity level ≥ L2 |",
        "| GROUND_TRUTH_QUALITY | yes | expected + unusual structural ground truth present |",
        "| GROUND_TRUTH_PROVENANCE | yes | independent source (never the anomaly outputs) |",
        "| NON_HUB_COVERAGE | yes | non-hub target edges ≥ 100 |",
        "| NEW_EDGE_COVERAGE | yes | new-edge events ≥ 50 |",
        "| COLD_START_COVERAGE | yes | new-node samples ≥ 20 |",
        "| ROLE_DIVERSITY | yes | role + zone metadata present |",
        "| ROLE_GENERALIZATION | yes | ≥ 3 independent assets per key role (hold-out) |",
        "| SCENARIO_REPLICATION | yes | ≥ 3 instances/scenario, ≥ 8 scenarios |",
        "| SPLIT_QUALITY | yes | independent topology regions to hold out |",
        "| TWO_HOP_CONTEXT | yes | 2-hop adds local (>0.5) but not whole-graph (<80% of nodes) context |",
        "| DATASET_INTEGRITY | yes | dataset id/version/capture id/checksums recorded |", "",
        "Thresholds: " + json.dumps(TH), "",
    ]))

    written.append(_w("structural_requirements.md", [
        "# Structural Requirements", "",
        "A dataset must be structurally **non-degenerate**: multiple local neighborhoods, no single "
        "node owning the sample distribution, and actual 2-hop information.", "",
        "## Required (REQUIRED)",
        "- ≥ 20 nodes; ≥ 2 independent local neighbourhoods (nodes of degree ≥ 2 split into ≥ 2 "
        "connected parts).",
        "- top-1 node incident to < 50% of edge-windows (FAIL), < 30% preferred (WARN).",
        "- 2-hop neighbourhood adds > 0.5 nodes on average over 1-hop.",
        "- ≥ 100 non-hub target edges.",
        "## Recommended",
        "- ≥ 4 independent neighbourhoods; degree entropy ≥ 2.0; clustering > 0.",
        "## Optional",
        "- heterogeneity (services/zones) — helpful, not forced.",
        "", "## Role-holdout feasibility (amendment 1)", "",
        "A dataset may contain **many nodes and still be unsuitable** for inductive graph "
        "evaluation if each role is represented by only one device. Total node count alone must "
        "**not** make a dataset appear ready. For every key role participating in "
        "train/validation/test generalization, require **≥ 3 independent asset instances** "
        "(e.g. Camera-01/02/03, PLC-01/02/03). Fewer instances → ROLE_GENERALIZATION WARN or FAIL "
        "depending on whether the planned hold-out is still statistically meaningful.", "",
        "## Current UNSW measured", "", "```json",
        json.dumps(s, indent=2), "```", "",
    ]))

    written.append(_w("temporal_requirements.md", [
        "# Temporal Requirements", "",
        "- ≥ 50 relationship births over the capture; ≥ 10 inactivity transitions (gaps > 24 h).",
        "- Repeated new-peer events, peer-set turnover > 0, and observable bursts/chains.",
        "- Enough distinct transition *types* represented (see scenario catalogue).", "",
        "## Current UNSW measured", "", "```json", json.dumps(t, indent=2), "```", "",
    ]))

    written.append(_w("identity_requirements.md", [
        "# Identity Requirements", "",
        "| level | meaning | readiness |", "|---|---|---|",
        "| L0 | IP-only provisional entity | FAIL |",
        "| L1 | IP + stable MAC | WARN |",
        "| L2 | MAC + DHCP/DNS/OUI corroboration | PASS (minimum) |",
        "| L3 | operator-confirmed asset identity/role | PASS (preferred) |", "",
        "Graph metrics must be reported separately by identity level, and IP churn must never be "
        "treated as structural change.", "",
        f"Current UNSW: **{a['identity_level']}** → FAIL.", "",
    ]))

    written.append(_w("ground_truth_schema.md", [
        "# Structural Ground-Truth Schema", "",
        "`StructuralTransitionGroundTruthV1` (research layer). Structure only; **no attack-stage "
        "semantics** (`attack_related` is true/false/unknown).", "",
        "Fields: `ground_truth_id`, `scenario_id`, `start_time`, `end_time`, `transition_type`, "
        "`expectedness` (EXPECTED/UNUSUAL/UNKNOWN), `source_asset_ids`, `destination_asset_ids`, "
        "`relationship_ids`, `zone_before`/`zone_after`, `role_context`, `scenario_origin` "
        "(LAB_CONTROLLED/OPERATOR_CONFIRMED/SYNTHETIC/DATASET_LABEL), `confidence`, `notes`, "
        "`evidence_refs`, `attack_related`.", "",
        "Transition types: " + ", ".join(f"`{x}`" for x in
                                         ["expected_structural_transition", "unusual_structural_transition",
                                          "normal_role_consistent_new_edge", "role_inconsistent_new_edge",
                                          "topology_rewiring", "fanout_burst", "inbound_convergence",
                                          "chain_formation", "peer_set_replacement",
                                          "cross_zone_communication"]) + ".",
        "",
        "Ground truth must not live only in human memory — it is a versioned file.", "",
        "## Independence / provenance (amendment 2)", "",
        "Structural ground truth **MUST NOT** be derived from the same anomaly outputs or "
        "telemetry patterns being evaluated. Forbidden sources: EdgeAnomalyResult, "
        "NodeAnomalyResult, GraphContext score, BehavioralEpisode, or an observed traffic spike "
        "after the fact.", "",
        "Allowed independent sources: lab orchestration system, operator action log, experiment "
        "controller, maintenance/change ticket, externally supplied dataset labels. For controlled "
        "lab scenarios, scenario start/end must be recorded **at execution time** by the "
        "orchestrator or operator.", "",
        "Provenance fields: `ground_truth_source` (enum), `ground_truth_recorded_at`, "
        "`orchestrator_run_id`, `operator_action_id`. A dataset with missing or forbidden "
        "provenance **FAILS** GROUND_TRUTH_PROVENANCE.", "",
    ]))

    written.append(_w("scenario_catalog.md", [
        "# Controlled Scenario Catalogue (LAB-G01..G12)", "",
        "| id | name | expected label | expectedness | duration (min) | entities |",
        "|---|---|---|---|---|---|",
    ] + [f"| {c['scenario_id']} | {c['name']} | {c['expected_label']} | {c['expectedness']} | "
         f"{c['duration_min']} | {', '.join(c['entities'])} |" for c in catalogue()] + [
        "", "## Hard controls", "",
        "| unusual | control | pairs with |", "|---|---|---|",
    ] + [f"| {c['unusual']} | {c['control']} | {c['pairs_with']} |" for c in CONTROLS] + [
        "", "## Replication", "",
        f"- ≥ **{REPLICATION_MIN_INSTANCES}** instances per key scenario across: "
        f"{', '.join(REPLICATION_DIMENSIONS)}.",
        "- Avoid learning a specific asset id: vary source/destination/timing/region.", "",
    ]))

    written.append(_w("split_strategy.md", [
        "# Split Strategy", "",
        "Do NOT randomly split scenario rows. Use a hierarchy, from strongest to weakest:",
        "",
        "1. **ASSET holdout** — train on some entities' instances, test the SAME structural pattern "
        "on unseen entities (primary generalization test).",
        "2. **TOPOLOGY-REGION holdout** — hold out a whole local neighbourhood.",
        "3. **TIME** — earlier vs later capture (drift test).",
        "4. **SCENARIO-INSTANCE** — same class, different assets/times.", "",
        "Report results per cold-start category and per identity level; never pool across holdouts.", "",
        "## Role-generalization test", "",
        "- TRAIN: `camera_01 -> nvr`",
        "- TEST (expected): `camera_04 -> nvr`",
        "- TEST (unusual): `camera_04 -> plc`", "",
        "A model must rely on structural/role context, not asset ids.", "",
    ]))

    written.append(_w("current_unsw_readiness.md", [
        "# Current UNSW Readiness", "",
        f"- **Evaluated package:** `{a['dataset_identity']['dataset_id']}` "
        f"`{a['dataset_identity']['dataset_version']}` (capture_id: "
        f"{a['dataset_identity']['capture_id']})",
        f"- Overall: **{a['overall']}** · GNN entry gate: "
        f"**{'PASS' if a['gnn_entry_gate_passed'] else 'BLOCKED'}**",
        f"- Identity: {a['identity_level']} · role coverage {a['role_coverage']:.0%} · "
        f"zone coverage {a['zone_coverage']:.0%}",
        f"- Clock: {a['clock']['status']} (out-of-order {a['clock']['out_of_order']}, "
        f"missing {a['clock']['missing']})", "",
        "| dimension | status | critical | reasons |", "|---|---|---|---|",
    ] + [f"| {d[0]} | {d[1]} | {d[2]} | {d[3]} |" for d in dim_rows] + [
        "", "## Why GNN is blocked (derived, not forced)", "",
        f"- top-1 node incident to **{s['hub_dominance_top1']:.1%}** of edge-windows; "
        f"top-5 {s['hub_dominance_top5']:.1%}.",
        f"- independent local neighbourhoods: **{s['independent_local_neighborhoods']}**.",
        f"- 2-hop minus 1-hop: **{s['two_hop_minus_one_hop']}** nodes.",
        f"- non-hub target edges: **{s['non_hub_target_edges']}**.",
        f"- new-edge events: **{s['new_edge_count']}**.",
        f"- new-node samples: **{a['new_node_samples']}**.",
        "- structural ground truth: **0**.",
        "",
    ]))

    written.append(_w("lab_topology_recommendation.md", [
        "# Lab Topology Recommendation (non-degenerate)", "",
        "Design a small IIoT lab with **multiple** high-degree nodes and genuine non-hub-to-non-hub "
        "traffic. Do NOT optimise the topology to make the AI look good.", "",
        "Components: Engineering Workstation · HMI · Historian · PLC-01/02/03 · MQTT Broker · "
        "NVR · 2–4 Cameras · IoT Sensor group · DNS · NTP · Gateway · Jump/Admin Workstation.",
        "", "Zones: IT · OT · Engineering · Control · IoT · Video/CCTV · Infrastructure.", "",
        "Topology properties:", "",
        "- ≥ 2 independent local neighbourhoods; more than one high-degree node.",
        "- non-hub-to-non-hub communication (control plane, sensor groups).",
        "- role-consistent edges + rare-but-legitimate edges.",
        "- cross-zone paths (allowed vs disallowed).",
        "- persistent (PLC↔Historian) and ephemeral (camera↔NVR) relationships.", "",
        "Zones feed ground truth: evaluate *structurally plausible* vs *cross-zone unusual*. Do not "
        "assume every customer site uses the same segmentation.", "",
    ]))

    written.append(_w("capture_package_spec.md", [
        "# Capture Package Spec (handoff from Network/Security)", "",
        "```",
        "site_metadata.json",
        "assets.parquet",
        "relationships.parquet",
        "observations.parquet",
        "asset_identity_observations.parquet",
        "zones.parquet",
        "roles.parquet",
        "structural_ground_truth.parquet",
        "scenario_manifest.json",
        "capture_manifest.json",
        "README.md",
        "```", "",
        "Compatibility: adapters sit **above** the frozen v0.2 contract; v0.2 is never changed.",
        "", "## Required observation fields", "",
        "timestamp, src identity, dst identity, src IP, dst IP, protocol, port, bytes, packets, "
        "relationship identity, capture source. Optional: MAC, VLAN, zone, role, service, DNS, "
        "DHCP, TLS, MQTT topics, OT protocol metadata.", "",
        "## Manifest (must record)", "",
        "scenario_id, site/lab id, start/end, operator, assets involved, expected transition, "
        "capture completeness, time-sync status, notes. Ground truth must NOT live only in memory.", "",
        "## Clock quality", "",
        f"- tolerance {1.0}s; missing timestamps FAIL; out-of-order WARN and must be documented "
        "(never silently reordered).", "",
        "## Privacy", "",
        "Tooling runs **on-site**; only aggregated statistics / readiness status / permitted "
        "scenario metadata leave the site. No packet payload export required.", "",
        "## Dataset integrity / versioning (amendment 3)", "",
        "Every capture package must record an **immutable identity**: `dataset_id`, "
        "`dataset_version`, `capture_id` / `lab_run_id`, `schema_versions`, `generated_at`, "
        "`source_manifests`, and file `checksums` where practical. A readiness report must state "
        "**exactly which immutable package it evaluated**, so later benchmark results cannot "
        "silently refer to a different capture revision.", "",
    ]))

    written.append(_w("temporal_gnn_entry_gate.md", [
        "# Temporal GNN Entry Gate", "",
        "Phase 4D may not begin unless **all critical dimensions PASS**.", "",
        "| requirement | rule |", "|---|---|",
    ] + [f"| {k} | {v} |" for k, v in ENTRY_GATE] + [
        "", f"Current UNSW gate: **{'PASS' if a['gnn_entry_gate_passed'] else 'BLOCKED'}**.", "",
    ]))

    written.append(_w("readiness.md", [
        "# Graph Data Readiness — Summary", "",
        f"- Overall status: **{a['overall']}**",
        f"- GNN entry gate: **{'PASS' if a['gnn_entry_gate_passed'] else 'BLOCKED'}**", "",
        "| dimension | status |", "|---|---|",
    ] + [f"| {d[0]} | {d[1]} |" for d in dim_rows] + [
        "", "Unlock condition: all critical dimensions PASS on a captured dataset (see "
        "temporal_gnn_entry_gate.md).", "",
    ]))

    results = {"structural": s, "temporal": t, "identity_level": a["identity_level"],
               "role_coverage": a["role_coverage"], "zone_coverage": a["zone_coverage"],
               "roles": a["roles"], "dataset_identity": a["dataset_identity"],
               "new_node_samples": a["new_node_samples"], "clock": a["clock"],
               "dimensions": [{"dimension": d.dimension, "status": str(d.status),
                               "critical": d.critical, "reasons": d.reasons, "metrics": d.metrics}
                              for d in a["dimensions"]],
               "overall": a["overall"], "gnn_entry_gate_passed": a["gnn_entry_gate_passed"],
               "thresholds": TH, "scenario_catalog": catalogue(), "controls": list(CONTROLS),
               "entry_gate": [{"requirement": k, "rule": v} for k, v in ENTRY_GATE]}
    (REPORTS / "results.json").write_text(json.dumps(results, indent=2, default=str))
    return {"overall": a["overall"], "gnn_entry_gate_passed": a["gnn_entry_gate_passed"],
            "reports_dir": str(REPORTS), "written": [p.name for p in written]}


def main() -> None:  # pragma: no cover
    print(json.dumps(generate(), indent=2, default=str))


if __name__ == "__main__":  # pragma: no cover
    main()
