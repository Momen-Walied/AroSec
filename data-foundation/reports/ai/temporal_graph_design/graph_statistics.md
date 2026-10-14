# Graph Statistics (UNSW v0.2, 30 s)

- Nodes: 63 · Directed edges: 74 · Edge instances: 67,885
- Time range: 2016-09-30 19:30:00+00:00 → 2016-10-31 23:47:00+00:00 (31.178 days)
- Window occupancy: 35,805/89,794 (39.9%)
- Density (directed): 0.0189
- Out-degree (p50/p90/max): 1/1/61 (mean 5.286)
- In-degree (p50/p90/max): 1/1/13 (mean 1.194)
- 1-hop neighbourhood (p50/p90/max): 1/1/62
- 2-hop neighbourhood (p50/p90/max): 62/62/62 → **2-hop collapses to the whole graph (hub effect)**
- Relationship lifetime days (p50/p90): 26.1/31.1
- Edge-windows per relationship (p50/p90/max): 133/2257/12697
- New relationships: 74 total over 9 active days (mean 8.222/day)
- Edges per window (p50/p90/max): 1/4/19
- Connected components (undirected): [63]

## Causal lookback probe (distinct edges / neighbors seen per target)

| lookback | edges p50 | edges p90 | neighbors p50 | neighbors p90 |
|---|---|---|---|---|
| 5min | 7 | 9 | 8 | 10 |
| 30min | 13 | 15 | 14 | 16 |
| 1h | 16 | 20 | 17 | 21 |
| 6h | 27 | 31 | 28 | 31 |
| 24h | 32 | 38 | 32 | 37 |

Reading: the graph saturates quickly (24 h ≈ half the whole graph). A 1 h lookback captures the recent, decision-relevant neighbourhood without dragging in the full star.

