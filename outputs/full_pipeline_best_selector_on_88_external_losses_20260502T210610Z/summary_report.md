# Full Pipeline + Best Selector on External-Loss Subset

- Run type: `B` (discovery rerun followed by post-hoc selected-selector application).
- Internal method: `direct_reserve_semantic_frontier_v2`.
- Selector: `outcome_verifier_answer_group_selector_v1` (`scorer_mode=cached_jsonl`).
- Total cases: 88, evaluated: 88, skipped: 0.
- Accuracy on subset: 0.2159.
- Fixed previous external-loss cases: 19.
- Still lost cases: 69.

## Claim Safety
- This run is a selected external-loss subset evaluation, not a broad external-baseline dominance claim.
- Gold is used only after prediction for evaluation/diagnosis.
