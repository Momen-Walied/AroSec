"""Temporal Graph Intelligence (Phase 4A).

Framework-independent temporal-graph dataset design + non-GNN baselines + evaluation
harness for the *current* homogeneous asset-communication graph.

This package deliberately does NOT contain any neural graph model, does not train
anything, and does not modify the frozen Data Foundation v0.2 contracts. Its job is to
make the research question answerable:

    Does causal temporal graph context carry measurable information beyond the existing
    Edge Behavior and Node Behavior intelligence?

Canonical data representations are framework-independent (Parquet / Arrow / JSON
metadata); adapters to PyG/DGL/etc. are intentionally out of scope for Phase 4A.
"""
from __future__ import annotations

__all__ = ["config", "contracts"]
