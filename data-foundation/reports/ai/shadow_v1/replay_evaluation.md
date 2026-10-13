# Shadow Replay Evaluation

- site (synthetic operational framing): `replay_site`
- scored windows: 67885 over 31.18 days
- alerts: 566 (rate 0.0083)
- alerts/site/day: 18.2
- alerts/asset/day: 1.30
- alerts/relationship/day: 0.245

## Score percentiles

| p50 | p90 | p95 | p99 |
|---|---|---|---|
| 0.195 | 0.259 | 0.272 | 0.312 |

## Severity distribution

- CRITICAL: 103
- HIGH: 77
- INFO: 67322
- LOW: 131
- MEDIUM: 252

## Top reasons

- TRAFFIC_VOLUME_DEVIATION: 38802
- FAN_OUT_DEVIATION: 27913
- PROTOCOL_NOVELTY: 9292
- PORT_NOVELTY: 105
- NEW_PEER: 74
- APP_PROTOCOL_NOVELTY: 73
- PORT_DIVERSITY: 23

## Novelty frequency (share of scored windows)

- NEW_PEER: 0.0011
- PORT_NOVELTY: 0.0015
- PROTOCOL_NOVELTY: 0.1369
- FAN_OUT_DEVIATION: 0.4112
- TRAFFIC_VOLUME_DEVIATION: 0.5716
- APP_PROTOCOL_NOVELTY: 0.0011

## Processing latency (ms)

| p50 | p90 | p95 | p99 |
|---|---|---|---|
| 0.000 | 0.000 | 0.000 | 0.000 |

