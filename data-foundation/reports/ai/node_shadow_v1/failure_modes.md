# Failure Modes (fail-open; component isolation)

| failure | behaviour | network impact |
|---|---|---|
| edge model failure | edge pipeline disabled; node pipeline continues | none |
| node model failure | node pipeline disabled; edge pipeline continues | none |
| state failure | logged + counted; runtime continues | none |
| sink failure | logged + counted; scoring continues | none |
| schema mismatch | fails fast at startup with a clear error | none |

Component isolation: `edge_pipeline_errors_total` / `node_pipeline_errors_total` are counted independently; a failure in one does not stop the other. No remediation path exists. Covered by 5 documented cases.

