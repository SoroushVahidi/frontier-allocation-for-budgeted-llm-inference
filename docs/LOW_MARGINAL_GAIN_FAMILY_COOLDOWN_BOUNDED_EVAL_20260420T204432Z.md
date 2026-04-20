# Low-marginal-gain family cooldown bounded eval (20260420T204432Z)

## Insertion point
- Inserted inside `GlobalDiversityAggregationController._anti_collapse_priority_adjustments` as a conditional same-family control on the promoted repeat-expansion line.

## Control definition
- Name: `low_marginal_gain_family_cooldown` (soft default) plus optional `hard_block_ablation`.
- Trigger: repeated same-family selection + recent family rolling marginal gain below threshold.
- Rolling marginal gain: mean of recent expansion score deltas (`score_after - score_before`, clipped at 0) over a short window.
- Answer-group-aware: threshold increases when many active siblings share the same answer group.
- Override: if top-support is high and adjusted family priority still beats alternatives by override margin.

## Parameters (soft)
- window_size=3, min_threshold=0.015, consecutive_family_trigger=4
- cooldown_steps=2, penalty_strength=0.14
- override_top_support_min=0.74, override_margin=0.12

## Comparison table
| Method | Accuracy | Absent-from-tree | Present-not-selected | Mean repeat-same-family rate | Mean actions | Mean expansions | Mean verifications |
|---|---:|---:|---:|---:|---:|---:|---:|
| `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1` | 0.500 | 7 | 3 | 0.672 | 9.65 | 8.85 | 0.80 |
| `broad_diversity_aggregation_strong_v1_anti_collapse_repeat_expansion_low_marginal_gain_cooldown_v1` | 0.650 | 6 | 1 | 0.681 | 9.65 | 8.10 | 1.55 |
| `broad_diversity_aggregation_strong_v1_anti_collapse_repeat_expansion_low_marginal_gain_hard_block_ablation_v1` | 0.650 | 4 | 3 | 0.619 | 10.50 | 9.00 | 1.50 |

## Improved cases (soft vs baseline): 6
- `openai/gsm8k / openai_gsm8k_19` (baseline failure=`absent_from_tree`, soft_trigger_count=0)
- `HuggingFaceH4/MATH-500 / HuggingFaceH4_MATH-500_34` (baseline failure=`present_but_not_selected`, soft_trigger_count=2)
- `HuggingFaceH4/aime_2024 / HuggingFaceH4_aime_2024_14` (baseline failure=`absent_from_tree`, soft_trigger_count=2)
- `openai/gsm8k / openai_gsm8k_7` (baseline failure=`present_but_not_selected`, soft_trigger_count=1)
- `HuggingFaceH4/MATH-500 / HuggingFaceH4_MATH-500_15` (baseline failure=`present_but_not_selected`, soft_trigger_count=2)
- `HuggingFaceH4/MATH-500 / HuggingFaceH4_MATH-500_37` (baseline failure=`absent_from_tree`, soft_trigger_count=0)

## Harmed cases (soft vs baseline): 3
- `HuggingFaceH4/aime_2024 / HuggingFaceH4_aime_2024_20` (soft failure=`absent_from_tree`, soft_block_count=0, soft_override_count=0)
- `openai/gsm8k / openai_gsm8k_36` (soft failure=`present_but_not_selected`, soft_block_count=0, soft_override_count=0)
- `HuggingFaceH4/MATH-500 / HuggingFaceH4_MATH-500_36` (soft failure=`absent_from_tree`, soft_block_count=0, soft_override_count=0)

## Conclusion
- Keep if soft control reduces collapse proxies and absent-from-tree failures without a meaningful accuracy drop; otherwise tune threshold/cooldown and avoid hard-block default.
