# Structural commitment v1 — offline replay

Output: `outputs/structural_commit_v1_replay_20260508T120000Z`

## Targets (PNS diagnosis case IDs)
```json
{
  "rows": 24,
  "unknown_no_replay_data": 1,
  "fixed_by_structural_commit_v1": 7,
  "fixed_by_existing_track_b": 3,
  "additional_fixes_over_track_b": 4,
  "unchanged_still_wrong": 0,
  "abstained": 16
}
```

## Guardrails
```json
{
  "rows": 188,
  "metadata_missing_rows": 2,
  "correct_to_wrong_regressions": 0
}
```

## Additional fixes by mechanism (structural only, not Track B)
```json
{
  "overlay_previous_equals_gold_but_surface_used_bad_pal_stdout": 3,
  "frontier_tiebreak_selected_peer_not_gold_while_gold_in_pool": 1
}
```

Gold used for scoring only. Gate logic is gold-free.