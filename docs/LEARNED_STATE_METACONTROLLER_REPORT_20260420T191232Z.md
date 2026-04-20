# Learned state-level metacontroller report (20260420T191232Z)

## Motivation
The current controller family reaches plausible neighborhoods but often under-specifies the next action choice among refine/verify/widen/commit.
This pass introduces a bounded learned action policy over controller state to replace brittle one-off thresholds.

## Canonical inputs read
- fresh_loss_bundle: `docs/TWENTY_EXACT_CURRENT_FULL_VS_BEST_FRESH_2026_04_20.md`
- twenty_case_improvement_report: `docs/TWENTY_CASE_CURRENT_FULL_IMPROVEMENT_REPORT_20260420T181131Z.md`
- targeted_failure_bundle_report: `docs/TARGETED_FAILURE_BUNDLE_REPORT_20260420T183801Z.md`
- near_miss_report: `docs/NEAR_MISS_CORRECTION_EVAL_REPORT_20260420T184849Z.md`
- broad_comparison_artifact: `outputs/full_method_comparison_bundle/20260419T214335Z/manifest.json`

## Feature set
- State features are action-local frontier signals emitted by the current controller: support concentration, continuation value, diversity/duplicate terms,
  anti-collapse penalties, uncertainty/near-miss flags, and short action history indicators.
- Exact feature schema written to `outputs/learned_state_metacontroller_20260420T191232Z/feature_schema.json`.

## Label generation
- For each sampled state snapshot, perform bounded one-step forced-action localized rollouts over all four actions.
- Select argmax final-outcome score as the training label.
- Detailed description: `outputs/learned_state_metacontroller_20260420T191232Z/label_generation_description.md`.

## Models tried
- `logreg`: accuracy=0.417, macro_f1=0.339
- `decision_tree`: accuracy=0.417, macro_f1=0.271
- `random_forest`: accuracy=0.500, macro_f1=0.336
- Selected model: `logreg`.

## Evaluation
### Targeted difficult slice
- heuristic: acc=0.286, correct=2/7, mean_actions=3.00
- learned: acc=0.571, correct=4/7, mean_actions=2.57
- near_miss_correction_gate: acc=0.857, correct=6/7, mean_actions=9.43
- old_current_full: acc=0.714, correct=5/7, mean_actions=10.86
- width_depth_challenger_guard: acc=0.571, correct=4/7, mean_actions=10.86
- Improvement count vs old current-full: 0.

### Broader surface
- heuristic: acc=0.350, correct=7/20, mean_actions=2.95
- learned: acc=0.600, correct=12/20, mean_actions=2.50
- near_miss_correction_gate: acc=0.700, correct=14/20, mean_actions=9.40
- old_current_full: acc=0.600, correct=12/20, mean_actions=10.75
- width_depth_challenger_guard: acc=0.600, correct=12/20, mean_actions=10.65
- Improvement count vs old current-full: 4.

## Action tendency diagnostics
- Per-case learned policy actions are in targeted/broader prediction CSVs.
- Feature importance exported for interpretability.

## Honest conclusion
The learned policy is a bounded extension of the current controller and can be directly compared against incumbent guarded variants.
If gains are small or mixed on broader surfaces, this report should be treated as evidence for further calibration rather than a definitive replacement.

## Required final fields
- old current full method name: `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1`
- new learned metacontroller method name: `broad_diversity_aggregation_strong_v1_state_action_metacontroller_v1`
- training dataset size: `236`
- targeted-slice improvement count: `0`
- broader-surface improvement count: `4`
- docs report path: `docs/LEARNED_STATE_METACONTROLLER_REPORT_20260420T191232Z.md`
- output bundle path: `outputs/learned_state_metacontroller_20260420T191232Z`
