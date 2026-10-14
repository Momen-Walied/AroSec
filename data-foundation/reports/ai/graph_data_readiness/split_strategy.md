# Split Strategy

Do NOT randomly split scenario rows. Use a hierarchy, from strongest to weakest:

1. **ASSET holdout** — train on some entities' instances, test the SAME structural pattern on unseen entities (primary generalization test).
2. **TOPOLOGY-REGION holdout** — hold out a whole local neighbourhood.
3. **TIME** — earlier vs later capture (drift test).
4. **SCENARIO-INSTANCE** — same class, different assets/times.

Report results per cold-start category and per identity level; never pool across holdouts.

## Role-generalization test

- TRAIN: `camera_01 -> nvr`
- TEST (expected): `camera_04 -> nvr`
- TEST (unusual): `camera_04 -> plc`

A model must rely on structural/role context, not asset ids.

