"""Interpretable, non-neural graph-context scorers.

Each feature family is scored on its own first; a combined ``graph_context_score`` is a
transparent mean of family z-scores mapped to [0,1]. Higher = more structurally unusual.
No neural network, no arbitrary giant weighted formula.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# feature families; sign = +1 means a HIGH value is structurally anomalous
FAMILIES: dict[str, list[tuple[str, int]]] = {
    "novelty": [("target_structural_novelty", 1), ("source_peer_set_novelty", 1),
                ("destination_peer_set_novelty", 1)],
    "change": [("source_neighbor_set_change", 1), ("destination_neighbor_set_change", 1),
               ("local_degree_change_rate", 1), ("local_new_edge_rate", 1)],
    "low_similarity": [("source_neighbor_similarity", -1), ("destination_neighbor_similarity", -1),
                       ("causal_jaccard", -1), ("causal_adamic_adar", -1)],
}

REASON_CODES = {
    "novelty": "GRAPH_PEER_NOVELTY",
    "change": "GRAPH_NEIGHBORHOOD_CHANGE",
    "low_similarity": "GRAPH_LOW_STRUCTURAL_SIMILARITY",
}

GRAPH_FEATURES = [f for fam in FAMILIES.values() for f, _ in fam]
DUPLICATE_RISK_FEATURES = ["source_out_degree_recent", "destination_in_degree_recent",
                           "source_new_out_neighbors_recent", "destination_new_in_neighbors_recent"]


@dataclass
class GraphContextScorer:
    mean_: dict[str, float] = field(default_factory=dict)
    std_: dict[str, float] = field(default_factory=dict)
    fitted: bool = False

    def fit(self, features) -> GraphContextScorer:
        for f in GRAPH_FEATURES:
            v = features[f].to_numpy(dtype=float)
            self.mean_[f] = float(v.mean())
            s = float(v.std())
            self.std_[f] = s if s > 1e-12 else 1.0
        self.fitted = True
        return self

    def _z(self, features, f: str) -> np.ndarray:
        v = features[f].to_numpy(dtype=float)
        return (v - self.mean_[f]) / self.std_[f]

    def family_scores(self, features) -> dict[str, np.ndarray]:
        if not self.fitted:
            raise RuntimeError("scorer not fitted")
        out = {}
        for fam, members in FAMILIES.items():
            out[fam] = np.mean([sign * self._z(features, f) for f, sign in members], axis=0)
        return out

    def score(self, features) -> np.ndarray:
        fam = self.family_scores(features)
        combined = np.mean(list(fam.values()), axis=0)
        return 1.0 / (1.0 + np.exp(-combined))  # logistic -> [0,1]

    def explain(self, features, i: int) -> dict:
        fam = self.family_scores(features)
        contrib = {k: float(v[i]) for k, v in fam.items()}
        codes = [REASON_CODES[k] for k, v in sorted(contrib.items(), key=lambda kv: kv[1], reverse=True)
                 if v > 0.5]
        return {"reason_codes": codes, "feature_contributions": contrib}


def scenario_score_from_features(f: dict, scorer: GraphContextScorer) -> float:
    """Score a single feature dict (e.g. a synthetic scenario target)."""
    import pandas as pd
    return float(scorer.score(pd.DataFrame([f]))[0])
