# Method Status Map (live-run and claim eligibility)

| method ID | runtime ID | status | runnable in live Cohere runner | eligible for paper headline claim | notes |
|---|---|---|---|---|---|
| strict_f3 | broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1 | manuscript-facing representative (internal) | yes | yes (when supported by canonical outputs) | Matched-surface representative method. |
| strict_gate1_cap_k6 | broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first_hard_max_family_expansions_cap_k6_v1_fixed_k6_control | canonical operational internal | yes | yes (context-dependent; canonical-surface guarded) | Broader operational default on different surface; do not overstate matched-surface margin. |
| strict_f2 | broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_coverage_forced_v1 | internal supporting variant | yes | conditional | Useful internal comparator; not standalone dominance evidence. |
| direct_reserve_semantic_frontier_v2 | direct_reserve_frontier_gate_v2 | internal diagnostic/promoted comparator | yes | no (diagnostic unless promoted) | Included in validated real-model method set for diagnostics. |
| direct_reserve_semantic_frontier_v2_selection_fix_v1 | direct_reserve_semantic_frontier_v2_selection_fix_v1 | internal diagnostic comparator | yes | no (diagnostic unless promoted) | Runnable; still supporting evidence by default. |
| direct_reserve_semantic_frontier_v2_thresholded_ordered | direct_reserve_semantic_frontier_v2_thresholded_ordered | excluded diagnostic-only | no | no | Diagnostic registry presence only; not runtime-present in live `build_frontier_strategies(...)`. |
| external_l1_max | external_l1_max | external baseline | yes | baseline reference only | Primary external comparator used in pairwise checks. |
| tale | external_tale_prompt_budgeting | external baseline | yes | baseline reference only | External adapter baseline. |
| s1 | external_s1_budget_forcing | external baseline | yes | baseline reference only | External adapter baseline. |
| self_consistency_3 | self_consistency_3 | external/self-consistency baseline | yes | baseline reference only | Baseline-style comparator for robustness context. |

## Notes
- “Eligible for paper headline claim” requires consistency with `docs/PAPER_SOURCE_OF_TRUTH.md` and canonical artifact outputs.
- Real-model use alone does not promote a method to headline claim status.
