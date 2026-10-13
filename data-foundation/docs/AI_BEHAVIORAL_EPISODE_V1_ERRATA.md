# Errata — Behavioral Episode Intelligence v1 (Phase 3)

**Status:** correction required. The Phase 3 published result is **superseded**.
**Immutable tag:** `ai-behavioral-episode-v1` is a historical release and is **not** moved or
rewritten. This document records the correction that lands with Phase 3.5.

## 1. What the bug was

In the read-only shadow runtime, **batched node scoring** mapped model scores back to node
windows by **index** (`windows[i]`) while the feature frame is **sorted** by
`(asset_id, window_start)`. Whenever a scoring batch contained more than one window, the
score/reasons computed for one row were attached to a **different node window**.

* This was an **upstream Node score → window attribution** defect.
* The behavioral-episode **correlator semantics were not the root cause**.

## 2. Which evaluation result it affected

* The **Phase 3 episode reference** — signals were derived from shadow records whose Node
  anomaly results could be attached to the wrong window, shifting a small number of Node
  alert signals and thus episode membership/counts.
* **Phase 2.5 / Phase 3.5 node replay per-window attribution.** Aggregate node score
  distributions were largely unaffected (same multiset of scores), but **per-window**
  attribution and any downstream per-window use were wrong.

## 3. Corrected reference (canonical)

| | Phase 3 (published) | Corrected |
|---|---:|---:|
| Edge signals | 566 | 566 |
| Node signals | 669 | 669 |
| Total signals | 1,235 | 1,235 |
| **Behavioral Episodes** | **857** | **633** |
| Compression ratio | 1.44 | **1.95** |
| Edge-only / Node-only / Mixed | 38.6% / 59.3% / 2.1% | 34.9% / 45.8% / **19.3%** |
| Observations/sec (edge+node) | ~2,045 | ~2,245 |

The **old result (857 episodes) is not hidden** — it is recorded here and in the Phase 3 tag
history. **633 is the canonical corrected result** and is reflected in the current Phase 3
reports and Episode Shadow reports.

## 4. Fix

* `ai/shadow/runtime.py::_flush_node_batch` now keys windows by their own identity
  (`(window_start, asset_id)`), never by frame index.
* Node scores are now **batch-size invariant** (verified).

## 5. Tests added to prevent recurrence

* `tests/ai/episode_shadow/test_episode_shadow_runtime.py::test_node_scores_batch_invariant_on_longer_sequence`
  — batched node scores must equal across batch sizes on a multi-window sequence.
* `tests/ai/episode_shadow/test_node_shadow_runtime.py::test_batch_size_invariance_for_node_scores`
  — pre-existing invariance check strengthened.
* Episode **batch-size invariance** and **offline/online parity** tests
  (`test_episode_shadow_runtime.py`, `test_watermark_finalization.py`) now guard the
  end-to-end contract.

## 6. Which commit contains the correction

The correction is included in the **Phase 3.5** publication (currently uncommitted, pending
architecture review), intended to be published as:

1. `fix(ai): correct node batch attribution and episode evaluation` — the node attribution fix,
   batch-invariance regression test, corrected Phase 3 reports/docs, and this errata.
2. `feat(ai): complete behavioral episode shadow integration v1` — online episode state,
   watermark-driven finalization, restart recovery, durable episode persistence, parity,
   metrics/reports/tests.

The tag `ai-behavioral-episode-v1` remains **immutable**; the corrected figures are carried by
the Phase 3.5 release and by the regenerated `reports/ai/behavioral_episode_v1/*`.
