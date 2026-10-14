# Hub Bias Analysis

One gateway owns ~99.6% of edge-windows. Hub membership is defined structurally as a causal degree ≥ the 95th percentile (no hardcoded asset id).

- TEST alert rate — hub-involved edges: **0.0135** (n=13576)
- TEST alert rate — non-hub edges: **0.0** (n=0)

| stratum | n | alert rate |
|---|---|---|
| src_hub | 13523 | 0.0126 |
| src_low | 53 | 0.2264 |
| dst_hub | 53 | 0.2264 |
| dst_low | 13523 | 0.0126 |

A feature that works *only* by recognising hub membership would show a severe hub/non-hub collapse. The strata above are reported independently so aggregate metrics cannot hide non-hub behaviour.

