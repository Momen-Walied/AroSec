# Edge / Node Complementarity (analysis only; NO fusion)

## Window overlap

- both alert: 25 (0.027)
- edge only: 413 (0.438)
- node only: 504 (0.535)

- edge alerts per node-alert window: 0.07
- node-alert windows containing >=1 edge alert: 0.047
- edge alerts while node normal: 0.943

## Score correlation (window level)

- windows compared: 35805
- Pearson: 0.0038 · Spearman: 0.0017

## Incident-like grouping (report only, NO combined score)

### asset:unsw:176.32.98.204 @ 2016-09-30T19:30:00+00:00
- node score 1.0 CRITICAL · reasons ['RELATIONSHIP_CREATION_BURST', 'PEER_SET_CHANGE', 'PORT_DIVERSITY_CHANGE', 'PROTOCOL_DIVERSITY_CHANGE']
  - 176.32.98.204->192.168.1.240: 0.679 (ALERT)

### asset:unsw:192.168.1.240 @ 2016-09-30T20:34:30+00:00
- node score 1.0 CRITICAL · reasons ['RELATIONSHIP_CREATION_BURST', 'PEER_SET_CHANGE', 'PORT_DIVERSITY_CHANGE', 'PROTOCOL_DIVERSITY_CHANGE', 'INBOUND_VOLUME_DEVIATION']
  - 192.168.1.240->192.168.1.1: 0.273
  - 192.168.1.240->208.67.220.220: 0.273
  - 192.168.1.240->8.8.8.8: 0.311

### asset:unsw:192.168.1.240 @ 2016-09-30T20:35:30+00:00
- node score 1.0 CRITICAL · reasons ['RELATIONSHIP_CREATION_BURST', 'PEER_SET_CHANGE', 'PORT_DIVERSITY_CHANGE', 'PROTOCOL_DIVERSITY_CHANGE', 'INBOUND_VOLUME_DEVIATION']
  - 192.168.1.240->192.168.1.1: 0.229
  - 192.168.1.240->54.239.26.180: 0.255
  - 192.168.1.240->72.21.192.213: 0.221
  - 192.168.1.240->72.21.207.120: 0.296
  - 192.168.1.240->8.8.8.8: 0.215

### asset:unsw:72.21.192.213 @ 2016-09-30T20:41:00+00:00
- node score 1.0 CRITICAL · reasons ['RELATIONSHIP_CREATION_BURST', 'PEER_SET_CHANGE', 'PORT_DIVERSITY_CHANGE', 'PROTOCOL_DIVERSITY_CHANGE']
  - 192.168.1.240->72.21.192.213: 0.218

### asset:unsw:74.125.34.101 @ 2016-09-30T21:31:00+00:00
- node score 1.0 CRITICAL · reasons ['RELATIONSHIP_CREATION_BURST', 'PEER_SET_CHANGE', 'INBOUND_VOLUME_DEVIATION', 'PORT_DIVERSITY_CHANGE', 'PROTOCOL_DIVERSITY_CHANGE']
  - 192.168.1.240->74.125.34.101: 0.28

These groupings are for analyst context only; no incident score is produced.

