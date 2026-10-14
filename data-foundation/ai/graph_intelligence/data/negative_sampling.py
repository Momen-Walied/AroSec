"""Temporal-safe negative sampling for link/edge tasks.

A negative candidate ``(u, v)`` at time ``T`` must satisfy:

  * ``(u, v)`` was never observed before ``T`` (not a known edge), AND
  * ``(u, v)`` is NOT observed within ``(T, T + horizon]`` (otherwise it is a future
    positive and labelling it negative would be label leakage — leakage class F).

Negatives are drawn from plausible candidates, not impossible pairs only.
"""
from __future__ import annotations

import hashlib

import numpy as np

NEGATIVE_CATEGORIES = ("new_peer", "hard", "temporally_plausible", "random_non_edge")


def _rng_for(seed: int, src: str, dst: str, as_of: str) -> np.random.Generator:
    h = int(hashlib.sha1(f"{src}|{dst}|{as_of}".encode()).hexdigest()[:8], 16)
    return np.random.default_rng((seed + h) % (2**32))


def _undirected(adj: dict[str, set[str]], u: str) -> set[str]:
    return set(adj.get(u, ()))


def sample_negatives(
    *,
    src: str,
    dst: str,
    as_of: str,
    all_nodes: list[str],
    known_edges_before: set[tuple[str, str]],
    future_edges_within_horizon: set[tuple[str, str]],
    adjacency: dict[str, set[str]],
    k: int,
    seed: int = 42,
) -> list[dict]:
    """Deterministic, temporal-safe negatives for a target positive (src, dst)."""
    rng = _rng_for(seed, src, dst, as_of)

    def _forbidden(a: str, b: str) -> bool:
        return ((a, b) in known_edges_before or (b, a) in known_edges_before
                or (a, b) in future_edges_within_horizon or (b, a) in future_edges_within_horizon)

    nbr_u = _undirected(adjacency, src)
    two_hop_u = set(nbr_u)
    for n in list(nbr_u):
        two_hop_u |= _undirected(adjacency, n)

    def _category(c: str) -> str:
        if nbr_u & _undirected(adjacency, c):
            return "hard"                    # shares at least one peer with src
        if c in two_hop_u:
            return "temporally_plausible"    # peer-of-peer, no shared peer
        if _undirected(adjacency, c):
            return "new_peer"                # active node src never relates to
        return "random_non_edge"

    candidates = [c for c in all_nodes if c not in (src, dst) and not _forbidden(src, c)]
    candidates = sorted(candidates)
    rng.shuffle(candidates)

    out: list[dict] = []
    for c in candidates:
        if len(out) >= k:
            break
        out.append({"src_asset_id": src, "dst_asset_id": c,
                    "category": _category(c), "temporal_safe": True})
    return out


def is_temporal_safe(src: str, dst: str, known_before: set[tuple[str, str]],
                     future_horizon: set[tuple[str, str]]) -> bool:
    return (src, dst) not in known_before and (src, dst) not in future_horizon
