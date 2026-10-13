# AI Behavioral Episode Shadow Integration v1

Integrates Behavioral Episode correlation into the read-only shadow runtime so the same
`CommunicationObservation v0.2` stream drives Edge, Node, and Episode layers independently.
No frozen contract was modified; no datasets downloaded; **no fusion, no incident/attack
semantics, no remediation**.

```
CommunicationObservation v0.2
  → shared event-time runtime (dedupe · watermark · lateness · durable state)
  ├─ edge pipeline → EdgeAnomalyResultV1
  └─ node pipeline → NodeAnomalyResultV1
        → online episode correlator (chronological, event-time)
        → BehavioralEpisodeV1 (closed) → EpisodeShadowRecordV1
        → shadow storage (edge_results · node_results · behavioral_episodes)
```

## 1. Reuse & extension

`ai/shadow/` is extended, not duplicated: `ObservationSource`, watermark/lateness, duplicate
handling, SQLite durable state, sinks (now with a separate `behavioral_episodes` table and
indexes), metrics, restart recovery, and failure isolation are reused. Only the episode
correlator, the `EpisodeShadowRecordV1` envelope, and episode metrics/analytics are added.

## 2. Online correlator & parity

The Phase 3 correlator is chronological and streaming-shaped, so offline and online share it.
The runtime feeds signals in exact `(window_start, signal_type, signal_id)` order; both
pipelines are flushed together so window sets align. Episodes therefore match the offline
reference **exactly** — see `reports/ai/episode_shadow_v1/offline_online_parity.md`.

## 3. Signals, event time, finalization

- Signals enter the episode layer only when they meet the **same alert criterion** used offline
  (Edge score ≥ 0.315, Node score ≥ 0.719). Scored-but-not-alerting windows are not correlated.
- Event time = signal `window_start`. Finalization is **watermark-driven**: the shared upstream
  event-time watermark advances the episode layer even when no signal is generated. An episode
  closes when `watermark > last_signal_end + gap` subject to the parity-safe reordering margin
  `window + lateness` (i.e. `> end_time + gap + window + lateness`), and the `max_duration` bound
  is enforced the same way. No wall-clock, no batch boundary, no synthetic future signals.
- Semantic vs runtime time: `BehavioralEpisodeV1.end_time` is the **last signal's event time**;
  the runtime close watermark is recorded separately in `EpisodeShadowRecordV1.closed_at`.
- To feed a signal before its episode could expire, finalized window-scoring batches are also
  flushed once the watermark passes the **maximal safe feed horizon** `gap + window + lateness`.
  This keeps finalization bounded (see `episode_finalization_lag_seconds`); on the sparse UNSW
  30 s stream it forces smaller scoring batches, so the episode-enabled throughput is below the
  episode-off path — see `performance.md` for the measured tradeoff.
- `correlation_gap_seconds = 60`, `max_episode_duration_seconds = 600` (provisional).
- Deterministic merge (oldest start wins; tie-break by `episode_id`) unchanged from Phase 3.

## 4. Duplicate & late-signal policy

- Stable `signal_id`; a redelivered signal increments `episode_signals_duplicate_total` and
  changes nothing (no membership/strength change, no duplicate episode).
- A signal too old to correlate safely (`window_start + gap + slack < max_seen_window_start`) is
  **quarantined** (`episode_signals_late_total`) — closed episodes are **never** rewritten.

## 5. Storage

Closed episodes are persisted once, in a separate `behavioral_episodes` table
(`episode_id` PK, `start_time`/`end_time` indexes, `episode_assets` index), retaining signal
references. Open episode state lives only in the durable state store — **no per-update
duplicate episode records**.

## 6. Metrics

`episode_signals_received_total`, `episode_signals_duplicate_total`, `episode_signals_late_total`,
`episodes_open`, `episodes_created_total`, `episodes_closed_total`, `episodes_merged_total`,
`episode_update_latency_ms`, `episode_close_latency_ms`, `episode_finalization_lag_seconds`,
`episode_signal_count` histogram,
`episode_asset_count` histogram, `edge_only_episodes_total`, `node_only_episodes_total`,
`mixed_episodes_total`, `evidence_strength_*`. These are **not** incident metrics.
`episode_finalization_lag_seconds` = close watermark − episode `end_time`; its baseline relates to
`gap + window + lateness` (per-scan ≈ 120 s), plus up to one observation-driven watermark step.

## 7. Failure isolation

Edge and Node scoring continue if the episode layer fails (correlator exception, episode state
DB failure, episode sink failure, malformed signal are caught and counted; no network effect).

## 8. Reproduce

```bash
python -m ai.shadow.reporting.generate_episode_shadow_reports   # parity + replay + perf + restart + reports
python -m pytest tests/ai/episode_shadow -q
```

## 9. Final questions

1. **Offline/online episode parity exact?** Yes — 0 mismatches (see `offline_online_parity.md`).
2. **Episode count offline vs online?** 633 = 633 (identical) (see `offline_online_parity.md`).
3. **Membership mismatches?** 0.
4. **Episode ID mismatches?** 0.
5. **Timestamp mismatches?** 0.
6. **Evidence mismatches?** 0.
7. **Full replay observation count?** 98,747.
8. **Edge signal count?** 566.
9. **Node signal count?** 669.
10. **Episode count?** 633 (gap 60 s).
11. **Compression ratio?** 1.95.
12. **Episodes/site/day?** 20.3.
13. **Edge-only / Node-only / Mixed?** 34.9% / 45.8% / 19.3%.
14. **Restart recovery exact?** Yes — 0 mismatches vs uninterrupted (paused without flushing open
    episodes, then resumed from durable state).
15. **Duplicate signals idempotent?** Yes.
16. **Late-signal policy verified?** Yes — too-old signals quarantined; closed episodes immutable.
17. **False merges?** 0 (Phase 3 regression preserved: proximity alone never merges).
18. **Sustainable observations/sec end-to-end?** See `performance.md`.
19. **Regression vs Phase 2.5 (~2,045 obs/s)?** See `performance.md` (episode layer is cheap).
20. **Episode update p99?** See `performance.md`.
21. **Episode close p99?** See `performance.md`.
22. **Peak RSS?** See `performance.md`.
23. **Durable state growth?** See `state_recovery.md`.
24. **Can Edge+Node continue if Episode layer fails?** Yes (tested).
25. **Ready for a real read-only stream?** Yes — Observation→Edge/Node→Episode is a read-only,
    fail-open shadow chain with exact parity and recovery.
26. **Provisional?** Episode gap/max-duration, Edge/Node thresholds, `dataset_ip_fallback`
    identity, modest compression on mostly-normal UNSW (not alert-reduction proof).

## 10. Performance status

Measured on the durable full chain (Observation → Edge → Node → Episode, SQLite sink):

- **Durable full-chain throughput: ~535 `CommunicationObservation`/sec** (episode layer ON).
- **Episode update p99:** ~0.028 ms.
- **Episode close p99:** ~0.078 ms.
- **Episode finalization lag:** p50 **180 s**, p95 **300 s**, p99 **300 s**.
- **Peak RSS:** ~2,279 MB in the full replay benchmark.

Interpretation:

- Episode correlation itself is **inexpensive** (microsecond-scale update/close).
- The current throughput loss is dominated by **small scoring batches**; bounded low-latency
  finalization constrains batching on sparse streams.
- **No correctness issue exists** — parity, membership, and lag are unaffected.
- **No performance optimization is included in this release.** Throughput must be
  re-benchmarked against real target-site load.
- Future optimization must **preserve existing event-time semantics**.

Backlog:

- **PERF-EPISODE-001** — Decouple inference micro-batching efficiency from episode watermark
  finalization while preserving exact feature/signal/episode semantics. Potential future
  direction: bounded asynchronous inference micro-batching / queueing. **Do not implement now.**

## 11. Finalization lag is not detection latency

Episode closure latency is **not** detection latency. `EdgeAnomalyResultV1` and
`NodeAnomalyResultV1` remain **independently available before** `BehavioralEpisodeV1`
finalization. The current finalization lag is acceptable for Shadow v1 but **provisional** for
future incident/security reasoning. `correlation_gap_seconds = 60` and
`max_episode_duration_seconds = 600` are unchanged in this release.

## Scope

No GNN/Temporal GNN, attack-path, attack-stage, incident engine, campaign reconstruction,
MITRE mapping, attack taxonomy, score fusion, or remediation. See `docs/PROJECT_STATUS.md`.
