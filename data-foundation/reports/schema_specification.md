# Schema Specification v0.1

Summary of the seven contracts and their key invariants.

| Contract | Fields | Key invariants |
|---|---:|---|
| Asset | 20 | asset_id != bare IP; MAC>hostname>device>IP identity precedence. |
| CommunicationEdge | 23 | FACTS only; forbidden AI fields rejected; window/first/last ordering enforced. |
| GraphEvent | 12 | Append-only; monotonic graph_version; event_type requires matching refs. |
| AttackLabel | 15 | is_attack consistent with attack_category; original labels preserved. |
| Campaign | 13 | No inferred objective/target when ground_truth_available is false. |
| EdgeFeatureWindow | 18 | All history fields computed strictly before window_start. |
| NodeFeatureWindow | 17 | Outbound-centric aggregates; leakage-safe novelty fields. |

See `docs/CYBER_GRAPH_DATA_CONTRACT_V0.1.md` for the full field tables.