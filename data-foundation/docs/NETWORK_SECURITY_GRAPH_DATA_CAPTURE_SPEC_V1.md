# Network / Security — Graph Data Capture Spec v1

Audience: network and security engineers capturing data for graph-intelligence research.
You do **not** need to know ML. If you can produce the files below for a lab or pilot site, the
research team can evaluate temporal graph intelligence. This spec is derived from the
readiness framework (`docs/AI_GRAPH_DATA_READINESS_V1.md`); it changes no existing contract.

## 1. What to capture (and why)

We need to see **who talks to whom, when, and how the pattern changes** — not payloads.

| field | required? | why |
|---|---|---|
| timestamp (UTC, ns) | **required** | ordering is the whole point |
| src identity (asset id) | **required** | graph node |
| dst identity (asset id) | **required** | graph node |
| src IP, dst IP | required | identity corroboration |
| protocol, dst port | required | relationship shape |
| bytes, packets | required | volume behaviour |
| relationship id (stable) | required | persistent edge |
| capture source (sensor/flow) | required | provenance |
| MAC | recommended | identity level L1+ |
| VLAN / zone | **required for readiness** | cross-zone ground truth |
| device role | **required for readiness** | role-consistent vs not |
| service / DNS / DHCP / OUI | recommended | identity level L2+ |
| TLS metadata, MQTT topics, OT protocol metadata | optional | richer context |

**Do NOT export packet payloads.** Tooling runs on-site; only aggregated statistics leave site.

## 2. Topology requirements (avoid another star benchmark)

The single most common failure is one gateway owning almost all traffic. Please ensure:

- **several** devices have many relationships (not one) — e.g. broker, historian, jump host;
- **non-hub-to-non-hub** traffic exists (device ↔ device, not only device ↔ gateway);
- **≥ 2 independent local neighbourhoods** (e.g. a camera/NVR cluster *and* a PLC/Historian
  cluster) that are not only connected through one node;
- both **persistent** relationships (PLC↔Historian) and **ephemeral** ones (camera↔NVR).

We will check this automatically: if one node is incident to ≥ 50% of the traffic, the dataset
**fails** graph-generalization readiness. Do not re-architect the lab to please the tool.

**Roles need repeats.** For any role you want us to *generalize* to (e.g. Camera, PLC, HMI),
provide **at least 3 separate devices** in that role (Camera-01/02/03, PLC-01/02/03 …). A site
with many devices but only **one** per role cannot be used to test whether a model learned
structure rather than a specific device.

## 3. Identity requirements

Levels: **L0** IP-only (fails) · **L1** IP+MAC · **L2** MAC + DHCP/DNS/OUI correlation (minimum)
· **L3** operator-confirmed role. Aim for **≥ L2**, prefer **L3** for the assets in scenarios.

## 4. Capture plan

1. **Baseline**: several days of ordinary operation with **no** injected changes. (We estimate the
   minimum from how often relationships recur — typically multiple full days.)
2. **Scenario periods**: run the catalogue below, one at a time where possible.
3. **Recovery**: return to normal and capture it.
Keep the clock synchronized (NTP/PTP). Note any gaps explicitly.

## 5. Scenario catalogue (structure, not attacks)

| id | what to do | expected graph change | label |
|---|---|---|---|
| LAB-G01 | known node talks to a plausible new peer | new role-consistent edge | NORMAL |
| LAB-G02 | commission a role-consistent new device | new device + expected edges | NORMAL |
| LAB-G03 | camera talks to an engineering workstation | role-inconsistent new edge | UNUSUAL |
| LAB-G04 | one node rapidly starts many new relationships | source out-degree spike | UNUSUAL |
| LAB-G05 | many nodes start contacting one destination | inbound convergence | UNUSUAL |
| LAB-G06 | a node keeps volume but replaces its peers | peer-set replacement | UNUSUAL |
| LAB-G07 | rewire edges within a neighbourhood | local topology change | UNUSUAL |
| LAB-G08 | an edge crosses zones where it normally would not | cross-zone edge | UNUSUAL |
| LAB-G09 | A→B then B→C in a short window | 2-hop chain | UNUSUAL |
| LAB-G10 | several nodes change edges at once | multi-node change | UNUSUAL |
| LAB-G11 | replace a device (new MAC/identity) | identity change in a role | NORMAL |
| LAB-G12 | scheduled admin maintenance burst | temporary legit edges | NORMAL |

**Controls are mandatory** (hard, not obvious): for every "unusual" scenario run a
structurally-similar but role-consistent control — e.g. `camera→engineering_ws` (unusual) vs
`camera→nvr` (control); `plc→arbitrary_iot` (unusual) vs `plc→historian` (control).

**Replication:** repeat each key scenario **≥ 3 times** using different source assets,
destination assets, times and topology regions.

## 6. Ground-truth procedure

For every scenario run, record a row (or a manifest entry) — **do not rely on memory**:

- scenario id, site/lab id, start/end time, operator
- assets involved, expected transition
- capture completeness, time-sync status, notes
- zone before/after and role context where known
- `attack_related`: `true` / `false` / `unknown` (only `true` if a controlled attack experiment
  actually produced it — otherwise leave `unknown`/`false`)

Record it as `structural_ground_truth.parquet` (+ `scenario_manifest.json`).

**Ground truth must be independent.** Do **not** create labels by looking at the anomaly scores
or the traffic spike afterwards. Record, per row: `ground_truth_source` (lab orchestrator /
operator action log / experiment controller / change ticket / external labels),
`ground_truth_recorded_at`, and where applicable `orchestrator_run_id` / `operator_action_id`.
Labels inferred from the alerts themselves are rejected.

## 7. File format (handoff package)

```
site_metadata.json
assets.parquet
relationships.parquet
observations.parquet
asset_identity_observations.parquet
zones.parquet
roles.parquet
structural_ground_truth.parquet
scenario_manifest.json
capture_manifest.json
README.md
```

Adapters sit **above** the frozen Data Foundation v0.2 contract; v0.2 is not modified.

**Record an immutable package identity** so results can never silently refer to a different
capture revision: `dataset_id`, `dataset_version`, `capture_id`/`lab_run_id`, `schema_versions`,
`generated_at`, `source_manifests`, and file `checksums`.

## 8. Validation procedure

Run `python -m ai.graph_intelligence.readiness.readiness_report` against the package (on-site).
It reports per-dimension PASS/WARN/FAIL and clock/manifest checks. Common rejections:
single-hub dominance, no zones/roles, L0 identity, missing ground truth, no scenario replication.

## 9. Acceptance gate

The dataset is accepted for Temporal GNN research only when **all critical dimensions PASS**:
acceptable hub dominance · ≥ 2 topology regions · ≥ 100 non-hub target edges · ≥ 50 new-edge
events · identity ≥ L2 · replicated expected/unusual scenarios **with hard controls** ·
**independent ground-truth provenance** · **≥ 3 independent assets per key role** ·
entity/topology/time holdout possible · non-global 2-hop context · **dataset package/version
integrity recorded**.

If it fails, we tell you exactly which dimension and why — and we do not start modelling.
