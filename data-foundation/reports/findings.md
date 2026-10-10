# Findings — Data Foundation v0.1

_Generated from actual inspection of downloaded files, not from papers._

## Summary

The v0.1 contracts, adapters, normalization pipeline, temporal features, graph
prototype, validation, and CLI are implemented and tested (**52 tests passing**).
Three of five datasets were worked end-to-end; two are gated and handled without
bypassing access controls.

| Dataset | Access outcome | Data obtained |
|---|---|---|
| CICAPT-IIoT 2024 | registration form | **none** (synthetic fixture for demo) |
| X-IIoTID 2021 | IEEE/Kaggle login | CC BY 4.0 derivative (1,672 rows) for schema validation |
| UNSW-IoTraffic 2025 | open (Dryad) | **flows.zip (4,944,068 rows, 27 devices)** |

---

## A. Datasets successfully downloaded

- **UNSW-IoTraffic 2025** — `device_pcap_summary.csv` (1.84 KB, 27 devices) and
  `flows.zip` (95.51 MB), via the official Dryad host using a real browser (Dryad's
  file streams sit behind the Anubis/"BotStopper" anti-bot challenge; a browser passes it
  legitimately — no auth bypass).
- **X-IIoTID 2021 (derivative)** — `X-IIoTID.csv` (710 KB, 1,672 rows) from Zenodo,
  **CC BY 4.0** (explicitly licensed for reuse), used only to validate schema/adapter.

## B. Datasets requiring manual access

- **CICAPT-IIoT 2024** — download is a registration form (`insert.php` → `browse.php`).
  Not bypassed. Exact steps in `reports/dataset_registry.md` and the adapter's `download()`
  notes. (Unlicensed third-party mirrors exist but are not endorsed or auto-fetched.)
- **X-IIoTID 2021 (full, 820,834 rows)** — IEEE DataPort account + terms, or Kaggle login.
- **Edge-IIoTset**, **CICIoT2023** — Kaggle / UNB registration; secondary, not downloaded.

## C. Actual sizes

| Artifact | Size |
|---|---|
| UNSW `flows.zip` | 95.51 MB (compressed) |
| UNSW extracted `flows/` (27 CSVs) | 4,944,068 flow rows |
| UNSW `device_pcap_summary.csv` | 1.84 KB |
| X-IIoTID Zenodo derivative | 710 KB (1,672 rows) |
| Total Dryad dataset (not fetched) | 28.47 GB (incl. `pcaps.zip` 13.92 GB) |

## D. Actual raw schemas found

- **UNSW flow CSV — 28 columns (verified):** `time, srcMac, dstMac, ethType, srcIp, dstIp,
  ipProto, srcPort, dstPort, flowSeqNum, srcNumPackets, dstNumPackets, srcPayloadSize,
  dstPayloadSize, srcAvgPayloadSize, dstAvgPayloadSize, srcMaxPayloadSize, dstMaxPayloadSize,
  srcStdDevPayloadSize, dstStdDevPayloadSize, flowDuration, srcAvgInterarrivalTime,
  dstAvgInterarrivalTime, avgInterarrivalTime, srcStdDevInterarrivalTime,
  dstStdDevInterarrivalTime, stdDevInterarrivalTime, allMatchedProtocols, protocol`.
- **X-IIoTID — 68 columns (verified):** `Date, Timestamp, Scr_IP, Scr_port, Des_IP, Des_port,
  Protocol, Service, Duration, Scr_bytes, Des_bytes, ... , OSSEC_alert, Login_attempt,
  File_activity, Process_activity, is_privileged, class1, class2, class3`.

## E. Dataset capabilities (inspect-verified)

| Capability | CICAPT | X-IIoTID | UNSW | Edge | CICIoT |
|---|:-:|:-:|:-:|:-:|:-:|
| node modeling | ~ (provenance) | ✓ | ✓ (IP) | ✓ | ✓ |
| edge behaviour | ✓ | ✓ | ✓✓ (baseline) | ✓ | ✓ |
| lateral movement | ✓ (T1021) | ✓✓ (77 labels) | ✗ | ✗ | ~ |
| campaign reconstruction | ✓✓ | ✗ | ✗ | ✗ | ✗ |
| long-term baseline | ✗ | ~ | ✓✓ (203 days) | ~ | ~ |

## F. Conflicts: published description vs actual files

1. **UNSW `time` format.** README says *"seconds since epoch"*; the actual files contain
   `"2016-09-30 19:30:02.820351"` datetime strings. Adapter parses both.
2. **UNSW MACs.** README documents `srcMac`/`dstMac`; in every inspected flow file they are
   the literal string `"null"` (pre-NAT capture). Consequently UNSW identity is **IP-based**
   (`identity_method=ip_only`) in v0.1 — documented, not hidden.
3. **UNSW special values.** `*` and `null` are explicit placeholders (README agrees); the
   adapter maps them to `None`.
4. **CICAPT network CSV schema.** Official `pcap2csv.py` output column names could not be
   verified while the dataset is gated; the adapter resolves columns by alias and will be
   confirmed on first real ingest.
5. **X-IIoTID filename/labels.** IEEE archive is `X-IIoTID-dataset.zip`; mirrors expose
   `X-IIoTID dataset.csv` / `XIIoTID.csv`; label columns are `class1/class2/class3`.
6. **Dryad anti-bot.** `datadryad.org/downloads/file_stream/<id>` returns 403 for
   non-browser user agents and an Anubis "Validating…" page for browser UAs; the supported
   programmatic route is the API v2 with an OAuth bearer token (account required).
7. `cicresearch.ca` over plain HTTP returned an ISP ad-injection page from this region;
   HTTPS works and redirects correctly.

## G. Normalized assets

- synthetic `cicapt_iiot`: **6**
- `unsw_iotraffic` (100k-row sample): **63**
- `x_iiotid` (derivative): **29**

Non-host IPs (multicast/loopback/link-local/reserved) are excluded from identity.

## H. Normalized temporal edges (30s windows)

- synthetic `cicapt_iiot`: **9**
- `unsw_iotraffic`: **77,102**
- `x_iiotid`: **1,118**

## I. Labeled attacks (`is_attack=true`)

- synthetic `cicapt_iiot`: **6**
- `x_iiotid`: **701**
- (`unsw_iotraffic`: 0 — no labels by design)

## J. Explicitly labeled lateral-movement observations

- synthetic `cicapt_iiot`: **4**
- `x_iiotid`: **77**

## J-bis. Correctness hardening (Oracle-style self-review)

A design review flagged a temporal-ordering defect: edges were processed grouped by
protocol, so a later window of one protocol could leak into an earlier window's
`historical_connection_count`/`last_seen` for the same pair. Fixed by processing rows in
strict chronological order grouped by `(pair, window)`, and by adding schema guards
(`first_seen <= window_start`, `last_seen <= window_end`). Regression tests were added; a
re-run over the real UNSW edges shows **0** leak violations.

## K. Fields that could not be populated

- `Asset.vendor`, `Asset.vlan_id`, `Asset.subnet`, `Asset.criticality`,
  `Asset.asset_type` — **unknown** (no evidence; never fabricated).
- `Asset.mac_addresses` for UNSW — source MACs are null.
- `AttackLabel.edge_id` — labels reference time + endpoints, not a specific window row.
- `Campaign.observed_path` / `probable_objective` / `probable_target_asset_id` — left empty/null
  (no inference in v0.1).
- `NodeFeatureWindow.failed_connection_ratio` — not available in source data (null).
- DNS features are partial (`dns_query_rate` only when transport ports are present).

## L. Recommended changes for Data Contract v0.2

1. Add `Asset.device_class` + `Asset.vendor` **with explicit `evidence_source`**, so UNSW
   device names and CICAPT node types can be attached without fabrication.
2. Add a `provenance_edge` table (or `DEPENDS_ON`/`CONTROLS` edge variant) so CICAPT
   provenance graphs are representable without overloading `COMMUNICATES_WITH`.
3. Add `CommunicationEdge.observation_window_seconds` and a `granularity` enum to make
   multi-resolution (5s/30s/60s) rows self-describing.
4. Add `EdgeFeatureWindow.session_count` / inter-arrival statistics for richer edge models.
5. Add a UNSW **device→IP binding** field (capture assignment) to upgrade identity from
   `ip_only` to device-pinned.
6. Add `Campaign.mitre_campaign_id` and `Campaign.source_rows` once CICAPT `Attack_info.csv`
   is ingested for real.
7. Add a `schema_version` migration note + a JSON Schema export for cross-language consumers.

---

## Definition of Done — demonstrated

`python -m src.cli demo` runs the full chain on the synthetic CICAPT-shaped scenario:

```
Raw dataset -> Adapter -> Stable assets -> Temporal edges -> Unified labels
-> Graph events -> Node/Edge feature windows -> Temporal graph -> Queries
```

Observed sequence (the required example):

```
02:13:00  cam-01      -> nvr-01     TCP RTSP   [NEW PEER]      # history: normal CAM<->NVR
02:14:00  cam-01      -> nvr-01     TCP RTSP
02:14:30  eng-pc-03   -> nvr-01     TCP RTSP   [NEW PEER]
02:14:00  cam-01      -> 10.0.0.50  TCP SMB    [NEW PEER]      # discovery scan
02:14:00  cam-01      -> eng-pc-03  TCP SMB    [NEW PEER]      # lateral movement
02:15:00  eng-pc-03   -> plc-07     TCP MODBUS [NEW PEER]      # lateral movement
02:15:30  eng-pc-03   -> plc-07     TCP MODBUS
02:16:00  plc-07      -> 10.0.0.99  TCP TLS    [NEW PEER]      # command & control
```

The two edges `CAM-01→NVR-01` (old, millions of connections, `historical_connection_count>0`,
`new_peer=false`) and `CAM-01→ENG-PC-03` (first seen seconds ago, SMB, `new_peer=true`,
`historical_connection_count=0`, `protocol_novelty=true`) are represented as **clearly
different** rows, and the graph preserves the ordering via `graph_version`.
