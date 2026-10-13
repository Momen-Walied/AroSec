# Edge Behavior v1 — Evaluation (normal test data)

> **Terminology.** This component detects *behavioural anomalies in temporal communication relationships*. On UNSW-IoTraffic (no attack labels) these are **relationship anomalies**, not proven attacks. UNSW identities are `dataset_ip_fallback` (source MACs are null), so results are **communication-entity anomalies**, not device anomalies. No claim of lateral-movement / malware detection is made.

## Normal-test alert behaviour (test split, no attack labels)

| model | alert rate | alerts | alerts/day | alerts/asset/day | alerts/rel/day | p50 | p90 | p99 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| statistical | 0.0968 | 1314 | 207.1 | 29.58 | 3.451 | 0.020 | 0.063 | 0.085 |
| isolation_forest | 0.0089 | 121 | 19.1 | 2.72 | 0.318 | 0.522 | 0.658 | 0.702 |
| autoencoder | 0.0059 | 80 | 12.6 | 1.80 | 0.210 | 0.629 | 0.930 | 1.000 |

Fusion: alert rate 0.0184, 39.4 alerts/day, 5.63 alerts/asset/day.

## Temporal stability (score drift)

| model | mean of daily mean | std of daily mean | max daily alert rate |
|---|---:|---:|---:|
| statistical | 0.0290 | 0.0062 | 0.1454 |
| isolation_forest | 0.5322 | 0.0089 | 0.0277 |
| autoencoder | 0.6733 | 0.0625 | 0.0253 |

> The statistical model's higher test alert rate reflects genuine behavioural novelty/drift in the test period (new peers/ports), not a labelling error. UNSW test traffic is normal, so these are *novelty* alerts.

## Definition-of-Done demonstration

Synthetic relationship windows (CAM-01 is a camera, NVR-01 a recorder, ENG-PC-03 an engineering workstation):

- **suspicious_cam01_to_engpc03** → fused_score=0.738, severity=CRITICAL, reasons: NEW_PEER(0.250), FAN_OUT_DEVIATION(0.117), APP_PROTOCOL_NOVELTY(0.100), PROTOCOL_NOVELTY(0.100), PORT_NOVELTY(0.075)
- **stable_cam01_to_nvr01** → fused_score=0.322, severity=LOW, reasons: APP_PROTOCOL_NOVELTY(0.100), TRAFFIC_VOLUME_DEVIATION(0.033), FAN_OUT_DEVIATION(0.020)

