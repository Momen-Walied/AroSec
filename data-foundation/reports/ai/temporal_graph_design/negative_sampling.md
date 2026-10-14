# Temporal-Safe Negative Sampling

A negative candidate (u,v) at time T must (a) never have been observed before T, and (b) not appear within the horizon (T, T+horizon]. Rule (b) is what prevents a sampled 'negative' from secretly being a near-future positive (leakage class F).

## Categories (strongest first)

| category | rule | intent |
|---|---|---|
| `hard` | shares ≥1 peer with src | hardest discriminative case |
| `temporally_plausible` | peer-of-peer (2-hop), no shared peer | plausible link |
| `new_peer` | active node src has never related to | cold-start realism |
| `random_non_edge` | any other non-edge | easy control |

Observed distribution on the real run: {'random_non_edge': 14975, 'hard': 18, 'new_peer': 2}. Most draws are `random_non_edge` because the star hub is an endpoint of almost every candidate query, leaving few plausible alternatives — further evidence the topology is degenerate.

Determinism: RNG seeded by `(seed + hash(src|dst|as_of))`, candidate order sorted then shuffled → identical negatives on every run (tested).

