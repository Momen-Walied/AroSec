# Limitations

- Behavioral episodes are **not** security incidents and carry **no** attack semantics.
- Correlation is temporal + relational only; it does **not** prove causality or movement.
- Inputs are UNSW (`dataset_ip_fallback`) alerts → **entity behavior**, not verified devices.
- Thresholds (edge 0.315 / node 0.719) are provisional; episode membership inherits them.
- No ground truth → episode quality is measured by compression/coherence, not accuracy.
- max_episode_duration caps percolation but may split genuinely long episodes.
- No score fusion; edge and node scores are reported separately.

