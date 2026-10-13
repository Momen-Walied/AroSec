# Readiness

- episode offline/online parity: 0 mismatches (EXACT)
- restart recovery: 0 mismatches (EXACT)
- edge/node signals: 566/669 → episodes 633
- compression: 1.95 · episodes/site/day: 20.3
- observations/sec (full chain): 535
- episode finalization lag p50/p95/p99 (s): 180/300/300
- false merges: 0
- throughput is below the episode-off path because bounded finalization forces small
  scoring batches on this sparse stream (see performance.md); parity is unaffected.
- provisional: episode gap/max-duration, edge/node thresholds, `dataset_ip_fallback` identity

✅ READY TO FREEZE.

