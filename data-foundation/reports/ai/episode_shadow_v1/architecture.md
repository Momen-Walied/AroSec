# Episode Shadow Integration v1 — Architecture

```
CommunicationObservation v0.2
  → shared event-time runtime (dedupe · watermark · lateness · durable state)
  ├─ edge pipeline → EdgeAnomalyResultV1
  └─ node pipeline → NodeAnomalyResultV1
        → online episode correlator (chronological, event-time)
        → BehavioralEpisodeV1 (closed) → EpisodeShadowRecordV1
        → shadow storage (edge_results · node_results · behavioral_episodes)
```

Edge and Node remain independent; the episode layer correlates their signals only.
No score fusion, no incident/attack semantics, no remediation.

