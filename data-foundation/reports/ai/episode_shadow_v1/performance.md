# Performance (full chain: Observation → Edge → Node → Episode, durable SQLite)

- observations/sec: **535** (Phase 2.5 reference 2045)
- regression vs Phase 2.5: -74%
- peak RSS: 2279.4 MB
- state DB: 8.70 MB · sink DB: 688.68 MB (incl. episodic table)
- edge feature p50=0.5597 p95=2.0940 p99=2.4575
- node feature p50=0.2126 p95=0.6041 p99=0.7677
- edge inference p50=1.1528 p95=5.2100 p99=5.6528
- node inference p50=0.0259 p95=0.0690 p99=0.0778
- **episode update p50=0.0132 p95=0.0243 p99=0.0277**
- **episode close p50=0.0403 p95=0.0566 p99=0.0780**
- **episode finalization lag (s) p50=180.0000 p95=300.0000 p99=300.0000**

Finalization lag = closure watermark - episode end_time; baseline relates to
correlation_gap + window/lateness semantics (per-scan ~= gap + window + lateness = 120 s).

> **Throughput note.** The Phase 2.5 reference (edge+node only) has no episode layer, so the
> delta above is not apples-to-apples. Watermark-driven episode finalization additionally
> forces finalized window batches to flush on the event-time feed horizon, which on the sparse
> UNSW 30 s stream means small scoring batches (episode layer ON ~535 obs/s vs
> episode layer OFF ~5,100 obs/s, same durable chain). This is the cost of bounded
> finalization latency, not an episode-correctness defect (parity is exact).

