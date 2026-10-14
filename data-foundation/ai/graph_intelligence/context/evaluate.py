"""Phase 4B evaluation: graph-context score vs Edge/Node Behavior, hub stratification,
complementarity, disagreement, ablations and performance.

Leakage discipline: the scorer's normalization is fit on TRAIN, the alert threshold is chosen
on VALIDATION only, and TEST is never used for fitting.
"""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pandas as pd

from ai.graph_intelligence.config import GraphIntelligenceConfig
from ai.graph_intelligence.data.builder import build_events
from ai.graph_intelligence.data.loader import load_edge_features
from ai.graph_intelligence.data.splits import assign_split, compute_boundaries

from .calibration import alert_rate, calibrate_threshold
from .features import build_context_features
from .scorers import GraphContextScorer

CACHE = Path(__file__).resolve().parent / "build"


def load_events(cfg: GraphIntelligenceConfig) -> pd.DataFrame:
    return build_events(cfg, load_edge_features(cfg))


def build_shadow_scores(cfg: GraphIntelligenceConfig, *, cache: bool = True):
    """Run Edge+Node shadow runtime once and return per-window scores (+local features)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    ep, npth = CACHE / "edge_scores.parquet", CACHE / "node_scores.parquet"
    if cache and ep.exists() and npth.exists():
        return pd.read_parquet(ep), pd.read_parquet(npth)
    from ai.edge_behavior.features.builder import load_asset_identity
    from ai.shadow.config import ShadowConfig
    from ai.shadow.inference.model_bundle import ShadowModelBundle
    from ai.shadow.inference.node_bundle import load_node_scorer
    from ai.shadow.runtime import ShadowRuntime
    from ai.shadow.sinks.memory import InMemoryShadowSink
    from ai.shadow.sources.list import ListObservationSource
    from ai.shadow.state.memory import InMemoryStateStore
    from src.config import get_settings
    from src.normalization import io
    from src.schemas.v2 import CommunicationObservation

    scfg = ShadowConfig(dataset_id=cfg.dataset_id, window_label=cfg.window_label)
    p = (get_settings().processed_dir / "v2" / "communication_observations"
         / f"{cfg.dataset_id}_obs_{cfg.window_label}.parquet")
    obs = io.frame_to_models(io.read_parquet(p), CommunicationObservation)
    im = load_asset_identity(cfg.dataset_id)
    sink = InMemoryShadowSink()
    ShadowRuntime(scfg, ListObservationSource(obs), sink, InMemoryStateStore(),
                  edge_bundle=ShadowModelBundle.load(scfg.model_bundle),
                  node_scorer=load_node_scorer(scfg.node_model_artifact, identity_map=im),
                  identity_map=im).run()
    edge = pd.DataFrame([{
        "relationship_id": r.feature_window.relationship_id,
        "window_start": r.feature_window.window_start,
        "edge_score": r.anomaly_result.anomaly_score,
        "new_peer": bool(r.feature_window.new_peer),
        "src_unique_peer_count": r.feature_window.src_unique_peer_count,
        "src_new_peer_count": r.feature_window.src_new_peer_count,
        "protocol_novelty_count": r.feature_window.protocol_novelty_count,
        "port_novelty_count": r.feature_window.port_novelty_count,
        "historical_connection_count": r.feature_window.historical_connection_count,
        "connections_count": r.feature_window.connections_count,
    } for r in sink.edge_records()])
    node = pd.DataFrame([{
        "asset_id": r.feature_window.asset_id,
        "window_start": r.feature_window.window_start,
        "node_score": r.anomaly_result.anomaly_score,
        "unique_outgoing_peers": r.feature_window.unique_outgoing_peers,
        "new_outgoing_peer_count": r.feature_window.new_outgoing_peer_count,
        "fan_out": r.feature_window.fan_out,
        "unique_incoming_peers": r.feature_window.unique_incoming_peers,
        "new_incoming_peer_count": r.feature_window.new_incoming_peer_count,
        "fan_in": r.feature_window.fan_in,
        "relationship_creation_count": r.feature_window.relationship_creation_count,
    } for r in sink.node_records()])
    if cache:
        edge.to_parquet(ep, index=False)
        node.to_parquet(npth, index=False)
    return edge, node


def context_for(cfg, events, lookback, hops):
    t0 = time.perf_counter()
    ctx = build_context_features(events, lookback_seconds=lookback, hops=hops)
    gen_s = time.perf_counter() - t0
    ctx["as_of"] = pd.to_datetime(ctx.window_start)
    return ctx, gen_s


def _stratified_alert_rate(ctx, threshold, mask):
    if mask.sum() == 0:
        return {"n": 0, "alert_rate": 0.0}
    return {"n": int(mask.sum()), "alert_rate": round(float((ctx.loc[mask, "graph_score"] >= threshold).mean()), 4)}


def run_normal_eval(cfg: GraphIntelligenceConfig | None = None) -> dict:
    cfg = cfg or GraphIntelligenceConfig()
    events = load_events(cfg)
    ctx, gen_s = context_for(cfg, events, cfg.lookback_seconds, cfg.hops)
    edge, node = build_shadow_scores(cfg)
    ctx["window_start"] = pd.to_datetime(ctx["window_start"])
    edge["window_start"] = pd.to_datetime(edge["window_start"])
    node["window_start"] = pd.to_datetime(node["window_start"])

    b = compute_boundaries(events.window_start.to_numpy(), cfg)
    ctx["split"] = [str(assign_split(t, b)) for t in ctx.as_of.to_numpy()]

    scorer = GraphContextScorer().fit(ctx[ctx.split == "train"])
    ctx["graph_score"] = scorer.score(ctx)

    val = ctx[ctx.split == "validation"]
    thr = calibrate_threshold(val.graph_score.to_numpy(), target_alert_rate=0.01)
    ctx["alert"] = ctx.graph_score >= thr
    test = ctx[ctx.split == "test"]

    days = float((events.window_end.max() - events.window_start.min()).total_seconds() / 86400)
    test_alerts = int(test.alert.sum())
    n_entities = ctx.src_asset_id.nunique()
    n_rel = ctx.relationship_id.nunique()

    edge_m = edge.merge(ctx[["relationship_id", "window_start", "dst_asset_id", "graph_score", "alert", "split",
                             "hub_involved", "src_degree_bucket", "dst_degree_bucket",
                             "target_structural_novelty"]],
                        on=["relationship_id", "window_start"], how="inner")
    edge_test = edge_m[edge_m.split == "test"]
    edge_thr = calibrate_threshold(edge_m[edge_m.split == "validation"].edge_score.to_numpy(), 0.01)
    edge_test_alerts = int((edge_test.edge_score >= edge_thr).sum())

    return {
        "shift_days": round(days, 3), "generation_seconds": round(gen_s, 2),
        "splits": {s: int((ctx.split == s).sum()) for s in ("train", "validation", "test")},
        "threshold": round(float(thr), 4),
        "test": {
            "n": int(len(test)),
            "alert_rate": round(alert_rate(test.graph_score.to_numpy(), thr), 4),
            "alerts": test_alerts,
            "alerts_per_site_per_day": round(test_alerts / max(days, 1e-9), 3),
            "alerts_per_entity_per_day": round(test_alerts / max(n_entities, 1) / max(days, 1e-9), 4),
            "alerts_per_relationship_per_day": round(test_alerts / max(n_rel, 1) / max(days, 1e-9), 4),
        },
        "edge_test_alert_rate": round(float((edge_test.edge_score >= edge_thr).mean()), 4),
        "edge_test_alerts": edge_test_alerts,
        "hub_strata": {
            "hub_involved": _stratified_alert_rate(ctx[ctx.split == "test"], thr, ctx[ctx.split == "test"].hub_involved),
            "non_hub": _stratified_alert_rate(ctx[ctx.split == "test"], thr, ~ctx[ctx.split == "test"].hub_involved),
        },
        "bucket_strata": {
            "src_hub": _stratified_alert_rate(ctx[ctx.split == "test"], thr, ctx[ctx.split == "test"].src_degree_bucket == "hub"),
            "src_low": _stratified_alert_rate(ctx[ctx.split == "test"], thr, ctx[ctx.split == "test"].src_degree_bucket == "low"),
            "dst_hub": _stratified_alert_rate(ctx[ctx.split == "test"], thr, ctx[ctx.split == "test"].dst_degree_bucket == "hub"),
            "dst_low": _stratified_alert_rate(ctx[ctx.split == "test"], thr, ctx[ctx.split == "test"].dst_degree_bucket == "low"),
        },
        "new_vs_known_edge_test": {
            "new_edge": _stratified_alert_rate(ctx[ctx.split == "test"], thr, ctx[ctx.split == "test"].target_structural_novelty == 1.0),
            "known_edge": _stratified_alert_rate(ctx[ctx.split == "test"], thr, ctx[ctx.split == "test"].target_structural_novelty == 0.0),
        },
        "scorer": scorer,
        "edge_merged": edge_m,
        "ctx": ctx,
    }


def complementarity(edge_merged: pd.DataFrame, node: pd.DataFrame, ctx: pd.DataFrame) -> dict:
    from scipy.stats import pearsonr, spearmanr
    te = edge_merged[edge_merged.split == "test"]
    e = te.edge_score.to_numpy()
    g = te.graph_score.to_numpy()
    pr = pearsonr(e, g) if len(e) > 2 else (0.0, 1.0)
    sr = spearmanr(e, g) if len(e) > 2 else (0.0, 1.0)
    # node vs graph by destination node score
    nkey = node.rename(columns={"asset_id": "dst_asset_id"})
    gn = te.merge(nkey[["dst_asset_id", "window_start", "node_score"]],
                  on=["dst_asset_id", "window_start"], how="inner")
    npr = nsr = (0.0, 1.0)
    if len(gn) > 2:
        npr = pearsonr(gn.node_score.to_numpy(), gn.graph_score.to_numpy())
        nsr = spearmanr(gn.node_score.to_numpy(), gn.graph_score.to_numpy())
    return {"edge_graph_pearson": round(float(pr[0]), 3), "edge_graph_spearman": round(float(sr[0]), 3),
            "node_graph_pearson": round(float(npr[0]), 3), "node_graph_spearman": round(float(nsr[0]), 3),
            "n_edge": int(len(e)), "n_node": int(len(gn))}


def quadrants(edge_merged: pd.DataFrame, edge_thr: float, graph_thr: float) -> dict:
    te = edge_merged[edge_merged.split == "test"]
    hi_e = te.edge_score >= edge_thr
    hi_g = te.graph_score >= graph_thr
    return {"both_high": int((hi_e & hi_g).sum()), "edge_high_graph_low": int((hi_e & ~hi_g).sum()),
            "edge_low_graph_high": int((~hi_e & hi_g).sum()), "both_low": int((~hi_e & ~hi_g).sum())}


def disagreement_examples(edge_merged: pd.DataFrame, edge_thr: float, graph_thr: float, k: int = 5) -> dict:
    te = edge_merged[edge_merged.split == "test"].copy()
    a = te[(te.edge_score >= edge_thr) & (te.graph_score < graph_thr)].nlargest(k, "edge_score")
    b = te[(te.edge_score < edge_thr) & (te.graph_score >= graph_thr)].nlargest(k, "graph_score")

    def rows(df):
        return [{"relationship_id": r.relationship_id, "window_start": str(r.window_start),
                 "edge_score": round(float(r.edge_score), 3), "graph_score": round(float(r.graph_score), 3),
                 "src_bucket": r.src_degree_bucket, "dst_bucket": r.dst_degree_bucket,
                 "new_structural_edge": bool(r.target_structural_novelty == 1.0)}
                for r in df.itertuples(index=False)]

    return {"edge_high_graph_low": rows(a), "edge_low_graph_high": rows(b)}


# --------------------------------------------------------------------- scenarios #
def _scenario_events(sc):
    rows = []
    for i, (u, v) in enumerate(sc.history):
        rows.append({"event_id": f"se:{i}", "relationship_id": f"srel:{u}:{v}",
                     "src_asset_id": u, "dst_asset_id": v,
                     "window_start": np.datetime64("2020-01-01T00:00:00") + np.timedelta64(i * 60, "s"),
                     "window_end": np.datetime64("2020-01-01T00:00:00") + np.timedelta64(i * 60 + 60, "s"),
                     "is_new_relationship": True, "new_peer": True})
    n = len(sc.history)
    rows.append({"event_id": "se:target", "relationship_id": "srel:target",
                 "src_asset_id": sc.target[0], "dst_asset_id": sc.target[1],
                 "window_start": np.datetime64("2020-01-01T00:00:00") + np.timedelta64(n * 60, "s"),
                 "window_end": np.datetime64("2020-01-01T00:00:00") + np.timedelta64(n * 60 + 60, "s"),
                 "is_new_relationship": True, "new_peer": True})
    return pd.DataFrame(rows), n


def scenario_context_scores(scorer: GraphContextScorer) -> dict:
    from ai.graph_intelligence.evaluation.scenarios import all_scenarios

    from .features import ContextExtractor
    out = {}
    for sc in all_scenarios():
        ev, target_idx = _scenario_events(sc)
        ex = ContextExtractor(ev, lookback_seconds=10 ** 9, hops=1)
        feat = ex.extract(target_idx)
        fdf = pd.DataFrame([feat])
        fam = scorer.family_scores(fdf)
        score = float(scorer.score(fdf)[0])
        out[sc.scenario_id] = {"structurally_unusual": sc.structurally_unusual,
                               "graph_context_score": round(score, 4),
                               "family_scores": {k: round(float(v[0]), 3) for k, v in fam.items()},
                               "neighborhood_size": int(feat["neighborhood_size"]),
                               "target_structural_novelty": float(feat["target_structural_novelty"]),
                               "causal_jaccard": round(float(feat["causal_jaccard"]), 4),
                               "edge_proxy_new_peer": 1.0}
    return out


# --------------------------------------------------------------------- ablations #
def run_ablation(cfg: GraphIntelligenceConfig | None = None, *, max_samples: int = 12000,
                 lookbacks=(300, 1800, 3600, 86400), hops=(1, 2)) -> dict:
    cfg = cfg or GraphIntelligenceConfig()
    events = load_events(cfg)
    b = compute_boundaries(events.window_start.to_numpy(), cfg)
    results = {}
    for lb in lookbacks:
        for hp in hops:
            stride = max(1, len(events) // max_samples)
            ctx = build_context_features(events, lookback_seconds=lb, hops=hp, stride=stride)
            ctx["as_of"] = pd.to_datetime(ctx.window_start)
            ctx["split"] = [str(assign_split(t, b)) for t in ctx.as_of.to_numpy()]
            scorer = GraphContextScorer().fit(ctx[ctx.split == "train"])
            ctx["graph_score"] = scorer.score(ctx)
            val = ctx[ctx.split == "validation"]
            thr = calibrate_threshold(val.graph_score.to_numpy(), 0.01)
            te = ctx[ctx.split == "test"]
            sc = scenario_context_scores(scorer)
            g06 = sc["SCN-G06_NORMAL_NEW_EDGE"]["graph_context_score"]
            g07 = sc["SCN-G07_UNUSUAL_EDGE"]["graph_context_score"]
            results[f"l{lb}_h{hp}"] = {
                "lookback_seconds": lb, "hops": hp, "n": int(len(ctx)),
                "neighborhood_size_p50": float(ctx.neighborhood_size.median()),
                "neighborhood_size_p95": float(ctx.neighborhood_size.quantile(0.95)),
                "test_alert_rate": round(alert_rate(te.graph_score.to_numpy(), thr), 4),
                "hub_alert_rate": _stratified_alert_rate(te, thr, te.hub_involved)["alert_rate"],
                "nonhub_alert_rate": _stratified_alert_rate(te, thr, ~te.hub_involved)["alert_rate"],
                "scenario_g06_plausible": g06, "scenario_g07_unusual": g07,
                "scenario_gap": round(g07 - g06, 4),
            }
    return results


# --------------------------------------------------------------------- performance #
def run_performance(cfg: GraphIntelligenceConfig | None = None, *, n_samples: int = 2000) -> dict:
    cfg = cfg or GraphIntelligenceConfig()
    events = load_events(cfg)
    from .features import ContextExtractor
    ex = ContextExtractor(events, lookback_seconds=cfg.lookback_seconds, hops=cfg.hops)
    step = max(1, len(events) // n_samples)
    idxs = list(range(0, len(events), step))[:n_samples]
    gen_ms = []
    for i in idxs:
        t0 = time.perf_counter()
        ex.extract(i)
        gen_ms.append((time.perf_counter() - t0) * 1000.0)
    ctx = build_context_features(events, lookback_seconds=cfg.lookback_seconds, hops=cfg.hops,
                                 max_samples=4000)
    scorer = GraphContextScorer().fit(ctx)
    t0 = time.perf_counter()
    scorer.score(ctx)
    score_ms = (time.perf_counter() - t0) * 1000.0 / max(len(ctx), 1)
    g = np.array(gen_ms)
    return {"feature_generation_ms": {"p50": round(float(np.percentile(g, 50)), 3),
                                      "p95": round(float(np.percentile(g, 95)), 3),
                                      "p99": round(float(np.percentile(g, 99)), 3),
                                      "mean": round(float(g.mean()), 3)},
            "scoring_ms_per_row": round(score_ms, 5),
            "n_measured": int(len(g))}
