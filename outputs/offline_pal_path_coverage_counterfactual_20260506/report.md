# Offline PAL path coverage counterfactual

- Focus rows (external_only + both_wrong): **48**
- Bucket counts: `{'external_only': 21, 'both_wrong': 27}`
- Counterfactual counts: `{'gold_absent_everywhere_detectable': 34, 'upstream_generation_likely_loss': 34, 'selection_or_overlay_likely_loss': 4, 'gold_available_somewhere_not_selector_pool': 10}`
- Discovery-first gate would trigger: **5**
- Discovery-first gate recoverable-if-trigger: **0**
- Dominant root cause: **gold_absent_everywhere_detectable**
- API calls: none
