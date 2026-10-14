# Capture Package Spec (handoff from Network/Security)

```
site_metadata.json
assets.parquet
relationships.parquet
observations.parquet
asset_identity_observations.parquet
zones.parquet
roles.parquet
structural_ground_truth.parquet
scenario_manifest.json
capture_manifest.json
README.md
```

Compatibility: adapters sit **above** the frozen v0.2 contract; v0.2 is never changed.

## Required observation fields

timestamp, src identity, dst identity, src IP, dst IP, protocol, port, bytes, packets, relationship identity, capture source. Optional: MAC, VLAN, zone, role, service, DNS, DHCP, TLS, MQTT topics, OT protocol metadata.

## Manifest (must record)

scenario_id, site/lab id, start/end, operator, assets involved, expected transition, capture completeness, time-sync status, notes. Ground truth must NOT live only in memory.

## Clock quality

- tolerance 1.0s; missing timestamps FAIL; out-of-order WARN and must be documented (never silently reordered).

## Privacy

Tooling runs **on-site**; only aggregated statistics / readiness status / permitted scenario metadata leave the site. No packet payload export required.

## Dataset integrity / versioning (amendment 3)

Every capture package must record an **immutable identity**: `dataset_id`, `dataset_version`, `capture_id` / `lab_run_id`, `schema_versions`, `generated_at`, `source_manifests`, and file `checksums` where practical. A readiness report must state **exactly which immutable package it evaluated**, so later benchmark results cannot silently refer to a different capture revision.

