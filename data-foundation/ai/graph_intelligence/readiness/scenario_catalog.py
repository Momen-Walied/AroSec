"""Controlled lab scenario catalogue (LAB-G01..G12) + hard controls + entry-gate spec.

Structure only: these describe expected STRUCTURAL transitions. They are NOT attacks and
carry no attack-stage semantics.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .contracts import Expectedness, TransitionType


@dataclass(frozen=True)
class LabScenario:
    scenario_id: str
    name: str
    setup: str
    expected_transition: str
    expected_label: TransitionType
    expectedness: Expectedness
    duration_min: int
    entities: tuple[str, ...]
    cleanup: str
    evidence: tuple[str, ...] = field(default_factory=tuple)


SCENARIOS: tuple[LabScenario, ...] = (
    LabScenario("LAB-G01", "Legitimate new peer",
                "Add a new but plausible peer to an existing role.",
                "A known node begins communicating with a role-consistent new peer.",
                TransitionType.NORMAL_ROLE_CONSISTENT_NEW_EDGE, Expectedness.EXPECTED, 30,
                ("engineering_ws", "plc_02"), "Stop traffic; leave history.", ("flow", "ground-truth note")),
    LabScenario("LAB-G02", "Role-consistent new device",
                "Commission a new device consistent with existing roles.",
                "New device joins and communicates with its expected peers.",
                TransitionType.NORMAL_ROLE_CONSISTENT_NEW_EDGE, Expectedness.EXPECTED, 45,
                ("plc_03", "historian"), "Decommission or park.", ("flow", "asset sheet")),
    LabScenario("LAB-G03", "Role-inconsistent new peer",
                "Make a camera talk to an engineering workstation (role violation).",
                "Camera -> engineering workstation edge appears.",
                TransitionType.ROLE_INCONSISTENT_NEW_EDGE, Expectedness.UNUSUAL, 20,
                ("camera_01", "engineering_ws"), "Stop traffic.", ("flow", "operator note")),
    LabScenario("LAB-G04", "Fan-out burst",
                "One node rapidly initiates many new relationships.",
                "Source-out degree spikes with several new peers within the window.",
                TransitionType.FANOUT_BURST, Expectedness.UNUSUAL, 15,
                ("asset_x",), "Stop traffic.", ("flow",)),
    LabScenario("LAB-G05", "Inbound convergence",
                "Many nodes begin connecting to one destination.",
                "Destination inbound degree spikes with many new sources.",
                TransitionType.INBOUND_CONVERGENCE, Expectedness.UNUSUAL, 15,
                ("asset_y",), "Stop traffic.", ("flow",)),
    LabScenario("LAB-G06", "Peer-set replacement",
                "A node keeps similar volume but replaces its peer set.",
                "Neighbor-set change high, volume approximately stable.",
                TransitionType.PEER_SET_REPLACEMENT, Expectedness.UNUSUAL, 30,
                ("asset_z",), "Restore original peers.", ("flow",)),
    LabScenario("LAB-G07", "Local topology rewiring",
                "Rewire edges within one neighborhood without new volume.",
                "Local subgraph changes shape; global volume stable.",
                TransitionType.TOPOLOGY_REWIRING, Expectedness.UNUSUAL, 30,
                ("plc_01", "plc_02", "broker"), "Restore topology.", ("flow",)),
    LabScenario("LAB-G08", "Cross-zone relationship",
                "An edge crosses from one zone to another where it normally would not.",
                "New edge whose endpoints are in different zones.",
                TransitionType.CROSS_ZONE_COMMUNICATION, Expectedness.UNUSUAL, 20,
                ("camera_02", "plc_03"), "Stop traffic.", ("flow", "zone map")),
    LabScenario("LAB-G09", "Temporal chain",
                "A -> B then B -> C within a short window.",
                "Two-hop directed chain forms within the window.",
                TransitionType.CHAIN_FORMATION, Expectedness.UNUSUAL, 20,
                ("asset_a", "asset_b", "asset_c"), "Stop traffic.", ("flow",)),
    LabScenario("LAB-G10", "Multi-node structural change",
                "Several nodes change relationships simultaneously.",
                "Multiple neighborhoods change in the same window.",
                TransitionType.TOPOLOGY_REWIRING, Expectedness.UNUSUAL, 30,
                ("group_1",), "Restore topology.", ("flow",)),
    LabScenario("LAB-G11", "Device replacement / identity change",
                "A device is replaced; identity (MAC/role) changes.",
                "New identity appears in an existing role; old identity goes quiet.",
                TransitionType.EXPECTED_STRUCTURAL_TRANSITION, Expectedness.EXPECTED, 45,
                ("plc_02_old", "plc_02_new"), "Decommission old identity.", ("flow", "asset sheet")),
    LabScenario("LAB-G12", "Legitimate maintenance window",
                "A scheduled maintenance burst by an admin node.",
                "Temporary new edges during a declared maintenance window.",
                TransitionType.EXPECTED_STRUCTURAL_TRANSITION, Expectedness.EXPECTED, 60,
                ("jump_host",), "End window; note in manifest.", ("flow", "change ticket")),
)

# Hard controls: structurally similar to an "unusual" scenario but role-consistent.
CONTROLS: tuple[dict, ...] = (
    {"unusual": "camera -> engineering_ws", "control": "camera -> nvr",
     "pairs_with": "LAB-G03"},
    {"unusual": "plc -> arbitrary_iot", "control": "plc -> historian",
     "pairs_with": "LAB-G03"},
    {"unusual": "cross-zone camera -> plc", "control": "cross-zone camera -> nvr (allowed path)",
     "pairs_with": "LAB-G08"},
)

# Replication guidance.
REPLICATION_MIN_INSTANCES = 3
REPLICATION_DIMENSIONS = ("distinct source nodes", "distinct destination nodes",
                          "different times", "different topology regions")

# Temporal GNN entry gate: critical requirements that must ALL pass.
ENTRY_GATE = (
    ("STRUCTURAL_DIVERSITY", "acceptable hub dominance, >=2 independent local neighbourhoods"),
    ("NON_HUB_COVERAGE", "meaningful non-hub target-edge count"),
    ("NEW_EDGE_COVERAGE", "enough new-edge events for evaluation"),
    ("TEMPORAL_DIVERSITY", "enough structural transitions over time"),
    ("IDENTITY_QUALITY", "identity level >= L2"),
    ("ROLE_DIVERSITY", "roles and zones recorded where required by the evaluated task"),
    ("GROUND_TRUTH_QUALITY", "expected/unusual ground truth present"),
    ("GROUND_TRUTH_PROVENANCE", "independent ground-truth source (never the anomaly outputs)"),
    ("SCENARIO_REPLICATION", f">= {REPLICATION_MIN_INSTANCES} instances per key scenario + hard controls"),
    ("COLD_START_COVERAGE", "new-node categories represented"),
    ("ROLE_GENERALIZATION", f">= {REPLICATION_MIN_INSTANCES} independent assets per key role for hold-out"),
    ("SPLIT_QUALITY", "entity/topology/time holdout evaluation is possible"),
    ("TWO_HOP_CONTEXT", "2-hop adds local (not whole-graph) context"),
    ("DATASET_INTEGRITY", "immutable dataset package/version identity recorded"),
)


def catalogue() -> list[dict]:
    return [{"scenario_id": s.scenario_id, "name": s.name, "setup": s.setup,
             "expected_transition": s.expected_transition,
             "expected_label": str(s.expected_label), "expectedness": str(s.expectedness),
             "duration_min": s.duration_min, "entities": list(s.entities),
             "cleanup": s.cleanup, "evidence": list(s.evidence)} for s in SCENARIOS]
