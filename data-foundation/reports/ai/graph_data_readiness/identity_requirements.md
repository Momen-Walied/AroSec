# Identity Requirements

| level | meaning | readiness |
|---|---|---|
| L0 | IP-only provisional entity | FAIL |
| L1 | IP + stable MAC | WARN |
| L2 | MAC + DHCP/DNS/OUI corroboration | PASS (minimum) |
| L3 | operator-confirmed asset identity/role | PASS (preferred) |

Graph metrics must be reported separately by identity level, and IP churn must never be treated as structural change.

Current UNSW: **L0_ip_only** → FAIL.

