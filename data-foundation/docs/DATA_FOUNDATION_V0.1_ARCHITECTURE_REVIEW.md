# Data Foundation v0.1 — Architecture Review

**Status:** review only. No schema migration, no ML implemented.
**Purpose:** decide whether the current temporal-graph representation is fit for a future
industrial Temporal GNN / attack-path reconstruction system, and whether
`CommunicationEdge` is safe to freeze as a Network-Team contract.

**Method:** direct inspection of `src/` + empirical experiments on the real normalized data
(UNSW sample, X-IIoTID derivative, synthetic CICAPT scenario), plus an independent
architecture consult. All claims below are reproduced from code execution.

---

## 0. Evidence base

| Table | raw obs | edge rows | unique `edge_id` | assets | labels | lateral-mv |
|---|---:|---:|---:|---:|---:|---:|
| `unsw_iotraffic` (100k sample, real) | 100,000 | 77,102 | 79 | 63 | 0 | 0 |
| `x_iiotid` (derivative, 1,672 rows) | 1,672 | 1,118 | 35 | 29 | 728 | 77 |
| `cicapt_iiot` (synthetic fixture) | 13 | 9 | 6 | 6 | 8 | 4 |

Key structural signal: **`edge_id` is unique per pair+protocol (79 for UNSW) while rows are
per-window (77,102)**. The table therefore already carries a relationship key on every
observation row — the two concepts are conflated, not separated.

---

## 1. Current architecture (as-built)

```
adapter.load_raw()  ->  RawBundle(observations, extra_assets, campaign_seeds)
   -> pipeline.build_assets()   union-find over mac/host/device/ip  -> Asset[]
   -> pipeline.build_edges()    group by (src,dst,network_protocol,window) -> CommunicationEdge[]
   -> pipeline.build_labels()   map external labels -> AttackLabel[]
   -> pipeline.build_campaigns()-> Campaign[] (from seeds)
   -> pipeline.build_graph_events() -> GraphEvent[] (append-only, graph_version)
   -> features.build_edge_features / build_node_features (leakage-safe)
```

* Aggregation: floor timestamps to 5s/30s/60s windows (**default 30s**), half-open
  `[window_start, window_end)`.
* `CommunicationEdge` = one row per `(src, dst, network_protocol, window)`.
* `edge_id = edge:{src}|{dst}|COMMUNICATES_WITH|{proto}` (protocol-scoped).
* Pair-level fields (`first_seen`, `last_seen`, `historical_connection_count`, `is_new_peer`)
  are duplicated onto every protocol/window row of the same pair.
* Identity: union-find token merge; asset_id = `asset:{ds}:{strongest-key}`.

---

## 2. Q1 — Relationship vs. temporal observation

**Finding: `CommunicationEdge` is NEITHER a pure relationship NOR a pure observation. It is a
temporal observation that also carries duplicated relationship metadata.**

* It is an **observation** because it is window-bounded (`window_start/end`), carries
  `connection_count/packet_count/bytes_*`, and there is one row per window.
* It pretends to be a **relationship** because `edge_id` is stable across windows and every row
  repeats the pair's `first_seen`/`last_seen`/`historical_connection_count`/`is_new_peer`.

Consequences:
* The same persistent relationship appears N times (once per window) with the *same* `edge_id`
  and *duplicated* history fields — denormalized and update-prone.
* There is no first-class object answering "does A COMMUNICATES_WITH B exist, since when, how
  often" without scanning windows and de-duplicating.
* A Temporal GNN wants a **stable edge identity over time** + **per-timestep features**. The
  current shape provides both, but fused, which forces downstream code to reverse-engineer
  which columns are relational vs observational.

### Proposed separation (to evaluate, not yet adopted)

```
CommunicationRelationship            CommunicationObservation
  relationship_id (PK)                 observation_id (PK)
  src_asset_id                         relationship_id (FK)
  dst_asset_id                         window_start / window_end
  relationship_type                    network_protocol
  first_seen / last_seen               application_protocol
  total_observation_count              src_port / dst_port
  total_connection_count               connection_count / packet_count
  direction                            bytes_out / bytes_in
  evidence_sources                     direction
                                       protocol_distribution (map)
                                       observed_dst_ports (list)
                                       evidence_sources / confidence
```

**Tradeoffs**

| Aspect | Split (relationship + observation) | Single fused table (current) |
|---|---|---|
| Semantics | Clear; one entity per concept | Ambiguous; mixed time scales |
| GNN consumption | Natural (nodes, edges, per-t snapshots) | Requires de-dup + inference |
| Storage | Slight duplication avoided | History fields duplicated per row |
| Query cost | One join | No join |
| Migration | New tables + FK; existing consumers unchanged if v0.1 kept | — |
| Risk | Relationship lifecycle (when does it "end"?) must be defined | Silent staleness |

**Verdict:** the split is correct and recommended for v0.2. The alternative (single table with a
`relationship_id` column) is simpler but keeps history fields duplicated and does not give a
first-class relationship object. An intermediate option — keep one table but add
`relationship_id` and move novelty fields to the feature view — is a lower-risk stepping stone.

---

## 3. Q2 — Multi-protocol / multi-port semantics (BLOCKER)

Reproduced with a single 30s window, pair `10.0.0.21 → 10.0.0.10`:

```
observations: TCP/443/TLS, UDP/53/DNS, TCP/445/SMB, TCP/443/TLS

produced CommunicationEdge rows:
  proto=TCP  app=SMB   dst_port=443 conn=3   <-- app=TLS majority DROPPED; port 445 DROPPED
  proto=UDP  app=DNS   dst_port=53  conn=1
```

Run:
`app_protocol = sorted(app_protos)[0]` and `dst_port = min(observed dst_ports)`.
So within a protocol bucket, **all ports except the minimum are lost**, and the application
protocol is chosen **lexicographically, not by frequency or signal value**.

Impact on real data:

| Dataset | pair/window with >1 network protocol | groups with >1 dst_port | max distinct ports in one group |
|---|---:|---:|---:|
| UNSW (sample) | **13.6%** | ~0.0% | 1 |
| X-IIoTID (derivative) | — | **3.8%** | **19** |

The X-IIoTID case is decisive: one 30s window contains a **19-port scan collapsed to a single
`dst_port=min`**. Port-scan / discovery / lateral-movement signatures are exactly what
attack-path reconstruction needs, and they are currently destroyed at normalization time.

**Also lost:** `unique_src_ports`, `unique_dst_ports`, full `observed_dst_ports`,
`protocol_distribution`, `application_protocol_distribution`. None exist in `CommunicationEdge`.

**Recommendation:** canonical storage should be **narrow/long** — one observation row per
`(relationship, window, protocol, port-bucket)` — with a **wide materialized view** for GNN
input carrying `protocol_distribution`, `observed_dst_ports`, `unique_src_ports`,
`unique_dst_ports`. Do not add these fields blindly to `CommunicationEdge` while it is still
one-row-per-protocol; the shape must change first or the row would be ambiguous.

---

## 4. Q3 — Asset identity quality

Current `identity_method` enum: `mac_pinned`, `hostname`, `dataset_derived`, `ip_only`,
`manual`, `unknown`, plus `identity_confidence` and `evidence_sources` (a provenance list, not
an identity-evidence list).

Reproduced facts:
* **UNSW: every `srcMac`/`dstMac` is the literal string `null`.** Therefore all UNSW assets are
  `ip_only` with `identity_confidence = 0.30`. This is correct but **not annotated as such in
  the reports or samples** — a consumer could read `asset:unsw:192.168.1.240` as a real device
  identity. It is a *dataset IP fallback*.
* Same MAC across two IPs → correctly one asset (2 IPs). ✔
* **Latent bug:** when identifiers for one entity appear in *separate* records that a later
  record unions (e.g. DHCP reuse: `192.168.1.50` used by MAC-A then MAC-B), `finalize()`
  materializes component roots *while still merging*, so a stale root survives and the entity is
  split into **two asset_ids** (`...mac-aaaaaaaaaa01` and `...mac-aaaaaaaaaa02`, both with
  `ip 192.168.1.50`). Reproduced; locked by an `xfail` test
  (`test_known_identity_fragmentation_across_records`).
* Union-find is **time-agnostic**: it merges IP/MAC/host tokens regardless of when they were
  observed, so long-horizon DHCP reuse across genuinely different devices can also merge them in
  other configurations. There is no lease/horizon eviction.

**Verdict:** `identity_method + confidence + evidence_sources` is conceptually sufficient, but
(a) the requested vocabulary is richer than the current enum, (b) `evidence_sources` mixes data
provenance with identity evidence, and (c) the resolver is not time-bounded. Proposed identity
vocabulary for v0.2:

```
identity_method ∈ { dataset_device_id, dataset_ip_fallback, mac_based,
                    dhcp_mac_correlated, multi_signal, manual_authoritative }
identity_confidence : float
identity_evidence   : list[str]   # e.g. ["mac:aa:bb..@t1", "ip:192.168.1.50@t2"]
```

**Explicit documentation required:** for UNSW, identity is **dataset/IP-derived
(`dataset_ip_fallback`) because source MACs are null**; do not read UNSW node ids as device
identities.

---

## 5. Q4 — Training-readiness vs. schema-readiness (per dataset)

| Dataset (actual artifact) | SCHEMA_VALIDATION_READY | FEATURE_RESEARCH_READY | MODEL_TRAINING_READY | CAMPAIGN_RECONSTRUCTION_READY |
|---|:-:|:-:|:-:|:-:|
| UNSW-IoTraffic — **real flows.zip** | ✅ | ✅ (normal baseline) | ⚠️ unsupervised only (0 labels) | ❌ |
| X-IIoTID — **1,672-row CC BY derivative** | ✅ | ⚠️ not representative | ❌ | ❌ |
| X-IIoTID — **full 820,834 rows** (NOT obtained) | — | — | ❌ (gated) | ❌ |
| CICAPT-IIoT — **NOT downloaded** | ⚠️ synthetic fixture only | ❌ | ❌ | ❌ (fixture only) |
| Edge-IIoTset / CICIoT2023 | ❌ not obtained | ❌ | ❌ | ❌ |

**X-IIoTID 77 lateral-movement examples — exact limitation:** they come from a **derivative
1,672-row sample**, not the full 820,834-row dataset. The sample is *balanced-ish* by
construction, so the 77 positives are **not a representative base rate** of the real corpus and
are **far too few** to train or even reliably evaluate a lateral-movement classifier. They are
adequate only to (a) validate the label-mapping path and (b) confirm the field is populated.
Treat as *schema/feature validation*, **not** training data.

---

## 6. Q5 — Campaign / provenance readiness

CICAPT-IIoT has **not** been downloaded (registration-gated). Validation status:

| Field | Real-file validated? | Status |
|---|---|---|
| `Campaign` (identity, times, affected assets) | ❌ | validated only on the **synthetic fixture** (1 campaign) |
| `Campaign.observed_path` | ❌ | **never populated** (always `[]`) — schema-only assumption |
| `Campaign.attack_stages` | ⚠️ | synthetic stages only; real MITRE tactic sequence unverified |
| `Campaign.entry_asset_id` | ❌ | `null` everywhere; synthetic campaign has no entry |
| `Campaign.probable_objective` / `probable_target_asset_id` | ❌ | deliberately never inferred; schema-only |
| `AttackLabel` from `Attack_info.csv` | ❌ | parser exists; **no real file** to test |
| Provenance relations (Used/WGB/WTB/WDF) | ❌ | parsed to `extra_assets` only; **not modeled as graph edges** |
| Provenance → `CONTROLS`/`DEPENDS_ON`/`AUTHENTICATES_TO` | ❌ | not implemented |

**Explicitly unvalidated (schema-only):** the entire campaign/provenance path, plus
`observed_path`. The synthetic fixture proves the *plumbing* only.

---

## 7. Q6 — Graph-ML readiness matrix

| Capability | Status | Gap |
|---|:-:|---|
| Node anomaly models (unsupervised) | **PARTIALLY READY** | Node features exist, but feature windows lack MAC/vendor/device context; novel graphs need a normal baseline (only UNSW). |
| Edge behaviour models | **PARTIALLY READY** | `EdgeFeatureWindow` works, but per-window protocol/port diversity is lost upstream; no port/scan signal. |
| Temporal GNNs | **NOT READY** | No first-class relationship object; observations are protocol-scoped with min-port/first-app loss; no stable per-t edge identity decoupled from history. |
| Graph anomaly detection | **PARTIALLY READY** | A single snapshot graph exists (Neo4j export); no relationship lifecycle (add/remove) semantics; novelty fields duplicated per row. |
| Attack-path reconstruction | **NOT READY** | Needs relationship identity + directed paths + campaign labels + port/protocol detail; the latter two are unvalidated/lost. |
| Attack-stage inference | **NOT READY** | Requires real campaign/stage labels from CICAPT (not obtained); stage sequence never validated. |

---

## 8. Q7 — Temporal integrity

Tests: `tests/test_temporal_integrity.py` (9 cases) + existing suites; **62 pass, 1 xfail**
(the xfail documents the identity-fragmentation bug in §4).

Coverage added/confirmed:
* multiple protocols in the same pair/window → no cross-contamination; `last_seen ≤ window_end`
* out-of-order raw records → identical output (order-independent) ✔
* repeated relationships across windows → `historical_connection_count` monotonic and equals the
  sum of strictly-earlier windows ✔
* changing IPs (same MAC) → one asset ✔; DHCP-reuse across records → **xfail (known bug)**
* `first_seen ≤ window_start`, `last_seen ≤ window_end`, `first_seen ≤ last_seen` ✔
* `new_peer` true **exactly once** per pair ✔; `protocol_novelty` true **exactly once** per
  `(pair, protocol)` ✔
* window boundaries half-open `[start, end)` ✔
* extending data with later observations does not change earlier window features ✔

Real-data check: UNSW edges report **0** `last_seen > window_end` and **0**
`first_seen > window_start` violations.

Remaining integrity caveat: the resolver's time-agnostic unioning (§4) is a **correctness** risk
that tests alone cannot fix; it needs the v0.2 time-bounded resolver.

---

## 9. Confirmed strengths

* Strict, enforced contracts (`extra="forbid"`), UTC-normalized, facts-only edge table.
* Deterministic, order-independent normalization with a working no-leakage discipline and
  schema-level temporal guards.
* Real, reproducible ingestion for UNSW and label mapping/preservation for X-IIoTID
  (unknowns preserved, originals kept).
* Point-in-time replay via `graph_version`; Neo4j export retains temporal properties.
* Clean separation of dataset parsing from shared graph code.

## 10. Blockers

1. **Protocol/port information loss** (`min(dst_port)`, `sorted(app_protos)[0]`); a 19-port scan
   collapses to one port. (BLOCKER for attack-path / edge-behaviour ML.)
2. **Relationship vs. observation conflation** — no first-class persistent edge. (BLOCKER for
   Temporal GNN.)
3. **Identity resolution bug + time-agnostic merging** — duplicate/false asset ids under
   multi-signal or DHCP-reuse. (BLOCKER for node identity stability.)

## 11. Design ambiguities

* Is `is_new_peer` pair-level (current) or protocol-level? `edge_id` is protocol-scoped, so the
  two disagree.
* Direction handling: only `bytes`-derived; `INBOUND`-only now possible but its meaning vs.
  initiator semantics is undocumented.
* Relationship lifecycle: no rule for when a relationship is "stale" (matters for
  `EDGE_REMOVED` and path recency).
* `evidence_sources` conflates data provenance with identity evidence.

---

## 12. Proposed v0.2 schema changes (additive, non-breaking)

1. **`CommunicationRelationship`** (new): `relationship_id, src_asset_id, dst_asset_id,
   relationship_type, first_seen, last_seen, last_activity_at, total_observation_count,
   total_connection_count, direction, evidence_sources`.
2. **`CommunicationObservation`** (new, narrow): `observation_id, relationship_id, window_start,
   window_end, network_protocol, application_protocol, src_port, dst_port, connection_count,
   packet_count, bytes_out, bytes_in, direction`.
3. **Wide GNN view** (`EdgeFeatureWindow` v0.2): add `protocol_distribution` (map),
   `application_protocol_distribution`, `observed_dst_ports`, `unique_src_ports`,
   `unique_dst_ports`; keep leakage-safe novelty flags here.
4. **Identity v0.2**: richer `identity_method` vocabulary, `identity_evidence` list, and a
   **time-bounded** resolver (only union tokens observed within a lease/horizon; materialize
   roots only after all unions).
5. Keep v0.1 tables **frozen** and emit v0.2 alongside via a migration flag (`SCHEMA_VERSION`).

## 13. Migration impact

* Additive: v0.1 files remain valid; v0.2 adds tables + a materialized wide view.
* Adapters unchanged (they emit `RawObservation`); only normalization/materialization changes.
* Network Team ingestion interface unchanged; AI Team gains relationship/observation + wide
  features.
* Effort estimate: ~1–2 days for schema + resolver hardening + materializer + tests.

---

## 14. Recommendation

### **MIGRATE TO V0.2** (additive; do not delete v0.1).

Reasons:
1. Attack-path reconstruction and edge-behaviour ML **cannot** be built on a table that drops
   port/protocol diversity (demonstrated 19→1 port collapse).
2. Temporal GNNs need a stable relationship with per-timestep observations; the current fused
   table forces every consumer to reverse-engineer which columns are which.
3. Identity is not yet safe for a temporal graph (latent duplication bug + time-agnostic merges
   + UNSW IP-only identity not clearly flagged).
4. Campaign/provenance fields are **schema-only** and must be validated on real CICAPT files
   before any stage/path model — this is a data-acquisition task, independent of schema work.

### Is `CommunicationEdge` safe to freeze for the Network Team?

**Partially.** It is safe as a **stable ingestion/output contract** *only if* its exact semantics
are frozen and documented: one row per `(src, dst, network_protocol, 30s window)`;
`dst_port = min(observed)`; `application_protocol = lexicographically-first observed`; pair-level
`first_seen/last_seen/historical_connection_count/is_new_peer` duplicated per row.

It is **NOT recommended as the final graph contract** for the AI Team. Freeze v0.1 for the
Network Team's pipeline stability, and commit to the v0.2 additive model before GNN training.

### Do not proceed to ML training until:
* v0.2 relationship/observation split + wide edge features are in place;
* the identity resolver is time-bounded and de-duplicated;
* real CICAPT-IIoT files are ingested to validate campaign/provenance/stage fields.
