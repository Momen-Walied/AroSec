"""Shadow runtime: observe -> online features -> score -> record.

Read-only with respect to the customer network. There is no remediation path: the only
outputs are a shadow sink, metrics, and logs.

Finalized windows are scored in batches (large amortization of pandas/sklearn per-call
overhead) while preserving per-window causal semantics: features come from the online
builder and the history-dependent ``app_protocol_novelty_count`` is applied per window.
"""
from __future__ import annotations

import time
from datetime import UTC, datetime

import pandas as pd

from ai.contracts.edge_anomaly_result import EdgeAnomalyResultV1, IdentityQuality
from ai.contracts.shadow_records import ShadowInferenceRecordV1
from ai.edge_behavior.features.builder import FEATURE_COLUMNS, build_feature_matrix
from ai.shadow.config import ShadowConfig
from ai.shadow.features.online_builder import OnlineFeatureBuilder
from ai.shadow.inference.model_bundle import ShadowModelBundle
from ai.shadow.metrics.collector import MetricsCollector
from ai.shadow.sinks.base import ShadowSink
from ai.shadow.sources.base import ObservationSource
from ai.shadow.state.base import StateStore
from src.schemas.v2 import EdgeFeatureWindowV2

RUNTIME_VERSION = "shadow-runtime-v1"
_APP_NOVELTY_IDX = FEATURE_COLUMNS.index("app_protocol_novelty_count")


class ShadowRuntime:
    def __init__(self, config: ShadowConfig, source: ObservationSource, sink: ShadowSink,
                 state_store: StateStore, bundle: ShadowModelBundle,
                 identity_map: dict | None = None, metrics: MetricsCollector | None = None,
                 batch_size: int = 2048) -> None:
        self.config = config
        self.source = source
        self.sink = sink
        self.state_store = state_store
        self.bundle = bundle
        self.identity_map = identity_map or {}
        self.metrics = metrics or MetricsCollector()
        self.batch_size = batch_size
        self.started_at = time.time()
        self._pending: list[EdgeFeatureWindowV2] = []

        saved = self.state_store.load()
        self.builder = OnlineFeatureBuilder.from_state(saved) if saved else OnlineFeatureBuilder(
            window_seconds=config.window_seconds,
            allowed_lateness_seconds=config.allowed_lateness_seconds,
            dedupe_capacity=config.dedupe_capacity,
            dataset_source=config.dataset_id,
        )

    # ------------------------------------------------------------------ #
    def run(self, persist_every: int = 50_000) -> dict:
        processed = 0
        self.metrics.gauge("active_relationships", float(len(self.builder.rel_state)))
        try:
            for obs in self.source:
                processed += 1
                try:
                    finalized = self.builder.add(obs)
                except Exception:  # noqa: BLE001 - fail-open: never affect the network
                    self.metrics.inc("malformed_observations_total")
                    continue
                if finalized:
                    self._pending.extend(finalized)
                    if len(self._pending) >= self.batch_size:
                        self._flush_batch()
                if processed % persist_every == 0:
                    self._persist()
            self._pending.extend(self.builder.flush())
            self._flush_batch()
        finally:
            self._persist()
            self.metrics.gauge("uptime_seconds", time.time() - self.started_at)
            self.metrics.gauge("active_relationships", float(len(self.builder.rel_state)))
            self.metrics.gauge("state_size_relationships", float(len(self.builder.rel_state)))
            self.metrics.gauge("state_size_sources", float(len(self.builder.src_state)))
        return self.summary(processed)

    def _persist(self) -> None:
        try:
            self.state_store.save(self.builder.to_state())
        except Exception:  # noqa: BLE001
            self.metrics.inc("state_store_errors_total")

    def _flush_batch(self) -> None:
        if not self._pending:
            return
        windows = self._pending
        self._pending = []
        t0 = time.perf_counter()
        try:
            frame = pd.DataFrame([w.model_dump() for w in windows])
            matrix = build_feature_matrix(frame)
            X = matrix[FEATURE_COLUMNS].to_numpy(dtype=float)
            by_key = {(w.window_start.isoformat(), w.relationship_id): w for w in windows}
            ordered: list[EdgeFeatureWindowV2] = []
            for i in range(len(matrix)):
                key = (pd.Timestamp(matrix.iloc[i]["window_start"]).isoformat(),
                       str(matrix.iloc[i]["relationship_id"]))
                ctx = self.builder.window_context.pop(key, None)
                if ctx is not None:
                    X[i, _APP_NOVELTY_IDX] = float(ctx["app_protocol_novelty_count"])
                ordered.append(by_key[key])
            n = max(len(ordered), 1)
            self.metrics.observe("feature_build_latency_ms", (time.perf_counter() - t0) * 1000.0 / n)

            it0 = time.perf_counter()
            scores = self.bundle.score(X)
            reasons_list, feats_list = self.bundle.explain_batch(X)
            self.metrics.observe("inference_latency_ms", (time.perf_counter() - it0) * 1000.0 / n)

            now = datetime.now(UTC)
            for i, window in enumerate(ordered):
                self._emit(window, float(scores[i]), reasons_list[i], feats_list[i], now)
        except Exception:  # noqa: BLE001 - fail-open
            self.metrics.inc("inference_errors_total")

    def _emit(self, window: EdgeFeatureWindowV2, score: float, reasons: list[dict],
              contributions: dict, now: datetime) -> None:
        self.metrics.inc("inference_total")
        self.metrics.observe("anomaly_score", score)
        severity = self.bundle.severity(score)
        self.metrics.inc(f"severity_{severity}_total")
        if score >= self.config.shadow_threshold:
            self.metrics.inc("alerts_total")
        for reason in reasons:
            self.metrics.inc(f"alert_reason_{reason['code']}_total")

        identity = self.identity_map.get(window.src_asset_id, {})
        anomaly = EdgeAnomalyResultV1(
            model_version=self.bundle.model_version,
            relationship_id=window.relationship_id,
            window_start=window.window_start, window_end=window.window_end,
            anomaly_score=score, severity=severity,
            reasons=reasons, feature_contributions=contributions,
            evidence_refs=[window.relationship_id, f"window:{window.window_start.isoformat()}",
                           f"src:{window.src_asset_id}", f"dst:{window.dst_asset_id}"],
            identity_quality=IdentityQuality(
                identity_method=identity.get("identity_method"),
                identity_confidence=identity.get("identity_confidence"),
                identity_is_provisional=True,
            ),
            inference_timestamp=now,
        )
        record = ShadowInferenceRecordV1(
            runtime_version=RUNTIME_VERSION,
            received_at=now, processed_at=now,
            feature_window=window, anomaly_result=anomaly,
            processing_latency_ms=0.0,
            late_record_count=int(self.builder.counters["observations_late_total"]),
            identity_method=identity.get("identity_method"),
            identity_confidence=identity.get("identity_confidence"),
        )
        try:
            self.sink.write(record)
        except Exception:  # noqa: BLE001
            self.metrics.inc("sink_errors_total")

    def summary(self, processed: int) -> dict:
        return {
            "runtime_version": RUNTIME_VERSION,
            "mode": self.config.mode,
            "observations_processed": processed,
            "builder_counters": dict(self.builder.counters),
            "metrics": self.metrics.snapshot(),
        }
