# Streaming Semantics

- Signals enter the episode layer only when they meet the Edge/Node alert criterion.
- Event time = signal `window_start`; ordering is `(window_start, type, id)` (matches offline).
- **Watermark-driven finalization**: the shared upstream event-time watermark advances the
  episode layer even with no new signal. An episode closes when
  `watermark > end_time + gap + window + lateness` (parity-safe margin), and the
  `max_duration` bound is enforced the same way — no wall-clock, no batch boundary, no
  synthetic signals.
- `end_time` is the **last signal's** event time; the runtime close watermark is stored
  separately as `EpisodeShadowRecordV1.closed_at`.
- Dedupe: stable `signal_id`; a redelivered signal never changes membership/strength.
- Late signal after finalization is **quarantined** (counted), never rewrites closed episodes.
- `correlation_gap_seconds=60`, `max_episode_duration_seconds=600` (provisional).

