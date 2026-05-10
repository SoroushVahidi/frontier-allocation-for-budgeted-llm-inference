# Adaptive router v3 policy (offline)

- Deterministic, regex/rule-based feature extraction inspired by target-quantity, number-role, and unified risk signals.
- Default conservative behavior: keep low-risk cases on base path; abstain on ambiguity.
- Route map:
  - average/target-score -> `average_target_score`
  - combinatorics cues -> `combinatorics_counting`
  - ratio/partition (without percent-base risk) -> `ratio_partition`
  - ordered state-change -> `state_composition`
  - rate/unit -> `rate_table_v1`
  - money multi-step (without percent-base risk) -> `quantity_ledger_v2_1`
  - difference cue -> `target_difference_v1`
- `percent_base_denominator` is held back by default (`enable_percent_base_denominator=False`).
- If multiple scaffold candidates and confidence is weak, router abstains.
