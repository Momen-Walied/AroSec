# Shadow Integration v1 — Architecture

```
CommunicationObservation v0.2
        │  (transport-agnostic ObservationSource)
        ▼
Online Temporal State  (OnlineFeatureBuilder, causal, event-time)
        │
        ▼
EdgeFeatureWindowV2  (byte-for-byte parity with offline builder)
        │
        ▼
Edge Behavior v1  (validation-weighted Statistical + Isolation Forest fusion)
        │
        ▼
EdgeAnomalyResultV1  (+ ShadowInferenceRecordV1 runtime envelope)
        │
        ▼
Shadow Sink  (JSONL / SQLite)  →  Metrics  ·  Drift  ·  Analyst feedback
```

The runtime only **OBSERVES, SCORES, EXPLAINS, RECORDS**. It never blocks, isolates,
responds, or changes network state.

## Components (all under `ai/shadow/`)

| Layer | Module | Responsibility |
|---|---|---|
| Config | `config.py` | `mode=shadow` invariant, window, lateness, provisional threshold, backends |
| Source | `sources/{base,replay,jsonl,list}.py` | `ObservationSource` interface + replay over local v0.2 Parquet |
| Feature | `features/online_builder.py` | incremental causal state → EdgeFeatureWindowV2 |
| State | `state/{base,memory,sqlite}.py` | `StateStore`; in-memory + SQLite durable |
| Inference | `inference/model_bundle.py` | loads + validates the selected fusion bundle |
| Envelope | `contracts/shadow_records.py` | `ShadowInferenceRecordV1` (does not modify EdgeAnomalyResultV1) |
| Sink | `sinks/{base,jsonl,sqlite,memory}.py` | `ShadowSink`; JSONL, SQLite, in-memory |
| Metrics | `metrics/{collector,drift}.py` | counters/histograms/gauges; PSI/KS drift |
| Feedback | `feedback/{schema,store}.py` | `AnalystFeedbackV1` + local JSONL store |
| Runtime | `runtime.py` | orchestration: observe → feature → score → record |
| Reporting | `reporting/shadow_report.py`, `reporting/generate_reports.py` | analytics + report generation |
| CLI | `cli/main.py` | `replay` · `parity` · `demo` · `report` |

## Online temporal state

**Relationship state** (per `relationship_id`): `first_seen`, observed network protocols,
observed application protocols, observed destination ports, cumulative connection count,
`window_seen` (first-window flag), observation count.

**Source-asset state** (per `src_asset_id`): the set of destination peers seen in
*already-finalized* windows (drives `src_unique_peer_count` / `src_new_peer_count`).

**Window buffers** (per active `window_start`): per-relationship connection/packet/byte
totals, protocol and application-protocol counts, and distinct src/dst ports. Buffers exist
only for windows inside the lateness horizon and are dropped on finalization.

**Memory growth:** state is proportional to the number of *relationships* and *source
assets* (sets, not raw history), plus buffers for open windows only. The dedupe set is
bounded by `dedupe_capacity` (default 500,000 observation ids). `finalized` window keys are
bounded to the most recent 5,000.

## Event-time semantics

* Event time is taken from `window_start`/`window_end` — **never** the process arrival time.
* Watermark = max `window_end` observed.
* A window finalizes when `window_start + window + lateness < watermark` (strict), i.e. once
  data strictly beyond its lateness horizon has arrived.
* **Because CommunicationObservation is pre-windowed, lateness tolerance is quantized to
  whole windows.** `allowed_lateness_seconds = 30` tolerates a record arriving up to one
  window late; values below 30 have no additional effect. Default = 30 (documented).
* Late records are quarantined (counted in `observations_late_total`); previously emitted
  results are **never** rewritten. Future versions may add explicit correction events.

## Windowing

30-second half-open windows `[window_start, window_end)`, identical to Data Foundation
training. The builder is parameterised by `window_seconds` for future windows but v1
reproduces the current 30s behaviour exactly.

## Safety

`mode` must be `"shadow"`; `ShadowInferenceRecordV1.shadow_mode` must be `true`. There is no
remediation code path (verified by `tests/ai/shadow/test_safety.py`). The runtime is
read-only with respect to the customer network and is fail-open: exceptions are counted and
do not propagate to any network function.

## Transport-agnostic input

The Network/Security team injects a future transport by implementing `ObservationSource`
(one method: `__iter__ -> Iterator[CommunicationObservation]`). No broker is required or
deployed in this phase. See `docs/AI_SHADOW_INTEGRATION_V1.md` §"Connecting a future source".
