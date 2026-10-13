# Behavioral Episode Intelligence v1 — Architecture

```
EdgeAnomalyResultV1 + NodeAnomalyResultV1 (alerts only)   <- shadow records
      │  chronologically ordered signals
      ▼
deterministic correlator (temporal + relational)
  · temporally close (correlation_gap_seconds)
  · relationally connected (shared asset / relationship endpoint)
  · bounded by max_episode_duration_seconds
      ▼
BehavioralEpisodeV1 (closed)  + evidence graph + machine summary
```

No ML, no score fusion, no attack taxonomy. Deterministic IDs; deterministic merge
(oldest start wins, tie-break by episode_id). Streaming-compatible (chronological).

Reason codes are grouped into evidence families to avoid over-counting correlated
evidence (see `ai/episodes/config.py`).

