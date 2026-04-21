# Selection scoring policy eval (20260421T173113Z)

- Output folder: `outputs/selection_scoring_policy_eval_20260421T173113Z`
- Control method: `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first_hard_max_family_expansions_cap_k6_v1_fixed_k6_control__deterministic_output_layer_repair_v1`
- Surface: canonical hundred strict_gate1_cap_k6-vs-best failure-statistics slice.
- Claims are restricted to this current evaluated repository phase and this selection-layer experiment.

## Aggregate metrics
- `current_selection_control`: accuracy=0.5600, absent_from_tree=26, present_not_selected=18, recovered_present_not_selected=0, accuracy_when_gold_in_tree=0.7568
- `answer_group_support_only`: accuracy=0.5500, absent_from_tree=26, present_not_selected=19, recovered_present_not_selected=0, accuracy_when_gold_in_tree=0.7432
- `answer_group_support_plus_node_score`: accuracy=0.5500, absent_from_tree=26, present_not_selected=19, recovered_present_not_selected=0, accuracy_when_gold_in_tree=0.7432
- `answer_group_support_plus_calibrated_score`: accuracy=0.5500, absent_from_tree=26, present_not_selected=19, recovered_present_not_selected=0, accuracy_when_gold_in_tree=0.7432
- `answer_group_support_plus_score_plus_tiebreak_cleanup`: accuracy=0.5500, absent_from_tree=26, present_not_selected=19, recovered_present_not_selected=0, accuracy_when_gold_in_tree=0.7432

## Target failure mode (present_not_selected)
- Control present_not_selected count: 18
- `current_selection_control` recovered 0 (0.000 of control present_not_selected)
- `answer_group_support_only` recovered 0 (0.000 of control present_not_selected)
- `answer_group_support_plus_node_score` recovered 0 (0.000 of control present_not_selected)
- `answer_group_support_plus_calibrated_score` recovered 0 (0.000 of control present_not_selected)
- `answer_group_support_plus_score_plus_tiebreak_cleanup` recovered 0 (0.000 of control present_not_selected)

## Dedicated failure-mode analysis
- Control policy in this evaluated slice is effectively answer-group-first plus deterministic repair, which already collapses many previously present-not-selected cases.
- Remaining control `present_not_selected` cases are singleton gold groups (`18/18`), so support aggregation cannot recover them.
- Calibration/tie-break variants have no additional recovery signal when the gold answer is represented by only one completed branch and is still lower-scored.
- The tested policy changes therefore do not reduce residual `present_not_selected` in this slice and slightly worsen one case overall.

## Explicit answers to decision questions
- Does the new scoring policy reduce `present_not_selected` failures? **No** (0 recoveries across tested variants).
- On gold-in-tree cases, how often is correctness recovered over control? **0 / 18** control present-not-selected cases.
- Does update improve overall accuracy? **No** (best remains control at 0.56).
- Does it hurt absent-from-tree cases? **No** absent-from-tree counts remain unchanged in this slice.
- Best variant overall: `current_selection_control`.
- Best variant for present-not-selected recovery: `current_selection_control` (tie at zero recovery).

## Selection-policy diagnosis in code terms
- Current scoring path already treats answer groups as first-class in final prediction (`_final_prediction_from_groups` and `_group_support_summary`).
- Final selection is answer-group-first, then node representative within selected group.
- Tie behavior comes from group-score ranking and representative-node max-score choice.
- Deterministic output-layer repair (`choose_repair_answer`) also applies post-selection extraction and support-consensus rescue.
- Residual failures in this run are primarily not missing aggregation logic, but low-maturity singleton gold groups where stronger evidence is still needed upstream.

## Best variants
- Best overall: `current_selection_control`
- Best for present_not_selected recovery: `current_selection_control`
- Recommended policy for this evaluated slice: `current_selection_control`

## Conservative conclusion
- For the current evaluated repository phase and current strict default, this bounded selection-layer policy sweep does **not** justify replacing the current control selection policy.
- Next meaningful progress on residual present-not-selected likely needs stronger per-branch quality signals (verifier/process quality) or upstream generation changes that increase multi-branch gold support, not support-only reweighting.
