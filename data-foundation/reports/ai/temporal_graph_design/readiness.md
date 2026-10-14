# Phase 4A Readiness

- Dataset builder: **framework-independent**, deterministic, causal (tested).
- Leakage model: `docs/TEMPORAL_GRAPH_LEAKAGE_MODEL.md`.
- Non-GNN baselines: 10 graph heuristics (implemented, tested).
- Synthetic scenarios: 8 (7 structurally-unusual, 1 structurally-normal controls).
- Tests: graph_intelligence suite green; existing suite unchanged.

## The honest research verdict

- The current graph is **63 nodes / 74 edges**, a **single-hub star**; 2-hop = full graph; only 74 new edges ever.
- Next-edge ranking (Task A) is **degenerate** here → not a discriminating benchmark.
- Therefore **TASK B (graph-context edge anomaly)** is recommended as the v1 primary task, evaluated on structural scenarios + normal-test rate against Edge Behavior v1.
- **A temporal GNN is NOT yet justified on this data.** The right next step is to run the non-GNN bar on TASK B and only proceed to Phase 4B if the graph-context signal is real. A richer (heterogeneous or larger) graph would strengthen any GNN claim.

## Recommended Phase 4B direction (conditional)

- IF graph context proves measurable on TASK B: **TGN**-style event-stream model first (TGAT as the attention variant), CPU-first, inductive memory for new nodes.
- Snapshot GraphSAGE/GAT and HGT are **not** recommended now.
- Cold-start categories must be tracked; the memory module is the inductive mechanism.

