# Failure Modes (fail-open; component isolation)

| failure | behaviour | network impact |
|---|---|---|
| edge model failure | edge pipeline disabled; node + episodes continue | none |
| node model failure | node pipeline disabled; edge + episodes continue | none |
| episode correlator failure | logged/counted; Edge/Node continue; episodes skipped | none |
| episode state DB failure | logged/counted; runtime continues (state loss on restart) | none |
| episode sink failure | logged/counted; scoring continues | none |
| malformed signal | skipped/quarantined; never rewrites closed episodes | none |

No remediation path exists; the runtime is read-only and fail-open.

