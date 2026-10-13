# False-Merge Analysis (deterministic)

| case | episodes | merged? |
|---|---:|---|
| same_timestamp_only | 2 | False |
| same_severity_only | 2 | False |
| same_reason_only | 2 | False |
| unrelated_simultaneous | 2 | False |
| positive_control_connected | 1 | True |

Proximity alone (same timestamp / severity / reason code) does NOT merge signals.
Only temporal AND relational connection merges.

