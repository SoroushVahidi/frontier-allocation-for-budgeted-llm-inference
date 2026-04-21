# Final strict phased cap K=6/7/8 follow-up evaluation (20260421T043950Z)

## Exact method definitions
- `strict_gate1`: `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first__deterministic_output_layer_repair_v1`
- `strict_gate1_cap_k6`: `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first_hard_max_family_expansions_cap_k6_v1__deterministic_output_layer_repair_v1`
- `strict_gate1_cap_k7`: `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first_hard_max_family_expansions_cap_k7_v1__deterministic_output_layer_repair_v1`
- `strict_gate1_cap_k8`: `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first_hard_max_family_expansions_cap_k8_v1__deterministic_output_layer_repair_v1`

## Exact broader matched strict-phased evaluation surface
- datasets: ['openai/gsm8k', 'HuggingFaceH4/MATH-500', 'HuggingFaceH4/aime_2024', 'olympiadbench']
- subset_size per (dataset, seed): 20
- seeds: [11, 23]
- budgets: [6, 8]
- total matched cases: dataset_count × seed_count × budget_count × subset_size
- strict phased law: finish F1 before F2 before F3, with normal in-phase controller ordering preserved

## Aggregate comparison table

| method | accuracy | absent_from_tree | present_not_selected | output_layer_mismatch | repeated-same-family-present | gold_in_tree | avg_actions | avg_expansions | avg_verifications | avg_max_family_share | avg_longest_same_family_run | cap_bound_case_count | dominant_family_hit_cap_case_count |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| strict_gate1 | 0.6469 | 75 | 38 | 0 | 264 | 245 | 5.850 | 5.416 | 0.434 | 0.000 | 0.000 | 0 | 0 |
| strict_gate1_cap_k6 | 0.6719 | 76 | 29 | 0 | 266 | 244 | 5.872 | 5.419 | 0.453 | 0.000 | 0.000 | 43 | 76 |
| strict_gate1_cap_k7 | 0.6156 | 99 | 24 | 0 | 268 | 221 | 5.841 | 5.350 | 0.491 | 0.000 | 0.000 | 0 | 28 |
| strict_gate1_cap_k8 | 0.6625 | 81 | 26 | 1 | 261 | 239 | 5.719 | 5.247 | 0.472 | 0.000 | 0.000 | 0 | 0 |

## Dataset-wise table

| dataset | method | accuracy | absent_from_tree | present_not_selected | repeated-same-family-present | gold_in_tree | avg_actions | avg_expansions | avg_verifications |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| openai/gsm8k | strict_gate1 | 0.6750 | 18 | 8 | 64 | 62 | 5.750 | 5.287 | 0.463 |
| openai/gsm8k | strict_gate1_cap_k6 | 0.7000 | 18 | 6 | 68 | 62 | 6.025 | 5.600 | 0.425 |
| openai/gsm8k | strict_gate1_cap_k7 | 0.5500 | 26 | 10 | 68 | 54 | 5.912 | 5.487 | 0.425 |
| openai/gsm8k | strict_gate1_cap_k8 | 0.6625 | 20 | 7 | 69 | 60 | 5.825 | 5.312 | 0.512 |
| HuggingFaceH4/MATH-500 | strict_gate1 | 0.6250 | 23 | 7 | 67 | 57 | 5.912 | 5.487 | 0.425 |
| HuggingFaceH4/MATH-500 | strict_gate1_cap_k6 | 0.6500 | 20 | 8 | 65 | 60 | 5.800 | 5.375 | 0.425 |
| HuggingFaceH4/MATH-500 | strict_gate1_cap_k7 | 0.6750 | 22 | 4 | 66 | 58 | 5.737 | 5.112 | 0.625 |
| HuggingFaceH4/MATH-500 | strict_gate1_cap_k8 | 0.6250 | 23 | 7 | 66 | 57 | 5.713 | 5.263 | 0.450 |
| HuggingFaceH4/aime_2024 | strict_gate1 | 0.6750 | 14 | 12 | 66 | 66 | 5.850 | 5.350 | 0.500 |
| HuggingFaceH4/aime_2024 | strict_gate1_cap_k6 | 0.6625 | 18 | 9 | 66 | 62 | 5.750 | 5.263 | 0.487 |
| HuggingFaceH4/aime_2024 | strict_gate1_cap_k7 | 0.5125 | 32 | 7 | 69 | 48 | 5.987 | 5.450 | 0.537 |
| HuggingFaceH4/aime_2024 | strict_gate1_cap_k8 | 0.7125 | 18 | 4 | 62 | 62 | 5.662 | 5.062 | 0.600 |
| olympiadbench | strict_gate1 | 0.6125 | 20 | 11 | 67 | 60 | 5.888 | 5.537 | 0.350 |
| olympiadbench | strict_gate1_cap_k6 | 0.6750 | 20 | 6 | 67 | 60 | 5.912 | 5.438 | 0.475 |
| olympiadbench | strict_gate1_cap_k7 | 0.7250 | 19 | 3 | 65 | 61 | 5.725 | 5.350 | 0.375 |
| olympiadbench | strict_gate1_cap_k8 | 0.6500 | 20 | 8 | 64 | 60 | 5.675 | 5.350 | 0.325 |

## Failure-decomposition table

| method | absent_from_tree | present_not_selected | output_layer_mismatch |
|---|---:|---:|---:|
| strict_gate1 | 75 | 38 | 0 |
| strict_gate1_cap_k6 | 76 | 29 | 0 |
| strict_gate1_cap_k7 | 99 | 24 | 0 |
| strict_gate1_cap_k8 | 81 | 26 | 1 |

## Cost / budget table

| method | avg_actions | avg_expansions | avg_verifications | cap_bound_case_count | dominant_family_hit_cap_case_count |
|---|---:|---:|---:|---:|---:|
| strict_gate1 | 5.850 | 5.416 | 0.434 | 0 | 0 |
| strict_gate1_cap_k6 | 5.872 | 5.419 | 0.453 | 43 | 76 |
| strict_gate1_cap_k7 | 5.841 | 5.350 | 0.491 | 0 | 28 |
| strict_gate1_cap_k8 | 5.719 | 5.247 | 0.472 | 0 | 0 |

## Head-to-head K comparisons
- strict_gate1_cap_k6 vs strict_gate1: `{'improved': 76, 'worsened': 68, 'unchanged': 176}`
- strict_gate1_cap_k7 vs strict_gate1: `{'improved': 70, 'worsened': 80, 'unchanged': 170}`
- strict_gate1_cap_k8 vs strict_gate1: `{'improved': 67, 'worsened': 62, 'unchanged': 191}`
- strict_gate1_cap_k7 vs strict_gate1_cap_k6: `{'improved': 59, 'worsened': 77, 'unchanged': 184}`
- strict_gate1_cap_k8 vs strict_gate1_cap_k7: `{'improved': 83, 'worsened': 68, 'unchanged': 169}`
- strict_gate1_cap_k8 vs strict_gate1_cap_k6: `{'improved': 68, 'worsened': 71, 'unchanged': 181}`

## Required decision questions
1. Does `K = 7` beat `K = 6` on the broader matched surface? **False**
2. Does `K = 8` beat `K = 7`? **True**
3. Does any capped variant beat uncapped `strict_gate1` clearly enough to justify keeping a cap in the final default? **True**
4. Does performance appear to plateau as K increases? **False**
5. Does larger K simply revert toward uncapped behavior? **True**
6. Should the repository keep `K = 6` as final default, move to `K = 7` or `K = 8`, or drop cap entirely? **strict_gate1_cap_k6**

## Honest final recommendation
Recommended method by conservative tie-break rule (accuracy -> absent_from_tree -> collapse -> actions): **strict_gate1_cap_k6**.

## Final cap recommendation
- recommended cap choice: **strict_gate1_cap_k6**
- one-paragraph justification: On the same broader matched strict-phased surface used for default finalization, strict_gate1_cap_k6 is the strongest conservative compromise after evaluating uncapped strict_gate1 and K=6/7/8 (plus optional higher K if included), while preserving strict phased-law compliance and stable failure/cost trade-offs.
- whether the cap should remain part of the broad default model: **True**
- one sentence explaining why the neighboring K values were not chosen: Neighboring K values either did not improve enough on broader matched accuracy/failure mix or moved closer to uncapped behavior without clear net benefit.