# Drift Baseline (metrics only; no automatic retraining)

PSI (population stability index) of recent replay vs the training/validation reference.
PSI thresholds: warning >= 0.10, high >= 0.25.

- reference score n=13577 mean=0.217
- recent score n=67885 mean=0.207

| metric | PSI | KS | class |
|---|---:|---:|---|
| anomaly_score | 0.382 | 0.213 | DRIFT_HIGH |
| connections_count | 0.000 | 0.014 | DRIFT_NONE |
| outbound_bytes | 0.003 | 0.019 | DRIFT_NONE |
| fan_out | 0.000 | 0.002 | DRIFT_NONE |
| new_peer_rate | 0.000 | 0.001 | DRIFT_NONE |
| protocol_novelty_rate | 0.000 | 0.001 | DRIFT_NONE |
| port_novelty_rate | 0.000 | 0.001 | DRIFT_NONE |

**Overall: DRIFT_HIGH**

Limitations: PSI/KS compare aggregate distributions and cannot attribute drift to a
cause; the reference is the UNSW sample. No retraining is triggered.

