# Synthetic Structural Scenarios — Edge Behavior vs Graph Context

Edge Behavior v1's edge-local novelty flags **NEW_PEER** for every synthetic new edge (proxy = 1.0 for all), so it cannot separate a *structurally normal* new edge from a structurally unusual one. Graph Context is independent evidence.

| scenario | unusual? | graph score | novelty | change | low-sim | neigh | notes |
|---|---|---|---|---|---|---|---|
| SCN-G01_NEW_EDGE | True | 0.9034 | 3.22 | 3.488 | 0.0 | 4 | causal_jaccard=0.0 |
| SCN-G02_FANOUT_BURST | True | 0.8643 | 3.22 | 2.333 | 0.0 | 3 | causal_jaccard=0.0 |
| SCN-G03_CHAIN_FORMATION | True | 0.7129 | 0.395 | 2.333 | 0.0 | 3 | causal_jaccard=0.0 |
| SCN-G04_LOCAL_REWIRING | True | 0.917 | 3.22 | 4.644 | -0.655 | 3 | causal_jaccard=1.0 |
| SCN-G05_INBOUND_CONVERGENCE | True | 0.8813 | 3.22 | 2.795 | 0.0 | 4 | causal_jaccard=0.0 |
| SCN-G06_NORMAL_NEW_EDGE | False | 0.9347 | 4.692 | 4.181 | -0.888 | 5 | causal_jaccard=0.6667 |
| SCN-G07_UNUSUAL_EDGE | True | 0.9506 | 4.692 | 4.181 | 0.0 | 6 | causal_jaccard=0.0 |
| SCN-G08_COMPOUND_CHANGE | True | 0.9301 | 4.692 | 3.072 | 0.0 | 5 | causal_jaccard=0.0 |

## Reading (honest)

- **Novelty flags every new edge** (G06 included) — exactly like Edge Behavior's NEW_PEER. Novelty alone therefore adds no discrimination on new edges.
- **The `low_similarity` family is the discriminator**: G06 (structurally plausible) has high shared structure (low-similarity z = -0.888) while G07 (structurally unusual) sits at 0.0.
- **The combined score does NOT cleanly separate G06 from G07** (both ≈ 0.93–0.95) because novelty/change dominate. Conclusion: graph context's *similarity* structure carries the incremental signal, not its novelty structure.

