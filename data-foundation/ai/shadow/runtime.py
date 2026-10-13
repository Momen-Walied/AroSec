"""Shadow runtime v3.5: observe -> (edge | node) -> behavioral episodes -> record.

Read-only; no remediation. Edge and Node intelligence remain INDEPENDENT; the episode layer
correlates their signals into BehavioralEpisodeV1 groups (no score fusion, no incident/attack
semantics). Observation idempotency and event-time handling are shared.
"""
from __future__ import annotations

import time
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from ai.contracts.edge_anomaly_result import EdgeAnomalyResultV1, IdentityQuality
from ai.contracts.node_anomaly_result import NodeAnomalyReason, NodeAnomalyResultV1
from ai.contracts.shadow_records import (
    EpisodeShadowRecordV1,
    ShadowInferenceRecordV1,
    ShadowNodeInferenceRecordV1,
)
from ai.edge_behavior.calibration import severity_for
from ai.edge_behavior.features.builder import FEATURE_COLUMNS, build_feature_matrix
from ai.episodes.correlator.correlator import BehavioralEpisodeCorrelator
from ai.episodes.correlator.signals import Signal
from ai.node_behavior.config import NODE_FEATURE_COLUMNS
from ai.node_behavior.features.builder import build_node_feature_matrix
from ai.node_behavior.features.schema import NodeFeatureWindowV2
from ai.shadow.config import ShadowConfig
from ai.shadow.features.online_builder import OnlineFeatureBuilder
from ai.shadow.features.online_node_builder import OnlineNodeFeatureBuilder
from ai.shadow.inference.model_bundle import ShadowModelBundle
from ai.shadow.metrics.collector import MetricsCollector
from ai.shadow.sinks.base import ShadowSink
from ai.shadow.sources.base import ObservationSource
from ai.shadow.state.base import StateStore
from src.schemas.v2 import CommunicationObservation, EdgeFeatureWindowV2

RUNTIME_VERSION = "shadow-runtime-v3.5"
_APP_NOVELTY_IDX = FEATURE_COLUMNS.index("app_protocol_novelty_count")


class ShadowRuntime:
    def __init__(self, config: ShadowConfig, source: ObservationSource, sink: ShadowSink,
                 state_store: StateStore, edge_bundle: ShadowModelBundle | None = None,
                 node_scorer=None, identity_map: dict | None = None,
                 metrics: MetricsCollector | None = None, batch_size: int = 2048) -> None:
        self.config = config
        self.source = source
        self.sink = sink
        self.state_store = state_store
        self.edge_bundle = edge_bundle
        self.node_scorer = node_scorer
        self.identity_map = identity_map or {}
        self.metrics = metrics or MetricsCollector()
        self.batch_size = batch_size
        self.started_at = time.time()
        self._pending_edge: list[EdgeFeatureWindowV2] = []
        self._pending_node: list[NodeFeatureWindowV2] = []
        self._signal_buffer: list[Signal] = []
        self._pending_wend_min = None
        self._seen: dict[str, None] = {}

        edge_state, node_state, episode_state = self._load_states()
        self.edge_builder = (OnlineFeatureBuilder.from_state(edge_state) if edge_state else
                             OnlineFeatureBuilder(window_seconds=config.window_seconds,
                                                  allowed_lateness_seconds=config.allowed_lateness_seconds,
                                                  dedupe_capacity=config.dedupe_capacity,
                                                  dataset_source=config.dataset_id))
        self.node_builder = (OnlineNodeFeatureBuilder.from_state(node_state) if node_state else
                             OnlineNodeFeatureBuilder(window_seconds=config.window_seconds,
                                                      allowed_lateness_seconds=config.allowed_lateness_seconds,
                                                      dedupe_capacity=config.dedupe_capacity,
                                                      dataset_source=config.dataset_id))
        if config.episodes_enabled and episode_state:
            self.correlator = BehavioralEpisodeCorrelator.from_state(episode_state)
            self.correlator.identity_map = self.identity_map
        elif config.episodes_enabled:
            self.correlator = BehavioralEpisodeCorrelator(
                config.episode_correlation_gap_seconds, config.episode_max_duration_seconds,
                self.identity_map, config.window_seconds, config.allowed_lateness_seconds)
        else:
            self.correlator = None

    def _load_states(self):
        saved = self.state_store.load()
        if not saved:
            return None, None, None
        if "edge" in saved or "node" in saved or "episodes" in saved:
            return saved.get("edge"), saved.get("node"), saved.get("episodes")
        if "rel_state" in saved:  # legacy v1 blob
            return saved, None, None
        return None, None, None

    # ------------------------------------------------------------------ #
    def run(self, persist_every: int = 50_000, flush_at_end: bool = True) -> dict:
        processed = 0
        try:
            for obs in self.source:
                processed += 1
                try:
                    self._dispatch(obs)
                except Exception:  # noqa: BLE001
                    self.metrics.inc("malformed_observations_total")
                    continue
                if processed % persist_every == 0:
                    self._persist()
            if flush_at_end:
                self._pending_edge.extend(self.edge_builder.flush())
                self._pending_node.extend(self.node_builder.flush())
                self._flush_batches()
                self._finalize_episodes()
            else:
                # pause: score already-finalized windows, but keep open windows/episodes open
                self._flush_batches()
        finally:
            self._persist()
            self.metrics.gauge("uptime_seconds", time.time() - self.started_at)
            self.metrics.gauge("active_relationships", float(len(self.edge_builder.rel_state)))
            self.metrics.gauge("active_entities", float(len(self.node_builder.asset_state)))
            if self.correlator is not None:
                self.metrics.gauge("episodes_open", float(len(self.correlator.active)))
        return self.summary(processed)

    def _dispatch(self, obs: CommunicationObservation) -> None:
        if obs.observation_id in self._seen:
            self.metrics.inc("observations_duplicate_total")
            return
        self._remember(obs.observation_id)

        if self.edge_bundle is not None:
            try:
                edge_fin = self.edge_builder.add(obs)
                self._pending_edge.extend(edge_fin)
            except Exception:  # noqa: BLE001
                self.metrics.inc("edge_pipeline_errors_total")
                edge_fin = []
        else:
            edge_fin = []
        if self.node_scorer is not None:
            try:
                node_fin = self.node_builder.add(obs)
                self._pending_node.extend(node_fin)
            except Exception:  # noqa: BLE001
                self.metrics.inc("node_pipeline_errors_total")
                node_fin = []
        else:
            node_fin = []
        newly = edge_fin + node_fin
        if newly:
            m = min(w.window_end for w in newly)
            self._pending_wend_min = m if self._pending_wend_min is None else min(self._pending_wend_min, m)

        wm = self.edge_builder.watermark
        slack = self.config.window_seconds + self.config.allowed_lateness_seconds
        # Feed finalized windows before any open episode could expire. The age horizon is the
        # maximal safe feed delay (gap + window + lateness), which minimizes forced small batches
        # while keeping watermark-driven finalization correct.
        horizon = self.config.episode_correlation_gap_seconds + slack
        due_by_size = (len(self._pending_edge) + len(self._pending_node)) >= self.batch_size
        due_by_age = (self.correlator is not None and self._pending_wend_min is not None and wm is not None
                      and (wm - self._pending_wend_min).total_seconds() > horizon)
        if due_by_size or due_by_age:
            self._flush_batches()
        self._maybe_close_episodes()

    def _maybe_close_episodes(self) -> None:
        """Watermark-driven episode expiry: close on event-time progress, even with no signal."""
        if self.correlator is None or not self.correlator.active:
            return
        wm = self.edge_builder.watermark
        if wm is None or not self.correlator.any_expired(wm):
            return
        if self._pending_edge or self._pending_node:
            self._flush_edge_batch()
            self._flush_node_batch()
            self._pending_wend_min = None
            self._process_signals()
        t0 = time.perf_counter()
        closed = self.correlator.advance_watermark(wm)
        if closed:
            self.metrics.observe("episode_close_latency_ms",
                                 (time.perf_counter() - t0) * 1000.0 / len(closed))
        for ep in closed:
            self.metrics.observe("episode_finalization_lag_seconds", (wm - ep.end_time).total_seconds())
        open_now = len(self.correlator.active)
        self.metrics.gauge("episodes_open", float(open_now))
        self.metrics.gauge("episodes_open_max",
                           float(max(open_now, int(self.metrics.gauges.get("episodes_open_max", 0)))))
        self._write_episodes(closed, closed_at=wm)

    def _remember(self, oid: str) -> None:
        self._seen[oid] = None
        if len(self._seen) > self.config.dedupe_capacity:
            for _ in range(len(self._seen) - self.config.dedupe_capacity):
                self._seen.pop(next(iter(self._seen)))

    def _persist(self) -> None:
        try:
            state = {"edge": self.edge_builder.to_state(), "node": self.node_builder.to_state()}
            if self.correlator is not None:
                state["episodes"] = self.correlator.to_state()
            self.state_store.save(state)
        except Exception:  # noqa: BLE001
            self.metrics.inc("state_store_errors_total")

    # ------------------------------------------------------------------ #
    def _flush_batches(self) -> None:
        self._flush_edge_batch()
        self._flush_node_batch()
        self._pending_wend_min = None
        self._process_signals()

    def _flush_edge_batch(self) -> None:
        if not self._pending_edge or self.edge_bundle is None:
            self._pending_edge = []
            return
        windows = self._pending_edge
        self._pending_edge = []
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
                ctx = self.edge_builder.window_context.pop(key, None)
                if ctx is not None:
                    X[i, _APP_NOVELTY_IDX] = float(ctx["app_protocol_novelty_count"])
                ordered.append(by_key[key])
            n = max(len(ordered), 1)
            self.metrics.observe("feature_build_latency_ms", (time.perf_counter() - t0) * 1000.0 / n)
            it0 = time.perf_counter()
            scores = self.edge_bundle.score(X)
            reasons_list, feats_list = self.edge_bundle.explain_batch(X)
            self.metrics.observe("inference_latency_ms", (time.perf_counter() - it0) * 1000.0 / n)
            now = datetime.now(UTC)
            for i, w in enumerate(ordered):
                self._emit_edge(w, float(scores[i]), reasons_list[i], feats_list[i], now)
        except Exception:  # noqa: BLE001
            self.metrics.inc("edge_inference_errors_total")

    def _emit_edge(self, window, score, reasons, contributions, now) -> None:
        self.metrics.inc("inference_total")
        self.metrics.observe("anomaly_score", score)
        severity = self.edge_bundle.severity(score)
        self.metrics.inc(f"severity_{severity}_total")
        if score >= self.config.shadow_threshold:
            self.metrics.inc("alerts_total")
        for reason in reasons:
            self.metrics.inc(f"alert_reason_{reason['code']}_total")
        identity = self.identity_map.get(window.src_asset_id, {})
        evidence_refs = [window.relationship_id, f"window:{window.window_start.isoformat()}",
                         f"src:{window.src_asset_id}", f"dst:{window.dst_asset_id}"]
        anomaly = EdgeAnomalyResultV1(
            model_version=self.edge_bundle.model_version, relationship_id=window.relationship_id,
            window_start=window.window_start, window_end=window.window_end,
            anomaly_score=score, severity=severity, reasons=reasons, feature_contributions=contributions,
            evidence_refs=evidence_refs,
            identity_quality=IdentityQuality(identity_method=identity.get("identity_method"),
                                             identity_confidence=identity.get("identity_confidence"),
                                             identity_is_provisional=True),
            inference_timestamp=now)
        self._safe_write(ShadowInferenceRecordV1(
            runtime_version=RUNTIME_VERSION, received_at=now, processed_at=now,
            feature_window=window, anomaly_result=anomaly, processing_latency_ms=0.0,
            late_record_count=int(self.edge_builder.counters["observations_late_total"]),
            identity_method=identity.get("identity_method"),
            identity_confidence=identity.get("identity_confidence")))
        if self.correlator is not None and score >= self.config.shadow_threshold:
            sid = f"sig:edge:{window.relationship_id}:{window.window_start.isoformat()}"
            self._signal_buffer.append(Signal(
                signal_id=sid, signal_type="edge", window_start=window.window_start,
                window_end=window.window_end, score=score, severity=severity,
                reason_codes=tuple(sorted({r["code"] for r in reasons})),
                asset_ids=tuple(sorted({window.src_asset_id, window.dst_asset_id})),
                relationship_id=window.relationship_id, result_ref=sid,
                evidence_refs=tuple(evidence_refs)))

    def _flush_node_batch(self) -> None:
        if not self._pending_node or self.node_scorer is None:
            self._pending_node = []
            return
        windows = self._pending_node
        self._pending_node = []
        t0 = time.perf_counter()
        try:
            frame = build_node_feature_matrix(windows)
            X = frame[NODE_FEATURE_COLUMNS].to_numpy(dtype=float)
            w_by_key = {(w.window_start.isoformat(), w.asset_id): w for w in windows}
            n = max(len(windows), 1)
            self.metrics.observe("node_feature_build_latency_ms", (time.perf_counter() - t0) * 1000.0 / n)
            it0 = time.perf_counter()
            scores = np.clip(self.node_scorer.model.score(X), 0.0, 1.0)
            reasons_list, feats_list = self.node_scorer.statistical.explain_batch(X)
            self.metrics.observe("node_inference_latency_ms", (time.perf_counter() - it0) * 1000.0 / n)
            now = datetime.now(UTC)
            for i in range(len(frame)):
                key = (pd.Timestamp(frame.iloc[i]["window_start"]).isoformat(), str(frame.iloc[i]["asset_id"]))
                self._emit_node(w_by_key[key], float(scores[i]), reasons_list[i], feats_list[i], now)
        except Exception:  # noqa: BLE001
            self.metrics.inc("node_inference_errors_total")

    def _emit_node(self, window, score, reasons, contributions, now) -> None:
        self.metrics.inc("node_inference_total")
        self.metrics.observe("node_anomaly_score", score)
        severity = severity_for(score, self.node_scorer.severity_thresholds)
        self.metrics.inc(f"node_severity_{severity}_total")
        if score >= self.config.node_threshold:
            self.metrics.inc("node_alerts_total")
        for reason in reasons:
            self.metrics.inc(f"node_alert_reason_{reason['code']}_total")
        identity = self.identity_map.get(window.asset_id, {})
        evidence_refs = [window.asset_id, f"window:{window.window_start.isoformat()}"]
        anomaly = NodeAnomalyResultV1(
            model_version=self.node_scorer.model_version, asset_id=window.asset_id,
            window_start=window.window_start, window_end=window.window_end,
            anomaly_score=score, severity=severity,
            reasons=[NodeAnomalyReason(**r) for r in reasons], feature_contributions=contributions,
            identity_method=identity.get("identity_method"),
            identity_confidence=identity.get("identity_confidence"),
            evidence_refs=evidence_refs, inference_timestamp=now)
        self._safe_write(ShadowNodeInferenceRecordV1(
            runtime_version=RUNTIME_VERSION, received_at=now, processed_at=now,
            feature_window=window, anomaly_result=anomaly, processing_latency_ms=0.0,
            late_record_count=int(self.node_builder.counters["node_observations_late_total"]),
            identity_method=identity.get("identity_method"),
            identity_confidence=identity.get("identity_confidence")))
        if self.correlator is not None and score >= self.config.node_threshold:
            sid = f"sig:node:{window.asset_id}:{window.window_start.isoformat()}"
            self._signal_buffer.append(Signal(
                signal_id=sid, signal_type="node", window_start=window.window_start,
                window_end=window.window_end, score=score, severity=severity,
                reason_codes=tuple(sorted({r["code"] for r in reasons})),
                asset_ids=(window.asset_id,), relationship_id=None, result_ref=sid,
                evidence_refs=tuple(evidence_refs)))

    # ------------------------------------------------------------------ #
    def _process_signals(self) -> list:
        if self.correlator is None or not self._signal_buffer:
            self._signal_buffer = []
            return []
        signals = sorted(self._signal_buffer,
                          key=lambda s: (s.window_start, s.signal_type, s.signal_id))
        self._signal_buffer = []
        closed: list = []
        for s in signals:
            t0 = time.perf_counter()
            try:
                closed.extend(self.correlator.add(s))
            except Exception:  # noqa: BLE001 - component isolation
                self.metrics.inc("episode_correlator_errors_total")
                continue
            self.metrics.observe("episode_update_latency_ms", (time.perf_counter() - t0) * 1000.0)
        open_now = len(self.correlator.active)
        self.metrics.gauge("episodes_open", float(open_now))
        self.metrics.gauge("episodes_open_max",
                           float(max(open_now, int(self.metrics.gauges.get("episodes_open_max", 0)))))
        self.metrics.gauge("signal_dedupe_size", float(self.correlator.seen_size))
        self._write_episodes(closed, closed_at=self.edge_builder.watermark)
        return closed

    def _finalize_episodes(self) -> None:
        if self.correlator is None:
            return
        self._process_signals()
        t0 = time.perf_counter()
        try:
            closed = self.correlator.flush()
        except Exception:  # noqa: BLE001
            self.metrics.inc("episode_correlator_errors_total")
            closed = []
        if closed:
            self.metrics.observe("episode_close_latency_ms", (time.perf_counter() - t0) * 1000.0)
        self._write_episodes(closed, closed_at=self.edge_builder.watermark)

    def _write_episodes(self, episodes: list, closed_at=None) -> None:
        for ep in episodes:
            self.metrics.inc("episodes_closed_total")
            self.metrics.inc("episode_signal_count_total", ep.edge_signal_count + ep.node_signal_count)
            self.metrics.observe("episode_signal_count", float(ep.edge_signal_count + ep.node_signal_count))
            self.metrics.observe("episode_asset_count", float(len(ep.involved_asset_ids)))
            if ep.edge_signal_count and ep.node_signal_count:
                self.metrics.inc("mixed_episodes_total")
            elif ep.edge_signal_count:
                self.metrics.inc("edge_only_episodes_total")
            else:
                self.metrics.inc("node_only_episodes_total")
            self.metrics.inc(f"evidence_strength_{ep.evidence_strength}_total")
            try:
                self.sink.write_episode(EpisodeShadowRecordV1(
                    runtime_version=RUNTIME_VERSION, episode=ep, closed_at=closed_at))
            except Exception:  # noqa: BLE001
                self.metrics.inc("episode_sink_errors_total")

    def _safe_write(self, record) -> None:
        try:
            self.sink.write(record)
        except Exception:  # noqa: BLE001
            self.metrics.inc("sink_errors_total")

    def summary(self, processed: int) -> dict:
        out = {
            "runtime_version": RUNTIME_VERSION, "mode": self.config.mode,
            "observations_processed": processed,
            "edge_builder_counters": dict(self.edge_builder.counters),
            "node_builder_counters": dict(self.node_builder.counters),
            "metrics": self.metrics.snapshot(),
        }
        if self.correlator is not None:
            out["episode_counters"] = dict(self.correlator.counters)
        return out
