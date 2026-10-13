# State Recovery (restart in the middle of the stream)

- restart mismatches vs uninterrupted: **0**
  (online-only 0, offline-only 0, membership 0)
- max simultaneous open episodes: 1
- open episodes at end: 0
- signal dedupe size: 1235

Episode state (open episodes, membership, evidence, dedupe, watermark) is persisted
alongside Edge/Node state; closed episodes leave active memory.

