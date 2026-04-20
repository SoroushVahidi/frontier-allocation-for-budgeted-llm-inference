# Hundred-case failure statistics: current full method vs reasoning_beam2

- Generated (UTC): `2026-04-20T22:04:16.355021+00:00`
- Output directory: `outputs/hundred_current_full_vs_best_failure_statistics_20260420T220416Z`

## Method resolution
- **Current full method**: `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1__deterministic_output_layer_repair_v1`
- **Best method (fixed for this report)**: `reasoning_beam2`

## Selection rule for the 100 cases
0. **Simulator surface (expanded, documented in `selection_manifest.json`)**: same benchmark mix as the 20-case builder, with per-seed subset size **96** (vs 40) and additional seeds `{101,113,137}` plus budgets `{14,16}` so 100 repair-consistent exact-loss cases exist under current exclusions.
1. **Eligibility**: On that grid, keep rows where the current full method is incorrect and `reasoning_beam2` is correct.
2. **De-duplication**: Group by `(dataset, example_id)`; score groups by support across the grid (loss_support_count, max_budget_with_loss, observability_priority, lexical id) exactly as the 20-case builder.
3. **Exclusions**: Union of the repo’s prior exact-failure manifests (see `selection_manifest.json`) plus any checked-in `twenty_exact_current_full_vs_best_fresh_20260420/*/selected_case_manifest.json` if present.
4. **Coverage-aware ordering**: Within each dataset, preserve the global rank order; merge datasets in **round-robin** (lexicographic dataset name) so early picks span benchmarks before going deeper in one dataset.
5. **Exact verification**: For each candidate group, try `(seed, budget)` rows in descending budget/seed order until a pair passes full observed-tree replay with deterministic output-layer repair where canonical grading still shows **ours wrong / beam2 correct** (stream tags `fresh_our` / `fresh_best` match the 20-case builder).

## Output files
- `outputs/hundred_current_full_vs_best_failure_statistics_20260420T220416Z/per_case_failure_statistics.json`
- `outputs/hundred_current_full_vs_best_failure_statistics_20260420T220416Z/aggregate_failure_statistics.json`
- `outputs/hundred_current_full_vs_best_failure_statistics_20260420T220416Z/failure_statistics_table.csv`
- `outputs/hundred_current_full_vs_best_failure_statistics_20260420T220416Z/selection_manifest.json`

## Aggregate: failure_type
- `absent_from_tree`: 78 (78.0%)
- `present_not_selected`: 22 (22.0%)

## Aggregate: dataset
- `HuggingFaceH4/MATH-500`: 27 (27.0%)
- `HuggingFaceH4/aime_2024`: 19 (19.0%)
- `olympiadbench`: 27 (27.0%)
- `openai/gsm8k`: 27 (27.0%)

## Aggregate: problem_regime_label
- `algebraic_manipulation`: 5 (5.0%)
- `counting_combinatorics`: 6 (6.0%)
- `geometry`: 14 (14.0%)
- `gsm8k_style_word_arithmetic`: 27 (27.0%)
- `number_theory`: 10 (10.0%)
- `other`: 38 (38.0%)

## Aggregate: error_geometry (multi-label; counts sum >100%)
- `near_miss`: 51 (51.0% of cases carry this tag)
- `arithmetic_slip`: 50 (50.0% of cases carry this tag)
- `wrong_local_neighborhood`: 22 (22.0% of cases carry this tag)
- `counting_error`: 19 (19.0% of cases carry this tag)
- `other`: 14 (14.0% of cases carry this tag)
- `sign_or_parity_error`: 1 (1.0% of cases carry this tag)

## Aggregate: best_method_advantage_type (multi-label)
- `better_budget_efficiency`: 85 (85.0% of cases carry this tag)
- `earlier_correct_entry`: 84 (84.0% of cases carry this tag)
- `less_collapse`: 69 (69.0% of cases carry this tag)
- `multiple_correct_beams`: 29 (29.0% of cases carry this tag)
- `better_selection`: 22 (22.0% of cases carry this tag)

## Correct-answer coverage (in our tree)
- `multiple`: 1 (1.0%)
- `none`: 78 (78.0%)
- `single`: 21 (21.0%)

## Same-family expansion severity (ours)
- repeated_same_family_present: **97 / 100** (97.0%)
- distribution summaries: see `aggregate_failure_statistics.json` under `distributions`

## Answer-group maturity (ours)
- See `alternative_answer_group_count_and_maturity` per case and `distributions.num_answer_groups` / `dominant_answer_group_share` in the table.

## Cross-tabs (excerpt)
- Full tables in `aggregate_failure_statistics.json` under `cross_tabs`.

## Representative examples
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_33` — **absent_from_tree** — error_geometry: `wrong_local_neighborhood, arithmetic_slip` — best_method_advantage: `earlier_correct_entry, less_collapse, better_budget_efficiency`
  - preview: 'If $3x + 2(1 + x) = 17$, what is the value of $6x + 5$?'
- `HuggingFaceH4__aime_2024__HuggingFaceH4_aime_2024_24` — **absent_from_tree** — error_geometry: `near_miss, arithmetic_slip` — best_method_advantage: `earlier_correct_entry, less_collapse, better_budget_efficiency`
  - preview: 'Jen enters a lottery by picking $4$ distinct numbers from $S=\\{1,2,3,\\cdots,9,10\\}.$ $4$ numbers are randomly chosen from $S.$ She wins a prize if at least two of her numbers were $2$ of the randomly chosen numbers, and wins the grand prize'
- `olympiadbench__Hothan_OlympiadBench_28` — **absent_from_tree** — error_geometry: `near_miss, arithmetic_slip` — best_method_advantage: `earlier_correct_entry, less_collapse, better_budget_efficiency`
  - preview: 'Compute the sum of all positive two-digit factors of $2^{32}-1$.'
- `openai__gsm8k__openai_gsm8k_10` — **absent_from_tree** — error_geometry: `near_miss, arithmetic_slip` — best_method_advantage: `earlier_correct_entry, multiple_correct_beams, less_collapse, better_budget_efficiency`
  - preview: "Two candidates are running for class representative at Sarai's school. If the winner got 3/4 of the votes and the total number of students who voted in the class was 80, calculate the number of votes the loser got."
- `olympiadbench__Hothan_OlympiadBench_90` — **present_not_selected** — error_geometry: `wrong_local_neighborhood` — best_method_advantage: `better_selection, better_budget_efficiency`
  - preview: 'Let $a, b, m, n$ be positive integers with $a m=b n=120$ and $a \\neq b$. In the coordinate plane, let $A=(a, m), B=(b, n)$, and $O=(0,0)$. If $X$ is a point in the plane such that $A O B X$ is a parallelogram, compute the minimum area of $A'
- `openai__gsm8k__openai_gsm8k_42` — **present_not_selected** — error_geometry: `near_miss, counting_error` — best_method_advantage: `better_selection, better_budget_efficiency`
  - preview: 'Gretchen has some coins. There are 30 more gold coins than silver coins. If she had 70 gold coins, how many coins did Gretchen have in total?'
- `openai__gsm8k__openai_gsm8k_47` — **present_not_selected** — error_geometry: `wrong_local_neighborhood` — best_method_advantage: `better_selection, earlier_correct_entry, better_budget_efficiency`
  - preview: 'Two sports coaches went shopping together. The baseball coach bought 9 new baseballs for $3 each. The basketball coach bought 8 new basketballs for $14 each. How much more did the basketball coach spend than the baseball coach?'
- `olympiadbench__Hothan_OlympiadBench_4` — **present_not_selected** — error_geometry: `other` — best_method_advantage: `better_selection, earlier_correct_entry, less_collapse, better_budget_efficiency`
  - preview: 'Given positive integers $m$ and $n \\geq m$, determine the largest number of dominoes $(1 \\times 2$ or $2 \\times 1$ rectangles) that can be placed on a rectangular board with $m$ rows and $2 n$ columns consisting of cells $(1 \\times 1$ squar'

## Conclusions
- Most losses are still driven by absent gold in our search tree (coverage) rather than output-layer errors, with repeated same-family expansion pressure remaining a common companion pattern.

