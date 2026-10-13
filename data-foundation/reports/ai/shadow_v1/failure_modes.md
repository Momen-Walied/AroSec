# Shadow Integration v1 — Failure Modes

**Core principle: fail-open.** If the AI fails, the network is unaffected. The shadow
runtime is read-only and its failures only produce logs, counters, quarantines, or restarts.

| Failure | Detection | Behaviour | Metric | Network impact |
|---|---|---|---|---|
| Corrupted / malformed observation | schema validation at the source/runtime boundary | record is **rejected**, processing continues | `malformed_observations_total` | none |
| Duplicate observation | `observation_id` idempotency set | record ignored (no double count / no duplicate window) | `observations_duplicate_total` | none |
| Late observation (beyond lateness horizon) | event-time watermark | **quarantined**; previously emitted results unchanged | `observations_late_total` | none |
| Missing model artifact | `ShadowModelBundle.load` | runtime **fails fast at startup** with a clear error; no auto-download, no auto-retrain | startup error | none |
| Incompatible feature schema / model version | bundle validation | **fails fast at startup** (`ModelBundleError`) | startup error | none |
| Calibration metadata missing/inconsistent | bundle validation | **fails fast at startup** | startup error | none |
| State-store error (save/load) | try/except in `runtime._persist` | logged + counted; runtime continues (may lose recent state on restart) | `state_store_errors_total` | none |
| Sink error (write) | try/except around `sink.write` | logged + counted; scoring continues | `sink_errors_total` | none |
| Inference error (unexpected) | try/except in `_handle_window` | logged + counted; window skipped | `inference_errors_total` | none |
| Process crash | operator/OS | restart; state reloaded from `StateStore` (SQLite) | — | none |

## Restart / recovery

SQLite state (`runtime_state` table, WAL) persists relationship/source state, open-window
buffers, the watermark, and the dedupe set. After restart the runtime resumes: already-seen
relationships are **not** re-flagged as `new_peer`, history counts are preserved, and
pending windows finalize on the next watermark advance or flush.

## What is deliberately NOT present

No firewall/iptables/switch/endpoint/isolation/blocking/quarantine-device code exists.
`tests/ai/shadow/test_safety.py` asserts the absence of remediation attributes and of
network-client usage in the runtime source.
