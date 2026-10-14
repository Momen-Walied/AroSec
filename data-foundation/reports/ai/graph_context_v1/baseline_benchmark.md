# Non-GNN Benchmark Table

| baseline | test alert rate | alerts/site/day | G04 | G05 | G07 | G08 | hub | non-hub |
|---|---|---|---|---|---|---|---|---|
| Edge Behavior v1 | 0.0178 | 7.7 | n/a | n/a | n/a | n/a | | |
| Graph Context v1 (combined) | 0.0135 | 5.869 | 0.917 | 0.8813 | 0.9506 | 0.9301 | 0.0135 | 0.0 |

*Scenario columns are the graph-context score; Edge v1 cannot be run on synthetic graphs (no trained window), so its scenario behaviour is the edge-local NEW_PEER proxy (1.0 for every new edge → cannot separate G06 from G07).*

See synthetic_scenarios.md for the full comparison.

