"""Ranking / detection metrics for Temporal Graph Intelligence v1."""
from __future__ import annotations

import numpy as np

try:  # metrics only; no model dependency
    from sklearn.metrics import average_precision_score, roc_auc_score
except Exception:  # pragma: no cover
    average_precision_score = None
    roc_auc_score = None


def _rank_of_positive(scores: np.ndarray, pos_index: int) -> int:
    """1-based rank of the positive when scores are sorted descending (ties: optimistic order)."""
    s = np.asarray(scores, dtype=float)
    order = np.argsort(-s, kind="mergesort")
    return int(np.nonzero(order == pos_index)[0][0]) + 1


def mrr(ranks: list[int]) -> float:
    if not ranks:
        return 0.0
    return float(np.mean([1.0 / r for r in ranks]))


def hits_at_k(ranks: list[int], k: int) -> float:
    if not ranks:
        return 0.0
    return float(np.mean([1.0 if r <= k else 0.0 for r in ranks]))


def ranking_metrics(queries: list[tuple[np.ndarray, int]]) -> dict:
    """queries: list of (scores, positive_index). Returns MRR + Hits@K."""
    ranks = [_rank_of_positive(s, p) for s, p in queries]
    return {"n": len(ranks), "mrr": mrr(ranks),
            "hits@1": hits_at_k(ranks, 1), "hits@5": hits_at_k(ranks, 5),
            "hits@10": hits_at_k(ranks, 10),
            "mean_rank": float(np.mean(ranks)) if ranks else 0.0}


def precision_at_k(scores: np.ndarray, labels: np.ndarray, k: int) -> float:
    s = np.asarray(scores, float)
    y = np.asarray(labels, int)
    top = np.argsort(-s, kind="mergesort")[:k]
    return float(y[top].mean()) if len(top) else 0.0


def recall_at_k(scores: np.ndarray, labels: np.ndarray, k: int) -> float:
    s = np.asarray(scores, float)
    y = np.asarray(labels, int)
    top = np.argsort(-s, kind="mergesort")[:k]
    total = int(y.sum())
    return float(y[top].sum() / total) if total else 0.0


def ndcg_at_k(scores: np.ndarray, labels: np.ndarray, k: int) -> float:
    s = np.asarray(scores, float)
    y = np.asarray(labels, float)
    top = np.argsort(-s, kind="mergesort")[:k]
    gains = y[top]
    discounts = 1.0 / np.log2(np.arange(2, len(gains) + 2))
    dcg = float((gains * discounts).sum())
    ideal = np.sort(y)[::-1][:k]
    idcg = float((ideal * discounts[:len(ideal)]).sum())
    return dcg / idcg if idcg > 0 else 0.0


def binary_metrics(scores: np.ndarray, labels: np.ndarray) -> dict:
    s = np.asarray(scores, float)
    y = np.asarray(labels, int)
    out = {"n": int(len(y)), "positives": int(y.sum())}
    if y.sum() and (len(y) - y.sum()):
        if roc_auc_score is not None:
            out["roc_auc"] = float(roc_auc_score(y, s))
        if average_precision_score is not None:
            out["pr_auc"] = float(average_precision_score(y, s))
    return out


def scenario_detection_rate(scores: np.ndarray, threshold: float) -> float:
    if len(scores) == 0:
        return 0.0
    return float((np.asarray(scores, float) >= threshold).mean())
