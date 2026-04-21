# Final strict phased default decision evaluation (20260421T042913Z)

## Scope
- Broader matched surface over canonical mix (including olympiadbench) rather than the frozen 100-case slice.
- Strict phased law enforced for all strict variants (F1→F2→F3), with controller-driven in-phase ordering.

## Methods compared
- `baseline`: `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1__deterministic_output_layer_repair_v1`
- `strict_f2`: `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_coverage_forced_v1__deterministic_output_layer_repair_v1`
- `strict_f3`: `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1__deterministic_output_layer_repair_v1`
- `strict_gate1`: `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first__deterministic_output_layer_repair_v1`
- `strict_gate2`: `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_gate_v2_budget_aware_rescue__deterministic_output_layer_repair_v1`
- `strict_gate1_cap_k6`: `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first_hard_max_family_expansions_cap_k6_v1__deterministic_output_layer_repair_v1`

## Aggregate comparison table

| method | accuracy | absent_from_tree | present_not_selected | output_layer_mismatch | repeated-same-family-present | gold_in_tree | avg_actions | avg_expansions | avg_verifications | improved | worsened | unchanged |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 0.6500 | 90 | 22 | 0 | 302 | 230 | 6.197 | 5.575 | 0.622 | 0 | 0 | 0 |
| strict_f2 | 0.6531 | 85 | 26 | 0 | 271 | 235 | 5.959 | 5.487 | 0.472 | 76 | 75 | 169 |
| strict_f3 | 0.6094 | 98 | 27 | 0 | 282 | 222 | 6.116 | 5.631 | 0.484 | 70 | 83 | 167 |
| strict_gate1 | 0.6469 | 75 | 38 | 0 | 264 | 245 | 5.850 | 5.416 | 0.434 | 78 | 79 | 163 |
| strict_gate2 | 0.5781 | 102 | 33 | 0 | 267 | 218 | 5.872 | 5.438 | 0.434 | 67 | 90 | 163 |
| strict_gate1_cap_k6 | 0.6719 | 76 | 29 | 0 | 266 | 244 | 5.872 | 5.419 | 0.453 | 83 | 76 | 161 |

## Dataset-wise table

| dataset | method | accuracy | absent_from_tree | present_not_selected | output_layer_mismatch | repeated-same-family-present | gold_in_tree | avg_actions | avg_expansions | avg_verifications |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openai/gsm8k | baseline | 0.6500 | 22 | 6 | 0 | 77 | 58 | 6.350 | 5.737 | 0.613 |
| openai/gsm8k | strict_f2 | 0.6750 | 19 | 7 | 0 | 64 | 61 | 5.787 | 5.362 | 0.425 |
| openai/gsm8k | strict_f3 | 0.5375 | 29 | 8 | 0 | 73 | 51 | 6.300 | 5.700 | 0.600 |
| openai/gsm8k | strict_gate1 | 0.6750 | 18 | 8 | 0 | 64 | 62 | 5.750 | 5.287 | 0.463 |
| openai/gsm8k | strict_gate2 | 0.6125 | 21 | 10 | 0 | 61 | 59 | 5.375 | 4.888 | 0.487 |
| openai/gsm8k | strict_gate1_cap_k6 | 0.7000 | 18 | 6 | 0 | 68 | 62 | 6.025 | 5.600 | 0.425 |
| HuggingFaceH4/MATH-500 | baseline | 0.6375 | 22 | 7 | 0 | 74 | 58 | 5.862 | 5.225 | 0.637 |
| HuggingFaceH4/MATH-500 | strict_f2 | 0.6125 | 25 | 6 | 0 | 68 | 55 | 6.025 | 5.537 | 0.487 |
| HuggingFaceH4/MATH-500 | strict_f3 | 0.6000 | 24 | 8 | 0 | 68 | 56 | 5.900 | 5.475 | 0.425 |
| HuggingFaceH4/MATH-500 | strict_gate1 | 0.6250 | 23 | 7 | 0 | 67 | 57 | 5.912 | 5.487 | 0.425 |
| HuggingFaceH4/MATH-500 | strict_gate2 | 0.5250 | 29 | 9 | 0 | 69 | 51 | 6.000 | 5.612 | 0.388 |
| HuggingFaceH4/MATH-500 | strict_gate1_cap_k6 | 0.6500 | 20 | 8 | 0 | 65 | 60 | 5.800 | 5.375 | 0.425 |
| HuggingFaceH4/aime_2024 | baseline | 0.5875 | 30 | 3 | 0 | 77 | 50 | 6.213 | 5.500 | 0.713 |
| HuggingFaceH4/aime_2024 | strict_f2 | 0.6500 | 19 | 9 | 0 | 72 | 61 | 6.062 | 5.575 | 0.487 |
| HuggingFaceH4/aime_2024 | strict_f3 | 0.7000 | 19 | 5 | 0 | 71 | 61 | 6.150 | 5.725 | 0.425 |
| HuggingFaceH4/aime_2024 | strict_gate1 | 0.6750 | 14 | 12 | 0 | 66 | 66 | 5.850 | 5.350 | 0.500 |
| HuggingFaceH4/aime_2024 | strict_gate2 | 0.5500 | 32 | 4 | 0 | 66 | 48 | 5.987 | 5.600 | 0.388 |
| HuggingFaceH4/aime_2024 | strict_gate1_cap_k6 | 0.6625 | 18 | 9 | 0 | 66 | 62 | 5.750 | 5.263 | 0.487 |
| olympiadbench | baseline | 0.7250 | 16 | 6 | 0 | 74 | 64 | 6.362 | 5.838 | 0.525 |
| olympiadbench | strict_f2 | 0.6750 | 22 | 4 | 0 | 67 | 58 | 5.963 | 5.475 | 0.487 |
| olympiadbench | strict_f3 | 0.6000 | 26 | 6 | 0 | 70 | 54 | 6.112 | 5.625 | 0.487 |
| olympiadbench | strict_gate1 | 0.6125 | 20 | 11 | 0 | 67 | 60 | 5.888 | 5.537 | 0.350 |
| olympiadbench | strict_gate2 | 0.6250 | 20 | 10 | 0 | 71 | 60 | 6.125 | 5.650 | 0.475 |
| olympiadbench | strict_gate1_cap_k6 | 0.6750 | 20 | 6 | 0 | 67 | 60 | 5.912 | 5.438 | 0.475 |

## Failure-decomposition table

| method | absent_from_tree | present_not_selected | output_layer_mismatch |
|---|---:|---:|---:|
| baseline | 90 | 22 | 0 |
| strict_f2 | 85 | 26 | 0 |
| strict_f3 | 98 | 27 | 0 |
| strict_gate1 | 75 | 38 | 0 |
| strict_gate2 | 102 | 33 | 0 |
| strict_gate1_cap_k6 | 76 | 29 | 0 |

## Cost / budget table

| method | avg_actions | avg_expansions | avg_verifications | strict_phase_law_violations |
|---|---:|---:|---:|---:|
| baseline | 6.197 | 5.575 | 0.622 | 0 |
| strict_f2 | 5.959 | 5.487 | 0.472 | 0 |
| strict_f3 | 6.116 | 5.631 | 0.484 | 0 |
| strict_gate1 | 5.850 | 5.416 | 0.434 | 0 |
| strict_gate2 | 5.872 | 5.438 | 0.434 | 0 |
| strict_gate1_cap_k6 | 5.872 | 5.419 | 0.453 | 0 |

## Head-to-head finalist comparison
- strict_gate1 vs strict_gate2: `{'improved': 95, 'unchanged': 152, 'worsened': 73}`
- strict_gate2 vs strict_f3: `{'worsened': 81, 'unchanged': 168, 'improved': 71}`
- strict_gate1 vs strict_f3: `{'unchanged': 178, 'worsened': 65, 'improved': 77}`
- strict_f3 vs strict_f2: `{'unchanged': 158, 'worsened': 88, 'improved': 74}`

## Required decision questions
1. Does `strict_gate1` beat `strict_gate2` on the broader matched surface? **True**
2. Does `strict_gate2` beat `strict_f3` on the broader matched surface? **False**
3. Does `strict_gate1` beat `strict_f3` on the broader matched surface? **True**
4. Is `strict_f2` still competitive enough to remain the simpler safer default? **False**
5. Is `K=6` competitive enough to remain in final conversation? **True**
6. Best compromise method across broader accuracy + failures + collapse + cost: **strict_gate1_cap_k6**.
7. Final default promoted model: **strict_gate1_cap_k6** (`broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first_hard_max_family_expansions_cap_k6_v1__deterministic_output_layer_repair_v1`).

## Capped-variant relevance decision
- If `strict_gate1_cap_k6` is present, it was included only as the strongest capped finalist for relevance-checking under the same broader matched scaffold.
- Cap variants weaker than K=6 are intentionally excluded from this final default pass.

## Final default recommendation
- recommended default model name: **strict_gate1_cap_k6**
- one-paragraph justification: On this broader matched surface, `strict_gate1_cap_k6` is the strongest conservative compromise by the configured decision rule (maximize accuracy, then reduce absent-from-tree and repeated-same-family collapse, then prefer lower budget cost), while preserving strict phased-law behavior checks in this run.
- whether the recommendation is broad-default or hard-regime-default only: **broad-default**
- one sentence explaining why the other leading candidate(s) were not chosen: The nearest alternatives either trailed on overall broader matched accuracy or required more compute / showed worse failure-mix tradeoffs under the same strict-law constraints.