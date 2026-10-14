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
| Temporal Graph Design v1 (Phase 4A) | **COMPLETE** |
| Graph-Context Edge Anomaly v1 (Phase 4B) | **COMPLETE / RESEARCH BASELINE** |
| Neural Temporal GNN | **BLOCKED — current graph data insufficient** |
| Graph-Context Shadow Integration | **NOT APPROVED** |

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

## Temporal Graph Intelligence — research status (Phases 4A / 4B)

- **Temporal Graph Design v1 (4A):** COMPLETE — framework-independent benchmark design.
- **Graph-Context Edge Anomaly v1 (4B):** COMPLETE / **RESEARCH BASELINE** (not shadow-ready, not
  a production detector, not an incident signal).
- **Neural Temporal GNN:** **BLOCKED — current graph data insufficient.**
- **Graph-Context Shadow Integration:** **NOT APPROVED.**

### Interpretation (do NOT delete, do NOT mark failed)

> Graph context contains **useful independent structural information**, but the current dataset
> **cannot validate a general graph-intelligence model**.

Keep `GraphContextAnomalyResultV1` as **research / diagnostic only**; it is **not** integrated
into `ai/shadow`. Specifically: the `low_similarity` family separates structurally **plausible**
vs structurally **unusual** new-edge scenarios (G06 −0.89 vs G07 0.00), while the aggregate score
currently obscures that signal. This is a research hypothesis to revisit on richer data.

### Why the GNN is blocked (evidence)

- current graph: **63 nodes / 74 directed relationships**.
- topology is **highly star-like**; one hub dominates ≈**99.6%** of edge windows.
- **all** TEST target edges are hub-involved; only **53** non-hub-source TEST edges exist.
- 2-hop context collapses to effectively the **full graph** (no incremental value).
- next-edge prediction is **degenerate**.
- the combined graph score does **not clearly improve** structural scenarios over Edge Behavior.
- `low_similarity` independently demonstrates useful structural information.
- Edge/Graph and Node/Graph correlations are **near zero** (independent evidence).

### Performance (4B baseline)

- TEST alert rate **1.35%** · alerts/site/day **5.87**.
- Edge–Graph Pearson **−0.032** / Spearman **−0.056**.
- Node–Graph Pearson **0.008** / Spearman **0.074**.
- feature generation p99 **0.161 ms**; **CPU-only**.
- best provisional context: **1-hop / 1-hour lookback**; **2-hop adds nothing**.

## Not started (gated)

Neural GNN / Temporal GNN, Attack Path reconstruction, attack-stage model, Incident Engine,
Campaign reconstruction, score fusion, automated remediation/retraining.
