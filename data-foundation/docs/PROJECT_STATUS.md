# AroSec AI — Project Status

Read-only shadow platform. This file is the authoritative high-level status.

## Release status

| Capability | Status |
|---|---|
| Data Foundation v0.2 | **FROZEN** |
| Edge Behavior Intelligence v1 | **COMPLETE** |
| Edge Shadow Integration v1 | **COMPLETE / SHADOW-READY** |
| Node Behavior Intelligence v1 | **COMPLETE** |
| Node Shadow Integration v1 | **COMPLETE / SHADOW-READY** |
| Behavioral Episode Intelligence v1.0.1 | **COMPLETE / CORRECTED** |
| Behavioral Episode Shadow Integration v1 | **COMPLETE / SHADOW-READY** |

## Semantic invariants (preserved)

- `BehavioralEpisode` is **NOT** a `SecurityIncident`.
- **Correlation does not imply causality.**
- No attack probability, no attack stage, no attacker/victim inference.
- No automated remediation.
- No automatic retraining.
- The runtime is **read-only** and fail-open: Edge/Node results stay available
  independently, before any episode finalizes.

## Historical releases (immutable)

- `ai-behavioral-episode-v1` — Phase 3, original behavior. **Never moved or rewritten.** Its
  published 857-episode result is **superseded** by the corrected evaluation (see
  `docs/AI_BEHAVIORAL_EPISODE_V1_ERRATA.md`), but the tag itself is preserved.
- `ai-behavioral-episode-v1.0.1` — corrective tag for the Node batch attribution fix + corrected
  canonical evaluation.
- `ai-behavioral-episode-shadow-v1` — Phase 3.5 read-only shadow integration.

## Open backlog

- **PERF-EPISODE-001** — Decouple inference micro-batching efficiency from episode watermark
  finalization while preserving exact feature/signal/episode semantics. Potential future
  direction: bounded asynchronous inference micro-batching / queueing. **Not implemented in this
  release.**

## Not started (gated)

GNN / Temporal GNN, Attack Path reconstruction, Incident Engine, Campaign reconstruction, score
fusion, automated remediation/retraining.
