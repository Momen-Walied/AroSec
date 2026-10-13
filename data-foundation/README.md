# Vigilance — Data Foundation v0.1

Production-quality **data contracts and normalized temporal cyber-graph data** for the
Vigilance edge-first IIoT/ICS cybersecurity platform.

This repository is the *foundation layer*. It intentionally contains **no trained models**.
Its job is to give the Network Team, AI Team, and future Graph Intelligence components
**one stable, time-aware contract** to build against.

> Design goal: the future Temporal GNN / attack-path model must see
> `CAM-01 → NVR-01` (old, millions of connections, normal) and
> `CAM-01 → ENG-PC-03` (first seen 20s ago, SMB, never observed before) as
> **clearly different edges**, without us hard-coding that distinction into the AI layer.

## Project status

```
Data Foundation v0.2 (Cyber Graph Data Contract):  FROZEN
Edge Behavior Intelligence v1:                     COMPLETE
Shadow Integration v1:                             COMPLETE / SHADOW-READY
```

- **Edge Behavior Intelligence v1** (`ai/edge_behavior/`) — leakage-safe edge-anomaly
  baselines; selected approach is a **validation-weighted Statistical + Isolation Forest
  fusion** (Autoencoder evaluated and rejected). **Relationship anomaly detection, not
  validated attack detection**; UNSW identities are provisional `dataset_ip_fallback`.
- **Shadow Integration v1** (`ai/shadow/`) — event-time, transport-agnostic shadow runtime
  with **exact online/offline feature parity** (0 mismatches / 67,885 windows), idempotent
  processing, durable SQLite state + restart recovery, drift monitoring, and an analyst
  feedback contract. **Shadow-only, read-only, fail-open — no remediation.**
- Threshold **0.315 is provisional**; **no automatic retraining**. Model binaries are
  regeneration-only.
- Docs: `docs/AI_EDGE_BEHAVIOR_V1.md`, `docs/AI_SHADOW_INTEGRATION_V1.md`.

## What is here

| Area | Location |
|---|---|
| Versioned contracts (Pydantic v2) | `src/schemas/` |
| Per-dataset adapters | `src/datasets/` |
| Dataset registry | `configs/datasets.yaml` |
| Temporal aggregation + features | `src/normalization/` |
| Stable identity resolution | `src/identity/` |
| Temporal graph + events + exports | `src/graph/` |
| Validation + data quality | `src/validation/` |
| Reports generation | `src/reports.py` |
| CLI | `src/cli/` |
| Tests (52) | `tests/` |
| Reports | `reports/` |
| **Data contract spec** | `docs/CYBER_GRAPH_DATA_CONTRACT_V0.1.md` |

## Quickstart

```bash
make setup                      # creates .venv (Python 3.12) and installs deps
cp .env.example .env            # defaults to DATA_MODE=sample

python -m src.cli datasets inspect
python -m src.cli datasets download   --dataset cicapt_iiot --mode sample
python -m src.cli datasets normalize  --dataset cicapt_iiot
python -m src.cli build-graph         --dataset cicapt_iiot --window 30s
python -m src.cli validate
python -m src.cli report
python -m src.cli demo          # full end-to-end APT scenario
```

Full sample pipeline end-to-end: `make e2e`.

## Data modes

* `DATA_MODE=sample` (default) — enough representative data to build and verify the whole
  pipeline without excessive disk use.
* `DATA_MODE=full` — the complete dataset (may be many GB). **Check sizes first.**

## Datasets and access

See `reports/dataset_registry.md` (generated) and `configs/datasets.yaml` (source of truth).

| Dataset | Access | Role in v0.1 |
|---|---|---|
| CICAPT-IIoT 2024 | registration form → `MANUAL_DOWNLOAD_REQUIRED` | APT campaigns, provenance, attack stages |
| X-IIoTID 2021 | IEEE DataPort / Kaggle login → `MANUAL_DOWNLOAD_REQUIRED` | lateral movement, MQTT/Modbus/CoAP |
| UNSW-IoTraffic 2025 | open (Dryad) → `NORMALIZED` | long-duration normal baselines |
| Edge-IIoTset / CICIoT2023 | secondary/optional | extra attack coverage |

**We never bypass authentication, paywalls, or access restrictions.** Gated datasets are
marked `MANUAL_DOWNLOAD_REQUIRED` with exact steps, and the adapters are ready for the files
once provided.

### Notes for the two tricky sources

* **UNSW-IoTraffic (Dryad).** File streams sit behind an anti-bot challenge. The supported
  programmatic path is the Dryad API v2 with an OAuth bearer token (free account); a real
  browser also works and the adapter adopts the file from `~/Downloads`. `download()` reports
  `MANUAL_DOWNLOAD_REQUIRED` if neither is available. See `src/datasets/unsw_iotraffic.py`.
* **CICAPT-IIoT.** Access is a registration form; not automated. Place the provenance CSVs,
  network CSV, and `Attack_info.csv` under `data/raw/cicapt_iiot/` and normalize. Until then,
  `python -m src.cli demo` runs a synthetic CICAPT-shaped scenario with the exact
  CAM-01 → NVR-01 → ENG-PC-03 → PLC-07 flow.

## Results at v0.1 (real data)

| dataset | raw obs | assets | edges (30s) | labels | lateral-mv | events |
|---|---:|---:|---:|---:|---:|---:|
| cicapt_iiot (synthetic demo) | 13 | 6 | 9 | 8 | 4 | 15 |
| x_iiotid (CC BY 4.0 derivative) | 1,672 | 29 | 1,118 | 728 | 77 | 1,147 |
| unsw_iotraffic (100k-row sample) | 100,000 | 63 | 77,102 | 0 | 0 | 77,165 |

`python -m src.cli validate` reports `schema_errors=0` for all normalized datasets.

## Design guarantees

* `CommunicationEdge` is **facts-only**; AI score fields are *rejected at validation time*.
* `asset_id` is stable and never a bare IP; identity precedence MAC > hostname > device > IP.
* Missing values are `null`; nothing is fabricated.
* Unknown labels → `attack_category=unknown`, `original_label` always preserved.
* Novelty/history features use **only** observations strictly before the window (no leakage).
* Every relationship is time-aware; `GraphEvent.graph_version` enables point-in-time replay.

## Repository layout

```
configs/datasets.yaml        registry (source of truth)
src/schemas/                 v0.1 pydantic contracts
src/datasets/                adapters (base + one per dataset + registry)
src/normalization/           aggregation, features, io, label mapping
src/identity/                stable id + key builders
src/graph/                   temporal graph, neo4j export
src/validation/              schema + data-quality checks
src/cli/                     CLI entrypoint
scripts/load_neo4j.py        optional Neo4j loader
data/{raw,interim,processed} (git-ignored)
reports/  docs/  samples/  tests/
```

## Engineering rules

* IP is an **observation**, never permanent identity. Raw data and large artifacts are
  never committed (`data/raw/`, `data/processed/` are git-ignored).
* No Spark, no model training in this layer.
* Dataset-specific parsing stays in adapters; shared graph/normalization code never hardcodes
  a dataset's column names (see `src/datasets/columns.py`).
