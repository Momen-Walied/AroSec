# Structural Ground-Truth Schema

`StructuralTransitionGroundTruthV1` (research layer). Structure only; **no attack-stage semantics** (`attack_related` is true/false/unknown).

Fields: `ground_truth_id`, `scenario_id`, `start_time`, `end_time`, `transition_type`, `expectedness` (EXPECTED/UNUSUAL/UNKNOWN), `source_asset_ids`, `destination_asset_ids`, `relationship_ids`, `zone_before`/`zone_after`, `role_context`, `scenario_origin` (LAB_CONTROLLED/OPERATOR_CONFIRMED/SYNTHETIC/DATASET_LABEL), `confidence`, `notes`, `evidence_refs`, `attack_related`.

Transition types: `expected_structural_transition`, `unusual_structural_transition`, `normal_role_consistent_new_edge`, `role_inconsistent_new_edge`, `topology_rewiring`, `fanout_burst`, `inbound_convergence`, `chain_formation`, `peer_set_replacement`, `cross_zone_communication`.

Ground truth must not live only in human memory — it is a versioned file.

## Independence / provenance (amendment 2)

Structural ground truth **MUST NOT** be derived from the same anomaly outputs or telemetry patterns being evaluated. Forbidden sources: EdgeAnomalyResult, NodeAnomalyResult, GraphContext score, BehavioralEpisode, or an observed traffic spike after the fact.

Allowed independent sources: lab orchestration system, operator action log, experiment controller, maintenance/change ticket, externally supplied dataset labels. For controlled lab scenarios, scenario start/end must be recorded **at execution time** by the orchestrator or operator.

Provenance fields: `ground_truth_source` (enum), `ground_truth_recorded_at`, `orchestrator_run_id`, `operator_action_id`. A dataset with missing or forbidden provenance **FAILS** GROUND_TRUTH_PROVENANCE.

