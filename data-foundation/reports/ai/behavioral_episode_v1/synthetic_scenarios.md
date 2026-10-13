# Synthetic Correlation Scenarios

gap = 60s, max duration = 600s.

| scenario | episodes | evidence strength | families |
|---|---:|---|---|
| SCN-E01_SAME_ENTITY_BURST | 1 | ['STRONG'] | [['PEER_NOVELTY', 'TOPOLOGY_SPREAD', 'PORT_CHANGE']] |
| SCN-E02_CHAIN | 1 | ['WEAK'] | [['PEER_NOVELTY']] |
| SCN-E03_UNRELATED_SIMULTANEOUS | 2 | ['WEAK', 'WEAK'] | [['PEER_NOVELTY'], ['PEER_NOVELTY']] |
| SCN-E04_SAME_ENTITY_LARGE_GAP | 2 | ['WEAK', 'WEAK'] | [['PEER_NOVELTY'], ['PEER_NOVELTY']] |
| SCN-E05_NODE_EDGE_SUPPORT | 1 | ['STRONG'] | [['PEER_NOVELTY', 'PORT_CHANGE']] |
| SCN-E06_ALERT_STORM | 1 | ['MODERATE'] | [['PEER_NOVELTY']] |
| SCN-E07_PERCOLATION_STRESS | 2 | ['MODERATE', 'WEAK'] | [['PEER_NOVELTY'], ['PEER_NOVELTY']] |
| SCN-E08_TWO_ACTIVE_MERGE | 1 | ['MODERATE'] | [['PEER_NOVELTY']] |

SCN-E02 chain correlation does NOT prove A→B→C attack movement; it only shows
relational connectivity in time.

