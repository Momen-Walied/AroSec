# Node Behavior v1 — Limitations

- **Identity:** UNSW entities are `dataset_ip_fallback` (source MACs null) → results are **entity/relationship behavior anomalies**, not device anomalies.
- **No attack labels:** evaluation is temporal-stability + synthetic-scenario + correlation based; no supervised detection performance is claimed.
- **Packet direction:** `packet_count` is flow-total and assigned by initiator side (splitting packets by direction is not available).
- **Drift:** thresholds are validation-derived; UNSW shows period drift.
- **Scope:** no GNN, no attack-path, no campaign reconstruction, no remediation; node/edge fusion not built (intentionally deferred).

