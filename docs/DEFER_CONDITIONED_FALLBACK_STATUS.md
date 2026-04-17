# Defer-conditioned fallback status

## Why defer-only is incomplete
A defer prediction can improve accepted-only accuracy, but it leaves a key policy question unanswered: what should happen next for unresolved hard states?

## Why complementarity-aware fallback matters
Fallback should not be selected only because of global average performance. We care about whether it helps *on the deferred subset* where the base defer policy explicitly abstains from commitment.

## Implemented fallback variants
- `pairwise_binary_backup`: deferred cases route to the existing binary pairwise comparator.
- `pointwise_value_backup`: deferred cases route to pointwise value comparison between branch i/j.
- `outside_option_aware_backup`: keeps unresolved when outside option remains competitive (proxy threshold), otherwise resolves via bounded backup ranking.
- `specialized_hard_case_backup` (optional): uses a specialist model trained only on deferred/hard subset rows.

## Trained specialist vs policy wrappers
- Policy wrappers (`pairwise_binary_backup`, `pointwise_value_backup`, `outside_option_aware_backup`) reuse existing trained models.
- `pairwise_deferred_specialist` is a true additional trained model (bounded logistic baseline on `x_pair_v3`) trained only on deferred/hard rows.

## Metric interpretation
- `accepted_only_accuracy_test` / `coverage_test`: pre-fallback defer-only behavior.
- `resolved_accuracy_test` / `resolved_coverage_test`: post-fallback behavior.
- `unresolved_rate_after_fallback_test`: how much remains intentionally unresolved.
- `fallback_subset_accuracy` and fallback gains vs binary/pointwise indicate deferred-subset complementarity.

## Safe interpretation
- This is a bounded fallback-resolution experiment for ambiguous states.
- Positive results suggest unresolved states benefit from specialist or complementary resolution.
- Negative/mixed results suggest defer targeting quality or fallback complementarity is still weak.
