# Graph Sample Design

Chosen representation: **D. EGO / LOCAL TEMPORAL SUBGRAPH** around the target edge-window, with **1 hop** and a **1 h** causal lookback.

`TemporalGraphSampleV1` fields: target edge-window, `as_of`, `hops`, `lookback_seconds`, causal `neighbor_node_ids`, causal `causal_event_ids`, `target_delta_s`, `neighborhood_span_s`, `split`, `cold_start_category`, identity quality.

## Representation comparison

| option | memory | streaming | leakage risk | explainability | verdict |
|---|---|---|---|---|---|
| A full snapshot G_t | low | poor (rebuild each step) | high (must rebuild causally) | medium | rejected |
| B snapshot sequence | high | poor | high | medium | rejected |
| C event stream (u,v,t,feats) | lowest | best | lowest | high | kept as canonical store |
| D ego temporal subgraph | low | good | low (bounded, causal) | high | **recommended** |

Rationale: D is causal-by-construction, streams naturally (append events, query a bounded window), is explainable (lists the exact neighbours/events), and is framework-independent. Because 2-hop = whole graph here, **1 hop** is the correct locality; record 2-hop as an ablation only.

