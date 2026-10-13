"""Sink + metrics tests."""
from __future__ import annotations

import json
import sqlite3

from ai.shadow.metrics.collector import MetricsCollector
from ai.shadow.sinks.jsonl import JsonlShadowSink
from ai.shadow.sinks.sqlite import SqliteShadowSink
from tests.ai.shadow._helpers import make_record


def test_jsonl_sink_writes_records(tmp_path):
    sink = JsonlShadowSink(tmp_path / "out.jsonl")
    sink.write(make_record(0.3))
    sink.write(make_record(0.7))
    sink.close()
    lines = [line for line in (tmp_path / "out.jsonl").read_text().splitlines() if line.strip()]
    assert len(lines) == 2
    assert json.loads(lines[0])["shadow_mode"] is True


def test_sqlite_sink_is_idempotent(tmp_path):
    path = tmp_path / "out.sqlite"
    sink = SqliteShadowSink(path)
    record = make_record(0.5)
    sink.write(record)
    sink.write(record)  # same (relationship_id, window_start)
    sink.close()
    conn = sqlite3.connect(str(path))
    count = conn.execute("SELECT COUNT(*) FROM shadow_records").fetchone()[0]
    conn.close()
    assert count == 1


def test_metrics_collector_percentiles():
    m = MetricsCollector()
    m.inc("alerts_total", 3)
    for v in range(1, 101):
        m.observe("inference_latency_ms", float(v))
    m.gauge("active_relationships", 5)
    snap = m.snapshot()
    assert snap["counters"]["alerts_total"] == 3
    assert snap["gauges"]["active_relationships"] == 5
    h = snap["histograms"]["inference_latency_ms"]
    assert h["count"] == 100
    assert h["p50"] == 50.5 or h["p50"] >= 50
    assert h["p99"] >= 99
