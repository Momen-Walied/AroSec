#!/usr/bin/env python3
"""Load exported nodes.csv / relationships.csv into Neo4j.

Optional convenience only — the transformation pipeline never requires Neo4j.

    python scripts/load_neo4j.py \
        --nodes data/processed/graph/neo4j/nodes.csv \
        --relationships data/processed/graph/neo4j/relationships.csv \
        --uri bolt://localhost:7687 --user neo4j --password secret

Requires: pip install "neo4j>=5"
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

try:
    from neo4j import GraphDatabase
except ImportError as exc:  # pragma: no cover
    raise SystemExit("neo4j driver not installed: pip install 'neo4j>=5'") from exc

NODE_QUERY = """
UNWIND $rows AS row
MERGE (a:Asset {asset_id: row.asset_id})
SET a.asset_type = row.asset_type,
    a.identity_method = row.identity_method,
    a.identity_confidence = toFloat(row.identity_confidence),
    a.ip_addresses = row.ip_addresses,
    a.mac_addresses = row.mac_addresses,
    a.hostname = row.hostname,
    a.first_seen = row.first_seen,
    a.last_seen = row.last_seen,
    a.dataset_source = row.dataset_source
"""

REL_QUERY = """
UNWIND $rows AS row
MATCH (s:Asset {asset_id: row.src_asset_id})
MATCH (d:Asset {asset_id: row.dst_asset_id})
MERGE (s)-[r:COMMUNICATES_WITH {edge_id: row.edge_id}]->(d)
SET r.network_protocol = row.network_protocol,
    r.application_protocol = row.application_protocol,
    r.connection_count = toInteger(row.connection_count),
    r.packet_count = toInteger(row.packet_count),
    r.bytes_out = toInteger(row.bytes_out),
    r.bytes_in = toInteger(row.bytes_in),
    r.window_start = row.window_start,
    r.window_end = row.window_end,
    r.first_seen = row.first_seen,
    r.last_seen = row.last_seen,
    r.historical_connection_count = toInteger(row.historical_connection_count),
    r.is_new_peer = (row.is_new_peer = 'true')
"""


def _rows(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def main() -> None:
    parser = argparse.ArgumentParser(description="Load Vigilance temporal graph into Neo4j")
    parser.add_argument("--nodes", type=Path, required=True)
    parser.add_argument("--relationships", type=Path, required=True)
    parser.add_argument("--uri", default="bolt://localhost:7687")
    parser.add_argument("--user", default="neo4j")
    parser.add_argument("--password", default="")
    parser.add_argument("--src-key", default="asset_id")
    parser.add_argument("--dst-key", default="src_asset_id")
    args = parser.parse_args()

    node_rows = _rows(args.nodes)
    rel_rows = _rows(args.relationships)
    for rel in rel_rows:
        rel["src_asset_id"] = rel.get(":START_ID", rel.get("src_asset_id", ""))

    driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))
    with driver.session() as session:
        session.run(NODE_QUERY, rows=node_rows)
        session.run(REL_QUERY, rows=rel_rows)
    driver.close()
    print(f"Loaded {len(node_rows)} nodes and {len(rel_rows)} relationships into {args.uri}")


if __name__ == "__main__":
    main()
