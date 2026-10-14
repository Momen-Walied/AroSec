# Candidate Task Comparison

| task | ground truth | measurability | leakage risk | product value | verdict |
|---|---|---|---|---|---|
| A next-edge / link prediction | self-supervised (next edge) | **degenerate here** (all heuristics MRR≈1) | medium (negative sampling) | low for anomaly | secondary/gated |
| B graph-context edge anomaly | scenarios + normal-test rate | high (vs Edge v1) | medium | **high** | **PRIMARY v1** |
| C graph-context node anomaly | scenarios + normal-test rate | high (vs Node v1) | medium | high | later track |
| D temporal subgraph deviation | scenarios | medium (no attack labels) | higher | very high (future stories) | later track |
| E next-relationship transition | self-supervised | low (few transitions) | medium | medium | later track |

## Why B first

1. It directly answers the central question — *does graph context beat Edge/Node behavior?*
2. It has an existing, frozen baseline (Edge Behavior v1) and an established evaluation pattern (synthetic scenarios + normal-test false-signal rate).
3. A (the most 'standard' temporal-graph task) is **degenerate on the current graph**: the hub makes next-edge ranking trivial for frequency/recency and pathological for structural heuristics. It cannot discriminate models today.
4. B degrades gracefully to a null result: if graph context adds nothing, we will see it rather than a fake high score.

