# Current Graph Audit

What the production contract actually contains today (no aspiration):

- **Nodes**: 63 assets (`asset:*`), identity method `dataset_ip_fallback` (provisional; no MAC/vendor/VLAN/subnet for UNSW).
- **Persistent edges**: 74 directed `CommunicationRelationship` rows (src→dst communication pairs).
- **Temporal edge observations**: 67,885 `EdgeFeatureWindowV2` rows over 35,805 distinct 30 s windows.
- **Identity metadata**: heterogeneous attributes (services/VLANs/users/processes) are **NOT** present. This is a homogeneous asset-communication graph, not a cyber knowledge graph.
- **Attack labels**: none for UNSW. Labeled small sets exist (x_iiotid 728, cicapt_iiot 8) and are usable for **evaluation only**.

## Honest topology characterisation

- Density (directed): **0.0189** (74/3906 possible pairs).
- Undirected connected components: **1** (one component of 63).
- Reciprocity: 24/74.
- **Single hub dominates**: one gateway asset accounts for ~99.6% of all edge-windows, which makes the graph effectively a **star**. 2-hop neighbourhood of any node is the whole graph.

## Graph classes

- **A. Current Temporal Asset Communication Graph** (implemented): assets + communication relationships + windowed observations. Homogeneous.
- **B. Future heterogeneous Cyber Knowledge Graph** (NOT available): would add services, VLANs, subnets, users, processes, assets-as-roles, vulnerabilities, reachability. Phase 4A designs for A and keeps the contract open for B.

