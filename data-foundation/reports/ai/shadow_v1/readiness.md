# Shadow Integration v1 — Readiness

Consolidated readiness for architecture review. Numeric detail lives in the sibling reports
(`offline_online_parity.md`, `replay_evaluation.md`, `performance.md`, `drift_baseline.md`).

## Definition of Done — status

| Requirement | Status |
|---|---|
| CommunicationObservation v0.2 → EdgeFeatureWindowV2 → EdgeAnomalyResultV1 → shadow storage + metrics | ✅ |
| Causal online state | ✅ |
| Restart recovery | ✅ (`test_state.py`, SQLite) |
| Duplicate safety | ✅ (`observation_id` idempotency) |
| Event-time handling | ✅ (watermark; lateness quarantine) |
| Offline/online parity | ✅ **exact, 0 mismatches / 67,885 windows** |
| No Data Foundation contract changes | ✅ (frozen v0.2 untouched) |
| No network actions | ✅ (no remediation paths; tested) |
| Observable performance | ✅ (`performance.md`) |
| Observable drift | ✅ (`drift_baseline.md`) |

## Answers (final readiness questions)

1. **Offline/online feature parity achieved?** Yes — exact.
2. **Parity mismatches?** 0 (offline 67,885 = online 67,885 windows; 0 missing / 0 extra).
3. **Restart recovery?** Yes. Relationship/source state, open-window buffers, watermark, and
   the dedupe set persist in SQLite; a relationship does not become `new_peer` again.
4. **Duplicate idempotency?** Yes — reprocessing the same `observation_id` neither
   double-counts nor creates duplicate windows/results.
5. **Late events?** Quarantined beyond the window-quantized lateness horizon (default 30s =
   one window); counted; emitted results are never rewritten.
6. **Sustainable observations/sec?** See `performance.md`.
7. **Feature-build latency p50/p95/p99?** See `performance.md`.
8. **Inference latency p50/p95/p99?** See `performance.md`.
9. **Memory usage?** See `performance.md` (tracemalloc peak).
10. **Replay alert rate?** See `replay_evaluation.md`.
11. **Top anomaly reasons?** See `replay_evaluation.md`.
12. **Score drift observable?** See `drift_baseline.md` (PSI/KS; overall class).
13. **Shadow threshold reasonable?** **Provisional** (0.315; validation-derived at a ~1%
    target). It must be recalibrated on real traffic during deployment — it is not a final
    production threshold.
14. **Ready for a real Network/Security stream?** The **read-only shadow path is ready**:
    frozen contract ingestion, exact online features, event-time handling, idempotency,
    restart recovery, sinks (JSONL/SQLite), metrics, drift, and analytics. A broker/firehose
    can be attached by implementing `ObservationSource` (see `docs/AI_SHADOW_INTEGRATION_V1.md`).
15. **Remaining provisional parts?** Threshold calibration; IP-only identity (UNSW
    `dataset_ip_fallback`); lateness semantics for pre-windowed input; behavior verified only
    for the UNSW 30s window; analyst feedback storage is not yet a label pipeline.

## Explicit non-goals (not started)

Node Behavior, Temporal GNN, Attack Path, Campaign reconstruction, and any automatic
response/remediation remain out of scope.

## Review gate

No commit/push performed. This phase stops here for architecture review.
