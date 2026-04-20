# Current ranking and competitive status (2026-04-20)

## Purpose

This note is the shortest current answer to:
- which method is best on the latest matched comparison bundle,
- where the latest integrated promoted method currently ranks,
- and what the clearest competitive bottleneck is now.

## Current matched comparison answer

On the current matched comparison bundle, the latest integrated full method is **not** the best overall method.

### Current #1 on the matched surface
- `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_v1`

### Current latest integrated full method
- base promoted line: `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1`
- evaluated full alias in the latest bundle: `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1__deterministic_output_layer_repair_v1`

### Current overall rank of the latest integrated full method
- **#3** on the matched bundle used in `CURRENT_FULL_METHOD_COMPARISON_BUNDLE_STATUS_2026_04_20.md`

## Important interpretation

This means:
- the deterministic output-layer repair is useful and real,
- but it does **not** by itself make the latest integrated method the strongest overall method on the current broad matched surface,
- and the broad-family repeat-fine variant without the full integrated stack still performs better overall in that comparison bundle.

## Strongest current competitor picture

There are now two different competitor views that should not be conflated:

### 1. Broad matched ranking view
In the latest full comparison bundle, the top overall method is the strong repeat-fine broad-family variant above.

### 2. Fresh exact current-loss-set view
In the fresh exact loss-set builder for the latest full method, the best direct comparison method on that fresh surface was `reasoning_beam2`.

So:
- `reasoning_beam2` is the strongest **direct adversary** on that fresh loss-set surface,
- while the repeat-fine broad-family variant is still the strongest **overall matched bundle leader** in the latest broad ranking artifact.

## Current bottleneck implied by the competitive picture

The current strongest broad bottleneck is no longer primarily output-layer mismatch.

The fresh exact loss-set against the best direct comparison method shows that many remaining failures are still shaped by:
- correct answer absent from our tree,
- repeated same-family expansion,
- and a smaller but still important slice where the correct answer is in our tree but not selected.

## Safe one-paragraph summary

The latest integrated promoted method is promising but is not the best overall method in the current broad matched comparison bundle. The strongest broad matched leader is still a strong repeat-fine broad-family variant, while the strongest direct adversary on the fresh exact current-loss surface is `reasoning_beam2`. The next method work should therefore target the remaining tree-generation and branch-family-monopolization failures rather than assume that the output-layer repair alone closes the competitive gap.

## Cross-links

- `CURRENT_FULL_METHOD_COMPARISON_BUNDLE_STATUS_2026_04_20.md`
- `TWENTY_EXACT_CURRENT_FULL_METHOD_FAILURES_VS_BEST_2026_04_20.md`
- `CURRENT_FAILURE_OUTPUT_LAYER_REPAIR_STATUS_2026_04_20.md`
- `CURRENT_RESULTS_AND_ARTIFACTS_INDEX_2026_04_20.md`
