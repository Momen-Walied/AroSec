# Temporal Split Design

Chronological 60/20/20 over target `as_of`, reusing the Edge/Node Behavior boundaries so comparisons are meaningful. **No random splits.**

```
{
  "train_end": "2016-10-19 15:45:00+00:00",
  "validation_end": "2016-10-25 15:27:30+00:00",
  "n_total": 67885,
  "n_train": 40731,
  "n_validation": 13577,
  "n_test": 13577
}
```

## Online semantics (history carry-over)

- TRAIN history **carries into** VALIDATION; TRAIN+VALIDATION history **carries into** TEST.
- Model parameters are frozen at each boundary; the graph keeps evolving. This matches real deployment and is stricter than resetting history (which would leak future structure under the guise of 'clean state').
- Normalization statistics are fit on **TRAIN only** (leakage class G).
- Episode-derived context is forbidden as an input to any sample whose `as_of` precedes episode completion (leakage class H).

