# AI Graph Data Readiness v1 (Phase 4C)

**Purpose.** Define and implement the data-readiness framework that must pass **before** any
Temporal GNN research (Phase 4D) is allowed. This phase trains nothing, changes no frozen
contract, and does not integrate Graph Context into the shadow runtime.

Question answered: *what structural, temporal, identity, and ground-truth properties must a
dataset satisfy before AroSec can scientifically evaluate temporal graph intelligence?*

Artifacts: `ai/graph_intelligence/readiness/` (contracts, structural/temporal metrics,
ground-truth + identity + clock + manifest validation, validators, readiness report, scenario
catalogue), `reports/ai/graph_data_readiness/*`, and the engineer-facing
`docs/NETWORK_SECURITY_GRAPH_DATA_CAPTURE_SPEC_V1.md`.

---

## 1. What is measured

Structural: node/edge count, density, components, degree distribution + entropy, hub dominance
(top-1/top-5 incidence share), assortativity, clustering, **independent local neighbourhoods**
(core components), non-hub target edges, 1-hop vs 2-hop gain, new-edge count, reappearing
relationships.

Temporal: relationship births/day, inactivity transitions (1 h / 24 h), new-peer events, burst
windows, chain formations, peer-set turnover.

Ground truth, identity, clock, manifest, scenario replication — see below.

## 2. Identity quality levels

L0 IP-only (FAIL) · L1 IP+MAC (WARN) · L2 MAC+DHCP/DNS/OUI (PASS minimum) ·
L3 operator-confirmed (PASS preferred). Metrics are reported per level; IP churn is never
treated as structural change.

## 3. Ground truth & scenario catalogue

`StructuralTransitionGroundTruthV1` records structure only (`transition_type`, `expectedness`,
`source/destination_asset_ids`, `zone_before/after`, `role_context`, `scenario_origin`,
`confidence`, `attack_related` true/false/unknown — **no attack stage**). Catalogue LAB-G01..G12
plus hard controls (e.g. `camera→engineering_ws` vs `camera→nvr`), each with setup / expected
transition / label / duration / entities / cleanup / evidence.

## 4. Split & generalization

Hierarchy: **asset holdout** (primary) → topology-region holdout → time → scenario instance.
Role-generalization test: train `camera_01→nvr`, test `camera_04→nvr` (expected) vs
`camera_04→plc` (unusual). New-node categories are first-class.

## 5. Readiness dimensions (each PASS/WARN/FAIL, never one opaque score)

STRUCTURAL_DIVERSITY · TEMPORAL_DIVERSITY · IDENTITY_QUALITY · GROUND_TRUTH_QUALITY ·
**GROUND_TRUTH_PROVENANCE** · NON_HUB_COVERAGE · NEW_EDGE_COVERAGE · COLD_START_COVERAGE ·
ROLE_DIVERSITY · **ROLE_GENERALIZATION** · SCENARIO_REPLICATION · SPLIT_QUALITY ·
TWO_HOP_CONTEXT · **DATASET_INTEGRITY**. **All critical dimensions must PASS.**

### Role-holdout feasibility (amendment 1)

Total node count alone must **not** make a dataset appear GNN-ready. For every key role that
participates in train/validation/test generalization, require **≥ 3 independent asset
instances** (e.g. Camera-01/02/03, PLC-01/02/03). Fewer instances → ROLE_GENERALIZATION
**WARN** (some roles short) or **FAIL** (no roles, or all key roles single-instance). A dataset
may contain many nodes and still be unsuitable for inductive graph evaluation if each role is
represented by only one device.

### Independent ground-truth provenance (amendment 2)

Structural ground truth **MUST NOT** be derived from the anomaly outputs under evaluation —
`EdgeAnomalyResult`, `NodeAnomalyResult`, GraphContext score, `BehavioralEpisode`, or an
after-the-fact traffic spike are **forbidden sources**. Allowed: lab orchestrator, operator
action log, experiment controller, change ticket, external dataset labels. Scenario start/end is
recorded at execution time. Provenance fields (`ground_truth_source`,
`ground_truth_recorded_at`, `orchestrator_run_id`, `operator_action_id`) are validated; missing
or forbidden provenance FAILS GROUND_TRUTH_PROVENANCE.

### Dataset package integrity (amendment 3)

Capture packages must record an immutable identity — `dataset_id`, `dataset_version`,
`capture_id`/`lab_run_id`, `schema_versions`, `generated_at`, `source_manifests`, file
`checksums` — and every readiness report states exactly which package it evaluated. Missing
id/version FAILS; missing capture id/checksums WARNs.

## 6. Current UNSW result (derived from metrics, not forced)

**14 dimensions: 10 FAIL · 3 WARN · 1 PASS. Overall FAIL · Temporal GNN entry gate: BLOCKED.**
Evaluated package: `unsw_iotraffic v0.2` (no capture id).

| dimension | status |
|---|---|
| STRUCTURAL_DIVERSITY | **FAIL** (top-1 = 50.0% of edge-windows; 1 independent neighbourhood) |
| TEMPORAL_DIVERSITY | WARN |
| IDENTITY_QUALITY | **FAIL** (L0) |
| GROUND_TRUTH_QUALITY | **FAIL** (0) |
| GROUND_TRUTH_PROVENANCE | **FAIL** (no ground truth) |
| NON_HUB_COVERAGE | **FAIL** (0 non-hub target edges) |
| NEW_EDGE_COVERAGE | WARN (74) |
| COLD_START_COVERAGE | PASS (62) |
| ROLE_DIVERSITY | **FAIL** |
| ROLE_GENERALIZATION | **FAIL** (no role metadata) |
| SCENARIO_REPLICATION | **FAIL** |
| SPLIT_QUALITY | **FAIL** |
| TWO_HOP_CONTEXT | **FAIL** (2-hop gain 60 ≈ whole graph) |
| DATASET_INTEGRITY | WARN (no capture id / checksums) |

## 7. Entry gate (Phase 4D)

See `reports/ai/graph_data_readiness/temporal_gnn_entry_gate.md`: acceptable hub dominance,
meaningful non-hub coverage, ≥2 topology regions, enough new edges/transitions, repeated
structural scenarios with expected/unusual controls, identity ≥ L2, chronological ground truth,
non-trivial (non-global) 2-hop context, and entity/topology holdout possible. **Phase 4D must not
begin until all critical dimensions PASS.**

## 8. Final answers

1. **Why UNSW fails:** single-hub star (top-1 = 50% of edge-windows; 1 independent
   neighbourhood; 2-hop = whole graph), 0 non-hub edges, L0 identity, 0 ground truth, no
   roles/zones, no replication, no holdout regions.
2. **Pass/Warn/Fail:** 10 FAIL, 3 WARN, 1 PASS (14 dimensions).
3. **Minimum structure:** ≥20 nodes, ≥2 independent local neighbourhoods, top-1 incidence
   < 50% (prefer < 30%), ≥100 non-hub target edges, 2-hop gain local not global.
4. **Acceptable hub dominance:** top-1 < 50% FAIL threshold, < 30% preferred; top-5 reported.
5. **Non-hub coverage required:** ≥100 non-hub target edges (prefer ≥500).
6. **New-edge events needed:** ≥50 (fail) / ≥200 (warn/pass target).
7. **Mandatory scenarios:** LAB-G01..G12 (at minimum G03, G04, G05, G06, G07, G08, G09, G11).
8. **Repetitions:** ≥3 instances per key scenario across source/destination/time/region; and
   **≥3 independent assets per key role** for role hold-out.
9. **Identity required:** ≥ L2 (L3 preferred).
10. **Role/zone metadata required:** role + zone for (most) assets; drives cross-zone ground truth.
11. **Duration:** ≥ a multi-day genuine baseline (estimate from recurrence/statistics) + scenario
    windows + recovery.
12. **Clock quality:** missing timestamps FAIL; out-of-order WARN and must be documented (never
    silently reordered); tolerance ~1 s, skew warn >5 s / fail >60 s.
13. **Files to deliver:** `site_metadata.json`, `assets/relationships/observations.parquet`,
    `asset_identity_observations.parquet`, `zones.parquet`, `roles.parquet`,
    `structural_ground_truth.parquet`, `scenario_manifest.json`, `capture_manifest.json`,
    `README.md` — plus an immutable package identity (dataset id/version, capture/lab run id,
    schema versions, checksums).
14. **How to record ground truth:** as versioned `StructuralTransitionGroundTruthV1` rows +
    manifest with **independent provenance** (`ground_truth_source` recorded at execution time) —
    never inferred from the anomaly outputs, never only in human memory.
15. **Train/val/test split:** asset-holdout primary, then topology region, then time, then
    scenario instance; no random scenario-row split.
16. **Unseen-asset generalization:** hold out entities; test the same structural pattern on unseen
    assets (role-generalization test).
17. **Prevent another degenerate star:** capture acceptance rule (hub-bias diagnostics) + the
    dimension gates reject single-hub datasets.
18. **Can it run on-site?** Yes — framework-independent, CPU-only, reads local files; only
    aggregated statistics/readiness status leave the site.
19. **Does UNSW pass?** **No — FAIL.**
20. **Unlock condition for Phase 4D:** all critical readiness dimensions PASS on a captured
    dataset — acceptable hub dominance, ≥2 topology regions, ≥100 non-hub edges, ≥200 new-edge
    events, identity ≥ L2, replicated expected/unusual scenarios **with hard controls**,
    **independent ground-truth provenance**, **role-holdout feasibility (≥3 assets/role)**,
    entity/topology/time holdout possible, non-global 2-hop context, and **dataset
    package/version integrity**.

## 9. Scope discipline

No GNN training, no frozen-contract change, no shadow integration, no new public dataset
download, no commit/push/tag in this phase.
