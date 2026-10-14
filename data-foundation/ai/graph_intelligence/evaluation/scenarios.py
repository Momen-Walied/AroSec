"""Synthetic graph scenarios (SCN-G01..G08) — EVALUATION ONLY.

These are never mixed into training. Each scenario is a small, explicit causal history
plus a target edge, labelled ``structurally_unusual`` when the target would be surprising
given the history. They exist to test whether graph context detects structural change that
single-edge novelty misses.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GraphScenario:
    scenario_id: str
    description: str
    history: list[tuple[str, str]]     # causal edges observed before the target
    target: tuple[str, str]
    structurally_unusual: bool


def _chain(prefix: str, n: int) -> list[tuple[str, str]]:
    return [(f"{prefix}{i}", f"{prefix}{i+1}") for i in range(n)]


def scn_g01() -> GraphScenario:
    return GraphScenario("SCN-G01_NEW_EDGE", "A suddenly connects to unseen B",
                         [("a", "n1"), ("a", "n2"), ("b", "n1"), ("b", "n2")],
                         ("a", "z_new"), True)


def scn_g02() -> GraphScenario:
    hist = [("a", "n1")] + [("h", f"m{i}") for i in range(6)]
    return GraphScenario("SCN-G02_FANOUT_BURST", "A creates many new edges at once",
                         hist, ("a", "m9"), True)


def scn_g03() -> GraphScenario:
    return GraphScenario("SCN-G03_CHAIN_FORMATION", "A -> B then B -> C chain",
                         [("a", "b")], ("b", "c_new"), True)


def scn_g04() -> GraphScenario:
    hist = [(f"a{i}", "hub") for i in range(5)] + [("hub", "a0"), ("hub", "a1")]
    return GraphScenario("SCN-G04_LOCAL_REWIRING", "A keeps volume but changes peer structure",
                         hist, ("a0", "a4"), True)


def scn_g05() -> GraphScenario:
    hist = [("b", "s1")] + [(f"x{i}", f"y{i}") for i in range(5)]
    return GraphScenario("SCN-G05_INBOUND_CONVERGENCE", "Many entities begin connecting to B",
                         hist, ("x3", "b"), True)


def scn_g06() -> GraphScenario:
    # a's group {g1,g2,g3} all connect to peer h; adding a->h is structurally normal
    hist = [("a", "g1"), ("a", "g2"), ("g1", "h"), ("g2", "h"), ("g3", "h")]
    return GraphScenario("SCN-G06_NORMAL_NEW_EDGE", "A connects to a new peer similar to its group",
                         hist, ("a", "h"), False)


def scn_g07() -> GraphScenario:
    hist = [("a", "g1"), ("a", "g2"), ("g1", "g2"),
            ("c1", "c2"), ("c2", "c3"), ("c3", "c1")]
    return GraphScenario("SCN-G07_UNUSUAL_EDGE", "A connects across an unrelated neighborhood",
                         hist, ("a", "c1"), True)


def scn_g08() -> GraphScenario:
    hist = ([("a", "p1"), ("a", "p2")] + [(f"q{i}", f"r{i}") for i in range(4)]
            + [("g1", "g2"), ("g2", "g3")])
    return GraphScenario("SCN-G08_COMPOUND_CHANGE",
                         "New edges + fan-out + neighbourhood change",
                         hist, ("a", "r2"), True)


SCENARIO_BUILDERS = (scn_g01, scn_g02, scn_g03, scn_g04, scn_g05, scn_g06, scn_g07, scn_g08)


def all_scenarios() -> list[GraphScenario]:
    return [f() for f in SCENARIO_BUILDERS]
