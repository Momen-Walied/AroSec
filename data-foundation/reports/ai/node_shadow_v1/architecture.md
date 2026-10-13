# Node Shadow Integration v1 — Architecture

One shared event-time runtime drives two INDEPENDENT pipelines (no fusion):

```
CommunicationObservation v0.2
   → shared event-time runtime (dedupe/watermark/lateness)
   ├─ edge pipeline: OnlineFeatureBuilder → EdgeFeatureWindowV2 → Edge Behavior v1 → EdgeAnomalyResultV1
   └─ node pipeline: OnlineNodeFeatureBuilder → NodeFeatureWindowV2 → Node Behavior v1 → NodeAnomalyResultV1
        → ShadowSink (edge/node records kept separate, intelligence_type=edge|node)
```

Reuses `ai/shadow/` config, sources, sinks, state stores, metrics, drift, feedback.
Node state is persisted alongside edge state in the same `StateStore`.

