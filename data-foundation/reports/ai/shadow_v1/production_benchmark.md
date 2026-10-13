# Shadow Production-like Benchmark (durable state + durable sink)

Durable `SqliteStateStore` + `SqliteShadowSink`; no in-memory accumulation of records.

- observations: 98747
- feature windows: 67885
- elapsed: 16.3s
- **observations/sec: 6058**
- **peak RSS: 676.9 MB**
- SQLite state DB: 4.30 MB
- SQLite shadow sink DB: 273.47 MB
- feature latency: p50=0.0596 p95=0.0639 p99=0.0834 ms
- inference latency: p50=0.0143 p95=0.0236 p99=0.0440 ms
- duplicates: 0 · late: 0

Note: peak RSS includes the replay source (the full v0.2 observation frame loaded from
Parquet) and the loaded model artifacts. In a live deployment the source is streamed and
the sink writes to disk; the runtime itself retains only relationship/source sets and
open-window buffers.
