# Candidate Model Review (no implementation)

Requirements: temporal event support, directed edges, edge features, node features, inductive/new-node behavior, **CPU inference**, online state, explainability, ecosystem.

| family | temporal | directed | edge feats | node feats | inductive | CPU | complexity |
|---|---|---|---|---|---|---|---|
| TGN | event-stream native | yes | memory + msg | via memory | strong | medium | medium-high |
| TGAT | event-stream native | yes | attention over edges | via attn | strong | medium | high |
| DyRep | event-stream | yes | limited | limited | good | medium | high |
| GraphSAGE (snapshot) | snapshots only | weak | no | yes | good | good | low |
| GAT (snapshot) | snapshots only | weak | no | yes | good | good | medium |
| HGT / heterogeneous | snapshots | yes | limited | yes | good | high | very high |

Conclusion: **HGT is not justified** — the current graph is homogeneous. **Snapshot GNNs (GraphSAGE/GAT) discard event time and edge features**, which our task needs. If the task is event-stream temporal edge anomaly, **TGN (or TGAT for attention)** fits best (event-native, directed, edge-featured, inductive via memory). Snapshot models are the wrong tool here.
Recommendation is conditional — see readiness.md.

