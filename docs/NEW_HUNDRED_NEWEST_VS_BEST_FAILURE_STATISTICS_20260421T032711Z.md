# New hundred-case failure statistics: newest strict-phased method vs best exact-loss comparator

- Generated (UTC): `2026-04-21T03:27:11.841813+00:00`
- Output directory: `outputs/new_hundred_newest_vs_best_failure_statistics_20260421T032711Z`

## Method resolution
- **Selected newest method**: `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_coverage_forced_v1__deterministic_output_layer_repair_v1`
- **Selected best comparator for exact-loss surface**: `reasoning_beam2`
- **Resolution evidence distinction**: exact-loss comparator and broad/light bundle leaders are treated separately; details recorded in `selection_manifest.json`.
- **Comparator distinction callout**: fresh exact-loss style artifacts identify `reasoning_beam2` as direct adversary, whereas older broader light bundles could rank methods like `self_consistency_3` higher on mean accuracy-over-budgets.
- **Strict gate ambiguity handling**: Gate 1 and Gate 2 were explicitly reviewed from newest strict-phased docs, then the broader strict-phased default decision artifact was used to pick the current newest method for this run.

## Selection rule for the 100 cases
0. **Simulator surface (expanded, documented in `selection_manifest.json`)**: same benchmark mix as the 20-case builder, with per-seed subset size 96 (vs 40) and additional seeds `{101,113,137}` plus budgets `{14,16}` to ensure 100 repair-consistent exact-loss cases exist under current exclusions.
1. **Eligibility**: On that grid, keep rows where the newest selected method is incorrect and `reasoning_beam2` is correct.
2. **De-duplication**: Group by `(dataset, example_id)`; score groups by support across the grid (loss_support_count, max_budget_with_loss, observability_priority, lexical id) exactly as the 20-case builder.
3. **Exclusions**: Union of the repo’s prior exact-failure manifests (see `selection_manifest.json`) plus any checked-in `twenty_exact_current_full_vs_best_fresh_20260420/*/selected_case_manifest.json` if present.
4. **Coverage-aware ordering**: Within each dataset, preserve the global rank order; merge datasets in **round-robin** (lexicographic dataset name) so early picks span benchmarks before going deeper in one dataset.
5. **Exact verification**: For each candidate group, try `(seed, budget)` rows in descending budget/seed order until a pair passes full observed-tree replay with deterministic output-layer repair where canonical grading still shows **ours wrong / reasoning_beam2 correct** (stream tags `fresh_our` / `fresh_best` match the 20-case builder).

## Output files
- `outputs/new_hundred_newest_vs_best_failure_statistics_20260421T032711Z/per_case_failure_statistics.json`
- `outputs/new_hundred_newest_vs_best_failure_statistics_20260421T032711Z/aggregate_failure_statistics.json`
- `outputs/new_hundred_newest_vs_best_failure_statistics_20260421T032711Z/failure_statistics_table.csv`
- `outputs/new_hundred_newest_vs_best_failure_statistics_20260421T032711Z/selection_manifest.json`

## Aggregate: failure_type
- `absent_from_tree`: 74 (74.0%)
- `output_or_extraction_mismatch`: 1 (1.0%)
- `present_not_selected`: 25 (25.0%)

## Aggregate: dataset
- `HuggingFaceH4/MATH-500`: 34 (34.0%)
- `olympiadbench`: 33 (33.0%)
- `openai/gsm8k`: 33 (33.0%)

## Aggregate: problem_regime_label
- `algebraic_manipulation`: 9 (9.0%)
- `counting_combinatorics`: 5 (5.0%)
- `geometry`: 2 (2.0%)
- `gsm8k_style_word_arithmetic`: 33 (33.0%)
- `number_theory`: 4 (4.0%)
- `other`: 44 (44.0%)
- `symbolic_series_or_formula`: 3 (3.0%)

## Aggregate: error_geometry (multi-label; counts sum >100%)
- `arithmetic_slip`: 52 (52.0% of cases carry this tag)
- `near_miss`: 49 (49.0% of cases carry this tag)
- `counting_error`: 23 (23.0% of cases carry this tag)
- `wrong_local_neighborhood`: 18 (18.0% of cases carry this tag)
- `other`: 6 (6.0% of cases carry this tag)
- `sign_or_parity_error`: 4 (4.0% of cases carry this tag)

## Aggregate: best_method_advantage_type (multi-label)
- `earlier_correct_entry`: 80 (80.0% of cases carry this tag)
- `better_budget_efficiency`: 68 (68.0% of cases carry this tag)
- `less_collapse`: 40 (40.0% of cases carry this tag)
- `multiple_correct_beams`: 30 (30.0% of cases carry this tag)
- `better_selection`: 26 (26.0% of cases carry this tag)

## Correct-answer coverage (in our tree)
- `none`: 74 (74.0%)
- `single`: 26 (26.0%)

## Same-family expansion severity (ours)
- repeated_same_family_present: **72 / 100** (72.0%)
- distribution summaries: see `aggregate_failure_statistics.json` under `distributions`

## Answer-group maturity (ours)
- See `alternative_answer_group_count_and_maturity` per case and `distributions.num_answer_groups` / `dominant_answer_group_share` in the table.

## Cross-tabs (excerpt)
- Full tables in `aggregate_failure_statistics.json` under `cross_tabs`.

## Representative examples
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_43` — **absent_from_tree** — error_geometry: `near_miss, arithmetic_slip` — best_method_advantage: `earlier_correct_entry, less_collapse, better_budget_efficiency`
  - preview: 'Find all the integer roots of \\[x^4 + 5x^3 + 9x^2 - x - 14 = 0.\\]Enter all the integer roots, separated by commas.'
- `openai__gsm8k__openai_gsm8k_35` — **absent_from_tree** — error_geometry: `counting_error` — best_method_advantage: `earlier_correct_entry, better_budget_efficiency`
  - preview: 'Kris is trying to earn a video game achievement for playing a total of 30 hours. If Kris plays for half an hour every day for 2 weeks then plays for 2 hours every day for a week, how many hours does she still need to play to earn the achiev'
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_73` — **absent_from_tree** — error_geometry: `near_miss, arithmetic_slip` — best_method_advantage: `earlier_correct_entry, less_collapse, better_budget_efficiency`
  - preview: 'The sum of the digits of a two-digit number is $13.$ The difference between the number and the number with its digits reversed is $27.$ What is the sum of the original number and the number with its digits reversed?'
- `olympiadbench__Hothan_OlympiadBench_51` — **absent_from_tree** — error_geometry: `near_miss, arithmetic_slip` — best_method_advantage: `earlier_correct_entry, less_collapse, better_budget_efficiency`
  - preview: 'Without using a calculator, determine positive integers $m$ and $n$ for which  $$ \\sin ^{6} 1^{\\circ}+\\sin ^{6} 2^{\\circ}+\\sin ^{6} 3^{\\circ}+\\cdots+\\sin ^{6} 87^{\\circ}+\\sin ^{6} 88^{\\circ}+\\sin ^{6} 89^{\\circ}=\\frac{m}{n} $$  (The sum on '
- `openai__gsm8k__openai_gsm8k_30` — **absent_from_tree** — error_geometry: `near_miss, counting_error` — best_method_advantage: `earlier_correct_entry, multiple_correct_beams`
  - preview: "Bahati, Azibo, and Dinar each contributed to their team's 45 points. Bahati scored the most points and it was 20 more than Azibo scored and 10 more points than Dinar scored. How many points did Azibo score?"
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_42` — **output_or_extraction_mismatch** — error_geometry: `near_miss, arithmetic_slip` — best_method_advantage: `better_selection, better_budget_efficiency`
  - preview: 'A regular octagon has the same perimeter as the regular hexagon shown here with side length 16 cm.  How long is each side of the octagon? [asy]size(80); pair A = dir(120); pair B=dir(60); pair M=(A+B)/2; draw(dir(360)--B--A--dir(180)--dir(2'
- `olympiadbench__Hothan_OlympiadBench_71` — **present_not_selected** — error_geometry: `near_miss, arithmetic_slip` — best_method_advantage: `better_selection, less_collapse, better_budget_efficiency`
  - preview: 'Compute the sum of all real numbers $x$ such that  $$ \\left\\lfloor\\frac{x}{2}\\right\\rfloor-\\left\\lfloor\\frac{x}{3}\\right\\rfloor=\\frac{x}{7} $$'
- `olympiadbench__Hothan_OlympiadBench_33` — **present_not_selected** — error_geometry: `wrong_local_neighborhood, arithmetic_slip` — best_method_advantage: `better_selection`
  - preview: 'The taxicab distance between points $A=\\left(x_{A}, y_{A}\\right)$ and $B=\\left(x_{B}, y_{B}\\right)$ is defined as $d(A, B)=$ $\\left|x_{A}-x_{B}\\right|+\\left|y_{A}-y_{B}\\right|$. Given some $s>0$ and points $A=\\left(x_{A}, y_{A}\\right)$ and '
- `HuggingFaceH4__MATH-500__HuggingFaceH4_MATH-500_18` — **present_not_selected** — error_geometry: `near_miss, arithmetic_slip` — best_method_advantage: `better_selection, earlier_correct_entry, better_budget_efficiency`
  - preview: 'Let $x_1,$ $x_2,$ $x_3,$ $y_1,$ $y_2,$ and $y_3$ be real numbers such that \\begin{align*} (x_1 - x_2)^2 + (y_1 - y_2)^2 &= 9, \\\\ (x_1 - x_3)^2 + (y_1 - y_3)^2 &= 16, \\\\ (x_2 - x_3)^2 + (y_2 - y_3)^2 &= 25. \\end{align*}Find $\\begin{vmatrix} '
- `olympiadbench__Hothan_OlympiadBench_92` — **present_not_selected** — error_geometry: `sign_or_parity_error, arithmetic_slip` — best_method_advantage: `better_selection`
  - preview: 'Let $n$ be a given positive integer. In the Cartesian plane, each lattice point with nonnegative coordinates initially contains a butterfly, and there are no other butterflies. The neighborhood of a lattice point $c$ consists of all lattice'
- `olympiadbench__Hothan_OlympiadBench_27` — **present_not_selected** — error_geometry: `near_miss, arithmetic_slip` — best_method_advantage: `better_selection, better_budget_efficiency`
  - preview: 'Let $T$ be a rational number. Let $a, b$, and $c$ be the three solutions of the equation $x^{3}-20 x^{2}+19 x+T=0$. Compute $a^{2}+b^{2}+c^{2}$.'

## Conclusions
- Most losses are still driven by absent gold in our search tree (coverage) rather than output-layer errors, with repeated same-family expansion pressure remaining a common companion pattern.

