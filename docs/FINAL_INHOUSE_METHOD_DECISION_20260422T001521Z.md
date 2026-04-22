# Final in-house method decision (20260422T001521Z)

## Purpose
Finalize one single canonical **in-house-only** winner method and remove ambiguity about what “our method” means.

## Definition of “our method”
For this artifact, “our method” must be exactly one method that is:
- designed/implemented in this repository,
- non-external,
- and top-ranked on the strongest currently supported canonical matched surface.

## Eligible in-house methods
See: `outputs/final_inhouse_method_decision_20260422T001521Z/eligible_inhouse_methods.csv`.

Eligibility rule used:
- include internal methods with runnable artifacts on the selected canonical matched surface,
- exclude external baselines,
- exclude methods missing runnable/runtime support on the selected surface.

## Excluded methods and reasons
See: `outputs/final_inhouse_method_decision_20260422T001521Z/excluded_methods.csv`.

Key explicit exclusions:
- external baselines (`external_s1_budget_forcing`, `external_tale_prompt_budgeting`, `external_l1_exact`, `external_l1_max`, and other imported/literature baselines) are ineligible by definition.
- `reasoning_beam1` is excluded due to missing runnable artifact in current `build_frontier_strategies` registry.
- `strict_gate1` and `strict_gate2` are excluded from final matched ranking because their runtime keys are missing on the canonical full-ranking surface (documented contract incompatibility for this surface).

## Evidence surfaces considered
1. `docs/FINAL_STRICT_PHASED_DEFAULT_DECISION_EVAL_20260421T042913Z.md` and `outputs/final_strict_phased_default_decision_eval_20260421T042913Z/`.
2. `docs/CANONICAL_FULL_METHOD_RANKING_20260421T212948Z.md` and `outputs/canonical_full_method_ranking_20260421T212948Z/`.
3. `docs/TWENTY_EXACT_CURRENT_FULL_VS_BEST_FRESH_2026_04_20.md` (older narrow exact-loss slice for direct-adversary diagnostics).

## Conflict resolution across older vs newer bundles
- Older/narrow surfaces show `reasoning_beam2` as a strong adversary against earlier current-full variants.
- The stronger canonical matched surface for **final in-house ranking** is `canonical_full_method_ranking_20260421T212948Z`, which is broader and already integrates strict-phased finalists with the current promoted strict method.
- Therefore final winner selection is anchored to that broader canonical matched surface, not a narrow historical slice.

## Final in-house ranking
Source: `outputs/final_inhouse_method_decision_20260422T001521Z/inhouse_overall_ranking.csv`.

Top ranks:
1. `strict_f3` — mean_accuracy=0.658333
2. `strict_gate1_cap_k6` — mean_accuracy=0.652778
3. `broad_diversity_aggregation_strong_v1` — mean_accuracy=0.636111
4. `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_v1` — mean_accuracy=0.633333
5. `strict_f2` — mean_accuracy=0.622222
6. `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1__deterministic_output_layer_repair_v1` — mean_accuracy=0.613889
7. `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1` — mean_accuracy=0.602778
8. `reasoning_beam2` — mean_accuracy=0.586111
9. `self_consistency_3` — mean_accuracy=0.566667
10. `adaptive_min_expand_2` — mean_accuracy=0.558333
11. `reasoning_greedy` — mean_accuracy=0.458333
12. `adaptive_min_expand_1` — mean_accuracy=0.450000

## Final winner
**`strict_f3`** (rank #1 on canonical in-house-only matched ranking).

## Why that winner beat the strongest internal competitors
- `strict_f3` beats `strict_gate1_cap_k6` on overall mean accuracy on the canonical full matched surface.
- `strict_f3` also beats strong internal anchors from older families (including `reasoning_beam2`, `self_consistency_3`, `reasoning_greedy`, and adaptive-min-expand variants) on that same surface.
- Head-to-head table against top in-house competitors is provided at `outputs/final_inhouse_method_decision_20260422T001521Z/head_to_head_top_candidates.csv`.

## Explicit treatment of `reasoning_beam1` and `reasoning_beam2`
- `reasoning_beam1`: explicitly checked and excluded (not runnable / not maintained as a current runnable method on selected canonical surface).
- `reasoning_beam2`: explicitly included and evaluated where available as a serious in-house contender; on the final matched ranking surface it does **not** outrank `strict_f3` (mean accuracy 0.586111 vs 0.658333).

## Safe repository-facing conclusion
Among non-external repository-designed methods on the strongest current canonical matched surface, `strict_f3` is the single best in-house method and should be the repository’s one canonical “our method”.

## Exact wording to use from now on
**From now on, our method means `strict_f3`.**

## Exact artifact paths
- `outputs/final_inhouse_method_decision_20260422T001521Z/eligible_inhouse_methods.csv`
- `outputs/final_inhouse_method_decision_20260422T001521Z/excluded_methods.csv`
- `outputs/final_inhouse_method_decision_20260422T001521Z/inhouse_overall_ranking.csv`
- `outputs/final_inhouse_method_decision_20260422T001521Z/head_to_head_top_candidates.csv`
- `outputs/final_inhouse_method_decision_20260422T001521Z/decision_manifest.json`
- `docs/FINAL_INHOUSE_METHOD_DECISION_20260422T001521Z.md`
- `docs/CURRENT_OUR_METHOD_STATUS_20260422T001521Z.md`

## Final naming rule
- Chosen winner method name: `strict_f3`.
- This is now the repository’s single canonical in-house method.
- From now on **“our method”** refers to `strict_f3` unless a future explicit replacement artifact supersedes it.
