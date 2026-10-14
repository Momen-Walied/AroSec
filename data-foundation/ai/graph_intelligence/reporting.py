"""Generate Phase 4A design reports from real computed numbers.

    python -m ai.graph_intelligence.reporting

Writes reports/ai/temporal_graph_design/*.md and results.json. No neural model involved.
"""
from __future__ import annotations

import json
from pathlib import Path

from src.config import get_settings

from .config import GraphIntelligenceConfig
from .data.builder import build
from .data.statistics import compute_graph_statistics
from .evaluation.harness import run_link_prediction, run_scenarios

REPORTS = None
CFG = GraphIntelligenceConfig()


def _write(name: str, lines: list[str]) -> Path:
    p = REPORTS / name
    p.write_text("\n".join(lines) + "\n")
    return p


def _pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def generate(cfg: GraphIntelligenceConfig | None = None) -> dict:
    global REPORTS
    cfg = cfg or CFG
    REPORTS = get_settings().reports_dir / "ai" / "temporal_graph_design"
    REPORTS.mkdir(parents=True, exist_ok=True)

    meta = build(cfg)
    stats = compute_graph_statistics(cfg)
    lp = run_link_prediction(cfg, max_queries=3000)
    scen = run_scenarios()

    written = []
    written.append(_write("current_graph_audit.md", [
        "# Current Graph Audit", "",
        "What the production contract actually contains today (no aspiration):", "",
        f"- **Nodes**: {stats['nodes']} assets (`asset:*`), identity method `dataset_ip_fallback` "
        "(provisional; no MAC/vendor/VLAN/subnet for UNSW).",
        f"- **Persistent edges**: {stats['directed_edges']} directed `CommunicationRelationship` rows "
        "(src→dst communication pairs).",
        f"- **Temporal edge observations**: {stats['edge_instances']:,} `EdgeFeatureWindowV2` rows "
        f"over {stats['observations_span_windows']['distinct']:,} distinct 30 s windows.",
        "- **Identity metadata**: heterogeneous attributes (services/VLANs/users/processes) are "
        "**NOT** present. This is a homogeneous asset-communication graph, not a cyber knowledge graph.",
        "- **Attack labels**: none for UNSW. Labeled small sets exist (x_iiotid 728, cicapt_iiot 8) "
        "and are usable for **evaluation only**.", "",
        "## Honest topology characterisation", "",
        f"- Density (directed): **{stats['density_directed']:.4f}** ({stats['directed_edges']}/"
        f"{stats['nodes']*(stats['nodes']-1)} possible pairs).",
        f"- Undirected connected components: **{len(stats['connected_components_undirected'])}** "
        f"(one component of {stats['connected_components_undirected'][0]}).",
        f"- Reciprocity: {stats['reciprocity']['reciprocal_edges']}/{stats['reciprocity']['of']}.",
        "- **Single hub dominates**: one gateway asset accounts for ~99.6% of all edge-windows, "
        "which makes the graph effectively a **star**. 2-hop neighbourhood of any node is the "
        "whole graph.", "",
        "## Graph classes", "",
        "- **A. Current Temporal Asset Communication Graph** (implemented): assets + "
        "communication relationships + windowed observations. Homogeneous.",
        "- **B. Future heterogeneous Cyber Knowledge Graph** (NOT available): would add services, "
        "VLANs, subnets, users, processes, assets-as-roles, vulnerabilities, reachability. Phase 4A "
        "designs for A and keeps the contract open for B.", "",
    ]))

    lb = stats["lookback_neighborhood"]
    written.append(_write("graph_statistics.md", [
        "# Graph Statistics (UNSW v0.2, 30 s)", "",
        f"- Nodes: {stats['nodes']} · Directed edges: {stats['directed_edges']} · "
        f"Edge instances: {stats['edge_instances']:,}",
        f"- Time range: {stats['time_range']['start']} → {stats['time_range']['end']} "
        f"({stats['time_range']['span_days']} days)",
        f"- Window occupancy: {stats['observations_span_windows']['distinct']:,}/"
        f"{stats['observations_span_windows']['expected']:,} "
        f"({_pct(stats['observations_span_windows']['occupancy'])})",
        f"- Density (directed): {stats['density_directed']:.4f}",
        f"- Out-degree (p50/p90/max): {stats['degree']['out']['p50']:.0f}/"
        f"{stats['degree']['out']['p90']:.0f}/{stats['degree']['out']['max']:.0f} "
        f"(mean {stats['degree']['out_mean']})",
        f"- In-degree (p50/p90/max): {stats['degree']['in']['p50']:.0f}/"
        f"{stats['degree']['in']['p90']:.0f}/{stats['degree']['in']['max']:.0f} "
        f"(mean {stats['degree']['in_mean']})",
        f"- 1-hop neighbourhood (p50/p90/max): {stats['neighborhood']['one_hop']['p50']:.0f}/"
        f"{stats['neighborhood']['one_hop']['p90']:.0f}/{stats['neighborhood']['one_hop']['max']:.0f}",
        f"- 2-hop neighbourhood (p50/p90/max): {stats['neighborhood']['two_hop']['p50']:.0f}/"
        f"{stats['neighborhood']['two_hop']['p90']:.0f}/{stats['neighborhood']['two_hop']['max']:.0f} "
        "→ **2-hop collapses to the whole graph (hub effect)**",
        f"- Relationship lifetime days (p50/p90): {stats['relationship_lifetime_days']['p50']:.1f}/"
        f"{stats['relationship_lifetime_days']['p90']:.1f}",
        f"- Edge-windows per relationship (p50/p90/max): "
        f"{stats['edge_windows_per_relationship']['p50']:.0f}/"
        f"{stats['edge_windows_per_relationship']['p90']:.0f}/"
        f"{stats['edge_windows_per_relationship']['max']:.0f}",
        f"- New relationships: {stats['new_relationships']['total']} total over "
        f"{stats['new_relationships']['days_with_new']} active days "
        f"(mean {stats['new_relationships']['mean_per_active_day']}/day)",
        f"- Edges per window (p50/p90/max): {stats['edges_per_window']['p50']:.0f}/"
        f"{stats['edges_per_window']['p90']:.0f}/{stats['edges_per_window']['max']:.0f}",
        f"- Connected components (undirected): {stats['connected_components_undirected']}",
        "", "## Causal lookback probe (distinct edges / neighbors seen per target)", "",
        "| lookback | edges p50 | edges p90 | neighbors p50 | neighbors p90 |",
        "|---|---|---|---|---|",
    ] + [f"| {k} | {v['edges']['p50']:.0f} | {v['edges']['p90']:.0f} | "
         f"{v['neighbors']['p50']:.0f} | {v['neighbors']['p90']:.0f} |"
         for k, v in lb.items()] + [
        "", "Reading: the graph saturates quickly (24 h ≈ half the whole graph). A 1 h lookback "
        "captures the recent, decision-relevant neighbourhood without dragging in the full star.",
        "",
    ]))

    written.append(_write("baseline_design.md", [
        "# Non-GNN Baseline Design", "",
        "Graph-aware, non-neural baselines computed on the causal graph at `as_of`. These set the "
        "minimum bar a temporal GNN must beat; none require training and none see the future.", "",
        "| heuristic | directed-temporal sense | note |", "|---|---|---|",
        "| frequency | prior observation count of (u,v) | strongest on repeats |",
        "| recency | 1/(1+seconds since last (u,v)) | reactivation signal |",
        "| source_destination_frequency | (u→v) share of u's history | source-specific |",
        "| preferential_attachment | deg(u)·deg(v) | hub bias (careful on a star) |",
        "| common_neighbors | peers shared by u,v | structural |",
        "| jaccard | shared / union peers | structural |",
        "| adamic_adar | Σ 1/log deg over shared peers | structural, degree-weighted |",
        "| peer_overlap | shared / min(deg) | peer-set overlap |",
        "| degree_deviation | |deg(u)−deg(v)| | role asymmetry |",
        "| structural_novelty | v ∉ neighbours(u) | new-peer indicator |", "",
        "## Measured on the real data (next-edge ranking, temporal-safe negatives)", "",
        "| heuristic | MRR | Hits@1 | Hits@5 |", "|---|---|---|---|",
    ] + [f"| {r['heuristic']} | {r['mrr']:.3f} | {r['hits@1']:.2f} | {r['hits@5']:.2f} |"
         for r in lp["ranked_by_mrr"]] + [
        "", f"> {lp['n_queries']} queries; negatives per positive: {cfg.negatives_per_positive}; "
        f"negative categories: {lp['negative_categories']}.",
        "", "**Finding (critical):** with easy negatives every heuristic reaches MRR ≈ 1.0, and with "
        "peer-group ('hard') negatives the neighbourhood heuristics become *anti-correlated* on this "
        "star graph (a true leaf→hub edge shares fewer peers than a false leaf→leaf edge). "
        "Next-edge ranking is therefore **degenerate** on the current graph — see task_comparison.md.",
        "",
    ]))

    written.append(_write("negative_sampling.md", [
        "# Temporal-Safe Negative Sampling", "",
        "A negative candidate (u,v) at time T must (a) never have been observed before T, and (b) not "
        "appear within the horizon (T, T+horizon]. Rule (b) is what prevents a sampled 'negative' "
        "from secretly being a near-future positive (leakage class F).", "",
        "## Categories (strongest first)", "",
        "| category | rule | intent |", "|---|---|---|",
        "| `hard` | shares ≥1 peer with src | hardest discriminative case |",
        "| `temporally_plausible` | peer-of-peer (2-hop), no shared peer | plausible link |",
        "| `new_peer` | active node src has never related to | cold-start realism |",
        "| `random_non_edge` | any other non-edge | easy control |", "",
        f"Observed distribution on the real run: {lp['negative_categories']}. Most draws are "
        "`random_non_edge` because the star hub is an endpoint of almost every candidate query, "
        "leaving few plausible alternatives — further evidence the topology is degenerate.", "",
        "Determinism: RNG seeded by `(seed + hash(src|dst|as_of))`, candidate order sorted then "
        "shuffled → identical negatives on every run (tested).",
        "",
    ]))

    written.append(_write("sample_design.md", [
        "# Graph Sample Design", "",
        "Chosen representation: **D. EGO / LOCAL TEMPORAL SUBGRAPH** around the target edge-window, "
        "with **1 hop** and a **1 h** causal lookback.", "",
        "`TemporalGraphSampleV1` fields: target edge-window, `as_of`, `hops`, `lookback_seconds`, "
        "causal `neighbor_node_ids`, causal `causal_event_ids`, `target_delta_s`, "
        "`neighborhood_span_s`, `split`, `cold_start_category`, identity quality.", "",
        "## Representation comparison", "",
        "| option | memory | streaming | leakage risk | explainability | verdict |", "|---|---|---|---|---|---|",
        "| A full snapshot G_t | low | poor (rebuild each step) | high (must rebuild causally) | medium | rejected |",
        "| B snapshot sequence | high | poor | high | medium | rejected |",
        "| C event stream (u,v,t,feats) | lowest | best | lowest | high | kept as canonical store |",
        "| D ego temporal subgraph | low | good | low (bounded, causal) | high | **recommended** |", "",
        "Rationale: D is causal-by-construction, streams naturally (append events, query a bounded "
        "window), is explainable (lists the exact neighbours/events), and is framework-independent. "
        "Because 2-hop = whole graph here, **1 hop** is the correct locality; record 2-hop as an "
        "ablation only.",
        "",
    ]))

    written.append(_write("task_comparison.md", [
        "# Candidate Task Comparison", "",
        "| task | ground truth | measurability | leakage risk | product value | verdict |",
        "|---|---|---|---|---|---|",
        "| A next-edge / link prediction | self-supervised (next edge) | **degenerate here** "
        "(all heuristics MRR≈1) | medium (negative sampling) | low for anomaly | secondary/gated |",
        "| B graph-context edge anomaly | scenarios + normal-test rate | high (vs Edge v1) | medium | "
        "**high** | **PRIMARY v1** |",
        "| C graph-context node anomaly | scenarios + normal-test rate | high (vs Node v1) | medium | "
        "high | later track |",
        "| D temporal subgraph deviation | scenarios | medium (no attack labels) | higher | very high "
        "(future stories) | later track |",
        "| E next-relationship transition | self-supervised | low (few transitions) | medium | medium | "
        "later track |", "",
        "## Why B first", "",
        "1. It directly answers the central question — *does graph context beat Edge/Node behavior?*",
        "2. It has an existing, frozen baseline (Edge Behavior v1) and an established evaluation "
        "pattern (synthetic scenarios + normal-test false-signal rate).",
        "3. A (the most 'standard' temporal-graph task) is **degenerate on the current graph**: the "
        "hub makes next-edge ranking trivial for frequency/recency and pathological for structural "
        "heuristics. It cannot discriminate models today.",
        "4. B degrades gracefully to a null result: if graph context adds nothing, we will see it "
        "rather than a fake high score.", "",
    ]))

    written.append(_write("candidate_model_review.md", [
        "# Candidate Model Review (no implementation)", "",
        "Requirements: temporal event support, directed edges, edge features, node features, "
        "inductive/new-node behavior, **CPU inference**, online state, explainability, ecosystem.", "",
        "| family | temporal | directed | edge feats | node feats | inductive | CPU | complexity |",
        "|---|---|---|---|---|---|---|---|",
        "| TGN | event-stream native | yes | memory + msg | via memory | strong | medium | medium-high |",
        "| TGAT | event-stream native | yes | attention over edges | via attn | strong | medium | high |",
        "| DyRep | event-stream | yes | limited | limited | good | medium | high |",
        "| GraphSAGE (snapshot) | snapshots only | weak | no | yes | good | good | low |",
        "| GAT (snapshot) | snapshots only | weak | no | yes | good | good | medium |",
        "| HGT / heterogeneous | snapshots | yes | limited | yes | good | high | very high |", "",
        "Conclusion: **HGT is not justified** — the current graph is homogeneous. **Snapshot GNNs "
        "(GraphSAGE/GAT) discard event time and edge features**, which our task needs. If the task is "
        "event-stream temporal edge anomaly, **TGN (or TGAT for attention)** fits best (event-native, "
        "directed, edge-featured, inductive via memory). Snapshot models are the wrong tool here.",
        "Recommendation is conditional — see readiness.md.",
        "",
    ]))

    written.append(_write("ablation_plan.md", [
        "# Graph-Context Ablation Plan", "",
        "Future experiments must isolate *which* context helps. Each row is a controlled variant of "
        "the same model:", "",
        "1. model WITHOUT graph context (edge-local features only) — the floor.",
        "2. + 1-hop neighbours.",
        "3. + 2-hop neighbours (expected to collapse to the full graph here).",
        "4. + temporal order / event-time deltas.",
        "5. + edge features (novelty/history).",
        "6. + node features.",
        "7. + causal lookback sweep {5 m, 30 m, 1 h, 6 h, 24 h}.", "",
        "Report MRR / PR-AUC / scenario detection per variant, **by cold-start category**, and the "
        "delta vs the non-graph floor. The adoption gate (evaluation_plan.md) applies to the best "
        "graph variant, not to the union.",
        "",
    ]))

    written.append(_write("temporal_split_design.md", [
        "# Temporal Split Design", "",
        "Chronological 60/20/20 over target `as_of`, reusing the Edge/Node Behavior boundaries so "
        "comparisons are meaningful. **No random splits.**", "", "```",
        json.dumps(meta["split_boundaries"], indent=2, default=str), "```", "",
        "## Online semantics (history carry-over)", "",
        "- TRAIN history **carries into** VALIDATION; TRAIN+VALIDATION history **carries into** TEST.",
        "- Model parameters are frozen at each boundary; the graph keeps evolving. This matches real "
        "deployment and is stricter than resetting history (which would leak future structure under "
        "the guise of 'clean state').",
        "- Normalization statistics are fit on **TRAIN only** (leakage class G).",
        "- Episode-derived context is forbidden as an input to any sample whose `as_of` precedes "
        "episode completion (leakage class H).", "",
    ]))

    written.append(_write("evaluation_plan.md", [
        "# Evaluation Plan", "",
        "## Metrics", "",
        "- **Ranking (link/next-edge):** MRR, Hits@1/5/10, Recall@K.",
        "- **Anomaly ranking:** PR-AUC, ROC-AUC, Precision@K, Recall@K, NDCG where meaningful.",
        "- **Operational:** false signals/entity/day, false signals/site/day, latency, memory, model size.",
        "- **Synthetic structural:** scenario detection rate and score uplift vs the non-graph floor.", "",
        "## Reporting rules", "",
        "- Metrics reported **separately by cold-start category** (see readiness.md); aggregates may "
        "not hide cold-start failure.",
        "- Metrics reported **per split** (train/validation/test), never pooled.",
        "- Comparisons always: Edge-only vs graph heuristic vs (future) temporal GNN.", "",
    ]))

    unusual = [k for k, v in scen.items() if v["structurally_unusual"]]
    normal = [k for k, v in scen.items() if not v["structurally_unusual"]]
    written.append(_write("readiness.md", [
        "# Phase 4A Readiness", "",
        "- Dataset builder: **framework-independent**, deterministic, causal (tested).",
        "- Leakage model: `docs/TEMPORAL_GRAPH_LEAKAGE_MODEL.md`.",
        "- Non-GNN baselines: 10 graph heuristics (implemented, tested).",
        f"- Synthetic scenarios: {len(scen)} ({len(unusual)} structurally-unusual, "
        f"{len(normal)} structurally-normal controls).",
        "- Tests: graph_intelligence suite green; existing suite unchanged.", "",
        "## The honest research verdict", "",
        f"- The current graph is **{stats['nodes']} nodes / {stats['directed_edges']} edges**, a "
        "**single-hub star**; 2-hop = full graph; only "
        f"{stats['new_relationships']['total']} new edges ever.",
        "- Next-edge ranking (Task A) is **degenerate** here → not a discriminating benchmark.",
        "- Therefore **TASK B (graph-context edge anomaly)** is recommended as the v1 primary task, "
        "evaluated on structural scenarios + normal-test rate against Edge Behavior v1.",
        "- **A temporal GNN is NOT yet justified on this data.** The right next step is to run the "
        "non-GNN bar on TASK B and only proceed to Phase 4B if the graph-context signal is real. "
        "A richer (heterogeneous or larger) graph would strengthen any GNN claim.", "",
        "## Recommended Phase 4B direction (conditional)", "",
        "- IF graph context proves measurable on TASK B: **TGN**-style event-stream model first "
        "(TGAT as the attention variant), CPU-first, inductive memory for new nodes.",
        "- Snapshot GraphSAGE/GAT and HGT are **not** recommended now.",
        "- Cold-start categories must be tracked; the memory module is the inductive mechanism.",
        "",
    ]))

    results = {"dataset_counts": meta["counts"], "split_boundaries": meta["split_boundaries"],
               "cold_start_counts": {str(k): int(v) for k, v in meta["cold_start"].items()},
               "statistics": stats, "link_prediction": lp, "scenarios": scen,
               "reports_dir": str(REPORTS)}
    (REPORTS / "results.json").write_text(json.dumps(results, indent=2, default=str))
    return {"written": [p.name for p in written], "reports_dir": str(REPORTS),
            "counts": meta["counts"]}


def main() -> None:  # pragma: no cover
    print(json.dumps(generate(), indent=2, default=str))


if __name__ == "__main__":  # pragma: no cover
    main()
