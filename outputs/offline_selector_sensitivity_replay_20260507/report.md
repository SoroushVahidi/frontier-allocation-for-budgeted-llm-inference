# Offline selector-sensitivity replay

- Cases analyzed: 12
- Prediction changed (any): 11
- Worsened exact (any): 3

## Bucket counts
- added_candidate_flip_wrong: 3
- duplicate_skip_flip: 2
- gold_present_improved_but_exact_worse: 0
- override_blocked_but_selection_changed: 10
- previously_correct_regressed: 3

## Top sensitivity features
- added_any
- conservative_override_blocked
- triggered_any
- duplicate_skip_any
- gold_present_delta_positive

## Recommendation
- Adopt a no-selection-side-effect exploration logging path: record exploratory candidates outside selector-visible pool until explicit selector-ablation diagnostics pass.
