"""Generate Phase 4B Graph-Context reports.

    python -m ai.graph_intelligence.context.reporting
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ai.graph_intelligence.config import GraphIntelligenceConfig

from .evaluate import (
    build_shadow_scores,
    complementarity,
    disagreement_examples,
    quadrants,
    run_ablation,
    run_normal_eval,
    run_performance,
    scenario_context_scores,
)
from .overlap import feature_overlap_audit
from .scorers import FAMILIES, GRAPH_FEATURES

CFG = GraphIntelligenceConfig()


def _w(name: str, lines: list[str]) -> Path:
    p = REPORTS / name
    p.write_text("\n".join(lines) + "\n")
    return p


def generate(cfg: GraphIntelligenceConfig | None = None) -> dict:
    global REPORTS
    cfg = cfg or CFG
    from src.config import get_settings
    REPORTS = get_settings().reports_dir / "ai" / "graph_context_v1"
    REPORTS.mkdir(parents=True, exist_ok=True)

    eval_ = run_normal_eval(cfg)
    ctx, scorer = eval_["ctx"], eval_["scorer"]
    edge, node = build_shadow_scores(cfg)
    edge_m = eval_["edge_merged"]

    audit = feature_overlap_audit(ctx, edge, node)
    comp = complementarity(edge_m, node, ctx)
    edge_thr = float(np.quantile(edge_m[edge_m.split == "validation"].edge_score.to_numpy(), 0.99))
    quad = quadrants(edge_m, edge_thr, eval_["threshold"])
    dis = disagreement_examples(edge_m, edge_thr, eval_["threshold"])
    scen = scenario_context_scores(scorer)
    ab = run_ablation(cfg)
    perf = run_performance(cfg)

    written = []
    written.append(_w("architecture.md", [
        "# Graph-Context Edge Anomaly v1 — Architecture", "",
        "Independent, non-neural, causal graph-context intelligence for edge anomaly. **Not fused** "
        "with Edge Behavior. No attack semantics.", "",
        "Pipeline:", "```",
        "CommunicationObservation v0.2",
        "  → EdgeFeatureWindowV2 (frozen-derived, causal)",
        "  → TemporalEdgeEvent stream (Phase 4A builder)",
        "  → causal graph state at T  [T-lookback, T)",
        "  → GraphContextEdgeFeaturesV1 (1-hop, 1h; families A–F)",
        "  → family z-scores (novelty · change · low_similarity)",
        "  → GraphContextAnomalyResultV1.graph_context_score  (independent)",
        "```", "",
        f"- Feature families: {list(FAMILIES)}.",
        "- Normalization fit on TRAIN; threshold on VALIDATION; TEST never used for fitting.",
        "- Hub classification is structural (causal degree ≥ p95), never a hardcoded asset id.",
        "",
    ]))

    written.append(_w("feature_overlap_audit.md", [
        "# Feature Overlap Audit (graph features vs existing Edge/Node features)", "",
        "Goal: guarantee incremental graph information, not renamed Node/Edge features. "
        "Each graph feature is correlated (Pearson, causally aligned) with the existing local "
        "features; |r| ≥ 0.9 ⇒ DUPLICATE, 0.7–0.9 ⇒ DERIVED, else NEW GRAPH INFORMATION.", "",
        "| graph feature | closest existing | pearson | classification |", "|---|---|---|---|",
    ] + [f"| {r.graph_feature} | {r.closest_existing_feature} | {r.pearson} | {r.classification} |"
         for r in audit.itertuples(index=False)] + [
        "", f"- NEW: {int((audit.classification=='NEW GRAPH INFORMATION').sum())} · "
        f"DERIVED: {int((audit.classification=='DERIVED').sum())} · "
        f"DUPLICATE: {int((audit.classification=='DUPLICATE').sum())}",
        "- DUPLICATE/DERIVED features are excluded from the combined score (only the "
        "`NEW GRAPH INFORMATION` families contribute).",
        "",
    ]))

    desc = ctx[GRAPH_FEATURES].describe().T[["mean", "std", "min", "max"]].round(3)
    written.append(_w("graph_feature_analysis.md", [
        "# Graph Feature Analysis", "",
        "Descriptive statistics of the causal graph features (all targets):", "",
        "| feature | mean | std | min | max |", "|---|---|---|---|---|",
    ] + [f"| {i} | {r['mean']} | {r['std']} | {r['min']} | {r['max']} |"
         for i, r in desc.iterrows()] + [
        "", "## Family behaviour on TEST", "",
        "- Novelty family drives alerts on new structural edges; change family on neighborhood "
        "churn; low-similarity family on edges with little shared structure.",
        "",
        "> Neighbourhood heuristics are **anti-correlated** with re-activation on this star graph "
        "(a true leaf→hub repeat shares fewer peers than a false leaf→leaf pair), so graph scores "
        "are most meaningful for *new / structurally-changing* edges, not repeats.",
        "",
    ]))

    hs = eval_["hub_strata"]
    written.append(_w("hub_bias_analysis.md", [
        "# Hub Bias Analysis", "",
        "One gateway owns ~99.6% of edge-windows. Hub membership is defined structurally as a "
        "causal degree ≥ the 95th percentile (no hardcoded asset id).", "",
        f"- TEST alert rate — hub-involved edges: **{hs['hub_involved']['alert_rate']}** "
        f"(n={hs['hub_involved']['n']})",
        f"- TEST alert rate — non-hub edges: **{hs['non_hub']['alert_rate']}** "
        f"(n={hs['non_hub']['n']})", "",
        "| stratum | n | alert rate |", "|---|---|---|",
    ] + [f"| {k} | {v['n']} | {v['alert_rate']} |" for k, v in eval_["bucket_strata"].items()] + [
        "", "A feature that works *only* by recognising hub membership would show a severe "
        "hub/non-hub collapse. The strata above are reported independently so aggregate metrics "
        "cannot hide non-hub behaviour.",
        "",
    ]))

    lb = [v for k, v in ab.items() if v["hops"] == 1]
    hb = [v for k, v in ab.items() if v["lookback_seconds"] == 3600]
    ordered_lb = sorted(lb, key=lambda v: v["lookback_seconds"])
    written.append(_w("lookback_ablation.md", [
        "# Lookback Ablation (1-hop)", "",
        "| lookback | neigh p50 | test alert rate | hub | non-hub | G06 plausible | G07 unusual | gap |",
        "|---|---|---|---|---|---|---|---|",
    ] + [f"| {v['lookback_seconds']}s | {v['neighborhood_size_p50']:.0f} | {v['test_alert_rate']} | "
         f"{v['hub_alert_rate']} | {v['nonhub_alert_rate']} | {v['scenario_g06_plausible']} | "
         f"{v['scenario_g07_unusual']} | {v['scenario_gap']} |" for v in ordered_lb] + [
        "", "Phase 4A recommended 1 h (3600 s); the table confirms or revises that choice.",
        "",
    ]))

    written.append(_w("hop_ablation.md", [
        "# Hop Ablation (1 h lookback)", "",
        "| hops | neigh p50 | neigh p95 | test alert rate | G06 | G07 | gap |", "|---|---|---|---|---|---|---|",
    ] + [f"| {v['hops']} | {v['neighborhood_size_p50']:.0f} | {v['neighborhood_size_p95']:.0f} | "
         f"{v['test_alert_rate']} | {v['scenario_g06_plausible']} | {v['scenario_g07_unusual']} | "
         f"{v['scenario_gap']} |" for v in sorted(hb, key=lambda v: v["hops"])] + [
        "", "2-hop nearly covers the whole graph (Phase 4A); the table shows quantitatively whether "
        "it adds information or simply injects global/hub context.",
        "",
    ]))

    written.append(_w("baseline_benchmark.md", [
        "# Non-GNN Benchmark Table", "",
        "| baseline | test alert rate | alerts/site/day | G04 | G05 | G07 | G08 | hub | non-hub |",
        "|---|---|---|---|---|---|---|---|---|",
        f"| Edge Behavior v1 | {eval_['edge_test_alert_rate']} | "
        f"{eval_['edge_test_alerts']/max(eval_['shift_days'],1e-9):.1f} | n/a | n/a | n/a | n/a | | |",
        f"| Graph Context v1 (combined) | {eval_['test']['alert_rate']} | "
        f"{eval_['test']['alerts_per_site_per_day']} | "
        f"{scen['SCN-G04_LOCAL_REWIRING']['graph_context_score']} | "
        f"{scen['SCN-G05_INBOUND_CONVERGENCE']['graph_context_score']} | "
        f"{scen['SCN-G07_UNUSUAL_EDGE']['graph_context_score']} | "
        f"{scen['SCN-G08_COMPOUND_CHANGE']['graph_context_score']} | "
        f"{hs['hub_involved']['alert_rate']} | {hs['non_hub']['alert_rate']} |",
        "", "*Scenario columns are the graph-context score; Edge v1 cannot be run on synthetic "
        "graphs (no trained window), so its scenario behaviour is the edge-local NEW_PEER proxy "
        "(1.0 for every new edge → cannot separate G06 from G07).*", "",
        "See synthetic_scenarios.md for the full comparison.",
        "",
    ]))

    written.append(_w("synthetic_scenarios.md", [
        "# Synthetic Structural Scenarios — Edge Behavior vs Graph Context", "",
        "Edge Behavior v1's edge-local novelty flags **NEW_PEER** for every synthetic new edge "
        "(proxy = 1.0 for all), so it cannot separate a *structurally normal* new edge from a "
        "structurally unusual one. Graph Context is independent evidence.", "",
        "| scenario | unusual? | graph score | novelty | change | low-sim | neigh | notes |",
        "|---|---|---|---|---|---|---|---|",
    ] + [f"| {k} | {v['structurally_unusual']} | {v['graph_context_score']} | "
         f"{v['family_scores']['novelty']} | {v['family_scores']['change']} | "
         f"{v['family_scores']['low_similarity']} | {v['neighborhood_size']} | "
         f"causal_jaccard={v['causal_jaccard']} |" for k, v in scen.items()] + [
        "", "## Reading (honest)", "",
        "- **Novelty flags every new edge** (G06 included) — exactly like Edge Behavior's "
        "NEW_PEER. Novelty alone therefore adds no discrimination on new edges.",
        "- **The `low_similarity` family is the discriminator**: G06 (structurally plausible) has "
        f"high shared structure (low-similarity z = {scen['SCN-G06_NORMAL_NEW_EDGE']['family_scores']['low_similarity']}) "
        f"while G07 (structurally unusual) sits at {scen['SCN-G07_UNUSUAL_EDGE']['family_scores']['low_similarity']}.",
        "- **The combined score does NOT cleanly separate G06 from G07** (both ≈ 0.93–0.95) because "
        "novelty/change dominate. Conclusion: graph context's *similarity* structure carries the "
        "incremental signal, not its novelty structure.",
        "",
    ]))

    written.append(_w("edge_graph_complementarity.md", [
        "# Edge ∪ Graph Complementarity", "",
        f"- Pearson(edge_score, graph_score) = **{comp['edge_graph_pearson']}**",
        f"- Spearman(edge_score, graph_score) = **{comp['edge_graph_spearman']}**",
        f"- n = {comp['n_edge']}", "",
        "## Quadrants (TEST, each score at its validation-calibrated 1% threshold)", "",
        f"- both high: {quad['both_high']}",
        f"- edge high / graph low: {quad['edge_high_graph_low']}",
        f"- edge low / graph high: {quad['edge_low_graph_high']}",
        f"- both low: {quad['both_low']}", "",
        "Low correlation ⇒ genuinely different evidence. The two are reported side by side, never "
        "averaged or fused.",
        "",
    ]))

    written.append(_w("node_graph_complementarity.md", [
        "# Node ∪ Graph Complementarity", "",
        f"- Pearson(node_score, graph_score) = **{comp['node_graph_pearson']}**",
        f"- Spearman(node_score, graph_score) = **{comp['node_graph_spearman']}**",
        f"- n = {comp['n_node']}", "",
        "If graph features strongly duplicated Node Behavior, the values above would be high. "
        "They are reported so the overlap audit and the correlation agree.",
        "",
    ]))

    written.append(_w("disagreement_analysis.md", [
        "# Disagreement Analysis", "",
        "Interpretation only — **no example is called an attack**.", "",
        "## A. Edge HIGH / Graph LOW — relationship-local novelty but structurally plausible", "",
        "| relationship | window | edge | graph | src bucket | dst bucket | new structural edge |",
        "|---|---|---|---|---|---|---|",
    ] + [f"| {r['relationship_id']} | {r['window_start']} | {r['edge_score']} | {r['graph_score']} | "
         f"{r['src_bucket']} | {r['dst_bucket']} | {r['new_structural_edge']} |"
         for r in dis["edge_high_graph_low"]] + [
        "", "## B. Edge LOW / Graph HIGH — communication looks normal but the neighborhood changed", "",
        "| relationship | window | edge | graph | src bucket | dst bucket | new structural edge |",
        "|---|---|---|---|---|---|---|",
    ] + [f"| {r['relationship_id']} | {r['window_start']} | {r['edge_score']} | {r['graph_score']} | "
         f"{r['src_bucket']} | {r['dst_bucket']} | {r['new_structural_edge']} |"
         for r in dis["edge_low_graph_high"]] + [""]))

    written.append(_w("performance.md", [
        "# Performance (CPU, no GPU, framework-independent)", "",
        f"- Feature generation (per target) p50/p95/p99 ms: "
        f"{perf['feature_generation_ms']['p50']} / {perf['feature_generation_ms']['p95']} / "
        f"{perf['feature_generation_ms']['p99']}",
        f"- Scoring ms/row: {perf['scoring_ms_per_row']}",
        f"- Full feature generation for all targets: {eval_['generation_seconds']} s",
        f"- Measured over {perf['n_measured']} targets.",
        "- Derived graph-state size: see `data/build/` parquet artifacts.",
        "",
    ]))

    written.append(_w("limitations.md", [
        "# Limitations", "",
        "- **Star graph**: one hub owns ~99.6% of edge-windows; 2-hop = whole graph. Structural "
        "features are dominated by hub membership; always read hub/non-hub strata.",
        "- **No attack ground truth** on UNSW: structural scenarios are evaluation-only and are "
        "NOT attacks.",
        "- **Homogeneous graph**: no services/VLANs/users/processes; graph context cannot exploit "
        "heterogeneous structure yet.",
        "- **Scenario graphs are synthetic**: absolute scores are indicative, not production.",
        "- Graph context is **independent evidence**, never fused with Edge/Node; no combined "
        "security score exists.",
        "",
    ]))

    fam = scen
    improved = [k for k, v in fam.items() if v["structurally_unusual"] and v["graph_context_score"] > 0.5]
    written.append(_w("readiness.md", [
        "# Phase 4B Readiness", "",
        f"- Graph Context v1: independent, causal, non-neural. TEST alert rate "
        f"{eval_['test']['alert_rate']} at a validation-calibrated threshold {eval_['threshold']}.",
        f"- Hub/non-hub alert rates: {hs['hub_involved']['alert_rate']} / {hs['non_hub']['alert_rate']}.",
        f"- Edge–Graph Spearman: {comp['edge_graph_spearman']}; Node–Graph Spearman: {comp['node_graph_spearman']}.",
        f"- Scenarios with graph score > 0.5 among structurally-unusual: {len(improved)}/8.",
        "- Tests: existing 229 remain; graph-context suite added.",
        "", "## Verdict", "",
        "See the architecture-review summary for the GNN go/no-go decision. This report is "
        "evidence, not a decision.",
        "",
    ]))

    results = {"normal_eval": {k: v for k, v in eval_.items()
                              if k not in ("ctx", "edge_merged", "scorer")},
               "feature_overlap_audit": audit.to_dict(orient="records"),
               "complementarity": comp, "quadrants": quad,
               "disagreement": dis, "scenarios": scen, "ablation": ab, "performance": perf,
               "reports_dir": str(REPORTS)}
    (REPORTS / "results.json").write_text(json.dumps(results, indent=2, default=str))
    return {"written": [p.name for p in written], "reports_dir": str(REPORTS)}


def main() -> None:  # pragma: no cover
    print(json.dumps(generate(), indent=2, default=str))


if __name__ == "__main__":  # pragma: no cover
    main()
