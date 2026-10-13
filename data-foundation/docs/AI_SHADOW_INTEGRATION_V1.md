# AI Shadow Integration v1

Connects the frozen `CYBER_GRAPH_DATA_CONTRACT_V0.2` communication stream to
Edge Behavior Intelligence v1 in a production-shaped, transport-agnostic runtime.

```
CommunicationObservation v0.2 → Online Temporal State → EdgeFeatureWindowV2
   → Edge Behavior v1 → EdgeAnomalyResultV1 → Shadow Sink → Metrics / Logs / Review
```

The system **OBSERVES · SCORES · EXPLAINS · RECORDS**. It does **not** block, isolate,
respond, or change network state. `mode=shadow` is enforced at config and record level.

> Terminology: this is **relationship anomaly detection**, not validated attack detection.
> UNSW identities are provisional `dataset_ip_fallback`. The shadow threshold is
> provisional and will be recalibrated during real deployment.

## Project status

```
Data Foundation v0.2 (Cyber Graph Data Contract):  FROZEN
Edge Behavior Intelligence v1:                     COMPLETE
Shadow Integration v1:                             COMPLETE / SHADOW-READY
```

**Operational notes**
- Relationship anomaly detection — **not** validated attack detection.
- **Shadow-only, read-only, fail-open** (no network actions; no remediation).
- Threshold **0.315 remains provisional**; real traffic will be used for recalibration.
- **No automatic retraining.**
- Model binaries are regeneration-only (see §4).

**Production-like benchmark** (durable SQLite state + sink): ~6,000 obs/s, peak RSS ≈ 677 MB,
state DB ≈ 4.3 MB, shadow sink DB ≈ 273 MB — see
`reports/ai/shadow_v1/production_benchmark.md`.

## 1. Offline / online feature parity (critical)

`ai/shadow/features/online_builder.py` maintains causal state and reproduces the offline
`build_edge_features_v2` output. Measured on the full UNSW v0.2 stream:

| metric | value |
|---|---|
| offline windows | 67,885 |
| online windows | 67,885 |
| missing / extra | 0 / 0 |
| **total field mismatches** | **0** |

All 18 compared fields match (`connections_count, packet_count, outbound/inbound_bytes,
protocol/application distributions, observed src/dst ports, unique ports,
relationship_age_seconds, historical_connection_count, new_peer, src_unique/new peers,
protocol_novelty_count/ratio, port_novelty_count`). See `reports/ai/shadow_v1/offline_online_parity.md`.

**Intentional difference:** `relationship_age_seconds` uses the first observed
`window_start` online because `CommunicationObservation` carries window boundaries, not raw
packet timestamps. Against the windowed offline reference it matches exactly; against
training-time features the offset is bounded by one window (0 for the first window).

## 2. Event-time, lateness, and windowing

* Event time comes from `window_start`/`window_end`, never arrival time.
* Watermark = max `window_end`; a window finalizes when
  `window_start + window + lateness < watermark` (strict).
* `allowed_lateness_seconds` default **30**. Because observations are pre-windowed, lateness
  tolerance is quantized to whole windows (30 = up to one window late; smaller values are
  equivalent to 0).
* Late records are quarantined and counted; **emitted results are never rewritten**.
* 30-second half-open windows, identical to training.

## 3. State and storage

`StateStore` interface with `InMemoryStateStore` (tests/dev) and `SqliteStateStore`
(durable). SQLite was chosen because it is single-file, serverless, crash-safe (WAL +
atomic commit), CPU-friendly, easily inspected/backed up, and a Python stdlib module — no
Redis/Kafka/distributed state needed for shadow. Restart recovery is tested
(`tests/ai/shadow/test_state.py`).

State is proportional to the number of relationships and source assets (sets, not raw
history) plus buffers for open windows; the dedupe set is bounded (`dedupe_capacity`).

## 4. Model bundle (regeneration-only binaries)

Selected production candidate: **validation-weighted Statistical + Isolation Forest fusion**
(`ai/shadow/configs/fusion_bundle.json`). The Autoencoder is **not** part of the runtime.
The statistical component supplies analyst reasons.

Model binaries are not committed. Regenerate locally, then run:

```bash
# 1) regenerate the two component artifacts (creates ai/edge_behavior/artifacts/...)
python -m ai.edge_behavior.training.run_experiments
# 2) (re)generate the shadow fusion bundle JSON (threshold + severity from validation)
python -c "from ai.shadow.inference.model_bundle import build_bundle; build_bundle('ai/shadow/configs/fusion_bundle.json')"
```

`ShadowModelBundle.load` validates feature-schema version, model versions, and calibration
metadata and **fails clearly** if the artifact is missing/incompatible. The runtime never
downloads or retrains.

## 5. Sinks, metrics, drift, feedback

* Sinks: `JsonlShadowSink` (debug/replay) and `SqliteShadowSink` (idempotent per
  `(relationship_id, window_start)`).
* Metrics (`metrics/collector.py`): `observations_received/duplicate/late/rejected/
  malformed`, `feature_windows_emitted_total`, `feature_build_latency_ms`, `inference_total`,
  `inference_latency_ms`, `inference_errors_total`, `anomaly_score`, `severity_*`,
  `alerts_total`, `alert_reason_*`, `active_relationships`, `state_size_*`, `uptime_seconds`,
  `state_store_errors_total`, `sink_errors_total`.
* Drift (`metrics/drift.py`): PSI + KS vs the training/validation reference for anomaly
  score, connections, byte volume, fan-out, new-peer rate, protocol/port novelty rate →
  `DRIFT_NONE / DRIFT_WARNING / DRIFT_HIGH`. **No automatic retraining.**
* Feedback: `AnalystFeedbackV1` (verdicts `benign_expected`, `benign_unusual`, `suspicious`,
  `confirmed_security_incident`, `unknown`) + append-only JSONL store. Not a training-label
  pipeline; never triggers retraining.

## 6. Privacy / data minimization

Retained: identifiers (asset/relationship ids), metadata (protocol, ports, window
boundaries), counts/bytes, evidence references, anomaly score/severity/reasons, identity
quality. **Not** retained: payload contents. No deep packet inspection.

## 7. Running it

```bash
python -m ai.shadow parity  --dataset unsw_iotraffic          # offline/online parity
python -m ai.shadow replay  --dataset unsw_iotraffic --speed max
python -m ai.shadow demo                                      # CAM/NVR/ENG-* scenario
python -m ai.shadow report  --input reports/ai/shadow_v1/shadow_output.jsonl
python -m ai.shadow.reporting.generate_reports                # regenerate all shadow reports
```

`--speed` supports `max | 1x | 10x ...`; historical replay is intended with `--speed max`
(pacing only matters for small demos).

## 8. Connecting a future source (no broker required)

Implement the `ObservationSource` interface and yield `CommunicationObservation` objects:

```python
from ai.shadow.sources.base import ObservationSource

class KafkaObservationSource(ObservationSource):
    def __init__(self, consumer): self.consumer = consumer
    def __iter__(self):
        for msg in self.consumer:                        # your broker client
            yield CommunicationObservation.model_validate_json(msg.value())
```

Then pass it to `ShadowRuntime(config, source, sink, state_store, bundle)`. The same applies
to NATS, Redpanda, HTTP, or a file tailer. Requirements: (a) records conform to the frozen
`CommunicationObservation v0.2` schema; (b) the source yields *event-time* records (the
runtime never uses arrival time). No AI code changes are needed to swap transports.

## 9. Limitations

* Offline/online parity is proven for the 30s UNSW stream; other datasets/windows should be
  re-verified.
* Lateness tolerance is window-quantized (pre-windowed input).
* Identity is provisional (`dataset_ip_fallback` for UNSW).
* Shadow threshold is provisional.
* No GNN, no attack-path, no campaign reconstruction, no remediation (by design).

## 10. Readiness answers

1. **Offline/online parity achieved?** Yes — exact (0 mismatches over 67,885 windows).
2. **Parity mismatches?** 0.
3. **Restart recovery?** Yes — SQLite state persists relationship/source state, buffers,
   watermark, dedupe set; tested.
4. **Duplicate idempotency?** Yes — `observation_id` idempotency; no double counting.
5. **Late events?** Quarantined beyond the (window-quantized) lateness horizon; counted;
   emitted results never rewritten.
6. **Sustainable observations/sec?** See `reports/ai/shadow_v1/performance.md`.
7. **Feature-build latency p50/p95/p99?** See `performance.md`.
8. **Inference latency p50/p95/p99?** See `performance.md`.
9. **Memory usage?** See `performance.md`.
10. **Replay alert rate?** See `reports/ai/shadow_v1/replay_evaluation.md`.
11. **Top anomaly reasons?** See `replay_evaluation.md`.
12. **Score drift observable?** See `reports/ai/shadow_v1/drift_baseline.md`.
13. **Shadow threshold operationally reasonable?** Provisional (0.315, validation-derived at
    ~1% target); to be recalibrated in deployment.
14. **Ready for a real stream?** The contract, online feature parity, event-time handling,
    idempotency, restart recovery, sinks, and metrics are ready for a read-only shadow stream.
15. **Provisional?** Threshold calibration, identity for IP-only data, lateness semantics for
    pre-windowed input, and any behavior beyond the UNSW 30s window.

See `reports/ai/shadow_v1/readiness.md` for the consolidated readiness summary.
